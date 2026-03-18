# Portfolio-Wide Diagnostic & Slideshow — Design Spec

## Purpose

Add a portfolio-level pricing diagnostic that aggregates all properties in the organization, runs a Claude-powered analysis, and presents results as a superset slideshow (~15 slides). The per-property diagnostic remains unchanged.

## User Flow

1. User is on PortfolioDashboard, sees the hero KPI bar (daily burn, blended occ)
2. Clicks "Run Portfolio Diagnosis" button in the hero bar
3. Button shows loading state with progress stepper (same pattern as per-property)
4. When complete, slideshow opens automatically
5. Slideshow starts with portfolio-level overview, then drills into each property

## Backend

### New Endpoint

`POST /diagnostic/portfolio/run`

- Requires JWT auth (uses `get_current_user`)
- Fetches all properties for the user's organization
- For each property with an active config: calls `compute_property_metrics()` + `generate_flags()`
- Properties without an active config are skipped with a warning logged; if zero properties have configs, return 400
- Aggregates into a portfolio-level metrics dict via new `aggregate_cross_property()` (in `app/engine/aggregator.py`)
- Sends to Claude with `PORTFOLIO_DIAGNOSIS_SYSTEM_PROMPT`
- Sends to Claude with `PORTFOLIO_ACTION_PLAN_SYSTEM_PROMPT`
- Narrative calls (2) can run in parallel since they depend only on completed diagnosis/action plan, not each other
- Stores result as `DiagnosticRun` with `property_id = NULL`, `scope = "portfolio"`, `organization_id` set from user
- Returns the run record (same polling pattern as per-property)

`GET /diagnostic/{run_id}` and `GET /diagnostic/{run_id}/slides` work unchanged — they already look up by run_id, not property_id. Both need minor updates (see Existing Endpoint Updates below).

### Portfolio Metrics Aggregation

New function: `aggregate_cross_property(all_property_metrics: list[dict]) -> dict`

Location: `backend/app/engine/aggregator.py` — this is pure computation on dicts with no DB access, consistent with the engine purity rule. Distinct from the existing `compute_portfolio_metrics()` which aggregates unit types within a single property.

Takes a list of per-property metrics dicts (output of `compute_property_metrics()`), returns:

```python
{
    "properties": {
        "PROP-A": { "name": "Property A", "unit_type_metrics": {...}, "portfolio_metrics": {...} },
        "PROP-B": { "name": "Property B", "unit_type_metrics": {...}, "portfolio_metrics": {...} },
    },
    "aggregate": {
        "total_units": int,
        "total_occupied": int,
        "total_vacant": int,
        "blended_occupancy": float,
        "total_daily_burn": float,
        "total_monthly_cost": float,
        "total_revenue_at_risk_30d": float,
        "property_count": int,
        "worst_property": str,   # by daily burn
        "best_property": str,    # by occupancy
    },
    "all_flags": {
        "PROP-A": { "A1": [...], "A2": [...] },
        "PROP-B": { "B1": [...], "B2": [...] },
    },
}
```

### Claude Prompts

New prompts in `backend/app/services/portfolio_diagnostic_service.py`:

**PORTFOLIO_DIAGNOSIS_SYSTEM_PROMPT** — similar to per-property but:
- Scores at portfolio level (0-100) AND per-property
- Ranks properties by urgency
- Identifies cross-property patterns (e.g., "both properties have DOM above threshold")
- Uses the same scoring rubric adapted for portfolio context
- Output schema uses `cross_property_assessment` (not `portfolio_assessment`, which is already used in per-property context to mean "across unit types within one property")

**PORTFOLIO_ACTION_PLAN_SYSTEM_PROMPT** — same 4-phase structure but:
- Actions prioritized across properties (not just within one)
- Phase 1 actions ranked by daily burn impact across entire portfolio
- Decision points reference specific properties

### Fallback

Same pattern as per-property: if Claude fails, `_fallback_portfolio_diagnosis()` generates structured diagnosis from flag counts and metrics. `_fallback_portfolio_action_plan()` generates empty-action phases with revenue facts.

### DiagnosticRun Model Changes

Three changes via one Alembic migration:

1. **Add `organization_id`** (UUID, FK to organizations, nullable initially). Backfill from `property.organization_id` for existing rows, then make NOT NULL. Required so portfolio runs (where `property_id` is NULL) can be filtered by organization — enforcing the data isolation rule.

