# -*- coding: utf-8 -*-
"""decoy로 1:1 균형 맞춘 학습셋(HSD17B13_train_with_decoys.xlsx)으로
4종 fingerprint 분류모델을 5-fold CV 비교하고, 최고 모델을 전체 데이터로
다시 학습해 스크리닝용으로 저장한다.

decoy 주의: decoy는 active와 구조가 일부러 다르게(Tanimoto<=0.35) 뽑혔으므로
'active vs decoy'는 쉽게 갈린다 → 전체 ROC-AUC는 부풀 수 있음.
그래서 '실측 inactive 396개를 CV에서 얼마나 inactive로 맞히는지'를 따로 본다
(진짜 어려운 판별력 지표).
"""
import sys
import numpy as np
import pandas as pd
import pickle
from rdkit import Chem, DataStructs
from rdkit.Chem import MACCSkeys, rdFingerprintGenerator
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import (roc_auc_score, average_precision_score,
                             confusion_matrix)
from lightgbm import LGBMClassifier

# 사용법: python 07_train_with_decoys.py [학습셋.xlsx] [모델출력.pkl]
#   기본은 06(전역창) decoy. DUD-E(06b) 결과로 비교하려면 인자로 파일 지정.
SRC = sys.argv[1] if len(sys.argv) > 1 else "data/HSD17B13_train_with_decoys.xlsx"
MODEL_OUT = sys.argv[2] if len(sys.argv) > 2 else "data/HSD17B13_screen_model.pkl"
NBITS = 1024
print(f"학습셋: {SRC}")

df = pd.read_excel(SRC).dropna(subset=["canonical_smiles"]).reset_index(drop=True)
print("학습셋 구성:")
print(df.groupby(["label", "source"]).size().to_string())

# ---------- fingerprint 생성기 ----------
gens = {
    "ECFP4": rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=NBITS),
    "RDKit": rdFingerprintGenerator.GetRDKitFPGenerator(fpSize=NBITS),
    "AtomPair": rdFingerprintGenerator.GetAtomPairGenerator(fpSize=NBITS),
}


def maccs_np(mol):
    fp = MACCSkeys.GenMACCSKeys(mol)
    arr = np.zeros((fp.GetNumBits(),), dtype=np.int8)
    DataStructs.ConvertToNumpyArray(fp, arr)
    return arr


def featurize(name, mol):
    if name == "MACCS":
        return maccs_np(mol)
    return gens[name].GetFingerprintAsNumPy(mol)


FP_NAMES = ["ECFP4", "MACCS", "RDKit", "AtomPair"]
fps = {n: [] for n in FP_NAMES}
y, src = [], []
for smi, lab, s in zip(df["canonical_smiles"], df["label"], df["source"]):
    mol = Chem.MolFromSmiles(str(smi))
    if mol is None:
        continue
    for n in FP_NAMES:
        fps[n].append(featurize(n, mol))
    y.append(int(lab))
    src.append(s)
y = np.array(y)
src = np.array(src)
real_inact = (y == 0) & (src == "real")   # 실측 inactive 마스크
print(f"\n학습 물질 {len(y)}개 | active {int(y.sum())} "
      f"inactive {int((y==0).sum())} (실측 {int(real_inact.sum())} + decoy {int(((y==0)&(src=='decoy')).sum())})")

# ---------- 5-fold CV 비교 ----------
print("\n" + "=" * 74)
print("Fingerprint별 5-fold CV (LightGBM, class_weight=balanced)")
print("=" * 74)
print(f"{'FP':9s} {'ROC-AUC':>8s} {'PR-AUC':>8s} {'Recall(act)':>12s} "
      f"{'Prec(act)':>10s} {'실측inact 정답률':>16s}")
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
results = {}
for name in FP_NAMES:
    X = np.vstack(fps[name])
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
    # 실측 inactive를 실제로 inactive(0)로 맞힌 비율
    ri_acc = np.mean(pred[real_inact] == 0) if real_inact.any() else float("nan")
    results[name] = auc
    print(f"{name:9s} {auc:8.3f} {pr:8.3f} {recall:12.3f} {prec:10.3f} {ri_acc:16.3f}")

best = max(results, key=results.get)
print(f"\n>>> 최고 fingerprint: {best} (ROC-AUC {results[best]:.3f})")

# ---------- 최고 fingerprint로 전체 데이터 재학습 → 저장 ----------
Xbest = np.vstack(fps[best])
final = LGBMClassifier(n_estimators=400, class_weight="balanced",
                       random_state=42, n_jobs=-1, verbosity=-1)
final.fit(Xbest, y)
with open(MODEL_OUT, "wb") as f:
    pickle.dump({"model": final, "fp_name": best, "nbits": NBITS,
                 "n_active": int(y.sum()), "n_inactive": int((y == 0).sum())}, f)
print(f"\n스크리닝용 모델 저장: {MODEL_OUT} (fingerprint={best}, {NBITS}bit)")
