# data/ 폴더 구조 가이드

`data/`는 역할별 7개 폴더로 정리됨. 노트북들은 모두 새 경로를 참조하도록 자동 갱신됨.
(`data/`는 `.gitignore` 대상이라 파일 자체는 GitHub에 안 올라감 — 이 문서만 추적됨.)

---

## 🏷️ 파일명 날짜 스탬프 (`YYMMDD_`)

파이프라인이 **만드는** 파일은 이름 앞에 생성 날짜가 붙음 → 파일명만 보고 최신본 판별.

```
data/processed/261010_train_1to1.csv        ← 2026-10-10 생성 (현재 최신)
data/archive/260928_train_1to1.csv          ← 2026-09-28 판 (보존)
```

- 노트북은 경로를 직접 쓰지 않고 `notebooks/pipeline/_paths.py`의 `out()`(쓰기, 오늘 스탬프) /
  `latest()`(읽기, **최신 스탬프 자동 선택**)를 사용.
- 새로 돌릴 때는 `_paths.py`의 `STAMP` 한 줄만 바꾸면 전 노트북에 반영.
- **스탬프 없는 파일**은 두 종류뿐:
  - `raw/` — 외부 원본(손대지 않음. 단 사용자가 받은 BindingDB/ChEMBL 파일명에는 이미 `261010`이 들어 있음)
  - `processed/HSD17B13_1to1_descriptors_weka_filtered.csv` — WEKA 수동 선택본(의도적 동결)
- 아래 목록의 파일명은 **스탬프를 뺀 기준 이름**으로 적음.

---

## 📂 raw/ — 외부 원본 (절대 수정 금지)
내려받은 원본 데이터. 파이프라인의 출발점.
- **현재 사용(2026-10-10 다운로드본)**
  - `261010 binding db hsd17b13 relavent raw.tsv` — BindingDB IC50 원본
  - `261010 Chembl hsd17b13 relavent raw.csv` — ChEMBL IC50 원본 (**구분자 `;`**, 노트북 01이 자동 판별)
  - `261010 Chembl hsd17b13 relavent raw.tsv` — 위 csv와 **내용 동일**(확장자만 다름), 미사용
- **구버전(보존, 미사용)**: `bindingdb_hsd17b13.tsv`, `chembl_hsd17b13.tsv` (2026-08 다운로드본)
- `coconut_csv-09-2026.csv` (700MB), `npass_structures.tsv`, `foodb_2020_4_7_csv/` — 스크리닝 대상 천연물 DB

## 📂 interim/ — 중간 산출물 (재생성 가능)
원본 → 최종 사이의 과정 파일. 지워도 노트북 재실행으로 복원 가능.
- `HSD17B13_IC50_merged.xlsx` — **BindingDB+ChEMBL+PubChem** 병합(4시트: all_data / duplicates_only / same_dedup_keepdiff / median_per_compound / robust_dedup)
- `pubchem_hsd17b13_ic50.csv` — PubChem BioAssay(Q7Z5P4, AID 34건) IC50 수집본, **nM 통일 완료**
  - 단위 규칙: PubChem `IC50` 컬럼=**NANOMOLAR**, `PubChem Standard Value`=**MICROMOLAR**
- `pubchem_hsd17b13_ic50_raw.csv` — 위의 수집 원시본(aid·outcome·value_src 포함)
- `pubchem_hsd17b13_actives.csv`, `_pubchem_hsd17b13_active_cids.pkl` — PubChem active CID 목록(NP 점수 포함)
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

## 📂 screening/ — 스크리닝/후보 결과
> ⚠️ **2026-10-10 기준 전부 구모델(active 2049판) 결과 = stale.** 신모델(active 2759판)로 08b→08c→08d 재실행 필요.
- `screen_3db_hits_repr.csv/.xlsx` — 3개 DB 스크리닝 전체 후보
- `screen_repr_th075_flagged.csv` — 임계값 0.75 + 합성지표 플래그
- `screen_repr_np_filtered.csv` — NP-likeness 통과
- `screen_repr_np_provenance.csv` — 출처·문헌 검증 천연물 16개
- `screen_top20_clean_named.csv`, `food_phytochemical_scores.csv`

## 📂 reports/ — 평가 그림 + 지표값
- `ensemble_evaluation.png` — 6분할 평가
- `eval_metrics_current.csv` / `.xlsx` — 평가지표 숫자표(시트: 전체지표·혼동행렬·source별)
- `eval_probe_compounds.csv` — 프로브 3종(GW-4064 / Quercetin / α-Terthienyl) 확률 점검
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
