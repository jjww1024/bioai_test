# -*- coding: utf-8 -*-
"""현황 덱용 차트 — 모두 이 프로젝트에서 실제로 측정한 수치"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

FDIR = os.path.join(os.environ["LOCALAPPDATA"], r"Microsoft\Windows\Fonts")
for f in ("GmarketSansTTFBold.ttf", "GmarketSansTTFMedium.ttf", "GmarketSansTTFLight.ttf"):
    p = os.path.join(FDIR, f)
    if os.path.exists(p):
        font_manager.fontManager.addfont(p)
fam = font_manager.FontProperties(fname=os.path.join(FDIR, "GmarketSansTTFMedium.ttf")).get_name()
print("font family:", fam)
plt.rcParams.update({
    "font.family": [fam, "Malgun Gothic", "DejaVu Sans"], "axes.unicode_minus": False,
    "axes.edgecolor": "#B9C8CA", "axes.labelcolor": "#1F1F1F",
    "xtick.color": "#4A4A4A", "ytick.color": "#4A4A4A",
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "savefig.facecolor": "white",
})
PETROL, TEAL, AMBER, RED, GRAYC = "#0B3C49", "#0E7C7B", "#E0A033", "#A8452C", "#9AAAAD"
OUT = r"C:\Users\jjww1\Desktop\claude code\bioai_test\docs\charts_261110"
os.makedirs(OUT, exist_ok=True)


def save(fig, name):
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("  ", name)


# 1) 등급구간 중앙값 지문
fig, ax = plt.subplots(figsize=(6.4, 3.1))
labels = ["300 nM\n(100~500)", "550 nM\n(100~1,000)", "15,500 nM\n(1,000~30,000)", "50,500 nM\n(1,000~100,000)"]
vals = [792, 374, 176, 374]
cols = [AMBER, AMBER, RED, RED]
b = ax.bar(labels, vals, color=cols, width=0.62)
for r, v in zip(b, vals):
    ax.text(r.get_x() + r.get_width() / 2, v + 14, f"{v:,}", ha="center", fontsize=10, color="#1F1F1F")
ax.set_ylabel("레코드 수")
ax.set_ylim(0, 900)
ax.tick_params(axis="x", labelsize=9.5)
ax.set_title("특허 등급구간의 '중앙점'이 실측값처럼 저장돼 있다", fontsize=11.5, color=PETROL, pad=10)
save(fig, "01_grade_midpoint.png")

# 2) 유효 표본 (Kish)
fig, ax = plt.subplots(figsize=(5.4, 3.1))
x = np.arange(2)
w = 0.36
ax.bar(x - w / 2, [2741, 210], w, color=GRAYC, label="겉보기 개수")
ax.bar(x + w / 2, [41, 30], w, color=RED, label="유효표본 (Kish)")
for i, (a, bb) in enumerate([(2741, 41), (210, 30)]):
    ax.text(i - w / 2, a * 1.12, f"{a:,}", ha="center", fontsize=10)
    ax.text(i + w / 2, bb * 1.12, f"{bb}", ha="center", fontsize=10, color=RED)
ax.set_yscale("log")
ax.set_xticks(x); ax.set_xticklabels(["active", "inactive"])
ax.set_ylabel("화합물 수 (로그)")
ax.set_ylim(10, 8000)
ax.legend(frameon=False, fontsize=9.5, loc="upper right")
ax.set_title("구조 중복을 걷어내면 실질 데이터는 41 : 30", fontsize=11.5, color=PETROL, pad=10)
save(fig, "02_effective_n.png")

# 3) 천연물 도메인 격차 (NP-likeness)  — GmarketSans에 U+2212가 없어 ASCII 하이픈 사용
fig, ax = plt.subplots(figsize=(7.4, 2.7))
ax.axhline(0, color="#D3DEE0", lw=1.4, zorder=0)
pts = [(-1.03, "학습 active 중앙값", "-1.03", TEAL, 46),
       (-0.19, "실측값 90분위", "-0.19", AMBER, 14),
       (2.10, "천연물", "+2.10", RED, 46)]
for v, lab, num, c, dy in pts:
    ax.scatter([v], [0], s=140, color=c, zorder=3)
    ax.annotate(lab, (v, 0), textcoords="offset points", xytext=(0, dy + 16),
                ha="center", fontsize=10, color=c)
    ax.annotate(num, (v, 0), textcoords="offset points", xytext=(0, dy),
                ha="center", fontsize=11.5, color=c)
    ax.plot([v, v], [0.03, 0.03 + dy / 190], color=c, lw=0.9, zorder=2)
ax.annotate("", xy=(2.05, -0.38), xytext=(-0.14, -0.38),
            arrowprops=dict(arrowstyle="<->", color=RED, lw=1.5))
ax.text(0.95, -0.72, "이 구간에 데이터 0건", ha="center", fontsize=11, color=RED)
ax.set_xlim(-2.0, 3.0); ax.set_ylim(-1.05, 1.15)
ax.set_yticks([]); ax.spines["left"].set_visible(False); ax.spines["bottom"].set_visible(False)
ax.set_xlabel("NP-likeness score  (천연물스러움)")
ax.set_title("학습 데이터와 천연물 사이가 비어 있다", fontsize=11.5, color=PETROL, pad=14)
save(fig, "03_domain_gap.png")

# 4) 어세이 천장
fig, ax = plt.subplots(figsize=(6.0, 3.0))
cats = ["5 ~ 10 µM", "10 ~ 20 µM", "> 20 µM"]
exact = [98, 0, 0]; ineq = [0, 155, 16]; grade = [6, 96, 198]
x = np.arange(3); w = 0.58
ax.bar(x, exact, w, label="실측값 (=)", color=TEAL)
ax.bar(x, ineq, w, bottom=exact, label="부등호 (>)", color=AMBER)
ax.bar(x, grade, w, bottom=np.array(exact) + np.array(ineq), label="등급 중앙값", color=RED)
ax.set_xticks(x); ax.set_xticklabels(cats)
ax.set_ylabel("레코드 수")
ax.legend(frameon=False, fontsize=9.5)
ax.annotate("실측값 0건", xy=(1, 10), xytext=(1.0, 90), ha="center", fontsize=10, color=TEAL,
            arrowprops=dict(arrowstyle="->", color=TEAL, lw=1.2))
ax.set_title("10 µM 넘는 '실측' IC50은 한 건도 없다", fontsize=11.5, color=PETROL, pad=10)
save(fig, "04_assay_ceiling.png")

# 5) 클러스터 축약
fig, ax = plt.subplots(figsize=(5.8, 3.0))
xs = [22, 36, 100]; ys = [0.796, 0.797, 0.864]
ax.plot(xs, ys, "-o", color=TEAL, lw=2, ms=9)
for a, b2, n in zip(xs, ys, ["302개", "495개", "1,382개"]):
    ax.annotate(f"{b2:.3f}\n({n})", (a, b2), textcoords="offset points",
                xytext=(0, 12), ha="center", fontsize=10, color=PETROL)
ax.set_xlabel("학습에 쓴 데이터 비율 (%)")
ax.set_ylabel("Spearman (scaffold 분할)")
ax.set_xlim(10, 112); ax.set_ylim(0.75, 0.93)
ax.set_title("1/5로 줄여도 순위 능력 0.80을 유지한다", fontsize=11.5, color=PETROL, pad=10)
save(fig, "05_downsample.png")

# 6) 멀티태스크 기각
fig, ax = plt.subplots(figsize=(6.2, 3.0))
names = ["(a) HSD17B13\n단독", "(b) + SDR\n패밀리", "(c) + AKR\n(대조군)", "(d) + 둘 다"]
sp = [0.631, 0.635, 0.601, 0.609]
add = [0, 3304, 1870, 5174]
cols2 = [GRAYC, TEAL, RED, GRAYC]
b = ax.bar(names, sp, color=cols2, width=0.6)
for r, v, a in zip(b, sp, add):
    ax.text(r.get_x() + r.get_width() / 2, v + 0.008, f"{v:.3f}", ha="center", fontsize=10.5)
    ax.text(r.get_x() + r.get_width() / 2, 0.30, f"+{a:,}" if a else "기준", ha="center",
            fontsize=9.5, color="#4A4A4A")
ax.axhline(0.631, color=GRAYC, ls="--", lw=1.1)
ax.set_ylabel("Spearman (HSD17B13 scaffold 홀드아웃)")
ax.set_ylim(0.25, 0.70)
ax.tick_params(axis="x", labelsize=9.5)
ax.set_title("패밀리 데이터를 17배 넣어도 +0.004", fontsize=11.5, color=PETROL, pad=10)
save(fig, "06_multitask.png")

# 7) 모델 지표 추이
fig, ax = plt.subplots(figsize=(5.8, 3.0))
stages = ["09/28", "10/10\n데이터확장", "10/10\n+충돌제외"]
mcc = [0.866, 0.892, 0.908]; ina = [0.63, 0.839, 0.871]
ax.plot(stages, mcc, "-o", color=PETROL, lw=2, ms=8, label="MCC")
ax.plot(stages, ina, "-o", color=AMBER, lw=2, ms=8, label="real_inactive 정답률")
for i, (a, b2) in enumerate(zip(mcc, ina)):
    ax.annotate(f"{a:.3f}", (i, a), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=10)
    ax.annotate(f"{b2:.3f}", (i, b2), xytext=(0, -17), textcoords="offset points", ha="center", fontsize=10)
ax.set_ylim(0.55, 1.0)
ax.legend(frameon=False, fontsize=9.5, loc="lower right")
ax.tick_params(axis="x", labelsize=9.5)
ax.set_title("지표는 올랐지만 — 누수 12.2%가 섞여 있다", fontsize=11.5, color=RED, pad=10)
save(fig, "07_metrics.png")

print("\n차트 저장 위치:", OUT)
