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
    #   ↓ chembl_id는 반드시 ChEMBL에서 "HSD17B13" 검색해 실제 값으로 확인/교체할 것.
    "HSD17B13": {"chembl_id": "CHEMBL4523954", "name": "17-beta-HSD type 13"},
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

def load_library_from_file(path: str,
                           smiles_col: str,
                           name_col: str,
                           sep: str = ",",
                           source_tag: str = "") -> dict[str, str]:
    """
    CSV/TSV 파일에서 {이름: SMILES} 딕셔너리를 만든다.
    - smiles_col : SMILES가 든 컬럼명
    - name_col   : 화합물 이름/ID 컬럼명
    - sep        : 구분자 (CSV=',', TSV='\\t')
    - source_tag : 이름 앞에 붙일 출처 태그 (예: 'FooDB'), 소스 구분/중복 방지용
    """
    df = pd.read_csv(path, sep=sep, usecols=lambda c: c in {smiles_col, name_col})
    df = df.dropna(subset=[smiles_col, name_col])
    lib: dict[str, str] = {}
    for _, row in df.iterrows():
        key = f"{source_tag}:{row[name_col]}" if source_tag else str(row[name_col])
        lib[key] = str(row[smiles_col])
    print(f"[lib] {source_tag or path}: {len(lib)}개 화합물 로드")
    return lib


def load_foodb(path: str) -> dict[str, str]:
    """FooDB Compounds 덤프(CSV) 로더. 컬럼명은 실제 파일에 맞게 조정하세요."""
    return load_library_from_file(
        path, smiles_col="moldb_smiles", name_col="name",
        sep=",", source_tag="FooDB")


def load_npass(path: str) -> dict[str, str]:
    """NPASS structure 덤프(TSV) 로더. 컬럼명은 실제 파일에 맞게 조정하세요."""
    return load_library_from_file(
        path, smiles_col="canonical_smiles", name_col="pref_name",
        sep="\t", source_tag="NPASS")


def load_coconut(path: str) -> dict[str, str]:
    """
    COCONUT (COlleCtion of Open NAtural producTs) 덤프(CSV) 로더.
    ~40만+ 천연물 구조를 포함하는 대형 DB. 컬럼명은 다운로드 버전마다 다를 수 있으니
    실제 파일 헤더를 확인해 smiles_col/name_col을 맞추세요.
    (흔한 컬럼: 'canonical_smiles' 또는 'smiles', 이름/ID는 'identifier' 또는 'name')
    """
    return load_library_from_file(
        path, smiles_col="canonical_smiles", name_col="identifier",
        sep=",", source_tag="COCONUT")


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

    df = fetch_bioactivity(cfg)
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
    args = parser.parse_args()

    cfg = Config(target=args.target, active_threshold=args.threshold)
    run_pipeline(cfg)


if __name__ == "__main__":
    main()
