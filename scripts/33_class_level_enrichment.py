# -*- coding: utf-8 -*-
"""클래스 단위 집계 — 개별 점수를 못 믿을 때 분포 이동을 본다.

착상은 Yang et al., J. Agric. Food Chem. 2025 (PMC12593347)에서 왔다.
그 논문은 플라보노이드 20종을 등몰 혼합해 '클래스 기준물'로 쓰면 개별 화합물의
특이 효과가 희석되고 클래스 공통 활성이 드러난다는 것을 습식으로 보였다.
여기서는 그 발상을 계산 쪽으로 옮긴다 — 개별 분자를 보지 말고 클래스를 본다.

왜 필요한가:
  30번 스크리닝에서 상위 100개의 적용범위(max_sim_known) 중앙값이 0.200이었다.
  개별 예측은 전부 외삽이라 한 분자의 점수는 믿을 근거가 없다.
  그러나 어떤 클래스 수백 개가 통째로 위쪽으로 쏠린다면, 그 '이동'은
  개별 점수보다 훨씬 안정적인 통계량이다.

중요한 자기검증:
  31번에서 확인했듯 모델은 '활성'이 아니라 '학습 영역과의 근접도'를 재고 있을
  수 있다. 그렇다면 클래스 농축도 똑같은 허상일 뿐이다.
  그래서 클래스별 농축이 그 클래스의 할로겐 보유율·NP-likeness와 얼마나
  상관되는지 같이 계산한다. 상관이 높으면 농축은 신호가 아니라 영역 효과다.

출력:
  data/reports/261124_class_enrichment.csv
  data/reports/261124_class_enrichment.png
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
from scipy.stats import mannwhitneyu, spearmanr
from rdkit import Chem, RDLogger, RDConfig
sys.path.append(os.path.join(RDConfig.RDContribDir, "NP_Score"))
import npscorer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RDLogger.DisableLog("rdApp.*")
NPM = npscorer.readNPModel()

SCREEN = "data/screening/261124_screen_full_ranked.csv.gz"
COCONUT = "data/raw/coconut_csv-09-2026.csv"
OUTDIR = "data/reports"
MIN_N = 30            # 이보다 작은 클래스는 통계가 안 된다
SAMPLE_PER_CLASS = 60  # 할로겐·NP-likeness 계산용 표본 (전수는 비용이 큼)
SEED = 42

# ---- 스크리닝 결과 ---------------------------------------------------------------
scr = pd.read_csv(SCREEN, usecols=["source", "id", "canonical_smiles",
                                   "active_prob", "rank", "pct_rank"],
                  low_memory=False)
print(f"스크리닝 결과 {len(scr):,}개")

# ---- COCONUT 클래스 주석 붙이기 ----------------------------------------------------
cols = ["identifier", "np_classifier_pathway", "np_classifier_superclass",
        "np_classifier_class", "np_classifier_is_glycoside"]
parts = []
for ch in pd.read_csv(COCONUT, usecols=cols, chunksize=200_000,
                      low_memory=False, on_bad_lines="skip"):
    parts.append(ch)
ann = pd.concat(parts, ignore_index=True)
ann["identifier"] = ann["identifier"].astype(str)
print(f"COCONUT 주석 {len(ann):,}개")

d = scr[scr.source == "COCONUT"].merge(ann, left_on="id", right_on="identifier", how="left")
print(f"COCONUT 분자 {len(d):,}개 중 클래스 주석 있는 것 "
      f"{int(d.np_classifier_class.notna().sum()):,}개")

N = len(scr)   # 전체 라이브러리 기준 순위를 쓴다


def enrich(level):
    """클래스별 순위 분포가 라이브러리 전체 대비 위로 쏠렸는지 검정."""
    rows = []
    allr = d["pct_rank"].to_numpy()
    for name, g in d.groupby(level):
        if len(g) < MIN_N or not isinstance(name, str):
            continue
        r = g["pct_rank"].to_numpy()
        other = allr[~np.isin(np.arange(len(allr)), g.index.values)] if False else allr
        # 단측: 이 클래스의 백분위 순위가 더 '작다'(=더 상위)인가
        try:
            u, p = mannwhitneyu(r, other, alternative="less")
        except ValueError:
            continue
        # 공통언어 효과크기: 무작위로 뽑은 이 클래스 분자가 라이브러리 분자보다 상위일 확률
        cles = 1.0 - u / (len(r) * len(other))
        rows.append({
            "level": level, "class": name, "n": len(g),
            "중앙_백분위": round(float(np.median(r)), 3),
            "상위1%_개수": int((g["rank"] <= N * 0.01).sum()),
            "상위1%_기대": round(len(g) * 0.01, 1),
            "농축배수": round(float((g["rank"] <= N * 0.01).sum() / max(len(g) * 0.01, 1e-9)), 2),
            "효과크기": round(float(1 - cles), 3),
            "p": p,
        })
    out = pd.DataFrame(rows)
    if not len(out):
        return out
    # Benjamini-Hochberg
    out = out.sort_values("p").reset_index(drop=True)
    m = len(out)
    out["q"] = (out["p"] * m / (out.index + 1)).cummin().clip(upper=1.0)
    return out


res = pd.concat([enrich(lv) for lv in
                 ["np_classifier_pathway", "np_classifier_superclass", "np_classifier_class"]],
                ignore_index=True)
res = res.sort_values(["level", "농축배수"], ascending=[True, False])

# ---- 자기검증: 농축이 할로겐·합성스러움과 상관되는가 ------------------------------------
print("\n" + "=" * 82)
print("자기검증 — 클래스 농축이 '활성 신호'인가 '영역 효과'인가")
print("=" * 82)
rng = np.random.default_rng(SEED)
prof = []
cls_level = res[res.level == "np_classifier_class"]
for _, r in cls_level.iterrows():
    g = d[d["np_classifier_class"] == r["class"]]
    s = g.sample(min(SAMPLE_PER_CLASS, len(g)), random_state=SEED)
    hal, nps = [], []
    for smi in s.canonical_smiles:
        m = Chem.MolFromSmiles(str(smi))
        if m is None:
            continue
        hal.append(any(a.GetSymbol() in ("Cl", "Br", "I", "F") for a in m.GetAtoms()))
        try:
            nps.append(npscorer.scoreMol(m, NPM))
        except Exception:
            pass
    if hal:
        prof.append({"class": r["class"], "할로겐%": float(np.mean(hal) * 100),
                     "NP_likeness": float(np.median(nps)) if nps else np.nan})
pf = pd.DataFrame(prof)
cls_level = cls_level.merge(pf, on="class", how="left")

rho_h, p_h = spearmanr(cls_level["농축배수"], cls_level["할로겐%"], nan_policy="omit")
rho_n, p_n = spearmanr(cls_level["농축배수"], cls_level["NP_likeness"], nan_policy="omit")
print(f"  농축배수 대 할로겐보유율    Spearman rho {rho_h:+.3f}  (p={p_h:.2e})")
print(f"  농축배수 대 NP-likeness   Spearman rho {rho_n:+.3f}  (p={p_n:.2e})")
if rho_h > 0.4:
    print("  → 농축은 상당 부분 '할로겐화된, 합성스러운 클래스'를 고른 결과다.")
    print("    활성 신호로 읽으면 안 된다.")
else:
    print("  → 농축이 할로겐 보유율로 설명되지 않는다. 별개 신호일 여지가 있다.")

# ---- 출력 -------------------------------------------------------------------------
os.makedirs(OUTDIR, exist_ok=True)
res.to_csv(f"{OUTDIR}/261124_class_enrichment.csv", index=False, encoding="utf-8-sig")
cls_level.to_csv(f"{OUTDIR}/261124_class_enrichment_audited.csv",
                 index=False, encoding="utf-8-sig")

for lv, label in [("np_classifier_pathway", "경로(pathway)"),
                  ("np_classifier_superclass", "상위클래스(superclass)")]:
    sub = res[res.level == lv].head(12)
    print(f"\n{'='*82}\n[{label}] 상위 농축\n{'='*82}")
    print(sub[["class", "n", "중앙_백분위", "상위1%_개수", "상위1%_기대",
               "농축배수", "효과크기", "q"]].to_string(index=False))

print(f"\n{'='*82}\n[클래스(class)] 농축 상위 15 — 할로겐·NP-likeness 동반 표시\n{'='*82}")
show = cls_level.head(15)[["class", "n", "농축배수", "효과크기", "q", "할로겐%", "NP_likeness"]]
print(show.to_string(index=False))

# ---- 그림 ---------------------------------------------------------------------------
plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
fig, axes = plt.subplots(1, 2, figsize=(13.5, 5))
ax = axes[0]
sub = res[res.level == "np_classifier_pathway"].sort_values("농축배수")
ax.barh(sub["class"], sub["농축배수"], color="#c75d4d")
ax.axvline(1.0, ls="--", lw=1.2, color="#555")
ax.set_xlabel("상위 1% 농축배수 (1.0 = 기대값)")
ax.set_title("천연물 경로별 농축", fontsize=11)
ax.grid(axis="x", alpha=0.25)

ax = axes[1]
ax.scatter(cls_level["할로겐%"], cls_level["농축배수"], s=28, alpha=0.7, color="#2f5d50")
ax.set_xlabel("클래스의 할로겐 보유율 (%)")
ax.set_ylabel("상위 1% 농축배수")
ax.set_title(f"자기검증: 농축 대 할로겐  (Spearman ρ={rho_h:+.2f})", fontsize=11)
ax.grid(alpha=0.25)
fig.tight_layout()
fig.savefig(f"{OUTDIR}/261124_class_enrichment.png", dpi=150)
print(f"\n저장 → {OUTDIR}/261124_class_enrichment.csv / _audited.csv / .png")
