# Holdout Scenarios: Spec 05 — Interactive Slideshow UI

## Scenario 5.1: Slideshow Renders Correctly End-to-End

### Setup
Backend running with seeded data. User logged in. Diagnostic run completed for Property B.

### Trigger
Navigate to Property B → "Run Diagnostic" → wait → slideshow appears.

### Expected Flow
12-slide presentation renders with navigation, charts, and narrative.

### Satisfaction Criteria
- Slideshow starts at Slide 1, counter shows "1 of 12"
- Arrow keys navigate; thumbnail strip allows direct slide access
- Cannot navigate before Slide 1 or after Slide 12
- Loading indicator shown during the ~12-15s pipeline execution
- Every slide renders without console errors or React error boundary triggers
- Spot checks: Slide 2 (gauge + KPIs visible), Slide 3 (data table with colored cells), Slide 5 (B1 crisis card red, waterfall chart renders), Slide 7 (bar chart with dollar labels), Slide 9 (action cards + experiment diagram), Slide 12 (before/after comparison)
- No "undefined", "null", "[object Object]", or placeholder text visible on any slide
- No chart overflow or layout breakage at 1280px viewport

### Edge Cases
- Resize to 1024px: layout holds, charts resize via ResponsiveContainer
- Rapid arrow key presses (12x): lands on Slide 12 without crash
- Page refresh mid-slideshow: either resumes or restarts cleanly

---

## Scenario 5.2: Data Visualization Accuracy

### Setup
Completed diagnostic. Slideshow rendered.

### Trigger
Inspect specific chart values against known metrics.

### Satisfaction Criteria
- **ScoreGauge** (Slide 2): needle matches portfolio score, color zone correct
- **Rent Waterfall** (Slide 5, B1): bars at Base=$1,405, +Amenity=$125, =Predicted=$1,530, Asking=$1,525, Comps=$1,434. Bracket shows +$91
- **Trend Lines** (Slide 6, B1): 4 data points — occupancy 0.88→0.83→0.79→0.79, asking $1,600→$1,575→$1,540→$1,525, comps $1,475→$1,460→$1,445→$1,434
- **Vacancy Cost Bar** (Slide 7): B2=$9,924 (tallest), B1=$7,625, A2=$7,055, A1=$2,730. Total=$27,334
- **KPI Cards** (Slide 2): exact values for units, occupancy, vacancy cost, critical flags
- Chart tooltips show exact values (not rounded)
- Small bars (A1=$2,730) still visible despite large bars (B2=$9,924) — appropriate y-axis scaling

### Edge Cases
- B1 waterfall: Asking ($1,525) < Predicted ($1,530) creates a negative step. The chart must handle this correctly without rendering errors.

---

## Scenario 5.3: Property Switching

### Setup
Both properties have diagnostic runs available.

### Trigger
Viewing Property B slideshow → switch to Property A via header dropdown.

### Satisfaction Criteria
- Charts update to show A1/A2 data (not B1/B2)
- Score gauge changes (Property A score higher than B)
- Vacancy cost changes ($9,785 for A vs $17,549 for B)
- Narrative text updates to address Property A findings
- Switching back to B restores all B data correctly
- No stale/mixed data from wrong property visible
- If switched property has no diagnostic yet, shows dashboard with "Run Diagnostic" prompt

### Edge Cases
- Switching mid-slide resets to Slide 1 or maintains position (either OK, must not crash)
- Rapid switching (A→B→A) does not produce mixed data
