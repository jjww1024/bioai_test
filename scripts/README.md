# scripts/ — 정제 데이터(BindingDB + ChEMBL) 기반 학습 파이프라인

`bioai_test.py`(ChEMBL/PubChem 자동 수집 파이프라인)와 별개로, **BindingDB·ChEMBL에서
수동 다운로드한 HSD17B13 IC50 실측 데이터**를 정제·학습하는 스크립트 모음.
(PubChem 자동수집이 무관한 assay로 오염됐던 문제를 피하기 위한 경로)

## 데이터 준비 (data/ 폴더에 아래 이름으로)

`data/`는 `.gitignore`로 제외되므로 대용량/개인 파일이 GitHub에 올라가지 않습니다.

| 파일 | 출처 |
|------|------|
| `data/bindingdb_hsd17b13.tsv` | BindingDB에서 HSD17B13 검색 → TSV 다운로드 |
| `data/chembl_hsd17b13.tsv` | ChEMBL 타겟(CHEMBL5305042) Activities → TSV |

## 실행 순서 (프로젝트 루트에서)

```bash
# --- 데이터 정제 & fingerprint 학습 ---
python scripts/01_merge_ic50.py        # 두 TSV 병합 + canonical SMILES 중복판정 → data/HSD17B13_IC50_merged.xlsx
python scripts/02_add_dedup_sheets.py  # 같은IC50 합침 / 물질별 중앙값 시트 추가
python scripts/03_robust_dedup.py      # 값 퍼짐(spread) 기반 신뢰도 등급 시트 추가
python scripts/04_make_fingerprints.py # 4종 fingerprint(ECFP4/MACCS/RDKit/AtomPair) → data/HSD17B13_fingerprints.xlsx
python scripts/05_train_clean.py       # IC50<=10000nM=active 라벨링 + 4종 fingerprint 학습·비교

# --- decoy로 클래스 균형 → 스크리닝 ---
python scripts/06_add_decoys.py        # DUD-E식 property-matched decoy를 PubChem에서 생성(active:inactive 1:1) → data/HSD17B13_train_with_decoys.xlsx
python scripts/07_train_with_decoys.py # 균형 데이터로 4종 fingerprint 재학습 → data/HSD17B13_screen_model.pkl (실측 inactive 판별력도 별도 리포트)
python scripts/08_screen_npass.py      # NPASS 천연물 9만개 스크리닝(활성확률 + 알려진 active와 유사도) → data/HSD17B13_npass_hits.xlsx

# --- descriptor(물성) 학습 & 해석 ---
python scripts/09_make_descriptors.py  # RDKit 2D descriptor 217종 계산 → data/HSD17B13_descriptors.xlsx
python scripts/10_train_descriptors.py # descriptor로 학습 + 어떤 물성이 활성과 연관되나 해석 → data/HSD17B13_descriptor_importance.csv
```

## 라벨링 기준 (05·07·09·10 공통)

- `IC50 ≤ 10000 nM` → **active(1)**
- `IC50 > 10000 nM` (회색지대·부등호 `>` 포함) → **inactive(0)**
- 같은 물질에 측정 여러 개면 하나라도 active면 active. 물질(canonical) 단위로 학습(누수 방지).

## decoy(06) 요약

- **깨끗한 decoy = active와 [MW·logP·HBD·HBA·회전결합·전하]는 닮았지만 구조(ECFP4 Tanimoto≤0.35)는 다르고, 알려진 active가 아닌 PubChem 무작위 분자** (DUD-E 방식).
- decoy는 *가정된* inactive → 스크리닝 결과는 1차 필터로만, 상위 후보는 도킹·문헌으로 재검증.

## 전처리 일관성 (중요)

- 신규물질(NPASS 등) 예측 시 **featurize를 학습과 완전히 동일하게** 적용해야 함(같은 fingerprint·비트수·canonical화).
- descriptor 모델은 imputation을 **Pipeline에 묶어 저장**(10) → 신규 데이터엔 `transform`만 적용(스케일러/임퓨터를 신규 데이터로 다시 fit 금지 = data leakage).
- 전처리가 같아도 신규 분자가 학습 분포 밖이면(도메인 시프트) 예측은 외삽 → applicability domain(유사도) 체크 병행.
