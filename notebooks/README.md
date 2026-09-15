# 노트북 분류 가이드

노트북을 **역할별 3개 폴더**로 나눴습니다. 파일명 번호는 **그대로 유지**했습니다(마크다운 안에서 "04에서 설명"처럼 서로 참조하기 때문). 각 노트북은 어느 폴더에서 열든 자동으로 프로젝트 루트를 찾아가 실행됩니다(`data/`를 찾을 때까지 상위로 이동).

---

## 📂 pipeline/ — 현재 활성 전과정 (★ 수정·대체 대상)

내가 실제로 **수정하거나, 더 좋은 방법을 찾으면 새 노트북으로 대체할** 노트북들. 데이터 수집부터 스크리닝까지 **전 과정이 여기 다 있습니다.** 실행 순서(파일번호 순서가 아니라 아래 순서):

| 순서 | 노트북 | 역할 |
|---|---|---|
| 1 | `01_merge_ic50` | 데이터 수집 — BindingDB + ChEMBL IC50 합치기 |
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
