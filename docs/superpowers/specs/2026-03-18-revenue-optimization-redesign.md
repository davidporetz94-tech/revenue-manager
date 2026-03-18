# Revenue Optimization Redesign — Design Spec

## Problem

The system is 75% vacancy-focused, 25% rent-focused. It correctly panics about empty units but entirely ignores underpricing, renewal capture, concession drag, and the rent/occupancy tradeoff. The result: operators filling units at below-market rents, freezing renewals unnecessarily, and never testing higher prices. The system minimizes vacancy cost when it should maximize net effective revenue per available unit over time.

## Goal

Transform the Revenue Manager from a vacancy alarm into a true revenue optimizer. Every metric, flag, score, experiment, and recommendation evaluates its impact on total revenue — not just one side of the equation. Revenue = f(rent, occupancy, velocity, renewals, concessions, seasonality, time). The system finds the revenue-maximizing price point for each unit type and shows operators how to get there.

## Design Principles

1. **Revenue is the single lens.** Vacancy is a revenue problem (lost units). Underpricing is a revenue problem (lost dollars per unit). Same equation, same score, same urgency.
2. **Dynamic weighting.** When occupancy is in crisis, filling dominates. When occupancy is strong, pricing and renewals dominate. The system adjusts automatically.
3. **Honest about data limits.** We have 4 monthly snapshots and a pricing export, not a live PMS feed. The implied elasticity model acknowledges confidence levels and recommends experimentation when uncertain.
4. **Every recommendation has a dollar amount.** Never "consider raising rents." Always "raise A1 asking to $1,395, capturing $2,100/mo. Risk: 1 additional vacant unit (cost: $1,365/mo vacancy). Net: +$735/mo."
5. **Renewals are first-class.** Zero vacancy cost, zero make-ready cost, pure margin capture. The highest-ROI lever in most portfolios.

---

## 1. Revenue Optimization Engine

### New Module: `engine/revenue_optimizer.py`

Pure function — no DB access, consistent with engine isolation rule.

#### 1.1 Implied Elasticity Model

**Function:** `compute_implied_elasticity(snapshot_trends: list[dict], comp_trends: list[dict]) -> dict`

Uses the 4-month snapshot history to estimate price sensitivity per unit type. If asking rent changed by X% between months and occupancy changed by Y%, that gives a crude elasticity coefficient.

**Data availability:** The snapshot model (`historical_snapshots`) stores `avg_occupancy`, `avg_asking_rent`, `avg_comp_asking_rent`, and exposure fields per month. `avg_in_place_rent` exists in the schema but is currently NULL in seeded data — the elasticity model does NOT depend on it. It uses only asking rent and occupancy changes (both populated). In-place rent for LTL calculations uses current-month data from the `units` table (point-in-time, not trended).

**Inputs:**
- `snapshot_trends`: list of monthly snapshots per unit type (occupancy, asking, comps, exposure)
- `comp_trends`: comp rent observations over the same period

**Output per unit type:**
```python
{
    "elasticity_coefficient": float,  # estimated occ change per 1% price change
    "confidence": "LOW" | "MEDIUM" | "HIGH",  # based on data quality
    "data_points": int,  # number of observations used
    "direction": "ELASTIC" | "INELASTIC" | "UNKNOWN",
    "notes": str,  # e.g., "Only 4 data points; treat as directional"
}
```

**Confidence assignment:**
- HIGH: 4+ months of data with clear directional correlation between price and occupancy changes, corroborated by comp movement
- MEDIUM: 3-4 months of data with directional signal but noise, or limited comp corroboration
- LOW: <3 months, contradictory signals, or flat pricing history (no price variation to learn from)

When confidence is LOW, the system recommends experimentation before aggressive pricing moves.

#### 1.2 Revenue-Maximizing Price Estimate

**Function:** `compute_optimal_price(unit_type_metrics: dict, elasticity: dict, seasonal_context: dict) -> dict`

Finds the asking rent where `rent × expected_occupancy_at_rent` is maximized, using the implied elasticity coefficient.

**Method:**
1. Start from current asking rent
2. Using the elasticity coefficient, estimate occupancy at price points ±10% from current
3. Compute `revenue = price × estimated_occupied_units` at each point
4. The peak is the optimal price estimate
5. Apply seasonal adjustment (approaching peak = shift optimal up; off-peak = shift down)
6. Constrain: optimal price must be within ±15% of comps (regulatory/market reality check). If the unconstrained optimal exceeds the comp constraint, cap at the constraint boundary and set `"comp_constrained": true` in output.

