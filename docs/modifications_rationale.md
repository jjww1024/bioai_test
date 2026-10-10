# 수정사항 근거·레퍼런스 (실제 시간순)

각 항목: **무엇을 / 왜 / 레퍼런스 / 레퍼런스 내용 / 참고한 부분**. (배포 모델 = `data/models/HSD17B13_repr_ensemble.pkl`)

---

## 08/01 — decoy 도입 (클래스 불균형 해소)
- **무엇을:** active만 있어 음성이 없으므로 가짜 음성(decoy)을 생성해 학습셋에 추가(`--add-decoys`, 초기엔 무작위/PubChem).
- **왜:** 분류 모델은 양성·음성이 둘 다 필요. active만으론 학습 불가.
- **레퍼런스:** Mysinger, Carchia, Irwin, Shoichet (2012) *Directory of Useful Decoys, Enhanced (DUD-E)*, J. Med. Chem. 55:6582.
- **내용:** active당 물성이 비슷하되 토폴로지는 다른 decoy를 생성하는 표준 방법.
- **참고한 부분:** "저해제가 없는 음성을 물성 매칭 decoy로 채운다"는 개념.

## 08/12 — descriptor 계산, DUD-E 매칭 decoy, 도킹 크기편향 보정
### (a) 2D descriptor(217종) 계산·학습
- **무엇을:** RDKit로 분자당 물리화학 descriptor 217종 계산해 학습에 사용.
- **왜:** 지문(부분구조)만으론 물성 정보가 빠짐. 상보적 표현 확보.
- **레퍼런스:** RDKit `Descriptors.CalcMolDescriptors`(표준 구현). / 개념: Todeschini & Consonni, *Molecular Descriptors for Cheminformatics*.
- **참고한 부분:** 표준 2D descriptor 집합.
### (b) 정식 DUD-E(active별 개별 매칭) decoy
- **무엇을:** 전역창 방식 → active 하나하나에 물성 매칭 decoy를 붙이는 DUD-E 정식 방식(06b)으로.
- **왜:** 전역 매칭은 active별 물성 차이를 반영 못 함.
- **레퍼런스:** Mysinger 2012 (DUD-E).
- **참고한 부분:** per-active 물성 매칭 + 토폴로지 상이 조건.
### (c) 도킹 Ligand Efficiency 보정
- **무엇을:** 도킹 점수(15)를 원자 수로 나눠(LE) 크기 편향 재랭킹.
- **왜:** 도킹 점수는 분자가 클수록 유리하게 나와, 큰 분자가 무조건 상위로 감.
- **레퍼런스:** Hopkins, Groom, Alex (2004) *Ligand efficiency: a useful metric for lead selection*, Drug Discovery Today 9:430.
- **내용:** 결합에너지를 중원자 수로 나눈 LE로 "원자당 효율"을 비교해 크기 편향 제거.
- **참고한 부분:** LE = −ΔG/heavy atoms 정의.

## 08/19~20 — DUD-E 전체 워크플로 + WEKA 특징선택 + 라벨 기준
### (a) 라벨 기준 (IC50 임계값)
- **무엇을:** IC50 **≤10,000 nM=active, ≥20,000 nM=inactive**, 사이(gray) 제거.
- **왜:** 경계값 근처는 활성/비활성이 모호 → 학습 노이즈. gray 제거로 신호 명확화. (10µM 컷은 사용자 지정)
- **레퍼런스:** 활성 임계값 관행(QSAR 분류에서 potency cutoff + 회색지대 제외).
- **참고한 부분:** 명확한 양/음성만 학습, 애매구간 배제.
### (b) WEKA로 2D descriptor 특징선택 (217→36)
- **무엇을:** 217개 descriptor 중 유효한 36개만 선택.
- **왜:** 고차원·중복 특징은 과적합·잡음↑(차원의 저주). 유효 특징만 남겨 일반화↑.
- **레퍼런스:** Guyon & Elisseeff (2003) *An Introduction to Variable and Feature Selection*, JMLR 3:1157.
- **내용:** 무관·중복 특징 제거가 성능·해석성을 높인다는 특징선택 개론.
- **참고한 부분:** 특징선택의 목적(중복·무관 제거).

## 08/24 — (문서화만) 전 노트북 초보용 주석. **모델 로직 변경 없음.**

