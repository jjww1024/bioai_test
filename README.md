# bioai_test — MASLD 바이오마커 타겟 소재 발굴 AI

MASLD(대사이상 관련 지방간질환) 개선을 위해 특정 **바이오마커(타겟)**를 억제/활성화하는
화합물·천연물을 발굴하는 머신러닝 파이프라인. 현재 기본 타겟은 **HSD17B13**.

## 파이프라인

```
ChEMBL 활성 데이터 ──┐
                     ├─→ RDKit (SMILES → ECFP fingerprint) ─→ RandomForest 학습
천연물 DB (스크리닝) ─┘
   FooDB / NPASS / COCONUT ─→ 학습된 모델로 활성 예측 ─→ hit ranking ─→ Tanimoto 유사도
```

| 단계 | 함수 |
|------|------|
| 1. 데이터 수집 | `fetch_bioactivity` — ChEMBL에서 IC50 → pIC50, active/inactive 라벨 |
| 2. 벡터화 | `smiles_to_fp`, `build_feature_matrix` — Morgan(ECFP4) fingerprint |
| 3. 학습 | `train_model` — RandomForest 분류 + ROC-AUC |
| 4. 스크리닝 | `screen_candidates` — 천연물 DB 활성 확률 예측 |
| 5. 유사도 | `similarity_matrix` — 후보 간 Tanimoto |
| 라이브러리 로딩 | `load_foodb` / `load_npass` / `load_coconut` |

## 설치

```bash
python -m venv venv
venv\Scripts\Activate.ps1          # Windows PowerShell
pip install -r requirements.txt
```

## 실행

```bash
python bioai_test.py                    # HSD17B13, 데모 후보로 바로 실행
python bioai_test.py --target THRB      # 다른 타겟
python bioai_test.py --augment-pubchem  # PubChem BioAssay로 학습셋 보강
python bioai_test.py --add-decoys       # 무작위 화합물로 decoy 추가 (불균형 해소)
python bioai_test.py --automl           # FLAML AutoML로 여러 모델 자동 탐색
python bioai_test.py --chembl-csv data/chembl_activities.csv  # 수동 ChEMBL CSV 사용

# 실전 조합 예시 (권장):
python bioai_test.py --augment-pubchem --add-decoys --automl --automl-budget 60
```

천연물 DB 파일이 없으면 내장 `DEMO_CANDIDATES`로 폴백하므로 설치 직후 바로 돌아갑니다.

## 학습 데이터 소스 (3가지, 자동 통합)

`assemble_training_data`가 아래를 합쳐 학습셋을 만듭니다:

1. **ChEMBL API** (기본) — 자동 다운로드
2. **ChEMBL 수동 CSV** (`data/chembl_activities.csv`가 있으면 API 대신 사용) — **API 장애 시 유용**
   - 다운로드: [ChEMBL](https://www.ebi.ac.uk/chembl/)에서 타겟(HSD17B13 = `CHEMBL5305042`) 검색 →
     Activities 탭 → CSV 내려받아 `data/chembl_activities.csv`로 저장. (세미콜론 구분·컬럼명 자동 인식)
3. **PubChem BioAssay** (`--augment-pubchem`) — NCBI GeneID로 active/inactive 수집

## 천연물 DB 준비 (선택)

`data/` 폴더에 아래 파일을 두면 자동으로 통합 스크리닝합니다. 컬럼명은 다운로드 버전마다
다를 수 있으니 실제 헤더를 확인해 `load_*` 함수의 `smiles_col`/`name_col`을 맞추세요.

| DB | 다운로드 | 기본 경로 |
|----|----------|-----------|
| FooDB | https://foodb.ca/downloads | `data/foodb_compounds.csv` |
| NPASS | https://bidd.group/NPASS/ | `data/npass_structures.tsv` |
| COCONUT | https://coconut.naturalproducts.net/download | `data/coconut.csv` |

## 주의

- **HSD17B13 ChEMBL ID 확인 필수**: 코드의 `CHEMBL4523954`는 미확인 값. ChEMBL에서 직접 검색해 교체.
- **최신 타겟은 데이터가 적을 수 있음**: 부족하면 PubChem BioAssay나 논문 SI로 학습셋 보강.
- **천연물 DB는 예측 대상**(라벨 없음)이며 학습에는 ChEMBL 데이터를 사용.
- 연구/탐색용 스캐폴드입니다. 실제 발굴 결과는 in vitro 검증이 필요합니다.
