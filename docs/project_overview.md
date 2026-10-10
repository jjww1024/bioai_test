# 프로젝트 전체 정리 (실제 시간순)

**목표:** MASLD(대사이상 지방간질환) 표적 **HSD17B13 저해 천연물** 후보를 AI로 스크리닝.
날짜는 git 커밋 기준. 논리 순서가 아니라 **실제로 작업한 순서**.

---

## 08/01 — 초기 스캐폴드 (올인원 스크립트)
- MASLD/HSD17B13 타겟 AI 스캐폴드 첫 커밋.
- HSD17B13 ChEMBL ID 확정: **CHEMBL5305042**.
- RDKit MorganGenerator 최신 API로 전환.
- 로더 구축: 천연물 DB 로더(컬럼 자동감지·대용량), **ChEMBL 수동 CSV 로더**(API 장애 대비), **PubChem BioAssay 학습셋 보강**.
- **decoy 생성으로 클래스 불균형 해소**(`--add-decoys`) — 이때부터 decoy 도입.
- FLAML AutoML 옵션 + 스크리닝 배치예측.

## 08/12 — 파이프라인 스크립트화 + 초기 실험 (지금 legacy/docking)
- 정제 데이터(**BindingDB+ChEMBL**) 학습 파이프라인 스크립트.
- **decoy 균형 스크리닝 + descriptor(217종) 학습**(09,10).
- 지문+descriptor **결합 모델 비교**(11) + 도킹 준비.
- **정식 DUD-E(active별 개별 매칭) decoy 생성기**(06b).
- **도킹 실행/분석**(12–15): 로컬 실행, BI-3231 대조, **Ligand Efficiency 보정**으로 크기편향 재랭킹.
- NPASS 단독 스크리닝(08).

## 08/14 — 라벨링 + 노트북 전환
- **16_label_fingerprints**: fingerprint 엑셀에 active/inactive 라벨 + 4중 검증. label 컬럼→**potency** 개명.
- **.py 17개 → 셀 구분 .ipynb** 전면 변환.

## 08/19~20 — DUD-E 워크플로 + 최종 데이터/모델 v1
- DUD-E 제출용 active 대표 선정(배치 간 겹침 방지).
- **17_dude_workflow 전면 개편**: DUD-E decoy 전체 워크플로(생성→중복제거→Tanimoto 검증→1:1/1:5/1:10). 실제 `.picked` 결과 처리.
- **18**: 1:1 학습셋 descriptor 계산 + **WEKA용 CSV**(217→선택).
- **19**: 최종 학습데이터 v1 구축.
- **20**: 최종 데이터로 모델 학습·성능평가.
- (라벨 기준: IC50 ≤10µM=active, ≥20µM=inactive, 사이 제거 → active 2049 + inactive 200)

## 08/24 — 초보용 주석 전면 강화
- 전 노트북(01~17, bioai_test)에 **[설명]+[코드]+[코드 뜯어보기]** 구조 주석 추가. **로직 불변**(문서화만).

## 09/08 — 지문 6종·3D·v2·초기 앙상블·3-DB 스크리닝
- **04**: fingerprint **6종으로 확장**(ECFP4·MACCS·RDKit·AtomPair·**Avalon·TopologicalTorsion**).
- **09b (신규)**: 3D descriptor 11종(ETKDG conformer, >60원자 제외).
- **19 확장**: 6지문+2D+3D → **v2 최종표**(4098×5336).
- **20a (신규)**: train/val/test 70/15/15 층화 분할.
- **21 (신규)**: 상위4 soft-voting 앙상블 — **전 특징 concat 방식**(초기 앙상블).
- **08**: FooDB+COCONUT+NPASS **3-DB 스크리닝**(지문 앙상블, 대형은 속도 위해 LightGBM). *(COCONUT은 9/1 다운로드)*

## 09/15 — 표현앙상블 전환 + 후보 필터 + 구조 정리
- **22 (신규)**: 재균형 학습셋(decoy를 real_inactive 200에 맞춰 축소).
- **23 (신규)**: **표현 기반 앙상블(late fusion)** — concat 대체. (모델×표현) 조합 평가 → 상위5 soft-voting + `class_weight`. + 레퍼런스 문서.
- **08b**: 신모델로 3-DB **재스크리닝** → **GW-4064 1위**(합성 오염물) 발견 = 합성 편향 노출.
- notebooks/ **pipeline·legacy·docking 분리** + chdir 보강 + **00_check_env**.
- **08c** NP-likeness(Ertl 2008) 필터, **08d** 출처(organisms/dois) 필터(→16개), **08e** 식품 파이토케미컬 재스크리닝.

