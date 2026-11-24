# -*- coding: utf-8 -*-
"""방향 전환 — 천연물 영역 안에서 모델을 만든다 (nnPU).

32번 결과가 길을 막았다. 활성을 가를 수 있는 모든 표현(ECFP4/FCFP4/결합/
MACCS/2D descriptor)에서 '학습 active 대 천연물' 영역 분류 AUC가 0.9999 이상이다.
활성 정보와 영역 정보가 같은 축에 실려 있어 분리가 안 된다. 합성물로 배워
천연물을 판별하는 일은 표현을 바꾸든 손실함수를 바꾸든 안 된다.

그래서 양성의 출처를 바꾼다.
  기존:  P = HSD17B13 합성 억제제 1,915개   (천연물과 영역이 완전히 다름)
  이번:  P = SDR/AKR 패밀리를 저해하는 '천연물' 87개 (27번에서 DB 대조로 확정)
         U = 천연물 라이브러리                (같은 영역)

P와 U가 같은 영역에 있으므로 '합성 대 천연' 축이 사라진다. 대신 P가 87개로
아주 적다. 적은 양성 + 많은 미분류 = nnPU가 정확히 상정한 상황이다
(Kiryo et al. 2017: "limited P data"에서 유연한 모델을 쓰려고 만든 추정량).

이 모델이 예측하는 것은 'HSD17B13 활성'이 아니라 'SDR/AKR 계열 저해 천연물
다움'이다. 더 약한 주장이지만, 적어도 묻는 공간 안에서 묻는다.

절차:
  1. 타당성 검사 — P(패밀리 천연물 active) 대 U(천연물 라이브러리) 영역 분류 AUC.
     1.0에 가까우면 이 길도 막힌 것이다.
  2. 막히지 않았으면 nnPU 학습 후 라이브러리 전체 채점.
  3. 기존 합성물 모델 순위와 비교 — 할로겐 편향이 사라졌는지 확인.

출력:
  data/reports/261124_npdomain_viability.csv
  data/screening/261124_npdomain_ranked.csv.gz
  data/reports/261124_npdomain_compare.csv / .png
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
sys.path.insert(0, "scripts")
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger, RDConfig
from rdkit.Chem import rdFingerprintGenerator as rfg
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier
sys.path.append(os.path.join(RDConfig.RDContribDir, "NP_Score"))
import npscorer
from nnpu import fit_nnpu, predict_score
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RDLogger.DisableLog("rdApp.*")
NPM = npscorer.readNPModel()

PROXY = "data/processed/261124_proxy_targets.csv"
SCREEN = "data/screening/261124_screen_full_ranked.csv.gz"
OUTDIR = "data/reports"
SCRDIR = "data/screening"
SEED = 42
NB = 1024
N_U_TRAIN = 20_000      # nnPU 학습에 쓸 미분류 표본
PI_P_GRID = [0.001, 0.005, 0.02]   # 클래스 사전확률 — 라이브러리 중 진짜 양성 비율 가정

inv = rfg.GetMorganFeatureAtomInvGen()
GE = rfg.GetMorganGenerator(radius=2, fpSize=NB)
GF = rfg.GetMorganGenerator(radius=2, fpSize=NB, atomInvariantsGenerator=inv)


def feats(mols):
    e = np.vstack([GE.GetFingerprintAsNumPy(m) for m in mols])
    f = np.vstack([GF.GetFingerprintAsNumPy(m) for m in mols])
    return np.hstack([e, f]).astype(np.float32)


def parse(smis):
    out = []
    for s in smis:
        m = Chem.MolFromSmiles(str(s))
        if m is not None:
            out.append(m)
    return out


def halogen_frac(mols):
    return float(np.mean([any(a.GetSymbol() in ("Cl", "Br", "I", "F")
                              for a in m.GetAtoms()) for m in mols]))


def np_median(mols):
    v = []
    for m in mols:
        try:
            v.append(npscorer.scoreMol(m, NPM))
        except Exception:
            pass
    return float(np.median(v)) if v else np.nan


# ---- P: 패밀리 천연물 active -------------------------------------------------------
px = pd.read_csv(PROXY)
pos = px[(px.is_np) & (px.label == 1)].drop_duplicates("canonical_smiles")
print("패밀리 천연물 active (타깃별):")
print(pos.gene.value_counts().to_string())
pmols = parse(pos.canonical_smiles)
print(f"  고유 양성 {len(pmols)}개")

# ---- U: 천연물 라이브러리 ------------------------------------------------------------
scr = pd.read_csv(SCREEN, usecols=["source", "id", "canonical_smiles",
                                   "active_prob", "rank"], low_memory=False)
print(f"라이브러리 {len(scr):,}개")
pos_smiles = set(Chem.MolToSmiles(m) for m in pmols)
pool = scr[~scr.canonical_smiles.isin(pos_smiles)]
u_samp = pool.sample(N_U_TRAIN, random_state=SEED)
umols = parse(u_samp.canonical_smiles)
print(f"  미분류 학습표본 {len(umols):,}개")

# ---- 1. 타당성 검사 ------------------------------------------------------------------
print("\n" + "=" * 78)
print("[1] 타당성 — P(패밀리 천연물 active) 대 U(천연물 라이브러리)가 갈리는가")
print("    1.0에 가까우면 이 길도 막힌 것이다")
print("=" * 78)
u_small = parse(pool.sample(3000, random_state=SEED + 1).canonical_smiles)
Xd = feats(pmols + u_small)
yd = np.r_[np.ones(len(pmols), int), np.zeros(len(u_small), int)]
pdm = np.zeros(len(yd))
for tr, te in StratifiedKFold(5, shuffle=True, random_state=SEED).split(Xd, yd):
    pdm[te] = LGBMClassifier(n_estimators=300, class_weight="balanced", random_state=SEED,
                             n_jobs=-1, verbosity=-1).fit(Xd[tr], yd[tr]).predict_proba(Xd[te])[:, 1]
dom_np = roc_auc_score(yd, pdm)
print(f"  영역 분류 AUC {dom_np:.4f}   (참고: 합성 active 대 천연물은 1.0000)")
viable = dom_np < 0.99
print(f"  → {'여지 있음. 진행한다' if viable else '막혔다. 이 길도 불가'}")

print(f"\n  양성 87개 성질 : 할로겐 {halogen_frac(pmols)*100:.1f}%  "
      f"NP-likeness {np_median(pmols):+.2f}")
print(f"  라이브러리 성질 : 할로겐 {halogen_frac(u_small)*100:.1f}%  "
      f"NP-likeness {np_median(u_small):+.2f}")
pd.DataFrame([{"영역분류_AUC_천연물기반": round(dom_np, 4),
               "영역분류_AUC_합성기반": 1.0,
               "n_positive": len(pmols), "n_unlabeled": len(u_small),
               "진행가능": viable}]).to_csv(
    f"{OUTDIR}/261124_npdomain_viability.csv", index=False, encoding="utf-8-sig")

if not viable:
    print("\n타당성 검사를 통과하지 못해 nnPU 학습을 건너뛴다.")
    sys.exit(0)

# ---- 2. nnPU 학습 ---------------------------------------------------------------------
print("\n" + "=" * 78)
print("[2] nnPU 학습 (Kiryo et al. 2017) — 미분류를 음성으로 단정하지 않는다")
print("=" * 78)
Xp = feats(pmols)
Xu = feats(umols)
models = {}
for pi in PI_P_GRID:
    print(f"  pi_p = {pi}")
    models[pi] = fit_nnpu(Xp, Xu, pi_p=pi, epochs=30, batch=512,
                          lr=3e-4, beta=0.0, gamma=1.0, seed=SEED, verbose=True)

# ---- 3. 라이브러리 채점 + 비교 -----------------------------------------------------------
print("\n" + "=" * 78)
print("[3] 라이브러리 채점 및 기존 합성물 모델과 비교")
print("=" * 78)
score_n = min(200_000, len(scr))
sub = scr.sample(score_n, random_state=SEED).reset_index(drop=True)
mols_sub, idx_ok = [], []
for i, s in enumerate(sub.canonical_smiles):
    m = Chem.MolFromSmiles(str(s))
    if m is not None:
        mols_sub.append(m); idx_ok.append(i)
sub = sub.loc[idx_ok].reset_index(drop=True)
Xs = feats(mols_sub)
print(f"  채점 대상 {len(sub):,}개 (전체에서 무작위 추출)")

rows = []
for pi, mdl in models.items():
    s = predict_score(mdl, Xs)
    col = f"nnpu_{pi}"
    sub[col] = s
    top = sub.nlargest(200, col)
    tm = [mols_sub[i] for i in top.index]
    rows.append({"모델": f"nnPU pi={pi}", "상위200_할로겐%": round(halogen_frac(tm) * 100, 1),
                 "상위200_NPlikeness": round(np_median(tm), 2),
                 "기존모델순위_중앙값": int(top["rank"].median())})
    print(f"  nnPU pi={pi}: 상위200 할로겐 {halogen_frac(tm)*100:5.1f}%  "
          f"NP-likeness {np_median(tm):+.2f}")

old_top = sub.nsmallest(200, "rank")
om = [mols_sub[i] for i in old_top.index]
rows.append({"모델": "기존 합성물 모델", "상위200_할로겐%": round(halogen_frac(om) * 100, 1),
             "상위200_NPlikeness": round(np_median(om), 2),
             "기존모델순위_중앙값": int(old_top["rank"].median())})
print(f"  기존 합성물 모델: 상위200 할로겐 {halogen_frac(om)*100:5.1f}%  "
      f"NP-likeness {np_median(om):+.2f}")
base_h, base_n = halogen_frac(mols_sub) * 100, np_median(mols_sub)
rows.append({"모델": "라이브러리 기준선", "상위200_할로겐%": round(base_h, 1),
             "상위200_NPlikeness": round(base_n, 2), "기존모델순위_중앙값": None})
print(f"  라이브러리 기준선: 할로겐 {base_h:5.1f}%  NP-likeness {base_n:+.2f}")

cmp = pd.DataFrame(rows)
cmp.to_csv(f"{OUTDIR}/261124_npdomain_compare.csv", index=False, encoding="utf-8-sig")
sub.sort_values(f"nnpu_{PI_P_GRID[1]}", ascending=False).to_csv(
    f"{SCRDIR}/261124_npdomain_ranked.csv.gz", index=False,
    encoding="utf-8-sig", compression="gzip")

# ---- 그림 ----------------------------------------------------------------------------
plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
lbl = cmp["모델"].tolist()
x = np.arange(len(lbl))
for ax, col, title, base in [
        (axes[0], "상위200_할로겐%", "상위 200의 할로겐 보유율", base_h),
        (axes[1], "상위200_NPlikeness", "상위 200의 NP-likeness", base_n)]:
    c = ["#2f5d50"] * len(PI_P_GRID) + ["#c75d4d", "#9fb6cd"]
    ax.bar(x, cmp[col], 0.6, color=c[:len(lbl)])
    ax.axhline(base, ls="--", lw=1.2, color="#555")
    ax.set_xticks(x); ax.set_xticklabels(lbl, rotation=18, ha="right", fontsize=8.5)
    ax.set_title(title, fontsize=11); ax.grid(axis="y", alpha=0.25)
fig.suptitle("천연물 영역 nnPU 모델 대 기존 합성물 모델 (점선 = 라이브러리 기준선)",
             fontsize=12)
fig.tight_layout()
fig.savefig(f"{OUTDIR}/261124_npdomain_compare.png", dpi=150)
print(f"\n저장 → {OUTDIR}/261124_npdomain_viability.csv / _compare.csv / .png")
print(f"저장 → {SCRDIR}/261124_npdomain_ranked.csv.gz")