## 09/08 — 지문 6종 확장, 3D descriptor, train/val/test 분할
### (a) fingerprint 6종으로 확장
- **무엇을:** 지문 1종 → **6종**(ECFP4·MACCS·RDKit·AtomPair·Avalon·TopologicalTorsion).
- **왜:** 지문마다 담는 정보가 다름(부분구조·작용기·원자쌍 거리 등). 여러 지문이 상보적.
- **레퍼런스:** Whittle, Gillet, Willett, Loesel (2006) *Analysis of Data Fusion Methods in Virtual Screening*, J. Chem. Inf. Model. 46:2206.
- **내용:** 서로 다른 지문/유사도를 결합(data fusion)하면 단일 최고만큼 또는 그 이상.
- **참고한 부분:** "지문마다 정보가 달라 결합이 이득."
### (b) 3D descriptor 생성
- **무엇을:** ETKDG conformer 생성 후 3D descriptor 11종 계산(09b).
- **왜:** 2D가 못 담는 입체 정보 후보로 검토.
- **레퍼런스:** Bahia 등 (2023) *A Comparison between 2D and 3D Descriptors in QSAR Modeling...*, Molecular Informatics.
- **내용:** 3D는 conformer 의존성이 커 2D 대비 이득이 제한적(때로 2D 우세) → "검증 후 채택".
- **참고한 부분:** 3D는 필수가 아니라 검증 대상. (→ 나중에 성능 약해 미채택)
### (c) train/validation/test 분할 (20a)
- **무엇을:** 기존 CV만 → 70/15/15 층화 분할.
- **왜:** 하이퍼파라미터/조합을 **val로 고르고** 최종성능은 **test로 한 번** 재야 공정. train 평가는 과적합 못 잡음, test로 고르면 오염.
- **레퍼런스:** Hastie, Tibshirani, Friedman, *The Elements of Statistical Learning*, ch.7.
- **참고한 부분:** train/val/test 역할 분리.

## 09/15 — ★ 핵심 개선: decoy 축소, concat→1대1 앙상블, class_weight, 후보필터
### (a) decoy 개수 축소 (→ real_inactive 수준)
- **무엇을:** decoy 1849 → 200(real_inactive 개수)으로 축소.
- **왜:** 쉬운 decoy(active와 Tanimoto ~0.2)가 90%를 차지 → 모델이 "합성물 감지기"가 되고 지표 부풀림. decoy는 실측이 아닌 설계 변수라 개수 조정 정당.
- **레퍼런스:** Chen 등 (2019) *Hidden Bias in the DUD-E Dataset...*, PLOS ONE 14:e0220113. / Wallach & Heifets (2018) *Most Ligand-Based Classification Benchmarks Reward Memorization...*, J. Chem. Inf. Model. 58:916.
- **내용:** Chen — 모델이 실제 결합이 아니라 decoy bias를 학습해 성능이 부풀려짐(실증). Wallach — train-val 유사도(AVE bias)가 성능과 강하게 상관 → "암기"를 보상.
- **참고한 부분:** "쉬운 decoy가 성능을 부풀린다"는 실증.

### (b) ★ 한번에 concat 학습 → 1대1 매칭(late fusion)  *(사용자 예시)*
- **무엇을:** 6지문+2D+3D를 한 벡터로 이어붙여 학습(early fusion) → **표현마다 모델을 따로 학습해 예측을 결합**(late fusion), 상위 조합만 soft-voting.
- **왜:** ① concat 시 지문 5287열이 descriptor 47열을 수적으로 압도 → descriptor 기여가 묻힘. ② 어느 표현이 유효한지 측정 불가. ③ 같은 입력을 본 모델들은 실수가 비슷해 앙상블 이득↓.
- **레퍼런스:**
  - Snoek, Worring, Smeulders (2005) *Early versus late fusion in semantic video analysis*, ACM Multimedia.
  - Wolpert (1992) *Stacked Generalization*, Neural Networks 5:241.
  - Ho (1998) *The Random Subspace Method for Constructing Decision Forests*, IEEE TPAMI 20:832.
