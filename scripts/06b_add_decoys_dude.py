# -*- coding: utf-8 -*-
"""정식 DUD-E 방식(active별 개별 property 매칭)으로 decoy를 생성한다.
06(전체 5~95% 창)의 업그레이드판.

DUD-E 알고리즘(Mysinger 2012)을 로컬 재현:
  - 각 active의 6가지 물성(MW, logP, HBD, HBA, 회전결합, 전하)에 대해
    개별 허용오차 안에 드는 PubChem 무작위 분자를 decoy로 매칭
  - 단, 어떤 active와도 ECFP4 Tanimoto <= 0.35 (구조는 비유사)
  - 각 decoy는 '가장 잘 맞는' active 하나에 1:1 배정, 재사용 금지
  - 알려진 active/inactive 및 중복 제외
소스는 ZINC 대신 PubChem(웹서버 불필요, 대기 없음).

출력:
  data/HSD17B13_decoys_dude.csv
  data/HSD17B13_train_with_decoys_dude.xlsx  (canonical_smiles, label, source)
"""
import time
import random
import numpy as np
import pandas as pd
import requests
from rdkit import Chem, DataStructs
from rdkit.Chem import Descriptors, rdMolDescriptors, rdFingerprintGenerator
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")

SRC = "data/HSD17B13_IC50_merged.xlsx"
OUT_XLSX = "data/HSD17B13_train_with_decoys_dude.xlsx"
OUT_CSV = "data/HSD17B13_decoys_dude.csv"
ACTIVE_MAX = 10000.0
TANIMOTO_MAX = 0.35
MAX_CID = 170_000_000
BATCH = 150
SEED = 42
MAX_SAMPLED = 600_000
BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# active별 개별 허용오차 (DUD-E 유사)
TOL = np.array([25.0, 1.0, 1.0, 2.0, 2.0, 0.0])   # MW, logP, HBD, HBA, RotB, charge(정확일치)

random.seed(SEED)
np.random.seed(SEED)


def make_label(ic50, rel):
    rel = str(rel).strip()
    if pd.isna(ic50):
        return np.nan
    if rel in ("<", "<="):
        return 1 if ic50 <= ACTIVE_MAX else 0
    if rel in (">", ">="):
        return 0
    return 1 if ic50 <= ACTIVE_MAX else 0


df = pd.read_excel(SRC, sheet_name="same_dedup_keepdiff")
df = df.dropna(subset=["canonical_smiles", "ic50_nM"]).copy()
df["label"] = [make_label(v, r) for v, r in zip(df["ic50_nM"], df["relation"])]
df = df.dropna(subset=["label"])
df["label"] = df["label"].astype(int)
comp = df.groupby("canonical_smiles")["label"].max().reset_index()
actives = comp[comp.label == 1]["canonical_smiles"].tolist()
inactives = comp[comp.label == 0]["canonical_smiles"].tolist()
known = set(actives) | set(inactives)
n_need = max(0, len(actives) - len(inactives))
print(f"active {len(actives)} / inactive(실측) {len(inactives)} → decoy {n_need}개 (1:1)")

gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def props(mol):
    return (Descriptors.MolWt(mol), Descriptors.MolLogP(mol),
            rdMolDescriptors.CalcNumHBD(mol), rdMolDescriptors.CalcNumHBA(mol),
            rdMolDescriptors.CalcNumRotatableBonds(mol), Chem.GetFormalCharge(mol))


A, active_fps = [], []
for s in actives:
    m = Chem.MolFromSmiles(str(s))
    if m is None:
        continue
    A.append(props(m))
    active_fps.append(gen.GetFingerprint(m))
A = np.array(A, float)                     # (n_active, 6)
gmin = (A.min(0) - TOL)
gmax = (A.max(0) + TOL)                     # 전역 프리필터 범위(느슨)
assigned = np.zeros(len(A), dtype=bool)    # active별 1개 배정 여부
print(f"active property 행렬 {A.shape} 준비 (개별 매칭용)")


