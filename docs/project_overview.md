# 프로젝트 전체 정리 (데이터 → 전처리 → 학습 → 개선 → 현재)

**목표:** MASLD(대사이상 지방간질환) 표적 **HSD17B13 저해 천연물** 후보를 AI로 스크리닝.

---

## 1단계 — 데이터 수집 (raw/)

**학습용 (active/inactive 원본, IC50):**
- `bindingdb_hsd17b13.tsv` — BindingDB, 2619행(고유 2471), IC50 최대 100µM
- `chembl_hsd17b13.tsv` — ChEMBL, 393행, IC50 ≤10µM에서 잘림

**스크리닝 대상 (천연물 DB):**
- `coconut_csv-09-2026.csv` — COCONUT 738,827개
- `npass_structures.tsv` — NPASS 96,235개
- `foodb_.../Compound.csv` — FooDB 70,477개 (식품 성분)

---

## 2단계 — 전처리 & 라벨링 (노트북 01–03, 17)

1. **01** BindingDB+ChEMBL IC50 병합.
2. **02–03** 중복 제거: 문자열→canonical SMILES→InChIKey, 값 신뢰도(값 퍼짐) 기반.
3. **라벨 정의:** IC50 **≤10,000 nM = active**, **≥20,000 nM = inactive**, 그 사이(gray)는 제거. (10µM 컷은 사용자 지정)
   - 결과 `curated_ligands.csv`: **active 2049 + inactive(real) 200**
4. **17 (DUD-E 워크플로):** active를 DUD-E에 넣어 property-matched decoy 생성 → 중복제거(canonical+InChIKey, inactive/배치 간 겹침 체크) + Tanimoto 검증 → `train_1to1.csv` (active 2049 : decoy 1849 + real 200).

---

## 3단계 — 피처(표현) 생성 (노트북 04, 18, 09b)

- **04** 지문 6종: ECFP4(Morgan), MACCS(167), RDKit, AtomPair, Avalon, TopologicalTorsion (각 1024, MACCS만 167).
- **18** 2D descriptor 217종 계산 → **WEKA 특징선택 36종** (`_weka_filtered.csv`).
- **09b** 3D descriptor 11종 (ETKDG conformer 생성 후, 대형 분자 >60원자 제외).

---

## 4단계 — 최종 학습데이터 조립 (노트북 19)

- 6지문(5287열) + 2D 36 + 3D 11 + potency → **`HSD17B13_final_training_1to1_v2.csv`** (4098행 × 5336열).

---

## 5단계 — 초기 모델 (구버전, 현재 legacy/)

- **05·07·10·11** 초기 학습 실험(지문/descriptor 개별·결합).
- **20·21** 초기 앙상블: **전 특징을 한 벡터로 concat** → 알고리즘 앙상블(상위4 soft voting).
- **08** 초기 스크리닝(지문 6종 concat + LightGBM).
- 문제 인식: 교차검증만 하고 train/val/test 미분할, descriptor가 지문에 묻힘, 성능(0.96)이 부풀려짐.

---

## 6단계 — 개선 반복 (이번 작업의 핵심)

시간순 변경:

1. **train/val/test 분할 도입 (20a):** 기존 CV만 → 70/15/15 층화 분할.
2. **재균형 학습셋 (22):** decoy를 real_inactive 개수(200)에 맞춰 축소 → active 2049 : (decoy 200 + real 200). *(근거: 쉬운 decoy가 성능 부풀림 — Chen 2019)*
3. **표현 기반 앙상블로 전환 (23):** concat(early fusion) → **(모델×표현) 1대1 학습 후 상위조합 결합(late fusion)** + `class_weight='balanced'`(active 전부 유지). *(근거: Snoek 2005, Wolpert 1992, Ho 1998)*
   - 초기 채택 조합: XGB×maccs, RF×rdkit, RF×desc2d, ET×desc2d, ET×topotorsion.