- **내용:**
  - Snoek 2005: early(특징결합)는 교차상관을 학습하나 이질적 표현에 약함, late(예측결합)는 표현별 최적처리·확장성이 좋다는 비교.
  - Wolpert 1992: 서로 다른(다양한) base learner의 출력을 결합하면 일반화 오차 감소.
  - Ho 1998: 같은 알고리즘이라도 다른 특징 부분집합에 학습하면 다양성이 생겨 앙상블에 이득(같은 RF를 rdkit·desc2d에 각각 쓰는 근거).
- **참고한 부분:** Snoek의 late fusion 정의·장점(표현 분리 학습), Wolpert의 "다양성=앙상블 핵심", Ho의 "같은 모델×다른 표현" 정당성.

### (c) class_weight='balanced' (active 전부 유지)
- **무엇을:** active를 언더샘플링해 버리지 않고, 소수 클래스 오분류에 큰 벌점(비용민감)으로 불균형 보정. (XGB는 scale_pos_weight)
- **왜:** active 데이터가 적어 버리기 아까움. 언더샘플링은 정보 손실.
- **레퍼런스:** *QSAR Modeling of Imbalanced High-Throughput Screening Data in PubChem*, J. Chem. Inf. Model. 2014 (ci400737s).
- **내용:** 불균형 시 클래스 가중(빈도 역수)으로 소수 클래스를 무겁게 다뤄 데이터 손실 없이 보정.
- **참고한 부분:** 데이터 삭제 없이 가중으로 불균형 처리.

### (d) 후보 필터: NP-likeness (08c)
- **무엇을:** 스크리닝 후보에 천연물다움 점수를 매겨 할로겐 없는 합성 열거물까지 제거(243→59).
- **왜:** 구조지표(할로겐)만으론 안 걸리는 합성 조합화학물이 상위에 다수.
- **레퍼런스:** Ertl, Roggo, Schuffenhauer (2008) *Natural Product-likeness Score...*, J. Chem. Inf. Model. 48:68.
- **내용:** 천연물/합성물 부분구조 빈도 통계로 천연물다움 점수화(양수=천연물다움).
- **참고한 부분:** scoreMol 점수(GW-4064 −0.64로 검증).

### (e) 후보 필터: 출처·문헌 (08d)
- **무엇을:** COCONUT의 organisms/dois가 있는 후보만(59→16).
- **왜:** NP-likeness는 "생김새"만 봄. 실재 분리·보고 여부는 메타데이터로 확인.
- **레퍼런스:** Sorokina 등 (2021) *COCONUT online: Collection of Open Natural Products*, J. Cheminform. 13:2.
- **참고한 부분:** organisms/dois/chemical class 메타데이터.

## 09/22 — 평가지표 + 확률 보정
### (a) 평가지표: Accuracy 대신 MCC·PR-AUC
- **무엇을:** 주 지표를 MCC(그리고 PR-AUC)로.
- **왜:** 불균형에서 정확도는 다수만 찍어도 높아 오해를 줌. MCC는 혼동행렬 4칸 반영.
- **레퍼런스:** Matthews (1975) Biochim. Biophys. Acta 405:442. / Saito & Rehmsmeier (2015) PR-AUC 유용성, PLOS ONE 10:e0118432.
- **내용:** MCC = TP·TN·FP·FN 균형 상관계수(−1~+1). PR-AUC는 희귀 양성 탐지에 ROC보다 민감.
- **참고한 부분:** MCC 정의·불균형 강건성.
### (b) Platt 확률보정 + 임계값 튜닝 (23c, 분석)
- **무엇을:** 검증셋에서 확률을 시그모이드로 보정, MCC 최대 임계값 선택. (배포 모델엔 미탑재)
- **왜:** 중간대(0.4~0.6) 확률이 실제 비율과 어긋나 신뢰 불가.
- **레퍼런스:** Platt (1999) *Probabilistic Outputs for SVMs*. / Niculescu-Mizil & Caruana (2005) *Predicting Good Probabilities...*, ICML.
- **내용:** 예측점수→확률 매핑 시그모이드(Platt); held-out Brier로 검증.
- **참고한 부분:** Platt 보정 + held-out 검증(Brier 0.031→0.028, 개선 미미).

