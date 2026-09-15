# 모델링 설계 근거 — 레퍼런스 정리

HSD17B13 QSAR 파이프라인에서 (1) 앙상블 설계, (2) decoy/불균형 처리, (3) 2D·3D descriptor 활용에 대한 학술 근거.

---

## 1. 앙상블 / data fusion (표현 기반 결합)

- **Wolpert, D.H. (1992). "Stacked Generalization." *Neural Networks* 5(2):241–259.**
  스태킹의 원논문. 서로 다른(다양한) base learner의 출력을 메타 학습기로 결합하면 일반화 오차가 준다. 앙상블에서 **다양성(diversity)** 이 핵심임을 확립.
  - https://www.semanticscholar.org/paper/Original-Contribution:-Stacked-generalization-Wolpert/bbc25a700e51984e560eae27df1587baa92e3afe

- **Whittle, Gillet, Willett, Loesel (2006). "Analysis of Data Fusion Methods in Virtual Screening: Similarity and Group Fusion." *J. Chem. Inf. Model.* 46(6):2206–2219.**
  가상 스크리닝에서 서로 다른 지문/유사도 랭킹을 **data fusion**으로 결합하면 단일 최고 지문만큼 또는 그 이상으로 좋다. → 여러 fingerprint를 결합하는 근거.
  - https://pubs.acs.org/doi/10.1021/ci0496144 · https://pubmed.ncbi.nlm.nih.gov/17125165/

- **Hert, Willett et al. "New methods for ligand-based virtual screening: use of data fusion and machine learning to enhance the effectiveness of similarity searching."**
  다중 기준구조·다중 지문을 머신러닝+data fusion으로 결합. 우리가 하려는 "(모델×표현) 조합 선정 후 앙상블"의 직접적 배경.

- **Ginn, Willett, Bradshaw. "Combination of molecular similarity measures using data fusion."**
  서로 다른 유사도 측도를 합치는 fusion의 고전.

**요지:** 지문마다 담는 정보가 다르므로(ECFP=부분구조, MACCS=작용기, AtomPair=거리쌍…), 표현이 다른 base learner를 결합(late fusion)하는 것이 표준적이며 근거가 있다. 우리가 처음 한 "전 특징 concat 후 알고리즘 앙상블"(early fusion)도 흔한 방식이나, 지문별 기여를 분리 측정하지 못한다.

---

## 2. decoy 편향 / DUD-E / 불균형 처리

- **Mysinger, Carchia, Irwin, Shoichet (2012). "Directory of Useful Decoys, Enhanced (DUD-E): Better Ligands and Decoys for Better Benchmarking." *J. Med. Chem.* 55(14):6582–6594.**
  DUD-E 원논문. active당 50개 property-matched decoy를 ZINC에서, **토폴로지상 가장 다른(dissimilar) 25%만** 선택 → decoy가 active와 구조적으로 멀어짐(=쉬움).
  - https://pubs.acs.org/doi/10.1021/jm300687e · https://pubmed.ncbi.nlm.nih.gov/22716043/

- **Chen, Cruz, Ramsey, Dickson, Duca, Hornak, Koes, Kurtzman (2019). "Hidden Bias in the DUD-E Dataset Leads to Misleading Performance of Deep Learning in Structure-Based Virtual Screening." *PLOS ONE* 14(8):e0220113.**
  ★ 우리 문제의 직접 근거. CNN이 실제 물리(결합)를 배우는 게 아니라 DUD-E의 **analogue/decoy bias**를 배워 성능이 부풀려진다. decoy가 너무 쉬워 ML이 쉽게 구별 → 성능이 일반화가 아님을 실증.
  - https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0220113 · https://pubmed.ncbi.nlm.nih.gov/31430292/

- **Sieg, Flachsenberg, Rarey (2019). "In Need of Bias Control: Evaluating Chemical Data for Machine Learning in Structure-Based Virtual Screening." *J. Chem. Inf. Model.* 59(3):947–961.**
  DUD-E actives/decoys의 물성 차이만으로도 분류가 되어버리는 편향을 분석.

- **Class imbalance 처리 (cost-sensitive / ensemble):**
  - `class_weight='balanced'` (cost-sensitive learning): 소수 클래스 오분류에 큰 벌점 → 데이터 삭제·복제 없이 불균형 보정. active를 버리지 않고 처리하는 방법.
  - **BalancedRandomForest / EasyEnsemble / RUSBoost** (imbalanced-learn): 트리마다 다수 클래스를 언더샘플링해 앙상블 → 정보 손실 줄이며 불균형 강건.
  - **Chawla et al. (2002). "SMOTE: Synthetic Minority Over-sampling Technique." *JAIR* 16:321–357.** — 소수 클래스 합성. ⚠️ 이진 지문에는 보간이 비현실적 분자를 만들 수 있어 부적합.
  - **QSAR 맥락:** "QSAR Modeling of Imbalanced High-Throughput Screening Data in PubChem." *J. Chem. Inf. Model.* 2014. https://pubs.acs.org/doi/10.1021/ci400737s

**요지:** decoy는 실측 데이터가 아니라 **설계 변수**이므로 개수 조정이 정당하며, 쉬운 decoy가 지배하면 모델이 "합성물 감지기"가 된다(Chen 2019). 어려운 real inactive를 유지하고 decoy를 줄인 뒤 `class_weight`로 active를 보존한 채 불균형을 다루는 것이 근거 있는 조합.

---

## 3. 2D vs 3D descriptor

- **Bahia et al. (2023). "A Comparison between 2D and 3D Descriptors in QSAR Modeling Based on Bio-Active Conformations." *Molecular Informatics* 42.**
  3D descriptor는 **conformer(입체구조)에 의존**해 공정 비교가 어렵고, 2D 대비 성능 이득이 제한적(때로 2D가 우세). 다만 **2D+3D를 함께 쓰면** 상보적이라 더 나은 모델이 나온 경우가 많음.
  - https://onlinelibrary.wiley.com/doi/full/10.1002/minf.202200186 · https://pubmed.ncbi.nlm.nih.gov/36617991/

**요지:** 3D는 "반드시 추가하면 좋아지는" 것이 아니라 **검증 후 채택할 후보**로 다뤄야 한다. 그래서 표현 기반 앙상블에서 2D·3D를 각각 독립 표현으로 넣어 실제 기여를 측정하는 설계가 타당.

---

## 우리 파이프라인에 적용된 결론

1. **표현 기반 앙상블**(각 모델×지문/descriptor 조합 평가 → 상위 조합만 결합): Wolpert 스태킹 + Willett data fusion 계열 근거.
2. **decoy 축소 + real inactive 유지**: Chen 2019 / Sieg 2019의 decoy bias 경고에 대응.
3. **active 전부 유지 + class_weight**: cost-sensitive learning으로 불균형을 데이터 손실 없이 처리.
4. **2D·3D descriptor는 독립 표현으로 넣어 기여를 측정**: Bahia 2023 근거.
