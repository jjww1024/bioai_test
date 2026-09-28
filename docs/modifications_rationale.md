# 모델 수정사항 — 근거·레퍼런스 정리

각 수정에 대해: **무엇을 / 왜 / 레퍼런스 / 레퍼런스 내용 / 참고한 부분**. (배포 모델 = `data/models/HSD17B13_repr_ensemble.pkl`)

---

## 1. Decoy 생성 (클래스 불균형 해결)
- **무엇을:** active(~2049)만 있어 음성이 없으므로, 물성 매칭 가짜 음성(decoy)을 생성해 학습셋에 추가.
- **왜:** 분류 모델은 양성·음성이 둘 다 필요. active만으론 학습 불가.
- **레퍼런스:** Mysinger, Carchia, Irwin, Shoichet (2012) *Directory of Useful Decoys, Enhanced (DUD-E)*, J. Med. Chem. 55:6582.
- **내용:** active당 물성(MW·logP·HBD·HBA·회전결합·전하)이 비슷하되 토폴로지는 다른 decoy를 ZINC에서 생성하는 표준 방법·도구.
- **참고한 부분:** 물성 매칭 + 토폴로지 상이 decoy 생성 절차. 우리는 DUD-E 웹툴로 active를 넣어 decoy 생성.

## 2. 앙상블 방식: "한번에 concat 학습" → "1대1 매칭 후 상위조합 결합"
- **무엇을:** 6지문+2D+3D를 한 벡터로 이어붙여 학습(early fusion) → **표현마다 모델을 따로 학습해 예측을 결합**(late fusion)으로 변경.
- **왜:** (1) concat 시 지문(5287열)이 descriptor(47열)를 수적으로 압도해 descriptor 기여가 묻힘. (2) 어느 표현이 유효한지 측정 불가. (3) 같은 입력을 본 모델들은 실수가 비슷해 앙상블 이득↓.
- **레퍼런스:**
  - Snoek, Worring, Smeulders (2005) *Early versus late fusion in semantic video analysis*, ACM Multimedia.
  - Wolpert (1992) *Stacked Generalization*, Neural Networks 5:241.
  - Whittle, Gillet, Willett, Loesel (2006) *Analysis of Data Fusion Methods in Virtual Screening*, J. Chem. Inf. Model. 46:2206.
- **내용:**
  - Snoek 2005: early fusion(특징결합)은 교차상관을 학습하나 이질적 표현에 약하고, late fusion(예측결합)은 표현별 최적처리·확장성이 좋다는 비교.
  - Wolpert 1992: 서로 다른(다양한) base learner의 출력을 결합하면 일반화 오차 감소.
  - Willett 2006: 가상 스크리닝에서 서로 다른 지문/유사도를 data fusion으로 결합하면 단일 최고만큼 또는 그 이상.
- **참고한 부분:** Snoek의 late fusion 정의·장점(표현별 분리 학습), Wolpert의 "다양성이 앙상블 성능의 핵심", Willett의 "지문 결합 이득".

## 3. 같은 알고리즘을 다른 표현에 중복 사용 (RF×rdkit + RF×desc2d 등)
- **무엇을:** 상위 조합에 같은 모델(RF·ET)이 서로 다른 표현으로 2번 들어가는 것을 허용.
- **왜:** 앙상블은 알고리즘 정체가 아니라 **예측의 다양성**을 봄. 같은 RF라도 입력이 다르면 다른 예측 → 다양성 확보.
- **레퍼런스:** Ho (1998) *The Random Subspace Method for Constructing Decision Forests*, IEEE TPAMI 20:832. / Kuncheva & Whitaker (2003) *Measures of diversity in classifier ensembles*, Machine Learning 51:181.
- **내용:** Ho — 같은 결정트리를 **서로 다른 특징 부분집합**에 학습시켜 앙상블(Random Forest의 기반 원리). Kuncheva — 다양성 지표가 앙상블 성능과 연결.
- **참고한 부분:** "같은 알고리즘 × 다른 특징 부분집합" 조합의 정당성·이득.

## 4. class_weight='balanced' (active 전부 유지한 채 불균형 처리)
- **무엇을:** active를 언더샘플링해 버리지 않고, 소수 클래스 오분류에 큰 벌점(비용민감 학습)으로 불균형 보정. (XGB는 scale_pos_weight)
- **왜:** active 데이터가 적어 버리기 아까움. 언더샘플링은 정보 손실.
- **레퍼런스:** 비용민감 학습(cost-sensitive learning) 일반론 / QSAR 맥락: *QSAR Modeling of Imbalanced High-Throughput Screening Data in PubChem*, J. Chem. Inf. Model. 2014 (ci400737s).
- **내용:** 불균형 시 클래스 가중(빈도 역수)으로 소수 클래스를 무겁게 다뤄 데이터 손실 없이 보정. 언더/오버샘플링 대안.
- **참고한 부분:** 데이터 삭제 없이 가중으로 불균형 처리하는 접근.

