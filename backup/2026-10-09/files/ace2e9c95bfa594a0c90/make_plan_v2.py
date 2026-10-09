"""
Interview Prep Plan v2 — Bogdan Babaev
12-week action roadmap targeting Mid-level DS / AI Engineer / DA roles
"""
from docx import Document
from docx.shared import Pt, RGBColor, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

doc = Document()

# ── Page margins ──────────────────────────────────────────────────────────────
for section in doc.sections:
    section.top_margin    = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin   = Cm(2.5)
    section.right_margin  = Cm(2.5)

# ── Colors ────────────────────────────────────────────────────────────────────
NAVY   = RGBColor(0x0D, 0x1B, 0x3E)
TEAL   = RGBColor(0x00, 0xAA, 0x88)
BLUE   = RGBColor(0x1A, 0x6C, 0xF8)
GRAY   = RGBColor(0x55, 0x55, 0x55)
GREEN  = RGBColor(0x1A, 0x7A, 0x40)
ORANGE = RGBColor(0xCC, 0x66, 0x00)
RED    = RGBColor(0xAA, 0x22, 0x22)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)

def set_cell_bg(cell, hex_color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color)
    tcPr.append(shd)

def heading(text, level=1, color=NAVY, size=20):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after  = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    run.font.color.rgb = color
    return p

def subheading(text, color=TEAL, size=13):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after  = Pt(2)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(size)
    run.font.color.rgb = color
    return p

