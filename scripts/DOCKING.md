# HSD17B13 도킹 검증 프로토콜

NPASS 스크리닝 상위 후보(ML 예측)를 **실제 단백질 포켓에 도킹**해 결합 가능성을
구조적으로 검증한다. ML은 학습 화학공간 밖(천연물)에서 **외삽**이라 신뢰가 낮으므로,
물리 기반 도킹으로 **독립 검증**하는 것이 목적.

## 0. 준비된 입력 (12_prep_docking.py 산출)

- `data/docking/hsd17b13_ligands.sdf` — 상위 후보 33개(prob≥0.7)의 3D 최소화 구조
- `data/docking/docking_manifest.csv` — prob·유사도·MW·logP·회전결합수·유연성 경고

## 1. 수용체 구조 (실험 구조 존재)

HSD17B13 (UniProt **Q7Z5P4**)의 첫 결정구조가 2023년 공개됨 (Nat. Commun.):

| PDB | 내용 | 용도 |
|-----|------|------|
| **8G89** | HSD17B13 + NAD⁺ 보조인자 + **저해제** | ★ 도킹 권장 — 포켓·리간드 좌표 정의됨 |
| 8G84 | HSD17B13 복합체 | 대체 |
| 8G9V | HSD17B13 | apo/참고 |

- 백업: AlphaFold 모델 `AF-Q7Z5P4` (https://alphafold.ebi.ac.uk/entry/Q7Z5P4) — 실험구조 있으니 실험구조 우선.
- **주의: HSD17B13은 NAD⁺ 의존 탈수소효소** → 보조인자 NAD⁺를 수용체에 포함(또는 포켓 정의에 반영)해야 결합이 현실적.

## 2. 수용체 준비

1. RCSB에서 8G89 다운로드 (`wget https://files.rcsb.org/download/8G89.pdb`).
2. 물 분자 제거, 필요시 여분 체인 제거. **NAD⁺는 유지**(리간드 포켓의 일부).
3. 수소 첨가 + 부분전하 → PDBQT 변환 (ADFR suite `prepare_receptor` 또는 Meeko).
4. **결합 포켓 = 공결정 저해제 좌표 중심** (8G89의 리간드 위치로 grid box 지정). 이게 검증된 포켓.

## 3. 리간드 준비

- `hsd17b13_ligands.sdf` → 각 분자 PDBQT 변환 (OpenBabel `obabel -isdf -opdbqt`, 또는 Meeko `mk_prepare_ligand`).
- 회전결합 >10 (매니페스트 `flexible_warn=True`)인 4개는 도킹 신뢰 낮음 → 결과 해석 시 주의.

## 4. 대조군 (설정 검증에 필수)

- **양성 대조 — redocking:** 8G89의 공결정 저해제를 빼서 다시 도킹 → 원래 포즈를 재현하면(RMSD < 2 Å) 도킹 셋업이 유효.
- **양성 대조 — 알려진 저해제:** **BI-3231**(검증된 HSD17B13 저해제 chemical probe)을 도킹 → 우리 후보 점수의 기준선.
- **음성 대조:** 무작위 drug-like 분자 몇 개 → 후보가 이보다 확실히 나은지 확인.

## 5. 실행 & 랭킹

- AutoDock **Vina** (`vina --receptor rec.pdbqt --ligand lig.pdbqt --config box.txt`) 또는 QuickVina/Smina.
- 결합 친화도(kcal/mol, **낮을수록 강함**)로 재랭킹.

## 6. 해석 (ML 외삽을 우회하는 지점)

후보가 **믿을 만한 hit**이 되려면:
1. 결합 점수가 BI-3231/공결정 저해제 대조군에 **필적하거나 더 좋음**.
2. 포켓의 **핵심 잔기·NAD⁺와 합리적 상호작용**(수소결합·소수성 접촉)을 형성 — PyMOL 등으로 육안 확인.
3. 포즈가 물리적으로 타당(뒤틀림·충돌 없음).

→ 이 세 가지를 통과하면 ML 점수가 외삽이더라도 **구조적 근거**가 생김. 그 후보만 실험(효소활성 assay)으로 넘김.

## 로컬(VS Code) 자동 실행 — 13·14 스크립트

수동 절차(1~5) 대신 아래 두 스크립트로 자동화. 윈도우 로컬용(smina + OpenBabel).

**① 도구 설치 (한 번만)**
```bash
conda install -c conda-forge openbabel smina
# smina가 conda로 안 깔리면 공식 smina.exe를 받아 PATH에 두거나 환경변수 SMINA=경로
```

**② 실행 (프로젝트 루트에서, venv 파이썬으로)**
```bash
python scripts/13_prep_receptor.py   # 8G89 다운로드 → 물 제거·NAD 유지·저해제(YXW) 분리 → receptor.pdbqt
python scripts/14_run_docking.py     # 후보 33개 + 대조군(YXW redock, BI-3231) 도킹 → results/docking_scores.csv
```

- 8G89의 공결정 저해제는 **YXW**(자동 탐지됨), 보조인자 **NAD** 유지.
- 14는 리간드당 수십 초~수 분(exhaustiveness=8) → 33개 + 대조군에 30~60분 예상. 빠른 테스트는 14 상단 `EXHAUST=4`.
- 결과 해석: 후보 결합에너지가 **대조군(YXW·BI-3231) 기준선 이하(더 음수)** 이면 유망 → PyMOL로 포켓 상호작용 확인 후 실험.

## 도구 (모두 무료)

RCSB PDB · OpenBabel · smina(또는 AutoDock Vina/QuickVina) · PyMOL(시각화)
- 로컬(윈도우)은 **smina + OpenBabel** 권장(PDBQT 변환 부담↓). Meeko/ADFR는 선택.

## 참고

- Crystal structures of HSD17B13 — Nat. Commun. 2023: https://www.nature.com/articles/s41467-023-40766-0
- 8G89: https://www.rcsb.org/structure/8G89 · 8G84: https://www.rcsb.org/structure/8G84
- BI-3231 (chemical probe): https://www.rcsb.org/structure/8G84 관련 논문 참조
