# -*- coding: utf-8 -*-
"""fingerprint(ECFP4 1024) + descriptor(217)를 이어붙인 결합 표현으로 학습하고,
fingerprint-only / descriptor-only / 결합 을 같은 조건에서 비교한다.

- 실측 데이터(active 2049 / inactive 396), 물질(canonical) 단위 dedup
- LightGBM(트리) → 이진 비트 + 연속 descriptor 혼합 OK, 스케일 불필요
"""
import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import rdFingerprintGenerator
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score, average_precision_score, confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from lightgbm import LGBMClassifier

SRC = "data/HSD17B13_descriptors.csv"   # canonical_smiles + label + descriptor 217
META = ["canonical_smiles", "ic50_nM", "relation", "sources", "label"]
NBITS = 1024

df = pd.read_csv(SRC).dropna(subset=["label"]).copy()
desc_cols = [c for c in df.columns if c not in META]
agg = {c: "first" for c in desc_cols}
agg["label"] = "max"
comp = df.groupby("canonical_smiles").agg(agg).reset_index()
comp["label"] = comp["label"].astype(int)

# ---------- ECFP4 계산 ----------
gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=NBITS)
fp_rows, desc_rows, y = [], [], []
D = comp[desc_cols].replace([np.inf, -np.inf], np.nan).to_numpy()
for i, smi in enumerate(comp["canonical_smiles"]):
    mol = Chem.MolFromSmiles(str(smi))
    if mol is None:
        continue
    fp_rows.append(gen.GetFingerprintAsNumPy(mol))
    desc_rows.append(D[i])
    y.append(int(comp["label"].iloc[i]))
y = np.array(y)
FP = np.vstack(fp_rows).astype(np.float32)
DESC = np.vstack(desc_rows).astype(np.float32)
COMB = np.hstack([FP, DESC])
print(f"물질 {len(y)}개 | active {int(y.sum())} / inactive {int((y==0).sum())}")
print(f"특징 차원: FP {FP.shape[1]} | DESC {DESC.shape[1]} | 결합 {COMB.shape[1]}")


def evaluate(name, X):
    pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("clf", LGBMClassifier(n_estimators=400, class_weight="balanced",
                               random_state=42, n_jobs=-1, verbosity=-1)),
    ])
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    proba = cross_val_predict(pipe, X, y, cv=skf, method="predict_proba", n_jobs=-1)[:, 1]
    pred = (proba >= 0.5).astype(int)
    tn, fp_, fn, tp = confusion_matrix(y, pred).ravel()
    auc = roc_auc_score(y, proba)
    pr = average_precision_score(y, proba)
    print(f"{name:16s} {auc:8.3f} {pr:8.3f} {tp/(tp+fn):12.3f} {tp/(tp+fp_):10.3f}")
    return auc


print("\n" + "=" * 62)
print(f"{'표현':16s} {'ROC-AUC':>8s} {'PR-AUC':>8s} {'Recall(act)':>12s} {'Prec(act)':>10s}")
print("=" * 62)
a1 = evaluate("fingerprint", FP)
a2 = evaluate("descriptor", DESC)
a3 = evaluate("결합(FP+DESC)", COMB)
print("=" * 62)
best = max([("fingerprint", a1), ("descriptor", a2), ("결합", a3)], key=lambda t: t[1])
print(f">>> 최고: {best[0]} (ROC-AUC {best[1]:.3f})")
gain = a3 - max(a1, a2)
print(f"결합이 단일 최고보다 {gain:+.3f} ROC-AUC "
      f"({'개선' if gain > 0.002 else '사실상 동일/미미'})")
