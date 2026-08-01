"""
bioai_test.py
=============
MASLD(대사이상 관련 지방간질환) 개선을 위한 바이오마커 타겟 소재 발굴 AI 스캐폴드.
현재 기본 타겟: HSD17B13 (17-beta-hydroxysteroid dehydrogenase 13)

목표
----
1) 특정 바이오마커(타겟)에 대해 활성이 측정된 화합물 데이터를 ChEMBL에서 수집
2) RDKit Morgan(ECFP) fingerprint로 분자를 벡터화
3) 머신러닝 모델(RandomForest)로 "이 물질이 타겟을 억제/활성화하는가"를 예측
4) 천연물 DB(FooDB / NPASS / COCONUT)를 스크리닝해 활성 후보 발굴
5) 발굴된 후보들끼리 fingerprint 기반 Tanimoto 유사도 계산

이 파일은 '시작점'입니다. 각 단계는 함수로 분리되어 있으니
필요에 따라 타겟/모델/임계값을 바꿔가며 실험하세요.

설치 (프로젝트 폴더에서)
------------------------
    python -m venv venv
    venv\\Scripts\\activate        # Windows PowerShell: venv\\Scripts\\Activate.ps1
    pip install -r requirements.txt

실행
----
    python bioai_test.py                  # 전체 데모 파이프라인 실행
    python bioai_test.py --target THRB
"""

from __future__ import annotations

import argparse
import os
import pickle
from dataclasses import dataclass

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# 0. MASLD 관련 바이오마커(타겟) 카탈로그
# ---------------------------------------------------------------------------
# ChEMBL target ID를 키로 관리합니다. 새 타겟은 https://www.ebi.ac.uk/chembl/ 에서
# 검색해 target_chembl_id를 찾아 추가하면 됩니다.
#
#  - THRB   : Thyroid hormone receptor beta — resmetirom(Rezdiffra)의 타겟, 유일한 FDA 승인 MASH 치료제
#  - FASN   : Fatty acid synthase — de novo lipogenesis 핵심 효소
#  - ACACA  : Acetyl-CoA carboxylase 1 — 지방산 합성 율속 효소
#  - SCD1   : Stearoyl-CoA desaturase 1
#  - DGAT2  : Diacylglycerol O-acyltransferase 2 — 중성지방 합성
#  - KHK    : Ketohexokinase — 과당 대사, MASLD 유발과 연관
#  - PPARA  : PPAR-alpha — 지방산 산화
TARGETS: dict[str, dict] = {
    # HSD17B13: 17-beta-hydroxysteroid dehydrogenase 13.
    #   GWAS에서 loss-of-function 변이가 MASLD/NASH에 보호적 → 저해제 개발 대상.
    #   대표 저해제: BI-3231. 비교적 최신 타겟이라 ChEMBL 데이터가 적을 수 있으니
    #   데이터가 부족하면 PubChem BioAssay / 논문 SI로 보강하세요.
    #   chembl_id는 UniProt Q7Z5P4(human)의 ChEMBL 상호참조로 확인함 (2026-08-01).
    #   geneid: NCBI Gene ID (PubChem BioAssay 보강용).
    "HSD17B13": {"chembl_id": "CHEMBL5305042", "geneid": 345275,
                 "name": "17-beta-hydroxysteroid dehydrogenase 13"},
    "THRB":  {"chembl_id": "CHEMBL1947",  "name": "Thyroid hormone receptor beta"},
    "FASN":  {"chembl_id": "CHEMBL4158",  "name": "Fatty acid synthase"},
    "ACACA": {"chembl_id": "CHEMBL3616",  "name": "Acetyl-CoA carboxylase 1"},
    "SCD1":  {"chembl_id": "CHEMBL5555",  "name": "Stearoyl-CoA desaturase"},
    "DGAT2": {"chembl_id": "CHEMBL5504",  "name": "Diacylglycerol O-acyltransferase 2"},
    "KHK":   {"chembl_id": "CHEMBL4979",  "name": "Ketohexokinase"},
    "PPARA": {"chembl_id": "CHEMBL239",   "name": "PPAR-alpha"},
}

# NOTE: 위 chembl_id 중 일부는 예시 값입니다. 실제 사용 전에 ChEMBL에서
#       타겟명을 검색해 정확한 target_chembl_id로 교체하세요. (fetch_bioactivity가
#       데이터를 못 가져오면 ID가 틀렸을 가능성이 큽니다.)


