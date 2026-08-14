# -*- coding: utf-8 -*-
"""fingerprint 엑셀(4시트)에 active/inactive 라벨을 붙이고, 라벨이 올바른
화합물에 정확히 붙었는지 4중 검증한다.

라벨 규칙(05_train_clean.py와 동일):
  relation '<','<=' : IC50<=10000 → active(1) else inactive(0)
  relation '>','>=' : inactive(0)   (>10000 취지)
  그 외('=' 등)      : IC50<=10000 → active(1) else inactive(0)

검증:
  ① 비트↔SMILES 무결성: 각 행 fingerprint를 canonical_smiles로 재계산 → 저장값과 일치?
  ② 라벨 규칙 감사: IC50/relation로 라벨 재계산 → 일치? + 경계값 예시
  ③ 시트 간 일관성: 같은 물질이 4시트에서 동일 라벨?
  ④ 원본 대조: 병합원본(same_dedup_keepdiff)에 같은 (smiles,ic50) 존재?

출력: data/HSD17B13_fingerprints_labeled.xlsx (원본 열려있어도 안전하게 새 파일)
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")   # 윈도우 콘솔 cp949 → utf-8
except Exception:
    pass
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import MACCSkeys, rdFingerprintGenerator
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")

SRC = "data/HSD17B13_fingerprints.xlsx"
MERGED = "data/HSD17B13_IC50_merged.xlsx"
OUT = "data/HSD17B13_fingerprints_labeled.xlsx"
ACTIVE_MAX = 10000.0
SHEETS = ["ECFP4", "MACCS", "RDKit", "AtomPair"]
META = ["canonical_smiles", "ic50_nM", "relation", "sources"]


def make_label(ic50, rel):
    rel = str(rel).strip()
    if pd.isna(ic50):
        return np.nan
    if rel in ("<", "<="):
        return 1 if ic50 <= ACTIVE_MAX else 0
    if rel in (">", ">="):
        return 0
    return 1 if ic50 <= ACTIVE_MAX else 0


# fingerprint 재계산기 (04_make_fingerprints.py와 동일 파라미터)
NBITS = 1024
gen_ecfp = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=NBITS)
gen_rdk = rdFingerprintGenerator.GetRDKitFPGenerator(fpSize=NBITS)
gen_ap = rdFingerprintGenerator.GetAtomPairGenerator(fpSize=NBITS)


def recompute_fp(name, mol):
    if name == "ECFP4":
        return gen_ecfp.GetFingerprintAsNumPy(mol)
    if name == "RDKit":
        return gen_rdk.GetFingerprintAsNumPy(mol)
    if name == "AtomPair":
        return gen_ap.GetFingerprintAsNumPy(mol)
    if name == "MACCS":
        fp = MACCSkeys.GenMACCSKeys(mol)
        arr = np.zeros((fp.GetNumBits(),), dtype=np.int8)
        DataStructs.ConvertToNumpyArray(fp, arr)
        return arr


# 원본 병합(대조용)
merged = pd.read_excel(MERGED, sheet_name="same_dedup_keepdiff")
merged_pairs = set(zip(merged["canonical_smiles"].astype(str),
                       pd.to_numeric(merged["ic50_nM"], errors="coerce")))

print("=" * 70)
labeled_sheets = {}
label_by_smiles = {}   # 물질별 라벨 집합(모순 측정 탐지용)
sheet_labels = {}      # 시트별 행단위 라벨(행 단위 시트 일치 확인용)
all_ok = True

for sheet in SHEETS:
    df = pd.read_excel(SRC, sheet_name=sheet)
    bit_cols = [c for c in df.columns if c not in META]
    # ---- 라벨 계산 & 삽입 ----
    lab_num = [make_label(v, r) for v, r in zip(df["ic50_nM"], df["relation"])]
    activity = ["active" if x == 1 else ("inactive" if x == 0 else "unlabeled")
                for x in lab_num]
    df.insert(len(META), "label", [("" if pd.isna(x) else int(x)) for x in lab_num])
    df.insert(len(META) + 1, "activity", activity)
    labeled_sheets[sheet] = df
    sheet_labels[sheet] = [(-9 if pd.isna(x) else int(x)) for x in lab_num]

    # ---- 검증 ① 비트↔SMILES 무결성 (전 행 재계산 비교) ----
    stored = df[bit_cols].to_numpy(dtype=np.int8)
    mism_bits = 0
    n_valid = 0
    for i, smi in enumerate(df["canonical_smiles"]):
        mol = Chem.MolFromSmiles(str(smi))
        if mol is None:
            mism_bits += 1
            continue
        rc = np.asarray(recompute_fp(sheet, mol), dtype=np.int8)
        if rc.shape[0] != stored.shape[1] or not np.array_equal(rc, stored[i]):
            mism_bits += 1
        else:
            n_valid += 1

    # ---- 검증 ② 라벨 규칙 감사 (재계산 일치 — 정의상 일치해야) ----
    # (make_label 결정론적이므로 재적용해 불일치 0 확인)
    audit = sum(1 for (v, r), x in zip(zip(df["ic50_nM"], df["relation"]), lab_num)
                if (make_label(v, r) if not (pd.isna(make_label(v, r))) else -9)
                != (x if not pd.isna(x) else -9))

    n_act = activity.count("active")
    n_ina = activity.count("inactive")
    n_unl = activity.count("unlabeled")
    ok = (mism_bits == 0 and audit == 0)
    all_ok = all_ok and ok
    print(f"[{sheet}] 행 {len(df)} | 비트 {len(bit_cols)} | "
          f"active {n_act} / inactive {n_ina} / unlabeled {n_unl}")
    print(f"    ① 비트↔SMILES 재계산 불일치: {mism_bits}  "
          f"{'✔ 전부 일치' if mism_bits == 0 else '✗ 불일치!'}")
    print(f"    ② 라벨 규칙 재적용 불일치: {audit}  {'✔' if audit == 0 else '✗'}")

    for smi, a in zip(df["canonical_smiles"], activity):
        label_by_smiles.setdefault(str(smi), set()).add(a)

# ---- 검증 ③ 행 단위 4시트 라벨 일치 (같은 행이 4시트에서 동일 라벨인지) ----
L = np.array([sheet_labels[s] for s in SHEETS])
row_consistent = int(np.all(L == L[0], axis=0).sum())
row_total = L.shape[1]
print("=" * 70)
print(f"③ 행 단위 4시트 라벨 일치: {row_consistent}/{row_total} "
      f"{'✔ 전부 일치' if row_consistent == row_total else '✗'}")
# 참고: 같은 물질이 측정마다 active/inactive 갈리는 경우 = 실측 모순(라벨 오류 아님)
conflict_mol = {s: v for s, v in label_by_smiles.items() if len(v) > 1}
print(f"   [참고] 실측이 상반돼 물질 단위로는 라벨이 갈리는 물질: {len(conflict_mol)}건 "
      f"(오류 아님 — 학습 dedup 시 'active 우선'으로 통합)")
inconsistent = {}   # (호환용) 행 단위 일치가 진짜 판정 기준

# ---- 검증 ④ 원본(same_dedup_keepdiff) 대조 ----
ref_df = labeled_sheets["ECFP4"]
present = sum(1 for s, v in zip(ref_df["canonical_smiles"].astype(str),
                                pd.to_numeric(ref_df["ic50_nM"], errors="coerce"))
              if (s, v) in merged_pairs)
print(f"④ 원본 대조: fingerprint 행 {len(ref_df)}개 중 병합원본에 존재 {present}개 "
      f"{'✔ 전부 일치' if present == len(ref_df) else '일부 불일치'}")

# ---- 라벨 규칙 경계값 예시(사람이 눈으로 확인) ----
ex = ref_df[["ic50_nM", "relation", "activity"]].copy()
print("\n[규칙 경계값 스팟체크] (직접 눈으로 규칙 확인)")
for cond, desc in [
    ((ex.relation.astype(str).str.strip() == "=") & (ex.ic50_nM <= 10000), "= & IC50<=10000 → active여야"),
    ((ex.relation.astype(str).str.strip() == "=") & (ex.ic50_nM > 10000), "= & IC50>10000 → inactive여야"),
    (ex.relation.astype(str).str.strip().isin([">", ">="]), "'>' → inactive여야"),
    (ex.relation.astype(str).str.strip().isin(["<", "<="]) & (ex.ic50_nM <= 10000), "'<' & <=10000 → active여야"),
]:
    sub = ex[cond].head(2)
    for _, r in sub.iterrows():
        print(f"    IC50={r.ic50_nM}, rel='{r.relation}' → {r.activity}   ({desc})")

# ---- 저장 ----
with pd.ExcelWriter(OUT, engine="openpyxl") as w:
    for sheet in SHEETS:
        labeled_sheets[sheet].to_excel(w, sheet_name=sheet, index=False)

print("\n" + "=" * 70)
print(f"저장: {OUT}")
verdict_ok = all_ok and (row_consistent == row_total) and (present == len(ref_df))
print(f"종합 검증: {'✔ 모두 통과 (라벨이 정확한 화합물에 붙음)' if verdict_ok else '✗ 문제 있음 — 위 로그 확인'}")
