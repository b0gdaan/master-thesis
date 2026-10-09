# -*- coding: utf-8 -*-
import os, re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted)
from reportlab.lib.styles import ParagraphStyle

BASE = r"D:\clear"
SRC = os.path.join(BASE, "thesis_russian.txt")
OUTDIR = os.path.join(BASE, "перевод")
os.makedirs(OUTDIR, exist_ok=True)
OUT = os.path.join(OUTDIR, "Магистерская_работа_RU.pdf")

MPL = r"C:\Users\Mini-ITX GAMER\AppData\Local\Programs\Python\Python314\Lib\site-packages\matplotlib\mpl-data\fonts\ttf"
pdfmetrics.registerFont(TTFont("DV", os.path.join(MPL, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", os.path.join(MPL, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DVI", os.path.join(MPL, "DejaVuSans-Oblique.ttf")))
pdfmetrics.registerFont(TTFont("DVM", os.path.join(MPL, "DejaVuSansMono.ttf")))
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVB")

body  = ParagraphStyle("body", fontName="DV", fontSize=10.5, leading=15, alignment=TA_JUSTIFY, spaceAfter=6)
h1    = ParagraphStyle("h1", fontName="DVB", fontSize=15, leading=19, spaceBefore=6, spaceAfter=10, textColor=colors.HexColor("#15406b"))
h2    = ParagraphStyle("h2", fontName="DVB", fontSize=12, leading=15, spaceBefore=10, spaceAfter=5, textColor=colors.HexColor("#21618c"))
mono  = ParagraphStyle("mono", fontName="DVM", fontSize=7.4, leading=9.3, spaceBefore=4, spaceAfter=8, backColor=colors.HexColor("#f4f6f8"), borderPadding=4, textColor=colors.HexColor("#222"))
note  = ParagraphStyle("note", fontName="DVI", fontSize=9.5, leading=13, spaceAfter=6, leftIndent=10, textColor=colors.HexColor("#555"))
li    = ParagraphStyle("li", parent=body, leftIndent=14, spaceAfter=3)
ttl   = ParagraphStyle("ttl", fontName="DVB", fontSize=17, leading=23, alignment=TA_CENTER, spaceAfter=10)
tsub  = ParagraphStyle("tsub", fontName="DV", fontSize=11.5, leading=16, alignment=TA_CENTER, spaceAfter=4)

def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
def is_div(l):  s=l.strip(); return len(s)>=4 and set(s)=={"="}
def is_dash(l): s=l.strip(); return len(s)>=3 and set(s)=={"-"}

with open(SRC, encoding="utf-8") as f:
    lines = f.read().split("\n")
N = len(lines)
story = []

# ---- Title page: first === block + following lines until the next === ----
i = 0
while i < N and not is_div(lines[i]): i += 1          # to first ===
heading = lines[i+1].strip() if i+1 < N else ""
i += 3                                                 # past === / title / ===
story.append(Spacer(1, 3*cm))
story.append(Paragraph(esc(heading), ttl))
story.append(Spacer(1, 0.6*cm))
while i < N and not is_div(lines[i]):
    s = lines[i].strip()
    if s: story.append(Paragraph(esc(s), tsub))
    i += 1
story.append(PageBreak())

# ---- Generic parse of the rest ----
para = []
first_sec = True   # title page already emitted a PageBreak; don't double it
def flush():
    t = " ".join(para).strip()
    para.clear()
    if t: story.append(Paragraph(esc(t), body))

while i < N:
    l = lines[i]
    if is_div(l) and i+2 < N and is_div(lines[i+2]):
        flush()
        if not first_sec: story.append(PageBreak())
        first_sec = False
        story.append(Paragraph(esc(lines[i+1].strip()), h1)); i += 3; continue
    if l.strip().startswith("```"):
        flush(); i += 1; code=[]
        while i < N and not lines[i].strip().startswith("```"): code.append(lines[i]); i += 1
        i += 1; story.append(Preformatted("\n".join(code) or " ", mono)); continue
    if "|" in l:
        flush(); tbl=[]
        while i < N and ("|" in lines[i] or (lines[i].strip() and set(lines[i].strip())<=set("-|+ :"))):
            tbl.append(lines[i].rstrip()); i += 1
        story.append(Preformatted("\n".join(tbl), mono)); continue
    if l.strip().startswith("[Рис"):     # [Рисунок ...]
        flush(); buf=[l.strip()]; i += 1
        while i < N and lines[i].strip() and "]" not in buf[-1]:
            buf.append(lines[i].strip()); i += 1
        story.append(Paragraph(esc(" ".join(buf)), note)); continue
    if l.strip() and i+1 < N and is_dash(lines[i+1]):
        flush(); story.append(Paragraph(esc(l.strip()), h2)); i += 2; continue
    if not l.strip():
        flush(); i += 1; continue
    st = l.strip()
    if re.match(r"^([-•*]|\d+[.)]|[a-zа-я][.)])\s", st):
        flush(); story.append(Paragraph(esc(st), li)); i += 1; continue
    para.append(l.strip()); i += 1
flush()

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DV", 8)
    canvas.setFillColor(colors.HexColor("#888"))
    canvas.drawCentredString(A4[0]/2, 1.1*cm, str(doc.page))
    canvas.restoreState()

doc = SimpleDocTemplate(OUT, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                        leftMargin=2.2*cm, rightMargin=2.2*cm,
                        title="Магистерская работа (перевод)",
                        author="Bogdan Babaev")
doc.build(story, onFirstPage=footer, onLaterPages=footer)
print("OK:", OUT)
print("size_kb:", round(os.path.getsize(OUT)/1024, 1))
