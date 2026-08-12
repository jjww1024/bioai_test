# -*- coding: utf-8 -*-
"""[도킹 1단계] HSD17B13 수용체(8G89) 다운로드 & 준비. (VS Code 로컬용)

- RCSB에서 8G89.pdb 다운로드
- 물 제거, NAD 계열 보조인자 유지, 단백질 유지 → 수용체
- 공결정 저해제(가장 큰 유기 헤테로 잔기)를 분리 → autobox 기준 + redocking 양성대조
- OpenBabel로 수용체 PDBQT 변환(수소·전하 추가, pH 7.4)

필요 도구: OpenBabel (conda install -c conda-forge openbabel)
출력: data/docking/receptor/  (8G89.pdb, receptor.pdb, receptor.pdbqt, ref_ligand.pdb)
"""
import os
import sys
import shutil
import subprocess
import urllib.request
from collections import defaultdict

OUTDIR = "data/docking/receptor"
PDB_ID = "8G89"
os.makedirs(OUTDIR, exist_ok=True)
RAW = os.path.join(OUTDIR, f"{PDB_ID}.pdb")
REC_PDB = os.path.join(OUTDIR, "receptor.pdb")
REC_PDBQT = os.path.join(OUTDIR, "receptor.pdbqt")
REF_LIG = os.path.join(OUTDIR, "ref_ligand.pdb")

# NAD 계열 보조인자(수용체에 유지) / 물·흔한 결정화 첨가물·이온(제거)
COFACTORS = {"NAD", "NAI", "NAP", "NDP", "NAJ", "NAX"}
DROP_HET = {"HOH", "WAT", "DOD",
            "GOL", "EDO", "PEG", "PGE", "PG4", "1PE", "ACT", "FMT", "DMS", "MPD",
            "SO4", "PO4", "CL", "NA", "K", "MG", "CA", "ZN", "MN", "IOD", "BR",
            "TRS", "EPE", "IMD", "BME", "CIT", "MES"}
AA = {"ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
      "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
      "MSE", "SEC", "PYL"}


def which(name):
    return shutil.which(name) or shutil.which(name + ".exe")


# 1) 다운로드
if not os.path.exists(RAW):
    url = f"https://files.rcsb.org/download/{PDB_ID}.pdb"
    print(f"다운로드: {url}")
    urllib.request.urlretrieve(url, RAW)
print(f"수용체 원본: {RAW}")

# 2) 파싱: 잔기별 라인 수집
with open(RAW) as f:
    lines = f.readlines()

het_atoms = defaultdict(list)   # (resname, chain, resseq) -> lines
het_count = defaultdict(int)    # resname -> atom 수
protein_lines, cofactor_lines = [], []
for ln in lines:
    rec = ln[:6].strip()
    if rec not in ("ATOM", "HETATM"):
        continue
    resn = ln[17:20].strip()
    chain = ln[21:22]
    resseq = ln[22:26].strip()
    if rec == "ATOM" or resn in AA:
        protein_lines.append(ln)
    elif resn in COFACTORS:
        cofactor_lines.append(ln)
    elif resn in DROP_HET:
        continue
    else:
        het_atoms[(resn, chain, resseq)].append(ln)
        het_count[resn] += 1

print("\n발견된 비표준 헤테로 잔기(물·이온·첨가물 제외):")
for (resn, ch, seq), lns in sorted(het_atoms.items(), key=lambda kv: -len(kv[1])):
    print(f"  {resn} (chain {ch} #{seq}): {len(lns)} atoms")
print(f"보조인자(유지): {sorted(set(l[17:20].strip() for l in cofactor_lines)) or '없음'}")

if not het_atoms:
    print("\n[경고] 저해제 후보를 못 찾음. PDB의 HET 목록을 확인해 수동 지정 필요.")
    sys.exit(1)

# 3) 가장 큰 유기 헤테로 잔기 = 공결정 저해제(기준 리간드)
ref_key = max(het_atoms, key=lambda k: len(het_atoms[k]))
print(f"\n기준 저해제로 선택: {ref_key[0]} (chain {ref_key[1]} #{ref_key[2]}, "
      f"{len(het_atoms[ref_key])} atoms)  ← 틀리면 스크립트 상단에서 조정")

# 4) 수용체(단백질+보조인자) / 기준 리간드 파일 작성
with open(REC_PDB, "w") as f:
    f.writelines(protein_lines + cofactor_lines)
    f.write("END\n")
with open(REF_LIG, "w") as f:
    f.writelines(het_atoms[ref_key])
    f.write("END\n")
print(f"수용체(단백질+NAD): {REC_PDB}")
print(f"기준 리간드: {REF_LIG}")

# 5) OpenBabel로 수용체 PDBQT (수소·전하, pH 7.4, 강체 -xr)
obabel = which("obabel")
if not obabel:
    print("\n[다음 단계 필요] OpenBabel 미설치. 설치 후 아래 실행:")
    print("  conda install -c conda-forge openbabel")
    print(f'  obabel "{REC_PDB}" -O "{REC_PDBQT}" -xr -p 7.4')
    sys.exit(0)
cmd = [obabel, REC_PDB, "-O", REC_PDBQT, "-xr", "-p", "7.4"]
print("\n실행:", " ".join(cmd))
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stderr.strip()[-300:] if r.stderr else "")
if os.path.exists(REC_PDBQT) and os.path.getsize(REC_PDBQT) > 0:
    print(f"수용체 PDBQT 완료: {REC_PDBQT}")
    print("\n→ 다음: python scripts/14_run_docking.py")
else:
    print("[실패] 수용체 PDBQT 생성 실패. OpenBabel 출력 확인.")
