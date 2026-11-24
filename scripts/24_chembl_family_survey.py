# -*- coding: utf-8 -*-
"""HSD17B 패밀리 + 인접 SDR/AKR 효소의 ChEMBL 활성 데이터량을 조사한다.

목적 — Cockroft 2019(STarFish)식 '멀티라벨 스태킹'을 우리 과제에 적용할 수 있는지
판단할 근거를 만든다. 스태킹이 논문처럼 작동하려면 level-1 분류기가 여러 타깃의
예측 확률을 동시에 받아야 하는데, 그러려면 타깃마다 학습 가능한 분량이 있어야 한다.

판단 기준(논문의 가지치기 규칙을 그대로 가져옴):
  - 타깃당 화합물 10개 이상  → 라벨로 쓸 수 있음
  - 타깃당 화합물 100개 상한 → 불균형 억제(여기선 조사만, 샘플링은 다음 단계)

덤으로 얻는 것 — 선택성(selectivity) 예측.
HSD17B13 억제제가 HSD17B1(에스트라디올 대사)에도 붙으면 호르몬 부작용 위험이
있는데, 지금 단일 타깃 모델로는 볼 방법이 없다. 멀티라벨로 가면 같이 나온다.

출력:
  data/interim/261124_hsd17b_family_survey.csv   타깃별 데이터량 요약
  data/processed/261124_sdr_multilabel_long.csv  화합물-타깃 long 테이블(다음 단계 입력)
"""

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import os
import time
import json
import urllib.parse
import pandas as pd
import requests

BASE = "https://www.ebi.ac.uk/chembl/api/data"
# 외부 API에는 개인정보를 보내지 않는다. 일반적인 클라이언트 이름만 사용.
HEADERS = {"User-Agent": "bioai-research-script/1.0", "Accept": "application/json"}
TIMEOUT = 60
PAUSE = 0.34          # EBI 권장 속도 준수

OUT_SURVEY = "data/interim/261124_hsd17b_family_survey.csv"
OUT_LONG = "data/processed/261124_sdr_multilabel_long.csv"

# 조사 대상 — HSD17B 패밀리 전체 + 이미 모아둔 인접 SDR/AKR
#   HSD17B5 = AKR1C3 (별칭), HSD17B9 는 사람에서 결번이라 제외
GENES = [
    "HSD17B1", "HSD17B2", "HSD17B3", "HSD17B4", "HSD17B6", "HSD17B7",
    "HSD17B8", "HSD17B10", "HSD17B11", "HSD17B12", "HSD17B13", "HSD17B14",
    "AKR1C3", "AKR1B1", "HSD11B1", "HSD11B2", "CBR1", "DHRS9",
]

ACT_TYPES = ["IC50", "Ki", "Kd", "EC50"]
POTENT_NM = 1000.0     # 논문과 동일한 활성 기준 1 µM


# ---- HTTP 도우미 (재시도 포함) ----------------------------------------------
def get(path, params, tries=4):
    """ChEMBL REST GET. 실패하면 점점 더 기다렸다가 재시도."""
    url = f"{BASE}/{path}"
    for k in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            # 429(과속)·5xx는 재시도 대상
            if r.status_code not in (429, 500, 502, 503, 504):
                print(f"    HTTP {r.status_code} — {url}")
                return None
        except requests.RequestException as e:
            if k == tries - 1:
                print(f"    네트워크 실패: {e}")
                return None
        time.sleep(1.5 * (k + 1))
    return None


# ---- 1단계: 유전자 이름 → 사람 단일단백질 타깃 ChEMBL ID ---------------------
def find_target(gene):
    """유전자 심볼로 사람 SINGLE PROTEIN 타깃 하나를 찾는다.

    UniProt ID를 코드에 박아 넣지 않는다 — 틀리면 조용히 엉뚱한 단백질을
    조사하게 되므로, ChEMBL이 직접 해석하게 한다.
    """
    js = get("target/search", {"q": gene, "format": "json", "limit": 25})
    if not js:
        return None
    cands = []
    for t in js.get("targets", []):
        if t.get("organism") != "Homo sapiens":
            continue
        if t.get("target_type") != "SINGLE PROTEIN":
            continue
        # 유전자 심볼이 동의어에 정확히 들어 있는지 확인(부분일치 오인 방지)
        syns = {c.get("component_synonym", "").upper()
                for comp in t.get("target_components", [])
                for c in comp.get("target_component_synonyms", [])}
        exact = gene.upper() in syns
        cands.append((exact, t.get("target_chembl_id"), t.get("pref_name")))
    if not cands:
        return None
    cands.sort(key=lambda x: not x[0])      # 정확일치 우선
    return cands[0][1], cands[0][2], cands[0][0]


# ---- 2단계: 타깃의 활성 레코드 전부 끌어오기 --------------------------------
def fetch_activities(target_id):
    """결합(assay_type=B) 활성 레코드를 페이지 단위로 전부 받는다."""
    rows, offset, limit = [], 0, 1000
    while True:
        params = {
            "target_chembl_id": target_id,
            "standard_type__in": ",".join(ACT_TYPES),
            "assay_type": "B",
            "standard_units": "nM",
            "standard_value__isnull": "false",
            "limit": limit, "offset": offset, "format": "json",
            "only": ("molecule_chembl_id,canonical_smiles,standard_type,"
                     "standard_value,standard_relation,pchembl_value"),
        }
        js = get("activity", params)
        if not js:
            break
        page = js.get("activities", [])
        rows.extend(page)
        total = js.get("page_meta", {}).get("total_count", 0)
        offset += limit
        if offset >= total or not page:
            break
        time.sleep(PAUSE)
    return rows


