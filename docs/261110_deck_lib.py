# -*- coding: utf-8 -*-
"""HSD17B13 덱 공통 레이아웃 모듈 (python-pptx, 16:9, GmarketSans)"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from lxml import etree
from PIL import Image

FIG = r"C:\Users\jjww1\Desktop\claude code\bioai_test\docs\ref_figures_261110"
CHART = r"C:\Users\jjww1\Desktop\claude code\bioai_test\docs\charts_261110"

PETROL = RGBColor(0x0B, 0x3C, 0x49)
TEAL   = RGBColor(0x0E, 0x7C, 0x7B)
AMBER  = RGBColor(0xE0, 0xA0, 0x33)
RED    = RGBColor(0xA8, 0x45, 0x2C)
INK    = RGBColor(0x1F, 0x1F, 0x1F)
GRAY   = RGBColor(0x6A, 0x6A, 0x6A)
LIGHT  = RGBColor(0xED, 0xF3, 0xF4)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
LINE   = RGBColor(0xD3, 0xDE, 0xE0)
DARK   = RGBColor(0x15, 0x4B, 0x59)

GB, GM, GL = "Gmarket Sans TTF Bold", "Gmarket Sans TTF Medium", "Gmarket Sans TTF Light"


def new_deck():
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    return prs


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


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


def header(slide, num, title, cite, numclr=TEAL):
    if num:
        b = rect(slide, 0.52, 0.34, 0.52, 0.52, numclr, shape=MSO_SHAPE.OVAL)
        tf = b.text_frame
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = tf.margin_right = 0
        tf.margin_top = tf.margin_bottom = 0
        para(tf, num, 15 if len(num) < 2 else 13, True, WHITE, GB,
             align=PP_ALIGN.CENTER, first=True, space_after=0)
        tx = 1.20
    else:
        tx = 0.52
    tf = box(slide, tx, 0.28, 11.6, 0.5)
    para(tf, title, 20.5, True, PETROL, GB, first=True, space_after=0)
    if cite:
        tf = box(slide, tx, 0.75, 11.6, 0.3)
        para(tf, cite, 9.5, False, GRAY, GL, first=True, space_after=0)
    rect(slide, 0.52, 1.08, 12.29, 0.025, TEAL)


def picture(slide, fname, x, y, maxw, maxh, caption=None, cap_size=10.5, base=None):
    path = os.path.join(base or FIG, fname)
    iw, ih = Image.open(path).size
    sc = min(maxw / iw, maxh / ih)
    w, h = iw * sc, ih * sc
    cx = x + (maxw - w) / 2
    slide.shapes.add_picture(path, Inches(cx), Inches(y), Inches(w), Inches(h))
    if caption:
        tf = box(slide, x, y + h + 0.10, maxw, 0.6)
        para(tf, caption, cap_size, False, GRAY, GL, first=True,
             align=PP_ALIGN.CENTER, line=1.15)
    return y + h


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
            for li, ln in enumerate(txt.split("\n")):
                para(tf, ln, fs, (head and ri == 0) or emph, clr,
                     first=(li == 0), space_after=0, align=al, line=1.08)
    return shp


def callout(slide, x, y, w, h, title, body, clr=AMBER, fs=11.5):
    rect(slide, x, y, w, h, LIGHT)
    rect(slide, x, y, 0.055, h, clr)
    tf = box(slide, x + 0.26, y + 0.14, w - 0.45, h - 0.24)
    if title:
        para(tf, title, fs, True, PETROL, GB, first=True, space_after=3)
    for i, ln in enumerate(body):
        para(tf, ln, fs, False, INK, GL, space_after=2, line=1.2,
             first=(not title and i == 0))


def term(slide, x, y, w, h, items, clr=TEAL):
    """용어 설명 박스: items = [(용어, 뜻), ...]"""
    rect(slide, x, y, w, h, LIGHT)
    rect(slide, x, y, 0.055, h, clr)
    tf = box(slide, x + 0.26, y + 0.14, w - 0.45, h - 0.24)
    para(tf, "처음 나오는 용어", 11.5, True, PETROL, GB, first=True, space_after=5)
    for k, v in items:
        p = tf.add_paragraph()
        p.space_after = Pt(4)
        p.line_spacing = 1.2
        r = p.add_run(); r.text = k + "  "
        setfont(r, 11.5, True, clr, GB)
        r = p.add_run(); r.text = v
        setfont(r, 11.5, False, INK, GL)


def foot(slide, text, label="▶ 우리 과제 적용", clr=TEAL):
    rect(slide, 0.52, 6.80, 12.29, 0.015, LINE)
    tf = box(slide, 0.52, 6.92, 12.29, 0.4)
    p = tf.paragraphs[0]
    r = p.add_run(); r.text = label + "   "
    setfont(r, 10.5, True, clr, GB)
    r = p.add_run(); r.text = text
    setfont(r, 10.5, False, INK, GL)
    p.space_after = Pt(0)


def pageno(slide, n):
    tf = box(slide, 12.2, 6.95, 0.7, 0.3)
    para(tf, str(n), 10, False, GRAY, GL, align=PP_ALIGN.RIGHT, first=True, space_after=0)


def cover(prs, title, subtitle, meta, rows=None, colw=None, rowh=0.44,
          rule_y=2.62, table_y=3.00, title_size=34):
    s = blank(prs)
    rect(s, 0, 0, 13.333, 7.5, PETROL)
    rect(s, 0, 0, 0.16, 7.5, TEAL)
    tf = box(s, 1.05, 1.10, 11.2, 1.3)
    para(tf, title, title_size, True, WHITE, GB, first=True, space_after=6)
    para(tf, subtitle, 23, False, RGBColor(0x9E, 0xC9, 0xC8), GM, space_after=0)
    rect(s, 1.05, rule_y, 2.6, 0.022, AMBER)
    if rows:
        shp = table(s, 1.05, table_y, sum(colw), rows, colw, fs=12, rowh=rowh, headclr=TEAL)
        for ri in range(1, len(rows)):
            for ci in range(len(colw)):
                c = shp.table.cell(ri, ci)
                c.fill.solid()
                c.fill.fore_color.rgb = DARK if ri % 2 else RGBColor(0x11, 0x44, 0x51)
                for p in c.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.color.rgb = WHITE if ci <= 1 else RGBColor(0xC8, 0xDC, 0xDE)
    tf = box(s, 1.05, 6.55, 11.2, 0.5)
    para(tf, meta, 11, False, RGBColor(0x8F, 0xB4, 0xB6), GL, first=True, space_after=0)
    return s
