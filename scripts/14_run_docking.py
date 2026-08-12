# -*- coding: utf-8 -*-
"""[도킹 2단계] smina로 HSD17B13 후보 도킹 & 랭킹. (VS Code 로컬용)

- 후보 33개(data/docking/hsd17b13_ligands.sdf)를 8G89 포켓에 도킹
- 대조군: 공결정 저해제 redocking(양성), BI-3231(알려진 저해제, PubChem 자동 조회)
- autobox = 기준 저해제 위치 / 결합에너지(kcal/mol, 낮을수록 강함)로 랭킹

필요 도구: smina (conda install -c conda-forge smina  또는 공식 smina.exe를 PATH에)
           먼저 13_prep_receptor.py 실행 필요.
출력: data/docking/results/docking_scores.csv  + 각 리간드 포즈(out_*.pdbqt)
"""
import os
import re
import sys
import glob
import shutil
import tempfile
import subprocess
import urllib.request
import pandas as pd
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")

RECDIR = "data/docking/receptor"
REC_PDBQT = os.path.join(RECDIR, "receptor.pdbqt")
REF_LIG = os.path.join(RECDIR, "ref_ligand.pdb")
LIGANDS = "data/docking/hsd17b13_ligands.sdf"
MANIFEST = "data/docking/docking_manifest.csv"
RESDIR = "data/docking/results"
OUT_CSV = os.path.join(RESDIR, "docking_scores.csv")
EXHAUST = 8          # 정확도(↑느림). 빠른 테스트는 4
AUTOBOX_ADD = 4      # 기준 리간드 경계 + Å
os.makedirs(RESDIR, exist_ok=True)


def which(name):
    return os.environ.get("SMINA") if name == "smina" and os.environ.get("SMINA") \
        else (shutil.which(name) or shutil.which(name + ".exe"))


SMINA = which("smina")
if not SMINA:
    sys.exit("[중단] smina 미설치. 설치 후 재실행:\n"
             "  conda install -c conda-forge smina\n"
             "  (또는 공식 smina.exe를 PATH에 두거나 환경변수 SMINA=경로 설정)")
if not (os.path.exists(REC_PDBQT) and os.path.exists(REF_LIG)):
    sys.exit("[중단] 수용체 준비 안 됨. 먼저: python scripts/13_prep_receptor.py")
print(f"smina: {SMINA}")


