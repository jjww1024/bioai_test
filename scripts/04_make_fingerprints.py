# -*- coding: utf-8 -*-
"""3번째 시트(same_dedup_keepdiff)의 물질로 4가지 fingerprint를 계산해
새 엑셀(HSD17B13_fingerprints.xlsx)에 시트별로 저장한다.
 - ECFP4 (Morgan radius=2, 1024bit)
 - MACCS (166 keys)
 - RDKit topological (1024bit)
 - AtomPair (1024bit)  ← +1 추가 fingerprint
"""
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import MACCSkeys, rdFingerprintGenerator
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")

SRC = "data/HSD17B13_IC50_merged.xlsx"
OUT = "data/HSD17B13_fingerprints.xlsx"
NBITS = 1024

df = pd.read_excel(SRC, sheet_name="same_dedup_keepdiff")
# fingerprint 계산에 쓸 기준 컬럼 (구조 = canonical_smiles, 라벨 = ic50_nM)
meta_cols = ["canonical_smiles", "ic50_nM", "relation", "sources"]
df = df.dropna(subset=["canonical_smiles"]).reset_index(drop=True)

# 생성기(한 번만 만들어 재사용)
gen_ecfp = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=NBITS)
gen_rdk = rdFingerprintGenerator.GetRDKitFPGenerator(fpSize=NBITS)
gen_ap = rdFingerprintGenerator.GetAtomPairGenerator(fpSize=NBITS)


def maccs_np(mol):
    fp = MACCSkeys.GenMACCSKeys(mol)
    arr = np.zeros((fp.GetNumBits(),), dtype=np.int8)
    DataStructs.ConvertToNumpyArray(fp, arr)
    return arr


# 분자 파싱은 한 번만, 4가지 FP 동시 계산
rows = {"ECFP4": [], "MACCS": [], "RDKit": [], "AtomPair": []}
keep_idx = []
for i, smi in enumerate(df["canonical_smiles"]):
    mol = Chem.MolFromSmiles(str(smi))
    if mol is None:
        continue
    keep_idx.append(i)
    rows["ECFP4"].append(gen_ecfp.GetFingerprintAsNumPy(mol))
    rows["RDKit"].append(gen_rdk.GetFingerprintAsNumPy(mol))
    rows["AtomPair"].append(gen_ap.GetFingerprintAsNumPy(mol))
    rows["MACCS"].append(maccs_np(mol))

meta = df.loc[keep_idx, meta_cols].reset_index(drop=True)

with pd.ExcelWriter(OUT, engine="openpyxl") as w:
    for name, mat in rows.items():
        X = np.vstack(mat)
        cols = [f"X{j+1}" for j in range(X.shape[1])]
        fp_df = pd.concat([meta, pd.DataFrame(X, columns=cols)], axis=1)
        fp_df.to_excel(w, sheet_name=name, index=False)
        print(f"[{name}] {X.shape[0]}행 x {X.shape[1]}bit")

print("\n저장 완료 →", OUT)
print(f"입력 {len(df)}개 중 {len(keep_idx)}개 정상 변환")
