# -*- coding: utf-8 -*-
"""30b에서 드러난 '할로겐 편향'이 교란인지 신호인지 가린다.

30b 관찰:
  상위 100의 99.0%가 할로겐 함유 (라이브러리 기준선 6.4%)
  학습 active 92.5% / inactive 87.9% — 둘 다 높다

가설 두 가지가 가능하다.
  (가) 교란  할로겐은 활성과 무관하고, '학습 영역'의 표식일 뿐이다.
            모델은 활성이 아니라 영역 소속을 재고 있다.
  (나) 신호  할로겐 자리가 실제 결합에 관여한다. 모델이 맞게 배운 것이고,
            천연물에 그런 분자가 없다는 게 진짜 결론이다.

가리는 방법 — 할로겐을 지우고 다시 학습시킨다.
  모든 F/Cl/Br/I를 H로 치환한 뒤 같은 조건으로 Butina 교차검증.
  (가)라면 성능이 거의 그대로다 (할로겐은 활성 판별에 안 쓰였으니).
  (나)라면 성능이 무너진다.

추가로 '영역 분리 가능성'도 잰다 — 학습 active 대 천연물 라이브러리를
구분하는 분류기를 만들어 본다. AUC가 1.0에 가까우면 두 공간이 자명하게
갈린다는 뜻이고, 그 경우 천연물을 음성으로 넣은 어떤 모델이든
'합성 대 천연'을 배우게 된다(= 교란이 구조적으로 불가피).

출력:
  data/reports/261124_confound_diagnosis.csv
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import rdFingerprintGenerator as rfg
from rdkit.ML.Cluster import Butina
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier

RDLogger.DisableLog("rdApp.*")

MERGED = "data/interim/261010_HSD17B13_IC50_merged.xlsx"
FULL = "data/screening/261124_screen_full_ranked.csv.gz"
OUT = "data/reports/261124_confound_diagnosis.csv"
SEED = 42
NFOLD = 5
NB = 1024

inv = rfg.GetMorganFeatureAtomInvGen()
GEN_E = rfg.GetMorganGenerator(radius=2, fpSize=NB)
GEN_F = rfg.GetMorganGenerator(radius=2, fpSize=NB, atomInvariantsGenerator=inv)
HALOGENS = {9, 17, 35, 53}        # F, Cl, Br, I


def dehalogenate(mol):
    """모든 할로겐을 수소로 바꾼다. 분자 골격은 그대로 두고 치환기만 지운다."""
    rw = Chem.RWMol(mol)
    for atom in rw.GetAtoms():
        if atom.GetAtomicNum() in HALOGENS:
            atom.SetAtomicNum(1)
            atom.SetNoImplicit(False)
            atom.SetFormalCharge(0)
    try:
        m = rw.GetMol()
        Chem.SanitizeMol(m)
        return Chem.RemoveHs(m)
    except Exception:
        return None


def feats(mols):
    e = np.vstack([GEN_E.GetFingerprintAsNumPy(m) for m in mols])
    f = np.vstack([GEN_F.GetFingerprintAsNumPy(m) for m in mols])
    return np.hstack([e, f]).astype(np.float32)


def butina(mols, cutoff=0.4):
    fps = [GEN_E.GetFingerprint(m) for m in mols]
    d = []
    for i in range(1, len(fps)):
        d.extend(1.0 - s for s in DataStructs.BulkTanimotoSimilarity(fps[i], fps[:i]))
    cl = Butina.ClusterData(d, len(fps), cutoff, isDistData=True)
    g = np.empty(len(fps), dtype=int)
    for cid, mem in enumerate(cl):
        for i in mem:
            g[i] = cid
    return g, len(cl)


def cv_auc(X, y, groups):
    p = np.zeros(len(y))
    for tr, te in StratifiedGroupKFold(NFOLD, shuffle=True, random_state=SEED).split(X, y, groups):
        c = LGBMClassifier(n_estimators=300, class_weight="balanced",
                           random_state=SEED, n_jobs=-1, verbosity=-1).fit(X[tr], y[tr])
        p[te] = c.predict_proba(X[te])[:, 1]
    return roc_auc_score(y, p)


# ---- 데이터 -------------------------------------------------------------------
df = pd.read_excel(MERGED, sheet_name="robust_dedup")
df = df.dropna(subset=["canonical_smiles", "ic50_median_nM"]).reset_index(drop=True)
mols, keep = [], []
for i, s in enumerate(df["canonical_smiles"]):
    m = Chem.MolFromSmiles(str(s))
    if m is not None:
        mols.append(m); keep.append(i)
df = df.loc[keep].reset_index(drop=True)
y = (df["ic50_median_nM"] <= 1000).astype(int).to_numpy()
print(f"실측 {len(y):,}개 — active {int(y.sum()):,} / inactive {int((y==0).sum()):,}")

dehal, dy, dkeep = [], [], []
for m, lab in zip(mols, y):
    d = dehalogenate(m)
    if d is not None:
        dehal.append(d); dy.append(lab); dkeep.append(True)
dy = np.array(dy)
print(f"할로겐 제거 성공 {len(dehal):,}개")

# ---- 진단 1: 할로겐 제거 전후 ------------------------------------------------------
print("\n" + "=" * 72)
print("[진단 1] 할로겐을 지우면 활성 판별력이 무너지는가")
print("=" * 72)
g_orig, n_orig = butina(mols)
auc_orig = cv_auc(feats(mols), y, g_orig)
g_de, n_de = butina(dehal)
auc_de = cv_auc(feats(dehal), dy, g_de)
print(f"  원본        Butina 군집 {n_orig:,}  ROC-AUC {auc_orig:.3f}")
print(f"  할로겐 제거  Butina 군집 {n_de:,}  ROC-AUC {auc_de:.3f}")
print(f"  차이 {auc_de - auc_orig:+.3f}")
if auc_orig - auc_de < 0.03:
    verdict1 = "교란 — 할로겐 없이도 거의 같은 성능. 활성 판별에 안 쓰이고 있다"
else:
    verdict1 = "신호 — 할로겐을 지우니 성능이 떨어진다. 결합에 관여할 수 있다"
print(f"  → {verdict1}")

# ---- 진단 2: 영역이 자명하게 갈리는가 -----------------------------------------------
print("\n" + "=" * 72)
print("[진단 2] 학습 active 대 천연물 라이브러리 — 얼마나 쉽게 갈리는가")
print("  AUC가 1.0에 가까우면, 천연물을 음성으로 쓰는 어떤 모델이든")
print("  '활성 여부'가 아니라 '합성 대 천연'을 배우게 된다")
print("=" * 72)
lib = pd.read_csv(FULL, usecols=["canonical_smiles"], low_memory=False)
lib = lib.sample(5000, random_state=SEED)
lmols = [Chem.MolFromSmiles(s) for s in lib.canonical_smiles]
lmols = [m for m in lmols if m is not None]
act_mols = [m for m, l in zip(mols, y) if l == 1]
Xd = feats(act_mols + lmols)
yd = np.r_[np.ones(len(act_mols), int), np.zeros(len(lmols), int)]
pd_ = np.zeros(len(yd))
for tr, te in StratifiedKFold(NFOLD, shuffle=True, random_state=SEED).split(Xd, yd):
    c = LGBMClassifier(n_estimators=300, class_weight="balanced",
                       random_state=SEED, n_jobs=-1, verbosity=-1).fit(Xd[tr], yd[tr])
    pd_[te] = c.predict_proba(Xd[te])[:, 1]
auc_dom = roc_auc_score(yd, pd_)
print(f"  영역 분류 ROC-AUC {auc_dom:.4f}  (active {len(act_mols):,} 대 천연물 {len(lmols):,})")

# 할로겐을 지운 상태에서도 영역이 갈리나
Xd2 = feats([dehalogenate(m) or m for m in act_mols] + [dehalogenate(m) or m for m in lmols])
pd2 = np.zeros(len(yd))
for tr, te in StratifiedKFold(NFOLD, shuffle=True, random_state=SEED).split(Xd2, yd):
    c = LGBMClassifier(n_estimators=300, class_weight="balanced",
                       random_state=SEED, n_jobs=-1, verbosity=-1).fit(Xd2[tr], yd[tr])
    pd2[te] = c.predict_proba(Xd2[te])[:, 1]
auc_dom2 = roc_auc_score(yd, pd2)
print(f"  할로겐 지운 뒤 영역 분류 ROC-AUC {auc_dom2:.4f}")
print(f"  → 할로겐을 지워도 영역은 {'여전히 갈린다' if auc_dom2 > 0.95 else '덜 갈린다'}"
      f" ({auc_dom:.3f} → {auc_dom2:.3f})")

# ---- 저장 ---------------------------------------------------------------------
os.makedirs("data/reports", exist_ok=True)
pd.DataFrame([
    {"진단": "활성판별 (원본)", "ROC_AUC": round(auc_orig, 4), "n": len(y)},
    {"진단": "활성판별 (할로겐 제거)", "ROC_AUC": round(auc_de, 4), "n": len(dy)},
    {"진단": "영역분류 (원본)", "ROC_AUC": round(auc_dom, 4), "n": len(yd)},
    {"진단": "영역분류 (할로겐 제거)", "ROC_AUC": round(auc_dom2, 4), "n": len(yd)},
]).to_csv(OUT, index=False, encoding="utf-8-sig")

print("\n" + "=" * 72)
print("[결론]")
print("=" * 72)
print(f"  활성 판별  {auc_orig:.3f} → {auc_de:.3f} (할로겐 제거)")
print(f"  영역 분류  {auc_dom:.3f} → {auc_dom2:.3f} (할로겐 제거)")
print(f"  {verdict1}")
print(f"\n저장 → {OUT}")