## 5. train/validation/test 분할 + 5-fold 교차검증
- **무엇을:** 데이터를 train(70)/val(15)/test(15)로 층화 분할. 조합·하이퍼파라미터는 val로 고르고, 최종 성능은 test로 한 번. 학습곡선은 5-fold CV로 평가.
- **왜:** train에서 평가하면 과적합을 못 잡음. test로 모델을 고르면 test가 오염됨. CV는 단일 분할의 운(분산)을 줄임.
- **레퍼런스:** 표준 ML 관행 (Hastie, Tibshirani, Friedman, *The Elements of Statistical Learning*, ch.7 — 모델 평가·선택, CV).
- **내용:** 일반화 오차 추정을 위해 데이터를 분리하고 CV로 분산을 낮추는 표준 절차.
- **참고한 부분:** train/val/test 역할 분리, k-fold CV 평균±표준편차.

## 6. 평가지표: Accuracy 대신 MCC·PR-AUC 중심
- **무엇을:** 불균형 데이터라 정확도 대신 MCC(그리고 PR-AUC)를 주 지표로.
- **왜:** 불균형에서 정확도는 다수 클래스만 찍어도 높게 나와 오해를 줌. MCC는 혼동행렬 4칸을 모두 반영.
- **레퍼런스:** Matthews (1975) *Comparison of the predicted and observed secondary structure of T4 phage lysozyme*, Biochim. Biophys. Acta 405:442. / Saito & Rehmsmeier (2015) PR-AUC 유용성, PLOS ONE.
- **내용:** MCC = TP·TN·FP·FN 균형 상관계수(−1~+1). PR-AUC는 희귀 양성 탐지 평가에 ROC보다 민감.
- **참고한 부분:** MCC 정의·불균형 강건성.

## 7. Decoy 개수를 real_inactive에 맞춰 축소
- **무엇을:** decoy 1849 → 200(real_inactive 개수)으로 축소. 쉬운 decoy 지배 완화.
- **왜:** 쉬운 decoy(active와 Tanimoto ~0.2)가 90%를 차지해 모델이 "합성물 감지기"로 학습되고 지표가 부풀려짐. decoy는 실측이 아니라 설계 변수라 개수 조정 정당.
- **레퍼런스:** Chen 등 (2019) *Hidden Bias in the DUD-E Dataset...*, PLOS ONE 14:e0220113. / Sieg, Flachsenberg, Rarey (2019) *In Need of Bias Control...*, J. Chem. Inf. Model. 59:947. / Wallach & Heifets (2018) *Most Ligand-Based Classification Benchmarks Reward Memorization Rather than Generalization*, J. Chem. Inf. Model. 58:916.
- **내용:**
  - Chen 2019: 모델이 실제 결합이 아니라 DUD-E의 analogue/decoy bias를 학습해 성능이 부풀려짐을 실증.
  - Sieg 2019: active/decoy의 물성 차이만으로 분류가 되는 편향 분석.
  - Wallach 2018: train-val 유사도(AVE bias)가 성능과 강하게 상관 → "암기"를 보상.
- **참고한 부분:** "쉬운 decoy가 성능을 부풀린다"는 실증(Chen), decoy 편향 개념.

## 8. Decoy 할로겐 매칭 (real_inactive 보존)
- **무엇을:** decoy의 할로겐 비율을 active(89%)에 맞춰 재선택(원래 56% → 88%). real_inactive는 안 건드림.
- **왜:** active 89%가 할로겐인데 decoy는 56%뿐 → 모델이 "할로겐=active" 지름길 학습(fr_halogen 상위 변수, GW-4064 오탐). 그런데 할로겐 없는 active도 IC50 중앙값 동일(300 nM) → 할로겐은 결합에 인과적이지 않고 약물 최적화(ADME)용. 즉 상관을 인과로 착각한 편향. 양쪽 할로겐 비율을 맞추면 할로겐이 구별 단서가 못 됨(DUD-E 물성 매칭 원리의 확장).
- **레퍼런스:** Mysinger 2012 (DUD-E 물성 매칭) / Geirhos 등 (2020) *Shortcut Learning in Deep Neural Networks*, Nature Machine Intelligence 2:665 / Chen 2019, Sieg 2019.
- **내용:** DUD-E — decoy를 active 물성에 매칭해 그 물성이 분류 단서가 못 되게. Geirhos — 모델은 의도한 특징 대신 데이터의 지름길(spurious feature)을 학습; 지름길 하나 막으면 다른 지름길로 감.
- **참고한 부분:** DUD-E의 "매칭으로 특정 속성을 중립화", Geirhos의 shortcut learning 개념. 결과: GW-4064 스크리닝 순위 8위→67위.