**Output:**
```python
{
    "optimal_asking": float,
    "optimal_revenue_monthly": float,
    "current_revenue_monthly": float,
    "revenue_gap_monthly": float,
    "price_direction": "INCREASE" | "DECREASE" | "HOLD",
    "recommended_asking": float,  # conservative: halfway between current and optimal
    "confidence": "LOW" | "MEDIUM" | "HIGH",  # inherited from elasticity
    "seasonal_adjustment_applied": float,  # +/- dollars from season
    "comp_constrained": bool,              # True if optimal was capped by ±15% comp rule
}
```

The `recommended_asking` is intentionally conservative — halfway between current and optimal. The system recommends incremental moves, not jumps, especially when elasticity confidence is not HIGH.

#### 1.3 Revenue Gap Decomposition

**Function:** `decompose_revenue_gap(unit_type_metrics: dict, optimal: dict, renewal_analysis: dict) -> dict`

Breaks the total revenue gap into actionable components — each one maps to a specific lever the operator can pull.

**Output:**
```python
{
    "current_monthly_revenue": float,    # in_place × occupied
    "optimal_monthly_revenue": float,    # optimal_asking × expected_occ_at_optimal
    "total_gap_monthly": float,
    "gap_components": {
        "vacancy_cost": {
            "amount": float,             # vacant × asking / 30 × avg_days_to_fill
            "lever": "FILL",
            "description": "Revenue lost to empty units"
        },
        "new_lease_underpricing": {
            "amount": float,             # (optimal - asking) × expected_new_leases_30d
            "lever": "REPRICE",
            "description": "Revenue lost from asking below optimal on new leases"
        },
        "in_place_underpricing": {
            "amount": float,             # LTL × occupied (capturable only at renewal)
            "lever": "RENEW",
            "description": "Revenue gap in current leases, addressable at renewal"
        },
        "renewal_opportunity": {
            "amount": float,             # from renewal optimizer
            "lever": "RENEW",
            "description": "Capturable through upcoming renewal increases"
        },
        "concession_drag": {
            "amount": float,             # headline - effective across concession units
            "lever": "DE_CONCESSION",
            "description": "Revenue reduction from active concessions"
        },
    },
    "dominant_lever": str,               # which component is largest
    "lever_ranking": list[str],          # components ranked by size
}
```

This decomposition is the backbone of the redesigned system. It replaces "daily vacancy burn" as the single headline metric with a richer picture of WHERE revenue is being lost and WHICH lever captures the most.

#### 1.4 Revenue Efficiency Score

**Function:** `compute_revenue_efficiency(unit_type_metrics: dict, optimal: dict, snapshot_trends: list[dict]) -> dict`

The unified score that replaces the flag-count-based health score.

**Three dimensions (each 0-100):**

1. **Occupancy Health:** How close to target occupancy, adjusted for seasonal norms. Target is not always 95% — in off-peak November, 91% may be healthy. Uses seasonal factor from `engine/seasonal.py`.

2. **Pricing Alignment:** How close asking is to the revenue-maximizing price. Penalizes BOTH overpricing (asking >> optimal, causing vacancy) AND underpricing (asking << optimal, leaving money on table). Symmetric penalty.

3. **Rent Roll Momentum:** Are things moving in the right direction? Computed from 4-month trends: executed rent trend (up/flat/down), occupancy trend, LTL trend (narrowing = good). A unit type with declining executed rents and widening LTL has negative momentum regardless of current occupancy.

**Dynamic weighting by occupancy zone:**

Zone boundaries are configurable via `client_configs` JSONB field `revenue_efficiency_zones` (see Section 7). Defaults:

| Occupancy Zone | Occ Health Weight | Pricing Weight | Momentum Weight |
|---------------|-------------------|----------------|-----------------|
| Crisis (<82%) | 60% | 15% | 25% |
| Stressed (82-89%) | 45% | 30% | 25% |
| Balanced (89-94%) | 30% | 35% | 35% |
| Strong (94-97%) | 15% | 45% | 40% |
| Full (97%+) | 10% | 50% | 40% |

Seasonal adjustment: approaching peak season (March-May) shifts 5% from Occupancy Health to Pricing Alignment (you have leverage). Approaching off-peak (Sep-Nov) shifts 5% the other way (protect occupancy).

**Output:**
```python
{
    "revenue_efficiency_score": int,     # 0-100 unified score
    "grade": str,                        # OPTIMIZED|OPPORTUNITY|IMBALANCED|DISTRESSED|CRISIS
    "dimensions": {
        "occupancy_health": {"score": int, "weight": float},
        "pricing_alignment": {"score": int, "weight": float},
        "rent_roll_momentum": {"score": int, "weight": float},
    },
    "dynamic_weights_reason": str,       # e.g., "Strong occupancy (96%) — pricing dominates"
    "occupancy_zone": str,
}
```

**Grade mapping:**