## 09/23 — CV 학습곡선 + 할로겐 매칭
### (a) 학습곡선을 5-fold CV + 음영으로
- **무엇을:** 단일 측정 → 5-fold CV 평균±표준편차(음영).
- **왜:** 단일 분할은 운(분산)에 좌우. CV로 안정적 추정 + 불확실성 표시.
- **레퍼런스:** ESL ch.7 (CV).
- **참고한 부분:** k-fold 반복 평가로 평균·분산.
### (b) ★ decoy 할로겐 매칭 (real_inactive 보존)
- **무엇을:** decoy 할로겐 비율을 active(89%)에 맞춰 재선택(56%→88%). real_inactive는 안 건드림.
- **왜:** active 89%가 할로겐 vs decoy 56% → 모델이 "할로겐=active" 지름길 학습(fr_halogen 상위, GW-4064 오탐). 그러나 비할로겐 active도 IC50 중앙값 동일(300nM) → 할로겐은 결합에 비인과(ADME용). 양쪽 비율을 맞추면 할로겐이 구별 단서가 못 됨.
- **레퍼런스:** Mysinger 2012 (DUD-E 물성 매칭) / Geirhos 등 (2020) *Shortcut Learning in Deep Neural Networks*, Nature Machine Intelligence 2:665.
- **내용:** DUD-E — decoy를 active 물성에 매칭해 그 속성이 분류 단서가 못 되게. Geirhos — 모델은 의도한 특징 대신 데이터의 지름길(spurious feature)을 학습; 하나 막으면 다른 지름길로.
- **참고한 부분:** DUD-E "매칭으로 속성 중립화", Geirhos "shortcut learning". 결과: GW-4064 스크리닝 8위→67위.

## 09/28 — desc2d 조합 고정
- **무엇을:** val MCC 상위 자동선택 대신 desc2d 포함 5조합 고정(XGB×maccs, RF×rdkit, RF×desc2d, ET×desc2d, ET×topotorsion).
- **왜:** 할로겐 매칭 후 자동선택은 합성 검증셋 MCC로 골라 **지문-only(합성 편향) 조합**을 택함(GW-4064 0.838 상승). 2D descriptor(부분전하·작용기)는 도메인 전이가 잘 되는 일반 특성이라, 포함하면 편향 완화(GW-4064↓, real_inactive↑, MCC↑).
- **레퍼런스:** Geirhos 2020 (shortcut learning) / Sahigara 등 (2012) *Comparison of Different Approaches to Define the Applicability Domain of QSAR Models*, Molecules 17:4791.
- **내용:** 검증 지표가 배포 도메인(천연물)을 대표 못 하면 "검증 1등"이 목표엔 최선이 아님(도메인 시프트). Sahigara — 예측 대상이 학습 화학공간 밖이면 신뢰도 낮음.
- **참고한 부분:** 도메인 시프트 시 지표-목표 불일치. **주의:** 프로브 2개에 기댄 임시 휴리스틱(정석은 천연물 검증셋으로 자동선택 — 향후).

## 10/10 — 데이터 재수집 + PubChem 3번째 소스 + 전 파이프라인 재실행

### (a) PubChem BioAssay를 3번째 데이터 소스로 추가
- **무엇을:** UniProt Q7Z5P4 관련 PubChem AID 34건에서 IC50 레코드 2,812건(고유 CID 2,422) 수집 → 노트북 01에서 BindingDB·ChEMBL과 병합. 고유 물질 2,686 → 3,253, active 2,049 → 2,759.
- **왜:** HSD17B13 공개 활성 데이터가 절대적으로 부족(active 2,049 / real_inactive 200). BindingDB·ChEMBL만으로는 특허 유래 데이터 상당수가 누락됨. 데이터 양 자체가 QSAR 성능의 1차 제약.
- **레퍼런스:** Kim 등 (2023) *PubChem 2023 update*, Nucleic Acids Research 51:D1373. / Tetko 등 (2016) *BigChem: Challenges and Opportunities for Big Data Analysis in Chemistry*, Molecular Informatics 35:615.
- **내용:** PubChem BioAssay는 ChEMBL·특허(SureChEMBL)·문헌을 통합 색인하며, assay별 `activity_outcome_method`(1=Screening, 2=Confirmatory)로 품질을 구분 제공. BigChem — 공개 데이터 통합 시 소스별 단위·품질 정규화가 필수.
- **참고한 부분:** ① `activity_outcome_method=2`(확정시험)만 사실상 수집되어 HTS 단일농도 잡음이 아님을 확인 ② **단위 정규화**: PubChem `IC50` 컬럼=NANOMOLAR, `PubChem Standard Value`=MICROMOLAR (헤더 설명행에서 확인) — 처음 전부 µM로 읽어 1,000배 부풀려진 것을 바로잡음.