def detect_smiles_prop():
    for name in ("SMILES", "ConnectivitySMILES", "CanonicalSMILES", "IsomericSMILES"):
        try:
            r = requests.get(f"{BASE}/compound/cid/2244/property/{name}/JSON", timeout=20)
            if r.ok and "PropertyTable" in r.json():
                return name
        except Exception:
            pass
    return "CanonicalSMILES"


SPROP = detect_smiles_prop()
NUM = "MolecularWeight,XLogP,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,Charge"
print(f"PubChem SMILES 속성명: {SPROP}")


def fetch_batch(cids):
    url = f"{BASE}/compound/cid/{','.join(map(str,cids))}/property/{NUM},{SPROP}/JSON"
    try:
        r = requests.get(url, timeout=40)
        return r.json().get("PropertyTable", {}).get("Properties", []) if r.ok else []
    except Exception:
        return []


def cand_props(p):
    try:
        return np.array([float(p["MolecularWeight"]), float(p["XLogP"]),
                         float(p["HBondDonorCount"]), float(p["HBondAcceptorCount"]),
                         float(p["RotatableBondCount"]), float(p["Charge"])])
    except (TypeError, ValueError, KeyError):
        return None


decoys, decoy_set = [], set()
sampled = 0
t0 = time.time()
while len(decoys) < n_need and sampled < MAX_SAMPLED:
    cids = [random.randint(1, MAX_CID) for _ in range(BATCH)]
    sampled += BATCH
    for p in fetch_batch(cids):
        if len(decoys) >= n_need:
            break
        v = cand_props(p)
        if v is None or v[5] != 0:                      # 중성만
            continue
        if np.any(v < gmin) or np.any(v > gmax):        # 전역 프리필터
            continue
        smi = p.get(SPROP)
        mol = Chem.MolFromSmiles(str(smi)) if smi else None
        if mol is None:
            continue
        canon = Chem.MolToSmiles(mol)
        if canon in known or canon in decoy_set:
            continue
        # active별 개별 허용오차 안에 드는 active 후보 찾기 (아직 미배정)
        within = np.all(np.abs(A - v) <= TOL, axis=1) & (~assigned)
        if not within.any():
            continue
        # 구조 비유사 조건: 어떤 active와도 Tanimoto <= 0.35
        q = gen.GetFingerprint(mol)
        sims = np.array(DataStructs.BulkTanimotoSimilarity(q, active_fps))
        if sims.max() > TANIMOTO_MAX:
            continue
        # 매칭되는 active 중 물성거리 가장 가까운 것에 1:1 배정
        cand_idx = np.where(within)[0]
        dist = np.abs((A[cand_idx] - v) / np.where(TOL == 0, 1, TOL)).sum(1)
        pick = cand_idx[int(np.argmin(dist))]
        assigned[pick] = True
        decoys.append(canon)
        decoy_set.add(canon)
    if sampled % (BATCH * 20) == 0:
        print(f"  CID {sampled:>7d} | decoy {len(decoys):>5d}/{n_need} "
              f"| 배정 active {int(assigned.sum())} | {time.time()-t0:.0f}s")
    time.sleep(0.15)

print(f"\ndecoy 수집 완료: {len(decoys)}개 (CID {sampled}, {time.time()-t0:.0f}s)")
pd.DataFrame({"canonical_smiles": decoys}).to_csv(OUT_CSV, index=False)
train = pd.DataFrame(
    [(s, 1, "real") for s in actives] +
    [(s, 0, "real") for s in inactives] +
    [(s, 0, "decoy") for s in decoys],
    columns=["canonical_smiles", "label", "source"])
train.to_excel(OUT_XLSX, index=False)
print(f"최종: active {int((train.label==1).sum())} / inactive {int((train.label==0).sum())} "
      f"(실측 {len(inactives)} + decoy {len(decoys)})")
print("저장:", OUT_CSV, "|", OUT_XLSX)