@dataclass
class Config:
    target: str = "HSD17B13"     # TARGETS의 키
    fp_radius: int = 2            # Morgan fingerprint 반경 (ECFP4 = radius 2)
    fp_bits: int = 2048          # fingerprint 비트 수
    active_threshold: float = 6.0  # pIC50 >= 6.0 (IC50 <= 1uM) 이면 'active'
    test_size: float = 0.2
    random_state: int = 42
    cache_dir: str = "bioai_cache"
    augment_pubchem: bool = False  # PubChem BioAssay로 학습셋 보강 여부
    # ChEMBL 웹에서 수동 다운로드한 activity CSV 경로 (있으면 API 대신 이 파일 사용)
    chembl_csv_path: str = "data/chembl_activities.csv"
    # 스크리닝 라이브러리 파일 경로 (없으면 DEMO_CANDIDATES로 폴백)
    foodb_path: str = "data/foodb_compounds.csv"
    npass_path: str = "data/npass_structures.tsv"
    coconut_path: str = "data/coconut.csv"


# ---------------------------------------------------------------------------
# 1. 데이터 수집 — ChEMBL에서 바이오활성 다운로드
# ---------------------------------------------------------------------------
def fetch_bioactivity(cfg: Config) -> pd.DataFrame:
    """타겟에 대해 IC50/EC50 등이 측정된 화합물을 ChEMBL에서 가져온다."""
    os.makedirs(cfg.cache_dir, exist_ok=True)
    cache = os.path.join(cfg.cache_dir, f"{cfg.target}_bioactivity.csv")
    if os.path.exists(cache):
        print(f"[data] 캐시 사용: {cache}")
        return pd.read_csv(cache)

    from chembl_webresource_client.new_client import new_client

    chembl_id = TARGETS[cfg.target]["chembl_id"]
    print(f"[data] ChEMBL 다운로드 중... target={cfg.target} ({chembl_id})")

    activity = new_client.activity
    res = activity.filter(
        target_chembl_id=chembl_id,
        standard_type="IC50",          # 필요시 "EC50", "Ki" 등으로 변경
    ).only(
        ["molecule_chembl_id", "canonical_smiles",
         "standard_value", "standard_units", "standard_type"]
    )

    df = pd.DataFrame(res)
    if df.empty:
        raise RuntimeError(
            f"'{cfg.target}'({chembl_id})에 대한 데이터가 없습니다. "
            "target chembl_id가 올바른지 확인하세요."
        )

    # 정제: SMILES/값 결측 제거, nM 단위만 사용
    df = df.dropna(subset=["canonical_smiles", "standard_value"])
    df = df[df["standard_units"] == "nM"].copy()
    df["standard_value"] = pd.to_numeric(df["standard_value"], errors="coerce")
    df = df.dropna(subset=["standard_value"])
    df = df[df["standard_value"] > 0]

    # 중복 분자는 중앙값으로 집계
    df = (df.groupby(["molecule_chembl_id", "canonical_smiles"], as_index=False)
            ["standard_value"].median())

    # pIC50 = -log10(IC50 in M)
    df["pIC50"] = -np.log10(df["standard_value"] * 1e-9)
    df["active"] = (df["pIC50"] >= cfg.active_threshold).astype(int)

    df.to_csv(cache, index=False)
    print(f"[data] {len(df)}개 화합물 저장 → {cache} "
          f"(active={df['active'].sum()}, inactive={(df['active']==0).sum()})")
    return df