### (b) ChEMBL 구분자 자동판별 (`sniff_sep`)
- **무엇을:** ChEMBL 내보내기 파일의 구분자를 헤더 첫 줄에서 `;` / tab / `,` 중 최다 출현 문자로 판별.
- **왜:** ChEMBL 웹 내보내기는 다운로드 시점·브라우저 로케일에 따라 구분자가 바뀜(2026-08본=tab, 2026-10본=`;`). 하드코딩하면 재다운로드마다 깨짐.
- **레퍼런스:** 없음(엔지니어링 수정). 실측: `261010 Chembl ... .csv`는 `;`, 기존 `chembl_hsd17b13.tsv`는 tab, **내용은 동일**.

### (c) 노트북 17 `REUSE_CLEAN` 모드 (decoy 재검증)
- **무엇을:** 원시 DUD-E `.picked`를 다시 파싱하지 않고, 기존 `decoys_clean.csv`를 **새 active 기준으로만 재검증**(active/inactive InChIKey 겹침 제거 + ECFP4 Tanimoto 재계산 ≤0.35). 121,992 → 121,952 (40개 제거).
- **왜:** active가 710개 늘었으므로 기존 decoy 중 일부가 (i) 새 active와 동일 물질이거나 (ii) 유사도 상한을 넘을 수 있음 → 라벨 오염·analogue bias. 반면 원시 decoy 풀 자체는 변하지 않았으므로 전체 재파싱은 불필요.
- **레퍼런스:** Mysinger 등 (2012) *Directory of Useful Decoys, Enhanced (DUD-E)*, J. Med. Chem. 55:6582. / Sieg, Flachsenberg, Rarey (2019) *In Need of Bias Control: Evaluating Chemical Data for Machine Learning in Structure-Based Virtual Screening*, JCIM 59:947.
- **내용:** DUD-E — decoy는 active와 물성은 비슷하되 **구조(토폴로지)는 달라야** 함. Sieg — active와 구조가 겹치는 decoy는 성능을 허위로 부풀리는 analogue bias의 직접 원인.
- **참고한 부분:** "decoy는 active와 구조적으로 충분히 달라야 한다"는 요건을 **active 집합이 바뀔 때마다 재확인**해야 한다는 점.
- **결론:** 신규 DUD-E 제출 **불필요** — 재균형 설계가 decoy를 real_inactive 개수(210)만큼만 쓰므로 121,952개 풀로 충분.

### (d) 2D descriptor 선택 목록(36개) 동결
- **무엇을:** 데이터가 늘었지만 WEKA 특징선택을 다시 돌리지 않고 기존 36개 목록을 그대로 사용(노트북 19는 `nrows=0`으로 **컬럼명만** 읽음).
- **왜:** 새 데이터로 재선택하면 09/28에 정한 "desc2d 포함 조합 고정" 전제가 깨지고, 모델 간 비교(0.866 vs 0.892)가 특징선택 변화와 데이터 증가 중 무엇 때문인지 분리 불가.
- **레퍼런스:** Guyon & Elisseeff (2003) *An Introduction to Variable and Feature Selection*, JMLR 3:1157. / Ambroise & McLachlan (2002) *Selection bias in gene extraction on the basis of microarray gene-expression data*, PNAS 99:6562.
- **내용:** Ambroise & McLachlan — 특징선택을 평가 루프 안에서 반복하면 선택 편향(selection bias)으로 성능이 낙관적으로 추정됨.
- **참고한 부분:** 특징선택을 고정해 두는 것이 변경 효과를 정직하게 비교하는 조건.