def run_smina(ligand_path, out_path):
    """도킹 실행 → 최고 모드 결합에너지(kcal/mol) 반환(실패 시 None)"""
    cmd = [SMINA, "-r", REC_PDBQT, "-l", ligand_path,
           "--autobox_ligand", REF_LIG, "--autobox_add", str(AUTOBOX_ADD),
           "--exhaustiveness", str(EXHAUST), "--seed", "42",
           "-o", out_path, "--cpu", "0"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    except subprocess.TimeoutExpired:
        return None
    best = None
    for line in r.stdout.splitlines():
        m = re.match(r"\s*1\s+(-?\d+\.\d+)", line)   # mode 1 = 최고
        if m:
            best = float(m.group(1))
            break
    return best


def sdf_iter(path):
    for mol in Chem.SDMolSupplier(path, removeHs=False):
        if mol is not None:
            yield mol


def dock_mol(mol, tag):
    with tempfile.NamedTemporaryFile("w", suffix=".sdf", delete=False) as tf:
        tmp = tf.name
    w = Chem.SDWriter(tmp)
    w.write(mol)
    w.close()
    out = os.path.join(RESDIR, f"pose_{tag}.pdbqt")
    aff = run_smina(tmp, out)
    os.unlink(tmp)
    return aff


man = pd.read_csv(MANIFEST).set_index("np_id") if os.path.exists(MANIFEST) else None
rows = []

# ---- resume: 이미 도킹된 항목은 재사용(빠진 것만 다시 도킹) ----
done = {}
if os.path.exists(OUT_CSV):
    prev = pd.read_csv(OUT_CSV)
    for _, pr in prev.iterrows():
        if pd.notna(pr.get("affinity")):
            done[str(pr["id"])] = pr.to_dict()
    if done:
        print(f"(resume) 기존 결과 {len(done)}건 재사용, 빠진 것만 도킹")


def pubchem_smiles(name):
    """PubChem 이름→SMILES. 속성명 변경(IsomericSMILES→SMILES) 대응."""
    import json
    for prop in ("SMILES", "ConnectivitySMILES", "IsomericSMILES", "CanonicalSMILES"):
        try:
            u = ("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
                 f"{name}/property/{prop}/JSON")
            with urllib.request.urlopen(u, timeout=30) as resp:
                d = json.load(resp)["PropertyTable"]["Properties"][0]
            for k in (prop, "SMILES", "ConnectivitySMILES", "IsomericSMILES", "CanonicalSMILES"):
                if d.get(k):
                    return d[k]
        except Exception:
            continue
    return None

# ---- 대조군 1: 공결정 저해제 redocking (양성) ----
if "REF_cocrystal" in done:
    rows.append(done["REF_cocrystal"])
    print(f"\n[대조군] 공결정 저해제: {done['REF_cocrystal']['affinity']} kcal/mol (재사용)")
else:
    print("\n[대조군] 공결정 저해제 redocking...")
    aff = run_smina(REF_LIG, os.path.join(RESDIR, "pose_REF_redock.pdbqt"))
    print(f"  공결정 저해제: {aff} kcal/mol (양성 기준선)")
    rows.append({"id": "REF_cocrystal", "type": "control", "affinity": aff})

# ---- 대조군 2: BI-3231 (PubChem 자동 조회) ----
if "BI-3231" in done:
    rows.append(done["BI-3231"])
    print(f"[대조군] BI-3231: {done['BI-3231']['affinity']} kcal/mol (재사용)")
else:
    print("[대조군] BI-3231 조회(PubChem)...")
    try:
        smi = pubchem_smiles("BI-3231")
        if not smi:
            raise ValueError("PubChem에서 SMILES 못 찾음")
        m = Chem.AddHs(Chem.MolFromSmiles(smi))
        p = AllChem.ETKDGv3(); p.randomSeed = 42
        AllChem.EmbedMolecule(m, p); AllChem.MMFFOptimizeMolecule(m)
        m.SetProp("_Name", "BI-3231")
        aff = dock_mol(m, "BI3231")
        print(f"  BI-3231: {aff} kcal/mol (알려진 저해제 기준선)")
        rows.append({"id": "BI-3231", "type": "control", "affinity": aff})
    except Exception as e:
        print(f"  BI-3231 조회/도킹 실패(건너뜀): {e}")

# ---- 후보 33개 ----
print(f"\n[후보] {LIGANDS} 도킹 시작 (exhaustiveness={EXHAUST})")
mols = list(sdf_iter(LIGANDS))
for i, mol in enumerate(mols, 1):
    npid = mol.GetProp("np_id") if mol.HasProp("np_id") else mol.GetProp("_Name")
    if npid in done:
        rows.append(done[npid])
        print(f"  [{i}/{len(mols)}] {npid}: {done[npid]['affinity']} kcal/mol (재사용)")
        continue
    aff = dock_mol(mol, npid)
    prob = mol.GetProp("active_prob") if mol.HasProp("active_prob") else ""
    sim = mol.GetProp("max_sim_known") if mol.HasProp("max_sim_known") else ""
    rows.append({"id": npid, "type": "candidate", "affinity": aff,
                 "active_prob": prob, "max_sim_known": sim})
    print(f"  [{i}/{len(mols)}] {npid}: {aff} kcal/mol")

# ---- 정리·랭킹 ----
res = pd.DataFrame(rows)
res["affinity"] = pd.to_numeric(res["affinity"], errors="coerce")
res = res.sort_values("affinity").reset_index(drop=True)  # 낮을수록 강함
res.to_csv(OUT_CSV, index=False)

ctrl = res[res.type == "control"]["affinity"]
ref_score = ctrl.max() if len(ctrl) else None   # 가장 약한 대조군 기준선
print(f"\n결과 저장: {OUT_CSV}")
print("\n=== 결합에너지 랭킹(낮을수록 강함) ===")
print(res[["id", "type", "affinity", "active_prob", "max_sim_known"]].to_string(index=False))
if ref_score is not None:
    good = res[(res.type == "candidate") & (res.affinity <= ref_score)]
    print(f"\n대조군 기준선({ref_score:.1f}) 이상으로 결합한 후보: {len(good)}개")
    print("→ 이들만 포즈(PyMOL)로 상호작용 확인 후 실험 후보로.")
