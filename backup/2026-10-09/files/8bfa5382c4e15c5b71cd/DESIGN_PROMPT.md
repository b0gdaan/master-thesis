# Design Improvement Prompt — Master Thesis Website

## Context

File: `D:\clear\website\index.html` — single-file (~1870 lines) academic thesis website.

**Topic:** "Forecasting Time-Varying Intermarket Dependencies Between Cryptocurrencies and Conventional Assets Using Machine Learning" — Master's thesis, University of Kragujevac, 2026.

**Current design:** GitHub Dark clone — `#0d1117` background, GitHub's exact color tokens, Inter + JetBrains Mono fonts. Functional but generic and flat.

**What the site contains (do NOT change content or data):**
- Hero with title, supervisor, stats (8 models, 4 windows, 6 assets, 10 years)
- Research questions section (RQ1–RQ3 cards)
- Dataset section (asset table with tickers)
- Methodology section (pipeline cards + tabs)
- Results section — large sortable metrics table (MAE/RMSE/R² per model per asset per window)
- Figures gallery (PNG plots from `../outputs/figures/` — correlation time series, heatmaps)
- Diebold-Mariano tests section
- Interactive demo (sliders → XGBoost signal output)
- Key findings (colored border-left blocks)
- Conclusions section
- Reproducibility section (code blocks)
- References list
- About section (author bio)

---

## Design Goals

Transform from "GitHub clone" → **premium academic research dashboard** with a distinctive identity. The site should feel like a serious data science publication — think Distill.pub meets a modern fintech dashboard.

---

## Specific Changes Required

### 1. Color Palette — Replace GitHub's colors entirely

Current (GitHub Dark, must change):
```css
--bg: #0d1117;
--bg2: #161b22;
--bg3: #21262d;
--border: #30363d;
--blue: #2d5be3;
```

Replace with a deep navy/slate palette with a teal or electric blue accent that feels premium, not corporate:
```
Backgrounds: #05090f → #0c1220 → #111b2e
Border: #1e2d45
Accent: #00b4d8 or #0ea5e9 (electric cyan-blue)
Green: #10b981, Red: #ef4444, Orange: #f59e0b
```
Make the whole palette feel like a Bloomberg Terminal or a professional quant research paper — dark, precise, data-focused.

### 2. Hero Section — Add visual impact

Current: plain text on flat background.

Make it visually striking:
- Add a **subtle animated gradient mesh** background behind the hero (CSS only, no canvas — use @keyframes on pseudo-elements with radial gradients in teal/blue/indigo)
- The h1 title should use a **gradient text effect** (linear-gradient from white to accent color, -webkit-background-clip: text)
- Add a **glowing accent line** or thin horizontal rule under the badge
- The stat cards (8 models, 4 windows, etc.) should have a subtle left-border accent color + slight glow on hover
- Hero should feel like a research paper cover, not a GitHub repo page

### 3. Navigation — Make it distinct

Current: flat sticky bar, identical to GitHub's nav.

- Change background to a slightly lighter surface than hero
- Add a **left-side colored accent bar** (3px) or a subtle bottom gradient
- The logo/brand text should use the gradient treatment
- Active nav link should have a pill background, not just colored text
- Add a thin animated underline on hover (CSS transform width 0→100%)

### 4. Section Headers — More hierarchy

Current: h2 with border-bottom only.

- Add a small **colored eyebrow label** above each h2 (e.g., "Section 03" or the section name in small caps, colored accent)
- The border-bottom on h2 should use a gradient line (background: linear-gradient(90deg, accent, transparent))
- Section alternating backgrounds — currently `--bg2` alternates. Keep this but make the transition smoother with a very subtle top/bottom gradient fade

### 5. Tables — Make them shine

Current: plain dark table, functional.

- **Header row**: add the accent color as a very subtle left border on the first column, change `--bg3` header to use the new accent-tinted color
- **Best row** (`.row-best`): change green tint + add a subtle left glow/bar in green
- **Worst row** (`.row-worst`): same treatment in red
- Add a **sticky header** to the table (`position: sticky; top: 52px` on thead tr)
- `.tag` pill badges should have slightly more padding and rounded corners (border-radius: 6px instead of 3px)
- On row hover, use the new accent tint instead of `--bg3`

### 6. Cards — Add depth

Current: flat `--bg2` background with `--border` border.

For ALL cards (`.card`, `.rq-card`, `.stat-card`, `.conclusion-card`, `.window-card`):
- Add `box-shadow: 0 1px 3px rgba(0,0,0,.3), 0 0 0 1px rgba(255,255,255,.03)` — inner light rim
- On hover: `transform: translateY(-2px)` + border-color shifts to accent
- `.conclusion-card .c-num` — make the big number use gradient text
- `.rq-card` — add a top-border gradient bar (3px, accent color)
- `.stat-card` — `.stat-num` should pulse very subtly on page load (single keyframe animation, scale 1→1.05→1, 0.4s, runs once)

### 7. Finding Blocks — More polished

