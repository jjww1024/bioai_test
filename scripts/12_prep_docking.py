# -*- coding: utf-8 -*-
"""NPASS 스크리닝 상위 후보(prob>=0.7)를 도킹 입력으로 준비한다.
ML 외삽 문제를 우회해 '실제 단백질 포켓 결합'을 구조적으로 검증하기 위한 전 단계.

각 후보: SMILES → 수소 첨가 → 3D 좌표 생성(ETKDGv3) → MMFF 에너지 최소화 → SDF 저장
매니페스트: prob, 유사도, MW, logP, 회전결합수(도킹 유연성), 3D 생성 성공여부

출력:
  data/docking/hsd17b13_ligands.sdf   (도킹용 3D 리간드 묶음)
  data/docking/docking_manifest.csv
"""
import os
import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")

SRC = "data/HSD17B13_npass_ranked_full.csv"
OUTDIR = "data/docking"
SDF = os.path.join(OUTDIR, "hsd17b13_ligands.sdf")
MAN = os.path.join(OUTDIR, "docking_manifest.csv")
PROB_MIN = 0.7
os.makedirs(OUTDIR, exist_ok=True)

r = pd.read_csv(SRC)
cand = r[(r.active_prob >= PROB_MIN) & (~r.is_known)].reset_index(drop=True)
print(f"도킹 준비 대상: prob>={PROB_MIN} 신규 후보 {len(cand)}개")


def make_3d(smi):
    """SMILES → 3D 최소화 mol (실패 시 None)"""
    mol = Chem.MolFromSmiles(str(smi))
    if mol is None:
        return None, "parse_fail"
    mol = Chem.AddHs(mol)
    p = AllChem.ETKDGv3()
    p.randomSeed = 42
    if AllChem.EmbedMolecule(mol, p) != 0:
        p.useRandomCoords = True
        if AllChem.EmbedMolecule(mol, p) != 0:
            return None, "embed_fail"
    try:
        if AllChem.MMFFHasAllMoleculeParams(mol):
            AllChem.MMFFOptimizeMolecule(mol, maxIters=1000)
            ff = "MMFF"
        else:
            AllChem.UFFOptimizeMolecule(mol, maxIters=1000)
            ff = "UFF"
    except Exception:
        ff = "none"
    return mol, ff


writer = Chem.SDWriter(SDF)
rows, ok = [], 0
for _, x in cand.iterrows():
    mol, status = make_3d(x.canonical_smiles)
    base = Chem.MolFromSmiles(str(x.canonical_smiles))
    rot = rdMolDescriptors.CalcNumRotatableBonds(base) if base else np.nan
    mw = Descriptors.MolWt(base) if base else np.nan
    logp = Descriptors.MolLogP(base) if base else np.nan
    success = mol is not None
    if success:
        mol.SetProp("_Name", str(x.np_id))
        mol.SetProp("np_id", str(x.np_id))
        mol.SetProp("active_prob", f"{x.active_prob:.4f}")
        mol.SetProp("max_sim_known", f"{x.max_sim_known:.4f}")
        writer.write(mol)
        ok += 1
    rows.append({
        "np_id": x.np_id, "active_prob": round(x.active_prob, 4),
        "max_sim_known": round(x.max_sim_known, 4),
        "MW": round(mw, 1) if mw == mw else None,
        "logP": round(logp, 2) if logp == logp else None,
        "n_rotatable": rot,
        "flexible_warn": (rot is not np.nan and rot > 10),  # Vina 유연성 한계
        "embed_status": status if not success else status,  # ff명 or 실패사유
        "canonical_smiles": x.canonical_smiles,
    })
writer.close()

man = pd.DataFrame(rows)
man.to_csv(MAN, index=False)

print(f"3D 생성 성공 {ok}/{len(cand)} → {SDF}")
fail = man[~man.embed_status.isin(["MMFF", "UFF", "none"])]
if len(fail):
    print(f"3D 실패 {len(fail)}개(대개 거대·복잡 천연물): "
          + ", ".join(fail.np_id.tolist()))
flex = man[man.flexible_warn == True]
print(f"고유연성(회전결합>10, 도킹 신뢰 낮음) {len(flex)}개")
print(f"매니페스트: {MAN}")
print("\n=== 상위 10 (도킹 우선순위) ===")
print(man.head(10)[["np_id", "active_prob", "max_sim_known", "MW", "logP",
                    "n_rotatable", "embed_status"]].to_string(index=False))
