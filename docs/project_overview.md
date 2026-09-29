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

---

## 현재 상태 (배포 모델)
`data/models/HSD17B13_repr_ensemble.pkl`
- 표현앙상블 5조합(고정): XGB×maccs, RF×rdkit, RF×desc2d, ET×desc2d, ET×topotorsion
- 학습셋: active 2049 + real_inactive 200 + **할로겐매칭 decoy 200**, class_weight
- **지표(test):** MCC 0.866 · ROC 0.990 · PR 0.998 · Acc 0.965 · Recall 0.994 · Prec 0.965 · Brier 0.032
- **source별:** active 0.99 · decoy 1.00 · **real_inactive 0.63** / **프로브:** GW-4064 0.790 · Quercetin 0.340
- **검증 천연물 후보 16개:** `data/screening/screen_repr_np_provenance.csv`

## 남은 한계 → 다음
- real_inactive 63%(activity cliff, 데이터 부족), 합성 편향 잔존, 천연물 도메인 확률 신뢰도 낮음.
- **근본 검증: 도킹(PDB 8G89) 또는 효소 assay.** / 조합선택을 천연물 검증셋으로 자동화(고정의 정식 대체).

---
## 논리순서 파이프라인 (참고: 실행 순서와 다름)
데이터(raw) → 전처리/라벨(01–03,17) → 피처(04,18,09b) → 조립(19,v2) → 재균형/분할(22,20a) → 학습(23) → 스크리닝(08b) → 필터(08c,08d) → 평가(23b).