2. **Make `property_id` nullable.** Portfolio runs have `property_id = NULL`.

3. **Add `scope` column** (VARCHAR(20), NOT NULL, default `"property"`). Constrained via `CheckConstraint("scope IN ('property', 'portfolio')")`. Existing rows get `"property"` via server_default.

The `config_id` column is set to NULL for portfolio runs (since multiple configs are involved). Per-property config IDs are included in the `metrics_json` for traceability.

**Migration reversibility:** Downgrade drops `scope` and `organization_id` columns and restores `property_id` NOT NULL. If any portfolio runs exist (property_id IS NULL), the downgrade deletes them first with a warning log.

### Existing Endpoint Updates

**`GET /diagnostic/{run_id}`** — The Pydantic `DiagnosticRunResponse` schema must change `property_id` from `str` to `str | None`. The endpoint's `str(run.property_id)` call must guard against None.

**`GET /diagnostic/{run_id}/slides`** — When `run.scope == "portfolio"`, call `assemble_portfolio_slide_deck()` instead of `assemble_slide_deck()`. Pass organization name (or "Portfolio Overview") as the title instead of property name.

**`GET /properties/{id}/diagnostic/history`** — Add explicit filter `.filter(DiagnosticRun.scope == "property")` for clarity, even though `property_id` filtering already excludes portfolio runs.

### New History Endpoint

`GET /diagnostic/portfolio/history` — returns diagnostic runs where `scope = "portfolio"` AND `organization_id = user.organization_id`. Used by the frontend to check if a portfolio diagnosis has been run before.

### Audit Logging

Portfolio diagnostic runs log to `audit_log` with:
- `action = "RUN_PORTFOLIO_DIAGNOSTIC"`
- `entity_type = "diagnostic_run"`
- `details` includes `{"scope": "portfolio", "property_ids": ["...", "..."], "properties_skipped": [...]}`

## Slide Deck

### Portfolio Slide Deck Service

New file: `backend/app/services/portfolio_slide_deck_service.py`

Assembles slides from portfolio-level diagnosis + metrics. Reuses existing viz generators where possible, adds new portfolio-specific generators.

### Slide Structure (~15 slides for 2 properties)

| # | Type | Title | Viz Data Source |
|---|------|-------|-----------------|
| 1 | `portfolio_title` | Portfolio Pricing Analysis — March 2026 | Static |
| 2 | `portfolio_executive_summary` | Executive Summary | Portfolio score gauge + aggregate KPI cards |
| 3 | `portfolio_snapshot` | Portfolio Snapshot | Property comparison table (occ, burn, exposure per property) |
| 4 | `property_ranking` | Property Health Ranking | Ranked cards with scores + key flags |
| 5 | `portfolio_trends` | Portfolio Trends | Blended occ + rent trend lines (all unit types overlaid) |
| 6 | `portfolio_revenue_at_risk` | Revenue at Risk | Stacked bar by property + total daily burn counter |
| 7 | `property_deep_dive` | Property A Deep Dive | Rent waterfalls for A1, A2 (reuse existing viz) |
| 8 | `property_deep_dive` | Property A Trends | Trend lines for A1, A2 (reuse existing viz) |
| 9 | `property_deep_dive` | Property B Deep Dive | Rent waterfalls for B1, B2 |
| 10 | `property_deep_dive` | Property B Trends | Trend lines for B1, B2 |
| 11 | `portfolio_action_plan` | 30-Day Action Plan | Timeline with actions ranked across properties |
| 12 | `portfolio_phase_detail` | Phase 1: Immediate Actions | Action cards with property labels |
| 13 | `portfolio_decision_point` | Day 15 Decision Points | Decision flowchart spanning properties |
| 14 | `portfolio_investigation` | Further Investigation | Investigation table with property column |
| 15 | `portfolio_summary` | Summary & Next Steps | Before/after with portfolio totals |

For N properties, slides 7–10 scale: 2 slides per property. With 2 properties = 15 slides, 3 = 17.

**Upper bound:** Cap at 10 properties (25 slides max). For orgs with >10 properties, include the top 10 by daily burn in the deep dives and note the others in the summary. This is acceptable for the current scope.

### Portfolio Viz Data

New file: `backend/app/services/portfolio_viz_data_service.py`

All generators take the portfolio aggregate metrics dict as input — no hardcoded data. Every value derives from the metrics passed in.