### (e) 프로브 화합물 3종 자동 점검 셀 (23b)
- **무엇을:** 매 평가 시 GW-4064(합성 FXR 작용제, 낮아야 좋음) / Quercetin(식물 플라보노이드) / α-Terthienyl(메리골드 유래, HSD17B13 저해 보고 → 높아야 좋음) 확률을 자동 출력·저장.
- **왜:** 내부 지표(MCC·ROC)는 학습 화학공간 안에서만 측정되어 **합성 편향 악화를 못 잡는다**. 실제로 이번 재학습에서 MCC는 0.866→0.892로 올랐으나 GW-4064는 0.790→0.900으로 악화 — 고정 프로브 없이는 놓쳤을 신호.
- **레퍼런스:** Sahigara 등 (2012) *Comparison of Different Approaches to Define the Applicability Domain of QSAR Models*, Molecules 17:4791. / Geirhos 등 (2020) *Shortcut Learning in Deep Neural Networks*, Nature Machine Intelligence 2:665.
- **내용:** Sahigara — 학습 화학공간 밖 예측은 신뢰도가 별도로 평가돼야 함(적용영역). Geirhos — 분포 내 지표가 좋아도 분포 밖(out-of-distribution) 테스트에서 지름길 학습이 드러남.
- **참고한 부분:** **분포 밖 고정 테스트 세트**를 상시 유지하라는 원칙. 프로브 3종이 최소 버전.

### (f) IC50 측정값 충돌(>100배) 물질 제외
- **무엇을:** `03_robust_dedup`이 `confidence == 'CONFLICT (>100x)'`로 판정한 물질(같은 구조인데 보고된 IC50이 100배 이상 갈리는 것)을 노트북 17 커레이션에서 **active/inactive 어느 쪽으로도 넣지 않고 제외**. 예: `US20250340546, Example 26` 8,095배 / `CHEMBL5411903` 2,260배 차이.
  - 03은 원래 `recommend_keep=False`로 표시만 했고 17은 이 플래그를 쓰지 않아 **18건 전부 active로 학습에 들어가 있었음** → 이번에 실제로 끊어냄.
  - 비교는 염·호변이성질체 차이를 흡수하려고 InChIKey 기준(`clean()` 통과 후)으로 수행.
- **왜:** 어느 값이 맞는지 알 수 없는 물질은 **라벨 자체가 미지**다. 임계값(10µM/20µM) 어느 쪽에 놓느냐로 active↔inactive가 뒤집히므로, 넣으면 라벨 노이즈를 주입하는 것과 같다. 공개 활성 데이터의 정상적인 assay 간 편차는 **0.5 log(약 3배)** 수준이고, 100배(2 log)는 그 범위를 한참 넘어 **서로 다른 assay를 섞었거나 기록 오류**임을 뜻한다.
- **레퍼런스:**
  - Kalliokoski, Kramer, Vulpetti, Gedeck (2013) *Comparability of Mixed IC50 Data — A Statistical Analysis*, PLOS ONE 8:e61007.
  - Kramer, Kalliokoski, Gedeck, Vulpetti (2012) *The Experimental Uncertainty of Heterogeneous Public Ki Data*, J. Med. Chem. 55:5165.
  - Fourches, Muratov, Tropsha (2010) *Trust, But Verify: On the Importance of Chemical Structure Curation in Cheminformatics and QSAR Modeling Research*, JCIM 50:1189.
- **내용:** Kalliokoski — ChEMBL의 서로 다른 assay에서 측정된 동일 물질 IC50의 표준편차는 약 0.5 log 단위이며, 이보다 크게 벌어지면 assay가 비교 불가능한 것. Kramer — 공개 Ki 데이터의 평균 오차는 0.44 log 단위. Fourches — 모순되는(contradictory) 레코드는 QSAR 학습 전 큐레이션 단계에서 **제거**가 표준 절차.
- **참고한 부분:** ① "정상 편차 ≈0.5 log" 기준 → 100배(2 log) 충돌은 노이즈로 간주 ② Fourches의 "모순 레코드 제거" 큐레이션 원칙을 커레이션 코드에 반영.