Current: `border-left: 3px solid var(--blue)` — bare.

- Increase left border to `4px`
- Add `background` with a gradient (from left border color at 10% opacity, to transparent)
- Add a small icon prefix before the text based on color: 💡 (blue), ✅ (green), ⚠️ (orange), ❌ (red) — using ::before with content
- Slightly increase padding

### 8. Figure Gallery — Professional look

Current: plain image cards in a grid.

- Add a **dark overlay gradient** on the bottom of each image on hover (via ::after pseudo-element) that reveals the caption
- The caption on hover should slide up from the bottom (CSS transition)
- Add a subtle `aspect-ratio: 16/9` enforced container with `object-fit: cover` — already there, just ensure consistent sizing
- The lightbox: add a **frosted glass** blur backdrop (already has it partially), and animate the image in (scale 0.95→1, opacity 0→1, 0.2s ease)

### 9. Demo Section — Make it feel alive

Current: functional but flat two-panel layout.

- `.signal-box` — add a **pulsing border animation** when green (box-shadow 0 0 0 0 → 0 0 20px accent, @keyframes pulse, repeating)
- `.prob-bar-fill` — already has transition, just make it start from 0 and animate in on page load (add `width: 0` default, then JS sets it)
- The demo panels should have the `box-shadow` depth treatment from §6

### 10. Code Blocks — Syntax feel

Current: `.code-block` is plain monospace on `--bg3`.

- Add `border-left: 3px solid var(--accent)` 
- Add a small **copy button** in the top-right corner of each `.code-block` (CSS + minimal JS: `navigator.clipboard.writeText()`)
- The copy button should show "✓ Copied" for 2s then revert

### 11. Footer — Polish

Current: centered text, minimal.

- Add a **subtle top gradient** (from transparent to `--bg2`)
- Add the thesis title and year prominently
- Social links as icon buttons (GitHub, LinkedIn) with hover glow matching the About section buttons

### 12. Micro-interactions & Polish

Add these small but impactful touches:
- **Scroll-reveal**: elements fade-in + translateY(16px→0) as they enter the viewport — use IntersectionObserver, class `reveal` added when visible, CSS transition `opacity .4s, transform .4s`
- **Number counter animation**: stat-num values count up from 0 when the hero first enters view (pure JS, IntersectionObserver, ~800ms duration)
- **Table sort indicator**: currently has `.sort-icon` — ensure it shows ▲▼ and animates on click
- **Nav active state**: highlight the current section's nav link as user scrolls (IntersectionObserver on each `.section`, update active class)

---

## Constraints (DO NOT change these)

1. **All content/text/data stays exactly as-is** — only styling and minor structural additions (wrapper divs, classes) allowed
2. **No external JS libraries** — vanilla JS and CSS only (Google Fonts link stays)
3. **No build tools** — must remain a single `index.html` file
4. **All existing functionality** must work: tabs, filters, lightbox, table sorting, demo sliders
5. **Figure image paths** (`../outputs/figures/`) must not change
6. **Responsive** — must work on mobile (existing breakpoints at 768px/900px)
7. **Performance** — no heavy animations that would slow down the page; all transitions should be `<300ms` (except scroll-reveal)

---

## Color Reference (use these exact values)

```css
:root {
  /* Backgrounds */
  --bg: #05090f;
  --bg2: #0c1220;
  --bg3: #111b2e;
  --border: #1e2d45;
  --border-light: #243650;

  /* Text */
  --text: #e2eaf5;
  --text2: #7a9ab8;
  --text3: #3a5470;

  /* Accents */
  --accent: #0ea5e9;
  --accent-dim: #0369a1;
  --accent-glow: rgba(14,165,233,.12);
  --accent-glow-strong: rgba(14,165,233,.25);

  /* Semantic */
  --green: #10b981;
  --green-dim: #064e3b;
  --green-text: #34d399;
  --red: #ef4444;
  --red-dim: #7f1d1d;
  --red-text: #f87171;
  --orange: #f59e0b;
  --orange-text: #fbbf24;
  --purple: #8b5cf6;
  --purple-text: #a78bfa;

  /* Gradients */
  --gradient-hero: radial-gradient(ellipse 80% 60% at 50% -10%, rgba(14,165,233,.18), transparent);
  --gradient-accent-line: linear-gradient(90deg, var(--accent), transparent);
}
```

---

## Expected Output

A fully redesigned `index.html` with:
- New color palette applied throughout (replacing all old GitHub dark colors)
- Hero gradient mesh background (CSS animated pseudo-elements)
- Gradient text on h1 and logo
- Enhanced cards with shadows and hover effects
- Gradient h2 border lines
- Polished tables (sticky header, better row highlights)
- Scroll-reveal on sections
- Hero stat counter animation
- Copy buttons on code blocks
- Pulsing demo signal box
- All existing functionality preserved

Apply changes carefully — the file is ~1870 lines with complex interleaved CSS, HTML, and JS. Make targeted replacements, not a full rewrite.
