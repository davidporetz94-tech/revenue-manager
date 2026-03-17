# Spec 05: Interactive Slideshow UI

## 1. Goal

Build the React frontend slideshow viewer that renders the 12-slide diagnostic presentation from the slide deck JSON. The slideshow must feel like a consulting-grade presentation: keyboard navigation (arrow keys), slide transitions, responsive charts rendered with Recharts, and a property-switching capability. This is the primary user-facing deliverable — the thing the EliseAI hiring team evaluates.

**Measurable outcome:** Opening the app, logging in, selecting a property, and clicking "Run Diagnostic" produces a navigable 12-slide presentation with live charts, data tables, and AI-generated narrative within 15 seconds.

## 2. Exemplar

**Slideshow navigation:** `bvaughn/react-presents` (https://github.com/bvaughn/react-presents) — Gene-transfuse the Presentation/Slide component pattern, keyboard navigation, and URL-based slide routing. Simplify heavily — we don't need presenter mode or code highlighting, just clean slide transitions.

**Dashboard/charts:** `luck18210/react-tailwind-dashboard` (https://github.com/luck18210/react-tailwind-dashboard) — Reference for Recharts + Tailwind layout patterns. Adapt their responsive chart container approach.

**Recharts:** Official docs at https://recharts.org/ — Use ResponsiveContainer for all charts. Reference their BarChart, LineChart, and PieChart examples.

**Do NOT use any slideshow library directly.** Build a lightweight custom `<SlideshowViewer>` component that maps slide_deck_json to slide components. The libraries above are inspiration only.

## 3. Constraints

- **React 18+ with functional components and hooks.** No class components.
- **Tailwind CSS for styling.** No CSS-in-JS, no styled-components, no external CSS frameworks.
- **Recharts** for all data visualizations. Use `<ResponsiveContainer>` wrapper on every chart.
- **No state management library** (no Redux, no Zustand). React Context for auth + slide state is sufficient.
- **Navigation:** Arrow keys (left/right), on-screen prev/next buttons, slide counter ("3 of 12"), clickable slide thumbnail strip at bottom.
- **Property switching:** Dropdown in header to switch between Property A and Property B. Switching triggers a new diagnostic run (or loads cached if available).
- **Progressive loading:** Show a loading skeleton for slides that depend on Claude output (slides 4-12) while rendering slides 1-3 immediately from metrics data. Poll `/diagnostic/{run_id}` every 2 seconds until complete.
- **Slide transitions:** Simple fade or slide-left animation. CSS transitions only — no animation libraries.
- **Responsive:** Must look good at 1024px+ width. Charts resize via ResponsiveContainer. Below 1024px, show a "best viewed on desktop" message.
- **Color system:** Use a consistent palette. Crisis=red, warning=amber, healthy=green/teal, neutral=gray, experiment=purple. Match the diagnostic severity colors.
- **Print:** Cmd+P should produce a reasonable printout. Add `@media print` styles that show all slides vertically, one per page.

### Custom Chart Components Required

```
ScoreGauge         — SVG semicircle gauge with colored zones (0-100 scale)
KPICards           — 4 stat cards in a row with conditional coloring
RentWaterfall      — Recharts BarChart with floating bars + bracket annotation showing spread
TrendLineChart     — Recharts LineChart with dual y-axis (occupancy % left, rent $ right)
VacancyCostBar     — Horizontal bar chart sorted by value (B2 tallest)
TimelineBar        — SVG horizontal timeline with 4 phase segments
ExperimentDiagram  — SVG showing unit allocation to experiment arms with price labels
DecisionFlowchart  — SVG branching decision tree with color-coded outcomes
BeforeAfter        — Two-column comparison table with improvement arrows
DataTableSlide     — HTML table with conditional cell coloring (red/amber/green)
ActionCards        — 2×2 grid of cards with colored left borders per urgency
InvestigationTable — Styled table with area, questions, data needed, deadline columns
```

### Frontend Component Structure

```
src/components/slideshow/
├── SlideshowViewer.jsx          # Main container: manages state, keyboard nav, polling
├── SlideNavigation.jsx          # Prev/next buttons + slide counter + thumbnail strip
├── slides/
│   ├── TitleSlide.jsx           # Slide 1
│   ├── ExecutiveSummarySlide.jsx # Slide 2
│   ├── PortfolioSnapshotSlide.jsx # Slide 3
│   ├── PropertyDeepDiveSlide.jsx # Slides 4-5 (reusable per property)
│   ├── TrendAnalysisSlide.jsx   # Slide 6
│   ├── RevenueAtRiskSlide.jsx   # Slide 7
│   ├── ActionPlanOverviewSlide.jsx # Slide 8
│   ├── PhaseDetailSlide.jsx     # Slide 9
│   ├── DecisionTreeSlide.jsx    # Slide 10
│   ├── InvestigationSlide.jsx   # Slide 11
│   └── SummarySlide.jsx         # Slide 12
└── charts/
    ├── ScoreGauge.jsx
    ├── KPICards.jsx
    ├── RentWaterfall.jsx
    ├── TrendLineChart.jsx
    ├── VacancyCostBar.jsx
    ├── TimelineBar.jsx
    ├── ExperimentDiagram.jsx
    └── DecisionFlowchart.jsx
```

### Color Palette

```
CRITICAL / Crisis:    #DC2626 (red-600)
HIGH / Warning:       #D97706 (amber-600)
MEDIUM / Caution:     #F59E0B (amber-400)
HEALTHY / Good:       #059669 (emerald-600)
POSITIVE / Push:      #0D9488 (teal-600)
Experiment / MAB:     #7C3AED (violet-600)
Neutral / Info:       #6B7280 (gray-500)
Background:           #F9FAFB (gray-50)
Card Background:      #FFFFFF (white)
Text Primary:         #111827 (gray-900)
Text Secondary:       #6B7280 (gray-500)
```

## 4. Anti-Patterns

- **Do NOT** use a heavy slideshow library (reveal.js, spectacle, etc). Build a simple custom viewer. These libraries add complexity we don't need and fight our styling.
- **Do NOT** put chart logic in slide components. Each chart is its own component that receives data props. Slide components compose charts + narrative.
- **Do NOT** hardcode any data in the frontend. All data comes from the API. The frontend renders whatever the slide deck JSON contains.
- **Do NOT** make API calls from chart components. The SlideshowViewer fetches the slide deck once and passes data down as props.
- **Do NOT** use `dangerouslySetInnerHTML` for narrative text. Narrative is plain text — render it in `<p>` tags.
- **Do NOT** skip loading states. Every async operation (login, diagnostic run, slide rendering) must show appropriate loading feedback.
- **Do NOT** build the dashboard/property-list pages before the slideshow. The slideshow is the primary deliverable — get it working first, then add the surrounding chrome.

## 5. Scenarios

1. **Happy path:** Login → property list → click Property B → click "Run Diagnostic" → loading state for ~12s → slideshow appears at Slide 1. Navigate with arrow keys through all 12 slides. Each slide renders charts and narrative correctly.

2. **Slide 2 (Executive Summary):** Score gauge shows ~55 (weighted across both properties). KPI cards show: 72 units, 85% blended occupancy (for B), $17,549/mo vacancy cost, 2 critical flags. Narrative headline is 1 sentence. Three key findings displayed.

3. **Slide 5 (Property B Deep Dive):** Dual score cards: B1 shows score <30 with red coloring and "CRITICAL" badge. B2 shows ~60 with amber. Rent waterfall for B1 clearly shows the $91 gap between Asking and Comps with a red bracket. Narrative uses urgent language about B1.

4. **Slide 9 (Phase 1 Actions):** Four action cards in 2×2 grid. B1 card has red left border. B2 experiment card has purple border. Experiment diagram shows the 2/2/2 three-arm split for B2 with price labels on each group.

5. **Slide 10 (Decision Tree):** Three decision trees (B1, A2, B2) showing branching outcomes. Each branch is color-coded (green=positive, amber=continue, red=escalate). Narrative explains in plain language.

6. **Property switching:** On Slide 5 viewing Property B, user switches to Property A via dropdown. Slideshow reloads with Property A data. A1 shows green/healthy, A2 shows amber/attention needed.

7. **Loading/error states:** If diagnostic takes >5 seconds, skeleton slides shown. If API fails, error message with retry button.

## 6. Convergence Criteria

- [ ] App loads at `http://localhost:3000`, login screen appears
- [ ] Login with `demo@example.com` / `demo123` succeeds, redirects to property list
- [ ] Clicking "Run Diagnostic" on a property triggers the pipeline and displays the slideshow within 20 seconds
- [ ] All 12 slides render without console errors
- [ ] Arrow keys navigate between slides; slide counter updates ("3 of 12")
- [ ] ScoreGauge renders with correct score value and colored zone
- [ ] RentWaterfall shows correct bars with bracket annotation between Asking and Comps
- [ ] TrendLineChart shows 4 data points (Dec-Mar) with dual y-axis
- [ ] VacancyCostBar shows 4 bars sorted by value, B2 tallest
- [ ] Data table on Slide 3 has conditional cell coloring (B1 occupancy red, A1 green)
- [ ] Narrative text on all slides is non-empty and contains no placeholder text or JSON artifacts
- [ ] Property switching dropdown works — loads different diagnostic for each property
- [ ] No console errors, no broken layouts, no overlapping elements at 1280px viewport width
