# -*- coding: utf-8 -*-
"""30번 스크리닝 결과 진단 — 모델이 무엇을 보고 상위를 고르고 있는가.

30번에서 두 가지가 눈에 띄었다.
  - 전체의 99.97%가 점수 0.25 미만 (Cockroft Figure 9가 경고한 그대로, 더 심하게)
  - 상위 100개의 99%가 할로겐 함유 (라이브러리 기준선은 6.4%)

두 번째가 문제다. 학습 active의 92.5%가 할로겐을 갖고 있고(평균 2.77개)
NP-likeness 중앙값이 -1.03 이다. 즉 학습셋 전체가 '할로겐화된 합성 의약화학
공간'에 들어 있다. 그런데 할로겐 보유율은 active 92.5% 대 inactive 87.9%로
거의 같다 — 활성을 가르는 신호가 아니라 '학습 영역'을 표시하는 꼬리표다.

모델이 천연물 80만 개에서 상위로 올린 것은 활성이 예측되는 분자가 아니라
'학습 영역과 닮은 분자', 즉 천연물 DB에 섞여 있는 합성스러운 분자들이다.

이 스크립트는 그 진단을 수치와 그림으로 남긴다.

출력:
  data/reports/261124_screen_diagnostics.csv
  data/reports/261124_screen_diagnostics.png
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
from rdkit import Chem, RDLogger, RDConfig
sys.path.append(os.path.join(RDConfig.RDContribDir, "NP_Score"))
import npscorer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RDLogger.DisableLog("rdApp.*")
NPM = npscorer.readNPModel()

FULL = "data/screening/261124_screen_full_ranked.csv.gz"
TOP = "data/screening/261124_screen_top2000.csv"
MERGED = "data/interim/261010_HSD17B13_IC50_merged.xlsx"
OUTDIR = "data/reports"
SEED = 1


def profile(smiles):
    hal, nps = [], []
    for s in smiles:
        m = Chem.MolFromSmiles(str(s))
        if m is None:
            continue
        hal.append(any(a.GetSymbol() in ("Cl", "Br", "I", "F") for a in m.GetAtoms()))
        try:
            nps.append(npscorer.scoreMol(m, NPM))
        except Exception:
            pass
    return float(np.mean(hal) * 100), float(np.median(nps))


# ---- 기준선: 학습셋 / 라이브러리 ------------------------------------------------
tr = pd.read_excel(MERGED, sheet_name="robust_dedup")
tr = tr.dropna(subset=["canonical_smiles", "ic50_median_nM"])
tr["lab"] = (tr.ic50_median_nM <= 1000).astype(int)
act_h, act_n = profile(tr.loc[tr.lab == 1, "canonical_smiles"])
ina_h, ina_n = profile(tr.loc[tr.lab == 0, "canonical_smiles"])

full = pd.read_csv(FULL, low_memory=False)
lib_h, lib_n = profile(full.sample(20_000, random_state=SEED).canonical_smiles)

print("=" * 72)
print("기준선")
print("=" * 72)
print(f"  학습 active     할로겐 {act_h:5.1f}%   NP-likeness {act_n:+.2f}")
print(f"  학습 inactive   할로겐 {ina_h:5.1f}%   NP-likeness {ina_n:+.2f}")
print(f"  천연물 라이브러리  할로겐 {lib_h:5.1f}%   NP-likeness {lib_n:+.2f}")
print("\n  → 할로겐은 active와 inactive를 가르지 못한다(92.5 대 87.9).")
print("    학습 '영역'의 표식일 뿐이다.")

# ---- 순위 구간별 ----------------------------------------------------------------
top = pd.read_csv(TOP)
bands = [(1, 100), (101, 500), (501, 1000), (1001, 2000)]
rows = [{"구간": "학습 active", "할로겐%": round(act_h, 1), "NP_likeness": round(act_n, 2),
         "n": int((tr.lab == 1).sum())}]
for a, b in bands:
    s = top[(top["rank"] >= a) & (top["rank"] <= b)]
    rows.append({"구간": f"상위 {a}-{b}", "할로겐%": round(s.has_halogen.mean() * 100, 1),
                 "NP_likeness": round(float(s.np_score.median()), 2), "n": len(s)})
rows.append({"구간": "라이브러리 전체", "할로겐%": round(lib_h, 1),
             "NP_likeness": round(lib_n, 2), "n": len(full)})
diag = pd.DataFrame(rows)
print("\n" + "=" * 72)
print("순위 구간별")
print("=" * 72)
print(diag.to_string(index=False))

os.makedirs(OUTDIR, exist_ok=True)
diag.to_csv(f"{OUTDIR}/261124_screen_diagnostics.csv", index=False, encoding="utf-8-sig")

# ---- 그림 ------------------------------------------------------------------------
plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))

# (1) 점수 분포
ax = axes[0]
ax.hist(full.active_prob, bins=60, color="#9fb6cd", log=True)
ax.axvline(0.5, color="#c75d4d", ls="--", lw=1.5)
ax.text(0.52, ax.get_ylim()[1] * 0.3, "기존 08b 커트라인 0.5\n→ 765,011개 중 105개",
        fontsize=8.5, color="#c75d4d")
ax.set_xlabel("예측 활성 확률"); ax.set_ylabel("분자 수 (로그)")
ax.set_title("점수 분포 — 99.97%가 0.25 미만", fontsize=11)

# (2) 할로겐
ax = axes[1]
lbl = diag["구간"].tolist()
x = np.arange(len(lbl))
cols = ["#2f5d50"] + ["#c75d4d"] * len(bands) + ["#9fb6cd"]
ax.bar(x, diag["할로겐%"], 0.6, color=cols)
ax.axhline(lib_h, ls="--", lw=1, color="#555")
ax.set_xticks(x); ax.set_xticklabels(lbl, rotation=20, ha="right", fontsize=8)
ax.set_ylabel("%"); ax.set_title(f"할로겐 보유율 (라이브러리 {lib_h:.1f}%)", fontsize=11)
ax.grid(axis="y", alpha=0.25)

# (3) NP-likeness
ax = axes[2]
ax.bar(x, diag["NP_likeness"], 0.6, color=cols)
ax.axhline(0, color="#333", lw=0.8)
ax.axhline(lib_n, ls="--", lw=1, color="#555")
ax.set_xticks(x); ax.set_xticklabels(lbl, rotation=20, ha="right", fontsize=8)
ax.set_ylabel("NP-likeness"); ax.set_title("천연물스러움 (높을수록 천연물다움)", fontsize=11)
ax.grid(axis="y", alpha=0.25)

fig.suptitle("모델은 '활성이 예측되는 분자'가 아니라 '학습 영역과 닮은 분자'를 올리고 있다",
             fontsize=12.5)
fig.tight_layout()
fig.savefig(f"{OUTDIR}/261124_screen_diagnostics.png", dpi=150)
print(f"\n저장 → {OUTDIR}/261124_screen_diagnostics.csv / .png")
