# -*- coding: utf-8 -*-
"""외부 천연물 시험셋 설계 0단계 — 우리 HSD17B13 데이터에 천연물이 섞여 있는가.

Cockroft 2019이 천연물 세트를 만든 방법과 같은 절차다.
  "ChEMBL 데이터를 천연물 DB와 InChIKey·SMILES로 대조해 두 더미로 쪼갠다"

이 확인이 먼저인 이유 두 가지:
  1. 섞여 있다면 그 분자들이 곧 '진짜 외부 천연물 시험셋'이다. 학습에서 빼야 한다.
  2. 0이라면 HSD17B13에는 천연물 라벨이 아예 없다는 뜻이고,
     그 경우 시험셋을 '대리 타깃(패밀리)'으로 만들 수밖에 없다.

대조 DB: COCONUT(73.9만) · NPASS(9.6만) · FooDB
매칭은 두 단계로 한다.
  - 완전 InChIKey 일치 (입체화학까지 동일)
  - 첫 블록(14자) 일치 (골격 동일, 입체·염 차이 허용) ← 천연물은 입체 표기가
    출처마다 달라서 완전 일치만 보면 놓친다

출력:
  data/interim/261124_np_overlap_audit.csv
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import glob
import re
import numpy as np
import pandas as pd
from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

MERGED = "data/interim/261010_HSD17B13_IC50_merged.xlsx"
COCONUT = "data/raw/coconut_csv-09-2026.csv"
NPASS = "data/raw/npass_structures.tsv"
FOODB_DIR = "data/raw/foodb_2020_4_7_csv"
OUT = "data/interim/261124_np_overlap_audit.csv"
POTENT_NM = 1000.0


# ---- 1. 우리 데이터 ----------------------------------------------------------
df = pd.read_excel(MERGED, sheet_name="robust_dedup")
df = df.dropna(subset=["canonical_smiles", "ic50_median_nM"]).reset_index(drop=True)

keys, blocks, ok = [], [], []
for i, smi in enumerate(df["canonical_smiles"]):
    m = Chem.MolFromSmiles(str(smi))
    if m is None:
        keys.append(None); blocks.append(None); continue
    try:
        k = Chem.MolToInchiKey(m)
    except Exception:
        k = None
    keys.append(k)
    blocks.append(k.split("-")[0] if k else None)
df["inchikey"] = keys
df["ik_block"] = blocks
df = df.dropna(subset=["inchikey"]).reset_index(drop=True)
df["label"] = (df["ic50_median_nM"] <= POTENT_NM).astype(int)

print(f"우리 HSD17B13 실측 데이터 {len(df):,}개 (InChIKey 생성 성공)")
print(f"  active(<=1uM) {int(df.label.sum()):,} / inactive {int((df.label == 0).sum()):,}")


# ---- 2. 천연물 DB 적재 (InChIKey만) -------------------------------------------
def load_coconut():
    ks = set()
    for chunk in pd.read_csv(COCONUT, usecols=["standard_inchi_key"],
                             chunksize=200_000, low_memory=False):
        ks |= set(chunk["standard_inchi_key"].dropna().astype(str))
    return ks


def load_npass():
    d = pd.read_csv(NPASS, sep="\t", usecols=["InChIKey"], low_memory=False)
    return set(d["InChIKey"].dropna().astype(str))


IK_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


def find_inchikey_column(path, probe=200):
    """헤더 이름이 아니라 '값의 생김새'로 InChIKey 컬럼을 찾는다.

    FooDB 2020 CSV는 헤더와 데이터가 한 칸씩 어긋나 있다 — 실제 InChIKey는
    'moldb_smiles'라는 이름의 컬럼에 들어 있고, 'moldb_inchikey'에는 InChI
    문자열이 들어 있다. 이름을 믿으면 조용히 빈손이 된다.
    """
    head = pd.read_csv(path, nrows=probe, low_memory=False, on_bad_lines="skip")
    best, score = None, 0.0
    for c in head.columns:
        vals = head[c].dropna().astype(str)
        if not len(vals):
            continue
        hit = vals.str.match(IK_RE).mean()
        if hit > score:
            best, score = c, hit
    return (best, score) if score >= 0.5 else (None, score)


def load_foodb():
    ks = set()
    for p in glob.glob(os.path.join(FOODB_DIR, "**", "*ompound*.csv"), recursive=True):
        try:
            col, score = find_inchikey_column(p)
        except Exception:
            continue
        if not col:
            continue
        print(f"    {os.path.basename(p)}: InChIKey 컬럼 = '{col}' (일치율 {score:.0%})")
        for chunk in pd.read_csv(p, usecols=[col], chunksize=100_000,
                                 low_memory=False, on_bad_lines="skip"):
            ks |= {v for v in chunk[col].dropna().astype(str) if IK_RE.match(v)}
    return ks


print("\n천연물 DB 적재 중...")
DBS = {}
for name, fn in [("COCONUT", load_coconut), ("NPASS", load_npass), ("FooDB", load_foodb)]:
    try:
        s = fn()
        s = {k for k in s if k and k != "nan"}
        DBS[name] = s
        print(f"  {name:9s} {len(s):>8,}개")
    except Exception as e:
        print(f"  {name:9s} 적재 실패: {e}")
        DBS[name] = set()

ALL = set().union(*DBS.values())
ALL_BLOCK = {k.split("-")[0] for k in ALL if isinstance(k, str) and "-" in k}
print(f"  {'합집합':9s} {len(ALL):>8,}개  (골격 블록 {len(ALL_BLOCK):,}종)")


# ---- 3. 대조 -----------------------------------------------------------------
print("\n" + "=" * 78)
print("[결과] 우리 HSD17B13 화합물 중 천연물인 것")
print("=" * 78)
rows = []
for name, s in list(DBS.items()) + [("전체 합집합", ALL)]:
    blk = {k.split("-")[0] for k in s if isinstance(k, str) and "-" in k}
    exact = df["inchikey"].isin(s)
    loose = df["ik_block"].isin(blk)
    rows.append({"DB": name, "완전일치": int(exact.sum()), "골격일치": int(loose.sum()),
                 "골격일치_active": int((loose & (df.label == 1)).sum()),
                 "골격일치_inactive": int((loose & (df.label == 0)).sum())})
    print(f"  {name:12s} 완전일치 {int(exact.sum()):>4}   "
          f"골격일치 {int(loose.sum()):>4}  "
          f"(active {int((loose & (df.label == 1)).sum())} / "
          f"inactive {int((loose & (df.label == 0)).sum())})")

audit = pd.DataFrame(rows)
os.makedirs("data/interim", exist_ok=True)
audit.to_csv(OUT, index=False, encoding="utf-8-sig")

hit = df[df["ik_block"].isin(ALL_BLOCK)]
if len(hit):
    print("\n[일치한 화합물 목록]")
    cols = [c for c in ["compound_id", "canonical_smiles", "ic50_median_nM",
                        "pIC50_median", "label", "sources"] if c in hit.columns]
    print(hit[cols].head(40).to_string(index=False))
    hit.to_csv("data/interim/261124_np_in_training.csv", index=False, encoding="utf-8-sig")
    print(f"\n→ data/interim/261124_np_in_training.csv 에 저장 "
          f"({len(hit)}개). 이들은 학습에서 빼고 시험셋으로 돌려야 한다.")
else:
    print("\n[결론] 우리 HSD17B13 실측 데이터에 천연물은 0개다.")
    print("  → HSD17B13 자체로는 '진짜 외부 천연물 시험셋'을 만들 수 없다.")
    print("  → 패밀리 대리 타깃(HSD17B1/2/3, AKR1C3 등)으로 낙폭을 추정해야 한다.")

print(f"\n저장 → {OUT}")
