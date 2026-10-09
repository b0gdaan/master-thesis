from docx import Document
from docx.shared import Pt, RGBColor, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

doc = Document()

# --- Page margins ---
for section in doc.sections:
    section.top_margin = Cm(1.5)
    section.bottom_margin = Cm(1.5)
    section.left_margin = Cm(1.8)
    section.right_margin = Cm(1.8)

# --- Colors ---
BLUE_DARK = RGBColor(0x1A, 0x52, 0x76)   # chapter headers bg
BLUE_MID  = RGBColor(0x21, 0x6A, 0x9A)   # section headers bg
BLUE_LITE = RGBColor(0xD6, 0xEA, 0xF8)   # section headers bg alt
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
BLACK     = RGBColor(0x00, 0x00, 0x00)
GRAY_ROW  = RGBColor(0xF2, 0xF2, 0xF2)

def set_cell_bg(cell, color_hex):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), color_hex)
    tcPr.append(shd)

def set_cell_borders(cell):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    for side in ['top','left','bottom','right']:
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '4')
        el.set(qn('w:space'), '0')
        el.set(qn('w:color'), 'AAAAAA')
        tcBorders.append(el)
    tcPr.append(tcBorders)

def add_chapter_header(doc, text, subtitle=None):
    """Blue box chapter header"""
    doc.add_paragraph()
    tbl = doc.add_table(rows=1 if not subtitle else 2, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    # Title row
    cell = tbl.rows[0].cells[0]
    set_cell_bg(cell, '1A5276')
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = WHITE
    run.font.name = 'Arial'
    if subtitle:
        cell2 = tbl.rows[1].cells[0]
        set_cell_bg(cell2, '1A5276')
        p2 = cell2.paragraphs[0]
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p2.paragraph_format.space_before = Pt(2)
        p2.paragraph_format.space_after = Pt(6)
        r2 = p2.add_run(subtitle)
        r2.italic = True
        r2.font.size = Pt(9)
        r2.font.color.rgb = RGBColor(0xAE, 0xD6, 0xF1)
        r2.font.name = 'Arial'
    doc.add_paragraph()

def add_section_header(doc, text):
    """Light blue section header"""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.rows[0].cells[0]
    set_cell_bg(cell, 'D6EAF8')
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(11)
    run.font.color.rgb = BLUE_DARK
    run.font.name = 'Arial'

def add_body(doc, text, bold=False, italic=False, size=10, space_after=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    run.font.name = 'Arial'
    return p

def add_bullet(doc, text, size=10):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.name = 'Arial'

def add_week_header(doc, text):
    tbl = doc.add_table(rows=1, cols=1)
    cell = tbl.rows[0].cells[0]
    set_cell_bg(cell, '216A9A')
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(10)
    run.font.color.rgb = WHITE
    run.font.name = 'Arial'

def make_table(doc, headers, rows, col_widths=None):
    """headers: list of str, rows: list of list of str"""
    n = len(headers)
    tbl = doc.add_table(rows=1+len(rows), cols=n)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = 'Table Grid'
    # Header row
    hrow = tbl.rows[0]
    for i, h in enumerate(headers):
        cell = hrow.cells[i]
        set_cell_bg(cell, '1A5276')
        p = cell.paragraphs[0]
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(3)
        run = p.add_run(h)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = WHITE
        run.font.name = 'Arial'
    # Data rows
    for ri, row in enumerate(rows):
        tr = tbl.rows[ri+1]
        bg = 'F8FBFD' if ri % 2 == 0 else 'FFFFFF'
        for ci, val in enumerate(row):
            cell = tr.cells[ci]
            set_cell_bg(cell, bg)
            set_cell_borders(cell)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(str(val))
            run.font.size = Pt(8)
            run.font.name = 'Arial'
    # Set col widths if provided
    if col_widths:
        for row in tbl.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph()
    return tbl

# ============================================================
# TITLE PAGE
# ============================================================
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(20)
r = p.add_run('ПЛАН ПОДГОТОВКИ К СОБЕСЕДОВАНИЯМ')
r.bold = True; r.font.size = Pt(20); r.font.color.rgb = WHITE; r.font.name = 'Arial'

# title block
tbl = doc.add_table(rows=3, cols=1)
tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
for i, (txt, sz, clr, it) in enumerate([
    ('ПЛАН ПОДГОТОВКИ К СОБЕСЕДОВАНИЯМ', 22, '1A5276', False),
    ('Data Scientist / ML Engineer / AI Engineer', 14, '1A5276', False),
    ('2 500+ EUR в месяц (EU) | $87 000+ (US Remote)', 12, '216A9A', True),
]):
    cell = tbl.rows[i].cells[0]
    set_cell_bg(cell, clr)
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(txt)
    run.bold = not it; run.italic = it
    run.font.size = Pt(sz)
    run.font.color.rgb = WHITE
    run.font.name = 'Arial'

doc.add_paragraph()

# Info box
info = doc.add_table(rows=1, cols=1)
icell = info.rows[0].cells[0]
set_cell_bg(icell, 'EBF5FB')
set_cell_borders(icell)
bullets = [
    '16 недель × 1 час в день = 112 часов до первых офферов',
    'Цель: Junior DS / ML Engineer / Junior AI Engineer / Senior Data Analyst',
    'Только бесплатные материалы: Kaggle, YouTube, GitHub, HuggingFace',
    'Чек-листы, банк вопросов (Python / SQL / ML / Stats / AI)',
    'Реальные зарплаты по компаниям и рынкам (EUR/USD) — Глава 2',
    'Карьерный трек: от 0 до Senior за 3–5 лет',
    'Персонализировано под ML-диплом (XGBoost, Ridge, DCC-GARCH, walk-forward, DM-тесты)',
]
for b in bullets:
    p = icell.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.left_indent = Cm(0.3)
    run = p.add_run('• ' + b)
    run.font.size = Pt(10)
    run.font.name = 'Arial'
    run.font.color.rgb = BLUE_DARK

doc.add_page_break()

# ============================================================
# ГЛАВА 1
# ============================================================
add_chapter_header(doc, 'ГЛАВА 1: ЦЕЛЕВАЯ ПОЗИЦИЯ И РЫНОК',
    'Почему Data Scientist / ML Engineer / AI Engineer — лучший выбор для тебя')

add_section_header(doc, '1.1  Анализ твоего профиля')
add_body(doc, 'Из диплома и кода ты уже умеешь: Python (pandas, numpy, sklearn, XGBoost, statsmodels, arch), walk-forward ML evaluation, временные ряды, DM-тесты, bootstrap CI, Jupyter, LaTeX, reproducible pipeline.')
add_body(doc, 'Твой профиль — начальный-средний Data Scientist / Quant Analyst. Четыре навыка, которые выделяют тебя среди джунов:')
for b in ['Walk-forward validation — понимаешь leakage там, где другие нет;',
          'DM-тест — статистически доказываешь, что твоя модель лучше;',
          'DCC-GARCH — эконометрика волатильности (ценится в финансах);',
          'Финансовые данные — понимаешь prod-данные с реального рынка.']:
    add_bullet(doc, b)

doc.add_paragraph()
add_section_header(doc, '1.2  Целевые роли')
make_table(doc,
    ['Роль', 'Твой уровень', 'Приоритет', 'Что усилить'],
    [['Junior Data Scientist', '4/5 — есть базис', 'Главная', 'SQL + Kaggle проекты'],
     ['Junior AI Engineer', '2/5 — развивать', 'Главная', 'LLM API + Embeddings + Agents'],
     ['Junior ML Engineer', '3/5 — развивать', 'Вторая', 'FastAPI + Docker + MLflow'],
     ['Data Analyst (Senior)', '4/5 — близко', 'Запасная', 'SQL strong + BI инструменты'],
     ['Quant / Risk Analyst', '3/5 — есть ниша', 'Бонус', 'VaR, эконометрика, финансы'],
     ['NLP / CV Engineer', '1/5 — далеко', 'Не сейчас', 'Слишком далеко от базы']],
    col_widths=[5.5, 3.5, 3.0, 4.5])

add_section_header(doc, '1.3  Что работодатели ищут в первую очередь')
add_body(doc, 'Для DS/ML/DA ролей:', bold=True)
for b in ['Python: pandas / numpy / sklearn — обязательно, без них не пройдёшь скрининг',
          'SQL: SELECT, JOIN, GROUP BY, оконные функции — спросят на 95% собесов',
          'ML: bias/variance, переобучение, кросс-валидация, метрики (RMSE, AUC, F1, AP)',
          'Практика: реальный проект на GitHub — твой диплом уже готовый проект!',
          'Git: базовые команды, PR workflow, чистый README с результатами',
          'Статистика: p-value, доверительные интервалы, A/B тесты',
          'Английский B2+: большинство высокооплачиваемых вакансий требуют его']:
    add_bullet(doc, b)

add_body(doc, 'Для AI Engineer ролей (дополнительно):', bold=True)
for b in ['LLM понимание: токены, context window, temperature, top-p, fine-tuning vs RAG',
          'API интеграция: OpenAI, Anthropic, HuggingFace — умение строить продукты на LLM',
          'Embeddings: преобразование текста в векторы, семантический поиск',
          'Vector databases: ChromaDB, Pinecone, Qdrant — хранение и поиск по embeddings',
          'AI Agents: LangChain, LlamaIndex, function calling, multi-step reasoning',
          'Безопасность: prompt injection, hallucination detection, evaluation frameworks',
          'Deployment: FastAPI + LLM endpoint, Docker, мониторинг качества ответов']:
    add_bullet(doc, b)

doc.add_page_break()

# ============================================================
# ГЛАВА 2
# ============================================================
add_chapter_header(doc, 'ГЛАВА 2: РЕАЛЬНЫЕ ЗАРПЛАТЫ — РЫНКИ И КОМПАНИИ',
    'Данные 2024–2025 · Источники: levels.fyi, Glassdoor, LinkedIn Salary, TeamBlind')

add_section_header(doc, '2.1  Зарплаты по рынкам')
make_table(doc,
    ['Рынок / Страна', 'Роль', 'Зарплата gross/мес', 'Тип договора', 'Заметки'],
    [['Польша (Варшава)', 'Junior DS', '1 900–3 300 EUR', 'B2B / UoP', 'Популярный старт в ЕС'],
     ['Польша (Варшава)', 'Mid DS', '3 300–5 200 EUR', 'B2B', 'После 2+ лет опыта'],
     ['Чехия (Прага)', 'Junior DS', '2 200–3 400 EUR', 'HPP', 'Рост рынка DS 2024'],
     ['Германия', 'Junior DS', '3 750–5 000 EUR', 'Festanstellung', 'Нужен немецкий B1+'],
     ['Нидерланды', 'Junior DS', '3 300–4 600 EUR', 'Contract / Perm', 'Tax ruling 30%'],
     ['Remote EU', 'Junior DS', '2 500–4 000 EUR', 'B2B contractor', 'Много вакансий после 2023'],
     ['Remote (US-компании)', 'Mid DS / ML Eng', '4 000–8 000 USD', 'Contractor', 'Нужен портфолио + LeetCode'],
     ['Remote (US-компании)', 'Junior AI Engineer', '5 000–8 700 USD', 'Contractor', 'Быстро растущий рынок'],
     ['Сербия (Белград)', 'Junior DS', '1 500–2 500 EUR', 'Аутсорс / local', 'Или remote на EU компании'],
     ['Сербия (Белград)', 'Mid DS (remote)', '2 500–4 000 EUR', 'B2B remote', 'Remote на EU/US из Белграда']],
    col_widths=[3.5, 3.2, 3.2, 3.2, 3.4])

add_section_header(doc, '2.2  AI Engineer зарплаты — US рынок (2024–2025)')
make_table(doc,
    ['Уровень', 'Зарплата/год (USD)', 'Примерно/мес (USD)', 'Источник'],
    [['Junior AI Engineer', '$87 000–116 000', '$7 250–9 700', 'levels.fyi, TeamBlind 2025'],
     ['Middle AI Engineer', '$150 000–220 000', '$12 500–18 300', 'levels.fyi 2025'],
     ['Senior AI Engineer', '$220 000–400 000', '$18 300–33 300', 'levels.fyi 2025'],
     ['Staff / Principal', '$400 000–800 000', '$33 300–66 700', 'FAANG, top startups'],
     ['Top positions (FAANG)', 'up to $1 700 000', 'up to $141 700', 'с акциями (RSU)']],
    col_widths=[4.5, 4.0, 4.0, 4.0])

add_body(doc, 'Для US remote нужны: прокачанный LinkedIn на английском, портфолио AI проектов на GitHub, C1 английский, понимание юридических аспектов работы как contractor из Сербии.', italic=True)

add_section_header(doc, '2.3  Конкретные компании — EU (Junior/Mid DS)')
make_table(doc,
    ['Компания', 'Локация', 'Роль', 'Base/мес', 'Бонус', 'Что спрашивают'],
    [['Booking.com', 'Амстердам', 'Junior DS', '4 500–5 500 EUR', '10–15%', 'A/B тесты, SQL window funcs'],
     ['Zalando', 'Берлин', 'Junior DS', '4 200–5 200 EUR', '10–20%', 'ML system design, case study'],
     ['Delivery Hero', 'Берлин', 'Junior DS', '4 000–5 000 EUR', '10%', 'ML метрики, SQL'],
     ['Revolut', 'Remote / EU', 'Junior DS', '3 000–5 000 EUR', '0–20%', 'ML pipeline, case study'],
     ['Wise', 'Варшава/Таллин', 'Data Analyst', '3 000–4 200 EUR', '10%', 'SQL, Python, A/B'],
     ['Klarna', 'Стокгольм/Remote', 'Junior DS', '3 500–5 000 EUR', '15%', 'Credit scoring, ML, SQL'],
     ['EPAM Systems', 'Remote / EU', 'Junior DS', '2 000–3 500 EUR', '10%', 'Алгоритмы, ML теория'],
     ['Grid Dynamics', 'Remote / EU', 'Junior DS', '2 500–4 000 EUR', '10%', 'ML кодинг, SQL, system design'],
     ['Toptal', 'Remote (US-рейт.)', 'ML Engineer', '4 000–7 000 USD', 'нет', 'Technical screen + LeetCode']],
    col_widths=[3.0, 3.0, 2.8, 3.0, 1.8, 3.9])

add_section_header(doc, '2.4  Финансовый сектор — твоя ниша (Quant / Risk DS)')
add_body(doc, 'Твой диплом (DCC-GARCH, DM-тест, walk-forward) открывает прямой вход в финансово-аналитические роли. Это ниша, где большинство джунов даже не знают о DM-тесте.')
make_table(doc,
    ['Компания / Тип', 'Роль', 'Зарплата gross', 'Ключ. требования'],
    [['Deutsche Bank, Commerzbank', 'Junior Quant Analyst', '4 500–7 000 EUR/мес', 'Python, статистика, VaR, временные ряды'],
     ['Goldman Sachs, JPMorgan (EU)', 'Junior Quant', '5 000–8 000 EUR + бонус', 'Econometrics, C++/Python, тесты'],
     ['NN Group, Allianz', 'Risk DS / Actuarial DS', '4 000–6 000 EUR/мес', 'Python, GLM, временные ряды'],
     ['Erste Bank, Raiffeisen', 'Junior Risk Analyst', '2 500–4 000 EUR/мес', 'Python, SQL, статистика, Excel'],
     ['Hedge funds (EU)', 'Junior Quant Researcher', '6 000–12 000 EUR/мес', 'ML + статистика + Math'],
     ['Revolut / Wise (Risk)', 'Risk / Fraud DS', '3 500–6 000 EUR/мес', 'ML классификация, SQL, Python']],
    col_widths=[4.0, 3.8, 3.5, 5.2])

add_section_header(doc, '2.5  Карьерный трек — рост зарплаты по этапам')
make_table(doc,
    ['Этап', 'Роль', 'Опыт', 'Зарплата (Remote EU)', 'Ключевое условие'],
    [['Сейчас', 'Студент / Junior', '0 лет', '0–1 500 EUR', 'Диплом + Python + SQL базовый'],
     ['3–6 мес.', 'Junior Data Analyst', '0–0.5 г.', '1 800–2 800 EUR', 'SQL strong + портфолио на GitHub'],
     ['6–12 мес.', 'Junior Data Scientist', '0.5–1 г.', '2 500–3 500 EUR', 'ML pipeline + Kaggle конкурс'],
     ['6–12 мес.', 'Junior AI Engineer', '0.5–1 г.', '3 000–5 000 EUR', 'LLM API + RAG проект + agents demo'],
     ['1–2 года', 'Data Scientist / AI Eng', '1–2 г.', '3 500–6 000 EUR', 'Production ML / AI продукт в проде'],
     ['2–4 года', 'Mid Data Scientist', '2–4 г.', '5 000–8 000 EUR', 'System Design + лидерство'],
     ['Параллельно', 'Quant / Risk DS', '1–2 г.', '4 500–8 000 EUR', 'Твоя финансовая ниша — диплом уже есть!']],
    col_widths=[2.5, 3.8, 2.0, 3.5, 4.7])

add_body(doc, 'Твой диплом = ~6–12 месяцев «виртуального опыта» в глазах финансовых работодателей. DCC-GARCH + DM-тест + walk-forward > Titanic для банков и хедж-фондов.', italic=True)

doc.add_page_break()

# ============================================================
# ГЛАВА 3
# ============================================================
add_chapter_header(doc, 'ГЛАВА 3: 16-НЕДЕЛЬНЫЙ ПЛАН',
    '1 час в день · 7 дней в неделю · 112 часов до первых офферов')

add_section_header(doc, 'Обзор фаз')
make_table(doc,
    ['Фаза', 'Недели', 'Название', 'Содержание', 'Результат'],
    [['Фаза 1', 'нед. 1–3', 'Фундамент', 'Python + SQL + Git', '→ базовые тесты'],
     ['Фаза 2', 'нед. 4–6', 'Теория ML', 'Алгоритмы, метрики, валидация', '→ ML-интервью'],
     ['Фаза 3', 'нед. 7–9', 'Практика', 'Kaggle + LeetCode + портфолио', '→ тест-задания'],
     ['Фаза 4', 'нед. 10–11', 'Спец-я DS', 'Time Series / Stats / Quant', '→ твоя ниша'],
     ['Фаза 5', 'нед. 12', 'Симуляция DS', 'Mock-интервью + оффер DS', '→ HR + финал'],
     ['Фаза 6', 'нед. 13–16', 'AI Engineer', 'LLM API → Embeddings → Agents → Deploy', '→ AI Engineer оффер']],
    col_widths=[2.2, 2.5, 2.8, 5.5, 3.5])

add_section_header(doc, 'Детальный план по неделям')

weeks = [
    ('НЕД. 1 — Python: pandas & numpy  [7ч]',
     'pandas Series/DataFrame, loc/iloc, boolean mask, groupby, pivot_table, merge/join/concat, apply, map, lambda, numpy arrays + broadcasting',
     '[ ] Kaggle Pandas курс до конца  [ ] 10 pandas задач решить  [ ] Broadcasting numpy изучить  [ ] EDA скрипт на своих данных  [ ] 1 Kaggle notebook опубликовать',
     'kaggle.com/learn/pandas · numpy.org/doc · github.com/guipsamora/pandas_exercises'),
    ('НЕД. 2 — SQL: основы + JOIN  [7ч]',
     'SELECT, WHERE, ORDER BY, GROUP BY, HAVING, DISTINCT, INNER/LEFT/RIGHT JOIN, Подзапросы, IN, EXISTS, CASE WHEN, COALESCE, NULLIF, Агрегатные функции',
     '[ ] SQLZoo все задачи Part 1–6  [ ] Mode Analytics SQL Tutorial  [ ] 15 LeetCode easy SQL задач  [ ] 5 аналитических запросов написать  [ ] DBeaver + PostgreSQL установить',
     'sqlzoo.net · mode.com/sql-tutorial · leetcode.com/studyplan/top-sql-50'),
    ('НЕД. 3 — SQL: оконные функции + Git  [7ч]',
     'ROW_NUMBER, RANK, DENSE_RANK, LAG, LEAD, NTILE, SUM/AVG OVER (PARTITION BY), CTE — WITH...AS, Git: commit/branch/merge/rebase, GitHub: PR/README/Issues',
     '[ ] LeetCode Top SQL 50 (medium)  [ ] GitHub профиль создать  [ ] Диплом загрузить на GitHub + README  [ ] 10 задач на оконные функции  [ ] learngitbranching.js.org пройти',
     'pgexercises.com · advanced-sql-puzzles.com · learngitbranching.js.org'),
    ('НЕД. 4 — ML: классика — теория  [7ч]',
     'Линейная/логистическая регрессия, Decision Tree, Random Forest, Bias-variance tradeoff, Кросс-валидация, GridSearchCV, Метрики: RMSE/MAE/R2/F1/AUC/AP, Регуляризация Ridge/Lasso/ElasticNet',
     '[ ] StatQuest: Linear Regression (YT)  [ ] StatQuest: Random Forest  [ ] sklearn: 3 модели на Titanic  [ ] Bias-variance объяснить своими словами  [ ] Pipeline с CV написать',
     'statquest.org · scikit-learn.org/stable/tutorial · kaggle.com/learn/machine-learning'),
    ('НЕД. 5 — ML: продвинутые алгоритмы  [7ч]',
     'Gradient Boosting, XGBoost, LightGBM, SVM (основы + kernel trick), K-Means, DBSCAN, PCA, t-SNE, UMAP, SHAP values + feature importance, Stacking/Blending ансамбли',
     '[ ] XGBoost туториал + своя модель  [ ] Kaggle: House Prices competition  [ ] SHAP объяснение одной модели  [ ] PCA визуализация своих данных  [ ] RF vs GBM vs XGBoost сравнить',
     'xgboost.readthedocs.io · shap.readthedocs.io · kaggle.com/competitions/house-prices'),
    ('НЕД. 6 — Статистика + А/В тесты  [7ч]',
     'Центральная предельная теорема, p-value, alpha, мощность теста, t-тест, Mann-Whitney U-тест, Доверительные интервалы (CI), A/B тест: дизайн + размер выборки, Multiple testing: Bonferroni, FDR',
     '[ ] Khan Academy: Statistics (бесплатно)  [ ] A/B тест написать с нуля на Python  [ ] Bootstrap CI разобрать (есть в дипломе!)  [ ] 3 вопроса про p-value с объяснением  [ ] Рассчитать размер выборки для A/B',
     'khanacademy.org · statisticsbyjim.com · StatQuest: Hypothesis Testing'),
    ('НЕД. 7 — Time Series — ТВОЯ НИША!  [7ч]',
     'ARIMA, SARIMA (p, d, q), ACF/PACF корреляграммы, Stationarity + ADF/KPSS тест, Rolling features, lag features, Prophet (Facebook/Meta), Метрики: MAPE, SMAPE, RMSE OOS',
     '[ ] Kaggle: Store Sales competition  [ ] ARIMA на финансовых данных  [ ] Prophet на открытом датасете  [ ] ADF тест объяснить (из диплома!)  [ ] Walk-forward (ты это уже делал!)',
     'otexts.com/fpp3 (БЕСПЛАТНАЯ книга!) · kaggle.com/competitions/store-sales · statsmodels ARIMA docs'),
    ('НЕД. 8 — Portfolio + LeetCode  [7ч]',
     'LeetCode: массивы, хэш-таблицы, строки, скользящее окно, Two pointers, binary search паттерны, ML project структура, Streamlit для демо-приложения, Docker basics',
     '[ ] 20 LeetCode easy задач  [ ] Диплом оформить как кейс на GitHub  [ ] Streamlit демо одной модели  [ ] 5 LeetCode medium задач  [ ] 2-страничное резюме написать',
     'leetcode.com/studyplan/top-interview-150 · streamlit.io/docs · neetcode.io'),
    ('НЕД. 9 — ML System Design + MLOps  [7ч]',
     'Feature store концепт, Model versioning (MLflow), Data drift + мониторинг, REST API с FastAPI + Pydantic, Docker: build/run/volumes/compose, CI/CD идеи для ML pipeline',
     '[ ] ML System Design primer прочесть  [ ] MLflow: залогировать эксперимент  [ ] FastAPI endpoint для модели сделать  [ ] Понять что такое feature store  [ ] Ответить на системный вопрос дизайна',
     'github.com/chiphuyen/ml-systems-design · mlflow.org/docs · fastapi.tiangolo.com'),
    ('НЕД. 10 — LLM Фундамент + AI API  [7ч]',
     'Что такое LLM: токены, context window, temperature, top-p; Transformer архитектура (концептуально); GPT vs BERT vs T5; OpenAI API / Anthropic API: основы; Prompt engineering: zero-shot, few-shot, chain-of-thought; Hallucination: причины и способы борьбы',
     '[ ] Andrej Karpathy: "Let\'s build GPT" (YouTube — ОБЯЗАТЕЛЬНО!)  [ ] OpenAI или Anthropic API: написать первый скрипт  [ ] 10 prompt engineering задач  [ ] Объяснить токенизацию своими словами  [ ] Прочесть: "Prompt Engineering Guide" (бесплатно)',
     'youtube.com (Andrej Karpathy) · platform.openai.com/docs · docs.anthropic.com · promptingguide.ai'),
    ('НЕД. 11 — Поведенческие вопросы + резюме  [7ч]',
     'STAR метод (Situation-Task-Action-Result), Elevator pitch (2 мин), Провалы и уроки, Почему DS/ML/AI Engineer?, Конфликты в команде, Зарплатные переговоры тактика',
     '[ ] 20 HR вопросов по STAR написать  [ ] Elevator pitch отрепетировать (запись!)  [ ] LinkedIn профиль обновить на английском  [ ] 10 откликов разослать  [ ] 3 вопроса для интервьюера подготовить',
     'linkedin.com/jobs · levels.fyi · glassdoor.com · github.com/yangshun/tech-interview-handbook'),
    ('НЕД. 12 — Mock-интервью DS + первые офферы  [7ч]',
     'Полное техническое интервью DS x2, Разбор ошибок + пробелы заполнить, Live coding на время, Salary negotiation тактика, Сравнение и оценка офферов, Первые 90 дней на новом месте',
     '[ ] 2 mock-интервью DS (Pramp / Interviewing.io)  [ ] 5 задач решить на время  [ ] Все пробелы DS закрыть  [ ] Резюме и LinkedIn финализировать  [ ] Ещё 20 откликов отправить (DS роли)',
     'pramp.com (БЕСПЛАТНО!) · interviewing.io · glassdoor interview questions'),
]

ai_weeks = [
    ('НЕД. 13 — LLM API Advanced + Prompt Engineering  [7ч]  ★ ФАЗА 6: AI ENGINEER',
     'OpenAI / Anthropic / Mistral API — полный разбор; Function calling (tool use); Structured outputs (JSON mode); Streaming responses; Управление context window; Cost optimization: кэширование, batching, выбор размера модели',
     '[ ] Построить chatbot с историей диалога  [ ] Реализовать function calling (weather tool)  [ ] Написать скрипт с structured JSON output  [ ] Сравнить GPT-4o vs Claude на одной задаче  [ ] deeplearning.ai: "Prompt Engineering for Developers" (бесплатно)',
     'platform.openai.com/docs/guides/function-calling · docs.anthropic.com/en/docs/tool-use · deeplearning.ai/short-courses · cookbook.openai.com'),
    ('НЕД. 14 — Embeddings + Vector Databases  [7ч]',
     'Что такое embedding: word2vec → sentence transformers → text-embedding-3; Семантический поиск vs keyword search; Vector databases: ChromaDB, Qdrant, Pinecone; Similarity metrics: cosine, dot product; Chunking стратегии; Основы RAG',
     '[ ] Создать semantic search на своих данных  [ ] Поднять ChromaDB локально  [ ] Реализовать простой RAG: PDF → embeddings → Q&A  [ ] HuggingFace: попробовать sentence-transformers  [ ] Визуализировать embeddings через PCA/UMAP',
     'chromadb.com/docs · qdrant.tech/documentation · huggingface.co/sentence-transformers · sbert.net'),
    ('НЕД. 15 — AI Agents + RAG Advanced  [7ч]',
     'Что такое AI Agent: ReAct, Chain-of-Thought, Tool Use; LangChain / LlamaIndex — основные концепции; Multi-step agents: планирование + исполнение + рефлексия; RAG advanced: hybrid search, reranking, HyDE; Memory для агентов: short-term vs long-term',
     '[ ] Построить простого агента с 2-3 инструментами (поиск + калькулятор + код)  [ ] Реализовать advanced RAG с reranking  [ ] LangChain: цепочка из 3+ шагов  [ ] Сравнить ReAct vs simple chain  [ ] Задокументировать агент на GitHub с README',
     'python.langchain.com/docs · docs.llamaindex.ai · deeplearning.ai/short-courses/functions-tools-agents-langchain'),
    ('НЕД. 16 — Deployment + Safety + Mock AI Engineer Interview  [7ч]',
     'Безопасность AI: prompt injection, jailbreaking, data exfiltration; Hallucination detection; Evaluation frameworks: RAGAS, TruLens, DeepEval; FastAPI + LLM: production endpoint; Docker контейнеризация AI приложения; Мониторинг: LangSmith, Langfuse',
     '[ ] Написать тест на prompt injection для своего агента  [ ] Добавить RAGAS evaluation к RAG pipeline  [ ] Задеплоить LLM endpoint на FastAPI + Docker  [ ] 2 mock AI Engineer интервью  [ ] Финальное портфолио: 3 AI проекта на GitHub',
     'ragas.io · docs.smith.langchain.com · fastapi.tiangolo.com · github.com/confident-ai/deepeval · owasp.org/LLM'),
]

for title, topics, tasks, resources in weeks:
    add_week_header(doc, title)
    make_table(doc,
        ['Темы', 'Задачи', 'Ресурсы'],
        [[topics, tasks, resources]],
        col_widths=[5.5, 5.5, 5.5])

for title, topics, tasks, resources in ai_weeks:
    add_week_header(doc, title)
    make_table(doc,
        ['Темы', 'Задачи', 'Ресурсы'],
        [[topics, tasks, resources]],
        col_widths=[5.5, 5.5, 5.5])

doc.add_page_break()

# ============================================================
# ГЛАВА 4
# ============================================================
add_chapter_header(doc, 'ГЛАВА 4: МАТРИЦА НАВЫКОВ',
    'Что у тебя есть и что нужно добавить — честный аудит')

add_section_header(doc, 'Технические навыки')
make_table(doc,
    ['Навык', 'Уровень', 'Приоритет', 'Что делать'],
    [['Python (pandas / numpy)', '4/5 — есть', 'КРИТИЧНО', 'Kaggle курс + 30 задач'],
     ['Python (sklearn pipeline)', '4/5 — есть', 'КРИТИЧНО', 'Углубить ColumnTransformer'],
     ['SQL — базовый (JOIN, GROUP BY)', '2/5 — слабо', 'КРИТИЧНО', 'Нед. 2 плана — ключевой пробел'],
     ['SQL — оконные функции', '1/5 — нет', 'КРИТИЧНО', 'Нед. 3 — без этого не пройти'],
     ['Git / GitHub + README', '2/5 — базово', 'ВАЖНО', 'Выложить диплом + readme'],
     ['ML алгоритмы (теория)', '3/5 — есть', 'КРИТИЧНО', 'StatQuest + объяснения вслух'],
     ['XGBoost / LightGBM', '4/5 — есть', 'OK', 'Поддерживать, знаешь хорошо'],
     ['Time Series (ARIMA / WF)', '4/5 — есть', 'ПРЕИМУЩЕСТВО!', 'Ниша для финансовых компаний'],
     ['DCC-GARCH / эконометрика', '4/5 — есть', 'FINANCE НИША', 'Редкий навык — акцентируй'],
     ['Bootstrap CI / DM-тест', '4/5 — есть', 'FINANCE НИША', 'Статвалидность — рассказывай!'],
     ['Статистика (p-value, CI, A/B)', '3/5 — есть', 'ВАЖНО', 'A/B тест + Bonferroni добавить'],
     ['LeetCode (coding задачи)', '2/5 — слабо', 'ВАЖНО', 'Easy: 30 задач, Medium: 10'],
     ['LLM основы (токены, API)', '1/5 — нет', 'AI ENGINEER', 'Нед. 10 — старт AI трека'],
     ['Prompt Engineering', '1/5 — нет', 'AI ENGINEER', 'Нед. 10 + 13 — ключевой навык'],
     ['Embeddings / Vector DB', '1/5 — нет', 'AI ENGINEER', 'Нед. 14 — ChromaDB + RAG'],
     ['AI Agents (LangChain)', '1/5 — нет', 'AI ENGINEER', 'Нед. 15 — строить агентов'],
     ['AI Safety / Evaluation', '1/5 — нет', 'AI ENGINEER', 'Нед. 16 — RAGAS, prompt injection'],
     ['Docker / MLflow', '1/5 — нет', 'ЖЕЛАТЕЛЬНО', 'Нед. 9 + 16 — базовый уровень'],
     ['FastAPI / REST API', '1/5 — нет', 'ЖЕЛАТЕЛЬНО', 'Нед. 9 + 16 + простое демо'],
     ['Deep Learning (теория)', '2/5 — есть', 'ЖЕЛАТЕЛЬНО', 'Понять transformer концептуально']],
    col_widths=[5.0, 3.0, 3.5, 5.0])

add_section_header(doc, 'Уникальные активы из диплома — говори о них на каждом собесе')
for b in ['Walk-forward evaluation — понимаешь leakage там, где большинство джунов нет',
          'Diebold-Mariano test — статистически доказываешь, что твоя модель лучше (редкость!)',
          'DCC-GARCH — эконометрика волатильности, высоко ценится в банках и хедж-фондах',
          'Bootstrap CI — правильная оценка неопределённости метрик (не просто RMSE)',
          'Fisher-z трансформация — понимаешь нюансы предобработки таргета',
          'Reproducible pipeline (config.yaml + run_all.py) — промышленный стандарт',
          'Реальные финансовые данные (yfinance + кэширование) — практика с prod-данными',
          'Сравнение ML vs эконометрика (DM-тест) — именно так работают Quant Analyst']:
    add_bullet(doc, b)

doc.add_page_break()

# ============================================================
# ГЛАВА 5
# ============================================================
add_chapter_header(doc, 'ГЛАВА 5: БАНК ВОПРОСОВ И ОТВЕТОВ',
    'Самые частые вопросы на собеседованиях DS / MLE / AI Engineer / Quant')

qa_sections = {
    'Python': [
        ('[Python] Разница между list и tuple?',
         'List — изменяемый (mutable), tuple — неизменяемый (immutable). Tuple быстрее для итерации и хэшируется. Используй tuple для фиксированных данных (координаты, ключи словаря), list — для изменяемых коллекций.'),
        ('[Python] Что такое Generator? Зачем нужен?',
         'Функция с yield — возвращает итератор лениво, не загружает всё в память. Используй для больших файлов, ETL пайплайнов, бесконечных последовательностей.'),
        ('[Python] Как работает GIL в Python?',
         'Global Interpreter Lock — мьютекс, только один поток выполняет байткод. threading не даёт CPU-параллелизм. Решение: multiprocessing или C-extensions (numpy, pandas уже обходят GIL внутри).'),
        ('[Python] copy() vs deepcopy()?',
         'copy() — поверхностная: копирует контейнер, вложенные объекты — ссылки. deepcopy() — рекурсивно. df.copy() в pandas — полная копия. df2 = df1 — это НЕ копия, это ссылка!'),
    ],
    'SQL': [
        ('[SQL] Разница INNER / LEFT / RIGHT / FULL JOIN?',
         'INNER: только совпадающие. LEFT: все из левой + NULL из правой. RIGHT: обратное. FULL OUTER: все строки обоих + NULL где нет совпадения. На практике LEFT JOIN используется чаще всего.'),
        ('[SQL] Оконные функции — объясни + пример.',
         'Вычисляют для каждой строки без схлопывания: ROW_NUMBER() OVER (PARTITION BY dept ORDER BY salary DESC) — ранг в отделе. LAG(salary, 1) OVER (ORDER BY date) — вчерашняя зарплата. Разница с GROUP BY: строки остаются.'),
        ('[SQL] Найди дубликаты в таблице.',
         'SELECT email, COUNT(*) cnt FROM users GROUP BY email HAVING COUNT(*) > 1. Или через ROW_NUMBER() OVER (PARTITION BY email ORDER BY id) и WHERE rn > 1.'),
        ('[SQL] WHERE vs HAVING?',
         'WHERE фильтрует строки ДО агрегации. HAVING фильтрует группы ПОСЛЕ GROUP BY. HAVING может использовать агрегатные функции (COUNT, SUM), WHERE — нет.'),
    ],
    'Machine Learning': [
        ('[ML] Bias-variance tradeoff — объясни.',
         'Bias = ошибка из-за слишком простой модели (underfitting). Variance = из-за слишком сложной (overfitting). Баланс: регуляризация, ансамбли, CV.'),
        ('[ML] Precision vs Recall — когда что?',
         'Precision = TP/(TP+FP). Recall = TP/(TP+FN). Ложные положительные дороги (спам-фильтр) → precision. Ложные отрицательные дороги (диагностика рака) → recall. F1 — гармоническое среднее.'),
        ('[ML] XGBoost vs Random Forest — отличия?',
         'RF: параллельные деревья, averaging снижает variance. XGBoost: последовательный boosting, каждое дерево исправляет ошибки предыдущего → снижает bias. XGBoost точнее, RF устойчивее к дефолтным параметрам.'),
        ('[ML] Data leakage — как предотвращал в дипломе?',
         'Walk-forward: обучение только на данных до момента предсказания. Нормализация только на train-части. DCC-GARCH на expanding window без lookahead. Конкретный пример — расскажи детально на собесе!'),
    ],
    'Time Series — твоя специализация': [
        ('[TS] Стационарность — что это и как проверить?',
         'Ряд стационарен если mean, variance, autocovariance не зависят от времени. ADF-тест: H0 = unit root (нестационарный). p<0.05 → стационарен. KPSS — обратная логика. Ты делал ADF в дипломе!'),
        ('[TS] Walk-forward validation — объясни.',
         'Expanding window: обучаем на [0..t], предсказываем t+1, затем [0..t+1] → t+2. Уважает временной порядок, предотвращает lookahead bias. Твой диплом: min_train=800, refit_every=20.'),
        ('[TS] Diebold-Mariano тест — объясни.',
         'Тест сравнения прогностической точности двух моделей. H0: обе дают одинаковую точность. Использует loss-дифференциалы и их автокорреляцию. Ты применял в дипломе (ML vs DCC-GARCH) — редкий навык!'),
    ],
    'AI Engineer': [
        ('[AI] Что такое токен в LLM? Почему это важно?',
         'Токен — единица текста, ~0.75 слова в английском. "Hello world" = 2-3 токена. Важно: (1) pricing по токенам, (2) context window ограничен (8K–200K токенов), (3) длинные документы нужно чанковать.'),
        ('[AI] RAG vs Fine-tuning — когда что применять?',
         'RAG: документы → embeddings → vector DB → при запросе извлекаем релевантное → в prompt. Плюсы: актуальные данные, нет переобучения, дешевле. Fine-tuning — если RAG не справляется с форматом/стилем.'),
        ('[AI] Что такое prompt injection? Как защититься?',
         'Атака: злой пользователь вставляет инструкции, которые меняют поведение LLM. Защита: (1) input validation, (2) output validation, (3) ограничение прав системного промпта, (4) sandboxing.'),
        ('[AI] Как работают embeddings? Зачем нужны?',
         'Преобразуют текст в вектор. Семантически похожие тексты → близкие векторы. Применения: семантический поиск, RAG, кластеризация документов, рекомендательные системы.'),
        ('[AI] Что такое AI агент? Отличие от LLM вызова?',
         'Простой вызов: prompt → LLM → ответ. Агент: LLM + инструменты + память + цикл рассуждений. ReAct паттерн: Think → Act → Observe → Think → ... Инструменты: поиск, калькулятор, SQL, API.'),
        ('[AI] Как оценивать качество RAG системы?',
         'RAGAS: (1) Faithfulness — ответ подтверждён retrieved документами? (2) Answer Relevancy — ответ релевантен вопросу? (3) Context Precision — retrieved контекст точный? (4) Context Recall — весь нужный контекст найден?'),
        ('[AI] Как бороться с галлюцинациями LLM?',
         '(1) RAG: отвечать только на основе retrieved фактов. (2) Self-consistency: несколько ответов → consensus. (3) Grounding: каждое утверждение подкреплять source. (4) Output validation через внешний источник.'),
    ],
    'Поведенческие вопросы (STAR)': [
        ('[HR] Расскажи о самом сложном техническом проекте.',
         'Диплом — ML-прогнозирование зависимостей Bitcoin и традиционных активов. Сложность: data leakage в временных рядах. Решение: walk-forward (min_train=800, refit_every=20). Результат: ML значимо лучше DCC-GARCH (DM-тест p<0.01), AR1 RMSE=0.066.'),
        ('[HR] Почему именно AI Engineering / Data Science?',
         'В дипломе увидел, что правильно построенная ML модель даёт реальные инсайты о рынке. Теперь хочу строить AI продукты, которые реально работают в продакшне. LLM-технологии открывают возможности, которых 3 года назад не было.'),
    ],
}

for section_name, qas in qa_sections.items():
    add_section_header(doc, section_name)
    for q, a in qas:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(1)
        r = p.add_run(q)
        r.bold = True; r.font.size = Pt(9); r.font.name = 'Arial'
        r.font.color.rgb = BLUE_DARK
        p2 = doc.add_paragraph()
        p2.paragraph_format.space_before = Pt(1)
        p2.paragraph_format.space_after = Pt(6)
        p2.paragraph_format.left_indent = Cm(0.5)
        r2 = p2.add_run(a)
        r2.font.size = Pt(9); r2.font.name = 'Arial'

doc.add_page_break()

# ============================================================
# ГЛАВА 6
# ============================================================
add_chapter_header(doc, 'ГЛАВА 6: БЕСПЛАТНЫЕ РЕСУРСЫ',
    'Всё что нужно для подготовки — есть бесплатно')

add_section_header(doc, 'Книги (open access)')
for b in ['«Introduction to Statistical Learning» (ISLP) — islp.org — классика ML с R и Python',
          '«Forecasting: Principles & Practice» (FPP3) — otexts.com/fpp3 — лучшее по временным рядам',
          '«Deep Learning» (Goodfellow) — deeplearningbook.org — теория нейросетей',
          '«Python Data Science Handbook» — jakevdp.github.io/PythonDataScienceHandbook',
          '«ML System Design» (Huyen) — github.com/chiphuyen/machine-learning-systems-design',
          'deeplearning.ai/short-courses — БЕСПЛАТНЫЕ курсы по LLM и AI Engineering']:
    add_bullet(doc, b)

add_section_header(doc, 'YouTube каналы')
for b in ['StatQuest with Josh Starmer — лучшие объяснения ML/Stats простым языком',
          'Andrej Karpathy — нейросети, backprop, GPT с нуля (ОБЯЗАТЕЛЕН для AI Engineer!)',
          '3Blue1Brown — математика с визуализацией (линейная алгебра, calculus)',
          'ritvikmath — временные ряды, ARIMA, эконометрика (отлично для твоей ниши!)',
          'AI Jason / Sam Witteveen — LangChain, AI Agents, LLM туториалы',
          'sentdex — практический Python для DS']:
    add_bullet(doc, b)

add_section_header(doc, 'Практика и тренажёры')
for b in ['kaggle.com — бесплатные курсы + соревнования + ноутбуки (главный ресурс!)',
          'leetcode.com — алгоритмические задачи (Easy 30 + Medium 10 = достаточно для DS)',
          'sqlzoo.net — SQL от нуля до оконных функций',
          'deeplearning.ai/short-courses — БЕСПЛАТНЫЕ мини-курсы по LLM',
          'huggingface.co/learn — embeddings, transformers, agents',
          'promptingguide.ai — полный гайд по prompt engineering',
          'colab.research.google.com — бесплатный GPU для AI экспериментов',
          'pramp.com — БЕСПЛАТНЫЕ mock-интервью с реальными людьми']:
    add_bullet(doc, b)

add_section_header(doc, 'Основные библиотеки')
make_table(doc,
    ['Библиотека', 'Важность', 'Что знать', 'Где учить'],
    [['pandas', 'Обязат.', 'read_csv, groupby, merge, pivot, apply, datetime index', 'kaggle.com/learn/pandas'],
     ['numpy', 'Обязат.', 'arrays, broadcasting, random, linalg basics', 'numpy.org quickstart'],
     ['scikit-learn', 'Обязат.', 'Pipeline, GridSearchCV, metrics, preprocessing', 'sklearn user guide'],
     ['XGBoost', 'Важно', 'XGBRegressor/Classifier, feature_importances_, cv', 'xgboost.readthedocs.io'],
     ['statsmodels', 'Важно', 'OLS, ARIMA, ADF test, acf/pacf, summary()', 'statsmodels examples'],
     ['openai', 'AI Engineer', 'ChatCompletion, embeddings, function calling', 'platform.openai.com/docs'],
     ['anthropic', 'AI Engineer', 'messages API, tool use, streaming', 'docs.anthropic.com'],
     ['langchain', 'AI Engineer', 'chains, agents, tools, memory, retrievers', 'python.langchain.com'],
     ['chromadb', 'AI Engineer', 'collections, add, query, embeddings', 'chromadb.com/docs'],
     ['FastAPI', 'Желат.', 'GET/POST endpoint, Pydantic model, uvicorn', 'fastapi.tiangolo.com'],
     ['MLflow', 'Желат.', 'log_metric, log_model, ui, model registry', 'mlflow.org tutorial'],
     ['Docker', 'Желат.', 'Dockerfile, build/run, volumes, ports, docker-compose', 'docs.docker.com']],
    col_widths=[2.8, 2.5, 6.0, 5.2])

add_section_header(doc, 'Поиск работы — площадки')
for b in ['linkedin.com/jobs — главная площадка, полный профиль на английском обязателен',
          'relocate.me — вакансии с релокацией + remote EU',
          'remoteok.com — remote DS/ML (много US-компаний, платят по US-рейтам)',
          'glassdoor.com — зарплаты + отзывы + реальные вопросы с интервью',
          'levels.fyi — реальные зарплаты DS/SWE по компаниям (лучший источник данных)',
          'otta.com — агрегатор стартапов Европа (много DS вакансий)',
          'bettingjobs.com + parlayJobs.com — iGaming вакансии для Белграда']:
    add_bullet(doc, b)

doc.add_page_break()

# ============================================================
# ГЛАВА 7: ЧЕК-ЛИСТЫ
# ============================================================
add_chapter_header(doc, 'ГЛАВА 7: ПЕЧАТНЫЕ ЧЕК-ЛИСТЫ',
    'Распечатай и отмечай каждый день')

checklists = {
    'Python / pandas / numpy': [
        'Kaggle Pandas курс пройден до конца',
        'Решено 30+ pandas задач',
        'Понимаю broadcasting в numpy',
        'Векторизованный код вместо for-loop — умею писать',
        'list comprehensions, generators, decorators — могу объяснить вслух',
        'copy() vs deepcopy() — знаю разницу и когда важно',
        'Могу написать EDA скрипт за 20 минут',
    ],
    'SQL': [
        'SELECT / WHERE / ORDER BY — автоматически, без гугла',
        'GROUP BY + HAVING + агрегатные функции — с примерами',
        'INNER / LEFT / RIGHT / FULL JOIN — объясняю разницу',
        'Оконные функции: ROW_NUMBER, RANK, LAG, SUM OVER',
        'CTE (WITH ... AS ...) — умею писать',
        'Решено 25+ задач LeetCode SQL (Easy + Medium)',
        'Дубликаты / N-я запись / топ-N per group — знаю несколько решений',
    ],
    'Machine Learning': [
        'Bias-variance tradeoff — объясняю без записки за 1 минуту',
        'Метрики: RMSE, MAE, R2, Precision, Recall, F1, AUC, PR-AUC',
        'Кросс-валидация: k-fold и TimeSeriesSplit — когда что',
        'RF vs XGBoost — разница, преимущества, когда что использовать',
        'Регуляризация L1/L2 — что делает математически и зачем',
        'Обработка пропусков: 4+ стратегии с примерами',
        'ROC-AUC vs PR-AUC — знаю когда что',
        'Расскажу о своём дипломе за 2 минуты',
    ],
    'AI Engineer': [
        'Объясняю что такое токен и почему context window важен',
        'Сделал хотя бы 1 проект с LLM API (OpenAI или Anthropic)',
        'Понимаю разницу RAG vs fine-tuning — когда что',
        'Реализовал простой RAG с vector database',
        'Знаю что такое prompt injection и 3 способа защиты',
        'Построил простого AI агента с инструментами',
        'Есть хотя бы 1 AI проект на GitHub с README',
    ],
    'Статистика': [
        'p-value — определение + 2 популярных заблуждения',
        't-тест vs Mann-Whitney — когда что применять',
        'Bootstrap CI — как считается, в чём преимущество',
        'A/B тест — дизайн от начала до конца',
        'Multiple testing problem — знаю Bonferroni поправку',
    ],
    'Portfolio & GitHub': [
        'GitHub профиль создан, фото, bio, skills',
        'Диплом-проект загружен с подробным README',
        'Kaggle notebook опубликован (хотя бы 1)',
        'LinkedIn полностью заполнен на английском + ключевые слова DS/ML/AI',
        '2-страничное резюме в PDF (без фото для EU/US)',
        'AI проект на GitHub: RAG или агент с документацией',
    ],
    'LeetCode / Coding': [
        '30 задач Easy решено (arrays, strings, hashmap)',
        '10 задач Medium решено (two pointers, sliding window)',
        'Binary search — умею писать чисто',
        'Могу решать задачу вслух, объясняя ход мыслей',
    ],
    'Поведение / HR': [
        'Elevator pitch (2 мин) отрепетирован и записан',
        'STAR ответы для 5+ ситуаций готовы и отрепетированы',
        'Желаемую зарплату знаю и умею называть диапазон',
        '3 умных вопроса для интервьюера подготовлены',
        'Провёл 2+ mock-интервью (Pramp или с другом)',
        'Знаю компанию перед собесом: продукт, рынок, стек, конкуренты',
    ],
}

for section_name, items in checklists.items():
    p = doc.add_paragraph()
    r = p.add_run('>> ' + section_name)
    r.bold = True; r.font.size = Pt(10); r.font.name = 'Arial'
    r.font.color.rgb = BLUE_DARK
    for item in items:
        p2 = doc.add_paragraph()
        p2.paragraph_format.left_indent = Cm(0.5)
        p2.paragraph_format.space_before = Pt(1)
        p2.paragraph_format.space_after = Pt(1)
        r2 = p2.add_run('[ ]  ' + item)
        r2.font.size = Pt(9); r2.font.name = 'Arial'
    doc.add_paragraph()

doc.add_page_break()

# ============================================================
# ГЛАВА 8
# ============================================================
add_chapter_header(doc, 'ГЛАВА 8: КАК ПОДАТЬ СВОЙ ОПЫТ',
    'Диплом = портфолио. Как правильно упаковать и продать.')

add_section_header(doc, '2-минутный рассказ о дипломном проекте')
add_body(doc, 'Структура: Проблема → Данные → Метод → Результат → Вывод', bold=True)
add_body(doc, '«Я разрабатывал систему прогнозирования зависимостей между Bitcoin и традиционными активами (S&P 500, Gold, USD) для инвесторов. Использовал ~2 000 ежедневных наблюдений с Yahoo Finance. Построил walk-forward ML пайплайн: Ridge, ElasticNet, XGBoost, Random Forest, сравнил с DCC-GARCH. Результат: ML значимо лучше DCC-GARCH (DM-тест, p<0.01), AR1 RMSE=0.066. Вывод: persistence доминирует — важно для портфельного риск-менеджмента.»')
add_body(doc, 'Три акцента: walk-forward (понимание leakage), DM-тест (статвалидность), reproducible pipeline — это то, что многие джуны не делают.', italic=True)

add_section_header(doc, 'Идеи для дополнительных AI/ML проектов GitHub')
for b in ['Titanic survival prediction — 2 часа, классика, должно быть в каждом резюме',
          'House Prices (regression + feature engineering) — 4 часа, Kaggle Medium',
          'Store Sales (time series + LightGBM) — 6 часов, прямо в твою специализацию!',
          'Bitcoin Q&A RAG System — задай вопросы о крипто рынке через свои данные + LLM',
          'Financial News Sentiment Agent — агент читает новости и анализирует влияние на BTC',
          'Crypto Correlation Dashboard (Streamlit + LLM summary) — продолжение диплома с AI']:
    add_bullet(doc, b)

add_section_header(doc, 'Зарплатные переговоры — тактика')
for b in ['Называй диапазон: «Ожидаю 2 500–3 200 EUR в зависимости от задач и стека»',
          'Никогда первым не называй цифру — спроси: «Какой бюджет у позиции?»',
          'Оффер ниже ожиданий — не отвергай сразу, бери 1–2 дня на «обдумывание»',
          'Аргументы: другие офферы, уникальные навыки (time series!), ранний старт',
          'Всё — часть компенсации: бонус, RSU, обучение, remote days, отпуск',
          'levels.fyi + glassdoor — знай рынок ДО переговоров',
          'Junior-роль: торгуйся за growth path + review через 6 мес.']:
    add_bullet(doc, b)

doc.add_page_break()

# ============================================================
# ГЛАВА 9
# ============================================================
add_chapter_header(doc, 'ГЛАВА 9: БЕЛГРАД — ПОЛНЫЙ РАЗБОР РЫНКА',
    'Персонально для Богдана Бабаева · Гражданин РФ · Белград · 2025')

add_section_header(doc, '9.0  Твой профиль vs рынок Белграда')
add_body(doc, 'Сильные стороны из CV, которые работают прямо сейчас:', bold=True)
for b in ['Сербский C1 — огромное преимущество, редкость среди россиян в Белграде',
          'Product Analyst + Data Analyst опыт 2+ лет (NNG Motors, EasyDev) — реальные проекты',
          'SQL advanced (CTEs, оконные функции) — сразу проходишь 90% скринингов',
          'ML диплом (XGBoost, walk-forward, DM-тест) — выделяешься среди аналитиков',
          'A/B тесты, воронки, когорты — product analytics, очень востребованная ниша',
          '297% рост продаж в NNG Motors — конкретная бизнес-метрика, цепляет нанимающих']:
    add_bullet(doc, b)

add_section_header(doc, '9.1  Гражданин РФ в Белграде — реальность найма')
add_body(doc, 'Сербия не присоединилась к санкциям ЕС против России. Более 17 000 российских граждан имеют ВНЖ в стране, тысячи работают в IT-секторе. Дискриминации по гражданству РФ на сербском рынке нет.')
make_table(doc,
    ['Тип компании', 'Отношение к РФ', 'Риски', 'Вывод'],
    [['Сербские локальные компании', 'Без ограничений', 'Нет', 'Зелёный свет'],
     ['Яндекс Белград', 'Российская компания', 'Нет', 'Зелёный свет'],
     ['iGaming / betting компании', 'Без ограничений, ищут рус.', 'Нет', 'Зелёный свет'],
     ['EPAM Serbia', 'Compliance check', 'Зависит от проекта', 'Жёлтый'],
     ['Grid Dynamics', 'US-компания, compliance', 'Нек. US-клиенты', 'Жёлтый'],
     ['Microsoft MDCS Belgrade', 'US-компания, санкц. compliance', 'Возможны огр.', 'Жёлтый'],
     ['Barclays / SocGen Serbia', 'EU-банки, KYC compliance', 'Возможны огр.', 'Жёлтый']],
    col_widths=[4.5, 4.5, 3.5, 4.0])

add_section_header(doc, '9.2  Топ-10 компаний Белграда для первой подачи')
make_table(doc,
    ['Приоритет', 'Компания', 'Роль', 'Почему именно ты', 'Где подать'],
    [['1. Срочно', '1xBet / Parimatch / Pin-Up', 'Product/Data Analyst', 'Рус. язык + воронки + SQL', 'LinkedIn, bettingjobs.com'],
     ['2. Срочно', 'Яндекс Белград', 'Product Analyst / DA', 'Рус. компания, M.Sc. AI, опыт', 'yandex.ru/jobs → Белград'],
     ['3. Высокий', 'Nordeus (Take-Two)', 'Data Analyst', 'Когорты, A/B, SQL — всё есть', 'nordeus.com/jobs'],
     ['4. Высокий', 'EPAM Serbia', 'Data / Product Analyst', 'Опыт аналитика 2+ лет, SQL', 'careers.epam.com'],
     ['5. Высокий', 'iGaming Белград (широко)', 'DA / Product Analyst', 'Рус. язык = конкурентное пр-во', 'bettingjobs.com, LinkedIn'],
     ['6. Средний', 'Grid Dynamics', 'Data Analyst / Jr DS', 'ML диплом + Python + SQL', 'griddynamics.com/careers'],
     ['7. Средний', 'Luxoft Belgrade', 'Data Analyst / BI', 'SQL, ETL, pandas — в наличии', 'career.luxoft.com/serbia'],
     ['8. Средний', 'Accenture / Deloitte Srb', 'Data Analyst', 'Сербский C1 + опыт аналитика', 'accenture.com/careers'],
     ['9. Цель', 'Microsoft MDCS', 'Data Scientist', 'После 1 года опыта в Белграде', 'jobs.careers.microsoft.com'],
     ['10. Цель', 'Barclays Tech Centre Srb', 'Risk / Data Analyst', 'Финансовый ML диплом — ниша', 'barclays.com/careers']],
    col_widths=[2.2, 3.5, 3.2, 4.5, 3.1])

add_body(doc, 'Сербский C1 — твоё главное конкурентное преимущество. Упомяни в первом предложении cover letter: «Как резидент Белграда, свободно владею сербским языком...»', italic=True)

doc.add_page_break()

# ============================================================
# ГЛАВА 10
# ============================================================
add_chapter_header(doc, 'ГЛАВА 10: ЕЖЕДНЕВНЫЙ ТРЕКЕР',
    'Распечатай и заполняй каждый день — 1 час = 1 шаг к офферу')

add_section_header(doc, 'Шаблон дня (1 час в день)')
tbl = doc.add_table(rows=1, cols=1)
cell = tbl.rows[0].cells[0]
set_cell_bg(cell, 'EBF5FB')
set_cell_borders(cell)
for line in ['Дата: ___________   Неделя: ____   День: ____   Тема сегодня: _______________________________',
             '',
             'Что сделал за час:',
             '  [ ] _____________________________________________________________________',
             '  [ ] _____________________________________________________________________',
             '  [ ] _____________________________________________________________________',
             '',
             'Что было сложно: ___________________________________   Что повторить завтра: _________________________________',
             '',
             'Уровень уверенности (1–10): ____']:
    p = cell.add_paragraph()
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    r = p.add_run(line)
    r.font.size = Pt(9); r.font.name = 'Arial'

doc.add_paragraph()
add_section_header(doc, 'Прогресс-трекер (16 недель)')
make_table(doc,
    ['Нед.', 'Тема', 'Часов', 'Готово', 'Заметки / ключевой вывод'],
    [[str(i+1), t, '7ч', '[ ]', ''] for i, t in enumerate([
        'Python pandas / numpy',
        'SQL основы + JOIN',
        'SQL оконные + Git',
        'ML теория (StatQuest)',
        'ML алгоритмы + XGBoost',
        'Статистика + А/В тесты',
        'Time Series — НИША!',
        'Portfolio + LeetCode',
        'ML System Design + MLOps',
        'LLM Фундамент + AI API',
        'Поведение / резюме',
        'Mock DS Interview',
        'LLM API Advanced',
        'Embeddings + Vector DB',
        'AI Agents + RAG',
        'Deploy + Safety + Mock AI',
    ])],
    col_widths=[1.5, 5.5, 1.8, 1.8, 5.9])

# Save
doc.save(r'D:\clode9\Interview_Prep_Guide_v5.docx')
print("DONE: D:\\clode9\\Interview_Prep_Guide_v5.docx")
