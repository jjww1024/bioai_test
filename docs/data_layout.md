# data/ 폴더 구조 가이드

`data/`는 역할별 7개 폴더로 정리됨. 노트북들은 모두 새 경로를 참조하도록 자동 갱신됨.
(`data/`는 `.gitignore` 대상이라 파일 자체는 GitHub에 안 올라감 — 이 문서만 추적됨.)

---

## 📂 raw/ — 외부 원본 (절대 수정 금지)
내려받은 원본 데이터. 파이프라인의 출발점.
- `bindingdb_hsd17b13.tsv`, `chembl_hsd17b13.tsv` — IC50 원본
- `coconut_csv-09-2026.csv` (683MB), `npass_structures.tsv`, `foodb_2020_4_7_csv/` — 스크리닝 대상 천연물 DB

## 📂 interim/ — 중간 산출물 (재생성 가능)
원본 → 최종 사이의 과정 파일. 지워도 노트북 재실행으로 복원 가능.
- `HSD17B13_IC50_merged.xlsx` — BindingDB+ChEMBL 병합
- `HSD17B13_1to1_descriptors_weka.csv` — WEKA 특징선택 **전** 단계
- `decoys_clean.*`, `HSD17B13_decoys*.csv`, `dude_*` — decoy 생성 과정

## 📂 processed/ — ★ 학습에 실제 쓰는 최신 파일
현재 파이프라인이 읽고 쓰는 핵심 파일.
- `HSD17B13_final_training_1to1_v2.csv` — **최종 학습표**(6지문+2D+3D+potency)
- `HSD17B13_rebalanced_membership.csv` — **현재 학습셋**(할로겐매칭 decoy + 분할)
- `HSD17B13_1to1_3d_descriptors.csv` — 3D descriptor
- `HSD17B13_1to1_descriptors.xlsx` — 2D descriptor(base)
- `HSD17B13_1to1_descriptors_weka_filtered.csv` — WEKA 선택 후 36개
- `train_1to1.csv` — 1:1 학습셋(source 라벨)
- `curated_ligands.csv` — 큐레이션 active/inactive
- `HSD17B13_fingerprints.xlsx` — 지문 6종

## 📂 models/ — 학습된 모델·성능표
- `HSD17B13_repr_ensemble.pkl` — **현재 배포 모델**(표현앙상블, 할로겐매칭+desc2d 고정)
- `HSD17B13_repr_grid.csv`, `HSD17B13_repr_test_summary.csv` — 조합 성능표

## 📂 screening/ — 스크리닝/후보 결과 (신모델)
- `screen_3db_hits_repr.csv/.xlsx` — 3개 DB 스크리닝 전체 후보
- `screen_repr_th075_flagged.csv` — 임계값 0.75 + 합성지표 플래그
- `screen_repr_np_filtered.csv` — NP-likeness 통과
- `screen_repr_np_provenance.csv` — 출처·문헌 검증 천연물 16개
- `screen_top20_clean_named.csv`, `food_phytochemical_scores.csv`

## 📂 reports/ — 평가 그림
- `ensemble_evaluation.png` — 6분할 평가
- `learning_curve_cv.png`, `calibration_threshold.png`, `_activity_cliff_example.png`

## 📂 archive/ — 구버전 (대체됨, 보존)
파이프라인에서 빠졌지만 참고용 보존. 무엇으로 대체됐는지:
| 구파일 | 대체 |
|---|---|
| `HSD17B13_final_training_1to1.csv/.xlsx` (v1) | → processed/ `_v2.csv` |
| `HSD17B13_split_1to1.csv` | → `rebalanced_membership.csv` |
| `HSD17B13_ensemble_screen_model.pkl` 외 구모델 3종 | → `repr_ensemble.pkl` |
| `HSD17B13_descriptors.csv/.xlsx` (217종) | → WEKA 필터본 |
| `screen_3db_hits.csv/.xlsx` (구모델 스크리닝) | → `screen_3db_hits_repr.*` |
| `train_1to5/1to10.csv` | 미사용(1to1만 씀) |
| `_top20_*.csv`, `screen_top20_np_check.csv` | 구모델 분석 |

---

## 파이프라인 데이터 흐름 (요약)
```
raw/ (원본)
  → interim/ (병합·decoy·descriptor 전처리)
  → processed/ (v2·membership·descriptor 최신본)
  → models/ (repr_ensemble.pkl)
  → screening/ (후보) + reports/ (평가)
```