### (g) 파일명 YYMMDD 스탬프 도입
- **무엇을:** 파이프라인이 만드는 모든 파일에 생성일 접두사(`261010_...`). 노트북은 경로를 직접 적지 않고 `notebooks/pipeline/_paths.py`의 `out()`(쓰기=오늘 스탬프) / `latest()`(읽기=최신 스탬프 자동선택)을 사용. `STAMP` 한 줄로 전 파이프라인 전환.
- **왜:** 같은 이름으로 덮어쓰면 "이 파일이 어느 실행 결과인지" 파일명으로 알 수 없고, 구버전과 신버전이 섞이면 어떤 모델이 어떤 데이터로 학습됐는지 추적 불가(09/28에 실제로 겪은 문제 — 배포 pkl과 노트북이 불일치).
- **레퍼런스:** Sandve, Nekrutenko, Taylor, Hovig (2013) *Ten Simple Rules for Reproducible Computational Research*, PLOS Computational Biology 9:e1003285.
- **내용:** Rule 3 "모든 중간 결과를 보관하라", Rule 4 "버전 관리로 결과와 그것을 만든 코드를 연결하라".
- **참고한 부분:** 중간 산출물을 덮어쓰지 않고 날짜로 보존 → 결과·코드·데이터의 대응관계 추적 가능. 예외: `raw/`(외부 원본)와 WEKA 수동 선택본은 무스탬프 유지.

### (h) 결과 요약 — 개선과 대가
**3단계 지표 변화**

| | 09/28 구모델 | 10/10 데이터확장 | 10/10 +충돌제외(현재) |
|---|---|---|---|
| 학습셋 | 2049+200+200 | 2759+210+210 | **2741+210+210** |
| MCC | 0.866 | 0.892 | **0.908** |
| ROC / PR | 0.990 / 0.998 | 0.989 / 0.998 | **0.993 / 0.999** |
| Brier | 0.032 | 0.026 | **0.021** |
| active recall | 0.994 | 0.983 | **0.988** |
| decoy | 1.000 | 1.000 | 0.969 |
| **real_inactive** | **0.63** | 0.839 | **0.871** |
| GW-4064 (낮아야 좋음) | 0.790 | 0.900 | 0.854 |
| Quercetin | 0.340 | 0.375 | 0.428 |
| α-Terthienyl (높아야 좋음) | 0.096 | 0.120 | 0.158 |

- **데이터 확장(b~e)의 대가:** 신규 active 710개가 **할로겐 99% / NP≥1 0개**(전부 제약사 특허 합성 시리즈) → 전체 active 할로겐율 89%→91%, NP 중앙값 −1.09→−0.99. **GW-4064 0.790→0.900**으로 위양성 악화.
- **충돌 제외(f)의 효과:** 내부 지표(MCC 0.892→0.908)와 **프로브를 동시에** 개선(GW-4064 0.900→0.854, α-Terthienyl 0.120→0.158). 라벨 노이즈 제거가 양쪽에 다 이득.
- **남은 문제:** 그래도 GW-4064는 **출발점 0.790보다 나쁨**. 공개 데이터를 더 모아도 전부 같은 합성 계열이라 **천연물 도메인 외삽은 개선되지 않음**. 근본 해법은 (i) 천연물 쪽 실측 라벨 확보 또는 (ii) 구조 기반 도킹(8G9V/YYC) 교차검증.

---

## 시간순 요약 표

| 날짜 | 수정 | 핵심 레퍼런스 |
|---|---|---|
| 08/01 | decoy 도입 | Mysinger 2012 (DUD-E) |
| 08/12 | descriptor·DUD-E매칭·LE보정 | Mysinger 2012, Hopkins 2004 |
| 08/19 | 라벨 임계값·WEKA 특징선택 | Guyon 2003 |
| 09/08 | 지문6종·3D·train/val/test | Willett 2006, Bahia 2023, ESL |
| 09/15 | decoy축소·**concat→1대1**·class_weight·NP/출처필터 | Chen 2019, **Snoek 2005·Wolpert 1992·Ho 1998**, Ertl 2008 |
| 09/22 | MCC·PR-AUC·보정 | Matthews 1975, Platt 1999 |
| 09/23 | CV곡선·**할로겐매칭** | ESL, **Geirhos 2020**·DUD-E |
| 09/28 | **desc2d 조합 고정** | Geirhos 2020, Sahigara 2012 |
| 10/10 | **PubChem 3소스 추가**·단위정규화·decoy 재검증·특징선택 동결·프로브 상시화·**IC50 충돌 제외**·파일명 스탬프 | **Kim 2023 (PubChem)**, Tetko 2016, Sieg 2019, Ambroise 2002, Sahigara 2012, **Kalliokoski 2013·Fourches 2010**, Sandve 2013 |
