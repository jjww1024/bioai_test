# -*- coding: utf-8 -*-
"""18번 재설계판 — decoy를 빼고 실측 데이터만으로 지문과 분할을 비교한다.

18번(첫 시도)이 실패한 이유:
  학습셋 negative 2,741개 중 2,531개가 decoy였다. decoy는 active와 Tanimoto
  <=0.35로 '일부러 안 닮게' 뽑은 분자라 active와 구별하기가 너무 쉽다.
  그 결과 지문 5종이 전부 AUC 0.997~0.999, BEDROC 1.000으로 포화돼
  표현 간 차이를 전혀 분별하지 못했다. 분할을 바꿔도 마찬가지였다.
  (07번 스크립트 docstring이 이미 경고해 둔 함정이다.)

이번 설계:
  - decoy 전부 제외. 실제로 측정된 IC50만 쓴다 (2,673개)
  - 라벨은 Cockroft와 같은 1 µM 기준 → active 1,915 / inactive 758
  - 분할 그룹을 Murcko 골격이 아니라 Butina 군집(Tanimoto 0.6)으로 잡는다.
    18번에서 Murcko 분할이 최근접 유사도를 0.723→0.639 로밖에 못 떨어뜨렸는데,
    유사체가 치환기 하나 차이로 서로 다른 Murcko 골격이 되어 폴드 사이로
    새기 때문이다. 군집 분할은 그 누수를 막는다.
  - 분류만 보지 않고 pIC50 회귀도 같이 본다. 분류가 포화되기 쉬운 반면
    '얼마나 센가'를 맞히는 문제는 표현의 차이가 그대로 드러난다.

출력:
  data/reports/261124_fcfp_real_clf.csv       분류 결과
  data/reports/261124_fcfp_real_reg.csv       회귀 결과
  data/reports/261124_fcfp_real.png           그림
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import warnings
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import rdFingerprintGenerator as rfg
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit.ML.Cluster import Butina
from rdkit.ML.Scoring import Scoring
from sklearn.model_selection import StratifiedKFold, StratifiedGroupKFold, GroupKFold, KFold
from sklearn.metrics import roc_auc_score, average_precision_score, mean_squared_error
from lightgbm import LGBMClassifier, LGBMRegressor
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RDLogger.DisableLog("rdApp.*")
warnings.filterwarnings("ignore")

SRC = "data/interim/261010_HSD17B13_IC50_merged.xlsx"
OUTDIR = "data/reports"
SEED = 42
NFOLD = 5
ALPHA = 20.0
POTENT_NM = 1000.0        # 1 µM — 논문과 동일한 활성 기준
CLUSTER_CUTOFF = 0.4      # Tanimoto 거리 0.4 = 유사도 0.6

# ---- 데이터: 실측만 ---------------------------------------------------------
df = pd.read_excel(SRC, sheet_name="robust_dedup")
df = df.dropna(subset=["canonical_smiles", "ic50_median_nM"]).reset_index(drop=True)

mols, keep = [], []
for i, smi in enumerate(df["canonical_smiles"]):
    m = Chem.MolFromSmiles(str(smi))
    if m is not None:
        mols.append(m)
        keep.append(i)
df = df.loc[keep].reset_index(drop=True)

y = (df["ic50_median_nM"] <= POTENT_NM).astype(int).to_numpy()
pic50 = df["pIC50_median"].to_numpy(dtype=float)
print(f"실측 화합물 {len(df):,}개  (decoy 0개)")
print(f"  분류 라벨 (<= {POTENT_NM:.0f} nM): active {int(y.sum()):,} / inactive {int((y == 0).sum()):,}")
print(f"  회귀 라벨 pIC50: {pic50.min():.2f} ~ {pic50.max():.2f}  (표준편차 {pic50.std():.2f})")

# ---- 분할 그룹: Butina 군집 --------------------------------------------------
print("\n" + "=" * 80)
print("[1] 분할 그룹 만들기")
print("=" * 80)

bitfps = [rfg.GetMorganGenerator(radius=2, fpSize=1024).GetFingerprint(m) for m in mols]
n = len(bitfps)
dists = []
for i in range(1, n):
    sims = DataStructs.BulkTanimotoSimilarity(bitfps[i], bitfps[:i])
    dists.extend(1.0 - s for s in sims)
clusters = Butina.ClusterData(dists, n, CLUSTER_CUTOFF, isDistData=True)
butina = np.empty(n, dtype=int)
for cid, members in enumerate(clusters):
    for idx in members:
        butina[idx] = cid


def murcko(mol, generic=False):
    try:
        core = MurckoScaffold.GetScaffoldForMol(mol)
        if generic:
            core = MurckoScaffold.MakeScaffoldGeneric(core)
        s = Chem.MolToSmiles(core)
        return s if s else "<acyclic>"
    except Exception:
        return "<error>"


murcko_g = np.array([murcko(m) for m in mols])
print(f"  Murcko 골격        {len(set(murcko_g)):>5,}개 그룹")
print(f"  Butina 군집(0.6)   {len(clusters):>5,}개 그룹   "
      f"가장 큰 군집 {max(len(c) for c in clusters):,}개")

# ---- 지문 5종 ----------------------------------------------------------------
feat_inv = rfg.GetMorganFeatureAtomInvGen()


def fps(gen):
    return np.vstack([gen.GetFingerprintAsNumPy(m) for m in mols]).astype(np.float32)


e1024 = fps(rfg.GetMorganGenerator(radius=2, fpSize=1024))
f1024 = fps(rfg.GetMorganGenerator(radius=2, fpSize=1024, atomInvariantsGenerator=feat_inv))
FEATURES = {
    "ECFP4-1024 (현행)": e1024,
    "ECFP4-2048": fps(rfg.GetMorganGenerator(radius=2, fpSize=2048)),
    "FCFP4-1024": f1024,
    "FCFP4-2048 (논문설정)": fps(rfg.GetMorganGenerator(radius=2, fpSize=2048,
                                                   atomInvariantsGenerator=feat_inv)),
    "ECFP4+FCFP4-1024": np.hstack([e1024, f1024]),
}

# ---- 분할이 실제로 화학공간을 갈랐는지 ----------------------------------------
print("\n" + "=" * 80)
print("[2] 분할 검증 — 시험 분자의 최근접 학습 분자 Tanimoto (1번 폴드)")
print("=" * 80)
SPLITS = {
    "무작위": (StratifiedKFold(NFOLD, shuffle=True, random_state=SEED), None),
    "Murcko": (StratifiedGroupKFold(NFOLD, shuffle=True, random_state=SEED), murcko_g),
    "Butina": (StratifiedGroupKFold(NFOLD, shuffle=True, random_state=SEED), butina),
}
sim_rows = []
for sname, (sp, g) in SPLITS.items():
    tr, te = next(iter(sp.split(e1024, y, g)))
    tr_fps = [bitfps[i] for i in tr]
    nn = np.array([max(DataStructs.BulkTanimotoSimilarity(bitfps[i], tr_fps)) for i in te])
    sim_rows.append({"분할": sname, "최근접_중앙값": round(float(np.median(nn)), 3),
                     "0.7이상%": round(float((nn >= 0.7).mean() * 100), 1),
                     "0.4미만%": round(float((nn < 0.4).mean() * 100), 1)})
    print(f"  {sname:8s} 중앙값 {np.median(nn):.3f}   "
          f">=0.7 {(nn >= 0.7).mean() * 100:5.1f}%   <0.4 {(nn < 0.4).mean() * 100:5.1f}%")

# ---- 지표 --------------------------------------------------------------------
def bedroc(y_true, score, alpha=ALPHA):
    order = np.argsort(-score)
    return Scoring.CalcBEDROC([[int(v)] for v in y_true[order]], 0, alpha)


def ef(y_true, score, frac=0.01):
    k = max(int(round(len(y_true) * frac)), 1)
    order = np.argsort(-score)[:k]
    return y_true[order].mean() / y_true.mean()


# ---- 분류 --------------------------------------------------------------------
print("\n" + "=" * 80)
print("[3] 분류 — active(<=1µM) vs inactive, decoy 없음")
print("=" * 80)
clf_rows = []
for name, X in FEATURES.items():
    row = {"표현": name}
    for sname, (sp, g) in SPLITS.items():
        proba = np.zeros(len(y))
        for tr, te in sp.split(X, y, g):
            clf = LGBMClassifier(n_estimators=300, class_weight="balanced",
                                 random_state=SEED, n_jobs=-1, verbosity=-1)
            clf.fit(X[tr], y[tr])
            proba[te] = clf.predict_proba(X[te])[:, 1]
        row[f"{sname}_AUC"] = roc_auc_score(y, proba)
        row[f"{sname}_BEDROC"] = bedroc(y, proba)
        row[f"{sname}_EF1"] = ef(y, proba)
    row["낙차(무작위-Butina)"] = row["무작위_AUC"] - row["Butina_AUC"]
    clf_rows.append(row)
    print(f"  {name:24s} 무작위 {row['무작위_AUC']:.3f} | "
          f"Murcko {row['Murcko_AUC']:.3f} | Butina {row['Butina_AUC']:.3f} "
          f"(낙차 {row['낙차(무작위-Butina)']:+.3f})")
clf = pd.DataFrame(clf_rows)

# ---- 회귀 --------------------------------------------------------------------
print("\n" + "=" * 80)
print("[4] 회귀 — pIC50 예측 (분류보다 표현 차이가 잘 드러난다)")
print("=" * 80)
REG_SPLITS = {
    "무작위": (KFold(NFOLD, shuffle=True, random_state=SEED), None),
    "Murcko": (GroupKFold(NFOLD), murcko_g),
    "Butina": (GroupKFold(NFOLD), butina),
}
reg_rows = []
for name, X in FEATURES.items():
    row = {"표현": name}
    for sname, (sp, g) in REG_SPLITS.items():
        pred = np.zeros(len(pic50))
        for tr, te in sp.split(X, pic50, g):
            rg = LGBMRegressor(n_estimators=400, random_state=SEED, n_jobs=-1, verbosity=-1)
            rg.fit(X[tr], pic50[tr])
            pred[te] = rg.predict(X[te])
        row[f"{sname}_Spearman"] = spearmanr(pic50, pred).statistic
        row[f"{sname}_RMSE"] = float(np.sqrt(mean_squared_error(pic50, pred)))
    row["낙차(무작위-Butina)"] = row["무작위_Spearman"] - row["Butina_Spearman"]
    reg_rows.append(row)
    print(f"  {name:24s} Spearman 무작위 {row['무작위_Spearman']:.3f} | "
          f"Murcko {row['Murcko_Spearman']:.3f} | Butina {row['Butina_Spearman']:.3f} "
          f"(낙차 {row['낙차(무작위-Butina)']:+.3f})  RMSE(Butina) {row['Butina_RMSE']:.3f}")
reg = pd.DataFrame(reg_rows)

# ---- 저장 + 그림 --------------------------------------------------------------
os.makedirs(OUTDIR, exist_ok=True)
clf.to_csv(f"{OUTDIR}/261124_fcfp_real_clf.csv", index=False, encoding="utf-8-sig")
reg.to_csv(f"{OUTDIR}/261124_fcfp_real_reg.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(sim_rows).to_csv(f"{OUTDIR}/261124_fcfp_real_similarity.csv",
                              index=False, encoding="utf-8-sig")

plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
x = np.arange(len(clf))
w = 0.26
cols = ["#9fb6cd", "#e0a033", "#c75d4d"]
for ax, (tab, keys, title, lo) in zip(axes, [
        (clf, ["무작위_AUC", "Murcko_AUC", "Butina_AUC"], "분류 ROC-AUC", 0.5),
        (clf, ["무작위_BEDROC", "Murcko_BEDROC", "Butina_BEDROC"], "분류 BEDROC (α=20)", 0.0),
        (reg, ["무작위_Spearman", "Murcko_Spearman", "Butina_Spearman"], "회귀 Spearman ρ", 0.0)]):
    for j, (k, c) in enumerate(zip(keys, cols)):
        ax.bar(x + (j - 1) * w, tab[k], w, label=k.split("_")[0], color=c)
    ax.set_xticks(x)
    ax.set_xticklabels(tab["표현"], rotation=20, ha="right", fontsize=8)
    ax.set_title(title, fontsize=11)
    ax.set_ylim(lo, 1.02)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)
fig.suptitle("decoy 제외 실측 데이터 · 분할 방식 3종 × 지문 5종", fontsize=12.5)
fig.tight_layout()
fig.savefig(f"{OUTDIR}/261124_fcfp_real.png", dpi=150)

print("\n" + "=" * 80)
print("[5] 요약")
print("=" * 80)
bc = clf.loc[clf["Butina_AUC"].idxmax()]
br = reg.loc[reg["Butina_Spearman"].idxmax()]
print(f"  분류 Butina 1위 : {bc['표현']}  AUC {bc['Butina_AUC']:.3f}")
print(f"  회귀 Butina 1위 : {br['표현']}  Spearman {br['Butina_Spearman']:.3f}")
base_c = clf[clf["표현"] == "ECFP4-1024 (현행)"].iloc[0]
base_r = reg[reg["표현"] == "ECFP4-1024 (현행)"].iloc[0]
print(f"\n  현행 ECFP4-1024 대비 변화 (Butina 분할 기준)")
for _, r in clf.iterrows():
    if r["표현"] != base_c["표현"]:
        print(f"    분류 {r['표현']:24s} {r['Butina_AUC'] - base_c['Butina_AUC']:+.4f} AUC")
for _, r in reg.iterrows():
    if r["표현"] != base_r["표현"]:
        print(f"    회귀 {r['표현']:24s} {r['Butina_Spearman'] - base_r['Butina_Spearman']:+.4f} ρ")
print(f"\n저장 → {OUTDIR}/261124_fcfp_real_clf.csv / _reg.csv / _real.png")
