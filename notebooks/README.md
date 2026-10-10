# 노트북 분류 가이드

노트북을 **역할별 3개 폴더**로 나눴습니다. 파일명 번호는 **그대로 유지**했습니다(마크다운 안에서 "04에서 설명"처럼 서로 참조하기 때문). 각 노트북은 어느 폴더에서 열든 자동으로 프로젝트 루트를 찾아가 실행됩니다(`data/`를 찾을 때까지 상위로 이동).

---

## 📂 pipeline/ — 현재 활성 전과정 (★ 수정·대체 대상)

내가 실제로 **수정하거나, 더 좋은 방법을 찾으면 새 노트북으로 대체할** 노트북들. 데이터 수집부터 스크리닝까지 **전 과정이 여기 다 있습니다.** 실행 순서(파일번호 순서가 아니라 아래 순서):

| 순서 | 노트북 | 역할 |
|---|---|---|
| 1 | `01_merge_ic50` | 데이터 수집 — BindingDB + ChEMBL + **PubChem** IC50 합치기(nM 통일) |
| 2 | `02_add_dedup_sheets` | 전처리 — 중복 정리 시트 추가 |
| 3 | `03_robust_dedup` | 전처리 — 값 신뢰도 기반 중복 제거 → curated ligands |
| 4 | `17_dude_workflow` | 학습셋 — DUD-E decoy 생성 + 1:1/1:5/1:10 세트 |
| 5 | `04_make_fingerprints` | 피처 — fingerprint 6종 |
| 6 | `18_descriptors_for_weka` | 피처 — 2D descriptor 계산 + WEKA용 CSV |
| — | *(WEKA 특징선택: 노트북 밖 수동 단계)* | 2D descriptor 36개 선별 |
| 7 | `09b_make_3d_descriptors` | 피처 — 3D descriptor |
| 8 | `19_final_training_data` | 조립 — 6지문 + 2D + 3D + potency → 최종표(v2) |
| 9 | `22_rebalanced_dataset` | 재균형 — decoy=real_inactive, active 전부 유지 + 층화 분할 |
| 10 | `23_representation_ensemble` | 학습 — (모델×표현) 조합 평가 → 상위 조합 앙상블 (class_weight) |
| 11 | `08b_screen_libraries_repr` | 스크리닝 — FooDB·NPASS·COCONUT 3개 DB |

> 데이터→전처리→피처→학습셋→분할→학습→스크리닝. 이 폴더만 보면 전체 흐름이 완결됩니다.

(평가: `23b_evaluate_ensemble` 6분할 평가+지표표+프로브, `23c_calibrate_threshold` 확률보정·임계값.
후보 필터: `08c_nplikeness_filter` → `08d_provenance_filter`, `08e_food_phytochemical_screen`.
환경 점검: `00_check_env`.)

---

## 🏷️ 파일명 날짜 스탬프 규칙 (`_paths.py`)

파이프라인이 **만드는** 모든 파일은 이름 앞에 **`YYMMDD_`** 가 붙습니다 → 파일명만 보고 최신본을 구분.

```
data/processed/261010_train_1to1.csv
data/models/261010_HSD17B13_repr_ensemble.pkl
```

노트북은 경로를 직접 쓰지 않고 `pipeline/_paths.py`의 함수 두 개를 씁니다.

| 함수 | 용도 | 동작 |
|---|---|---|
| `out("data/x/name.csv")` | **쓰기** | `data/x/261010_name.csv` — 오늘 스탬프를 붙임 |
| `latest("data/x/name.csv")` | **읽기** | 스탬프가 **가장 큰(최신)** 파일을 자동 선택. 스탬프본이 없으면 무스탬프 원본(예: WEKA 수동 선택본) |
| `which("data/x/name.csv")` | 진단 | 그 이름으로 존재하는 모든 스탬프본을 최신순 나열 |

**파이프라인을 새로 돌릴 때는 `_paths.py`의 `STAMP = "261010"` 한 줄만 새 날짜로 바꾸면 됩니다.**
노트북별로 날짜를 적지 않으므로 스탬프가 서로 엇갈릴 수 없고, 이전 결과는 옛 스탬프 이름으로 그대로 남습니다.

> 예외: `data/raw/`(외부 원본, 손대지 않음)와 `data/interim/dude_decoys`·`dude_input`(폴더)은 스탬프를 붙이지 않습니다.

---

## 📂 legacy/ — 구형(대체됨), 코드 공부용

더 나은 버전이 나와 **파이프라인에서 빠졌지만**, 개념·코드 학습용으로 보존. 무엇으로 대체됐는지:

| 노트북 | 상태 | 대체 |
|---|---|---|
| `05_train_clean` | 초기 학습 실험 | → 23 |
| `06_add_decoys` | decoy 생성(전역창) | → 17 |
| `06b_add_decoys_dude` | decoy 생성(초기 DUD-E) | → 17 |
| `07_train_with_decoys` | decoy 학습(초기) | → 22·23 |
| `08_screen_npass` | NPASS 단일 스크리닝 | → 08b |
| `08_screen_libraries` | 3DB 스크리닝(6지문+LGBM) | → 08b |
| `09_make_descriptors` | descriptor 217종 | → 18 |
| `10_train_descriptors` | descriptor 학습 | → 23 |
| `11_train_combined` | 지문+descriptor 결합(초기) | → 23 |
| `16_label_fingerprints` | 라벨 부착 유틸 | (일회성) |
| `20_model_eval` | 모델 평가(초기) | → 23 |
| `20a_split_train_val_test` | 1:1 분할 | → 22(재균형+분할) |
| `21_ensemble` | 전특징 concat + 알고리즘 앙상블 | → 23(표현 기반) |

---

## 📂 docking/ — 도킹 검증 트랙 (별도, 참고/향후)

지문 모델과 **독립적인** 물리 기반 검증 경로(PDB 8G89). 스크리닝 후보를 실제 결합으로 확인할 때 사용.

| 노트북 | 역할 |
|---|---|
| `12_prep_docking` | 도킹용 3D 리간드 준비 |
| `13_prep_receptor` | 수용체(단백질) 준비 |
| `14_run_docking` | smina 도킹 실행 & 랭킹 |
| `15_analyze_docking` | 도킹 점수 크기편향 보정(ligand efficiency) |

---

## 배경 근거
설계 판단(표현 기반 앙상블, decoy 축소, class_weight, 2D/3D)의 학술 근거는 `../docs/references_modeling.md` 참고.
