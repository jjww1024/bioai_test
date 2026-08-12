# -*- coding: utf-8 -*-
"""HSD17B13 실측 화합물(same_dedup_keepdiff 시트)에 대해 RDKit 2D 분자
descriptor(~210종)를 전부 계산해 라벨과 함께 저장한다.

descriptor = 분자의 물리화학·위상 수치 (MW, logP, TPSA, 방향족고리 수 등).
fingerprint(0/1 비트)와 달리 연속값이라 ML에 쓸 땐 결측/무한대 정리 + 스케일링 필요.

출력:
  data/HSD17B13_descriptors.xlsx  (canonical_smiles, ic50_nM, relation, sources,
                                    label, + descriptor ~210열)
  data/HSD17B13_descriptors.csv
"""
import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")

SRC = "data/HSD17B13_IC50_merged.xlsx"
OUT_XLSX = "data/HSD17B13_descriptors.xlsx"
OUT_CSV = "data/HSD17B13_descriptors.csv"
ACTIVE_MAX = 10000.0


def make_label(ic50, rel):
    rel = str(rel).strip()
    if pd.isna(ic50):
        return np.nan
    if rel in ("<", "<="):
        return 1 if ic50 <= ACTIVE_MAX else 0
    if rel in (">", ">="):
        return 0
    return 1 if ic50 <= ACTIVE_MAX else 0


df = pd.read_excel(SRC, sheet_name="same_dedup_keepdiff")
df = df.dropna(subset=["canonical_smiles"]).reset_index(drop=True)
df["label"] = [make_label(v, r) for v, r in zip(df["ic50_nM"], df["relation"])]

# RDKit 등록 descriptor 전체 이름
desc_names = [name for name, _ in Descriptors._descList]
print(f"RDKit descriptor {len(desc_names)}종 계산")

meta_cols = ["canonical_smiles", "ic50_nM", "relation", "sources", "label"]
rows, keep_idx = [], []
for i, smi in enumerate(df["canonical_smiles"]):
    mol = Chem.MolFromSmiles(str(smi))
    if mol is None:
        continue
    d = Descriptors.CalcMolDescriptors(mol)          # 전체 descriptor dict
    rows.append([d.get(n, np.nan) for n in desc_names])
    keep_idx.append(i)

X = pd.DataFrame(rows, columns=desc_names)

# 결측/무한대 정리 (ML 투입 전 최소 처리)
n_inf = np.isinf(X.to_numpy(dtype=float, na_value=np.nan)).sum()
X = X.replace([np.inf, -np.inf], np.nan)
n_nan = int(X.isna().sum().sum())
print(f"정상 변환 {len(keep_idx)}/{len(df)}개 | inf {int(n_inf)}개, NaN {n_nan}개 발견 "
      f"(ML 시 imputation/스케일링 필요)")

meta = df.loc[keep_idx, meta_cols].reset_index(drop=True)
out = pd.concat([meta, X.reset_index(drop=True)], axis=1)

out.to_csv(OUT_CSV, index=False)
with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as w:
    out.to_excel(w, sheet_name="descriptors", index=False)

lab = out["label"].dropna()
print(f"\n저장: {OUT_XLSX} | {OUT_CSV}")
print(f"행 {len(out)} x 열 {out.shape[1]} (메타 {len(meta_cols)} + descriptor {len(desc_names)})")
print(f"라벨 분포: active {int((lab==1).sum())} / inactive {int((lab==0).sum())}")
print("\ndescriptor 예시(앞 12종):", ", ".join(desc_names[:12]))