## 09/22 — 정밀 평가 + 확률 보정
- **23b**: 6분할 평가(Learning Curve·ROC·Confusion·Prediction Error·Calibration·Feature Importance).
  - **핵심 발견:** MCC 0.86이지만 **real_inactive 정답률 60%**가 진짜 실력. `fr_halogen` 상위 변수.
- **23c**: Platt 확률보정 + MCC 임계값 튜닝 → 개선 미미(Brier 0.031→0.028). "후처리 한계" 확인.

## 09/23 — CV 학습곡선 + 할로겐 매칭
- **23b 갱신**: 학습곡선을 5-fold CV + 음영(±std)으로.
- 할로겐 편향 진단: active 89% 할로겐 vs decoy 56%, 그러나 비할로겐 active도 IC50 동일(300nM) → 할로겐은 비인과(ADME용).
- "할로겐 active 제거" 실험 → 모델 붕괴(실패). **채택: 22 업데이트 = decoy만 할로겐 89% 매칭, real_inactive 보존.** → GW-4064↓, real_inactive 0.60→0.63, MCC↑.

## 09/28 — 정리·조합 고정·문서화
- **data/ 재구성**: raw·interim·processed·models·screening·reports·archive + **전 노트북 경로 자동수정**.
- **23 desc2d 조합 고정**: 재학습 시 grid 자동선택이 지문-only 편향 조합을 골라 → desc2d 포함 조합 고정(배포모델 일치). 재스크리닝 시 **GW-4064 8위→67위**.
- eval 지표/이미지 저장 + **modifications_rationale**(수정별 근거) + **project_overview**(이 문서) 작성.

## 10/10 — 데이터 재수집 + 전 파이프라인 재실행 (PubChem 신규 소스 추가)
- **raw 신규본 투입**: BindingDB·ChEMBL 재다운로드(`261010 *`). 실질 증가는 BindingDB **+7 분자**, ChEMBL은 **0**(동일 데이터, 구분자만 `;`).
- **PubChem BioAssay를 3번째 소스로 추가**: UniProt Q7Z5P4 관련 **AID 34건** → IC50 레코드 **2,812건 / 고유 CID 2,422**.
  - 단위 버그 발견·수정: PubChem `IC50` 컬럼=**nM**, `PubChem Standard Value`=**µM**. (처음 µM로 읽어 1000배 부풀려짐 → 바로잡음)
  - 대부분 **미국 특허 유래 용량-반응(confirmatory) assay** — HTS 단일농도 잡음 데이터가 아님.
- **01 개편**: BindingDB+ChEMBL → **+PubChem 3소스 병합**, ChEMBL 구분자 자동판별(`sniff_sep`). → 02·03 그대로 재실행.
  - 고유 물질 **2,686 → 3,253** / robust_dedup: CONFLICT(>100×) 18건.
- **17 패치**: ① PART C 저장경로 버그 수정(`data/` → `data/processed/`) ② `REUSE_CLEAN` 모드 추가 —
  원시 `.picked` 재파싱 없이 기존 clean decoy를 **새 active 기준으로 재검증**(겹침 제거 + Tanimoto 재계산).
  - 커레이션: **active 2049 → 2759(+710)**, **real_inactive 200 → 210(+10)**.
- **IC50 충돌(>100배) 18건 제외**: 03이 `CONFLICT (>100x)`로 표시했지만 17이 그 플래그를 안 써서 **전부 active로 학습에 들어가 있던 것**을 끊어냄 → active 2759 → **2741**. 공개 IC50의 정상 assay 간 편차는 ~0.5 log인데 2 log(100배) 충돌은 라벨 자체가 미지라 노이즈. (Kalliokoski 2013, Fourches 2010)
- **파일명 YYMMDD 스탬프 도입**(`notebooks/pipeline/_paths.py`): 산출 파일은 `out()`으로 `261010_*`, 입력은 `latest()`로 최신 스탬프 자동 선택. `STAMP` 한 줄만 바꾸면 전 노트북 반영.
  - decoy 풀 121,992 → **121,952** (새 active와 Tanimoto>0.35가 된 40개 제거). **신규 DUD-E 제출 불필요**(풀이 충분).
