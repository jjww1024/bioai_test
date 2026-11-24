# -*- coding: utf-8 -*-
"""25b에서 나온 지문 간 차이(±0.01~0.02)가 진짜인지 반복 측정으로 확인한다.

25b 결과 요약 (Butina 군집 분할):
  분류 AUC   ECFP4-1024 0.891 / FCFP4-2048 0.887 / 둘 합침 0.902
  회귀 ρ     ECFP4-1024 0.794 / FCFP4-2048 0.813 / 둘 합침 0.808

차이가 0.02 안쪽이라 폴드를 어떻게 나눴느냐에 따라 뒤집힐 수 있다.
분할 시드를 5개로 바꿔 가며 반복하고 평균과 표준편차를 낸다.
같은 시드에서는 모든 지문이 같은 분할을 쓰므로(짝지은 비교) 지문 간 차이를
시드별로 직접 빼서 그 차이의 분포를 본다 — 이게 "진짜 나은가"의 답이다.

출력:
  data/reports/261124_fcfp_significance.csv
  data/reports/261124_fcfp_significance.png
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
from rdkit.ML.Cluster import Butina
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import roc_auc_score, mean_squared_error
from lightgbm import LGBMClassifier, LGBMRegressor
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RDLogger.DisableLog("rdApp.*")
warnings.filterwarnings("ignore")

SRC = "data/interim/261010_HSD17B13_IC50_merged.xlsx"
OUTDIR = "data/reports"
NFOLD = 5
SEEDS = [11, 22, 33, 44, 55]
POTENT_NM = 1000.0
CLUSTER_CUTOFF = 0.4
BASELINE = "ECFP4-1024 (현행)"

# ---- 데이터 ------------------------------------------------------------------
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
print(f"실측 {len(df):,}개 | active {int(y.sum()):,} / inactive {int((y == 0).sum()):,}")

# ---- Butina 군집 --------------------------------------------------------------
bitfps = [rfg.GetMorganGenerator(radius=2, fpSize=1024).GetFingerprint(m) for m in mols]
n = len(bitfps)
dists = []
for i in range(1, n):
    dists.extend(1.0 - s for s in DataStructs.BulkTanimotoSimilarity(bitfps[i], bitfps[:i]))
clusters = Butina.ClusterData(dists, n, CLUSTER_CUTOFF, isDistData=True)
groups = np.empty(n, dtype=int)
for cid, mem in enumerate(clusters):
    for idx in mem:
        groups[idx] = cid
print(f"Butina 군집 {len(clusters):,}개 | 분할 시드 {len(SEEDS)}개 x {NFOLD}-fold")

# ---- 지문 ---------------------------------------------------------------------
inv = rfg.GetMorganFeatureAtomInvGen()


def fps(gen):
    return np.vstack([gen.GetFingerprintAsNumPy(m) for m in mols]).astype(np.float32)


e1024 = fps(rfg.GetMorganGenerator(radius=2, fpSize=1024))
f1024 = fps(rfg.GetMorganGenerator(radius=2, fpSize=1024, atomInvariantsGenerator=inv))
FEATURES = {
    BASELINE: e1024,
    "ECFP4-2048": fps(rfg.GetMorganGenerator(radius=2, fpSize=2048)),
    "FCFP4-1024": f1024,
    "FCFP4-2048 (논문설정)": fps(rfg.GetMorganGenerator(radius=2, fpSize=2048,
                                                   atomInvariantsGenerator=inv)),
    "ECFP4+FCFP4-1024": np.hstack([e1024, f1024]),
}

# ---- 반복 측정 -----------------------------------------------------------------
print("\n" + "=" * 78)
print("시드별 측정 중")
print("=" * 78)
rows = []
for seed in SEEDS:
    sp = StratifiedGroupKFold(NFOLD, shuffle=True, random_state=seed)
    folds = list(sp.split(e1024, y, groups))         # 지문끼리 동일 분할(짝지은 비교)
    for name, X in FEATURES.items():
        proba = np.zeros(len(y))
        pred = np.zeros(len(pic50))
        for tr, te in folds:
            c = LGBMClassifier(n_estimators=300, class_weight="balanced",
                               random_state=0, n_jobs=-1, verbosity=-1).fit(X[tr], y[tr])
            proba[te] = c.predict_proba(X[te])[:, 1]
            r = LGBMRegressor(n_estimators=400, random_state=0,
                              n_jobs=-1, verbosity=-1).fit(X[tr], pic50[tr])
            pred[te] = r.predict(X[te])
        rows.append({"seed": seed, "표현": name,
                     "AUC": roc_auc_score(y, proba),
                     "Spearman": spearmanr(pic50, pred).statistic,
                     "RMSE": float(np.sqrt(mean_squared_error(pic50, pred)))})
    print(f"  시드 {seed} 완료")

raw = pd.DataFrame(rows)

# ---- 집계 ----------------------------------------------------------------------
agg = raw.groupby("표현").agg(
    AUC평균=("AUC", "mean"), AUC표준편차=("AUC", "std"),
    ρ평균=("Spearman", "mean"), ρ표준편차=("Spearman", "std"),
    RMSE평균=("RMSE", "mean"), RMSE표준편차=("RMSE", "std"),
).reindex(FEATURES.keys())

print("\n" + "=" * 78)
print(f"[1] 시드 {len(SEEDS)}회 평균 ± 표준편차  (Butina 군집 분할)")
print("=" * 78)
for name, r in agg.iterrows():
    print(f"  {name:24s} AUC {r['AUC평균']:.3f}±{r['AUC표준편차']:.3f}   "
          f"ρ {r['ρ평균']:.3f}±{r['ρ표준편차']:.3f}   "
          f"RMSE {r['RMSE평균']:.3f}±{r['RMSE표준편차']:.3f}")

# ---- 짝지은 차이: 같은 시드 안에서 baseline 과 직접 비교 -------------------------
print("\n" + "=" * 78)
print(f"[2] 짝지은 비교 — 같은 분할에서 '{BASELINE}' 대비 차이")
print("    5회 모두 같은 부호면 차이가 분할 운이 아니라는 뜻")
print("=" * 78)
piv_a = raw.pivot(index="seed", columns="표현", values="AUC")
piv_s = raw.pivot(index="seed", columns="표현", values="Spearman")
diff_rows = []
for name in FEATURES:
    if name == BASELINE:
        continue
    da = piv_a[name] - piv_a[BASELINE]
    ds = piv_s[name] - piv_s[BASELINE]
    diff_rows.append({
        "표현": name,
        "ΔAUC평균": da.mean(), "ΔAUC표준편차": da.std(),
        "AUC이긴횟수": f"{int((da > 0).sum())}/{len(SEEDS)}",
        "Δρ평균": ds.mean(), "Δρ표준편차": ds.std(),
        "ρ이긴횟수": f"{int((ds > 0).sum())}/{len(SEEDS)}",
    })
    print(f"  {name:24s} ΔAUC {da.mean():+.4f}±{da.std():.4f} ({int((da > 0).sum())}/{len(SEEDS)})"
          f"   Δρ {ds.mean():+.4f}±{ds.std():.4f} ({int((ds > 0).sum())}/{len(SEEDS)})")
diff = pd.DataFrame(diff_rows)

# ---- 저장 + 그림 ----------------------------------------------------------------
os.makedirs(OUTDIR, exist_ok=True)
raw.to_csv(f"{OUTDIR}/261124_fcfp_significance_raw.csv", index=False, encoding="utf-8-sig")
agg.to_csv(f"{OUTDIR}/261124_fcfp_significance.csv", encoding="utf-8-sig")
diff.to_csv(f"{OUTDIR}/261124_fcfp_significance_diff.csv", index=False, encoding="utf-8-sig")

plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
names = list(FEATURES.keys())
fig, axes = plt.subplots(1, 2, figsize=(13.5, 4.8))
for ax, (col, sd, title) in zip(axes, [
        ("AUC평균", "AUC표준편차", "분류 ROC-AUC (시드 5회)"),
        ("ρ평균", "ρ표준편차", "회귀 Spearman ρ (시드 5회)")]):
    vals = agg.loc[names, col].to_numpy()
    errs = agg.loc[names, sd].to_numpy()
    colors = ["#9fb6cd" if nm == BASELINE else "#c75d4d" for nm in names]
    ax.bar(np.arange(len(names)), vals, 0.6, yerr=errs, capsize=4, color=colors)
    ax.axhline(agg.loc[BASELINE, col], ls="--", lw=1, color="#555")
    ax.set_xticks(np.arange(len(names)))
    ax.set_xticklabels(names, rotation=20, ha="right", fontsize=8.5)
    lo = min(vals - errs) - 0.02
    ax.set_ylim(lo, max(vals + errs) + 0.01)
    ax.set_title(title, fontsize=11)
    ax.grid(axis="y", alpha=0.25)
fig.suptitle("점선 = 현행 ECFP4-1024 · 막대 오차는 분할 시드 5회 표준편차", fontsize=11.5)
fig.tight_layout()
fig.savefig(f"{OUTDIR}/261124_fcfp_significance.png", dpi=150)
print(f"\n저장 → {OUTDIR}/261124_fcfp_significance.csv / _diff.csv / .png")