| Score | Grade | Action Posture |
|-------|-------|---------------|
| 85-100 | OPTIMIZED | Hold — monitor for drift |
| 70-84 | OPPORTUNITY | Push — raise rents, capture renewals, reduce concessions |
| 55-69 | IMBALANCED | Rebalance — combination of fill + reprice |
| 40-54 | DISTRESSED | Fill first — vacancy is the dominant problem |
| 0-39 | CRISIS | Emergency — cut price, concede, fill immediately |

---

## 2. Renewal Optimizer

### New Module: `engine/renewal_optimizer.py`

Pure function. Computes renewal increase recommendations and revenue capture potential per unit type.

**Function:** `compute_renewal_opportunity(unit_type_metrics: dict, elasticity: dict, seasonal_context: dict, upcoming_renewals: int) -> dict`

**Renewal increase recommendation model:**

| Occupancy Zone | LTL Upside | Season | Recommended Increase |
|----------------|-----------|--------|---------------------|
| Strong (94%+) | >5% | Approaching peak | 4-6% |
| Strong (94%+) | >5% | Off-peak | 3-4% |
| Strong (94%+) | <5% | Any | 2-3% |
| Balanced (89-94%) | >5% | Peak | 3-4% |
| Balanced (89-94%) | Any | Off-peak | 1-3% |
| Stressed (<89%) | Any | Any | 0% (freeze) |

**Turnover cost model:**

```
Estimated turnover probability = min(max_turnover_cap, base_rate × (1 + increase_pct × sensitivity_factor))
  where base_rate ≈ 0.10 (industry 10% non-renewal at 0% increase)
  and sensitivity_factor ≈ 5.0 (each 1% increase adds ~5% turnover probability)
  and max_turnover_cap = 0.60 (configurable; prevents >100% at extreme values)

Turnover cost per unit = avg_vacancy_days × (asking / 30) + make_ready_estimate
  where make_ready_estimate = $2,500 (configurable in client_config)

Net renewal capture = (increase_dollars × renewals × 12) - (turnover_prob × turnover_cost × renewals)
```

**Output:**
```python
{
    "upcoming_renewals_90d": int,
    "recommended_increase_pct": float,
    "recommended_increase_dollars": float,
    "gross_annual_capture": float,
    "estimated_turnover_probability": float,
    "estimated_turnover_cost": float,
    "net_annual_capture": float,
    "net_monthly_capture": float,
    "confidence": "LOW" | "MEDIUM" | "HIGH",
}
```

### Data Source for Upcoming Renewals

The system derives upcoming renewal count from the unit dicts already passed to the engine. The `_units_to_dicts()` function in `metrics_engine.py` already includes `lease_end` and `status` fields. The renewal optimizer computes the count inside the engine function by filtering unit dicts where `status == 'occupied'` and `lease_end` is within 90 days of `reference_date`. No additional DB query needed — this is a pure function operating on data already available.

---

## 3. Rebalanced Flag Generator

### New Flags (6)

Added to `services/flag_generator.py`:

| Flag | Trigger Condition | Severity | Category |
|------|------------------|----------|----------|
| `RENT_PUSH_OPPORTUNITY` | occ ≥ 94% AND asking < optimal by >3% | HIGH | Revenue capture |
| `HIGH_LTL_CAPTURE` | LTL > 5% of in_place AND occ ≥ 88% | HIGH | Revenue capture |
| `RENEWAL_INCREASE_ELIGIBLE` | renewals in 90d > 0 AND occ ≥ 90% AND LTL > 0 | MEDIUM | Revenue capture |
| `UNDERPRICED_VS_COMPS` | asking < comps by >3% AND occ ≥ 90% | MEDIUM | Revenue capture |
| `CONCESSION_REMOVAL_ELIGIBLE` | active concessions AND occ ≥ 93% AND exposure < 10% | MEDIUM | Revenue capture |
| `ELASTICITY_WARNING` | implied elasticity is HIGH (price sensitive) AND confidence ≥ MEDIUM | INFO | Caution |

### Reclassified Existing Flags

| Flag | Current Severity | New Severity | Rationale |
|------|-----------------|-------------|-----------|
| `OCCUPANCY_PUSH_ELIGIBLE` | INFO | **HIGH** | This is a revenue opportunity, not trivia |
| `RENEWAL_FREEZE_RECOMMENDED` | Fires at occ < 88% | Fires at occ < 82% only | 88% is too aggressive — blocks rent growth when occupancy is merely soft |
| `CONCESSION_TRIGGER` | Always "offer concession" | Conditional: if occ ≥ 93%, becomes `CONCESSION_REMOVAL_ELIGIBLE` instead | High-occupancy properties should be removing concessions, not adding them |

### Flag Balance After Redesign

| Direction | Before | After |
|-----------|--------|-------|
| Push rent down / fill | 10 | 9 |
| Push rent up / capture | 1 | 7 |
| Investigation / neutral | 9 | 10 |
| Ratio (down:up) | 10:1 | ~1.3:1 |