# ---------------------------------------------------------------------------
# 1.5 학습 데이터 보강 — PubChem BioAssay (ChEMBL이 부족/장애일 때)
# ---------------------------------------------------------------------------
# PubChem은 assay 결과를 Active/Inactive 범주로 제공하므로 active 라벨로 직접 사용.
# NCBI GeneID로 타겟에 연결된 assay(AID)를 찾고, 각 AID의 active/inactive 화합물을
# 모아 SMILES까지 받아온다. ChEMBL(IC50 기반)과 스키마를 맞춰 concat 가능.
def fetch_pubchem_bioassay(cfg: "Config", geneid: int,
                           max_aids: int = 60, max_cids: int = 6000,
                           pause: float = 0.25) -> pd.DataFrame:
    """반환: DataFrame[canonical_smiles, active] (active: 1/0)."""
    import time
    import requests

    os.makedirs(cfg.cache_dir, exist_ok=True)
    cache = os.path.join(cfg.cache_dir, f"{cfg.target}_pubchem.csv")
    if os.path.exists(cache):
        print(f"[pubchem] 캐시 사용: {cache}")
        return pd.read_csv(cache)

    base = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

    def _get(url, **params):
        for _ in range(3):
            try:
                r = requests.get(url, params=params, timeout=60)
            except requests.RequestException:
                time.sleep(1.0); continue
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:   # 해당 유형 결과 없음 — 정상
                return None
            time.sleep(1.0)
        return None

    # 1) geneid → AID 목록
    j = _get(f"{base}/assay/target/geneid/{geneid}/aids/JSON")
    aids = (j or {}).get("IdentifierList", {}).get("AID", [])[:max_aids]
    print(f"[pubchem] geneid {geneid}: assay {len(aids)}개")

    active_cids, inactive_cids = set(), set()
    for aid in aids:
        for label, bucket in (("active", active_cids), ("inactive", inactive_cids)):
            ja = _get(f"{base}/assay/aid/{aid}/cids/JSON", cids_type=label)
            for info in (ja or {}).get("InformationList", {}).get("Information", []):
                bucket.update(info.get("CID", []))
            time.sleep(pause)
    inactive_cids -= active_cids   # active 우선
    print(f"[pubchem] active CID {len(active_cids)}, inactive CID {len(inactive_cids)}")

    # 2) CID → SMILES (배치 100개씩). PubChem 속성명 버전차 대비해 폴백.
    def cids_to_rows(cids, label):
        cids = list(cids)[:max_cids]
        rows = []
        for i in range(0, len(cids), 100):
            chunk = ",".join(map(str, cids[i:i + 100]))
            jp = None
            for prop in ("SMILES", "CanonicalSMILES"):
                jp = _get(f"{base}/compound/cid/{chunk}/property/{prop}/JSON")
                if jp and jp.get("PropertyTable", {}).get("Properties"):
                    break
            for p in (jp or {}).get("PropertyTable", {}).get("Properties", []):
                smi = p.get("SMILES") or p.get("CanonicalSMILES")
                if smi:
                    rows.append({"canonical_smiles": smi, "active": label})
            time.sleep(pause)
        return rows

    rows = cids_to_rows(active_cids, 1) + cids_to_rows(inactive_cids, 0)
    df = pd.DataFrame(rows)
    if df.empty:
        print("[pubchem] 수집된 화합물이 없습니다.")
        return df
    df = df.drop_duplicates("canonical_smiles")
    df.to_csv(cache, index=False)
    print(f"[pubchem] {len(df)}개 화합물 저장 → {cache} "
          f"(active={int(df['active'].sum())})")
    return df


def load_chembl_csv(path: str, cfg: "Config") -> pd.DataFrame:
    """
    ChEMBL 웹사이트에서 수동으로 내려받은 activity CSV를 학습 스키마로 변환한다.
    (API가 장애일 때 유용. ChEMBL 웹 CSV는 보통 ';' 구분 — 구분자/컬럼 자동 판별.)

    active 판정: 'pChEMBL Value'가 있으면 그 값을, 없으면 'Standard Value'(nM)를
                 pIC50 = -log10(value*1e-9)로 환산해 active_threshold와 비교.
    반환: DataFrame[canonical_smiles, active]

    다운로드 방법:
      https://www.ebi.ac.uk/chembl/ → 타겟(HSD17B13, CHEMBL5305042) 검색 →
      Activities 탭 → CSV 내려받아 data/chembl_activities.csv 로 저장.
    """
    raw = pd.read_csv(path, sep=None, engine="python", on_bad_lines="skip")
    cols = {c.lower().strip(): c for c in raw.columns}

    def find(*keys):
        for k in keys:
            for lc, orig in cols.items():
                if k in lc:
                    return orig
        return None

    smiles_c = find("smiles")
    pchembl_c = find("pchembl")
    value_c = find("standard value", "standard_value")
    units_c = find("standard units", "standard_units")
    if smiles_c is None:
        raise ValueError(f"SMILES 컬럼을 찾지 못했습니다. 헤더: {list(raw.columns)}")

    df = raw.rename(columns={smiles_c: "canonical_smiles"})
    df = df.dropna(subset=["canonical_smiles"]).copy()

    pic50 = pd.to_numeric(df[pchembl_c], errors="coerce") if pchembl_c \
        else pd.Series(np.nan, index=df.index)
    if value_c:                                    # pChEMBL이 없는 행은 값으로 보완
        val = pd.to_numeric(df[value_c], errors="coerce")
        if units_c:                                # 단위가 있으면 nM만 사용
            val = val.where(df[units_c].astype(str).str.strip() == "nM")
        pic50 = pic50.fillna(-np.log10(val * 1e-9))

    df["pIC50"] = pic50
    df = df.dropna(subset=["pIC50"])
    df["active"] = (df["pIC50"] >= cfg.active_threshold).astype(int)
    df = df.drop_duplicates("canonical_smiles")
    print(f"[chembl-csv] {path}: {len(df)}개 "
          f"(active={int(df['active'].sum())}, inactive={int((df['active']==0).sum())})")
    return df[["canonical_smiles", "active"]]


