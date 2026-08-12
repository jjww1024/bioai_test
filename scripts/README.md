# scripts/ — 정제 데이터(BindingDB + ChEMBL) 기반 학습 파이프라인

`bioai_test.py`(ChEMBL/PubChem 자동 수집 파이프라인)와 별개로, **BindingDB·ChEMBL에서
수동 다운로드한 HSD17B13 IC50 실측 데이터**를 정제·학습하는 스크립트 모음.
(PubChem 자동수집이 무관한 assay로 오염됐던 문제를 피하기 위한 경로)

## 데이터 준비 (data/ 폴더에 아래 이름으로)

`data/`는 `.gitignore`로 제외되므로 대용량/개인 파일이 GitHub에 올라가지 않습니다.

| 파일 | 출처 |
|------|------|
| `data/bindingdb_hsd17b13.tsv` | BindingDB에서 HSD17B13 검색 → TSV 다운로드 |
| `data/chembl_hsd17b13.tsv` | ChEMBL 타겟(CHEMBL5305042) Activities → TSV |

## 실행 순서 (프로젝트 루트에서)

```bash
python scripts/01_merge_ic50.py        # 두 TSV 병합 + canonical SMILES 중복판정 → data/HSD17B13_IC50_merged.xlsx
python scripts/02_add_dedup_sheets.py  # 같은IC50 합침 / 물질별 중앙값 시트 추가
python scripts/03_robust_dedup.py      # 값 퍼짐(spread) 기반 신뢰도 등급 시트 추가
python scripts/04_make_fingerprints.py # 4종 fingerprint(ECFP4/MACCS/RDKit/AtomPair) → data/HSD17B13_fingerprints.xlsx
python scripts/05_train_clean.py       # IC50<=10000nM=active 라벨링 + 4종 fingerprint 학습·비교
```

## 라벨링 기준 (05_train_clean.py)

- `IC50 ≤ 10000 nM` → **active(1)**
- `IC50 > 10000 nM` (회색지대·부등호 `>` 포함) → **inactive(0)**
- 같은 물질에 측정 여러 개면 하나라도 active면 active. 물질(canonical) 단위로 학습(누수 방지).
