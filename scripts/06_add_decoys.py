# -*- coding: utf-8 -*-
"""HSD17B13 active와 '성질은 닮았지만 구조는 다른' decoy(가정 inactive)를
PubChem에서 property-matched 방식으로 뽑아, active:inactive를 1:1로 맞춘 학습셋을 만든다.

깨끗한 decoy 조건 (DUD-E 방식):
  ① PubChem 무작위 분자에서 추출 (타겟과 무관한 범용 화합물)
  ② active의 [MW, logP, HBD, HBA, 회전결합, 형식전하] 5~95퍼센타일 창 안에 드는 것만
     → '성질만으로 찍는' 편법 차단
  ③ active와 ECFP4 Tanimoto <= 0.35  → 구조는 충분히 달라 실제 결합 가능성 낮음
  ④ 알려진 active/inactive(및 중복)와 canonical SMILES 겹치면 제외

출력:
  data/HSD17B13_decoys.csv                (decoy canonical_smiles 목록)
  data/HSD17B13_train_with_decoys.xlsx    (canonical_smiles, label, source)
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
OUT_XLSX = "data/HSD17B13_train_with_decoys.xlsx"
OUT_CSV = "data/HSD17B13_decoys.csv"
ACTIVE_MAX = 10000.0
TANIMOTO_MAX = 0.35
MAX_CID = 170_000_000
BATCH = 150
SEED = 42
BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
MAX_SAMPLED = 400_000   # 무한루프 방지: 이만큼 CID 살펴봐도 못 채우면 중단

random.seed(SEED)
np.random.seed(SEED)


# ---------- 라벨링 (05_train_clean.py와 동일) ----------
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
print(f"active {len(actives)} / inactive(실측) {len(inactives)} → 필요한 decoy {n_need}개 (목표 1:1)")

# ---------- active 성질 창 + fingerprint ----------
gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def props(mol):
    return (Descriptors.MolWt(mol),
            Descriptors.MolLogP(mol),
            rdMolDescriptors.CalcNumHBD(mol),
            rdMolDescriptors.CalcNumHBA(mol),
            rdMolDescriptors.CalcNumRotatableBonds(mol),
            Chem.GetFormalCharge(mol))


active_mols, active_fps, P = [], [], []
for s in actives:
    m = Chem.MolFromSmiles(str(s))
    if m is None:
        continue
    active_mols.append(m)
    active_fps.append(gen.GetFingerprint(m))
    P.append(props(m))
P = np.array(P, float)
lo = np.percentile(P, 5, axis=0)
hi = np.percentile(P, 95, axis=0)
lbl = ["MW", "logP", "HBD", "HBA", "RotB", "charge"]
print("active 성질 창(5~95%):")
for i, name in enumerate(lbl):
    print(f"  {name:6s} {lo[i]:8.2f} ~ {hi[i]:8.2f}")


# ---------- PubChem SMILES 속성명 자동 탐지(명칭 변경 대비) ----------
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
print(f"PubChem SMILES 속성명: {SPROP}")

NUM = "MolecularWeight,XLogP,HBondDonorCount,HBondAcceptorCount,RotatableBondCount,Charge"


def fetch_batch(cids):
    cid_str = ",".join(map(str, cids))
    url = f"{BASE}/compound/cid/{cid_str}/property/{NUM},{SPROP}/JSON"
    try:
        r = requests.get(url, timeout=40)
        if not r.ok:
            return []
        return r.json().get("PropertyTable", {}).get("Properties", [])
    except Exception:
        return []


def in_window(p):
    try:
        v = (float(p["MolecularWeight"]), float(p["XLogP"]),
             float(p["HBondDonorCount"]), float(p["HBondAcceptorCount"]),
             float(p["RotatableBondCount"]), float(p["Charge"]))
    except (TypeError, ValueError, KeyError):
        return False
    return all(lo[i] <= v[i] <= hi[i] for i in range(6))


# ---------- decoy 수집 루프 ----------
decoys = []
decoy_set = set()
sampled = 0
t0 = time.time()
while len(decoys) < n_need and sampled < MAX_SAMPLED:
    cids = [random.randint(1, MAX_CID) for _ in range(BATCH)]
    sampled += BATCH
    for p in fetch_batch(cids):
        if len(decoys) >= n_need:
            break
        if not in_window(p):
            continue
        smi = p.get(SPROP)
        if not smi:
            continue
        mol = Chem.MolFromSmiles(str(smi))
        if mol is None:
            continue
        canon = Chem.MolToSmiles(mol)
        if canon in known or canon in decoy_set:
            continue
        sim = max(DataStructs.BulkTanimotoSimilarity(gen.GetFingerprint(mol), active_fps))
        if sim > TANIMOTO_MAX:
            continue
        decoys.append(canon)
        decoy_set.add(canon)
    if sampled % (BATCH * 20) == 0:
        rate = len(decoys) / sampled * 100
        el = time.time() - t0
        print(f"  살펴본 CID {sampled:>7d} | decoy {len(decoys):>5d}/{n_need} "
              f"| 채택률 {rate:.2f}% | {el:.0f}s")
    time.sleep(0.15)   # PubChem 예의상 rate limit

print(f"\ndecoy 수집 완료: {len(decoys)}개 (살펴본 CID {sampled}, {time.time()-t0:.0f}s)")

# ---------- 저장 ----------
pd.DataFrame({"canonical_smiles": decoys}).to_csv(OUT_CSV, index=False)

train = pd.DataFrame(
    [(s, 1, "real") for s in actives] +
    [(s, 0, "real") for s in inactives] +
    [(s, 0, "decoy") for s in decoys],
    columns=["canonical_smiles", "label", "source"])
train.to_excel(OUT_XLSX, index=False)

print(f"\n최종 학습셋: active {int((train.label==1).sum())} / "
      f"inactive {int((train.label==0).sum())} "
      f"(실측 {len(inactives)} + decoy {len(decoys)})")
print("저장:", OUT_CSV, "|", OUT_XLSX)