4. **재스크리닝 (08b):** 신모델로 3-DB 스크리닝 → **GW-4064가 1위**로 나옴(합성 FXR 작용제, 오염물) → **합성 편향** 발견.
5. **후보 정제 필터 추가:**
   - **08c** NP-likeness(Ertl 2008)로 할로겐 없는 합성 열거물 제거 (243→59).
   - **08d** 출처(organisms)/문헌(dois)로 실재 검증 천연물만 (59→16).
   - **08e** 식품 지향 재스크리닝(대량생산 파이토케미컬 30종): 전부 <0.5 → 모델은 식품 성분에 보수적.
6. **정밀 평가 (23b):** Learning Curve(CV 음영)·ROC·Confusion·Prediction Error·Calibration·Feature Importance.
   - **핵심 발견:** 겉보기 MCC 0.86이지만 **real_inactive(어려운 음성) 정답률 60%**가 진짜 실력. `fr_halogen`이 상위 변수.
7. **확률 보정/임계값 실험 (23c):** Platt 보정+MCC 임계값 → 개선 미미(MCC≈, Brier 0.031→0.028). "후처리로는 한계" 확인.
8. **할로겐 편향 진단 & 수정:**
   - 진단: active 89%가 할로겐 vs decoy 56%. 그런데 **비할로겐 active도 IC50 중앙값 동일(300nM)** → 할로겐은 결합에 인과적이지 않고 ADME용. 모델이 상관을 인과로 착각.
   - "할로겐 active 제거" 실험 → active 89% 손실로 **모델 붕괴(MCC→0)**. 실패.
   - **채택: decoy만 할로겐 89%로 매칭, real_inactive 보존 (22 업데이트)** → GW-4064↓, real_inactive 0.60→0.63, MCC 0.855→0.866. *(근거: DUD-E 매칭, Geirhos 2020)*
9. **조합 고정 (23 업데이트):** 할로겐 매칭 후 재학습 시 grid 자동선택이 **지문-only 편향 조합**을 골라 GW-4064가 오히려 0.838로 상승 → **desc2d 포함 조합 고정**으로 편향 완화. *(근거: 도메인 시프트, Sahigara 2012)*
10. **재스크리닝(개선 모델):** GW-4064 **8위→67위**, 1위가 Circumdatin D(실제 천연물)로 교체. (단 top100 할로겐 51→48%로 편향 일부 잔존)
11. **정리:** notebooks/ → pipeline·legacy·docking 분리, data/ → raw·interim·processed·models·screening·reports·archive 분리(경로 자동수정), 근거 문서화.

---

## 7단계 — 현재 상태

**배포 모델** `data/models/HSD17B13_repr_ensemble.pkl`:
- 표현앙상블 5조합(고정): XGB×maccs, RF×rdkit, RF×desc2d, ET×desc2d, ET×topotorsion
- 학습셋: active 2049 + real_inactive 200 + **할로겐매칭 decoy 200**, class_weight 보정
- **지표(test):** MCC 0.866 · ROC-AUC 0.990 · PR-AUC 0.998 · Acc 0.965 · Recall 0.994 · Prec 0.965 · Brier 0.032
- **source별:** active 0.99 · decoy 1.00 · **real_inactive 0.63**
- **편향 프로브:** GW-4064 0.790 · Quercetin 0.340

**최종 천연물 후보 (검증됨, 16개):** Kibdelone류, Chondramide류, Fumiquinazoline M, Circumdatin D, Aspidosperma 알칼로이드 등. `data/screening/screen_repr_np_provenance.csv`.

**남은 한계 (미해결):**
- real_inactive 63% — activity cliff(비할로겐 사촌 구분)는 데이터 부족(real 200개)으로 한계.
- 합성 편향 부분 잔존(할로겐 외 여러 피처).
- 확률은 도메인 밖(천연물)에서 신뢰도 낮음.
- **→ 근본 검증은 도킹(PDB 8G89) 또는 효소 assay 필요.**

**다음 후보 작업:**
- 조합 선택을 "천연물다운 검증셋"으로 자동화(현재 고정의 정식 대체).
- 상위 천연물 후보 도킹 검증.
