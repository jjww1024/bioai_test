# -*- coding: utf-8 -*-
"""스캐폴드 분할을 도입하고, 그 위에서 ECFP4 대 FCFP4를 비교한다.

왜 두 개를 같이 하는가 —
FCFP는 "더 좋은" 지문이 아니라 "더 추상적인" 지문이다(Cockroft 2019가 FCFP를
고른 이유: 약리작용단에 가까운 표현). 추상화한 만큼 구별력을 버렸으므로,
학습셋과 시험셋이 닮아 있는 무작위 분할에서는 ECFP4보다 오히려 낮게 나오기 쉽다.
FCFP의 값어치는 '모르는 화학공간으로 넘어갈 때 덜 무너진다'에 있으므로,
스캐폴드 분할을 먼저 깔지 않으면 비교 자체가 무의미하다.

세 가지를 잰다:
  1. 우리 데이터의 compound series bias 실태 (활성 2,741개가 몇 개 골격인가)
  2. 무작위 CV 대 스캐폴드 CV의 낙차 (지금 성능 숫자가 얼마나 부풀어 있나)
  3. 지문 5종의 낙차 비교 (어느 표현이 화학공간 이동에 강한가)

평가 지표는 Cockroft 논문과 맞춘다 — ROC-AUC만 보면 속으므로 조기 인식 지표
(BEDROC α=20, EF 1%)를 같이 본다.

출력:
  data/reports/261124_scaffold_fcfp_results.csv
  data/reports/261124_scaffold_fcfp.png
  data/reports/261124_split_similarity.csv
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
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import rdFingerprintGenerator as rfg
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit.ML.Scoring import Scoring
from sklearn.model_selection import StratifiedKFold, StratifiedGroupKFold
from sklearn.metrics import roc_auc_score, average_precision_score
from lightgbm import LGBMClassifier
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RDLogger.DisableLog("rdApp.*")
warnings.filterwarnings("ignore")

SRC = "data/processed/261010_train_1to1.csv"
OUTDIR = "data/reports"
SEED = 42
NFOLD = 5
ALPHA = 20.0        # BEDROC — 논문과 동일


# ---- 데이터 ----------------------------------------------------------------
df = pd.read_csv(SRC).dropna(subset=["canonical_smiles"]).reset_index(drop=True)
mols, keep = [], []
for i, smi in enumerate(df["canonical_smiles"]):
    m = Chem.MolFromSmiles(str(smi))
    if m is not None:
        mols.append(m)
        keep.append(i)
df = df.loc[keep].reset_index(drop=True)
y = df["label"].astype(int).to_numpy()
src = df["source"].to_numpy()
print(f"학습셋 {len(df):,}개  (active {int(y.sum()):,} / inactive {int((y == 0).sum()):,})")
print(df.groupby(["label", "source"]).size().to_string())


# ---- 1. Murcko 골격 — compound series bias 실태 ------------------------------
def murcko(mol, generic=False):
    """Bemis-Murcko 골격 SMILES. generic=True면 원자종류까지 지운 뼈대."""
    try:
        core = MurckoScaffold.GetScaffoldForMol(mol)
        if generic:
            core = MurckoScaffold.MakeScaffoldGeneric(core)
        s = Chem.MolToSmiles(core)
        return s if s else "<acyclic>"      # 고리가 없는 분자
    except Exception:
        return "<error>"


df["scaffold"] = [murcko(m) for m in mols]
df["scaffold_generic"] = [murcko(m, generic=True) for m in mols]

print("\n" + "=" * 78)
print("[1] compound series bias 실태 — 분자 수 대비 골격 수")
print("=" * 78)
rows = []
for name, sub in [("활성(active)", df[df.label == 1]),
                  ("실측 비활성", df[df.source == "real_inactive"]),
                  ("decoy", df[df.source == "decoy"]),
                  ("전체", df)]:
    rows.append({
        "집단": name, "분자": len(sub),
        "골격": sub.scaffold.nunique(),
        "골격당 분자": round(len(sub) / max(sub.scaffold.nunique(), 1), 1),
        "일반뼈대": sub.scaffold_generic.nunique(),
    })
bias = pd.DataFrame(rows)
print(bias.to_string(index=False))

top = df[df.label == 1].scaffold.value_counts().head(5)
print(f"\n활성에서 가장 많은 골격 5개 (활성 {int(y.sum()):,}개 중 "
      f"{top.sum():,}개 = {top.sum() / y.sum() * 100:.1f}%)")
for s, n in top.items():
    print(f"  {n:>5,}개  {s[:66]}")


# ---- 2. 지문 5종 -------------------------------------------------------------
feat_inv = rfg.GetMorganFeatureAtomInvGen()      # FCFP: 원자를 기능 6종으로 추상화


def fps(generator, mols):
    return np.vstack([generator.GetFingerprintAsNumPy(m) for m in mols]).astype(np.float32)


print("\n" + "=" * 78)
print("[2] 지문 생성")
print("=" * 78)
ecfp1024 = fps(rfg.GetMorganGenerator(radius=2, fpSize=1024), mols)
ecfp2048 = fps(rfg.GetMorganGenerator(radius=2, fpSize=2048), mols)
fcfp1024 = fps(rfg.GetMorganGenerator(radius=2, fpSize=1024,
                                      atomInvariantsGenerator=feat_inv), mols)
fcfp2048 = fps(rfg.GetMorganGenerator(radius=2, fpSize=2048,
                                      atomInvariantsGenerator=feat_inv), mols)

FEATURES = {
    "ECFP4-1024 (현행)": ecfp1024,
    "ECFP4-2048": ecfp2048,
    "FCFP4-1024": fcfp1024,
    "FCFP4-2048 (논문설정)": fcfp2048,
    "ECFP4+FCFP4-1024": np.hstack([ecfp1024, fcfp1024]),
}
for k, v in FEATURES.items():
    dens = v.mean()
    print(f"  {k:24s} {v.shape[1]:>5}bit  켜진 비트 비율 {dens * 100:5.2f}%")


# ---- 3. 평가 지표 -------------------------------------------------------------
def bedroc(y_true, score, alpha=ALPHA):
    """조기 인식 지표. 목록 앞쪽에 활성이 몰려 있을수록 1에 가깝다."""
    order = np.argsort(-score)
    return Scoring.CalcBEDROC([[int(v)] for v in y_true[order]], 0, alpha)


def ef(y_true, score, frac=0.01):
    """EF 1% — 상위 1%에 활성이 무작위 대비 몇 배 몰렸나."""
    n = max(int(round(len(y_true) * frac)), 1)
    order = np.argsort(-score)[:n]
    hit = y_true[order].mean()
    base = y_true.mean()
    return hit / base if base > 0 else np.nan


def run_cv(X, y, splitter, groups=None):
    """교차검증 예측 확률을 모아서 돌려준다(폴드별 모델 재학습)."""
    proba = np.zeros(len(y))
    for tr, te in splitter.split(X, y, groups):
        clf = LGBMClassifier(n_estimators=300, class_weight="balanced",
                             random_state=SEED, n_jobs=-1, verbosity=-1)
        clf.fit(X[tr], y[tr])
        proba[te] = clf.predict_proba(X[te])[:, 1]
    return proba


# ---- 4. 두 가지 분할로 전부 돌리기 --------------------------------------------
random_cv = StratifiedKFold(n_splits=NFOLD, shuffle=True, random_state=SEED)
scaffold_cv = StratifiedGroupKFold(n_splits=NFOLD, shuffle=True, random_state=SEED)
groups = df["scaffold"].to_numpy()

print("\n" + "=" * 78)
print(f"[3] 교차검증 — 무작위 {NFOLD}-fold 대 스캐폴드 {NFOLD}-fold")
print(f"    스캐폴드 그룹 수 {df.scaffold.nunique():,}개 "
      f"(같은 골격은 학습·시험에 쪼개지지 않음)")
print("=" * 78)

real_mask = (src == "active") | (src == "real_inactive")   # decoy 뺀 실측만
results = []
for name, X in FEATURES.items():
    row = {"표현": name}
    for split_name, splitter in [("무작위", random_cv), ("스캐폴드", scaffold_cv)]:
        g = groups if split_name == "스캐폴드" else None
        p = run_cv(X, y, splitter, g)
        row[f"{split_name}_AUC"] = roc_auc_score(y, p)
        row[f"{split_name}_PR"] = average_precision_score(y, p)
        row[f"{split_name}_BEDROC"] = bedroc(y, p)
        row[f"{split_name}_EF1"] = ef(y, p)
        # decoy를 뺀 실측 active vs real_inactive 만으로 다시 채점(진짜 어려운 판별)
        row[f"{split_name}_AUC실측"] = roc_auc_score(y[real_mask], p[real_mask])
    row["AUC낙차"] = row["무작위_AUC"] - row["스캐폴드_AUC"]
    row["BEDROC낙차"] = row["무작위_BEDROC"] - row["스캐폴드_BEDROC"]
    results.append(row)
    print(f"  {name:24s} 무작위 AUC {row['무작위_AUC']:.3f} → "
          f"스캐폴드 {row['스캐폴드_AUC']:.3f}  (낙차 {row['AUC낙차']:+.3f})")

res = pd.DataFrame(results)


# ---- 5. 분할이 실제로 화학공간을 갈랐는지 확인 (Cockroft Figure 5 방식) --------
print("\n" + "=" * 78)
print("[4] 분할 검증 — 시험 분자가 학습 분자와 얼마나 닮았나")
print("    (Cockroft Figure 5와 같은 확인. 닮음이 낮을수록 어려운 시험)")
print("=" * 78)

bitfps = [rfg.GetMorganGenerator(radius=2, fpSize=1024).GetFingerprint(m) for m in mols]
sim_rows = []
for split_name, splitter in [("무작위", random_cv), ("스캐폴드", scaffold_cv)]:
    g = groups if split_name == "스캐폴드" else None
    tr, te = next(iter(splitter.split(FEATURES["ECFP4-1024 (현행)"], y, g)))
    tr_fps = [bitfps[i] for i in tr]
    nn = [max(DataStructs.BulkTanimotoSimilarity(bitfps[i], tr_fps)) for i in te]
    nn = np.array(nn)
    sim_rows.append({"분할": split_name, "시험분자": len(te),
                     "최근접유사도_중앙값": round(float(np.median(nn)), 3),
                     "0.7이상_비율%": round(float((nn >= 0.7).mean() * 100), 1),
                     "0.4미만_비율%": round(float((nn < 0.4).mean() * 100), 1)})
    print(f"  {split_name:6s} 최근접 Tanimoto 중앙값 {np.median(nn):.3f}   "
          f"≥0.7 {(nn >= 0.7).mean() * 100:5.1f}%   <0.4 {(nn < 0.4).mean() * 100:5.1f}%")
sim = pd.DataFrame(sim_rows)


# ---- 6. 저장 + 그림 ----------------------------------------------------------
os.makedirs(OUTDIR, exist_ok=True)
res.to_csv(f"{OUTDIR}/261124_scaffold_fcfp_results.csv", index=False, encoding="utf-8-sig")
sim.to_csv(f"{OUTDIR}/261124_split_similarity.csv", index=False, encoding="utf-8-sig")

plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
x = np.arange(len(res))
w = 0.38
for ax, (a, b, title) in zip(axes, [
        ("무작위_AUC", "스캐폴드_AUC", "ROC-AUC"),
        ("무작위_BEDROC", "스캐폴드_BEDROC", "BEDROC (α=20) — 상위권 적중")]):
    ax.bar(x - w / 2, res[a], w, label="무작위 분할", color="#9fb6cd")
    ax.bar(x + w / 2, res[b], w, label="스캐폴드 분할", color="#c75d4d")
    ax.set_xticks(x)
    ax.set_xticklabels(res["표현"], rotation=18, ha="right", fontsize=8.5)
    ax.set_title(title, fontsize=11)
    ax.set_ylim(0, 1.02)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8.5)
fig.suptitle("무작위 분할은 성능을 얼마나 부풀리는가 · 지문별 비교", fontsize=12.5)
fig.tight_layout()
fig.savefig(f"{OUTDIR}/261124_scaffold_fcfp.png", dpi=150)

print("\n" + "=" * 78)
print("[5] 최종 표")
print("=" * 78)
cols = ["표현", "무작위_AUC", "스캐폴드_AUC", "AUC낙차",
        "무작위_BEDROC", "스캐폴드_BEDROC", "BEDROC낙차", "스캐폴드_AUC실측"]
print(res[cols].round(3).to_string(index=False))

best_gap = res.loc[res["AUC낙차"].idxmin()]
best_abs = res.loc[res["스캐폴드_AUC"].idxmax()]
print(f"\n낙차가 가장 작은 표현 : {best_gap['표현']} ({best_gap['AUC낙차']:+.3f})")
print(f"스캐폴드 절대성능 1위 : {best_abs['표현']} (AUC {best_abs['스캐폴드_AUC']:.3f})")
print(f"\n저장 → {OUTDIR}/261124_scaffold_fcfp_results.csv")
print(f"저장 → {OUTDIR}/261124_scaffold_fcfp.png")