# ---- 3단계: 타깃 하나 조사 --------------------------------------------------
def survey_gene(gene):
    hit = find_target(gene)
    if hit is None:
        print(f"  {gene:10s} 타깃을 찾지 못함")
        return None, []
    tid, pref, exact = hit
    acts = fetch_activities(tid)
    if not acts:
        print(f"  {gene:10s} {tid:14s} 활성 레코드 0건")
        return {"gene": gene, "chembl_id": tid, "pref_name": pref,
                "exact_match": exact, "n_records": 0, "n_compounds": 0,
                "n_potent_records": 0, "n_potent_compounds": 0}, []

    df = pd.DataFrame(acts)
    df["standard_value"] = pd.to_numeric(df["standard_value"], errors="coerce")
    df = df.dropna(subset=["standard_value", "canonical_smiles"])
    # '=' 관계만 — '>' 는 비활성 상한이라 활성 근거로 못 씀
    eq = df[df["standard_relation"].fillna("=") == "="]
    potent = eq[eq["standard_value"] <= POTENT_NM]

    rec = {
        "gene": gene, "chembl_id": tid, "pref_name": pref, "exact_match": exact,
        "n_records": len(df),
        "n_compounds": df["molecule_chembl_id"].nunique(),
        "n_potent_records": len(potent),
        "n_potent_compounds": potent["molecule_chembl_id"].nunique(),
    }
    print(f"  {gene:10s} {tid:14s} 레코드 {rec['n_records']:>6,}  "
          f"화합물 {rec['n_compounds']:>5,}  "
          f"≤1µM 화합물 {rec['n_potent_compounds']:>5,}")

    long = potent[["molecule_chembl_id", "canonical_smiles", "standard_value"]].copy()
    long["gene"] = gene
    long["target_chembl_id"] = tid
    return rec, long.to_dict("records")


# ---- 실행 -------------------------------------------------------------------
print("ChEMBL HSD17B 패밀리 + 인접 SDR 조사")
print(f"기준: assay_type=B, {'/'.join(ACT_TYPES)}, nM, relation '=', 활성 ≤ {POTENT_NM:.0f} nM")
print("=" * 86)

records, long_rows = [], []
for g in GENES:
    rec, lr = survey_gene(g)
    if rec:
        records.append(rec)
    long_rows.extend(lr)
    time.sleep(PAUSE)

survey = pd.DataFrame(records)
os.makedirs("data/interim", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)
survey.to_csv(OUT_SURVEY, index=False, encoding="utf-8-sig")

long_df = pd.DataFrame(long_rows)
if len(long_df):
    # 같은 화합물-타깃이 여러 논문에 나오면 가장 강한 값만 남긴다
    long_df = (long_df.sort_values("standard_value")
                      .drop_duplicates(["molecule_chembl_id", "gene"], keep="first")
                      .reset_index(drop=True))
    long_df.to_csv(OUT_LONG, index=False, encoding="utf-8-sig")

# ---- 요약: 멀티라벨로 갈 수 있는가 ------------------------------------------
print("=" * 86)
print("\n[타깃별 조사 결과]")
show = survey.sort_values("n_potent_compounds", ascending=False)
print(show[["gene", "chembl_id", "n_compounds", "n_potent_compounds"]].to_string(index=False))

if len(long_df):
    per_target = long_df.groupby("gene")["molecule_chembl_id"].nunique()
    usable = per_target[per_target >= 10]
    per_cmpd = long_df.groupby("molecule_chembl_id")["gene"].nunique()

    print("\n[논문 기준(타깃당 화합물 ≥10)을 통과하는 타깃]")
    print(f"  통과 {len(usable)} / 조사 {len(per_target)}개")
    print(f"  → level-1 분류기가 받게 될 확률 개수: 모델 1개당 {len(usable)}개 "
          f"(지금 단일 타깃이면 1개)")

    print("\n[화합물당 라벨 수]")
    print(f"  고유 화합물 {long_df['molecule_chembl_id'].nunique():,}개")
    print(f"  화합물당 평균 타깃 수 {per_cmpd.mean():.2f}")
    print(f"  2개 이상 타깃에서 시험된 화합물 {(per_cmpd >= 2).sum():,}개 "
          f"({(per_cmpd >= 2).mean() * 100:.1f}%)")

    print("\n[HSD17B13과 함께 시험된 화합물 수 — 선택성 학습 가능성]")
    b13 = set(long_df.loc[long_df.gene == "HSD17B13", "molecule_chembl_id"])
    for g in sorted(per_target.index):
        if g == "HSD17B13":
            continue
        ov = len(b13 & set(long_df.loc[long_df.gene == g, "molecule_chembl_id"]))
        if ov:
            print(f"  HSD17B13 ∩ {g:10s} {ov:>5,}개")

print(f"\n저장 → {OUT_SURVEY}")
print(f"저장 → {OUT_LONG}")
