# -*- coding: utf-8 -*-
"""[도킹 3단계] 도킹 점수의 '크기 편향'을 보정해 재해석.

도킹 결합에너지는 분자가 클수록 유리(접촉↑)해서, 큰 천연물이 실제 결합력과
무관하게 좋은 점수를 받을 수 있다. Ligand Efficiency로 정규화한다:
    LE = -affinity / (무거운 원자 수)   # 원자 1개당 결합 기여, 클수록 효율적

- 후보/대조군의 무거운 원자 수 계산 → LE 재랭킹
- 알려진 저해제(YXW, BI-3231)의 LE를 기준선으로, 'affinity도 좋고 LE도 기준 이상'인
  후보를 진짜 유망군으로 표시
출력: data/docking/results/docking_analysis.csv
"""
import os
import json
import urllib.request
import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")

RESDIR = "data/docking/results"
SCORES = os.path.join(RESDIR, "docking_scores.csv")
MANIFEST = "data/docking/docking_manifest.csv"
REF_LIG = "data/docking/receptor/ref_ligand.pdb"
OUT = os.path.join(RESDIR, "docking_analysis.csv")

scores = pd.read_csv(SCORES)
man = pd.read_csv(MANIFEST).set_index("np_id")


def heavy_from_smiles(smi):
    m = Chem.MolFromSmiles(str(smi))
    return m.GetNumHeavyAtoms() if m else np.nan


def heavy_from_pdb(path):
    n = 0
    with open(path) as f:
        for ln in f:
            if ln[:6].strip() in ("ATOM", "HETATM"):
                elem = ln[76:78].strip() or ln[12:14].strip()
                if elem.upper() != "H":
                    n += 1
    return n


def pubchem_smiles(name):
    for prop in ("SMILES", "ConnectivitySMILES", "IsomericSMILES", "CanonicalSMILES"):
        try:
            u = ("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
                 f"{name}/property/{prop}/JSON")
            with urllib.request.urlopen(u, timeout=30) as r:
                d = json.load(r)["PropertyTable"]["Properties"][0]
            for k in (prop, "SMILES", "ConnectivitySMILES", "IsomericSMILES", "CanonicalSMILES"):
                if d.get(k):
                    return d[k]
        except Exception:
            continue
    return None


# 무거운 원자 수 채우기
heavy = {}
for _, r in scores.iterrows():
    i = str(r["id"])
    if i in man.index:
        heavy[i] = heavy_from_smiles(man.loc[i, "canonical_smiles"])
    elif i == "REF_cocrystal":
        heavy[i] = heavy_from_pdb(REF_LIG)
    elif i == "BI-3231":
        smi = pubchem_smiles("BI-3231")
        heavy[i] = heavy_from_smiles(smi) if smi else np.nan

scores["n_heavy"] = scores["id"].map(lambda i: heavy.get(str(i), np.nan))
scores["LE"] = -scores["affinity"] / scores["n_heavy"]

# 알려진 저해제 LE 기준선(더 낮은 쪽 = 통과 문턱)
ctrl = scores[scores.type == "control"]
le_thr = ctrl["LE"].min()
aff_thr = ctrl["affinity"].max()   # 더 약한 대조군(덜 음수)
print("=== 대조군(알려진 저해제) ===")
print(ctrl[["id", "affinity", "n_heavy", "LE"]].to_string(index=False))
print(f"\n문턱: affinity <= {aff_thr:.1f} 이고 LE >= {le_thr:.3f} 이면 '진짜 유망'")

cand = scores[scores.type == "candidate"].copy()
cand["beats_affinity"] = cand["affinity"] <= aff_thr
cand["beats_LE"] = cand["LE"] >= le_thr
cand["both"] = cand["beats_affinity"] & cand["beats_LE"]

out = scores.sort_values("LE", ascending=False)
out.to_csv(OUT, index=False)

print("\n=== Ligand Efficiency 재랭킹 (높을수록 원자당 효율적) ===")
show = out[["id", "type", "affinity", "n_heavy", "LE"]].head(15)
print(show.to_string(index=False))

promising = cand[cand["both"]].sort_values("LE", ascending=False)
print(f"\n>>> affinity·LE 둘 다 대조군 이상인 후보: {len(promising)}개")
if len(promising):
    print(promising[["id", "affinity", "n_heavy", "LE",
                     "active_prob", "max_sim_known"]].to_string(index=False))

# 크기빨 경고: affinity는 좋은데 LE는 문턱 미달(=큰 분자라 점수만 좋음)
size_inflated = cand[(cand["beats_affinity"]) & (~cand["beats_LE"])]
if len(size_inflated):
    print(f"\n[크기 편향 주의] affinity는 좋지만 LE 낮음(덩치빨 의심) {len(size_inflated)}개:")
    print(size_inflated[["id", "affinity", "n_heavy", "LE"]].to_string(index=False))
print(f"\n저장: {OUT}")
