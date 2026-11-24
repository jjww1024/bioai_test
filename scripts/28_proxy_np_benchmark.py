# -*- coding: utf-8 -*-
"""외부 천연물 시험셋 설계 2단계 — 합성물→천연물 낙폭을 대리 타깃에서 측정한다.

측정하려는 값 하나:
    "합성물로 학습한 SDR 억제 모델을, 학습에 쓰지 않은 천연물로 시험하면
     성능이 몇 % 떨어지는가"

HSD17B13에는 천연물 활성이 0개라(26번) 직접 잴 수 없다. 그래서 합성물과
천연물이 둘 다 있는 가까운 효소에서 재고, 그 낙폭을 HSD17B13 모델의
기대치로 쓴다. Cockroft가 1,907개 타깃에서 한 측정의 축소판이다.

타깃마다 두 숫자를 낸다.
    내부 기준  = 합성물만으로 Butina 군집 교차검증 (우리가 지금 보고하는 종류의 값)
    외부 시험  = 그 합성물 전부로 학습 → 천연물 세트 예측 (한 번도 안 본 데이터)
    낙폭       = 내부 - 외부

프로토콜은 27번의 판정을 따른다.
    A (라벨 대조)   천연물 쪽에 실측 active/inactive가 둘 다 충분
                   → 실측 라벨끼리 AUROC·BEDROC 비교. 가장 깨끗하다.
    B (스파이크 농축) 천연물 inactive가 모자람
                   → 천연물 active를 '성질을 맞춘' COCONUT 배경에 섞고 농축도를 본다.
                     배경을 비활성으로 가정하므로 논문과 같은 한계를 진다.
                     배경은 우리가 실제로 스크리닝하는 라이브러리에서 뽑는다.

지문은 25c에서 고른 ECFP4+FCFP4 결합을 쓴다.

출력:
  data/reports/261124_np_penalty.csv
  data/reports/261124_np_penalty.png
  data/reports/261124_np_similarity_gap.csv
"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import rdFingerprintGenerator as rfg, Descriptors, Crippen
from rdkit.ML.Cluster import Butina
from rdkit.ML.Scoring import Scoring
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import roc_auc_score
from lightgbm import LGBMClassifier
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RDLogger.DisableLog("rdApp.*")

PROXY = "data/processed/261124_proxy_targets.csv"
FEAS = "data/reports/261124_proxy_feasibility.csv"
COCONUT = "data/raw/coconut_csv-09-2026.csv"
OUTDIR = "data/reports"
SEED = 42
NFOLD = 5
ALPHA = 20.0
CLUSTER_CUTOFF = 0.4
BG_PER_ACTIVE = 50        # 프로토콜 B: active 1개당 배경 50개

inv = rfg.GetMorganFeatureAtomInvGen()
GEN_E = rfg.GetMorganGenerator(radius=2, fpSize=1024)
GEN_F = rfg.GetMorganGenerator(radius=2, fpSize=1024, atomInvariantsGenerator=inv)


def featurize(mols):
    """25c에서 고른 ECFP4+FCFP4 결합 표현."""
    e = np.vstack([GEN_E.GetFingerprintAsNumPy(m) for m in mols])
    f = np.vstack([GEN_F.GetFingerprintAsNumPy(m) for m in mols])
    return np.hstack([e, f]).astype(np.float32)


def parse(smiles):
    out, idx = [], []
    for i, s in enumerate(smiles):
        m = Chem.MolFromSmiles(str(s))
        if m is not None:
            out.append(m); idx.append(i)
    return out, np.array(idx)


def bedroc(y_true, score, alpha=ALPHA):
    order = np.argsort(-score)
    return Scoring.CalcBEDROC([[int(v)] for v in np.asarray(y_true)[order]], 0, alpha)


def ef(y_true, score, frac=0.01):
    y_true = np.asarray(y_true)
    k = max(int(round(len(y_true) * frac)), 1)
    order = np.argsort(-score)[:k]
    base = y_true.mean()
    return y_true[order].mean() / base if base > 0 else np.nan


def butina_groups(mols):
    fps = [GEN_E.GetFingerprint(m) for m in mols]
    n = len(fps)
    d = []
    for i in range(1, n):
        d.extend(1.0 - s for s in DataStructs.BulkTanimotoSimilarity(fps[i], fps[:i]))
    cl = Butina.ClusterData(d, n, CLUSTER_CUTOFF, isDistData=True)
    g = np.empty(n, dtype=int)
    for cid, mem in enumerate(cl):
        for i in mem:
            g[i] = cid
    return g, fps


# ---- 입력 --------------------------------------------------------------------
comps = pd.read_csv(PROXY)
feas = pd.read_csv(FEAS)
print(f"대리 타깃 {comps.gene.nunique()}개 / 화합물 {len(comps):,}개")

# 프로토콜 B용 배경 라이브러리 (필요할 때만 적재)
_bg_cache = {"df": None}


def background_pool():
    if _bg_cache["df"] is None:
        print("  COCONUT 배경 라이브러리 적재 중...")
        rows = []
        for ch in pd.read_csv(COCONUT, usecols=["canonical_smiles", "molecular_weight", "alogp"],
                              chunksize=200_000, low_memory=False):
            ch = ch.dropna()
            rows.append(ch.sample(min(len(ch), 20_000), random_state=SEED))
        bg = pd.concat(rows, ignore_index=True)
        _bg_cache["df"] = bg
        print(f"  배경 후보 {len(bg):,}개")
    return _bg_cache["df"]


def matched_background(np_actives_mols, n_need):
    """active의 분자량·logP 분포에 맞춰 배경을 고른다.
    성질을 안 맞추면 decoy 함정(25번)을 그대로 반복하게 된다."""
    bg = background_pool()
    mw = np.array([Descriptors.MolWt(m) for m in np_actives_mols])
    lp = np.array([Crippen.MolLogP(m) for m in np_actives_mols])
    lo_mw, hi_mw = np.percentile(mw, [5, 95])
    lo_lp, hi_lp = np.percentile(lp, [5, 95])
    sel = bg[(bg.molecular_weight.between(lo_mw, hi_mw)) &
             (bg.alogp.between(lo_lp, hi_lp))]
    if len(sel) < n_need:
        sel = bg
    return sel.sample(min(n_need, len(sel)), random_state=SEED)["canonical_smiles"].tolist()


# ---- 타깃별 측정 ---------------------------------------------------------------
print("\n" + "=" * 100)
print("대리 타깃별 내부 기준 대 외부 천연물 시험")
print("=" * 100)

results, simrows = [], []
for _, frow in feas.iterrows():
    gene, proto = frow["gene"], frow["프로토콜"]
    # 27번이 '불가'로 판정한 타깃도, 천연물 active가 5개 이상이면 저신뢰 B로 돌린다.
    # 1순위 17b-HSD가 둘이나 탈락해 표본이 너무 얇아지기 때문. 대신 신뢰도를 표시한다.
    if proto.startswith("불가"):
        if int(frow["천연물_active"]) >= 5:
            proto = "B (저신뢰 n<10)"
        else:
            print(f"  {gene:9s} 건너뜀 — 천연물 active {int(frow['천연물_active'])}개")
            continue
    sub = comps[comps.gene == gene]
    syn = sub[~sub.is_np].reset_index(drop=True)
    npd = sub[sub.is_np].reset_index(drop=True)

    smols, sidx = parse(syn.canonical_smiles)
    sy = syn.label.to_numpy()[sidx]
    if sy.sum() < 20 or (sy == 0).sum() < 20:
        print(f"  {gene:9s} 건너뜀 — 합성물 라벨 불균형")
        continue
    SX = featurize(smols)
    groups, sfps = butina_groups(smols)

    # (a) 내부 기준 — 합성물 Butina 교차검증
    proba = np.zeros(len(sy))
    sp = StratifiedGroupKFold(NFOLD, shuffle=True, random_state=SEED)
    for tr, te in sp.split(SX, sy, groups):
        c = LGBMClassifier(n_estimators=300, class_weight="balanced",
                           random_state=SEED, n_jobs=-1, verbosity=-1).fit(SX[tr], sy[tr])
        proba[te] = c.predict_proba(SX[te])[:, 1]
    in_auc, in_bed, in_ef = roc_auc_score(sy, proba), bedroc(sy, proba), ef(sy, proba)

    # (b) 외부 시험 — 합성물 전부로 학습 후 천연물 예측
    model = LGBMClassifier(n_estimators=300, class_weight="balanced",
                           random_state=SEED, n_jobs=-1, verbosity=-1).fit(SX, sy)

    if proto.startswith("A"):
        nmols, nidx = parse(npd.canonical_smiles)
        ny = npd.label.to_numpy()[nidx]
        used = "실측 천연물 active/inactive"
    else:
        act = npd[npd.label == 1]
        amols, aidx = parse(act.canonical_smiles)
        bg_smi = matched_background(amols, len(amols) * BG_PER_ACTIVE)
        bmols, _ = parse(bg_smi)
        nmols = amols + bmols
        ny = np.r_[np.ones(len(amols), int), np.zeros(len(bmols), int)]
        used = f"천연물 active {len(amols)} + 성질맞춤 배경 {len(bmols)}"

    NX = featurize(nmols)
    npro = model.predict_proba(NX)[:, 1]
    ex_auc, ex_bed, ex_ef = roc_auc_score(ny, npro), bedroc(ny, npro), ef(ny, npro)

    # (c) 화학공간 간격 — 이 낙폭이 우리 상황에 옮겨지는지 판단하는 근거
    nfps = [GEN_E.GetFingerprint(m) for m in nmols]
    nn = np.array([max(DataStructs.BulkTanimotoSimilarity(f, sfps)) for f in nfps])
    simrows.append({"gene": gene, "천연물_최근접_중앙값": round(float(np.median(nn)), 3),
                    "0.4미만%": round(float((nn < 0.4).mean() * 100), 1)})

    results.append({
        "gene": gene, "tier": frow["tier"], "프로토콜": proto, "시험구성": used,
        "합성물수": len(sy), "시험분자수": len(ny), "시험active": int(ny.sum()),
        "내부_AUC": in_auc, "외부_AUC": ex_auc, "AUC낙폭": in_auc - ex_auc,
        "내부_BEDROC": in_bed, "외부_BEDROC": ex_bed, "BEDROC낙폭": in_bed - ex_bed,
        "내부_EF1": in_ef, "외부_EF1": ex_ef,
        "천연물_최근접": round(float(np.median(nn)), 3),
    })
    print(f"  {gene:9s} [{proto[:1]}] 내부 AUC {in_auc:.3f} → 외부 {ex_auc:.3f} "
          f"(낙폭 {in_auc - ex_auc:+.3f}) | BEDROC {in_bed:.3f} → {ex_bed:.3f} "
          f"| 천연물 최근접 {np.median(nn):.3f}")

res = pd.DataFrame(results)
os.makedirs(OUTDIR, exist_ok=True)
res.to_csv(f"{OUTDIR}/261124_np_penalty.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(simrows).to_csv(f"{OUTDIR}/261124_np_similarity_gap.csv",
                             index=False, encoding="utf-8-sig")

# ---- 집계: HSD17B13 기대 낙폭 ---------------------------------------------------
print("\n" + "=" * 100)
print("[집계] HSD17B13 모델의 기대 낙폭")
print("=" * 100)
t1 = res[res.tier.str.contains("1순위")]
t1hi = t1[~t1["프로토콜"].astype(str).str.contains("저신뢰")]
for nm, grp in [("17b-HSD 1순위 (고신뢰만)", t1hi),
                ("17b-HSD 1순위 전체", t1), ("전체 대리 타깃", res)]:
    if not len(grp):
        continue
    print(f"  {nm:16s} AUC 낙폭 {grp['AUC낙폭'].mean():+.3f} "
          f"(범위 {grp['AUC낙폭'].min():+.3f} ~ {grp['AUC낙폭'].max():+.3f})   "
          f"BEDROC 낙폭 {grp['BEDROC낙폭'].mean():+.3f}")

OUR_INTERNAL = 0.895      # 25c의 ECFP4+FCFP4 Butina AUC
if len(t1):
    d = t1["AUC낙폭"].mean()
    print(f"\n  우리 HSD17B13 내부 성능(25c, Butina)  AUC {OUR_INTERNAL:.3f}")
    print(f"  → 천연물에서의 기대 AUC          약 {OUR_INTERNAL - d:.3f}")
    print(f"    (1순위 대리 타깃 평균 낙폭 {d:.3f} 적용)")

print("\n[주의] 이 추정이 성립하려면 대리 타깃의 '합성물→천연물 간격'이")
print("       우리 상황과 비슷해야 한다. 간격 비교:")
print(pd.DataFrame(simrows).to_string(index=False))
print("       우리 HSD17B13 학습셋 ↔ 스크리닝 천연물 Tanimoto는 0.18~0.20 수준이다.")
print("       위 값들이 그보다 훨씬 높으면, 실제 낙폭은 여기 추정치보다 클 것이다.")

# ---- 그림 ----------------------------------------------------------------------
if len(res):
    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    x = np.arange(len(res))
    for ax, (a, b, title) in zip(axes, [
            ("내부_AUC", "외부_AUC", "ROC-AUC"),
            ("내부_BEDROC", "외부_BEDROC", "BEDROC (α=20)")]):
        ax.bar(x - 0.19, res[a], 0.38, label="내부 (합성물 CV)", color="#9fb6cd")
        ax.bar(x + 0.19, res[b], 0.38, label="외부 (천연물)", color="#c75d4d")
        ax.set_xticks(x); ax.set_xticklabels(res.gene, rotation=15, fontsize=9)
        ax.set_title(title, fontsize=11); ax.set_ylim(0, 1.02)
        ax.grid(axis="y", alpha=0.25); ax.legend(fontsize=8.5)
    fig.suptitle("대리 타깃에서 측정한 합성물→천연물 낙폭", fontsize=12.5)
    fig.tight_layout()
    fig.savefig(f"{OUTDIR}/261124_np_penalty.png", dpi=150)

print(f"\n저장 → {OUTDIR}/261124_np_penalty.csv / .png")
