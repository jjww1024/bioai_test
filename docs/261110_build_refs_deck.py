# -*- coding: utf-8 -*-
"""HSD17B13 소재발굴 - 참고문헌 6편 정리 덱 (20장)"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from lxml import etree
from PIL import Image

FIG = r"C:\Users\jjww1\Desktop\claude code\bioai_test\docs\ref_figures_261110"
OUT = r"C:\Users\jjww1\Desktop\claude code\bioai_test\docs\261110_HSD17B13_참고문헌6편.pptx"

PETROL = RGBColor(0x0B, 0x3C, 0x49)
TEAL   = RGBColor(0x0E, 0x7C, 0x7B)
AMBER  = RGBColor(0xE0, 0xA0, 0x33)
RED    = RGBColor(0xA8, 0x45, 0x2C)
INK    = RGBColor(0x1F, 0x1F, 0x1F)
GRAY   = RGBColor(0x6A, 0x6A, 0x6A)
LIGHT  = RGBColor(0xED, 0xF3, 0xF4)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
LINE   = RGBColor(0xD3, 0xDE, 0xE0)

GB, GM, GL = "Gmarket Sans TTF Bold", "Gmarket Sans TTF Medium", "Gmarket Sans TTF Light"
W, H = Inches(13.333), Inches(7.5)

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]


def setfont(run, size, bold=False, color=INK, face=None):
    f = face or (GB if bold else GM)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = f
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rPr, qn(tag))
        el.set("typeface", f)


def box(slide, x, y, w, h):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return tf


def para(tf, text, size, bold=False, color=INK, face=None, space_before=0,
         space_after=4, align=PP_ALIGN.LEFT, first=False, line=1.22, bullet=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_before = Pt(space_before)
    p.space_after = Pt(space_after)
    p.line_spacing = line
    if bullet:
        pPr = p._p.get_or_add_pPr()
        pPr.set("marL", str(int(Inches(0.23))))
        pPr.set("indent", str(-int(Inches(0.23))))
        r = p.add_run()
        r.text = bullet + "  "
        setfont(r, size, True, TEAL)
    r = p.add_run()
    r.text = text
    setfont(r, size, bold, color, face)
    return p


def rect(slide, x, y, w, h, fill=None, lineclr=None, lw=1.0, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if lineclr is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = lineclr
        s.line.width = Pt(lw)
    s.shadow.inherit = False
    s.text_frame.word_wrap = True
    return s


def header(slide, num, title, cite):
    if num:
        b = rect(slide, 0.52, 0.34, 0.52, 0.52, TEAL, shape=MSO_SHAPE.OVAL)
        tf = b.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        para(tf, num, 16, True, WHITE, GB, align=PP_ALIGN.CENTER, first=True, space_after=0)
        tx = 1.20
    else:
        tx = 0.52
    tf = box(slide, tx, 0.28, 11.6, 0.5)
    para(tf, title, 20.5, True, PETROL, GB, first=True, space_after=0)
    tf = box(slide, tx, 0.75, 11.6, 0.3)
    para(tf, cite, 9.5, False, GRAY, GL, first=True, space_after=0)
    rect(slide, 0.52, 1.08, 12.29, 0.025, TEAL)


def picture(slide, fname, x, y, maxw, maxh, caption=None, cap_size=10.5):
    path = os.path.join(FIG, fname)
    iw, ih = Image.open(path).size
    sc = min(maxw / iw, maxh / ih)
    w, h = iw * sc, ih * sc
    cx = x + (maxw - w) / 2
    slide.shapes.add_picture(path, Inches(cx), Inches(y), Inches(w), Inches(h))
    if caption:
        tf = box(slide, x, y + h + 0.10, maxw, 0.6)
        para(tf, caption, cap_size, False, GRAY, GL, first=True,
             align=PP_ALIGN.CENTER, line=1.15)
    return h


def table(slide, x, y, w, rows, colw, head=True, fs=11.5, rowh=0.33, headclr=PETROL):
    nr, nc = len(rows), len(rows[0])
    shp = slide.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(rowh * nr))
    tbl = shp.table
    tbl.first_row = head
    tbl.horz_banding = False
    for i, cwid in enumerate(colw):
        tbl.columns[i].width = Inches(cwid)
    for ri, row in enumerate(rows):
        tbl.rows[ri].height = Inches(rowh)
        for ci, val in enumerate(row):
            c = tbl.cell(ri, ci)
            c.margin_left = Inches(0.10)
            c.margin_right = Inches(0.08)
            c.margin_top = Inches(0.03)
            c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid()
            if head and ri == 0:
                c.fill.fore_color.rgb = headclr
            else:
                c.fill.fore_color.rgb = WHITE if ri % 2 else LIGHT
            tf = c.text_frame
            tf.word_wrap = True
            al = PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER
            emph = isinstance(val, tuple)
            txt = val[0] if emph else val
            clr = WHITE if (head and ri == 0) else (RED if emph else INK)
            lines = txt.split("\n")
            for li, ln in enumerate(lines):
                para(tf, ln, fs, (head and ri == 0) or emph, clr,
                     first=(li == 0), space_after=0, align=al, line=1.08)
    return shp


def callout(slide, x, y, w, h, title, body, clr=AMBER):
    rect(slide, x, y, w, h, LIGHT)
    rect(slide, x, y, 0.055, h, clr)
    tf = box(slide, x + 0.26, y + 0.14, w - 0.45, h - 0.24)
    para(tf, title, 11.5, True, PETROL, GB, first=True, space_after=3)
    for ln in body:
        para(tf, ln, 11.5, False, INK, GL, space_after=2, line=1.2)


def foot(slide, text, clr=TEAL):
    rect(slide, 0.52, 6.80, 12.29, 0.015, LINE)
    tf = box(slide, 0.52, 6.92, 12.29, 0.4)
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "\u25b6 우리 과제 적용   "
    setfont(r, 10.5, True, clr, GB)
    r = p.add_run()
    r.text = text
    setfont(r, 10.5, False, INK, GL)
    p.space_after = Pt(0)


def pageno(slide, n):
    tf = box(slide, 12.2, 6.95, 0.7, 0.3)
    para(tf, str(n), 10, False, GRAY, GL, align=PP_ALIGN.RIGHT, first=True, space_after=0)


# ===================================================== 1. 표지
s = prs.slides.add_slide(BLANK)
rect(s, 0, 0, 13.333, 7.5, PETROL)
rect(s, 0, 0, 0.16, 7.5, TEAL)
tf = box(s, 1.05, 1.15, 11.2, 1.3)
para(tf, "HSD17B13 소재발굴", 34, True, WHITE, GB, first=True, space_after=6)
para(tf, "참고문헌 6편 정리", 24, False, RGBColor(0x9E, 0xC9, 0xC8), GM, space_after=0)
rect(s, 1.05, 2.68, 2.6, 0.022, AMBER)

rows = [["", "저자 · 연도", "저널", "핵심"],
        ["\u2460", "van Tilborg 2026", "Nature Mach Intell", "모델이 '낯선 분자'를 스스로 알아챈다"],
        ["\u2461", "Altae-Tran 2017", "ACS Central Science", "데이터가 몇 개뿐일 때 배우는 법"],
        ["\u2462", "Mayr 2018", "Chemical Science", "50만 분자 규모의 공정한 방법 비교"],
        ["\u2463", "Cockroft 2019", "J Chem Inf Model", "합성물로 배운 모델을 천연물에 쓰면"],
        ["\u2464", "Qiang 2021", "Int J Mol Sci", "BatchNorm만 조정해 천연물에 맞추기"],
        ["\u2465", "Jia 2022", "ACS Omega", "AI로 고르고 실험으로 확인하기"]]
shp = table(s, 1.05, 3.05, 11.2, rows, [0.5, 2.35, 2.55, 5.8], fs=12, rowh=0.44, headclr=TEAL)
for ri in range(1, 7):
    for ci in range(4):
        c = shp.table.cell(ri, ci)
        c.fill.solid()
        c.fill.fore_color.rgb = RGBColor(0x15, 0x4B, 0x59) if ri % 2 else RGBColor(0x11, 0x44, 0x51)
        for p in c.text_frame.paragraphs:
            for r in p.runs:
                r.font.color.rgb = WHITE if ci in (0, 1) else RGBColor(0xC8, 0xDC, 0xDE)

tf = box(s, 1.05, 6.55, 11.2, 0.5)
para(tf, "2026-11-10   ·   홍재원   ·   Figure는 각 논문 원본(오픈액세스)에서 추출",
     11, False, RGBColor(0x8F, 0xB4, 0xB6), GL, first=True, space_after=0)

# ===================================================== (1) van Tilborg
C1 = "van Tilborg, Rossen & Grisoni (2026)  Nature Machine Intelligence 8:575-587"

s = prs.slides.add_slide(BLANK)
header(s, "\u2460", "문제 - 모델이 모르는 분자를 알아채지 못한다", C1)
tf = box(s, 0.52, 1.35, 5.55, 4.3)
for i, t in enumerate(["AI는 학습한 분자와 비슷한 것만 잘 맞힌다",
                       "모양이 다르면 틀리는데, 틀릴 때도 자신 있게 숫자를 낸다",
                       "\"이 분자가 모델에게 낯선가\"를 재는 표준 방법이 없었다",
                       "33개 데이터셋에서 확인 - 골격이 먼 분자(OOD)를 시험셋으로 떼어내면 모델 5종이 전부 성능 하락"]):
    para(tf, t, 13.5, space_after=9, bullet="\u2022", first=(i == 0))
callout(s, 0.52, 4.25, 5.55, 2.30, "숫자로 보면",
        ["균형정확도 약 0.80  \u2192  약 0.60  (Test_ID \u2192 Test_OOD)",
         "모델 5종 전부 유의하게 하락 (Wilcoxon, P < 0.05)",
         " ",
         "Test_OOD는 Train과 골격 유사도 · 공통핵심구조(MCS) ·",
         "파마코포어 유사도가 모두 유의하게 낮다"])
picture(s, "vanTilborg2026_Fig2de_OOD성능하락.png", 6.45, 2.05, 6.4, 3.4,
        "Figure 2d,e | 회색 = Test_ID, 노랑 = Test_OOD.   * = 통계적으로 유의")
foot(s, "우리 천연물은 학습셋과 Tanimoto 0.18-0.20 - 정확히 이 OOD 상황이다.")
pageno(s, 2)

s = prs.slides.add_slide(BLANK)
header(s, "\u2460", "방법 - 모델에게 일을 두 개 시킨다", C1)
tf = box(s, 0.52, 1.35, 12.29, 2.1)
para(tf, "\u2460 활성 예측하기      \u2461 분자를 다시 그려내기      (JMM, joint modelling)",
     14, True, PETROL, GB, first=True, space_after=10)
for t in ["다시 그리기를 못 할수록 낯선 분자 \u2192 재구성 손실의 로그 = 불친숙도 U(x)",
          "데이터 분할: Bemis-Murcko 골격 \u2192 스펙트럼 군집화 \u2192 가장 먼 군집 25% = Test_OOD, 나머지 Test_ID 25% / Train 50%",
          "다시 그리기를 붙인 대가: Test_ID 균형정확도 0.75 \u00b1 0.02 (기존 ECFP 모델 0.78 \u00b1 0.02) - 거의 없음"]:
    para(tf, t, 13.5, space_after=8, bullet="\u2022")
picture(s, "vanTilborg2026_Fig1b_JMM구조.png", 0.52, 2.95, 12.29, 3.35,
        "Figure 1b | 인코더(1D-CNN) \u2192 압축 벡터 z \u2192 디코더(RNN)가 분자를 다시 그린다 + 예측 헤드가 활성을 맞힌다")
pageno(s, 3)

s = prs.slides.add_slide(BLANK)
header(s, "\u2460", "결과 - 낯섦은 불확실함과 다른 정보다", C1)
rows = [["확인 항목", "결과"],
        ["U(x)가 OOD를 구분하는가", "33개 데이터셋 전부 유의"],
        ["140만 개 상용 라이브러리", "Test_OOD보다 더 낯섦 (KS D = 0.999)"],
        ["불확실성 H(y|x)와의 관계", ("r = -0.03 \u00b1 0.03   \u2192   서로 다른 정보",)],
        ["실험 적중률 (60개, 10 \u00b5M)", "PIM1 17% (5/30)  ·  CDK1 7% (2/30)"],
        ["저마이크로몰 7개의 출신", ("5개가 Method A (불확실성\u2191 · 불친숙도\u2193)",)]]
table(s, 0.52, 1.40, 12.29, rows, [4.3, 7.99], fs=12.5, rowh=0.42)
picture(s, "vanTilborg2026_Fig4g_실험히트맵.png", 0.52, 4.25, 12.29, 1.85,
        "Figure 4g | PIM1 · CDK1 각 30개를 10 \u00b5M 단일농도로 측정. 진한 칸일수록 활성 억제가 강함")
foot(s, "예측값과 U(x)를 함께 보고 높으면 판정 보류. 단 \"낯선 것을 고르라\"는 결론은 아니다 - 실제 히트는 낯설지 않은 쪽에서 나왔다.")
pageno(s, 4)

# ===================================================== (2) Altae-Tran
C2 = "Altae-Tran, Ramsundar, Pappu & Pande (2017)  ACS Central Science 3(4):283-293"

s = prs.slides.add_slide(BLANK)
header(s, "\u2461", "문제 - 데이터가 몇 개뿐일 때", C2)
tf = box(s, 0.52, 1.40, 7.1, 4.4)
for i, t in enumerate(["보통 AI는 학습 데이터가 수천~수만 개 필요하다",
                       "신약·천연물 분야는 한 타깃당 수십~수백 개인 경우가 많다",
                       "데이터가 적으면 모델이 외워버리고(과적합) 새 분자에서 틀린다",
                       "이 논문은 \"적은 데이터로 배우기(one-shot learning)\"를 화학에 처음 적용했다",
                       "모델 전부 DeepChem에 공개"]):
    para(tf, t, 13.5, space_after=11, bullet="\u2022", first=(i == 0))
callout(s, 7.95, 1.62, 4.88, 1.95, "우리 과제의 실제 데이터 양",
        ["겉보기   active 2,741  ·  inactive 210",
         "유효표본(Kish)   active 41  ·  inactive 30",
         "상위 10개 군집이 active의 42.5%",
         "\u2192 겉보기 숫자와 무관하게 실질 데이터는 적다"], RED)
tf = box(s, 0.52, 4.30, 12.29, 0.35)
para(tf, "평가에 쓴 벤치마크 3종", 13.5, True, TEAL, GB, first=True, space_after=0)
_bm = [("Tox21", "독성 어세이 12종|앞 9종 학습 / 뒤 3종 시험"),
       ("SIDER", "약물 부작용 27개 기관계|앞 21종 학습 / 뒤 6종 시험"),
       ("MUV", "가상스크리닝용 17종|활성끼리 구조가 서로 다르게 설계됨")]
_bx = 0.52
for _k, _v in _bm:
    rect(s, _bx, 4.72, 3.93, 1.30, LIGHT, LINE)
    _t = box(s, _bx + 0.22, 4.88, 3.55, 1.05)
    para(_t, _k, 13, True, PETROL, GB, first=True, space_after=5)
    for _ln in _v.split("|"):
        para(_t, _ln, 11.5, False, INK, GL, space_after=2, line=1.18)
    _bx += 4.09
foot(s, "데이터를 더 모으는 것보다, 적은 데이터에 맞는 학습 방식을 고르는 쪽이 현실적이다.")
pageno(s, 5)

s = prs.slides.add_slide(BLANK)
header(s, "\u2461", "방법 - 정답 몇 개를 함께 넣어준다", C2)
tf = box(s, 0.52, 1.45, 5.3, 4.6)
for i, t in enumerate(["지지집합(정답을 아는 소수 분자)과 질의분자를 함께 모델에 넣는다",
                       "둘 다 그래프 합성곱으로 숫자 벡터(임베딩)로 바꾼다",
                       "IterRefLSTM - 두 임베딩이 서로를 보면서 반복해서 다듬어진다",
                       "질의분자와 비슷한 지지분자들의 정답을 가중평균해 예측한다",
                       "평가: Tox21 · SIDER · MUV.  지지집합을 20번 무작위로 바꿔 중앙값 보고"]):
    para(tf, t, 13, space_after=6, bullet="\u2022", first=(i == 0))
picture(s, "AltaeTran2017_Fig1.png", 6.05, 2.35, 6.76, 4.0,
        "Figure 1 | 위 = 지지집합(정답 있음), 아래 = 새 분자.   g·f로 임베딩 \u2192 k로 유사도 \u2192 가중합으로 예측")
pageno(s, 6)

s = prs.slides.add_slide(BLANK)
header(s, "\u2461", "결과 - 언제 되고 언제 안 되나", C2)
rows = [["데이터셋 / 조건", "Random Forest", "ResLSTM (one-shot)"],
        ["Tox21   (양성 10 · 음성 10)", "0.563", ("0.840",)],
        ["Tox21   (양성 1 · 음성 1)", "0.542", ("0.784",)],
        ["SIDER   (양성 10 · 음성 10)", "0.546", ("0.752",)],
        ["MUV - 활성끼리 구조가 제각각", ("0.741",), "0.712"],
        ["Tox21로 학습 \u2192 SIDER 예측", "0.546", ("0.509   = 찍기",)]]
table(s, 0.52, 1.42, 12.29, rows, [5.49, 3.4, 3.4], fs=12.5, rowh=0.44)
tf = box(s, 0.52, 4.28, 12.29, 1.2)
para(tf, "데이터가 적을수록 one-shot의 이득이 크다", 13.5, space_after=9, bullet="1", first=True)
para(tf, "활성끼리 구조가 제각각이면 진다 - 구조 유사성을 쓸 수가 없기 때문 (MUV)", 13.5, space_after=9, bullet="2")
para(tf, "관련 없는 과제로는 전이가 전혀 안 된다 - 0.509는 동전 던지기 수준", 13.5, space_after=0, bullet="3")
callout(s, 0.52, 5.42, 12.29, 1.28, "우리 데이터에 대입하면",
        ["학습 active 2,741개는 Butina 군집 312개에 몰려 있다 — 상위 10개 군집이 42.5%.  Tox21 · SIDER 쪽 상황이다",
         "반대로 예측 대상인 천연물은 서로 구조가 제각각이다 — MUV 쪽 상황에 가깝다",
         "즉 \"학습은 쉬운 조건, 예측은 어려운 조건\"이 겹쳐 있다"], RED)
foot(s, "우리 SDR 패밀리 멀티태스크 실험(3,304개 추가 \u2192 Spearman +0.004)과 같은 결론이다.")
pageno(s, 7)

# ===================================================== (3) Mayr
C3 = "Mayr, Klambauer, Unterthiner \u2026 Hochreiter (2018)  Chemical Science 9(24):5441-5451"

s = prs.slides.add_slide(BLANK)
header(s, "\u2462", "문제 - 비교가 공정하지 않았다", C3)
tf = box(s, 0.52, 1.40, 6.0, 4.4)
for i, t in enumerate(["\"딥러닝이 좋다\" vs \"랜덤포레스트면 충분하다\" 논쟁이 계속됐다",
                       "기존 비교 논문은 어세이를 몇 개만 써서 결론을 일반화할 수 없었다",
                       "무작위로 나눠 평가하면 학습·시험에 같은 계열 분자가 섞여 점수가 부풀려진다",
                       "하이퍼파라미터를 시험셋 보고 고르면 또 부풀려진다"]):
    para(tf, t, 13.5, space_after=12, bullet="\u2022", first=(i == 0))
picture(s, "Mayr2018_Fig1.jpg", 6.85, 1.60, 5.95, 4.1,
        "Figure 1 | 왼쪽 = 두 어세이에 모두 측정된 화합물 수,  오른쪽 = 그 화합물들에서의 상관\n서로 강하게 상관된 어세이가 많다 \u2192 멀티태스크 학습의 근거")
foot(s, "우리 모델의 test 행 12.2%가 train과 골격을 공유한다 - 바로 이 문제다.")
pageno(s, 8)

s = prs.slides.add_slide(BLANK)
header(s, "\u2462", "방법 - 중첩 군집 교차검증", C3)
tf = box(s, 0.52, 1.35, 6.0, 4.6)
for i, t in enumerate(["ChEMBL에서 화합물 약 50만 개 / 어세이 1,310개 벤치마크 구축",
                       "어세이 하나를 개별 분류 문제로 둔다 - 결합·길항·작용제 어세이를 섞지 않는다",
                       "구조 군집으로 분할 \u2192 시험셋은 학습에 없던 골격",
                       "바깥 루프 = 성능 측정, 안쪽 루프 = 하이퍼파라미터 조정",
                       "비교 9종: FNN · SVM · RF · KNN · NB · SEA · GC · Weave · SmilesLSTM"]):
    para(tf, t, 13, space_after=11, bullet="\u2022", first=(i == 0))
picture(s, "Mayr2018_Fig7.jpg", 6.85, 1.70, 5.95, 4.0,
        "Figure 7 | 화합물 1개가 등장하는 어세이 라벨 수 (로그 눈금)")
foot(s, "우리는 타깃 1개 · 어세이 1종이다. 멀티태스크 이전에 분할 방식부터 이 기준으로 맞춰야 한다.")
pageno(s, 9)

s = prs.slides.add_slide(BLANK)
header(s, "\u2462", "결과 - 심층망이 1위, 성능은 실험 수준", C3)
rows = [["", "FNN", "SVM", "SmilesLSTM", "GC", "RF", "Weave", "KNN", "NB", "SEA"],
        ["ECFP6 기준 assay-AUC", ("0.724",), "0.715", "0.698", "0.692", "0.679", "0.673", "0.669", "0.661", "0.593"]]
table(s, 0.52, 1.42, 12.29, rows,
      [2.95, 1.00, 1.00, 1.35, 0.95, 0.95, 1.05, 1.00, 0.95, 1.09], fs=11.5, rowh=0.42)
tf = box(s, 0.52, 2.50, 6.0, 3.9)
para(tf, "최고 조합  FNN + SemiF = 0.743 \u00b1 0.124", 14, True, RED, GB, first=True, space_after=4)
para(tf, "\u03b1 = 0.01에서 나머지 전부에 유의하게 우세", 11.5, False, GRAY, GL, space_after=13)
for t in ["그래프 신경망(GC · Weave)은 지문 기반 FNN을 못 이겼다",
          "학습 데이터가 많을수록 AUC 상승 - 세 방법 모두 같은 경향",
          "AI vs 실험: 같은 타깃의 대리 실험 0.81 \u00b1 0.17  vs  딥러닝 0.82 \u00b1 0.10",
          "22쌍 중 13쌍 차이 없음 · 5쌍 AI 승 · 4쌍 실험 승"]:
    para(tf, t, 13, space_after=10, bullet="\u2022")
picture(s, "Mayr2018_Fig2.jpg", 6.85, 2.50, 5.95, 3.45,
        "Figure 2 | 1,310개 어세이의 AUC 분포")
foot(s, "멀티태스크가 통하려면 이 정도 규모가 필요하다. 그리고 군집 분할이 표준이다.")
pageno(s, 10)

# ===================================================== (4) Cockroft
C4 = "Cockroft, Cheng & Fuchs (2019)  J Chem Inf Model 59(11):4906-4920  ·  STarFish"

s = prs.slides.add_slide(BLANK)
header(s, "\u2463", "문제 - 천연물에서의 성능은 아무도 재지 않았다", C4)
tf = box(s, 0.52, 1.40, 5.8, 4.3)
for i, t in enumerate(["타깃 예측 모델은 거의 전부 합성 화합물로 학습된다",
                       "천연물에 쓰면 성능이 어떻게 되는지 보고된 적이 없었다",
                       "이유 \u2460  천연물 활성 데이터가 적다",
                       "이유 \u2461  DB에 \"이건 천연물\"이라는 표시가 없다",
                       "\u2192 천연물 벤치마크 세트를 직접 만들어 측정했다"]):
    para(tf, t, 13.5, space_after=11, bullet="\u2022", first=(i == 0))
picture(s, "Cockroft2019_Fig3.jpg", 6.55, 1.45, 6.28, 4.5,
        "Figure 3 | 천연물 DB 20개의 크기(위)와 상호 중복(아래).   어느 DB도 전체를 담지 못한다")
foot(s, "천연물 라이브러리를 구할 때도 DB 하나로는 부족하다 — 여러 DB를 합치고 중복을 걷어내야 한다.")
pageno(s, 11)

s = prs.slides.add_slide(BLANK)
header(s, "\u2463", "방법 - 데이터 구축 + 2층 스태킹", C4)
tf = box(s, 0.52, 1.35, 6.2, 2.6)
para(tf, "데이터", 13.5, True, TEAL, GB, first=True, space_after=6)
for t in ["천연물 DB 20개 통합 \u2192 고유 천연물 438,258개",
          "ChEMBL23과 대조 (활성 \u2264 1 \u00b5M, confidence score 9)",
          "합성 세트   107,190쌍 / 88,728 화합물 / 1,907 타깃",
          "천연물 세트   5,589쌍 / 1,943 화합물 / 1,023 타깃"]:
    para(tf, t, 12.5, space_after=6, bullet="\u2022")
tf = box(s, 0.52, 4.05, 6.2, 2.4)
para(tf, "모델", 13.5, True, TEAL, GB, first=True, space_after=6)
for t in ["지문: FCFP 2048비트 (반경 2)",
          "Level 0 - KNN(k=10) · RF(1,000트리 \u00d7 1,907개) · MLP(은닉 1,000)",
          "Level 1 - 로지스틱 회귀가 Level 0의 확률을 받아 최종 판단"]:
    para(tf, t, 12.5, space_after=6, bullet="\u2022")
callout(s, 0.52, 5.30, 6.2, 1.20, "눈여겨볼 전처리",
        ["타깃당 화합물 수를 100개로 상한 → 타깃 간 불균형을 강제로 줄였다",
         "활성 기준을 1 µM로 엄격히 잡아 애매한 구간을 아예 뺐다"])
picture(s, "Cockroft2019_Fig2.jpg", 6.95, 1.70, 5.88, 4.0,
        "Figure 2 | 2층 스태킹 구조")
pageno(s, 12)

s = prs.slides.add_slide(BLANK)
header(s, "\u2463", "결과 - 합성물 0.94~0.99 \u2192 천연물 0.70~0.85", C4)
rows = [["지표", "합성물 10-fold CV", "천연물 벤치마크"],
        ["AUROC", "0.94 - 0.99", ("0.70 - 0.85",)],
        ["BEDROC (조기 인식)", "0.89 - 0.94", ("0.43 - 0.59",)],
        ["상위 10개에 정답 포함", "89 - 92 %", ("55 - 60 %",)],
        ["Coverage error (낮을수록 좋음)", "187 - 29", ("1,286 - 416",)]]
table(s, 0.52, 1.42, 6.6, rows, [2.8, 1.9, 1.9], fs=11.5, rowh=0.42)
tf = box(s, 0.52, 3.78, 6.6, 2.8)
for i, t in enumerate(["스태킹하면 천연물에서 회복 - AUROC 0.82-0.94 (KNN 단독 0.70 \u2192 0.94)",
                       "원인: 학습·시험 유사도 분포는 거의 겹치는데 천연물만 낮은 쪽으로 쏠린다",
                       "타깃당 학습 500개에서 성능이 포화된다 (AUROC 0.999)",
                       "저자 인정 - \"무작위 분할은 compound series bias가 있어 낙관적이다\""]):
    para(tf, t, 12.5, space_after=10, bullet="\u2022", first=(i == 0))
picture(s, "Cockroft2019_Fig5.jpg", 7.35, 1.60, 5.48, 4.25,
        "Figure 5 | 학습 화합물과의 Tanimoto 유사도 누적분포\n빨강 = 학습,  파랑 = 시험,  초록 = 천연물")
foot(s, "우리 천연물은 학습셋과 Tanimoto 0.18-0.20 - 초록 곡선과 같은 위치다.")
pageno(s, 13)

# ===================================================== (5) Qiang
C5 = "Qiang, Lai, Jin, Zhang & Liu (2021)  Int J Mol Sci 22(9):4632  ·  MDPI"

s = prs.slides.add_slide(BLANK)
header(s, "\u2464", "문제 - 적은 천연물 데이터에 맞추기", C5)
tf = box(s, 0.52, 1.40, 6.0, 4.3)
for i, t in enumerate(["천연물 활성 데이터는 적어서 처음부터 학습할 수 없다",
                       "합성물로 배운 모델을 그대로 쓰면 천연물에서 성능이 떨어진다",
                       "데이터가 적은데 모델 전체를 다시 학습하면 과적합된다",
                       "\u2192 모델의 일부만 바꿔서 천연물 쪽으로 맞춘다"]):
    para(tf, t, 13.5, space_after=12, bullet="\u2022", first=(i == 0))
callout(s, 0.52, 5.00, 6.0, 1.45, "전제 확인",
        ["ChEMBL 45만 분자와  ChEMBL \u2229 COCONUT 천연물 2,600개의",
         "\"화합물당 타깃 수\" 분포가 비슷하다 \u2192 같은 구조를 그대로 쓸 수 있다"])
picture(s, "Qiang2021_Fig5.png", 6.85, 1.95, 5.98, 3.5,
        "Figure 5 | 화합물당 타깃 수 분포.   a  ChEMBL,   b  ChEMBL \u2229 COCONUT")
pageno(s, 14)

s = prs.slides.add_slide(BLANK)
header(s, "\u2464", "방법 - 은닉층은 얼리고 BatchNorm만 조정", C5)
rect(s, 0.52, 1.35, 6.2, 2.75, LIGHT)
rect(s, 0.52, 1.35, 0.055, 2.75, TEAL)
tf = box(s, 0.80, 1.52, 5.8, 2.5)
para(tf, "1단계   사전학습", 12.5, True, PETROL, GB, first=True, space_after=3)
para(tf, "ChEMBL27 - 45만 분자 / 4,193 타깃  (활성 기준 1,000 nM)", 12, False, INK, GL, space_after=10)
para(tf, "2단계   미세조정", 12.5, True, PETROL, GB, space_after=3)
para(tf, "ChEMBL \u2229 COCONUT 천연물 2,600개", 12, False, INK, GL, space_after=5)
para(tf, "\u2744  은닉층 Linear 파라미터   \u2192   전부 동결", 12, False, INK, GL, space_after=3)
para(tf, "\u25cf  BatchNorm 파라미터   \u2192   학습", 12, False, RED, GL, space_after=3)
para(tf, "\u25cf  분류기 Linear   \u2192   학습", 12, False, RED, GL, space_after=3)
para(tf, "\uff0b 학습률은 올리고, 데이터 균형 맞추기 병행", 12, False, INK, GL, space_after=0)
tf = box(s, 0.52, 4.35, 6.2, 2.2)
for i, t in enumerate(["원리 - BatchNorm만 바꿔도 데이터 분포를 천연물 쪽으로 옮길 수 있다 (AdaBN)",
                       "나머지를 얼려 두어 적은 데이터로도 모델이 무너지지 않는다"]):
    para(tf, t, 13, space_after=10, bullet="\u2022", first=(i == 0))
picture(s, "Qiang2021_Fig10.png", 6.95, 1.60, 5.88, 3.5,
        "Figure 10 | 타깃 예측 모델 구조.  아래 줄의 파란 BatchNorm만 학습된다")
callout(s, 0.52, 5.45, 12.29, 1.15, "우리 과제에 그대로 옮기면",
        ["사전학습 ChEMBL 전체  →  미세조정 HSD17B13 — 우리 실측값 1,727개는 이 논문의 천연물 2,600개와 같은 규모다",
         "은닉층 Linear 동결 + BatchNorm · 분류기만 학습, 학습률은 올리고 불균형 보정(cost-sensitive) 병행"])
pageno(s, 15)

s = prs.slides.add_slide(BLANK)
header(s, "\u2464", "결과 - 전 구간에서 상승", C5)
tf = box(s, 0.52, 1.38, 12.29, 1.9)
for i, t in enumerate(["미세조정 효과 (모델 12종) - 사전학습 AUROC 0.69-0.86   \u2192   0.80-0.90",
                       "예외는 모델 8 하나 - 천연물이 없는 데이터에 과적합된 상태였다",
                       "선택: 모델 12 (사전학습 lr 5e-5, batch 1024).  전이는 lr 5e-3 + batch 128이 안정",
                       "데이터 균형을 빼면 성능이 떨어진다 \u2192 불균형 보정은 필수",
                       "STarFish와 직접 비교 (cutoff 0.5) - SE 0.6404  vs  0.0395"]):
    para(tf, t, 12.5, space_after=5, bullet="\u2022", first=(i == 0))
picture(s, "Qiang2021_Fig3.png", 0.52, 3.35, 6.1, 2.7,
        "Figure 3 | 모델 1-12의 미세조정 전(초록) / 후(파랑) AUROC")
picture(s, "Qiang2021_Fig7.png", 6.95, 3.35, 5.88, 2.7,
        "Figure 7 | STarFish(파랑)와 미세조정 모델(주황)의 SE 비교")
foot(s, "기법은 그대로 채택하되 MDPI 저널이므로 인용은 \u2462 · \u2463으로 받친다.", RED)
pageno(s, 16)

# ===================================================== (6) Jia
C6 = "Jia et al. (2022)  ACS Omega 7(32):28334-28346"

s = prs.slides.add_slide(BLANK)
header(s, "\u2465", "문제 - 전부 실험할 수는 없다", C6)
tf = box(s, 0.52, 1.40, 6.3, 3.2)
for i, t in enumerate(["천연물 수천 개를 전부 실험할 수는 없다",
                       "\u03b2-튜불린(세포 골격) 저해제를 천연물에서 찾고 싶다",
                       "\u2192 AI로 순위를 매기고 위쪽만 실험한다",
                       "학습 데이터 규모가 우리 과제와 가장 비슷한 사례다"]):
    para(tf, t, 13.5, space_after=12, bullet="\u2022", first=(i == 0))
rows = [["", "Jia 2022", "우리 (현재)"],
        ["양성 (hit / active)", "637", "2,741"],
        ["음성 (non-hit / inactive)", "2,932", ("210",)],
        ["양성 : 음성", "1 : 4.6", ("13 : 1",)],
        ["스크리닝 대상", "천연물 4,247", "천연물 라이브러리"],
        ["최종 실험 후보", "71 \u2192 3", "미정"]]
table(s, 0.52, 4.00, 6.3, rows, [2.7, 1.8, 1.8], fs=11.5, rowh=0.40)
tf = box(s, 7.15, 1.55, 5.68, 4.8)
para(tf, "눈여겨볼 점", 14, True, TEAL, GB, first=True, space_after=10)
for t in ["음성을 \"관련 없는 다른 약효군 화합물\"로 채웠다 (decoy 미사용)",
          "티로신키나아제 저해제 · 면역항암 · 혈관신생 화합물 2,932개",
          "우리는 양성이 음성의 13배로, 방향이 정반대다",
          "후보를 71개까지 좁힌 뒤에야 실험으로 넘어갔다"]:
    para(tf, t, 13, space_after=11, bullet="\u2022")
foot(s, "음성을 decoy 대신 \"다른 약효군의 실측 화합물\"로 채우는 방식은 우리도 검토할 수 있다.")
pageno(s, 17)

s = prs.slides.add_slide(BLANK)
header(s, "\u2465", "방법 - 순위 매기고 좁히고 실험", C6)
steps = [("학습", "hit 637 (알려진 \u03b2-튜불린 저해제)\nnon-hit 2,932"),
         ("모델", "DMPNN\n분자지문 4종 비교"),
         ("스크리닝", "천연물 4,247개\n\u2192 hit probability 순위"),
         ("필터", "\u2460 hit probability\n\u2461 Lipinski 규칙\n\u2462 Tanimoto 유사도"),
         ("후보", "71개 \u2192 전문가 검토"),
         ("실험", "3개 확정")]
yy = 1.38
for i, (k, v) in enumerate(steps):
    hgt = 0.56 + 0.20 * v.count("\n")
    rect(s, 0.52, yy, 4.4, hgt, LIGHT if i % 2 == 0 else WHITE, LINE)
    t2 = box(s, 0.72, yy + 0.08, 4.0, hgt - 0.12)
    para(t2, k, 11.5, True, TEAL, GB, first=True, space_after=2)
    for ln in v.split("\n"):
        para(t2, ln, 11, False, INK, GL, space_after=1, line=1.12)
    yy += hgt + 0.12
picture(s, "Jia2022_Fig1.jpg", 5.35, 1.45, 7.48, 4.75,
        "Figure 1 | 전체 흐름 - 학습 \u2192 스크리닝 \u2192 필터 \u2192 전문가 검토 \u2192 실험")
pageno(s, 18)

s = prs.slides.add_slide(BLANK)
header(s, "\u2465", "결과 - 71개 중 3개를 실험으로 확정", C6)
rows = [["입력 특징", "AUC", "ACC", "Precision", "Recall"],
        ["2D normalized features", ("0.9962",), "0.9600", "0.9832", "0.9360"],
        ["Morgan fingerprint (count)", "0.9859", "0.9120", "0.9813", "0.8400"],
        ["특징 없음", "0.9915", "0.9280", "0.9908", "0.8640"]]
table(s, 0.52, 1.42, 6.3, rows, [2.42, 0.97, 0.97, 1.12, 0.82], fs=11, rowh=0.40)
tf = box(s, 0.52, 3.15, 6.6, 3.4)
para(tf, "찾아낸 3개", 13.5, True, TEAL, GB, first=True, space_after=7)
for t in ["Eleutherobin - 이미 알려진 \u03b2-튜불린 중합 유도제 (모델이 맞다는 증거)",
          "Bruceine D - IC50 10.8 \u00b5M (MDA-MB-231, MTT)",
          "PMA - IC50 10.6 \u00b5M"]:
    para(tf, t, 12.5, space_after=6, bullet="\u2022")
para(tf, "실험 검증 (10 \u00b5M, 24시간)", 13.5, True, TEAL, GB, space_before=8, space_after=7)
for t in ["면역형광 - 미세소관 붕괴, \u03b2-tubulin 강도 감소",
          "세포주기 정지 - CDK1 · CDK2 · cyclin E 변화",
          "세포자멸사 - cleaved caspase 3 \u2191, Bax / Bcl-2 변화"]:
    para(tf, t, 12.5, space_after=6, bullet="\u2022")
picture(s, "Jia2022_Fig4.jpg", 6.95, 1.45, 5.88, 2.55,
        "Figure 4 | a  MTT 용량반응,   b·c  면역형광 - 미세소관 붕괴")
picture(s, "Jia2022_Fig3.jpg", 6.95, 4.25, 5.88, 2.0,
        "Figure 3 | 찾아낸 3개의 구조")
foot(s, "\"후보 71개로 줄여서 3개 확인\" - 우리 스크리닝의 현실적인 목표치로 삼을 수 있다.")
pageno(s, 19)

# ===================================================== 20. 요약
s = prs.slides.add_slide(BLANK)
header(s, None, "한 장 요약", "2026-11-10")
rows = [["", "한 문장", "우리가 쓸 것"],
        ["\u2460 van Tilborg 2026\nNature Mach Intell",
         "모델이 \"이건 나한테 낯설다\"를 스스로 말하게 만들었고,\n불확실성과는 다른 정보임을 보였다",
         "출력에 불친숙도 U(x) 동반 보고\n\u2192 높으면 판정 보류"],
        ["\u2461 Altae-Tran 2017\nACS Central Science",
         "데이터가 적을 때 one-shot이 이기지만,\n관련 없는 과제로는 전이가 0이다",
         "SDR 멀티태스크 기각의 근거"],
        ["\u2462 Mayr 2018\nChemical Science",
         "50만 분자 · 1,310 어세이에서 심층망이 1위,\n성능은 실험 재현성 수준",
         "군집 분할을 표준으로 채택\n+ 규모 논증"],
        ["\u2463 Cockroft 2019\nJ Chem Inf Model",
         "합성물로 배운 모델은 천연물에서 AUROC 0.94 \u2192 0.70,\n스태킹으로 0.94 회복",
         "도메인 격차의 정량 수치 인용"],
        ["\u2464 Qiang 2021\nInt J Mol Sci",
         "은닉층 동결 + BatchNorm만 조정으로\n적은 천연물 데이터에 적응",
         "미세조정 레시피 그대로 채택"],
        ["\u2465 Jia 2022\nACS Omega",
         "637 : 2,932 데이터로 천연물 4,247개 중 71개를 추려\n3개를 실험으로 확정",
         "현실적 목표치 설정\n+ 음성 구성 방식 참고"]]
table(s, 0.52, 1.35, 12.29, rows, [2.65, 6.15, 3.49], fs=11, rowh=0.80)
tf = box(s, 0.52, 6.95, 12.29, 0.4)
para(tf, "Figure 원본 41장:  bioai_test\\docs\\ref_figures_261110\\",
     10.5, False, GRAY, GL, first=True, space_after=0)
pageno(s, 20)

prs.save(OUT)
print("저장:", OUT)
print("슬라이드 수:", len(prs.slides._sldIdLst))
