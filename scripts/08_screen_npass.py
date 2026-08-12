# -*- coding: utf-8 -*-
"""decoy 균형 모델(HSD17B13_screen_model.pkl)로 NPASS 천연물 라이브러리를
스크리닝해 HSD17B13 저해 후보 상위를 뽑는다.

각 후보에 대해:
  - active_prob        : 모델이 매긴 활성 확률
  - max_sim_known      : 알려진 active와의 최대 ECFP4 Tanimoto (신규성 지표)
  - nearest_active     : 가장 닮은 알려진 active의 SMILES
  - is_known           : 학습 active와 사실상 동일(canonical 일치)한지

해석: prob 높고 max_sim_known이 '중간'(0.3~0.6)이면 → 그럴듯한 신규 후보.
      prob 높은데 max_sim_known 매우 낮으면 → 모델 외삽, 신중.
      is_known=True → 이미 알려진 물질(신규 아님).
"""
import time
import pickle
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import MACCSkeys, rdFingerprintGenerator
from rdkit import RDLogger
RDLogger.DisableLog("rdApp.*")

MODEL = "data/HSD17B13_screen_model.pkl"
NPASS = "data/npass_structures.tsv"
TRAIN = "data/HSD17B13_train_with_decoys.xlsx"
OUT_XLSX = "data/HSD17B13_npass_hits.xlsx"
OUT_CSV = "data/HSD17B13_npass_ranked_full.csv"
TOP_N = 300

with open(MODEL, "rb") as f:
    bundle = pickle.load(f)
model, fp_name, nbits = bundle["model"], bundle["fp_name"], bundle["nbits"]
print(f"모델: fingerprint={fp_name}, {nbits}bit "
      f"(학습 active {bundle['n_active']} / inactive {bundle['n_inactive']})")

# ---------- fingerprint 함수 (학습과 동일) ----------
gens = {
    "ECFP4": rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=nbits),
    "RDKit": rdFingerprintGenerator.GetRDKitFPGenerator(fpSize=nbits),
    "AtomPair": rdFingerprintGenerator.GetAtomPairGenerator(fpSize=nbits),
}
sim_gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def maccs_np(mol):
    fp = MACCSkeys.GenMACCSKeys(mol)
    arr = np.zeros((fp.GetNumBits(),), dtype=np.int8)
    DataStructs.ConvertToNumpyArray(fp, arr)
    return arr


def featurize(mol):
    if fp_name == "MACCS":
        return maccs_np(mol)
    return gens[fp_name].GetFingerprintAsNumPy(mol)


# ---------- 알려진 active (유사도 비교용) ----------
tr = pd.read_excel(TRAIN)
act_smis = tr[(tr.label == 1) & (tr.source == "real")]["canonical_smiles"].tolist()
act_fps, act_keep = [], []
for s in act_smis:
    m = Chem.MolFromSmiles(str(s))
    if m:
        act_fps.append(sim_gen.GetFingerprint(m))
        act_keep.append(s)
known_canon = set(act_keep)
print(f"알려진 active {len(act_fps)}개 로드(유사도 비교용)")

# ---------- NPASS 읽기 + featurize ----------
npass = pd.read_csv(NPASS, sep="\t", usecols=["np_id", "SMILES"])
print(f"NPASS {len(npass)}개 로드 → featurize 시작")

ids, canons, mats, sims, nn_smi, is_known = [], [], [], [], [], []
t0 = time.time()
for i, (npid, smi) in enumerate(zip(npass["np_id"], npass["SMILES"])):
    mol = Chem.MolFromSmiles(str(smi))
    if mol is None:
        continue
    canon = Chem.MolToSmiles(mol)
    mats.append(featurize(mol))
    q = sim_gen.GetFingerprint(mol)
    s = DataStructs.BulkTanimotoSimilarity(q, act_fps)
    j = int(np.argmax(s))
    ids.append(npid)
    canons.append(canon)
    sims.append(float(s[j]))
    nn_smi.append(act_keep[j])
    is_known.append(canon in known_canon)
    if (i + 1) % 10000 == 0:
        print(f"  {i+1}/{len(npass)} 처리 ({time.time()-t0:.0f}s)")

X = np.vstack(mats).astype(np.float32)
print(f"featurize 완료: {X.shape[0]}개 ({time.time()-t0:.0f}s) → 배치 예측")

# ---------- 배치 예측 ----------
prob = model.predict_proba(X)[:, 1]

res = pd.DataFrame({
    "np_id": ids,
    "canonical_smiles": canons,
    "active_prob": prob,
    "max_sim_known": sims,
    "nearest_active": nn_smi,
    "is_known": is_known,
}).sort_values("active_prob", ascending=False).reset_index(drop=True)

res.to_csv(OUT_CSV, index=False)

# 신규 후보(이미 알려진 것 제외) 상위 TOP_N
novel = res[~res["is_known"]].head(TOP_N)
with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as w:
    novel.to_excel(w, sheet_name=f"top{TOP_N}_novel", index=False)
    res.head(50).to_excel(w, sheet_name="top50_all", index=False)

print(f"\n전체 순위: {OUT_CSV}")
print(f"상위 후보(신규): {OUT_XLSX}")
print(f"\nactive_prob >= 0.9: {(res.active_prob>=0.9).sum()}개 "
      f"(그중 신규 {((res.active_prob>=0.9)&(~res.is_known)).sum()}개)")
print(f"NPASS에서 발견된 '이미 알려진 active': {res.is_known.sum()}개")
print("\n=== 신규 후보 상위 15 ===")
print(novel.head(15)[["np_id", "active_prob", "max_sim_known"]].to_string(index=False))
