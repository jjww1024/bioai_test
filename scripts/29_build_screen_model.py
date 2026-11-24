# -*- coding: utf-8 -*-
"""스크리닝용 모델을 다시 만든다 — 25c에서 고른 표현 + 배경을 바꾼 음성셋.

기존 모델의 문제 두 가지:

  1) 표현 — ECFP4 단독. 25c에서 ECFP4+FCFP4 결합이 분류 +0.008 AUC(5/5),
     회귀 +0.019 rho(5/5)로 일관되게 나았다.

  2) 음성 데이터의 출처 — 더 큰 문제다.
     기존 decoy는 PubChem 무작위 분자에서 뽑았다(06번). 즉 합성 의약품스러운
     분자들이다. 그런데 우리가 스크리닝하는 대상은 천연물 80만 개다.
     "합성 활성물 대 합성 decoy"로 배운 경계선을, 당·테르펜·알칼로이드가
     가득한 공간에 가져다 쓰는 셈이다. 모델이 그 공간을 본 적이 없다.

     이번에는 배경을 '우리가 실제로 스크리닝할 라이브러리'에서 뽑는다.
     COCONUT/NPASS/FooDB에서 active와 성질(MW·logP·HBD·HBA·회전결합)을
     맞추고 Tanimoto <= 0.35 인 분자만 골라 음성으로 쓴다.
     Cockroft와 같은 '모르면 비활성' 가정이며, 80만 중 수만 개를 뽑으므로
     진짜 활성물이 섞일 확률은 무시할 수 있다.

주의 — 배경으로 쓴 분자는 학습에 들어갔으므로 30번 스크리닝 결과에서
      따로 표시한다(그 분자들의 점수는 외워서 낮은 것이므로 못 믿는다).

출력:
  data/models/261124_screen_model_ef.pkl
  data/interim/261124_np_background.csv
  data/reports/261124_screen_model_cv.csv
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import re
import glob
import pickle
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import rdFingerprintGenerator as rfg, Descriptors, rdMolDescriptors
from rdkit.ML.Cluster import Butina
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import roc_auc_score, average_precision_score
from lightgbm import LGBMClassifier

RDLogger.DisableLog("rdApp.*")

MERGED = "data/interim/261010_HSD17B13_IC50_merged.xlsx"
COCONUT = "data/raw/coconut_csv-09-2026.csv"
NPASS = "data/raw/npass_structures.tsv"
FOODB = "data/raw/foodb_2020_4_7_csv/foodb_2020_04_07_csv/Compound.csv"
OUT_MODEL = "data/models/261124_screen_model_ef.pkl"
OUT_BG = "data/interim/261124_np_background.csv"
OUT_CV = "data/reports/261124_screen_model_cv.csv"

POTENT_NM = 1000.0
N_BACKGROUND = 12_000      # active 1,915개 대비 약 6배
TANI_MAX = 0.35
SEED = 42
NFOLD = 5
NB = 1024

inv = rfg.GetMorganFeatureAtomInvGen()
GEN_E = rfg.GetMorganGenerator(radius=2, fpSize=NB)
GEN_F = rfg.GetMorganGenerator(radius=2, fpSize=NB, atomInvariantsGenerator=inv)
GEN_SIM = rfg.GetMorganGenerator(radius=2, fpSize=2048)


def featurize(mols):
    e = np.vstack([GEN_E.GetFingerprintAsNumPy(m) for m in mols])
    f = np.vstack([GEN_F.GetFingerprintAsNumPy(m) for m in mols])
    return np.hstack([e, f]).astype(np.float32)


def props(m):
    return (Descriptors.MolWt(m), Descriptors.MolLogP(m),
            rdMolDescriptors.CalcNumHBD(m), rdMolDescriptors.CalcNumHBA(m),
            rdMolDescriptors.CalcNumRotatableBonds(m))


# ---- 1. 실측 데이터 -----------------------------------------------------------
df = pd.read_excel(MERGED, sheet_name="robust_dedup")
df = df.dropna(subset=["canonical_smiles", "ic50_median_nM"]).reset_index(drop=True)
mols, keep = [], []
for i, s in enumerate(df["canonical_smiles"]):
    m = Chem.MolFromSmiles(str(s))
    if m is not None:
        mols.append(m); keep.append(i)
df = df.loc[keep].reset_index(drop=True)
df["label"] = (df["ic50_median_nM"] <= POTENT_NM).astype(int)
act_mols = [m for m, l in zip(mols, df.label) if l == 1]
act_fps = [GEN_SIM.GetFingerprint(m) for m in act_mols]
print(f"실측 {len(df):,}개 — active {int(df.label.sum()):,} / inactive {int((df.label==0).sum()):,}")

P = np.array([props(m) for m in act_mols])
lo, hi = np.percentile(P, 5, axis=0), np.percentile(P, 95, axis=0)
print("active 성질 5~95퍼센타일 창:")
for nm, a, b in zip(["MW", "logP", "HBD", "HBA", "RotB"], lo, hi):
    print(f"  {nm:5s} {a:8.2f} ~ {b:8.2f}")


# ---- 2. 천연물 라이브러리에서 배경 뽑기 ------------------------------------------
IK = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


# DB별 할당량. 한 DB에서 몰아 뽑으면 그 DB의 화학만 '음성'으로 배우게 된다.
# FooDB는 식품 유래 성분이라 건강기능식품 소재와 가장 가깝다 — 반드시 포함한다.
# FooDB CSV는 헤더가 한 칸 밀려 있어 'cas_number' 컬럼에 SMILES가 들어 있다.
LIBS = [
    ("COCONUT", COCONUT, ",", "identifier", "canonical_smiles", 0.55),
    ("NPASS", NPASS, "\t", "np_id", "SMILES", 0.20),
    ("FooDB", FOODB, ",", "public_id", "cas_number", 0.25),
]


def iter_one(path, sep, idc, smic):
    for ch in pd.read_csv(path, sep=sep, usecols=[idc, smic],
                          chunksize=50_000, low_memory=False, on_bad_lines="skip"):
        for i, s in zip(ch[idc], ch[smic]):
            yield i, s


print(f"\n천연물 라이브러리에서 배경 {N_BACKGROUND:,}개 수집 중")
print(f"  조건: active 성질 창 안 + active와 Tanimoto <= {TANI_MAX}")
rng = np.random.default_rng(SEED)
bg_rows, seen = [], set()
for src, path, sep, idc, smic, share in LIBS:
    quota = int(round(N_BACKGROUND * share))
    got, n_scan = 0, 0
    for cid, smi in iter_one(path, sep, idc, smic):
        n_scan += 1
        if got >= quota:
            break
        if rng.random() > 0.35:        # 전체를 다 보지 않고 솎아서 훑는다
            continue
        m = Chem.MolFromSmiles(str(smi))
        if m is None:
            continue
        if any(v < a or v > b for v, a, b in zip(props(m), lo, hi)):
            continue
        canon = Chem.MolToSmiles(m)
        if canon in seen:
            continue
        q = GEN_SIM.GetFingerprint(m)
        if max(DataStructs.BulkTanimotoSimilarity(q, act_fps)) > TANI_MAX:
            continue
        seen.add(canon)
        bg_rows.append({"source": src, "id": cid, "canonical_smiles": canon})
        got += 1
    print(f"  {src:8s} 할당 {quota:,} → 확보 {got:,} (스캔 {n_scan:,})")

bg = pd.DataFrame(bg_rows)
os.makedirs("data/interim", exist_ok=True)
bg.to_csv(OUT_BG, index=False, encoding="utf-8-sig")
print(f"배경 {len(bg):,}개 확보")
print(bg.source.value_counts().to_string())


# ---- 3. 학습셋 조립 ------------------------------------------------------------
bg_mols = [Chem.MolFromSmiles(s) for s in bg.canonical_smiles]
bg_mols = [m for m in bg_mols if m is not None]

all_mols = mols + bg_mols
y = np.r_[df.label.to_numpy(), np.zeros(len(bg_mols), dtype=int)]
origin = np.array(["real"] * len(mols) + ["np_background"] * len(bg_mols))
X = featurize(all_mols)
print(f"\n학습셋 {len(y):,}개 — active {int(y.sum()):,} / "
      f"inactive {int((y==0).sum()):,} (실측 {int((df.label==0).sum()):,} + 배경 {len(bg_mols):,})")
print(f"특징 {X.shape[1]}차원 (ECFP4 {NB} + FCFP4 {NB})")


# ---- 4. 정직한 검증: 배경 제외하고 실측만 Butina 교차검증 --------------------------
print("\n" + "=" * 76)
print("검증 — 실측만(배경 제외) Butina 군집 교차검증")
print("  배경을 넣고 채점하면 25번의 decoy 함정을 반복하게 되므로 뺀다")
print("=" * 76)
rfps = [GEN_E.GetFingerprint(m) for m in mols]
d = []
for i in range(1, len(rfps)):
    d.extend(1.0 - s for s in DataStructs.BulkTanimotoSimilarity(rfps[i], rfps[:i]))
cl = Butina.ClusterData(d, len(rfps), 0.4, isDistData=True)
groups = np.empty(len(rfps), dtype=int)
for cid, mem in enumerate(cl):
    for i in mem:
        groups[i] = cid

Xr, yr = X[:len(mols)], y[:len(mols)]
Xb, yb = X[len(mols):], y[len(mols):]
proba = np.zeros(len(yr))
sp = StratifiedGroupKFold(NFOLD, shuffle=True, random_state=SEED)
for tr, te in sp.split(Xr, yr, groups):
    # 각 폴드 학습에는 배경을 전부 넣는다(실제 모델과 같은 조건), 채점은 실측만
    Xtr = np.vstack([Xr[tr], Xb])
    ytr = np.r_[yr[tr], yb]
    c = LGBMClassifier(n_estimators=400, class_weight="balanced",
                       random_state=SEED, n_jobs=-1, verbosity=-1).fit(Xtr, ytr)
    proba[te] = c.predict_proba(Xr[te])[:, 1]

auc = roc_auc_score(yr, proba)
pr = average_precision_score(yr, proba)
print(f"  실측 ROC-AUC {auc:.3f}   PR-AUC {pr:.3f}   (Butina 군집 {len(cl):,}개)")
print(f"  참고 — 25c의 배경 없는 같은 조건 값은 0.895였다")
pd.DataFrame([{"ROC_AUC": auc, "PR_AUC": pr, "n_real": len(yr),
               "n_background": len(yb), "n_clusters": len(cl)}]
             ).to_csv(OUT_CV, index=False, encoding="utf-8-sig")


# ---- 5. 최종 모델: 전부로 학습 ----------------------------------------------------
final = LGBMClassifier(n_estimators=400, class_weight="balanced",
                       random_state=SEED, n_jobs=-1, verbosity=-1).fit(X, y)
os.makedirs("data/models", exist_ok=True)
with open(OUT_MODEL, "wb") as f:
    pickle.dump({
        "model": final, "nbits": NB, "features": "ECFP4+FCFP4",
        "n_active": int(y.sum()), "n_inactive_real": int((df.label == 0).sum()),
        "n_background": len(bg_mols), "potent_nM": POTENT_NM,
        "cv_roc_auc_real": auc,
        "background_ids": set(bg["id"].astype(str)),
        "known_active_smiles": [Chem.MolToSmiles(m) for m in act_mols],
    }, f)
print(f"\n저장 → {OUT_MODEL}")
print(f"저장 → {OUT_BG}")
