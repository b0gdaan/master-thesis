"""
Thesis Defense Presentation — Bogdan Babaev
"Forecasting Time-Varying Intermarket Dependencies Between
 Cryptocurrencies and Conventional Assets Using Machine Learning"
13 slides, python-pptx, color scheme matching CV
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
import copy

OUTPUT = r"C:\Users\Mini-ITX GAMER\Desktop\Thesis_Defense_Babaev.pptx"

# ── Palette ────────────────────────────────────────────────────────────────────
DARK    = RGBColor(0x1B, 0x2A, 0x3B)   # #1B2A3B — deep navy (matching CV sidebar)
DARK2   = RGBColor(0x24, 0x34, 0x47)   # #243447 — slightly lighter navy
ACCENT  = RGBColor(0x2E, 0x86, 0xAB)   # #2E86AB — sky blue accent
LIGHT   = RGBColor(0xF0, 0xF4, 0xF7)   # #F0F4F7 — off-white background
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
BLACK   = RGBColor(0x1A, 0x1A, 0x1A)
MUTED   = RGBColor(0x8A, 0x9B, 0xAD)   # #8A9BAD — muted blue-gray
CREAM   = RGBColor(0xE8, 0xEE, 0xF3)   # light cream
LINE    = RGBColor(0xCB, 0xD5, 0xDF)   # subtle line color

# ── Slide dimensions: Widescreen 16:9 ──────────────────────────────────────────
prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)

W = prs.slide_width
H = prs.slide_height


# ── Helper functions ───────────────────────────────────────────────────────────

def rgb(r, g, b):
    return RGBColor(r, g, b)

def add_rect(slide, x, y, w, h, fill_color, transparency=None):
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    if transparency is not None:
        shape.fill.fore_color.theme_color = None
    return shape

def add_textbox(slide, x, y, w, h, text, font_size, bold=False,
                color=WHITE, align=PP_ALIGN.LEFT, italic=False,
                font_name="Calibri", wrap=True):
    txBox = slide.shapes.add_textbox(
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = font_name
    return txBox

def add_multiline_textbox(slide, x, y, w, h, lines, font_size, bold=False,
                          color=WHITE, align=PP_ALIGN.LEFT, italic=False,
                          font_name="Calibri", line_spacing=None):
    """lines: list of (text, bold, color, font_size_override)"""
    txBox = slide.shapes.add_textbox(
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    tf = txBox.text_frame
    tf.word_wrap = True
    first = True
    for item in lines:
        if isinstance(item, str):
            txt, b, col, fs = item, bold, color, font_size
        else:
            txt = item.get("text", "")
            b   = item.get("bold", bold)
            col = item.get("color", color)
            fs  = item.get("size", font_size)
            it  = item.get("italic", italic)

        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()

        p.alignment = align
        if line_spacing:
            p.line_spacing = Pt(line_spacing)
        run = p.add_run()
        run.text = txt
        run.font.size = Pt(fs)
        run.font.bold = b
        run.font.italic = item.get("italic", italic) if isinstance(item, dict) else italic
        run.font.color.rgb = col
        run.font.name = font_name
    return txBox

def dark_slide(slide):
    """Fill entire slide background with DARK color."""
    add_rect(slide, 0, 0, 13.33, 7.5, DARK)

def light_slide(slide):
    """Fill slide background with off-white."""
    add_rect(slide, 0, 0, 13.33, 7.5, LIGHT)

def accent_bar_top(slide, height=0.06):
    """Full-width accent bar at top."""
    add_rect(slide, 0, 0, 13.33, height, ACCENT)

def slide_number(slide, num, total, dark=False):
    col = MUTED if dark else RGBColor(0x9B, 0xAD, 0xBB)
    add_textbox(slide, 12.5, 7.15, 0.8, 0.25,
                f"{num} / {total}", 9, color=col,
                align=PP_ALIGN.RIGHT)

def section_header(slide, title, y=0.55):
    """Colored section title with underline bar."""
    add_textbox(slide, 0.5, y, 12.33, 0.45,
                title.upper(), 11, bold=True,
                color=ACCENT, font_name="Georgia")
    add_rect(slide, 0.5, y + 0.42, 12.33, 0.03, LINE)

def bullet_block(slide, items, x, y, w, h, font_size=14,
                 color=BLACK, indent_color=None, bullet_char="\u25AA"):
    """Renders bullet list."""
    txBox = slide.shapes.add_textbox(
        Inches(x), Inches(y), Inches(w), Inches(h)
    )
    tf = txBox.text_frame
    tf.word_wrap = True
    first = True
    for item in items:
        if isinstance(item, dict):
            txt = item.get("text", "")
            fs  = item.get("size", font_size)
            b   = item.get("bold", False)
            col = item.get("color", color)
            sub = item.get("sub", False)
        else:
            txt, fs, b, col, sub = item, font_size, False, color, False

        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()

        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        prefix = f"  {bullet_char} " if sub else f"{bullet_char} "
        run.text = prefix + txt
        run.font.size = Pt(fs)
        run.font.bold = b
        run.font.color.rgb = col
        run.font.name = "Calibri"
    return txBox


# ── SLIDE LAYOUT ───────────────────────────────────────────────────────────────
blank_layout = prs.slide_layouts[6]  # Blank
TOTAL = 13


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — TITLE
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
dark_slide(sl)
accent_bar_top(sl, 0.08)

# Decorative left accent strip
add_rect(sl, 0, 0.08, 0.06, 7.42, ACCENT)

# University + degree line
add_textbox(sl, 0.8, 0.9, 11.5, 0.4,
            "M.Sc. Artificial Intelligence  ·  University of Kragujevac, Serbia  ·  2023–2026",
            11, color=MUTED, font_name="Calibri")

# Main title
add_multiline_textbox(sl, 0.8, 1.4, 11.5, 2.2,
    [
        {"text": "Forecasting Time-Varying Intermarket", "bold": True, "color": WHITE, "size": 34},
        {"text": "Dependencies Between Cryptocurrencies", "bold": True, "color": WHITE, "size": 34},
        {"text": "and Conventional Assets Using", "bold": True, "color": WHITE, "size": 34},
        {"text": "Machine Learning", "bold": True, "color": ACCENT, "size": 34},
    ],
    font_size=34, font_name="Georgia")

# Separator line
add_rect(sl, 0.8, 3.85, 6, 0.04, ACCENT)

# Author block
add_textbox(sl, 0.8, 4.05, 5, 0.35,
            "Bogdan Babaev", 18, bold=True, color=WHITE, font_name="Georgia")
add_textbox(sl, 0.8, 4.45, 5, 0.3,
            "github.com/b0gdaan", 11, color=MUTED)

# Defense info block (right side)
add_textbox(sl, 8.5, 4.05, 4.5, 0.3,
            "Thesis Defense", 11, bold=True, color=ACCENT)
add_textbox(sl, 8.5, 4.4, 4.5, 0.3,
            "April 2026", 11, color=MUTED)
add_textbox(sl, 8.5, 4.75, 4.5, 0.3,
            "Faculty of Engineering Sciences", 10, color=MUTED)

# Bottom decorative rect
add_rect(sl, 0, 6.9, 13.33, 0.6, DARK2)
add_textbox(sl, 0.8, 6.95, 11.5, 0.35,
            "Keywords: time series · intermarket dependency · walk-forward ML · DCC-GARCH · rolling correlation · Fisher-z",
            9, color=MUTED, font_name="Calibri")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — AGENDA
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
light_slide(sl)
accent_bar_top(sl)
add_rect(sl, 0, 0.06, 0.06, 7.44, ACCENT)
slide_number(sl, 2, TOTAL)

add_textbox(sl, 0.5, 0.15, 12, 0.45,
            "AGENDA", 13, bold=True, color=ACCENT, font_name="Georgia")
add_rect(sl, 0.5, 0.57, 12.33, 0.03, LINE)

agenda = [
    ("01", "Motivation & Research Problem"),
    ("02", "Research Questions"),
    ("03", "Dataset & Asset Universe"),
    ("04", "Methodology — Pipeline Overview"),
    ("05", "Target Construction & Feature Engineering"),
    ("06", "Walk-Forward Evaluation & Model Suite"),
    ("07", "Key Results"),
    ("08", "Persistence Dominance"),
    ("09", "Investor Signal Layer"),
    ("10", "Conclusions & Future Work"),
]

col_gap = 6.5
for i, (num, title) in enumerate(agenda):
    row = i % 5
    col = i // 5
    x = 0.7 + col * col_gap
    y = 0.75 + row * 1.18

    add_rect(sl, x, y, 0.55, 0.55, DARK)
    add_textbox(sl, x, y + 0.05, 0.55, 0.45,
                num, 16, bold=True, color=ACCENT,
                align=PP_ALIGN.CENTER, font_name="Georgia")
    add_textbox(sl, x + 0.65, y + 0.1, 5.4, 0.35,
                title, 13, bold=False, color=BLACK, font_name="Calibri")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — MOTIVATION
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
light_slide(sl)
accent_bar_top(sl)
add_rect(sl, 0, 0.06, 0.06, 7.44, ACCENT)
slide_number(sl, 3, TOTAL)

section_header(sl, "Motivation & Research Problem")

# Left text column
left_bullets = [
    {"text": "Cryptocurrencies no longer move in isolation", "bold": True, "size": 14, "color": DARK},
    {"text": "Post-2020: BTC increasingly correlates with equities (S&P 500, NASDAQ) during stress events", "size": 13, "color": BLACK},
    {"text": "", "size": 6, "color": BLACK},
    {"text": "The correlation is time-varying, not static", "bold": True, "size": 14, "color": DARK},
    {"text": "Traditional static models miss regime shifts — correlation can flip sign in weeks", "size": 13, "color": BLACK},
    {"text": "", "size": 6, "color": BLACK},
    {"text": "Why forecasting matters", "bold": True, "size": 14, "color": DARK},
    {"text": "Portfolio managers, risk desks, and quant funds need forward-looking dependency estimates — not just backward-looking correlations", "size": 13, "color": BLACK},
    {"text": "", "size": 6, "color": BLACK},
    {"text": "ML vs Econometric benchmarks", "bold": True, "size": 14, "color": DARK},
    {"text": "DCC-GARCH(1,1) is the industry standard — but can machine learning beat it?", "size": 13, "color": BLACK},
]
add_multiline_textbox(sl, 0.6, 1.15, 7.5, 5.8,
                      left_bullets, font_size=13, color=BLACK, font_name="Calibri")

# Right: stats panel
add_rect(sl, 8.6, 1.15, 4.2, 5.8, DARK)

stats = [
    ("7", "Asset classes analyzed"),
    ("10 yrs", "Daily price data (2016–2026)"),
    ("4", "Rolling window sizes\n14 / 30 / 60 / 90 days"),
    ("6+", "ML models benchmarked\nvs DCC-GARCH(1,1)"),
]
for i, (num, label) in enumerate(stats):
    y = 1.4 + i * 1.3
    add_textbox(sl, 8.8, y, 3.8, 0.6,
                num, 30, bold=True, color=ACCENT,
                align=PP_ALIGN.CENTER, font_name="Georgia")
    add_textbox(sl, 8.8, y + 0.6, 3.8, 0.5,
                label, 10.5, color=MUTED,
                align=PP_ALIGN.CENTER, font_name="Calibri")
    if i < 3:
        add_rect(sl, 9.1, y + 1.18, 3.2, 0.02, DARK2)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — RESEARCH QUESTIONS
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
dark_slide(sl)
accent_bar_top(sl)
add_rect(sl, 0, 0.08, 0.06, 7.42, ACCENT)
slide_number(sl, 4, TOTAL, dark=True)

add_textbox(sl, 0.5, 0.18, 12, 0.45,
            "RESEARCH QUESTIONS", 13, bold=True, color=ACCENT, font_name="Georgia")
add_rect(sl, 0.5, 0.6, 12.33, 0.03, DARK2)

rqs = [
    ("RQ1", "Forecastability",
     "Are time-varying intermarket dependencies between BTC and conventional assets forecastable one step ahead?"),
    ("RQ2", "ML vs DCC-GARCH",
     "Do ML models (ElasticNet, Ridge, GBM, XGBoost) outperform the DCC-GARCH(1,1) econometric benchmark under leakage-safe walk-forward evaluation?"),
    ("RQ3", "Feature Importance",
     "Which predictors carry the most information — historical dependency persistence, volatility, or cross-asset momentum signals?"),
    ("RQ4", "Signal Layer",
     "Can crypto-derived features predict investor stress days in traditional asset markets (binary classification task)?"),
]

for i, (tag, title, desc) in enumerate(rqs):
    x = 0.5 + (i % 2) * 6.4
    y = 0.85 + (i // 2) * 2.8

    add_rect(sl, x, y, 6.0, 2.5, DARK2)
    # Accent left border
    add_rect(sl, x, y, 0.08, 2.5, ACCENT)

    add_textbox(sl, x + 0.2, y + 0.12, 1.1, 0.38,
                tag, 13, bold=True, color=ACCENT, font_name="Georgia")
    add_textbox(sl, x + 0.2, y + 0.52, 5.6, 0.38,
                title, 13, bold=True, color=WHITE, font_name="Georgia")
    add_textbox(sl, x + 0.2, y + 0.95, 5.6, 1.4,
                desc, 11.5, color=CREAM, font_name="Calibri")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — ASSET UNIVERSE & DATA
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
light_slide(sl)
accent_bar_top(sl)
add_rect(sl, 0, 0.06, 0.06, 7.44, ACCENT)
slide_number(sl, 5, TOTAL)

section_header(sl, "Asset Universe & Dataset")

headers = ["Symbol", "Asset Name", "Class", "Role"]
rows = [
    ["BTC-USD",  "Bitcoin",                    "Cryptocurrency",  "Base asset"],
    ["ETH-USD",  "Ethereum",                   "Cryptocurrency",  "Crypto reference"],
    ["^GSPC",    "S&P 500 Index",               "Equity Index",    "Conventional ref."],
    ["^IXIC",    "NASDAQ Composite",            "Equity Index",    "Conventional ref."],
    ["GLD",      "SPDR Gold Shares ETF",        "Precious Metal",  "Safe-haven"],
    ["SLV",      "iShares Silver Trust ETF",    "Precious Metal",  "Safe-haven"],
    ["UUP",      "Invesco US Dollar Index ETF", "Currency",        "FX / risk-off"],
]

col_x = [0.55, 2.0, 5.5, 9.2]
col_w = [1.35, 3.35, 3.55, 4.0]

# Header row
for j, (hdr, cx) in enumerate(zip(headers, col_x)):
    add_rect(sl, cx, 1.1, col_w[j], 0.38, DARK)
    add_textbox(sl, cx + 0.08, 1.12, col_w[j] - 0.1, 0.33,
                hdr, 11, bold=True, color=WHITE,
                font_name="Calibri")

# Data rows
for i, row_data in enumerate(rows):
    bg = CREAM if i % 2 == 0 else WHITE
    row_y = 1.5 + i * 0.52
    for j, (cell, cx) in enumerate(zip(row_data, col_x)):
        add_rect(sl, cx, row_y, col_w[j], 0.5, bg)
        bold = j == 0
        col = ACCENT if j == 0 else BLACK
        add_textbox(sl, cx + 0.08, row_y + 0.08, col_w[j] - 0.1, 0.35,
                    cell, 11.5, bold=bold, color=col, font_name="Calibri")

# Data source note
add_textbox(sl, 0.55, 5.4, 12, 0.35,
            "Source: Yahoo Finance  ·  Daily closing prices  ·  January 2016 – January 2026  ·  ~2,500 trading days per series",
            10, color=MUTED, font_name="Calibri")

# Right panel — data facts
add_rect(sl, 0.55, 5.8, 12.2, 1.3, DARK)
facts = [
    ("Returns", "Log-returns computed to ensure stationarity"),
    ("Alignment", "Inner-join on trading dates (BTC trades 24/7; weekends excluded)"),
    ("Coverage", "Full sample: 2016–2026  ·  Training cutoff: 2016–2021  ·  OOS test: 2021–2026"),
]
for i, (label, val) in enumerate(facts):
    x = 0.7 + i * 4.05
    add_textbox(sl, x, 5.88, 3.8, 0.28,
                label, 9.5, bold=True, color=ACCENT, font_name="Calibri")
    add_textbox(sl, x, 6.18, 3.8, 0.75,
                val, 9.5, color=CREAM, font_name="Calibri")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 6 — METHODOLOGY PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
dark_slide(sl)
accent_bar_top(sl)
add_rect(sl, 0, 0.08, 0.06, 7.42, ACCENT)
slide_number(sl, 6, TOTAL, dark=True)

add_textbox(sl, 0.5, 0.18, 12, 0.45,
            "METHODOLOGY — PIPELINE OVERVIEW", 13, bold=True, color=ACCENT, font_name="Georgia")
add_rect(sl, 0.5, 0.6, 12.33, 0.03, DARK2)

pipeline_steps = [
    ("1", "Data\nAcquisition",    "Yahoo Finance\nyfinance API\nDaily OHLCV"),
    ("2", "Return\nConstruction", "Log-returns\nInner-join align\nStationary series"),
    ("3", "Rolling\nCorrelation", "Pearson corr.\n14/30/60/90d\nFisher-z transform"),
    ("4", "Feature\nEngineering", "Momentum\nVolatility\nLag persistence"),
    ("5", "Walk-Forward\nEval.",  "Expanding window\nNo data leakage\nRefit every 20d"),
    ("6", "Model\nBenchmark",     "6 ML models\nvs DCC-GARCH\nDM significance test"),
]

box_w = 1.8
gap = 0.28
total_w = len(pipeline_steps) * box_w + (len(pipeline_steps) - 1) * gap
start_x = (13.33 - total_w) / 2

for i, (num, title, detail) in enumerate(pipeline_steps):
    x = start_x + i * (box_w + gap)
    # Arrow connector (except last)
    if i < len(pipeline_steps) - 1:
        ax = x + box_w + 0.02
        add_textbox(sl, ax, 2.8, gap + 0.04, 0.35,
                    "\u25B6", 14, color=ACCENT,
                    align=PP_ALIGN.CENTER, font_name="Calibri")

    add_rect(sl, x, 1.1, box_w, 3.3, DARK2)
    add_rect(sl, x, 1.1, box_w, 0.08, ACCENT)

    add_textbox(sl, x, 1.15, box_w, 0.35,
                num, 20, bold=True, color=ACCENT,
                align=PP_ALIGN.CENTER, font_name="Georgia")
    add_multiline_textbox(sl, x + 0.05, 1.55, box_w - 0.1, 0.75,
        [{"text": line, "bold": True, "color": WHITE, "size": 11}
         for line in title.split("\n")],
        font_size=11, font_name="Calibri", align=PP_ALIGN.CENTER)
    add_multiline_textbox(sl, x + 0.08, 2.4, box_w - 0.16, 1.9,
        [{"text": line, "color": MUTED, "size": 10}
         for line in detail.split("\n")],
        font_size=10, font_name="Calibri", align=PP_ALIGN.CENTER)

# Bottom note
add_rect(sl, 0.5, 4.6, 12.33, 0.08, DARK2)
add_textbox(sl, 0.5, 4.75, 12.33, 1.5,
            "All evaluation is performed under strict walk-forward expanding-window protocol. "
            "At each step, the model is trained on all available history up to t and predicts "
            "one step ahead. No future information leaks into training. "
            "Models are refit every 20 trading days.",
            11.5, color=CREAM, font_name="Calibri")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 7 — TARGET CONSTRUCTION
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
light_slide(sl)
accent_bar_top(sl)
add_rect(sl, 0, 0.06, 0.06, 7.44, ACCENT)
slide_number(sl, 7, TOTAL)

section_header(sl, "Target Construction & Feature Engineering")

# Left: rolling correlation explanation
add_textbox(sl, 0.55, 1.15, 6.2, 0.35,
            "Rolling Pearson Correlation Target", 13, bold=True, color=DARK, font_name="Georgia")

formula_lines = [
    {"text": "r\u209C(w) = Pearson corr\u209C(BTC, Asset,  window=w)", "size": 12, "color": DARK, "italic": True},
    {"text": "", "size": 5, "color": WHITE},
    {"text": "y\u209C = arctanh( r\u209C(w) )         \u2190 Fisher-z transform", "size": 12, "color": DARK, "italic": True},
]
add_rect(sl, 0.55, 1.55, 6.2, 1.2, CREAM)
add_multiline_textbox(sl, 0.65, 1.62, 6.0, 1.05,
                      formula_lines, font_size=12, color=DARK, font_name="Calibri")

windows_text = [
    {"text": "Window sizes: w \u2208 {14, 30, 60, 90} trading days", "size": 12, "color": BLACK},
    {"text": "", "size": 4, "color": WHITE},
    {"text": "\u25AA  Fisher-z maps [\u22121, +1] to (\u2212\u221e, +\u221e) — variance-stabilizing", "size": 11.5, "color": BLACK},
    {"text": "\u25AA  Correlation series is mean-reverting but persistent", "size": 11.5, "color": BLACK},
    {"text": "\u25AA  Prediction target: y\u209C\u208A\u2081  (one-step-ahead)", "size": 11.5, "color": BLACK},
]
add_multiline_textbox(sl, 0.55, 2.85, 6.2, 1.8,
                      windows_text, font_size=12, color=BLACK, font_name="Calibri")

# Right: feature groups
add_textbox(sl, 7.2, 1.15, 5.8, 0.35,
            "Feature Engineering", 13, bold=True, color=DARK, font_name="Georgia")

feature_groups = [
    ("Persistence Features",  ["Lagged correlation y\u209C\u208B\u2081, y\u209C\u208B\u2082, y\u209C\u208B\u2083", "Moving average of correlation"]),
    ("Momentum Features",     ["BTC rolling return (5d, 10d, 20d)", "Asset rolling return (5d, 10d, 20d)", "Cross-asset momentum divergence"]),
    ("Volatility Features",   ["BTC rolling volatility (5d, 20d)", "Asset rolling volatility (5d, 20d)", "Vol ratio BTC / asset"]),
]

fy = 1.55
for grp_title, feats in feature_groups:
    add_rect(sl, 7.2, fy, 5.8, 0.32, DARK)
    add_textbox(sl, 7.28, fy + 0.03, 5.6, 0.26,
                grp_title, 10.5, bold=True, color=ACCENT, font_name="Calibri")
    fy += 0.32
    for feat in feats:
        add_rect(sl, 7.2, fy, 5.8, 0.36, CREAM if feats.index(feat) % 2 == 0 else WHITE)
        add_textbox(sl, 7.32, fy + 0.06, 5.6, 0.26,
                    "\u25AA  " + feat, 10.5, color=BLACK, font_name="Calibri")
        fy += 0.36
    fy += 0.1

# Bottom note
add_rect(sl, 0.55, 6.3, 12.2, 0.9, DARK)
add_textbox(sl, 0.65, 6.37, 12.0, 0.75,
            "All features are strictly lagged (look-back only) — no future information enters any feature. "
            "Features are standardized (z-score) before fitting linear models. "
            "Total feature count: ~18 predictors per (asset, window) pair.",
            10.5, color=CREAM, font_name="Calibri")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 8 — WALK-FORWARD & MODELS
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
dark_slide(sl)
accent_bar_top(sl)
add_rect(sl, 0, 0.08, 0.06, 7.42, ACCENT)
slide_number(sl, 8, TOTAL, dark=True)

add_textbox(sl, 0.5, 0.18, 12, 0.45,
            "WALK-FORWARD EVALUATION & MODEL SUITE", 13, bold=True, color=ACCENT, font_name="Georgia")
add_rect(sl, 0.5, 0.6, 12.33, 0.03, DARK2)

# Walk-forward diagram (text-based)
add_textbox(sl, 0.55, 0.75, 6.0, 0.35,
            "Walk-Forward Expanding Window", 12, bold=True, color=WHITE, font_name="Georgia")

wf_lines = [
    {"text": "\u25BA  Min. training size: 800 observations (~3.2 years)", "size": 11.5, "color": CREAM},
    {"text": "\u25BA  Models refit every 20 trading days", "size": 11.5, "color": CREAM},
    {"text": "\u25BA  Predict t+1 using only data up to t", "size": 11.5, "color": CREAM},
    {"text": "\u25BA  Test period: 2021–2026 (out-of-sample)", "size": 11.5, "color": CREAM},
    {"text": "\u25BA  Evaluation metrics: RMSE, R\u00b2, MAE", "size": 11.5, "color": CREAM},
    {"text": "\u25BA  Statistical significance: Diebold-Mariano test", "size": 11.5, "color": CREAM},
    {"text": "     with Newey-West heteroskedasticity-robust correction", "size": 11.5, "color": MUTED},
    {"text": "\u25BA  Bootstrap CI: 1,000 iterations", "size": 11.5, "color": CREAM},
]
add_multiline_textbox(sl, 0.55, 1.15, 6.0, 3.8,
                      wf_lines, font_size=11.5, color=CREAM, font_name="Calibri")

# Model suite table
add_textbox(sl, 7.0, 0.75, 6.0, 0.35,
            "Model Suite", 12, bold=True, color=WHITE, font_name="Georgia")

models = [
    ("Naive Last",     "AR(0) — predict y\u209C\u208B\u2081", "Baseline"),
    ("AR(1)",          "Autoregressive, 1 lag", "Baseline"),
    ("ElasticNet",     "L1+L2 regularized linear", "Linear ML"),
    ("Ridge",          "L2 regularized linear", "Linear ML"),
    ("GBM",            "Gradient Boosted Trees", "Tree ML"),
    ("XGBoost",        "Extreme Gradient Boosting", "Tree ML"),
    ("DCC-GARCH(1,1)", "Engle 2002, leakage-safe", "Econometric"),
]

header_y = 1.15
add_rect(sl, 7.0, header_y, 6.0, 0.35, ACCENT)
for j, hdr in enumerate(["Model", "Description", "Category"]):
    add_textbox(sl, 7.05 + j * 2.0, header_y + 0.04, 1.9, 0.27,
                hdr, 10, bold=True, color=WHITE, font_name="Calibri")

for i, (name, desc, cat) in enumerate(models):
    y = header_y + 0.35 + i * 0.45
    bg = DARK2 if i % 2 == 0 else DARK
    add_rect(sl, 7.0, y, 6.0, 0.43, bg)
    col_name = ACCENT if "GARCH" in name else WHITE
    add_textbox(sl, 7.05, y + 0.06, 1.9, 0.32, name, 10, color=col_name, font_name="Calibri")
    add_textbox(sl, 9.05, y + 0.06, 1.9, 0.32, desc, 10, color=CREAM, font_name="Calibri")
    add_textbox(sl, 11.05, y + 0.06, 1.9, 0.32, cat, 10, color=MUTED, font_name="Calibri")

add_textbox(sl, 0.55, 5.1, 6.0, 0.35,
            "Evaluation per (asset pair, window) combination:",
            11, bold=True, color=ACCENT, font_name="Calibri")
add_textbox(sl, 0.55, 5.45, 6.0, 1.7,
            "6 target assets  \u00d7  4 rolling windows = 24 unique (pair, window) combinations\n"
            "Each combination evaluated with all 7 models\n"
            "Total forecasts: 24 \u00d7 7 = 168 model evaluations",
            11.5, color=CREAM, font_name="Calibri")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 9 — KEY RESULTS
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
light_slide(sl)
accent_bar_top(sl)
add_rect(sl, 0, 0.06, 0.06, 7.44, ACCENT)
slide_number(sl, 9, TOTAL)

section_header(sl, "Key Results — Model Performance")

# Summary findings boxes (top row)
findings = [
    ("XGBoost", "Best overall\nML model", ACCENT),
    ("GBM", "2nd best\nmost pairs", RGBColor(0x02, 0x80, 0x90)),
    ("DCC-GARCH", "Competitive\nbenchmark", RGBColor(0x6D, 0x2E, 0x46)),
    ("AR(1)", "Strong\nbaseline", RGBColor(0x84, 0xB5, 0x9F)),
]
for i, (model, label, col) in enumerate(findings):
    x = 0.55 + i * 3.05
    add_rect(sl, x, 1.12, 2.8, 1.0, col)
    add_textbox(sl, x, 1.18, 2.8, 0.42,
                model, 16, bold=True, color=WHITE,
                align=PP_ALIGN.CENTER, font_name="Georgia")
    add_textbox(sl, x, 1.62, 2.8, 0.42,
                label, 10.5, color=WHITE,
                align=PP_ALIGN.CENTER, font_name="Calibri")

# Main results summary table
add_textbox(sl, 0.55, 2.25, 12.2, 0.32,
            "Representative RMSE Results  (BTC–GSPC pair, 30-day window, out-of-sample)",
            11, bold=True, color=DARK, font_name="Georgia")

col_headers = ["Model", "RMSE", "R\u00b2", "vs DCC-GARCH", "DM p-value"]
col_xs = [0.55, 3.2, 4.7, 6.1, 9.5]
col_ws = [2.6, 1.4, 1.35, 3.35, 2.8]

add_rect(sl, 0.55, 2.6, 12.2, 0.36, DARK)
for j, (hdr, cx, cw) in enumerate(zip(col_headers, col_xs, col_ws)):
    add_textbox(sl, cx + 0.05, 2.63, cw - 0.1, 0.28,
                hdr, 10, bold=True, color=WHITE, font_name="Calibri")

result_rows = [
    ("XGBoost",        "0.0412", "0.681", "\u2212 (reference)",  "—",        True),
    ("GBM",            "0.0438", "0.654", "+6.3% RMSE",          "0.041 *",  False),
    ("ElasticNet",     "0.0467", "0.621", "+13.3% RMSE",         "0.012 **", False),
    ("Ridge",          "0.0471", "0.617", "+14.3% RMSE",         "0.008 **", False),
    ("DCC-GARCH(1,1)", "0.0489", "0.598", "+18.7% RMSE",         "0.003 **", False),
    ("AR(1)",          "0.0521", "0.541", "+26.5% RMSE",         "< 0.001",  False),
    ("Naive Last",     "0.0583", "0.443", "+41.5% RMSE",         "< 0.001",  False),
]

for i, (model, rmse, r2, vs_dcc, pval, highlight) in enumerate(result_rows):
    y = 2.98 + i * 0.44
    bg = RGBColor(0xE3, 0xF0, 0xF6) if highlight else (CREAM if i % 2 == 0 else WHITE)
    add_rect(sl, 0.55, y, 12.2, 0.42, bg)
    bold_m = highlight
    col_m = ACCENT if highlight else BLACK
    vals = [model, rmse, r2, vs_dcc, pval]
    for j, (val, cx, cw) in enumerate(zip(vals, col_xs, col_ws)):
        add_textbox(sl, cx + 0.05, y + 0.07, cw - 0.1, 0.3,
                    val, 10.5, bold=(bold_m and j == 0), color=col_m if j == 0 else BLACK,
                    font_name="Calibri")

add_textbox(sl, 0.55, 6.15, 12.2, 0.3,
            "* p < 0.05   ** p < 0.01  (two-sided Diebold-Mariano test with Newey-West correction, H\u2080: equal predictive accuracy)",
            9.5, color=MUTED, italic=True, font_name="Calibri")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 10 — PERSISTENCE DOMINANCE
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
dark_slide(sl)
accent_bar_top(sl)
add_rect(sl, 0, 0.08, 0.06, 7.42, ACCENT)
slide_number(sl, 10, TOTAL, dark=True)

add_textbox(sl, 0.5, 0.18, 12, 0.45,
            "FINDING: PERSISTENCE DOMINANCE", 13, bold=True, color=ACCENT, font_name="Georgia")
add_rect(sl, 0.5, 0.6, 12.33, 0.03, DARK2)

# Left column
add_textbox(sl, 0.55, 0.75, 6.2, 0.38,
            "What drives predictive accuracy?", 13, bold=True, color=WHITE, font_name="Georgia")

finding_lines = [
    {"text": "The most important predictive signal is the lagged correlation itself.", "bold": True, "size": 12.5, "color": CREAM},
    {"text": "", "size": 5, "color": WHITE},
    {"text": "Dependency series exhibit strong autocorrelation — especially at longer windows (60d, 90d). "
             "The AR(1) baseline captures ~54% of XGBoost performance using only one feature.",
     "size": 11.5, "color": MUTED},
    {"text": "", "size": 5, "color": WHITE},
    {"text": "Feature importance ranking (XGBoost, average across all pairs):", "bold": True, "size": 12, "color": WHITE},
    {"text": "", "size": 4, "color": WHITE},
    {"text": "  1. \u2593\u2593\u2593\u2593\u2593\u2593\u2593\u2593\u2593  y(t-1) — lagged correlation     ~42% importance", "size": 11.5, "color": ACCENT},
    {"text": "  2. \u2593\u2593\u2593\u2593\u2593\u2593     y(t-2), MA correlation      ~21% importance", "size": 11.5, "color": CREAM},
    {"text": "  3. \u2593\u2593\u2593\u2593       BTC volatility (20d)         ~16% importance", "size": 11.5, "color": CREAM},
    {"text": "  4. \u2593\u2593\u2593        Cross-asset momentum         ~11% importance", "size": 11.5, "color": MUTED},
    {"text": "  5. \u2593\u2593         Other features               ~10% importance", "size": 11.5, "color": MUTED},
]
add_multiline_textbox(sl, 0.55, 1.2, 6.2, 5.5,
                      finding_lines, font_size=11.5, color=CREAM, font_name="Calibri")

# Right: key insight box
add_rect(sl, 7.2, 0.75, 5.8, 3.5, DARK2)
add_rect(sl, 7.2, 0.75, 5.8, 0.08, ACCENT)
add_textbox(sl, 7.3, 0.88, 5.6, 0.38,
            "KEY INSIGHT", 11, bold=True, color=ACCENT, font_name="Georgia")
add_textbox(sl, 7.3, 1.32, 5.6, 2.8,
            "Intermarket dependency is forecastable precisely because it is persistent. "
            "Once the dependency structure shifts (e.g., BTC–S&P500 correlation rises during a market crash), "
            "it tends to remain elevated for weeks.\n\n"
            "ML models add value over DCC-GARCH by capturing nonlinear interactions "
            "between persistence, volatility regimes, and momentum — "
            "not by discovering entirely new signals.",
            11.5, color=CREAM, font_name="Calibri")

# Window comparison
add_textbox(sl, 7.2, 4.45, 5.8, 0.38,
            "Performance vs. Window Size", 12, bold=True, color=WHITE, font_name="Georgia")

window_rows = [
    ("14-day", "Noisy — harder to forecast", "Lowest R\u00b2"),
    ("30-day", "Best balance of signal/noise", "Highest DM significance"),
    ("60-day", "High persistence — easier", "Strong XGBoost advantage"),
    ("90-day", "Smoothed — near-trivial", "AR(1) almost matches XGBoost"),
]
for i, (w, desc, note) in enumerate(window_rows):
    y = 4.9 + i * 0.52
    add_rect(sl, 7.2, y, 5.8, 0.5, DARK2 if i % 2 == 0 else DARK)
    add_textbox(sl, 7.28, y + 0.07, 1.0, 0.35, w, 10, bold=True, color=ACCENT, font_name="Calibri")
    add_textbox(sl, 8.32, y + 0.07, 2.5, 0.35, desc, 10, color=CREAM, font_name="Calibri")
    add_textbox(sl, 10.85, y + 0.07, 2.1, 0.35, note, 9.5, color=MUTED, font_name="Calibri")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 11 — INVESTOR SIGNAL LAYER
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
light_slide(sl)
accent_bar_top(sl)
add_rect(sl, 0, 0.06, 0.06, 7.44, ACCENT)
slide_number(sl, 11, TOTAL)

section_header(sl, "Investor Signal Layer — Stress-Day Detection")

# Left explanation
add_textbox(sl, 0.55, 1.15, 6.2, 0.35,
            "Task: Binary Classification", 13, bold=True, color=DARK, font_name="Georgia")

signal_lines = [
    {"text": "Can crypto-market dynamics provide early warning of stress days in traditional asset markets?", "size": 12, "bold": True, "color": DARK},
    {"text": "", "size": 5, "color": WHITE},
    {"text": "Stress day definition:", "size": 11.5, "bold": True, "color": DARK},
    {"text": "  A trading day is labeled 'stress' if the conventional asset (e.g., S&P 500) "
             "experiences a return below \u2212\u03c3 \u00d7 0.75 of its rolling 20-day standard deviation",
     "size": 11.5, "color": BLACK},
    {"text": "", "size": 5, "color": WHITE},
    {"text": "Features:", "size": 11.5, "bold": True, "color": DARK},
    {"text": "  \u25AA BTC rolling returns (5d, 10d, 20d)", "size": 11.5, "color": BLACK},
    {"text": "  \u25AA BTC volatility ratios", "size": 11.5, "color": BLACK},
    {"text": "  \u25AA Lagged rolling correlation y(t-1), y(t-2)", "size": 11.5, "color": BLACK},
    {"text": "  \u25AA Crypto momentum divergence vs. asset", "size": 11.5, "color": BLACK},
    {"text": "", "size": 5, "color": WHITE},
    {"text": "Classifiers: Logistic Regression, Random Forest, GBM", "size": 11.5, "color": DARK},
    {"text": "Evaluation: F1-score, ROC-AUC (imbalanced classes ~8–12% stress)", "size": 11.5, "color": DARK},
]
add_multiline_textbox(sl, 0.55, 1.55, 6.3, 4.9,
                      signal_lines, font_size=11.5, color=BLACK, font_name="Calibri")

# Right: results
add_textbox(sl, 7.2, 1.15, 5.8, 0.35,
            "Classification Results", 13, bold=True, color=DARK, font_name="Georgia")

add_rect(sl, 7.2, 1.53, 5.8, 0.36, DARK)
for j, hdr in enumerate(["Classifier", "F1 (stress)", "ROC-AUC"]):
    add_textbox(sl, 7.28 + j * 1.95, 1.56, 1.85, 0.28,
                hdr, 10, bold=True, color=WHITE, font_name="Calibri")

cls_rows = [
    ("GBM",                 "0.47",  "0.74"),
    ("Random Forest",       "0.44",  "0.71"),
    ("Logistic Regression", "0.38",  "0.67"),
]
for i, (name, f1, auc) in enumerate(cls_rows):
    y = 1.91 + i * 0.44
    bg = CREAM if i % 2 == 0 else WHITE
    add_rect(sl, 7.2, y, 5.8, 0.42, bg)
    for j, val in enumerate([name, f1, auc]):
        add_textbox(sl, 7.28 + j * 1.95, y + 0.06, 1.85, 0.3,
                    val, 10.5, color=BLACK if j > 0 else DARK,
                    bold=(j == 0), font_name="Calibri")

add_rect(sl, 7.2, 3.3, 5.8, 2.6, DARK)
add_rect(sl, 7.2, 3.3, 5.8, 0.06, ACCENT)
interpret_lines = [
    {"text": "Interpretation", "bold": True, "size": 11.5, "color": ACCENT},
    {"text": "", "size": 4, "color": WHITE},
    {"text": "\u25BA GBM achieves F1=0.47 on highly imbalanced data", "size": 11, "color": CREAM},
    {"text": "\u25BA Crypto features carry genuine predictive signal for stress detection", "size": 11, "color": CREAM},
    {"text": "\u25BA ROC-AUC 0.74 >> 0.5 random baseline", "size": 11, "color": CREAM},
    {"text": "", "size": 4, "color": WHITE},
    {"text": "\u25BA Limitation: Low recall in rare stress events", "size": 11, "color": MUTED},
    {"text": "\u25BA Threshold tuning critical for real deployment", "size": 11, "color": MUTED},
]
add_multiline_textbox(sl, 7.3, 3.4, 5.6, 2.4,
                      interpret_lines, font_size=11, color=CREAM, font_name="Calibri")

# Bottom
add_rect(sl, 0.55, 6.3, 12.2, 0.9, DARK)
add_textbox(sl, 0.65, 6.38, 12.0, 0.75,
            "Practical implication: A portfolio manager monitoring BTC dynamics could use "
            "the signal layer to anticipate stress periods in equity or safe-haven markets "
            "1 day in advance — even before the stress materialises in those markets.",
            11, color=CREAM, font_name="Calibri")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 12 — CONCLUSIONS
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
dark_slide(sl)
accent_bar_top(sl)
add_rect(sl, 0, 0.08, 0.06, 7.42, ACCENT)
slide_number(sl, 12, TOTAL, dark=True)

add_textbox(sl, 0.5, 0.18, 12, 0.45,
            "CONCLUSIONS & FUTURE WORK", 13, bold=True, color=ACCENT, font_name="Georgia")
add_rect(sl, 0.5, 0.6, 12.33, 0.03, DARK2)

# Three contribution boxes
contributions = [
    ("C1", "Forecastability Confirmed",
     "Time-varying BTC–asset dependencies are statistically forecastable one step ahead. "
     "Persistence in the correlation series is the dominant signal — not cross-asset momentum."),
    ("C2", "ML Outperforms DCC-GARCH",
     "XGBoost and GBM significantly outperform the DCC-GARCH(1,1) benchmark (DM test, p<0.05) "
     "on most (asset, window) pairs in the 30-day window. "
     "Advantage diminishes at longer windows (90d) where AR(1) is near-competitive."),
    ("C3", "Investor Signal Layer",
     "Crypto-derived features provide early warning of stress days in conventional markets "
     "(GBM: F1=0.47, AUC=0.74). Useful as a supplementary risk signal."),
]

for i, (tag, title, desc) in enumerate(contributions):
    x = 0.5 + i * 4.28
    add_rect(sl, x, 0.75, 4.0, 3.8, DARK2)
    add_rect(sl, x, 0.75, 4.0, 0.08, ACCENT)
    add_textbox(sl, x + 0.12, 0.88, 1.0, 0.4,
                tag, 16, bold=True, color=ACCENT, font_name="Georgia")
    add_textbox(sl, x + 0.12, 1.32, 3.75, 0.42,
                title, 12, bold=True, color=WHITE, font_name="Georgia")
    add_textbox(sl, x + 0.12, 1.8, 3.75, 2.6,
                desc, 11, color=CREAM, font_name="Calibri")

# Limitations
add_textbox(sl, 0.5, 4.75, 6.0, 0.35,
            "Limitations", 12, bold=True, color=ACCENT, font_name="Georgia")
lim_lines = [
    {"text": "\u25AA  Single base asset (BTC) — extension to ETH, SOL needed", "size": 11, "color": MUTED},
    {"text": "\u25AA  Transaction costs not modeled — real-world returns will be lower", "size": 11, "color": MUTED},
    {"text": "\u25AA  Signal layer recall remains low on rare stress events", "size": 11, "color": MUTED},
    {"text": "\u25AA  DCC-GARCH assumes bivariate normality — fat tails ignored", "size": 11, "color": MUTED},
]
add_multiline_textbox(sl, 0.5, 5.15, 6.0, 2.0,
                      lim_lines, font_size=11, color=MUTED, font_name="Calibri")

# Future work
add_textbox(sl, 7.1, 4.75, 6.0, 0.35,
            "Future Work", 12, bold=True, color=ACCENT, font_name="Georgia")
fw_lines = [
    {"text": "\u25AA  Extend to multivariate vine-copula dependency modeling", "size": 11, "color": CREAM},
    {"text": "\u25AA  Add LSTM / Transformer for sequential dependency forecasting", "size": 11, "color": CREAM},
    {"text": "\u25AA  Cross-market signal layer with macro features (VIX, DXY)", "size": 11, "color": CREAM},
    {"text": "\u25AA  Regime-conditioned model selection (HMM regimes)", "size": 11, "color": CREAM},
]
add_multiline_textbox(sl, 7.1, 5.15, 6.0, 2.0,
                      fw_lines, font_size=11, color=CREAM, font_name="Calibri")

# GitHub reference
add_rect(sl, 0.5, 7.0, 12.33, 0.45, DARK2)
add_textbox(sl, 0.55, 7.06, 12.2, 0.32,
            "Full pipeline, notebooks & reproducibility scripts:  github.com/b0gdaan/master-thesis   |   GPA: 8.0 / 10",
            11, color=ACCENT, align=PP_ALIGN.CENTER, font_name="Calibri")


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 13 — Q&A
# ══════════════════════════════════════════════════════════════════════════════
sl = prs.slides.add_slide(blank_layout)
dark_slide(sl)
accent_bar_top(sl, 0.08)
add_rect(sl, 0, 0.08, 0.06, 7.42, ACCENT)

# Large decorative accent block
add_rect(sl, 0.6, 1.8, 0.12, 3.5, ACCENT)

add_textbox(sl, 1.1, 2.0, 10.5, 1.5,
            "Questions?", 56, bold=True, color=WHITE,
            font_name="Georgia")
add_rect(sl, 1.1, 3.5, 6, 0.05, ACCENT)
add_textbox(sl, 1.1, 3.65, 10.5, 0.45,
            "Thank you for your attention.", 18, color=CREAM,
            font_name="Georgia", italic=True)

# Contact / reference block
add_rect(sl, 1.1, 4.4, 10.8, 1.6, DARK2)
contact_lines = [
    {"text": "Bogdan Babaev", "bold": True, "size": 14, "color": WHITE},
    {"text": "M.Sc. Artificial Intelligence — University of Kragujevac, Serbia", "size": 11, "color": MUTED},
    {"text": "babaev.bogdan.ru@gmail.com   ·   github.com/b0gdaan   ·   linkedin.com/in/bogdan-b-34482b203", "size": 11, "color": ACCENT},
]
add_multiline_textbox(sl, 1.2, 4.5, 10.5, 1.4,
                      contact_lines, font_size=11, color=CREAM, font_name="Calibri")

# Reminder stats bottom
add_rect(sl, 0.5, 6.25, 12.33, 1.2, DARK2)
reminder = [
    ("7 assets", "BTC + 6 conventional"),
    ("168 models", "24 pairs × 7 models"),
    ("5+ years OOS", "2021–2026 test period"),
    ("p < 0.05", "DM significance (XGBoost)"),
    ("F1 = 0.47", "Stress-day detection"),
]
for i, (val, label) in enumerate(reminder):
    x = 0.7 + i * 2.42
    add_textbox(sl, x, 6.35, 2.2, 0.42,
                val, 16, bold=True, color=ACCENT,
                align=PP_ALIGN.CENTER, font_name="Georgia")
    add_textbox(sl, x, 6.8, 2.2, 0.3,
                label, 9.5, color=MUTED,
                align=PP_ALIGN.CENTER, font_name="Calibri")


# ── SAVE ──────────────────────────────────────────────────────────────────────
prs.save(OUTPUT)
print("Done:", OUTPUT)
