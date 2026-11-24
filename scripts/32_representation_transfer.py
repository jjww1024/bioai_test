# -*- coding: utf-8 -*-
"""전이 가능한 표현 고르기 — '활성은 잘 가르면서 영역은 덜 가르는' 공간 찾기.

31번에서 나온 사실:
  학습 active 대 천연물 라이브러리 분류 ROC-AUC = 1.0000
  할로겐을 전부 지워도 1.0000

두 집단이 현재 지문 공간에서 자명하게 분리된다. 이 상태에서는 천연물을
음성이나 미분류(U)로 넣는 어떤 학습법도 — nnPU 포함 — '합성 대 천연'을
배우게 된다. 라벨을 고쳐서 될 일이 아니라 표현을 바꿔야 한다.

그래서 표현마다 두 숫자를 잰다.
  활성 AUC  실측 active/inactive 를 Butina 군집 분할로 가른 성능 (높을수록 좋다)
  영역 AUC  학습 active 와 천연물 라이브러리를 가른 성능 (1.0에서 멀수록 좋다)

고를 기준 — 활성 AUC를 지키면서 영역 AUC가 가장 낮은 표현.
영역 AUC가 1.0이면 그 표현으로는 천연물 전이가 원리적으로 불가능하다.
(판별 모델은 가장 쉬운 분리축을 쓰는데, 그 축이 '합성 대 천연'이기 때문)

후보 표현:
  ECFP4        현행 (원자 동일성 기반)
  FCFP4        약리작용단 추상화 — Cockroft가 고른 것
  ECFP4+FCFP4  25c에서 고른 결합
  MACCS        166개 구조 키 — 훨씬 거친 표현
  2D descriptor  물리화학 성질 — 위상 구조를 안 봄
  FCFP4(골격)   Murcko 일반 뼈대만 남기고 지문화 — 치환기 전부 제거

출력:
  data/reports/261124_representation_transfer.csv
  data/reports/261124_representation_transfer.png
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
from rdkit.Chem import rdFingerprintGenerator as rfg, MACCSkeys, Descriptors
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit.ML.Cluster import Butina
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.metrics import roc_auc_score
from sklearn.impute import SimpleImputer
from lightgbm import LGBMClassifier
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RDLogger.DisableLog("rdApp.*")
warnings.filterwarnings("ignore")

MERGED = "data/interim/261010_HSD17B13_IC50_merged.xlsx"
FULL = "data/screening/261124_screen_full_ranked.csv.gz"
OUTDIR = "data/reports"
SEED = 42
NFOLD = 5
NB = 1024
N_LIB = 5000

inv = rfg.GetMorganFeatureAtomInvGen()
GE = rfg.GetMorganGenerator(radius=2, fpSize=NB)
GF = rfg.GetMorganGenerator(radius=2, fpSize=NB, atomInvariantsGenerator=inv)

DESC = [(n, f) for n, f in Descriptors.descList]
print(f"2D descriptor {len(DESC)}종")


def generic_scaffold(m):
    try:
        c = MurckoScaffold.MakeScaffoldGeneric(MurckoScaffold.GetScaffoldForMol(m))
        return c if c.GetNumAtoms() else m
    except Exception:
        return m


def rep_matrix(mols, rep):
    if rep == "ECFP4":
        return np.vstack([GE.GetFingerprintAsNumPy(m) for m in mols]).astype(np.float32)
    if rep == "FCFP4":
        return np.vstack([GF.GetFingerprintAsNumPy(m) for m in mols]).astype(np.float32)
    if rep == "ECFP4+FCFP4":
        return np.hstack([rep_matrix(mols, "ECFP4"), rep_matrix(mols, "FCFP4")])
    if rep == "MACCS":
        out = []
        for m in mols:
            fp = MACCSkeys.GenMACCSKeys(m)
            a = np.zeros((fp.GetNumBits(),), dtype=np.int8)
            DataStructs.ConvertToNumpyArray(fp, a)
            out.append(a)
        return np.vstack(out).astype(np.float32)
    if rep == "2D descriptor":
        a = np.array([[f(m) for _, f in DESC] for m in mols], dtype=np.float64)
        a[~np.isfinite(a)] = np.nan
        return SimpleImputer(strategy="median").fit_transform(a).astype(np.float32)
    if rep == "FCFP4(일반뼈대)":
        return np.vstack([GF.GetFingerprintAsNumPy(generic_scaffold(m))
                          for m in mols]).astype(np.float32)
    raise ValueError(rep)


REPS = ["ECFP4", "FCFP4", "ECFP4+FCFP4", "MACCS", "2D descriptor", "FCFP4(일반뼈대)"]


def clf():
    return LGBMClassifier(n_estimators=300, class_weight="balanced",
                          random_state=SEED, n_jobs=-1, verbosity=-1)


# ---- 데이터 ---------------------------------------------------------------------
df = pd.read_excel(MERGED, sheet_name="robust_dedup")
df = df.dropna(subset=["canonical_smiles", "ic50_median_nM"]).reset_index(drop=True)
mols, keep = [], []
for i, s in enumerate(df["canonical_smiles"]):
    m = Chem.MolFromSmiles(str(s))
    if m is not None:
        mols.append(m); keep.append(i)
df = df.loc[keep].reset_index(drop=True)
y = (df["ic50_median_nM"] <= 1000).astype(int).to_numpy()
act_mols = [m for m, l in zip(mols, y) if l == 1]

lib = pd.read_csv(FULL, usecols=["canonical_smiles"], low_memory=False).sample(
    N_LIB, random_state=SEED)
lmols = [Chem.MolFromSmiles(s) for s in lib.canonical_smiles]
lmols = [m for m in lmols if m is not None]
print(f"실측 {len(y):,} (active {int(y.sum()):,}) | 천연물 표본 {len(lmols):,}")

# Butina 군집(활성 과제 분할) — 표현과 무관하게 ECFP4 기준으로 한 번만
fps = [GE.GetFingerprint(m) for m in mols]
d = []
for i in range(1, len(fps)):
    d.extend(1.0 - s for s in DataStructs.BulkTanimotoSimilarity(fps[i], fps[:i]))
cl = Butina.ClusterData(d, len(fps), 0.4, isDistData=True)
groups = np.empty(len(fps), dtype=int)
for cid, mem in enumerate(cl):
    for i in mem:
        groups[i] = cid
print(f"Butina 군집 {len(cl):,}개\n")

ydom = np.r_[np.ones(len(act_mols), int), np.zeros(len(lmols), int)]

print("=" * 86)
print(f"{'표현':18s} {'활성 AUC':>10s} {'영역 AUC':>10s} {'영역 1.0과의 거리':>18s}  판정")
print("=" * 86)
rows = []
for rep in REPS:
    Xa = rep_matrix(mols, rep)
    pa = np.zeros(len(y))
    for tr, te in StratifiedGroupKFold(NFOLD, shuffle=True, random_state=SEED).split(Xa, y, groups):
        pa[te] = clf().fit(Xa[tr], y[tr]).predict_proba(Xa[te])[:, 1]
    act_auc = roc_auc_score(y, pa)

    Xd = rep_matrix(act_mols + lmols, rep)
    pdm = np.zeros(len(ydom))
    for tr, te in StratifiedKFold(NFOLD, shuffle=True, random_state=SEED).split(Xd, ydom):
        pdm[te] = clf().fit(Xd[tr], ydom[tr]).predict_proba(Xd[te])[:, 1]
    dom_auc = roc_auc_score(ydom, pdm)

    gap = 1.0 - dom_auc
    verdict = ("전이 불가 (자명 분리)" if dom_auc > 0.999 else
               "전이 어려움" if dom_auc > 0.99 else "여지 있음")
    rows.append({"표현": rep, "활성_AUC": round(act_auc, 4),
                 "영역_AUC": round(dom_auc, 4), "영역여유": round(gap, 4),
                 "판정": verdict, "차원": Xa.shape[1]})
    print(f"{rep:18s} {act_auc:10.4f} {dom_auc:10.4f} {gap:18.4f}  {verdict}")

res = pd.DataFrame(rows)
os.makedirs(OUTDIR, exist_ok=True)
res.to_csv(f"{OUTDIR}/261124_representation_transfer.csv", index=False, encoding="utf-8-sig")

# ---- 그림 -----------------------------------------------------------------------
plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
fig, ax = plt.subplots(figsize=(8.2, 6))
ax.scatter(res["영역_AUC"], res["활성_AUC"], s=120, color="#c75d4d", zorder=3)
for _, r in res.iterrows():
    ax.annotate(r["표현"], (r["영역_AUC"], r["활성_AUC"]),
                textcoords="offset points", xytext=(8, 5), fontsize=9)
ax.axvline(1.0, ls="--", lw=1.2, color="#555")
ax.text(0.9995, ax.get_ylim()[0], " 영역 AUC 1.0\n = 자명 분리\n = 전이 불가",
        fontsize=8.5, color="#555", va="bottom")
ax.set_xlabel("영역 AUC — 학습 active 와 천연물을 가르는 정도 (낮을수록 좋다)")
ax.set_ylabel("활성 AUC — 실제 활성 판별력 (높을수록 좋다)")
ax.set_title("왼쪽 위로 갈수록 좋은 표현", fontsize=12)
ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig(f"{OUTDIR}/261124_representation_transfer.png", dpi=150)

best = res[res["영역_AUC"] < 0.999].sort_values("활성_AUC", ascending=False)
print("\n" + "=" * 86)
if len(best):
    b = best.iloc[0]
    print(f"[권고] {b['표현']} — 활성 {b['활성_AUC']:.3f}, 영역 {b['영역_AUC']:.4f}")
    print("  이 표현에서는 두 집단이 완전히 갈리지 않으므로, 천연물을 U(미분류)로")
    print("  쓰는 nnPU 같은 방법이 의미를 가질 여지가 있다.")
else:
    print("[권고] 어떤 표현에서도 영역이 자명하게 갈린다.")
    print("  판별 학습으로는 천연물 전이가 불가능하다는 뜻이다.")
    print("  유사도 기반 순위 + 클래스 단위 집계로 과제를 바꾸는 편이 낫다.")
print(f"\n저장 → {OUTDIR}/261124_representation_transfer.csv / .png")