## 9. 앙상블 조합: 자동선택 → desc2d 포함 조합 고정
- **무엇을:** val MCC 상위 자동선택 대신 desc2d 포함 5조합 고정(XGB×maccs, RF×rdkit, RF×desc2d, ET×desc2d, ET×topotorsion).
- **왜:** 자동선택은 합성 검증셋 MCC로 골라 **지문-only(합성 편향) 조합**을 택함(GW-4064 0.838로 상승). 2D descriptor는 부분전하·작용기 등 도메인 전이가 잘 되는 일반 특성이라, 포함하면 합성 편향 완화(GW-4064↓, real_inactive↑, MCC↑).
- **레퍼런스:** Geirhos 2020 (shortcut learning) / 적용범위(Applicability Domain): Sahigara 등 (2012) *Comparison of Different Approaches to Define the Applicability Domain of QSAR Models*, Molecules 17:4791.
- **내용:** 검증 지표가 배포 도메인(천연물)을 대표하지 못하면 "검증 1등"이 목표엔 최선이 아님(도메인 시프트). Sahigara — 예측 대상이 학습 화학공간 밖이면 신뢰도가 낮음.
- **참고한 부분:** 도메인 시프트 시 지표-목표 불일치. **주의:** 이는 프로브 2개(GW-4064, Quercetin)에 기댄 임시 휴리스틱. 정석은 천연물다운 검증셋으로 조합을 자동선택(향후 과제).

## 10. (분석) 확률 보정(Platt) + 임계값 튜닝
- **무엇을:** 앙상블 확률을 검증셋에서 시그모이드로 보정하고, MCC 최대 임계값 선택. (실험/분석 단계 — 배포 모델엔 미탑재)
- **왜:** 중간대(0.4~0.6) 확률이 실제 비율과 어긋나 신뢰 불가.
- **레퍼런스:** Platt (1999) *Probabilistic Outputs for SVMs...* / Niculescu-Mizil & Caruana (2005) *Predicting Good Probabilities with Supervised Learning*, ICML.
- **내용:** 예측 점수→확률로 매핑하는 시그모이드(Platt)/등순위(isotonic) 보정. held-out에서 Brier로 검증.
- **참고한 부분:** Platt 시그모이드 보정 + held-out 검증(Brier 0.031→0.028).

## 11. 후보 필터: NP-likeness (합성 열거물 제거)
- **무엇을:** 스크리닝 후보에 천연물다움 점수를 매겨 할로겐 없는 합성 조합화학물까지 제거.
- **레퍼런스:** Ertl, Roggo, Schuffenhauer (2008) *Natural Product-likeness Score...*, J. Chem. Inf. Model. 48:68.
- **내용:** 천연물/합성물 부분구조 빈도 통계로 "천연물다움"을 점수화(양수=천연물다움).
- **참고한 부분:** scoreMol 점수로 후보 필터(GW-4064 −0.64로 검증).

## 12. 후보 필터: 출처·문헌(provenance)
- **무엇을:** COCONUT의 organisms/dois가 있는 후보만 남겨 실재 검증 천연물로 압축(59→16).
- **왜:** NP-likeness는 "생김새"만 봄. 실제 분리·보고 여부는 메타데이터로 확인해야.
- **레퍼런스:** COCONUT DB (Sorokina 등 2021, *COCONUT online: Collection of Open Natural Products*, J. Cheminform. 13:2).
- **참고한 부분:** organisms/dois/chemical class 메타데이터.

## 13. 3D descriptor: 생성했으나 배포 모델에서 제외
- **무엇을:** 3D descriptor를 만들되(09b), 단독 성능이 약해(val MCC 0.29) 앙상블 조합에 미채택.
- **레퍼런스:** Bahia 등 (2023) *A Comparison between 2D and 3D Descriptors in QSAR Modeling...*, Molecular Informatics.
- **내용:** 3D는 conformer 의존성이 커 2D 대비 이득이 제한적(때로 2D 우세).
- **참고한 부분:** "3D는 검증 후 채택할 후보" — 검증 결과 미채택.

---

## 요약 표

| # | 수정 | 핵심 레퍼런스 |
|---|---|---|
| 1 | decoy 생성 | Mysinger 2012 (DUD-E) |
| 2 | concat→1대1(late fusion) | Snoek 2005, Wolpert 1992, Willett 2006 |
| 3 | 같은 모델×다른 표현 허용 | Ho 1998, Kuncheva 2003 |
| 4 | class_weight | 비용민감학습, JCIM 2014 |
| 5 | train/val/test+CV | ESL ch.7 |
| 6 | MCC·PR-AUC | Matthews 1975, Saito 2015 |
| 7 | decoy 축소 | Chen 2019, Sieg 2019, Wallach 2018 |
| 8 | 할로겐 매칭 | DUD-E, Geirhos 2020 |
| 9 | desc2d 조합 고정 | Geirhos 2020, Sahigara 2012 |
| 10 | 보정+임계값 | Platt 1999, Niculescu-Mizil 2005 |
| 11 | NP-likeness 필터 | Ertl 2008 |
| 12 | 출처 필터 | COCONUT (Sorokina 2021) |
| 13 | 3D 제외 | Bahia 2023 |