def body(text, size=10.5, color=None, bold=False, indent=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after  = Pt(2)
    if indent:
        p.paragraph_format.left_indent = Cm(0.5)
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = color
    return p

def bullet(text, size=10.5, color=None, bold_prefix=None):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after  = Pt(1)
    p.paragraph_format.left_indent  = Cm(0.5)
    if bold_prefix:
        run1 = p.add_run(bold_prefix)
        run1.bold = True
        run1.font.size = Pt(size)
        if color: run1.font.color.rgb = color
        run2 = p.add_run(text)
        run2.font.size = Pt(size)
        if color: run2.font.color.rgb = color
    else:
        run = p.add_run(text)
        run.font.size = Pt(size)
        if color: run.font.color.rgb = color
    return p

def divider():
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(4)
    run = p.add_run("─" * 90)
    run.font.size = Pt(7)
    run.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
    return p

def status_badge(text, color_hex, text_color=WHITE):
    """Returns inline text for status"""
    return f"[{text}]"

# ════════════════════════════════════════════════════════════════════════════════
# TITLE PAGE
# ════════════════════════════════════════════════════════════════════════════════
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(20)
run = p.add_run("INTERVIEW PREPARATION ROADMAP")
run.bold = True; run.font.size = Pt(26); run.font.color.rgb = NAVY

p2 = doc.add_paragraph()
p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
run2 = p2.add_run("Bogdan Babaev  ·  Data Scientist & AI Engineer")
run2.font.size = Pt(13); run2.font.color.rgb = GRAY

p3 = doc.add_paragraph()
p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
run3 = p3.add_run("May 2026 → August 2026  ·  12 Weeks to Mid-level Job")
run3.font.size = Pt(11); run3.font.color.rgb = TEAL

divider()

# ════════════════════════════════════════════════════════════════════════════════
# SECTION 0 — PROFILE STATUS (audit)
# ════════════════════════════════════════════════════════════════════════════════
heading("0. Profile Audit — Current State", color=NAVY, size=16)

body("Status as of May 2026. ✅ = done  ⚠️ = needs action  ❌ = missing", size=10, color=GRAY)

# LinkedIn audit table
subheading("LinkedIn — linkedin.com/in/b0gdaan", color=BLUE)

tbl = doc.add_table(rows=1, cols=3)
tbl.style = 'Table Grid'
hdr = tbl.rows[0].cells
for i, t in enumerate(["Element", "Status", "Note"]):
    hdr[i].text = t
    hdr[i].paragraphs[0].runs[0].bold = True
    hdr[i].paragraphs[0].runs[0].font.size = Pt(9)
    set_cell_bg(hdr[i], "0D1B3E")
    hdr[i].paragraphs[0].runs[0].font.color.rgb = WHITE

rows_data = [
    ("Photo",            "✅ Done",    "Professional headshot visible"),
    ("Banner",           "✅ Done",    "Dark navy tech banner uploaded"),
    ("Headline",         "✅ Done",    "Data Scientist | AI Engineer | Python · SQL · XGBoost · LLM APIs · Time Series | M.Sc. AI"),
    ("About section",    "✅ Done",    "~1800 chars rewrite, keywords: LLM, RAG, FastAPI, PostgreSQL, walk-forward"),
    ("Open to Work",     "✅ Done",    "Belgrade | On-site · Hybrid · Remote"),
    ("Skills (top 5)",   "⚠️ Check",  "Verify: TensorFlow removed, PyTorch + FastAPI + pandas added"),
    ("Skills (full 50)", "⚠️ Action", "Add: NumPy, scikit-learn, Docker, LangChain, ChromaDB, ETL, MLflow"),
    ("Experience",       "⚠️ Check",  "EasyDev description softened — verify it's saved"),
    ("LinkedIn post",    "⚠️ Action", "Post about Master's thesis results (draft ready)"),
    ("Recommendations",  "❌ Missing", "Ask 1-2 colleagues/professors for a recommendation"),
]
for row_data in rows_data:
    row = tbl.add_row()
    for i, val in enumerate(row_data):
        cell = row.cells[i]
        cell.text = val
        cell.paragraphs[0].runs[0].font.size = Pt(9)
        if i == 1:
            if "✅" in val:   cell.paragraphs[0].runs[0].font.color.rgb = GREEN
            elif "⚠️" in val: cell.paragraphs[0].runs[0].font.color.rgb = ORANGE
            elif "❌" in val:  cell.paragraphs[0].runs[0].font.color.rgb = RED

doc.add_paragraph()

# GitHub audit table
subheading("GitHub — github.com/b0gdaan", color=BLUE)

tbl2 = doc.add_table(rows=1, cols=3)
tbl2.style = 'Table Grid'
hdr2 = tbl2.rows[0].cells
for i, t in enumerate(["Element", "Status", "Note"]):
    hdr2[i].text = t
    hdr2[i].paragraphs[0].runs[0].bold = True
    hdr2[i].paragraphs[0].runs[0].font.size = Pt(9)
    set_cell_bg(hdr2[i], "0D1B3E")
    hdr2[i].paragraphs[0].runs[0].font.color.rgb = WHITE

rows_gh = [
    ("Bio",              "✅ Done",    "Data Scientist & AI Engineer · Python · ML · FastAPI · PostgreSQL · M.Sc. AI"),
    ("LinkedIn link",    "✅ Done",    "In bio"),
    ("Profile README",   "✅ Done",    "b0gdaan/b0gdaan repo — shields, 3 projects, stats"),
    ("Pinned repos",     "✅ Done",    "master-thesis, auv-defect-detection, data_for_wb_ozon, parkinsons-severity-ml"),
    ("Repo topics",      "✅ Done",    "Tags added: ml, xgboost, pytorch, fastapi, etc."),
    ("Avatar",           "⚠️ Action", "Upload D:\\clode9\\github_avatar.png via Settings → Profile"),
    ("Contribution graph","⚠️ Action","Enable private contributions in GitHub settings; build daily commit habit"),
    ("Repo READMEs",     "⚠️ Action", "master-thesis & data_for_wb_ozon need detailed READMEs with results/screenshots"),
    ("Demo / live link", "❌ Missing", "At least one project needs a demo (Hugging Face Spaces or live URL)"),
]
for row_data in rows_gh:
    row = tbl2.add_row()
    for i, val in enumerate(row_data):
        cell = row.cells[i]
        cell.text = val
        cell.paragraphs[0].runs[0].font.size = Pt(9)
        if i == 1:
            if "✅" in val:   cell.paragraphs[0].runs[0].font.color.rgb = GREEN
            elif "⚠️" in val: cell.paragraphs[0].runs[0].font.color.rgb = ORANGE
            elif "❌" in val:  cell.paragraphs[0].runs[0].font.color.rgb = RED

doc.add_paragraph()
divider()

# ════════════════════════════════════════════════════════════════════════════════
# SECTION 1 — TARGET ROLES & STRATEGY
# ════════════════════════════════════════════════════════════════════════════════
heading("1. Target Roles & Job Search Strategy", color=NAVY, size=16)

subheading("Priority order (highest demand → fastest hire)", color=TEAL)
rows_roles = [
    ("1", "AI Engineer / ML Engineer",     "LLM pipelines, RAG, embeddings, agents",          "€2,500–5,000/mo",  "HIGH"),
    ("2", "Data Scientist",                "ML modeling, A/B tests, Python, XGBoost",          "€2,000–4,000/mo",  "HIGH"),
    ("3", "Data Analyst",                  "SQL, dashboards, business metrics, Python",         "€1,500–3,000/mo",  "MEDIUM"),
    ("4", "Backend Python / FastAPI Dev",  "APIs, PostgreSQL, ETL pipelines",                  "€2,000–3,500/mo",  "MEDIUM"),
]
tbl3 = doc.add_table(rows=1, cols=5)
tbl3.style = 'Table Grid'
for i, h in enumerate(["#", "Role", "Key skills needed", "Salary range", "Demand"]):
    cell = tbl3.rows[0].cells[i]
    cell.text = h
    cell.paragraphs[0].runs[0].bold = True
    cell.paragraphs[0].runs[0].font.size = Pt(9)
    set_cell_bg(cell, "0D1B3E")
    cell.paragraphs[0].runs[0].font.color.rgb = WHITE
for r in rows_roles:
    row = tbl3.add_row()
    for i, val in enumerate(r):
        cell = row.cells[i]
        cell.text = val
        cell.paragraphs[0].runs[0].font.size = Pt(9)
doc.add_paragraph()

subheading("Where to apply", color=TEAL)
bullet("LinkedIn Jobs — primary channel. Turn on job alerts: 'AI Engineer', 'ML Engineer', 'Data Scientist', 'Python Developer'. Locations: Remote, EU, Serbia")
bullet("Otta.com — startup-focused, strong DS/ML listings, good for remote")
bullet("Wellfound (AngelList) — tech startups, many AI-first companies")
bullet("Himalayas.app / Remote.co — fully remote positions")
bullet("Toptal, Arc.dev — freelance/contract with high rates (good side income while searching)")
bullet("Direct: target Belgrade tech companies (Nordeus, Levi9, HTEC, NCR), iGaming companies (remote-friendly)")

subheading("Weekly application cadence", color=TEAL)
bullet("Weeks 1–8: Focus 80% on skill building, 20% on passive applications (5-10 apps/week)")
bullet("Weeks 9–12: Flip to 60% active applications (20-30/week) + interview prep")
bullet("Track everything in a simple spreadsheet: Company | Role | Status | Date | Notes")

divider()

# ════════════════════════════════════════════════════════════════════════════════
# SECTION 2 — 12-WEEK ROADMAP
# ════════════════════════════════════════════════════════════════════════════════
heading("2. 12-Week Action Roadmap", color=NAVY, size=16)
body("Each week: ~10-15h total. Split into skill blocks + project work + interview practice.", size=10, color=GRAY)

weeks = [
    # (week_range, theme, color_hex, daily_goals, deliverable)
    (
        "Week 1–2", "Profile Polish + Python & Stats Foundation",
        "1A3A6E",
        [
            "Upload GitHub avatar (D:\\clode9\\github_avatar.png)",
            "Add 15+ skills to LinkedIn (pandas, NumPy, PyTorch, FastAPI, PostgreSQL, Docker, LangChain...)",
            "Write detailed READMEs for master-thesis and data_for_wb_ozon repos",
            "Python refresh: decorators, generators, async/await, dataclasses, typing",
            "Stats refresh: p-values, confidence intervals, CLT, Bayes theorem, A/B test design",
            "SQL: window functions, CTEs, subqueries — solve 20 problems on Mode Analytics or StrataScratch",
            "Post the LinkedIn thesis post (draft was prepared)",
            "Enable private contributions on GitHub",
        ],
        "Deliverable: LinkedIn at 85%+ SSI score. GitHub avatar live. 2 repo READMEs updated."
    ),
    (
        "Week 3–4", "ML Deep Dive — Modeling & Evaluation",
        "0A4A5E",
        [
            "Tree models: XGBoost hyperparameter tuning (max_depth, learning_rate, subsample, colsample), early stopping",
            "Ensemble methods: Random Forest, Gradient Boosting, Stacking — when to use each",
            "Feature engineering: encoding categoricals, target encoding, feature selection (SHAP, mutual info)",
            "Model evaluation: ROC-AUC, PR-AUC, log-loss, calibration curves, classification_report",
            "Cross-validation strategies: k-fold, stratified, time-series split, walk-forward",
            "Overfitting diagnosis: learning curves, validation curves, regularization",
            "Read: 'Approaching Almost Any Machine Learning Problem' by Abhishek Thakur (free PDF)",
            "Practice: Kaggle Titanic + House Prices + one tabular competition",
        ],
        "Deliverable: Kaggle notebook with full ML pipeline (EDA→model→evaluation) — add to GitHub."
    ),
    (
        "Week 5–6", "AI Engineering — LLMs, RAG, Agents",
        "0A3A5E",
        [
            "OpenAI API: chat completions, function calling, embeddings, token counting, cost management",
            "Prompt engineering: system/user/assistant roles, few-shot, chain-of-thought, output structuring",
            "RAG pipeline: chunking strategies → embeddings → vector store (ChromaDB/Qdrant) → retrieval → generation",
            "LangChain basics: chains, retrievers, memory, ConversationalRetrievalChain",
            "Evaluation: RAGAS metrics — faithfulness, answer relevancy, context precision",
            "AI safety: prompt injection, jailbreaks, guardrails basics",
            "Watch: DeepLearning.AI 'Building Systems with the ChatGPT API' (free)",
            "Read: LangChain docs + RAGAS GitHub examples",
        ],
        "Deliverable: RAG chatbot project on GitHub (PDF/docs → ChromaDB → FastAPI → query interface)."
    ),
    (
        "Week 7–8", "Portfolio Project — AI Engineer Showcase",
        "083A3E",
        [
            "BUILD: Production-ready RAG or AI Agent project (choose one):",
            "  Option A: AI Job Search Assistant — scrape job listings → embed → RAG → personalized cover letters",
            "  Option B: Financial News Analyst — fetch news → sentiment + summary → store → query via API",
            "  Option C: Document Q&A — upload PDFs → chunk → embed → retrieval → FastAPI → simple UI",
            "Requirements: FastAPI backend, ChromaDB or Qdrant, Docker, proper error handling, README with demo GIF",
            "Deploy on Hugging Face Spaces or Render.com (free tier) for a live demo link",
            "Add to GitHub pinned repos, update LinkedIn About with project mention",
        ],
        "Deliverable: 1 live AI Engineering project with GitHub stars-worthy README + live demo URL."
    ),
    (
        "Week 9", "Coding Interview Prep — LeetCode & System Design",
        "1A3A1E",
        [
            "LeetCode: solve 3 problems/day — focus on Arrays, HashMaps, Strings, Two Pointers (Medium level)",
            "Python-specific: list comprehensions, Counter, defaultdict, heapq, bisect — these come up often",
            "SQL: 2 problems/day on StrataScratch (company-tagged: Meta, Google, Airbnb)",
            "System Design basics: load balancing, caching, databases (SQL vs NoSQL), message queues",
            "ML System Design: how to serve a model at scale, feature stores, model monitoring, A/B testing infra",
            "Practice explaining your projects out loud (use Loom or just record yourself)",
        ],
        "Deliverable: 30 LeetCode solved, 20 SQL problems solved, can explain all 3 GitHub projects clearly."
    ),
    (
        "Week 10", "ML Theory Interview Prep",
        "1A3A1E",
        [
            "Bias-variance tradeoff — know how to explain it with a diagram",
            "Regularization: L1 vs L2, when to use each, effect on coefficients",
            "Gradient descent variants: SGD, Adam, RMSprop — intuition, not formulas",
            "Neural networks basics: backprop, activation functions, batch normalization, dropout",
            "Time series: stationarity, ADF test, ARIMA vs SARIMA, walk-forward vs expanding window",
            "Statistics: Type I/II errors, multiple testing correction, power analysis",
            "Probability: Bayes theorem, conditional probability, distributions (Normal, Poisson, Binomial)",
            "Practice: 50 ML flashcards from ml-interviews.com (free)",
        ],
        "Deliverable: Can answer 80% of common ML interview questions without hesitation."
    ),
    (
        "Week 11", "Mock Interviews & Behavioral Prep",
        "2A1A1E",
        [
            "Schedule 3+ mock interviews: Pramp.com (free), Interviewing.io, or with a friend/mentor",
            "STAR format stories for 8 behavioral questions: conflict, failure, impact, leadership, data-driven decision",
            "Your top 3 project stories timed to 2 minutes each (master-thesis, WB/Ozon, AUV)",
            "Salary negotiation: research market rates, prepare counter-offer script, know your minimum",
            "Questions to ask interviewer: prepared list of 5-7 good questions",
            "Company research template: products, tech stack, recent news, why you want to join",
        ],
        "Deliverable: 3 mock interviews done. STAR stories written and practiced. Confident salary range."
    ),
    (
        "Week 12", "Full Application Push",
        "2A1A1E",
        [
            "Apply to 30+ companies this week — have personalized cover letter template ready",
            "LinkedIn: connect with 5+ recruiters per day with short personal note",
            "Follow up on all previous applications (polite email after 7-10 days of silence)",
            "Track metrics: applications sent, responses, phone screens, technical rounds",
            "Negotiate every offer — first offer is almost never final",
            "Keep coding and building even during interview rounds — shows momentum",
        ],
        "Deliverable: 30+ applications sent, 3-5 phone screens scheduled, 1+ technical round in progress."
    ),
]

for week_range, theme, color_hex, goals, deliverable in weeks:
    # Week header
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after  = Pt(0)

    tbl_w = doc.add_table(rows=1, cols=1)
    tbl_w.style = 'Table Grid'
    cell = tbl_w.rows[0].cells[0]
    set_cell_bg(cell, color_hex)
    p2 = cell.paragraphs[0]
    r1 = p2.add_run(f"  {week_range}  —  ")
    r1.bold = True; r1.font.size = Pt(11); r1.font.color.rgb = WHITE
    r2 = p2.add_run(theme)
    r2.bold = False; r2.font.size = Pt(11); r2.font.color.rgb = RGBColor(0xCC, 0xDD, 0xFF)

    for g in goals:
        indent = g.startswith("  ")
        p_g = doc.add_paragraph()
        p_g.paragraph_format.space_before = Pt(0)
        p_g.paragraph_format.space_after  = Pt(0)
        p_g.paragraph_format.left_indent  = Cm(0.8 if not indent else 1.4)
        run_bullet = p_g.add_run("• " if not indent else "  ◦ ")
        run_bullet.font.size = Pt(10)
        run_bullet.font.color.rgb = TEAL
        run_text = p_g.add_run(g.strip())
        run_text.font.size = Pt(10)

    # Deliverable
    p_d = doc.add_paragraph()
    p_d.paragraph_format.space_before = Pt(3)
    p_d.paragraph_format.space_after  = Pt(4)
    p_d.paragraph_format.left_indent  = Cm(0.8)
    r_label = p_d.add_run("🎯 ")
    r_label.font.size = Pt(10)
    r_bold = p_d.add_run("Deliverable: ")
    r_bold.bold = True; r_bold.font.size = Pt(10); r_bold.font.color.rgb = GREEN
    r_val = p_d.add_run(deliverable)
    r_val.font.size = Pt(10); r_val.font.color.rgb = GREEN

divider()

# ════════════════════════════════════════════════════════════════════════════════
# SECTION 3 — DAILY HABITS
# ════════════════════════════════════════════════════════════════════════════════
heading("3. Daily Habits (Non-Negotiable)", color=NAVY, size=16)

habits = [
    ("Morning (30 min)", "1 LeetCode / 1 SQL problem. No skipping."),
    ("Evening (1–2 hrs)",  "Main study block: current week's topic OR project work."),
    ("GitHub commit",      "Push something every day — even 5 lines of code or a README update. Keeps contribution graph green."),
    ("LinkedIn (10 min)", "Like/comment on 2-3 posts from DS/AI people. Engage with recruiter posts. Increases profile visibility."),
    ("Weekly review (Sun)","30 min: what did I learn this week? Which topics am I weak on? Adjust plan for next week."),
]

tbl_h = doc.add_table(rows=len(habits), cols=2)
tbl_h.style = 'Table Grid'
for i, (label, desc) in enumerate(habits):
    c1 = tbl_h.rows[i].cells[0]
    c2 = tbl_h.rows[i].cells[1]
    r = c1.paragraphs[0].add_run(label)
    r.bold = True; r.font.size = Pt(10); r.font.color.rgb = NAVY
    r2 = c2.paragraphs[0].add_run(desc)
    r2.font.size = Pt(10)

doc.add_paragraph()
divider()

# ════════════════════════════════════════════════════════════════════════════════
# SECTION 4 — SKILLS CHECKLIST
# ════════════════════════════════════════════════════════════════════════════════
heading("4. Skills Checklist — By Interview Category", color=NAVY, size=16)
body("Rate yourself 1-5 at the start and end of each week.", size=10, color=GRAY)

categories = {
    "Python": [
        "List/dict comprehensions, generators, itertools",
        "OOP: classes, inheritance, dunder methods, dataclasses",
        "Decorators, context managers, async/await",
        "Type hints, mypy basics",
        "Testing: pytest, mock",
    ],
    "ML / Statistics": [
        "Linear & logistic regression (assumptions, when they fail)",
        "Tree models: XGBoost, LightGBM, RF — hyperparameters by heart",
        "Feature engineering: encoding, scaling, imputation",
        "Model evaluation: AUC, F1, log-loss, RMSE — when to use each",
        "Bias-variance, regularization, cross-validation",
        "Time series: stationarity, ARIMA, walk-forward CV",
        "A/B testing: sample size, p-value, multiple testing",
        "Clustering: k-means, DBSCAN — use cases",
    ],
    "AI Engineering": [
        "OpenAI / Anthropic API: completions, function calling, streaming",
        "Prompt engineering: few-shot, CoT, structured output",
        "Embeddings: what they are, similarity metrics, use cases",
        "RAG pipeline: end-to-end build from scratch",
        "Vector databases: ChromaDB, Qdrant — indexing, retrieval",
        "LangChain: chains, memory, retrieval, agents",
        "Evaluation: RAGAS, hallucination detection",
        "AI safety: prompt injection, output filtering",
    ],
    "Data Engineering / Backend": [
        "FastAPI: routing, Pydantic models, dependency injection, background tasks",
        "PostgreSQL: joins, window functions, indexes, EXPLAIN ANALYZE",
        "ETL patterns: batch vs streaming, idempotency, error handling",
        "Docker: Dockerfile, docker-compose, volumes, networking",
        "REST API design: status codes, pagination, auth",
        "MLflow or W&B: experiment tracking basics",
    ],
    "SQL (Interview)": [
        "GROUP BY + HAVING",
        "Window functions: ROW_NUMBER, RANK, LAG, LEAD, SUM OVER",
        "CTEs, recursive CTEs",
        "Self-joins, CROSS JOINs",
        "Date functions, string manipulation",
        "Performance: indexes, query plans",
    ],
    "System Design": [
        "How to serve an ML model (batch vs real-time)",
        "Feature stores concept",
        "Model monitoring: drift detection, alerting",
        "Data pipeline architecture (Airflow/Prefect patterns)",
        "Scale: sharding, caching, load balancing — basic concepts",
    ],
    "Behavioral": [
        "Tell me about yourself (2-min pitch ready)",
        "3 project stories in STAR format",
        "Failure story + what you learned",
        "Conflict resolution story",
        "Why this company / this role",
        "Where do you see yourself in 2-3 years",
        "Salary expectations (know your number)",
    ],
}

for cat, items in categories.items():
    subheading(f"► {cat}", color=BLUE, size=11)
    for item in items:
        p_skill = doc.add_paragraph()
        p_skill.paragraph_format.left_indent = Cm(0.5)
        p_skill.paragraph_format.space_before = Pt(1)
        p_skill.paragraph_format.space_after  = Pt(1)
        run_box = p_skill.add_run("☐  ")
        run_box.font.size = Pt(10); run_box.font.color.rgb = GRAY
        run_item = p_skill.add_run(item)
        run_item.font.size = Pt(10)

divider()

# ════════════════════════════════════════════════════════════════════════════════
# SECTION 5 — RESOURCES
# ════════════════════════════════════════════════════════════════════════════════
heading("5. Resources (Free)", color=NAVY, size=16)

resources = [
    ("LeetCode",         "https://leetcode.com/problemset/",      "DS&A practice. Filter: Easy→Medium. Python."),
    ("StrataScratch",    "https://stratascratch.com/",             "SQL + Python interview questions tagged by company"),
    ("ML Interviews",    "https://huyenchip.com/ml-interviews/",   "Chip Huyen's free ML interview book — PDF"),
    ("DeepLearning.AI",  "https://learn.deeplearning.ai/",         "Free short courses: LangChain, RAG, Agents, Prompt Eng"),
    ("RAGAS",            "https://docs.ragas.io/",                 "RAG evaluation framework — docs + examples"),
    ("Kaggle",           "https://kaggle.com",                     "Competitions + free GPU notebooks + datasets"),
    ("Papers with Code", "https://paperswithcode.com/",            "Latest ML papers + implementations"),
    ("Glassdoor",        "https://glassdoor.com/",                 "Salary research + company reviews + interview questions"),
    ("Pramp",            "https://pramp.com/",                     "Free peer-to-peer mock technical interviews"),
    ("Systemdesign.io",  "https://systemdesign.one/",              "System design concepts for ML engineers"),
]

tbl_r = doc.add_table(rows=1, cols=3)
tbl_r.style = 'Table Grid'
for i, h in enumerate(["Resource", "URL", "Use for"]):
    c = tbl_r.rows[0].cells[i]
    c.text = h
    c.paragraphs[0].runs[0].bold = True
    c.paragraphs[0].runs[0].font.size = Pt(9)
    set_cell_bg(c, "0D1B3E")
    c.paragraphs[0].runs[0].font.color.rgb = WHITE
for name, url, use in resources:
    row = tbl_r.add_row()
    row.cells[0].text = name
    row.cells[1].text = url
    row.cells[2].text = use
    for c in row.cells:
        c.paragraphs[0].runs[0].font.size = Pt(9)

doc.add_paragraph()
divider()

# ════════════════════════════════════════════════════════════════════════════════
# SECTION 6 — SUCCESS METRICS
# ════════════════════════════════════════════════════════════════════════════════
heading("6. Success Metrics (End of 12 Weeks)", color=NAVY, size=16)

metrics = [
    ("GitHub",    "Daily green commits. 3+ repos with proper READMEs. 1 live demo project."),
    ("LinkedIn",  "SSI score > 65. 50+ skills. 2+ recommendations. 500+ connections."),
    ("LeetCode",  "60+ problems solved. Comfortable with Medium difficulty."),
    ("SQL",       "Can write any window function / CTE query from scratch without docs."),
    ("AI Eng",    "Built and deployed 1 RAG project. Can explain RAG end-to-end in interview."),
    ("ML Theory", "90% success rate on ML flashcards. Can whiteboard bias-variance."),
    ("Job Search","30+ applications sent. 3+ technical rounds completed. 1+ offer received."),
]
for label, desc in metrics:
    p_m = doc.add_paragraph()
    p_m.paragraph_format.space_before = Pt(2)
    p_m.paragraph_format.space_after  = Pt(2)
    p_m.paragraph_format.left_indent  = Cm(0.3)
    r1 = p_m.add_run(f"✅  {label}: ")
    r1.bold = True; r1.font.size = Pt(10.5); r1.font.color.rgb = NAVY
    r2 = p_m.add_run(desc)
    r2.font.size = Pt(10.5)

doc.add_paragraph()
p_final = doc.add_paragraph()
p_final.alignment = WD_ALIGN_PARAGRAPH.CENTER
p_final.paragraph_format.space_before = Pt(10)
r = p_final.add_run("You have the projects. You have the degree. Now it's about consistency and execution.")
r.italic = True; r.font.size = Pt(11); r.font.color.rgb = TEAL

# ── Save ──────────────────────────────────────────────────────────────────────
out_path = r"D:\clode9\Interview_Prep_Plan_v2.docx"
doc.save(out_path)
print(f"Saved: {out_path}")