### Updated Expected Flag Counts (Default Config)

After redesign, expected flags per unit type archetype:

- **A1 (HEALTHY/OPPORTUNITY):** OCCUPANCY_PUSH_ELIGIBLE (HIGH), RENT_PUSH_OPPORTUNITY (HIGH), HIGH_LTL_CAPTURE (HIGH), RENEWAL_INCREASE_ELIGIBLE (MEDIUM), DOM_ABOVE_THRESHOLD (MEDIUM), EXECUTED_BELOW_ASKING (LOW) — **6 flags, 3 revenue-capture**
- **A2 (OVERPRICING/IMBALANCED):** OCCUPANCY_BELOW_ACTION (HIGH), EXPOSURE_ACTION_NEEDED (HIGH), HIGH_REVENUE_AT_RISK (HIGH), CONCESSION_TRIGGER (HIGH), DOM_ABOVE_THRESHOLD (MEDIUM), MAB_ELIGIBLE (INFO) — **6 flags, vacancy-dominant (correct — A2 needs to fill)**
- **B1 (CRISIS):** OCCUPANCY_CRISIS (CRITICAL), EXPOSURE_CRISIS (CRITICAL), ABOVE_COMP_PREMIUM_THRESHOLD (HIGH), NEGATIVE_LTL (HIGH), EXECUTED_SIGNIFICANTLY_ABOVE_ASKING (HIGH), HIGH_REVENUE_AT_RISK (HIGH), EXPOSURE_DETERIORATING (HIGH), DOM_ABOVE_THRESHOLD (MEDIUM), AMENITY_AUDIT_RECOMMENDED (MEDIUM), MAB_ELIGIBLE (INFO) — **10 flags, all vacancy/crisis (correct — B1 must fill first)**
- **B2 (PUZZLE/IMBALANCED):** CONCESSION_TRIGGER (HIGH), HIGH_REVENUE_AT_RISK (HIGH), OCCUPANCY_BELOW_CONCERN (MEDIUM), EXPOSURE_CAUTION (MEDIUM), ASKING_ABOVE_PREDICTED_THRESHOLD (MEDIUM), DOM_ABOVE_THRESHOLD (MEDIUM), MAB_ELIGIBLE (INFO) — **7 flags, mixed (correct — B2 at 88% occ does not meet the 90% gate for RENEWAL_INCREASE_ELIGIBLE)**

The flag mix now naturally leads Claude to balanced recommendations: A1 gets "push rents" urgency, B1 gets "fill now" urgency, A2 and B2 get nuanced "rebalance" recommendations.

---

## 4. Bidirectional Experiments

### Direction Logic

Added to `services/action_plan_service.py`:

```
If asking > optimal price AND gap > 3%:
  → Test DOWN toward optimal

If asking < optimal price AND gap > 3% AND occ ≥ 92%:
  → Test UP toward optimal

If asking ≈ optimal (within 3%):
  → No experiment — hold and monitor

If occ < 82% (crisis):
  → Skip experiment, direct action down (unchanged)
```

### Upward Experiment Design

