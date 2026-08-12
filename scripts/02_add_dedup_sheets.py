# -*- coding: utf-8 -*-
"""기존 병합 엑셀에 2개 시트 추가:
  1) same_dedup_keepdiff : 같은 물질+같은 IC50 → 1줄, 다른 IC50 → 그대로
  2) median_per_compound : 같은 물질 → 1줄, IC50는 중앙값 집계
"""
import numpy as np
import pandas as pd

OUT = "data/HSD17B13_IC50_merged.xlsx"

df = pd.read_excel(OUT, sheet_name="all_data")
# IC50 중심 시트이므로 canonical/IC50 유효한 행만
d = df.dropna(subset=["canonical_smiles", "ic50_nM"]).copy()
d["ic50_key"] = d["ic50_nM"].round(3)   # 부동소수 잡음 방지용 비교키


def join_sources(s):
    return ", ".join(sorted(s.dropna().astype(str).unique()))


def first_valid(s):
    v = s.dropna()
    return v.iloc[0] if len(v) else np.nan


# ---------- 시트1: 같은 IC50는 제거, 다른 IC50는 유지 ----------
# (canonical_smiles, ic50_key) 조합 단위로 집계 → 같은 값은 1줄, 다른 값은 별도 줄
s1 = (d.groupby(["canonical_smiles", "ic50_key"], as_index=False)
        .agg(compound_id=("compound_id", first_valid),
             smiles=("smiles", first_valid),
             ic50_nM=("ic50_nM", "first"),
             relation=("relation", first_valid),
             pChEMBL=("pChEMBL", first_valid),
             sources=("source", join_sources),
             n_records=("source", "size")))
# 물질별로 IC50 값이 몇 종류인지(=여전히 남은 중복 줄 수)
s1["n_ic50_values"] = s1.groupby("canonical_smiles")["ic50_nM"].transform("size")
s1 = s1.sort_values(["n_ic50_values", "canonical_smiles", "ic50_nM"],
                    ascending=[False, True, True]).reset_index(drop=True)
s1 = s1.drop(columns=["ic50_key"], errors="ignore")
s1 = s1[["canonical_smiles", "compound_id", "smiles", "ic50_nM", "relation",
         "pChEMBL", "sources", "n_records", "n_ic50_values"]]

# ---------- 시트2: 물질당 1줄, IC50 중앙값 ----------
s2 = (d.groupby("canonical_smiles", as_index=False)
        .agg(compound_id=("compound_id", first_valid),
             smiles=("smiles", first_valid),
             ic50_nM_median=("ic50_nM", "median"),
             ic50_nM_min=("ic50_nM", "min"),
             ic50_nM_max=("ic50_nM", "max"),
             n_measurements=("ic50_nM", "size"),
             sources=("source", join_sources)))
# 부등호(>,<) 값이 섞였는지 표시 (중앙값 해석 시 주의)
qual = (d.assign(q=d["relation"].astype(str).str.strip().isin([">", "<", ">=", "<="]))
          .groupby("canonical_smiles")["q"].any().reset_index(name="has_qualifier"))
s2 = s2.merge(qual, on="canonical_smiles", how="left")
s2 = s2.sort_values(["n_measurements", "canonical_smiles"],
                    ascending=[False, True]).reset_index(drop=True)
s2 = s2[["canonical_smiles", "compound_id", "smiles", "ic50_nM_median",
         "ic50_nM_min", "ic50_nM_max", "n_measurements", "has_qualifier", "sources"]]

# ---------- 기존 파일에 시트 추가 (기존 시트/서식 보존) ----------
with pd.ExcelWriter(OUT, engine="openpyxl", mode="a",
                    if_sheet_exists="replace") as w:
    s1.to_excel(w, sheet_name="same_dedup_keepdiff", index=False)
    s2.to_excel(w, sheet_name="median_per_compound", index=False)

print("추가 완료 →", OUT)
print(f"[시트1 same_dedup_keepdiff] {len(s1)}행 "
      f"(입력 {len(d)}행에서 같은 IC50 중복 제거)")
print(f"  - IC50 값이 2개 이상 남은 물질 행: "
      f"{int((s1['n_ic50_values'] > 1).sum())}")
print(f"[시트2 median_per_compound] {len(s2)}행 (물질당 1줄)")
print(f"  - 측정 2건 이상인 물질: {int((s2['n_measurements'] > 1).sum())}")
print(f"  - 부등호 섞인 물질: {int(s2['has_qualifier'].sum())}")