def assemble_training_data(cfg: "Config") -> pd.DataFrame:
    """ChEMBL + (선택)PubChem을 합쳐 학습셋을 만든다. 스키마: canonical_smiles, active."""
    frames = []
    # ChEMBL: 수동 CSV가 있으면 우선 사용, 없으면 API 시도
    if cfg.chembl_csv_path and os.path.exists(cfg.chembl_csv_path):
        frames.append(load_chembl_csv(cfg.chembl_csv_path, cfg))
    else:
        try:
            chembl = fetch_bioactivity(cfg)
            frames.append(chembl[["canonical_smiles", "active"]])
        except Exception as e:
            msg = " ".join(str(e).split())[:200]   # 장문 HTML 에러 방지로 잘라냄
            print(f"[data] ChEMBL API 수집 실패 (건너뜀): {msg}")
            print(f"[data] 대안: ChEMBL 웹에서 CSV 받아 {cfg.chembl_csv_path} 에 두면 그걸 사용합니다.")

    if cfg.augment_pubchem:
        geneid = TARGETS[cfg.target].get("geneid")
        if geneid:
            pc = fetch_pubchem_bioassay(cfg, geneid)
            if not pc.empty:
                frames.append(pc[["canonical_smiles", "active"]])
        else:
            print(f"[data] {cfg.target}에 geneid가 없어 PubChem 보강 스킵")

    if not frames:
        raise RuntimeError(
            "학습 데이터를 하나도 확보하지 못했습니다. "
            "ChEMBL API 상태를 확인하거나 --augment-pubchem을 켜세요."
        )
    df = pd.concat(frames, ignore_index=True).drop_duplicates("canonical_smiles")
    df = df.reset_index(drop=True)
    print(f"[data] 통합 학습셋: {len(df)}개 "
          f"(active={int(df['active'].sum())}, inactive={int((df['active']==0).sum())})")
    return df


# ---------------------------------------------------------------------------
# 2. Featurization — SMILES → Morgan fingerprint
# ---------------------------------------------------------------------------
# RDKit 2026부터 GetMorganFingerprintAsBitVect는 deprecated → MorganGenerator 사용.
# 생성기는 (radius, bits)별로 한 번만 만들어 캐시 (대용량 DB 스크리닝 성능).
_MORGAN_GEN_CACHE: dict = {}


def _morgan_gen(cfg: Config):
    from rdkit.Chem import rdFingerprintGenerator
    key = (cfg.fp_radius, cfg.fp_bits)
    gen = _MORGAN_GEN_CACHE.get(key)
    if gen is None:
        gen = rdFingerprintGenerator.GetMorganGenerator(
            radius=cfg.fp_radius, fpSize=cfg.fp_bits)
        _MORGAN_GEN_CACHE[key] = gen
    return gen


def smiles_to_fp(smiles: str, cfg: Config):
    """단일 SMILES를 Morgan fingerprint(numpy array)로. 실패 시 None."""
    from rdkit import Chem

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return _morgan_gen(cfg).GetFingerprintAsNumPy(mol)