When testing higher prices:
- Control arm: current asking
- Test arm: halfway between current and optimal (conservative first move)
- Max upward spread: 5% or $75, whichever is tighter (more conservative than downward max of 6%/$100)
- Minimum occupancy gate: 92% (don't test up when filling is still a priority)
- Early termination: if test arm unit sits >21 days without application, revert to control price

### Convergence Rule Change

**Current:** "Which arm leases faster?" (velocity only)

**New:** "Which arm generates more revenue per unit per day?"

```
Revenue per unit per day = monthly_rent / (vacancy_days + 1)
```

This naturally balances rent level against velocity. A higher-priced unit that takes slightly longer to lease can still win if the rent premium outweighs the extra vacancy days.

**Practical significance threshold:** 15%+ revenue-per-day difference (not 5-day velocity difference). This is more conservative and prevents premature convergence on noisy data.

### Experiment Output Schema Update

The experiment design JSON adds:
```python
{
    "direction": "UP" | "DOWN",
    "convergence_metric": "revenue_per_unit_per_day",  # was: "days_to_lease"
    "revenue_per_day_control_estimate": float,
    "revenue_per_day_test_estimate": float,
    "early_termination_days": int,  # for upward tests: 21 days no application → revert
}
```

---

## 5. Claude Prompt Redesign

### DIAGNOSIS_SYSTEM_PROMPT

Replace the flag-count scoring rubric with a revenue-efficiency rubric. Claude receives the pre-computed revenue efficiency scores, revenue gap decomposition, and implied elasticity data.

**Key changes:**

1. Scoring guidance uses the composite Revenue Efficiency Score (0-100, from Section 1.4), not flag counts. Claude receives the pre-computed score and grade — it does not recompute them:
   - CRISIS (score 0-39): Dominant vacancy component, occupancy in freefall
   - DISTRESSED (score 40-54): Mixed vacancy + pricing problems
   - IMBALANCED (score 55-69): One dimension dragging (usually pricing or momentum)
   - OPPORTUNITY (score 70-84): Healthy occupancy, meaningful pricing or renewal upside
   - OPTIMIZED (score 85-100): Near the revenue frontier, monitor for drift

2. Claude must identify the DOMINANT revenue lever per unit type (fill, reprice, renew, de-concession)

3. Claude must acknowledge elasticity confidence — if LOW, recommend experimentation before aggressive action

4. Claude must quantify every recommendation in dollars using the pre-computed gap components

5. Cross-unit-type analysis: does repricing A1 up risk cannibalizing A2 demand?

### ACTION_PLAN_SYSTEM_PROMPT

Replace "stabilization" framing with revenue optimization framing. Phase structure adapts to the dominant problem:

- **CRISIS/DISTRESSED:** Phase 1 = fill (cut price, concede). Phases 2-4 = optimize once stabilized.
- **IMBALANCED:** Phase 1 = quick wins (reprice obvious misalignment). Phases 2-4 = experiment + renewals.
- **OPPORTUNITY:** Phase 1 = implement renewal increases + remove concessions. Phase 2 = test higher asking. Phases 3-4 = lock gains.
- **OPTIMIZED:** Phase 1 = hold. Phases 2-4 = seasonal positioning for next quarter.

Every action must include:
- Which lever it pulls (fill, reprice, renew, de-concession)
- Dollar impact per month (from pre-computed gap decomposition)
- Confidence level (from elasticity model)
- Downside risk quantified (e.g., "if 4% renewal increase causes 1 turnover, net impact is still +$5,704/year")

### Action Taxonomy Update

**New actions:**
- `INCREASE_ASKING_RENT` — for units where asking < optimal AND occ ≥ 92%
- `IMPLEMENT_RENEWAL_INCREASE` — with specific % and dollar capture
- `REMOVE_CONCESSION` — when occupancy supports it
- `TEST_HIGHER_ASKING` — upward experiment for high-occ units
- `TEST_TERM_PREMIUM` — test longer lease term at current asking vs shorter term at lower

**Modified actions:**
- `LAUNCH_PRICE_EXPERIMENT` — now bidirectional (specify direction: UP or DOWN)
- `FREEZE_RENEWAL_INCREASES` — only triggers below 82% (was 88%)

### Fallback Behavior

When Claude is unavailable, the fallback uses the revenue gap decomposition directly:
1. Rank unit types by revenue gap (largest first)
2. For each, recommend the dominant lever action with dollar amounts
3. Phase assignment based on grade: CRISIS → Phase 1, OPPORTUNITY → Phase 2, etc.

The fallback is significantly more useful than the current flag-counting version because the engine does all the hard math. Claude adds nuance and cross-unit-type reasoning; the fallback still produces actionable, quantified recommendations.

---

## 6. Slide Deck Restructure

### Principle

Same slide count (12 property / 15 portfolio). Every vacancy-only slide becomes a unified revenue slide showing both sides of the equation. The headline shifts from "how much are we losing to vacancy?" to "how much more revenue can we capture and how?"

### Per-Property Slides (12)

| # | Type | Title | Content Changes |
|---|------|-------|-----------------|
| 1 | `TITLE` | [Property] Revenue Analysis — [Date] | Minor: "Revenue Analysis" replaces "Pricing Diagnostic" |
| 2 | `EXECUTIVE_SUMMARY` | Executive Summary | **Major.** Score gauge shows Revenue Efficiency with dynamic weight breakdown visible. 6 KPI cards: Revenue Efficiency %, Revenue Gap $/mo, Occupancy %, Blended Rent vs Optimal, Vacancy Cost $/mo, Renewal Opportunity $/yr. Headline is the gap. |
| 3 | `REVENUE_POSITION` | Revenue Position | **Major.** Data table adds: optimal asking, revenue gap per unit type, elasticity confidence indicator. Color coding: red = large revenue gap (from any cause), not just low occupancy. |
| 4-5 | `REVENUE_DEEP_DIVE` | [Unit Type] Revenue Analysis | **Major.** Waterfall becomes: Base → Amenity → Predicted → Optimal → Asking → Comps → In-Place. Score cards show 3-dimension breakdown (occ/pricing/momentum) with dynamic weights. |
| 6 | `REVENUE_TRENDS` | Revenue Trend Analysis | **Moderate.** Add optimal price trend line alongside asking, comps, and occupancy. Divergence between asking and optimal is visually obvious. |
| 7 | `REVENUE_ANALYSIS` | Revenue Analysis | **Major.** Replace vacancy-only stacked bar with revenue gap waterfall: Current Revenue → +Fill Vacant → +Reprice New Leases → +Capture Renewals → −Concession Drag → Optimal Revenue. Each segment is a lever. |
| 8 | `ACTION_PLAN_OVERVIEW` | 30-Day Revenue Plan | **Moderate.** Actions ranked by revenue impact ($/mo captured), not just urgency. Shows total projected capture across all actions. |
| 9 | `PHASE_DETAIL` | Phase 1: [Adaptive Title] | **Moderate.** Experiment cards show direction (UP/DOWN) and revenue-per-day metric. Phase title adapts: "Immediate Stabilization" for crisis, "Revenue Capture" for opportunity. |
| 10 | `DECISION_TREE` | Decision Points | **Moderate.** Branch conditions use revenue impact: "If test arm revenue-per-day > control by 15%+, lock price across unit type." |
| 11 | `INVESTIGATION` | Investigation & Confidence | **Minor.** Add elasticity confidence row. If LOW confidence, recommend data gathering before aggressive moves. |
| 12 | `REVENUE_ROADMAP` | Revenue Roadmap | **Major.** Before/after with full revenue decomposition: "Fill 3 units: +$4,500/mo. Reprice A1: +$2,100/mo. Renewals: +$6,091/yr. Remove concessions: +$800/mo. Total projected capture: $13,491/mo." |

### Portfolio Slides

Same restructuring principle applied to portfolio-level slides:
- Portfolio executive summary shows aggregate revenue efficiency and revenue gap
- Property ranking by revenue efficiency (not vacancy burn)
- Portfolio revenue gap waterfall shows which properties contribute most to the gap
- Property deep dives show per-property revenue gap decomposition

### Viz Data Changes

**Modified generators** (in `viz_data_service.py`):

| Generator | Changes |
|-----------|---------|
| `generate_score_gauge()` | Revenue efficiency gauge with zone labels (CRISIS through OPTIMIZED). Shows dynamic weight breakdown. |
| `generate_kpi_cards()` | 6 cards instead of 4. Add Revenue Gap and Renewal Opportunity. |
| `generate_data_table()` | Add columns: optimal asking, revenue gap, elasticity confidence. Color by gap magnitude. |
| `generate_rent_waterfall()` | Add Optimal bar between Predicted and Asking. |
| `generate_line_charts()` | Add optimal price trend line. |

**New generators:**

| Generator | Slide | Output |
|-----------|-------|--------|
| `generate_revenue_gap_waterfall()` | 7 | Waterfall chart: Current → +Fill → +Reprice → +Renew → −Concessions → Optimal |
| `generate_revenue_roadmap()` | 12 | Before/after bars with per-lever dollar amounts |
| `generate_dimension_breakdown()` | 4-5 | Horizontal stacked bar showing occ/pricing/momentum weights and scores |

**Removed generators:**
- `generate_stacked_bar()` — replaced by revenue gap waterfall. This is a coordinated change: the backend viz_data, `slide_deck_service.py` (which calls it on slide 7), and the frontend `VacancyCostBar` chart component must all change together. The old generator is removed, not deprecated — there is no transition period.

### Portfolio Viz Data Changes

Same pattern as per-property. `portfolio_viz_data_service.py` adds:
- `generate_portfolio_revenue_gap_waterfall()` — aggregate gap across properties
- `generate_portfolio_efficiency_ranking()` — properties ranked by revenue efficiency
- Existing generators updated to show revenue metrics alongside vacancy metrics

---

## 7. Data Model Changes

### No Schema Migration Required

All new computations are derived from existing data. The revenue optimizer, renewal optimizer, and elasticity model are pure functions operating on data already in `metrics_json`, `flags_json`, and `diagnosis_json`.

The `metrics_json` stored in `diagnostic_runs` will now contain richer content (revenue gap decomposition, elasticity data, renewal analysis), but this is a JSON column — no migration needed.

### Client Config Extensions

Add new configurable thresholds to `client_configs` JSONB fields:

In `pricing_tolerance`:
```python
{
    # existing
    "asking_above_predicted_pct": 0.04,
    "comp_premium_pct": 0.05,
    # new
    "rent_push_gap_pct": 0.03,       # min gap between asking and optimal to trigger RENT_PUSH_OPPORTUNITY
    "underpriced_vs_comps_pct": 0.03, # min gap below comps to trigger UNDERPRICED_VS_COMPS
    "max_upward_experiment_spread_pct": 0.05,  # max upward test spread (more conservative than downward 0.06)
}
```

In `renewal_policy`:
```python
{
    # existing
    "freeze_below_occupancy": 0.82,  # was 0.88
    # new
    "make_ready_cost_estimate": 2500,  # used in renewal turnover cost model
    "base_non_renewal_rate": 0.10,     # industry baseline 10%
    "increase_sensitivity_factor": 5.0, # each 1% increase adds ~5% turnover probability
}
```

In `concession_policy`:
```python
{
    # existing fields
    # new
    "removal_occupancy_threshold": 0.93,  # occ above this → flag CONCESSION_REMOVAL_ELIGIBLE
    "removal_exposure_threshold": 0.10,   # exposure below this → safe to remove concessions
}
```

New JSONB field `revenue_efficiency_zones` (top-level config section):
```python
{
    "crisis_below": 0.82,
    "stressed_below": 0.89,
    "balanced_below": 0.94,
    "strong_below": 0.97,
    # Full = anything ≥ strong_below
    "crisis_weights": [0.60, 0.15, 0.25],     # [occ, pricing, momentum]
    "stressed_weights": [0.45, 0.30, 0.25],
    "balanced_weights": [0.30, 0.35, 0.35],
    "strong_weights": [0.15, 0.45, 0.40],
    "full_weights": [0.10, 0.50, 0.40],
    "seasonal_weight_shift": 0.05,             # % shifted between occ↔pricing by season
    "max_turnover_probability": 0.60,          # cap for renewal turnover model
}
```

All zone boundaries and weights referenced in the engine functions (Sections 1.4, 2, 4) are read from this config with the defaults above. No hardcoded thresholds in engine code.

These are JSONB fields — no migration required. New keys are added with sensible defaults. Existing configs without these keys use the defaults.

---

## 8. Metrics Engine Integration

### Changes to `services/metrics_engine.py`

**Prerequisite:** `_units_to_dicts()` must be extended to include `concession_active`, `concession_type`, and `concession_value_monthly` fields from the Unit model. These are currently omitted but needed for the `concession_drag` component of the revenue gap and the `CONCESSION_REMOVAL_ELIGIBLE` flag.

`compute_property_metrics()` is extended to call the new engine functions and include their output in the metrics dict:

After computing existing metrics per unit type:
1. Call `compute_implied_elasticity()` with snapshot trends
2. Call `compute_optimal_price()` with unit type metrics + elasticity
3. Call `compute_renewal_opportunity()` with unit type metrics + elasticity + upcoming renewal count
4. Call `decompose_revenue_gap()` with all the above
5. Call `compute_revenue_efficiency()` for the unified score

The unit type metrics dict gains new sections:
```python
{
    # existing sections (unchanged)
    "occupancy_metrics": {...},
    "exposure_metrics": {...},
    "velocity_metrics": {...},
    "pricing_spreads": {...},
    "revenue_metrics": {...},
    "demand_metrics": {...},
    "lease_term_metrics": {...},
    "trend_metrics": {...},
    "seasonal_context": {...},
    "ltl_analysis": {...},

    # new sections
    "elasticity": {...},             # from compute_implied_elasticity
    "optimal_pricing": {...},        # from compute_optimal_price
    "renewal_opportunity": {...},    # from compute_renewal_opportunity
    "revenue_gap": {...},            # from decompose_revenue_gap
    "revenue_efficiency": {...},     # from compute_revenue_efficiency
}
```

### Changes to `services/flag_generator.py`

`generate_flags()` receives the enriched metrics dict and evaluates 6 new flag rules in addition to the existing 20 (with 3 reclassifications).

### Changes to `engine/aggregator.py`

`compute_portfolio_metrics()` and `aggregate_cross_property()` aggregate the new revenue metrics:
- Portfolio-level revenue gap (sum of all unit type gaps)
- Portfolio revenue efficiency: computed as `sum(current_revenue_all_ut) / sum(optimal_revenue_all_ut) × 100` — this is the aggregate ratio, not a weighted average of per-unit-type scores. The aggregate ratio is more accurate because it accounts for unit count and rent level differences.
- Portfolio renewal opportunity (sum across unit types)
- Portfolio optimal revenue (sum of per-unit-type optimal)

---

## 9. Service Layer Changes

### `services/diagnostic_service.py`

- Updated Claude prompts (diagnosis + action plan) as described in Section 5
- Fallback diagnosis uses revenue efficiency score and gap decomposition instead of flag counts
- Fallback action plan ranks actions by revenue gap component size

### `services/action_plan_service.py`

- Bidirectional experiment design (Section 4)
- Revenue-per-day convergence metric
- Upward experiment guardrails (92% occ gate, 5%/$75 max spread, 21-day revert)
- Renewal increase actions with dollar amounts and turnover risk

### `services/slide_deck_service.py`

- Restructured slide assembly (Section 6)
- Revenue gap waterfall data passed to slides
- Dynamic weight breakdown passed to score gauge
- Adaptive phase titles based on grade

### `services/viz_data_service.py`

- Modified generators for revenue-aware content
- New generators for revenue gap waterfall, revenue roadmap, dimension breakdown

### `services/narrative_service.py`

- Updated narrative prompts to reference revenue efficiency, gap decomposition, and lever recommendations
- Fallback narratives use gap components to generate specific dollar-amount text

### Portfolio Services

`portfolio_diagnostic_service.py`, `portfolio_viz_data_service.py`, `portfolio_narrative_service.py`, `portfolio_slide_deck_service.py` — all receive the same restructuring pattern as their per-property counterparts.

---

## 10. Frontend Changes

### Slide Components

**Modified components:**
- `ExecutiveSummarySlide.jsx` — render 6 KPI cards, revenue efficiency gauge with dimension breakdown
- `DataTableSlide.jsx` (was PortfolioSnapshotSlide) — add optimal asking, revenue gap, elasticity columns
- `PropertyDeepDiveSlide.jsx` — updated waterfall (add Optimal bar), 3-dimension score cards
- `TrendAnalysisSlide.jsx` — add optimal price trend line
- `SummarySlide.jsx` — becomes Revenue Roadmap with per-lever before/after

**New components:**
- `RevenueGapWaterfallChart.jsx` — horizontal waterfall showing gap decomposition by lever
- `DimensionBreakdownChart.jsx` — horizontal stacked bar showing occ/pricing/momentum scores and weights
- `RevenueTrendLine.jsx` — line chart overlay for optimal price alongside existing trend lines

**Modified components (charts):**
- `ScoreGauge.jsx` — new zone labels (CRISIS through OPTIMIZED), show dynamic weight info
- `RentWaterfall.jsx` — add Optimal bar with distinct color
- `BeforeAfter.jsx` — show revenue decomposition, not just occupancy before/after

### SlideshowViewer

Updated slide type mappings for renamed slide types. No structural change to the viewer itself.

---

## What Stays Unchanged

- Database schema (no migrations — all new data lives in existing JSONB columns)
- Auth system
- Comp management endpoints
- API endpoint structure (same routes, richer response data)
- Engine isolation rule (all new modules are pure functions)
- Regulatory compliance rules (public data only, audit logging, org isolation)
- Frontend shell, routing, auth flow

---

## Testing Strategy

### New Test File: `tests/test_revenue_optimizer.py`

- Implied elasticity computation with known snapshot data
- Optimal price calculation for each archetype (A1, A2, B1, B2)
- Revenue gap decomposition correctness (components sum to total)
- Revenue efficiency score with dynamic weighting
- Edge cases: flat pricing history (LOW confidence), single data point, zero vacancy

### New Test File: `tests/test_renewal_optimizer.py`

- Renewal increase recommendations per occupancy zone
- Turnover cost model
- Net capture calculation
- Edge cases: no upcoming renewals, 100% occupancy, crisis occupancy

### Modified Tests: `tests/test_flag_generator.py`

- Updated expected flag counts for all 4 archetypes
- New flag trigger conditions verified
- Reclassified flag behavior (PUSH_ELIGIBLE → HIGH, FREEZE → 82% threshold)

### Modified Tests: `tests/test_metrics_engine.py`

- Verify new sections present in metrics output
- Revenue gap decomposition included per unit type

### Modified Tests: `tests/test_diagnostic_service.py`

- Updated scoring expectations (revenue efficiency, not flag counts)
- Fallback uses revenue gap decomposition

### New/Modified Tests: `tests/test_action_plan.py`

- Bidirectional experiment direction logic (UP when asking < optimal AND occ ≥ 92%, DOWN otherwise)
- Upward experiment design: max spread 5%/$75, occupancy gate at 92%
- Early termination condition for upward tests (21 days, no application)
- Revenue-per-day convergence metric calculation
- Practical significance threshold at 15%
- Edge cases: asking ≈ optimal (within 3%, no experiment), crisis occupancy (skip experiment)

### Seasonal Weight Adjustment Tests

In `test_revenue_optimizer.py`, include at least two seasonal contexts (e.g., March spring ramp and November off-peak) to verify the 5% weight shift works bidirectionally.

### Portfolio Aggregation Tests

In `test_portfolio_diagnostic.py`, verify that the portfolio-level revenue gap is the sum of per-unit-type gaps, and portfolio revenue efficiency is weighted by unit count.

### Backward Compatibility

Existing stored diagnostic runs have the old `metrics_json` schema (no `elasticity`, `optimal_pricing`, `revenue_gap`, `revenue_efficiency` sections). The frontend and slide deck services must handle their absence gracefully — check for key existence before accessing new sections. Add a test that verifies slide assembly works with a metrics dict missing the new sections (returns degraded but functional output).

### Existing Tests Must Continue Passing

- Reconciliation tests (71 assertions) — unchanged, data integrity
- All existing engine tests — pure functions, inputs/outputs don't change
- Portfolio diagnostic tests — updated for new metrics structure
