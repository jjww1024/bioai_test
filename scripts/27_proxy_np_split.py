# -*- coding: utf-8 -*-
"""외부 천연물 시험셋 설계 1단계 — 대리 타깃의 합성물/천연물 분리.

왜 대리 타깃인가 —
HSD17B13에는 천연물 활성 데이터가 없다(26번에서 확인). 그러면 "합성물로 배운
모델이 천연물로 넘어갈 때 얼마나 떨어지는가"를 HSD17B13 자체로는 잴 수 없다.
대신 합성물과 천연물 데이터가 둘 다 있는 가까운 효소들에서 그 낙폭을 재고,
그 값을 HSD17B13 모델의 기대 낙폭으로 삼는다. Cockroft가 1,907개 타깃에서
한 일을, 우리는 몇 개 타깃에서 하는 셈이다.

대리 타깃 선정 —
  1순위 17베타-HSD 계열: HSD17B1, HSD17B2, HSD17B3, AKR1C3(=HSD17B5)
       HSD17B13과 같은 기능군(스테로이드 17베타 위치 산화환원)
  2순위 인접 SDR/AKR : HSD11B1, AKR1B1
       기능은 다르지만 보조인자(NAD(P)H) 결합 양식과 기질 크기가 비슷

이 스크립트가 하는 일:
  - 타깃별 ChEMBL 활성 기록을 '전부' 받는다 (1 µM 초과 = 비활성도 필요하므로)
  - 화합물 단위로 중앙값 집계
  - COCONUT/NPASS/FooDB InChIKey 골격 블록으로 합성물/천연물 분리
  - 각 더미의 active/inactive 수를 세어 '어떤 평가 프로토콜이 가능한지' 판정

판정 기준:
  프로토콜 A (라벨 대조)  천연물 쪽에 active >= 15 이고 inactive >= 15
      → 실측 라벨끼리 AUROC 비교. 가장 깨끗하다.
  프로토콜 B (스파이크 농축)  천연물 active는 있는데 inactive가 모자람
      → 천연물 active를 COCONUT 배경에 섞고 EF/BEDROC으로 농축도를 본다.
        배경은 '모르니까 비활성'으로 가정하는 것이라 논문과 같은 한계를 진다.

출력:
  data/interim/261124_np_keyblocks.txt          천연물 InChIKey 골격 블록 캐시
  data/processed/261124_proxy_targets.csv       타깃별 화합물 + 합성/천연 구분
  data/reports/261124_proxy_feasibility.csv     프로토콜 판정표
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import glob
import time
import numpy as np
import pandas as pd
import requests
from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

BASE = "https://www.ebi.ac.uk/chembl/api/data"
HEADERS = {"User-Agent": "bioai-research-script/1.0", "Accept": "application/json"}
PAUSE = 0.34
POTENT_NM = 1000.0

COCONUT = "data/raw/coconut_csv-09-2026.csv"
NPASS = "data/raw/npass_structures.tsv"
FOODB_DIR = "data/raw/foodb_2020_4_7_csv"
KEYCACHE = "data/interim/261124_np_keyblocks.txt"
OUT_COMPOUNDS = "data/processed/261124_proxy_targets.csv"
OUT_FEAS = "data/reports/261124_proxy_feasibility.csv"

PROXIES = {
    "HSD17B1": ("CHEMBL3181", "17b-HSD 1순위"),
    "HSD17B2": ("CHEMBL2789", "17b-HSD 1순위"),
    "HSD17B3": ("CHEMBL4234", "17b-HSD 1순위"),
    "AKR1C3": ("CHEMBL4681", "17b-HSD 1순위 (=HSD17B5)"),
    "HSD11B1": ("CHEMBL4235", "인접 SDR 2순위"),
    "AKR1B1": ("CHEMBL1900", "인접 AKR 2순위"),
}


# ---- 천연물 키 캐시 -----------------------------------------------------------
def build_np_keyblocks():
    """세 DB의 InChIKey 첫 블록(14자) 합집합. 한 번 만들어 파일로 캐시한다."""
    if os.path.exists(KEYCACHE):
        with open(KEYCACHE, encoding="utf-8") as f:
            blocks = {ln.strip() for ln in f if ln.strip()}
        print(f"천연물 키 캐시 적재: {len(blocks):,}종")
        return blocks

    print("천연물 키 캐시 생성 중 (COCONUT 668MB — 1~2분)")
    keys = set()
    for chunk in pd.read_csv(COCONUT, usecols=["standard_inchi_key"],
                             chunksize=200_000, low_memory=False):
        keys |= set(chunk["standard_inchi_key"].dropna().astype(str))
    print(f"  COCONUT {len(keys):,}")
    d = pd.read_csv(NPASS, sep="\t", usecols=["InChIKey"], low_memory=False)
    keys |= set(d["InChIKey"].dropna().astype(str))
    # FooDB 2020 CSV는 헤더와 데이터가 한 칸 어긋나 있다(실제 InChIKey는
    # 'moldb_smiles' 컬럼에 있음). 이름이 아니라 값의 생김새로 찾는다.
    import re as _re
    IK = _re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
    for p in glob.glob(os.path.join(FOODB_DIR, "**", "*ompound*.csv"), recursive=True):
        try:
            head = pd.read_csv(p, nrows=200, low_memory=False, on_bad_lines="skip")
        except Exception:
            continue
        col, score = None, 0.0
        for c in head.columns:
            v = head[c].dropna().astype(str)
            if len(v) and v.str.match(IK).mean() > score:
                col, score = c, v.str.match(IK).mean()
        if not col or score < 0.5:
            continue
        print(f"  FooDB InChIKey 컬럼 = '{col}' (일치율 {score:.0%})")
        n0 = len(keys)
        for chunk in pd.read_csv(p, usecols=[col], chunksize=100_000,
                                 low_memory=False, on_bad_lines="skip"):
            keys |= {v for v in chunk[col].dropna().astype(str) if IK.match(v)}
        print(f"  FooDB {len(keys) - n0:,}개 추가")
    blocks = {k.split("-")[0] for k in keys if isinstance(k, str) and "-" in k}
    os.makedirs(os.path.dirname(KEYCACHE), exist_ok=True)
    with open(KEYCACHE, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(blocks)))
    print(f"  합집합 골격 블록 {len(blocks):,}종 → {KEYCACHE}")
    return blocks


# ---- ChEMBL 전체 활성 기록 ----------------------------------------------------
def fetch_all(target_id):
    """활성도 상한 없이 전부 받는다 — 비활성(>1uM)이 있어야 라벨 대조가 된다."""
    rows, off, limit = [], 0, 1000
    while True:
        p = {"target_chembl_id": target_id,
             "standard_type__in": "IC50,Ki,Kd,EC50",
             "assay_type": "B", "standard_units": "nM",
             "standard_value__isnull": "false",
             "limit": limit, "offset": off, "format": "json",
             "only": ("molecule_chembl_id,canonical_smiles,standard_value,"
                      "standard_relation,standard_type")}
        for attempt in range(4):
            try:
                r = requests.get(f"{BASE}/activity", params=p, headers=HEADERS, timeout=60)
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(1.5 * (attempt + 1))
        else:
            break
        if r.status_code != 200:
            break
        j = r.json()
        rows.extend(j.get("activities", []))
        tot = j.get("page_meta", {}).get("total_count", 0)
        off += limit
        if off >= tot:
            break
        time.sleep(PAUSE)
    return rows


np_blocks = build_np_keyblocks()

print("\n" + "=" * 92)
print("대리 타깃별 합성물/천연물 분리")
print("=" * 92)

all_rows, feas = [], []
for gene, (tid, tier) in PROXIES.items():
    acts = fetch_all(tid)
    if not acts:
        print(f"  {gene:9s} 기록 없음")
        continue
    d = pd.DataFrame(acts)
    d["standard_value"] = pd.to_numeric(d["standard_value"], errors="coerce")
    d = d.dropna(subset=["standard_value", "canonical_smiles"])
    d = d[d["standard_relation"].fillna("=") == "="]
    # 화합물 단위 중앙값
    comp = (d.groupby("molecule_chembl_id")
              .agg(canonical_smiles=("canonical_smiles", "first"),
                   value_nM=("standard_value", "median"),
                   n_records=("standard_value", "size"))
              .reset_index())
    # InChIKey 골격 블록
    blks = []
    for smi in comp["canonical_smiles"]:
        m = Chem.MolFromSmiles(str(smi))
        try:
            blks.append(Chem.MolToInchiKey(m).split("-")[0] if m else None)
        except Exception:
            blks.append(None)
    comp["ik_block"] = blks
    comp = comp.dropna(subset=["ik_block"])
    comp["is_np"] = comp["ik_block"].isin(np_blocks)
    comp["label"] = (comp["value_nM"] <= POTENT_NM).astype(int)
    comp["gene"] = gene
    comp["tier"] = tier
    all_rows.append(comp)

    syn, npd = comp[~comp.is_np], comp[comp.is_np]
    na, ni = int(npd.label.sum()), int((npd.label == 0).sum())
    sa, si = int(syn.label.sum()), int((syn.label == 0).sum())
    proto = "A (라벨 대조)" if (na >= 15 and ni >= 15) else (
            "B (스파이크 농축)" if na >= 10 else "불가 (천연물 active 부족)")
    feas.append({"gene": gene, "tier": tier,
                 "합성물_active": sa, "합성물_inactive": si,
                 "천연물_active": na, "천연물_inactive": ni,
                 "천연물비율%": round(len(npd) / len(comp) * 100, 1),
                 "프로토콜": proto})
    print(f"  {gene:9s} 합성물 {len(syn):>5,} (act {sa:>4}/inact {si:>4})   "
          f"천연물 {len(npd):>4,} (act {na:>3}/inact {ni:>3})  "
          f"{len(npd) / len(comp) * 100:>4.1f}%   → {proto}")
    time.sleep(PAUSE)

comps = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
os.makedirs("data/processed", exist_ok=True)
os.makedirs("data/reports", exist_ok=True)
if len(comps):
    comps.to_csv(OUT_COMPOUNDS, index=False, encoding="utf-8-sig")
feasdf = pd.DataFrame(feas)
feasdf.to_csv(OUT_FEAS, index=False, encoding="utf-8-sig")

print("\n" + "=" * 92)
print("[판정]")
print("=" * 92)
print(feasdf.to_string(index=False))
a = feasdf[feasdf["프로토콜"].str.startswith("A")]
b = feasdf[feasdf["프로토콜"].str.startswith("B")]
print(f"\n  프로토콜 A 가능 타깃 {len(a)}개"
      + (f" — {', '.join(a.gene)}" if len(a) else ""))
print(f"  프로토콜 B 가능 타깃 {len(b)}개"
      + (f" — {', '.join(b.gene)}" if len(b) else ""))
print(f"\n저장 → {OUT_COMPOUNDS}")
print(f"저장 → {OUT_FEAS}")
