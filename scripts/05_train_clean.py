# -*- coding: utf-8 -*-
"""HSD17B13_IC50_merged.xlsx의 3번째 시트(same_dedup_keepdiff)를
IC50<=10000nM=active 로 라벨링하고, 4가지 fingerprint로 분류모델을 학습·비교한다."""
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import MACCSkeys, rdFingerprintGenerator
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.metrics import (roc_auc_score, classification_report,
                             confusion_matrix, average_precision_score)
from lightgbm import LGBMClassifier

SRC = "data/HSD17B13_IC50_merged.xlsx"
ACTIVE_MAX = 10000.0   # IC50 <= 10000nM => active
NBITS = 1024

# ---------- 라벨링 규칙 ----------
def make_label(ic50, rel):
    rel = str(rel).strip()
    if pd.isna(ic50):
        return np.nan
    if rel in ("<", "<="):          # 상한: value 이하가 확실 → value<=10000이면 active 확정
        return 1 if ic50 <= ACTIVE_MAX else 0
    if rel in (">", ">="):          # 하한: value 이상 → 항상 inactive(>10000 취지에 부합)
        return 0
    return 1 if ic50 <= ACTIVE_MAX else 0   # '=' 등

df = pd.read_excel(SRC, sheet_name="same_dedup_keepdiff")
df = df.dropna(subset=["canonical_smiles", "ic50_nM"]).copy()
df["label"] = [make_label(v, r) for v, r in zip(df["ic50_nM"], df["relation"])]
df = df.dropna(subset=["label"])
df["label"] = df["label"].astype(int)

print("=== 행(row) 기준 라벨 분포 ===")
print(df["label"].value_counts().rename({1: "active", 0: "inactive"}).to_string())
gray = df[(df["relation"].astype(str).str.strip() == "=") &
          (df["ic50_nM"] > 10000) & (df["ic50_nM"] < 20000)]
print(f"회색지대(10000~20000nM, '=') 행: {len(gray)} → inactive 처리됨")

# ---------- 물질(canonical) 단위로 dedup (같은 분자가 train/test에 겹쳐 성능 뻥튀기되는 것 방지) ----------
# 같은 물질에 측정이 여러 개면: 하나라도 active면 active로 간주
comp = (df.groupby("canonical_smiles")
          .agg(label=("label", "max"),
               n_rows=("label", "size"),
               contradictory=("label", lambda s: s.nunique() > 1))
          .reset_index())
print(f"\n=== 물질(canonical) 기준: {len(comp)}개 ===")
print(comp["label"].value_counts().rename({1: "active", 0: "inactive"}).to_string())
print(f"라벨이 충돌한 물질(측정마다 active/inactive 갈림): {int(comp['contradictory'].sum())}개")

# ---------- fingerprint 4종 계산 ----------
gen_ecfp = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=NBITS)
gen_rdk = rdFingerprintGenerator.GetRDKitFPGenerator(fpSize=NBITS)
gen_ap = rdFingerprintGenerator.GetAtomPairGenerator(fpSize=NBITS)

def maccs_np(mol):
    fp = MACCSkeys.GenMACCSKeys(mol)
    arr = np.zeros((fp.GetNumBits(),), dtype=np.int8)
    DataStructs.ConvertToNumpyArray(fp, arr)
    return arr

fps = {"ECFP4": [], "MACCS": [], "RDKit": [], "AtomPair": []}
y, keep = [], []
for smi, lab in zip(comp["canonical_smiles"], comp["label"]):
    mol = Chem.MolFromSmiles(str(smi))
    if mol is None:
        continue
    fps["ECFP4"].append(gen_ecfp.GetFingerprintAsNumPy(mol))
    fps["RDKit"].append(gen_rdk.GetFingerprintAsNumPy(mol))
    fps["AtomPair"].append(gen_ap.GetFingerprintAsNumPy(mol))
    fps["MACCS"].append(maccs_np(mol))
    y.append(lab)
y = np.array(y)
print(f"\n학습 대상 물질: {len(y)}개 (active {int(y.sum())}, inactive {int((y==0).sum())})")

# ---------- 4종 fingerprint로 학습·비교 (5-fold CV) ----------
print("\n" + "=" * 60)
print("Fingerprint별 5-fold 교차검증 결과 (LightGBM, class_weight=balanced)")
print("=" * 60)
print(f"{'Fingerprint':10s} {'ROC-AUC':>9s} {'PR-AUC':>9s} {'Recall(act)':>12s} {'Precision(act)':>15s}")
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
results = {}
for name, mat in fps.items():
    X = np.vstack(mat)
    clf = LGBMClassifier(n_estimators=400, class_weight="balanced",
                         random_state=42, n_jobs=-1, verbosity=-1)
    proba = cross_val_predict(clf, X, y, cv=skf, method="predict_proba",
                              n_jobs=-1)[:, 1]
    pred = (proba >= 0.5).astype(int)
    auc = roc_auc_score(y, proba)
    pr = average_precision_score(y, proba)
    tn, fp_, fn, tp = confusion_matrix(y, pred).ravel()
    recall = tp / (tp + fn) if (tp + fn) else 0
    prec = tp / (tp + fp_) if (tp + fp_) else 0
    results[name] = auc
    print(f"{name:10s} {auc:9.3f} {pr:9.3f} {recall:12.3f} {prec:15.3f}")

best = max(results, key=results.get)
print(f"\n>>> 최고 fingerprint: {best} (ROC-AUC {results[best]:.3f})")