def build_feature_matrix(df: pd.DataFrame, cfg: Config):
    """DataFrame(canonical_smiles 열) → (X, valid_index)."""
    feats, keep = [], []
    for idx, smi in df["canonical_smiles"].items():
        arr = smiles_to_fp(smi, cfg)
        if arr is not None:
            feats.append(arr)
            keep.append(idx)
    X = np.vstack(feats)
    print(f"[feat] {X.shape[0]}개 분자 벡터화 완료 (dim={X.shape[1]})")
    return X, keep


# ---------------------------------------------------------------------------
# 3. 모델 학습
# ---------------------------------------------------------------------------
def train_model(df: pd.DataFrame, cfg: Config):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, roc_auc_score

    X, keep = build_feature_matrix(df, cfg)
    y = df.loc[keep, "active"].values

    if len(np.unique(y)) < 2:
        raise RuntimeError(
            "active/inactive 중 한 클래스만 존재합니다. "
            "active_threshold를 조정하거나 데이터를 더 모으세요."
        )

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=cfg.test_size,
        random_state=cfg.random_state, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=300, class_weight="balanced",
        random_state=cfg.random_state, n_jobs=-1
    )
    clf.fit(X_tr, y_tr)

    proba = clf.predict_proba(X_te)[:, 1]
    pred = (proba >= 0.5).astype(int)
    print("\n[model] 평가 결과")
    print(classification_report(y_te, pred, target_names=["inactive", "active"]))
    try:
        print(f"[model] ROC-AUC = {roc_auc_score(y_te, proba):.3f}")
    except ValueError:
        pass

    os.makedirs(cfg.cache_dir, exist_ok=True)
    model_path = os.path.join(cfg.cache_dir, f"{cfg.target}_rf.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(clf, f)
    print(f"[model] 저장 → {model_path}")
    return clf


# ---------------------------------------------------------------------------
# 4. 스크리닝 — 새 화합물/천연물 예측
# ---------------------------------------------------------------------------
def screen_candidates(clf, candidates: dict[str, str], cfg: Config) -> pd.DataFrame:
    """
    candidates: {이름: SMILES} 딕셔너리
    반환: 각 물질의 활성 확률(activity_prob) 내림차순 DataFrame
    """
    rows = []
    for name, smi in candidates.items():
        arr = smiles_to_fp(smi, cfg)
        if arr is None:
            continue   # SMILES 파싱 실패 항목은 조용히 스킵 (대용량 DB에서 로그 폭주 방지)
        prob = clf.predict_proba(arr.reshape(1, -1))[0, 1]
        rows.append({"name": name, "smiles": smi, "activity_prob": prob})
    out = pd.DataFrame(rows).sort_values("activity_prob", ascending=False)
    print(f"\n[screen] {len(out)}개 예측 완료. 상위 20개:")
    print(out.head(20).to_string(index=False))
    return out


# ---------------------------------------------------------------------------
# 5. Fingerprint 유사도 — 발굴된 후보들끼리 Tanimoto
# ---------------------------------------------------------------------------
def similarity_matrix(candidates: dict[str, str], cfg: Config) -> pd.DataFrame:
    """후보 물질 간 Tanimoto 유사도 행렬(대칭)."""
    from rdkit import Chem
    from rdkit import DataStructs

    gen = _morgan_gen(cfg)
    names, fps = [], []
    for name, smi in candidates.items():
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            continue
        fps.append(gen.GetFingerprint(mol))
        names.append(name)

    n = len(fps)
    mat = np.eye(n)
    for i in range(n):
        # BulkTanimotoSimilarity로 한 번에 계산
        sims = DataStructs.BulkTanimotoSimilarity(fps[i], fps)
        mat[i] = sims

    sim_df = pd.DataFrame(mat, index=names, columns=names)
    print("\n[sim] Tanimoto 유사도 행렬")
    print(sim_df.round(3).to_string())
    return sim_df


# ---------------------------------------------------------------------------
# 5.5 스크리닝 라이브러리 로딩 — 천연물 DB(FooDB / NPASS / COCONUT)를 RDKit으로 통합
# ---------------------------------------------------------------------------
# 핵심 개념: RDKit은 DB가 아니라 '읽는 도구'입니다. 어떤 DB든 SMILES 컬럼만 있으면
# 아래 로더로 읽어 하나의 후보 딕셔너리 {이름: SMILES}로 합칠 수 있습니다.
# 그 뒤 screen_candidates / similarity_matrix가 소스와 무관하게 동일하게 처리합니다.
#
# 다운로드:
#   FooDB   : https://foodb.ca/downloads             (Compounds CSV; SMILES = 'moldb_smiles')
#   NPASS   : https://bidd.group/NPASS/               (structure TSV; SMILES = 'canonical_smiles')
#   COCONUT : https://coconut.naturalproducts.net/download  (CSV; SMILES = 'canonical_smiles')

# 컬럼 자동 감지용 힌트 (우선순위 순). 대부분의 천연물 DB 덤프를 커버합니다.
_SMILES_HINTS = ("canonical_smiles", "smiles", "moldb_smiles",
                 "isomeric_smiles", "smile", "structure")
_NAME_HINTS = ("name", "pref_name", "compound_name", "identifier",
               "coconut_id", "np_id", "public_id", "cid", "id", "title")


def detect_columns(path: str, sep: str) -> tuple[str, str]:
    """파일 헤더에서 SMILES 컬럼과 이름/ID 컬럼을 자동으로 찾는다."""
    header = pd.read_csv(path, sep=sep, nrows=0).columns.tolist()
    lower = {c.lower(): c for c in header}

    smiles_col = next((lower[h] for h in _SMILES_HINTS if h in lower), None)
    if smiles_col is None:   # 부분 일치 폴백
        smiles_col = next((c for c in header if "smiles" in c.lower()), None)
    if smiles_col is None:
        raise ValueError(f"SMILES 컬럼을 찾지 못했습니다. 헤더: {header}")

    name_col = next((lower[h] for h in _NAME_HINTS if h in lower), None)
    if name_col is None or name_col == smiles_col:
        name_col = next((c for c in header if c != smiles_col), header[0])
    return smiles_col, name_col


def load_library_from_file(path: str,
                           smiles_col: str | None = None,
                           name_col: str | None = None,
                           sep: str | None = None,
                           source_tag: str = "") -> dict[str, str]:
    """
    CSV/TSV 파일에서 {이름: SMILES} 딕셔너리를 만든다.
    smiles_col / name_col을 생략하면 헤더에서 자동 감지한다.
    - sep : None이면 확장자로 추정(.tsv/.tab/.txt → 탭, 그 외 → 콤마)
    - source_tag : 이름 앞에 붙일 출처 태그 (예: 'FooDB'), 소스 구분/중복 방지용
    """
    if sep is None:
        sep = "\t" if path.lower().endswith((".tsv", ".tab", ".txt")) else ","
    if smiles_col is None or name_col is None:
        det_s, det_n = detect_columns(path, sep)
        smiles_col = smiles_col or det_s
        name_col = name_col or det_n

    print(f"[lib] {source_tag or path}: SMILES='{smiles_col}', 이름='{name_col}' 컬럼 사용")
    df = pd.read_csv(path, sep=sep, usecols=[smiles_col, name_col],
                     on_bad_lines="skip", low_memory=False)
    df = df.dropna(subset=[smiles_col, name_col])

    # 대용량 DB(수십만 행) 대비: iterrows 대신 zip으로 빠르게 딕셔너리 생성
    prefix = f"{source_tag}:" if source_tag else ""
    lib = {prefix + str(n): str(s)
           for n, s in zip(df[name_col], df[smiles_col])}
    print(f"[lib] {source_tag or path}: {len(lib)}개 화합물 로드")
    return lib


def load_foodb(path: str) -> dict[str, str]:
    """FooDB Compounds 덤프(CSV) 로더. 컬럼은 자동 감지."""
    return load_library_from_file(path, sep=",", source_tag="FooDB")


def load_npass(path: str) -> dict[str, str]:
    """NPASS structure 덤프(TSV) 로더. 컬럼은 자동 감지."""
    return load_library_from_file(path, sep="\t", source_tag="NPASS")


def load_coconut(path: str) -> dict[str, str]:
    """COCONUT(~40만+ 천연물) 덤프(CSV) 로더. 컬럼은 자동 감지."""
    return load_library_from_file(path, sep=",", source_tag="COCONUT")


# 소스 태그 → (로더 함수, cfg 경로 속성명) 매핑. 새 DB는 여기에 한 줄만 추가하면 됩니다.
LIBRARY_LOADERS = {
    "FooDB":   (load_foodb,   "foodb_path"),
    "NPASS":   (load_npass,   "npass_path"),
    "COCONUT": (load_coconut, "coconut_path"),
}


def build_screening_library(cfg: "Config") -> dict[str, str]:
    """
    설정된 경로에서 FooDB/NPASS/COCONUT을 읽어 하나로 합친다.
    파일이 없으면 DEMO_CANDIDATES로 폴백 (바로 테스트 가능하도록).
    RDKit이 SMILES를 파싱하지 못하는 항목은 screen 단계에서 자동으로 걸러집니다.
    """
    lib: dict[str, str] = {}
    for tag, (loader, path_attr) in LIBRARY_LOADERS.items():
        path = getattr(cfg, path_attr, None)
        if path and os.path.exists(path):
            lib.update(loader(path))

    if not lib:
        print("[lib] 천연물 DB 파일을 찾지 못해 DEMO_CANDIDATES로 폴백합니다.")
        return DEMO_CANDIDATES
    print(f"[lib] 통합 스크리닝 라이브러리: 총 {len(lib)}개 화합물")
    return lib


# ---------------------------------------------------------------------------
# 데모용 후보 물질 (천연물/약물 예시) — 천연물 DB 파일이 없을 때의 폴백
# ---------------------------------------------------------------------------
DEMO_CANDIDATES = {
    "Resmetirom":   "CCC1=CC(=CC(=C1OC2=CC(=NC(=O)NC2=O)Cl)C#N)N3C(=O)NC(=O)C(=N3)C(F)(F)F",
    "Quercetin":    "O=c1c(O)c(-c2ccc(O)c(O)c2)oc2cc(O)cc(O)c12",
    "Resveratrol":  "Oc1ccc(/C=C/c2cc(O)cc(O)c2)cc1",
    "Curcumin":     "COc1cc(/C=C/C(=O)CC(=O)/C=C/c2ccc(O)c(OC)c2)ccc1O",
    "Silymarin":    "COc1cc(C2Oc3cc(C4Oc5cc(O)ccc5C(=O)C4O)ccc3OC2CO)ccc1O",
    "EGCG":         "O=C(O)c1cc(O)c(O)c(O)c1",  # 단순화 예시
    "Berberine":    "COc1ccc2cc3[n+](cc2c1OC)CCc1cc2c(cc1-3)OCO2",
}


def run_pipeline(cfg: Config):
    print("=" * 70)
    print(f"MASLD 소재 발굴 파이프라인 | 타겟: {cfg.target} "
          f"({TARGETS[cfg.target]['name']})")
    print("=" * 70)

    df = assemble_training_data(cfg)          # ChEMBL (+ 선택적 PubChem 보강)
    clf = train_model(df, cfg)

    library = build_screening_library(cfg)   # FooDB + NPASS + COCONUT 통합 (없으면 데모)
    hits = screen_candidates(clf, library, cfg)

    # 유사도는 상위 후보만 (전체는 N^2라 클 수 있음) — 상위 20개로 제한
    top = dict(zip(hits["name"].head(20), hits["smiles"].head(20)))
    similarity_matrix(top, cfg)

    out_path = os.path.join(cfg.cache_dir, f"{cfg.target}_screening_results.csv")
    hits.to_csv(out_path, index=False)
    print(f"\n[done] 스크리닝 결과 저장 → {out_path}")


def main():
    parser = argparse.ArgumentParser(description="MASLD 바이오마커 타겟 소재 발굴 AI")
    parser.add_argument("--target", default="HSD17B13", choices=list(TARGETS.keys()),
                        help="타겟 바이오마커 (기본: HSD17B13)")
    parser.add_argument("--threshold", type=float, default=6.0,
                        help="active 판정 pIC50 임계값 (기본: 6.0 = IC50 1uM)")
    parser.add_argument("--augment-pubchem", action="store_true",
                        help="PubChem BioAssay로 학습셋 보강 (ChEMBL이 적을 때)")
    parser.add_argument("--chembl-csv", default=None,
                        help="ChEMBL 웹에서 받은 activity CSV 경로 (API 대신 사용)")
    args = parser.parse_args()

    cfg = Config(target=args.target, active_threshold=args.threshold,
                 augment_pubchem=args.augment_pubchem)
    if args.chembl_csv:
        cfg.chembl_csv_path = args.chembl_csv
    run_pipeline(cfg)


if __name__ == "__main__":
    main()