- **04·18·09b·19 재실행**: 지문 6종(3,581행), 2D desc 217종, 3D desc 11종(5,503/5,518 성공), v2 최종표 **(5,518 × 5,336)**.
  - 2D descriptor **선택 목록(36개)은 고정 유지** — 새 데이터로 재선택하면 조합 고정 원칙이 깨지므로 의도적으로 동결.
- **22 재실행**: active 2741 전부 + real_inactive 210 전부 + **할로겐매칭 decoy 210**(56%→91%, active 91%에 맞춤) = 3,161행.
- **23 재학습**(고정 조합 그대로) → **MCC 0.866 → 0.892(데이터 확장) → 0.908(충돌 18건 제외)**.
- **23b 갱신 + 셀 추가**: 평가지표 숫자표(`eval_metrics_current.csv/.xlsx`) + **프로브 3종 자동 점검**(`eval_probe_compounds.csv`).
- **23c**: 최적 임계값 0.77, Brier 0.021→0.018이나 MCC 0.908→0.900 → **원확률·0.5 유지**(이전과 같은 결론).
- ⚠️ **데이터 확장의 대가**: 신규 active 710개가 **99% 할로겐 / NP≥1 0개**(특허 합성 시리즈) → 합성 편향 심화.
  GW-4064 0.790 → **0.900**(위양성 악화). 이후 충돌 18건 제외로 0.854까지 되돌아왔으나 **여전히 출발점(0.790)보다 나쁨**.

### 지표 변화 (3단계)
| | 09/28 구모델 | 10/10 데이터확장 | 10/10 +충돌제외(현재) |
|---|---|---|---|
| 학습셋 | 2049+200+200 | 2759+210+210 | **2741+210+210** |
| MCC | 0.866 | 0.892 | **0.908** |
| ROC / PR | 0.990 / 0.998 | 0.989 / 0.998 | **0.993 / 0.999** |
| Brier | 0.032 | 0.026 | **0.021** |
| active recall | 0.994 | 0.983 | **0.988** |
| decoy | 1.000 | 1.000 | 0.969 |
| **real_inactive** | **0.63** | 0.839 | **0.871** |
| GW-4064 (낮아야) | 0.790 | 0.900 | 0.854 |
| Quercetin | 0.340 | 0.375 | 0.428 |
| α-Terthienyl (높아야) | 0.096 | 0.120 | 0.158 |

→ 충돌 18건 제외는 **내부 지표와 프로브를 동시에** 개선. 라벨 노이즈 제거 효과.

---

## 현재 상태 (배포 모델, 2026-10-10)
`data/models/261010_HSD17B13_repr_ensemble.pkl`
- 표현앙상블 5조합(고정): XGB×maccs, RF×rdkit, RF×desc2d, ET×desc2d, ET×topotorsion
- 학습셋: active **2741** + real_inactive **210** + **할로겐매칭 decoy 210** = 3,161 (train 2211 / val 475 / test 475), class_weight
- **지표(test):** MCC **0.9085** · ROC 0.9927 · PR 0.9989 · Acc 0.9789 · Recall 0.9879 · Prec 0.9879 · Brier 0.0213
- **혼동행렬:** TN 58 / FP 5 / FN 5 / TP 407
- **source별:** active 0.988 · decoy 0.969 · **real_inactive 0.871**
- **프로브:** GW-4064 0.854 · Quercetin 0.428 · α-Terthienyl 0.158
- 스크리닝 결과(`data/screening/*`)는 **구모델 기준 = stale** → 08b~08d 재실행 필요

## 남은 한계 → 다음
- **합성 편향 잔존(출발점보다 악화)**: 공개 HSD17B13 활성 데이터가 전부 제약사 특허 합성물(할로겐 91%, NP≥1 0개).
  내부 지표는 올랐지만 **천연물 도메인 외삽은 09/28보다 나쁨**(GW-4064 0.790→0.854).
- real_inactive 87%로 개선됐으나 n=31(test)로 표본이 작음.
- **근본 검증: 도킹(PDB 8G9V, 리간드 YYC) 또는 효소 assay.**
- 조합선택을 천연물 검증셋으로 자동화(고정의 정식 대체) / 천연물 쪽 라벨 확보가 유일한 근본 해법.

---
## 논리순서 파이프라인 (참고: 실행 순서와 다름)
데이터(raw) → 전처리/라벨(01–03,17) → 피처(04,18,09b) → 조립(19,v2) → 재균형/분할(22,20a) → 학습(23) → 스크리닝(08b) → 필터(08c,08d) → 평가(23b).
