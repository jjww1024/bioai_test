# -*- coding: utf-8 -*-
"""천연물 라이브러리 3종을 새 모델(29번)로 다시 스크리닝한다.

기존 08b와 달라지는 점:

  1) 모델 — ECFP4+FCFP4, 배경을 천연물 라이브러리에서 뽑은 것(29번)

  2) 절대 점수 커트라인을 쓰지 않는다.
     기존 08b는 prob >= 0.5 로 잘랐다. Cockroft Figure 9이 바로 이 관행을
     경고한다 — 천연물은 정답을 맞혀도 점수가 낮게 나온다(그 논문에서
     천연물 예측의 93.8%가 0.25 이하, 합성물은 50.5%). 구조적으로 그렇다.
     그래서 여기서는 전체를 점수순으로 줄 세우기만 하고, 자르는 일은
     사람이 '순위'로 한다.

  3) 모든 후보에 적용 범위(applicability domain) 정보를 붙인다.
     max_sim_known 이 낮으면 모델이 외삽 중이라는 뜻이다. 버리라는 게
     아니라, 점수를 액면 그대로 믿지 말라는 표시다.

  4) 29번에서 음성 배경으로 쓴 분자를 표시한다. 그 분자들의 낮은 점수는
     모델이 외운 결과라 신뢰할 수 없다.

출력:
  data/screening/261124_screen_full_ranked.csv.gz   전체 순위
  data/screening/261124_screen_top2000.csv          상위 2,000
  data/screening/261124_screen_top100.xlsx          상위 100 (검토용)
  data/reports/261124_screen_score_profile.csv      점수 분포 — Cockroft Fig 9 대조
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import time
import pickle
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import rdFingerprintGenerator as rfg, Descriptors, RDConfig

RDLogger.DisableLog("rdApp.*")

MODEL = "data/models/261124_screen_model_ef.pkl"
COCONUT = "data/raw/coconut_csv-09-2026.csv"
NPASS = "data/raw/npass_structures.tsv"
FOODB = "data/raw/foodb_2020_4_7_csv/foodb_2020_04_07_csv/Compound.csv"
OUTDIR = "data/screening"
REPDIR = "data/reports"
CHUNK = 20_000
TOP_SIM = 20_000          # 유사도는 상위 이만큼 + 무작위 표본에만 계산(비용)
SEED = 42

# ---- NP-likeness (RDKit Contrib) ----------------------------------------------
try:
    sys.path.append(os.path.join(RDConfig.RDContribDir, "NP_Score"))
    import npscorer
    NPMODEL = npscorer.readNPModel()
except Exception as e:
    NPMODEL = None
    print(f"NP-likeness 사용 불가: {e}")

# ---- 모델 ---------------------------------------------------------------------
with open(MODEL, "rb") as f:
    B = pickle.load(f)
model, NB = B["model"], B["nbits"]
BG_IDS = B.get("background_ids", set())
KNOWN = set(B.get("known_active_smiles", []))
print(f"모델: {B['features']} {NB}bit x2 | active {B['n_active']:,} / "
      f"실측 inactive {B['n_inactive_real']:,} / 배경 {B['n_background']:,}")
print(f"  실측 Butina CV ROC-AUC {B['cv_roc_auc_real']:.3f}")

inv = rfg.GetMorganFeatureAtomInvGen()
GEN_E = rfg.GetMorganGenerator(radius=2, fpSize=NB)
GEN_F = rfg.GetMorganGenerator(radius=2, fpSize=NB, atomInvariantsGenerator=inv)
GEN_SIM = rfg.GetMorganGenerator(radius=2, fpSize=2048)

known_mols = [Chem.MolFromSmiles(s) for s in KNOWN]
act_fps = [GEN_SIM.GetFingerprint(m) for m in known_mols if m is not None]
act_smi = [s for s, m in zip(KNOWN, known_mols) if m is not None]
print(f"알려진 active {len(act_fps):,}개 (유사도 비교용)")


def featurize(mols):
    e = np.vstack([GEN_E.GetFingerprintAsNumPy(m) for m in mols])
    f = np.vstack([GEN_F.GetFingerprintAsNumPy(m) for m in mols])
    return np.hstack([e, f]).astype(np.float32)


# ---- 라이브러리 스트림 -----------------------------------------------------------
def streams():
    yield ("COCONUT", COCONUT, ",", "identifier", "canonical_smiles")
    yield ("NPASS", NPASS, "\t", "np_id", "SMILES")
    # FooDB CSV는 헤더가 한 칸 밀려 'cas_number' 컬럼에 SMILES가 들어 있다
    yield ("FooDB", FOODB, ",", "public_id", "cas_number")


print("\n" + "=" * 74)
print("스크리닝")
print("=" * 74)
rows, t0 = [], time.time()
for name, path, sep, idc, smic in streams():
    n, t1 = 0, time.time()
    for ch in pd.read_csv(path, sep=sep, usecols=[idc, smic], chunksize=CHUNK,
                          low_memory=False, on_bad_lines="skip"):
        ids, mols, canons = [], [], []
        for cid, smi in zip(ch[idc], ch[smic]):
            m = Chem.MolFromSmiles(str(smi))
            if m is None:
                continue
            ids.append(str(cid)); mols.append(m); canons.append(Chem.MolToSmiles(m))
        n += len(ch)
        if not mols:
            continue
        p = model.predict_proba(featurize(mols))[:, 1]
        rows.extend(zip([name] * len(ids), ids, canons, p.astype(np.float32)))
        if n % (CHUNK * 10) == 0:
            print(f"  [{name}] {n:,} 처리, 누적 {len(rows):,} ({time.time()-t1:.0f}s)")
    print(f"  [{name}] 완료 {n:,}행 → 유효 분자 누적 {len(rows):,} ({time.time()-t1:.0f}s)")

res = pd.DataFrame(rows, columns=["source", "id", "canonical_smiles", "active_prob"])
print(f"\n총 {len(res):,}개 예측 완료 ({time.time()-t0:.0f}s)")

# 같은 분자가 DB 여러 곳에 있으면 한 번만 (점수는 같다)
res = res.sort_values("active_prob", ascending=False)
dup = res.duplicated("canonical_smiles")
print(f"  DB 간 중복 {int(dup.sum()):,}개 제거 → 고유 분자 {int((~dup).sum()):,}개")
res = res[~dup].reset_index(drop=True)
res["rank"] = np.arange(1, len(res) + 1)
res["pct_rank"] = (res["rank"] / len(res) * 100).round(4)

# ---- 표시: 이미 알려진 것 / 학습 배경으로 쓴 것 -------------------------------------
res["is_known_active"] = res["canonical_smiles"].isin(KNOWN)
res["in_train_background"] = res["id"].isin(BG_IDS)
print(f"  학습 active와 동일: {int(res.is_known_active.sum()):,}개")
print(f"  29번 학습 배경으로 쓰임(점수 신뢰 불가): {int(res.in_train_background.sum()):,}개")

# ---- 적용 범위: 상위 + 무작위 표본에 유사도 계산 -------------------------------------
print(f"\n적용 범위 계산 — 상위 {TOP_SIM:,}개 + 무작위 표본 {TOP_SIM:,}개")
rng = np.random.default_rng(SEED)
top_idx = np.arange(min(TOP_SIM, len(res)))
rest = np.arange(len(top_idx), len(res))
samp_idx = rng.choice(rest, size=min(TOP_SIM, len(rest)), replace=False) if len(rest) else np.array([], int)
need = np.union1d(top_idx, samp_idx)

sim = np.full(len(res), np.nan, dtype=np.float32)
nnsmi = np.array([None] * len(res), dtype=object)
for k, i in enumerate(need):
    m = Chem.MolFromSmiles(res.canonical_smiles.iat[i])
    if m is None:
        continue
    s = DataStructs.BulkTanimotoSimilarity(GEN_SIM.GetFingerprint(m), act_fps)
    j = int(np.argmax(s))
    sim[i] = s[j]; nnsmi[i] = act_smi[j]
    if (k + 1) % 5000 == 0:
        print(f"  {k+1:,}/{len(need):,}")
res["max_sim_known"] = sim
res["nearest_active"] = nnsmi

# ---- NP-likeness + 합성 지표 (상위만) ------------------------------------------------
def halogen(m):
    return any(a.GetSymbol() in ("Cl", "Br", "I", "F") for a in m.GetAtoms())


npsc = np.full(len(res), np.nan, dtype=np.float32)
hal = np.array([None] * len(res), dtype=object)
mw = np.full(len(res), np.nan, dtype=np.float32)
for i in top_idx:
    m = Chem.MolFromSmiles(res.canonical_smiles.iat[i])
    if m is None:
        continue
    mw[i] = Descriptors.MolWt(m)
    hal[i] = halogen(m)
    if NPMODEL is not None:
        try:
            npsc[i] = npscorer.scoreMol(m, NPMODEL)
        except Exception:
            pass
res["np_score"] = npsc
res["has_halogen"] = hal
res["mw"] = mw

# ---- 저장 ------------------------------------------------------------------------
os.makedirs(OUTDIR, exist_ok=True)
os.makedirs(REPDIR, exist_ok=True)
res.to_csv(f"{OUTDIR}/261124_screen_full_ranked.csv.gz", index=False,
           encoding="utf-8-sig", compression="gzip")
top = res.head(2000)
top.to_csv(f"{OUTDIR}/261124_screen_top2000.csv", index=False, encoding="utf-8-sig")
cols = ["rank", "source", "id", "active_prob", "max_sim_known", "np_score",
        "mw", "has_halogen", "is_known_active", "in_train_background",
        "canonical_smiles", "nearest_active"]
with pd.ExcelWriter(f"{OUTDIR}/261124_screen_top100.xlsx", engine="openpyxl") as w:
    res.head(100)[cols].to_excel(w, sheet_name="top100", index=False)

# ---- 점수 분포 — Cockroft Figure 9 대조 ----------------------------------------------
print("\n" + "=" * 74)
print("점수 분포 — 절대 커트라인을 쓰면 안 되는 이유")
print("=" * 74)
bins = [(0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.01)]
prof = []
for a, b in bins:
    sel = (res.active_prob >= a) & (res.active_prob < b)
    prof.append({"구간": f"[{a:.2f}, {b:.2f})", "개수": int(sel.sum()),
                 "비율%": round(float(sel.mean() * 100), 2)})
    print(f"  {a:.2f} ~ {b:.2f}   {int(sel.sum()):>8,}개  {sel.mean()*100:6.2f}%")
pd.DataFrame(prof).to_csv(f"{REPDIR}/261124_screen_score_profile.csv",
                          index=False, encoding="utf-8-sig")

# ---- 출처별 — 건강기능식품 소재(FooDB)가 어디에 분포하는가 ---------------------------
# 29번에서 FooDB가 배경 할당량을 못 채웠다(70,477개 중 214개만 active 성질창 통과).
# active의 화학 공간과 식품 성분의 화학 공간이 거의 겹치지 않는다는 신호라,
# 과제 목표(건강기능식품 소재 발굴)에 직접 영향을 준다. 수치로 확인한다.
print("\n" + "=" * 74)
print("출처별 분포 — 식품 성분이 상위에 오는가")
print("=" * 74)
src_rows = []
for s, g in res.groupby("source"):
    in1k = int((g["rank"] <= 1000).sum())
    in10k = int((g["rank"] <= 10000).sum())
    src_rows.append({"출처": s, "분자수": len(g),
                     "점수중앙값": round(float(g.active_prob.median()), 4),
                     "상위1000": in1k, "상위10000": in10k,
                     "상위1000_기대": round(len(g) / len(res) * 1000, 1),
                     "농축배수": round(in1k / max(len(g) / len(res) * 1000, 1e-9), 2)})
srcdf = pd.DataFrame(src_rows).sort_values("분자수", ascending=False)
print(srcdf.to_string(index=False))
srcdf.to_csv(f"{REPDIR}/261124_screen_by_source.csv", index=False, encoding="utf-8-sig")
print(f"\n  기존 08b는 prob >= 0.5 로 잘랐다 → 이번 기준으로 "
      f"{int((res.active_prob >= 0.5).sum()):,}개가 남는다")
print(f"  상위 2,000위의 점수 하한: {res.active_prob.iat[min(1999, len(res)-1)]:.3f}")
print(f"  상위 100위 적용범위(max_sim_known) 중앙값: "
      f"{np.nanmedian(res.max_sim_known.values[:100]):.3f}")

print(f"\n저장 → {OUTDIR}/261124_screen_full_ranked.csv.gz")
print(f"저장 → {OUTDIR}/261124_screen_top2000.csv")
print(f"저장 → {OUTDIR}/261124_screen_top100.xlsx")