New generators (deterministic, never Claude):
- `generate_portfolio_score_gauge()` — portfolio-level health score
- `generate_portfolio_kpi_cards()` — aggregate KPIs
- `generate_property_comparison_table()` — side-by-side property metrics
- `generate_property_ranking_cards()` — sorted by health score
- `generate_portfolio_trend_lines()` — blended occupancy + rent across all unit types
- `generate_portfolio_stacked_bar()` — revenue at risk stacked by property

Reused from existing viz_data_service (per-property deep dives):
- `generate_rent_waterfall()` — per unit type
- `generate_line_charts()` — per unit type trends

### Portfolio Narrative

New file: `backend/app/services/portfolio_narrative_service.py`

Two Claude calls (same pattern as per-property):
1. Portfolio diagnostic narrative (slides 2-6, 14-15)
2. Portfolio action plan narrative (slides 11-13)

Fallback generates template-based narratives from aggregate metrics with consulting tone (direct address, specific numbers, no hedging).

## Frontend

### PortfolioDashboard Changes

Add "Run Portfolio Diagnosis" button to the hero KPI bar. Three states:
1. **Not run yet** — green accent button with "Run Portfolio Diagnosis ~20s"
2. **Running** — disabled with spinner and status text
3. **Complete** — opens slideshow automatically

Error handling:
- If the diagnostic fails, show error toast with "Retry" button, reset to state 1
- If user navigates away during run, polling continues in background; result is available when they return
- "View Last Portfolio Report" link shown if a previous portfolio run exists (checked via `/diagnostic/portfolio/history` on mount)

State management:
- `portfolioDiagLoading`, `portfolioDiagResult`, `portfolioSlideDeck` state in PortfolioDashboard
- On completion, calls `getSlides(runId)` and opens SlideshowViewer
- Slideshow receives `isPortfolio={true}` prop so the viewer can show "Portfolio" in the title bar

### API Client Additions

```javascript
export async function runPortfolioDiagnostic() { ... }
export async function getPortfolioDiagnosticHistory() { ... }
```

### New Slide Components

New frontend slides for portfolio-specific types:
- `PortfolioTitleSlide.jsx` — portfolio branding
- `PropertyComparisonSlide.jsx` — side-by-side property table
- `PropertyRankingSlide.jsx` — ranked health cards
- `PortfolioTrendSlide.jsx` — blended trend lines

Reused components:
- `ExecutiveSummarySlide` — works with portfolio score gauge
- `PropertyDeepDiveSlide` — already handles unit type waterfalls
- `TrendAnalysisSlide` — already handles per-unit-type trends
- `RevenueAtRiskSlide` — works with portfolio stacked bar
- `ActionPlanOverviewSlide`, `PhaseDetailSlide`, `DecisionTreeSlide` — work as-is
- `SummarySlide` — works with portfolio before/after

### SlideshowViewer Changes

Add new slide type mappings for portfolio-specific slides. The viewer is already type-driven (`slide.slide_type` → component), so this is additive.

## What Stays Unchanged

- Per-property diagnostic pipeline (endpoint, prompts, slide deck)
- Engine modules (pure functions, no DB access)
- Per-property slideshow (accessed from PricingReview)
- Existing test suites (203 tests)
- Auth, config, comps, experiments endpoints

## Testing

- New test file: `tests/test_portfolio_diagnostic.py`
  - `aggregate_cross_property()` correctness (totals, blended occ, worst/best)
  - Portfolio diagnosis fallback structure
  - Portfolio slide deck assembly (correct slide count for N properties)
  - DiagnosticRun with nullable property_id and scope column
  - Skipping properties without active config
  - Organization isolation (portfolio history filtered by org)
- Existing tests must continue passing (no regressions)

## Migration

One Alembic migration (reversible):

**Upgrade:**
1. Add `organization_id UUID REFERENCES organizations(id)` (nullable)
2. Backfill `organization_id` from `properties.organization_id` for existing rows
3. Make `organization_id` NOT NULL
4. Add `scope VARCHAR(20) NOT NULL DEFAULT 'property'` with `CHECK (scope IN ('property', 'portfolio'))`
5. Make `property_id` nullable
6. Add index on `(organization_id, scope, run_date DESC)` for portfolio history query

**Downgrade:**
1. Delete any rows where `scope = 'portfolio'` (these have NULL property_id)
2. Make `property_id` NOT NULL
3. Drop `scope` column
4. Drop `organization_id` column
