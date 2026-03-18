# Revenue Optimization Redesign — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Revenue Manager from a vacancy-focused system into a true revenue optimizer that maximizes net effective revenue per available unit over time, balancing occupancy, pricing, renewals, and concessions.

**Architecture:** Two new pure-function engine modules (`revenue_optimizer.py`, `renewal_optimizer.py`) compute implied elasticity, optimal pricing, revenue gap decomposition, and renewal opportunity. These feed into rebalanced flags (6 new, 3 reclassified), bidirectional experiments, revenue-efficiency scoring, and restructured slides. All new computation is deterministic; Claude provides judgment only.

**Tech Stack:** Python/FastAPI, SQLAlchemy 2.0, Alembic, React 18, Recharts, Claude API

**Spec:** `docs/superpowers/specs/2026-03-18-revenue-optimization-redesign.md`

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `backend/app/engine/revenue_optimizer.py` | Implied elasticity, optimal price, revenue gap decomposition, revenue efficiency score |
| `backend/app/engine/renewal_optimizer.py` | Renewal increase recommendations, turnover cost model, net capture |
| `backend/tests/test_revenue_optimizer.py` | Tests for all revenue optimizer functions |
| `backend/tests/test_renewal_optimizer.py` | Tests for renewal optimizer |
| `backend/tests/test_backward_compatibility.py` | Graceful degradation for old metrics format |
| `frontend/src/components/slideshow/charts/RevenueGapWaterfall.jsx` | Gap decomposition waterfall chart |
| `frontend/src/components/slideshow/charts/DimensionBreakdownChart.jsx` | Occ/pricing/momentum stacked bar |
| `frontend/src/components/slideshow/charts/RevenueRoadmapBars.jsx` | Before/after per-lever breakdown |

### Modified Files
| File | Changes |
|------|---------|
| `backend/app/engine/aggregator.py` | Add portfolio-level revenue metrics to `compute_portfolio_metrics()` and `aggregate_cross_property()` |
| `backend/app/models/config.py` | No column change — `revenue_efficiency_zones` stored as key in existing JSONB fields |
| `backend/app/services/metrics_engine.py` | Extend `_units_to_dicts()` with concession fields; call 5 new engine functions in `compute_property_metrics()` |
| `backend/app/services/flag_generator.py` | 6 new flags, 3 reclassifications |
| `backend/app/services/action_plan_service.py` | Bidirectional experiment design, revenue-per-day convergence |
| `backend/app/services/diagnostic_service.py` | Revenue-efficiency Claude prompts, updated fallback |
| `backend/app/services/viz_data_service.py` | Modify 5 generators, add 3 new, remove `generate_stacked_bar()` |
| `backend/app/services/slide_deck_service.py` | Restructure slides 2, 3, 7, 12 for revenue content |
| `backend/app/services/narrative_service.py` | Update prompts for revenue framing |
| `backend/app/services/portfolio_diagnostic_service.py` | Align with revenue-efficiency scoring |
| `backend/app/services/portfolio_viz_data_service.py` | Add revenue gap waterfall, efficiency ranking |
| `backend/app/services/portfolio_slide_deck_service.py` | Restructure portfolio slides |
| `backend/tests/test_flag_generator.py` | Updated expected counts, new flag tests |
| `backend/tests/test_metrics_engine.py` | Assert new metric sections present |
| `backend/tests/test_action_plan.py` | Bidirectional experiment tests |
| `backend/tests/test_diagnostic_service.py` | Revenue-efficiency scoring expectations |
| `frontend/src/components/slideshow/charts/ScoreGauge.jsx` | New zone labels + dynamic weight display |
| `frontend/src/components/slideshow/charts/RentWaterfall.jsx` | Add Optimal bar |
| `frontend/src/components/slideshow/charts/VacancyCostBar.jsx` | **REMOVE** — replaced by RevenueGapWaterfall |
| `backend/app/services/portfolio_narrative_service.py` | Update prompts for revenue framing |
| `backend/app/seed/seed_config.py` | Add new config keys to demo client seed data |
| `frontend/src/components/slideshow/slides/ExecutiveSummarySlide.jsx` | 6 KPI cards + dimension breakdown |
| `frontend/src/components/slideshow/slides/PortfolioSnapshotSlide.jsx` | Add revenue columns |
| `frontend/src/components/slideshow/slides/PropertyDeepDiveSlide.jsx` | Optimal bar + dimension cards |
| `frontend/src/components/slideshow/slides/TrendAnalysisSlide.jsx` | Optimal price trend line |
| `frontend/src/components/slideshow/slides/RevenueAtRiskSlide.jsx` | Replace with revenue gap waterfall |
| `frontend/src/components/slideshow/slides/SummarySlide.jsx` | Revenue roadmap |

---

## Task 1: Revenue Optimizer Engine — Implied Elasticity + Optimal Price

**Files:**
- Create: `backend/app/engine/revenue_optimizer.py`
- Create: `backend/tests/test_revenue_optimizer.py`

- [ ] **Step 1: Write failing tests for implied elasticity**

Create `backend/tests/test_revenue_optimizer.py`:

```python
"""Tests for revenue optimization engine — implied elasticity and optimal pricing."""
import pytest
from app.engine.revenue_optimizer import compute_implied_elasticity


# 4-month snapshot data mimicking A1 trend: asking flat, occ stable
A1_SNAPSHOTS = [
    {"month": "2025-12", "avg_occupancy": 0.94, "avg_asking_rent": 1350, "avg_comp_asking": 1340},
    {"month": "2026-01", "avg_occupancy": 0.95, "avg_asking_rent": 1355, "avg_comp_asking": 1345},
    {"month": "2026-02", "avg_occupancy": 0.96, "avg_asking_rent": 1360, "avg_comp_asking": 1350},
    {"month": "2026-03", "avg_occupancy": 0.96, "avg_asking_rent": 1365, "avg_comp_asking": 1353},
]

# B1 trend: asking dropped, occ still declining — high elasticity
B1_SNAPSHOTS = [
    {"month": "2025-12", "avg_occupancy": 0.85, "avg_asking_rent": 1580, "avg_comp_asking": 1440},
    {"month": "2026-01", "avg_occupancy": 0.83, "avg_asking_rent": 1560, "avg_comp_asking": 1435},
    {"month": "2026-02", "avg_occupancy": 0.81, "avg_asking_rent": 1540, "avg_comp_asking": 1434},
    {"month": "2026-03", "avg_occupancy": 0.79, "avg_asking_rent": 1525, "avg_comp_asking": 1434},
]

COMP_TRENDS = []  # empty for initial tests


class TestImpliedElasticity:
    def test_returns_required_fields(self):
        result = compute_implied_elasticity(A1_SNAPSHOTS, COMP_TRENDS)
        assert "elasticity_coefficient" in result
        assert "confidence" in result
        assert "data_points" in result
        assert "direction" in result

    def test_stable_market_low_elasticity(self):
        """A1: flat asking, stable occ → INELASTIC or UNKNOWN."""
        result = compute_implied_elasticity(A1_SNAPSHOTS, COMP_TRENDS)
        assert result["direction"] in ("INELASTIC", "UNKNOWN")
        assert result["confidence"] in ("LOW", "MEDIUM")

    def test_declining_market_higher_elasticity(self):
        """B1: dropping asking, dropping occ → ELASTIC."""
        result = compute_implied_elasticity(B1_SNAPSHOTS, COMP_TRENDS)
        assert result["direction"] == "ELASTIC"
        assert result["elasticity_coefficient"] > 0

    def test_insufficient_data_low_confidence(self):
        """Single data point → LOW confidence."""
        result = compute_implied_elasticity(B1_SNAPSHOTS[:1], COMP_TRENDS)
        assert result["confidence"] == "LOW"
        assert result["direction"] == "UNKNOWN"

    def test_data_points_count(self):
        result = compute_implied_elasticity(A1_SNAPSHOTS, COMP_TRENDS)
        assert result["data_points"] == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_revenue_optimizer.py::TestImpliedElasticity -v`
Expected: FAIL — `ImportError: cannot import name 'compute_implied_elasticity'`

- [ ] **Step 3: Implement `compute_implied_elasticity()`**

Create `backend/app/engine/revenue_optimizer.py`:

```python
"""Revenue optimization engine — implied elasticity, optimal pricing, gap decomposition, efficiency scoring.

All functions are PURE — no DB access, no side effects. Consistent with engine isolation rule.
"""
import math


def compute_implied_elasticity(
    snapshot_trends: list[dict],
    comp_trends: list[dict],
) -> dict:
    """Estimate price sensitivity per unit type from historical snapshot data.

    Uses month-over-month changes in asking rent and occupancy to infer
    a crude elasticity coefficient. Confidence reflects data quality.

    Args:
        snapshot_trends: Monthly snapshots with avg_occupancy, avg_asking_rent, avg_comp_asking.
        comp_trends: Comp rent observations (used for corroboration).

    Returns:
        Dict with elasticity_coefficient, confidence, data_points, direction, notes.
    """
    n = len(snapshot_trends)
    if n < 2:
        return {
            "elasticity_coefficient": 0.0,
            "confidence": "LOW",
            "data_points": n,
            "direction": "UNKNOWN",
            "notes": f"Only {n} data point(s); insufficient for elasticity estimate",
        }

    # Compute month-over-month changes
    price_changes = []
    occ_changes = []
    for i in range(1, n):
        prev = snapshot_trends[i - 1]
        curr = snapshot_trends[i]
        prev_ask = prev.get("avg_asking_rent", prev.get("asking_rent", 0))
        curr_ask = curr["avg_asking_rent"]
        if prev_ask > 0:
            pct_price_change = (curr_ask - prev_ask) / prev_ask
            occ_change = curr.get("avg_occupancy", curr.get("occupancy_rate", 0)) - prev.get("avg_occupancy", prev.get("occupancy_rate", 0))
            price_changes.append(pct_price_change)
            occ_changes.append(occ_change)

    if not price_changes:
        return {
            "elasticity_coefficient": 0.0,
            "confidence": "LOW",
            "data_points": n,
            "direction": "UNKNOWN",
            "notes": "No valid price change observations",
        }

    # Average absolute price change — if near zero, can't estimate elasticity
    avg_abs_price_change = sum(abs(p) for p in price_changes) / len(price_changes)
    avg_occ_change = sum(occ_changes) / len(occ_changes)
    avg_price_change = sum(price_changes) / len(price_changes)

    if avg_abs_price_change < 0.002:  # <0.2% avg change — too flat
        return {
            "elasticity_coefficient": 0.0,
            "confidence": "LOW",
            "data_points": n,
            "direction": "UNKNOWN",
            "notes": "Asking rent too stable to estimate elasticity (<0.2% avg change)",
        }

    # Elasticity coefficient: estimated occupancy change per 1% price change
    # Negative = price up → occ down (normal). We store as positive magnitude.
    raw_elasticity = avg_occ_change / avg_price_change if avg_price_change != 0 else 0.0
    elasticity_coefficient = abs(raw_elasticity)

    # Direction
    if avg_price_change > 0 and avg_occ_change < -0.005:
        direction = "ELASTIC"  # price went up, occ went down
    elif avg_price_change < 0 and avg_occ_change < -0.005:
        direction = "ELASTIC"  # price went down but occ STILL declining — very elastic
    elif abs(avg_occ_change) < 0.005:
        direction = "INELASTIC"  # occ barely changed despite price movement
    else:
        direction = "INELASTIC"

    # Confidence based on data quality
    # Check for consistent direction (all changes same sign)
    price_signs = [1 if p > 0.001 else (-1 if p < -0.001 else 0) for p in price_changes]
    occ_signs = [1 if o > 0.005 else (-1 if o < -0.005 else 0) for o in occ_changes]
    consistent = all(s == price_signs[0] for s in price_signs if s != 0)

    if n >= 4 and consistent and avg_abs_price_change >= 0.005:
        confidence = "HIGH"
    elif n >= 3 and avg_abs_price_change >= 0.003:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "elasticity_coefficient": round(elasticity_coefficient, 4),
        "confidence": confidence,
        "data_points": n,
        "direction": direction,
        "notes": (
            f"{n} months of data; avg price change {avg_abs_price_change:.1%}; "
            f"avg occ change {avg_occ_change:+.2%}"
        ),
    }
```

- [ ] **Step 4: Run elasticity tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_revenue_optimizer.py::TestImpliedElasticity -v`
Expected: 5 passed

- [ ] **Step 5: Write failing tests for optimal price**

Add to `backend/tests/test_revenue_optimizer.py`:

```python
from app.engine.revenue_optimizer import compute_optimal_price

# Default revenue efficiency zones config
DEFAULT_ZONES = {
    "crisis_below": 0.82,
    "stressed_below": 0.89,
    "balanced_below": 0.94,
    "strong_below": 0.97,
}

A1_METRICS = {
    "occupancy_metrics": {"occupancy_rate": 0.96, "total_units": 48, "occupied": 46, "vacant": 2},
    "pricing_spreads": {"asking_rent": 1365, "predicted_rent": 1329, "comps_rent": 1353, "base_rent": 1240, "amenity_price": 89, "in_place_rent": 1269},
    "revenue_metrics": {"daily_vacancy_burn": 91, "monthly_vacancy_cost": 2730},
    "velocity_metrics": {"avg_dom": 24},
    "ltl_analysis": {"ltl_dollars": 96, "ltl_pct": 0.076, "ltl_direction": "UPSIDE"},
}

A1_ELASTICITY = {"elasticity_coefficient": 0.3, "confidence": "LOW", "direction": "INELASTIC"}

A1_SEASONAL = {"season": "SPRING_RAMP", "seasonal_factor": 0.98, "months_to_peak": 2}

B1_METRICS = {
    "occupancy_metrics": {"occupancy_rate": 0.79, "total_units": 24, "occupied": 19, "vacant": 5},
    "pricing_spreads": {"asking_rent": 1525, "predicted_rent": 1530, "comps_rent": 1434, "base_rent": 1405, "amenity_price": 125, "in_place_rent": 1572},
    "revenue_metrics": {"daily_vacancy_burn": 254, "monthly_vacancy_cost": 7625},
    "velocity_metrics": {"avg_dom": 25},
    "ltl_analysis": {"ltl_dollars": -47, "ltl_pct": -0.030, "ltl_direction": "NEGATIVE"},
}

B1_ELASTICITY = {"elasticity_coefficient": 1.2, "confidence": "MEDIUM", "direction": "ELASTIC"}


class TestOptimalPrice:
    def test_returns_required_fields(self):
        result = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        for field in ("optimal_asking", "optimal_revenue_monthly", "current_revenue_monthly",
                       "revenue_gap_monthly", "price_direction", "recommended_asking",
                       "confidence", "comp_constrained"):
            assert field in result, f"Missing field: {field}"

    def test_a1_price_direction_increase(self):
        """A1: 96% occ, asking below comps — should recommend INCREASE."""
        result = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        assert result["price_direction"] == "INCREASE"
        assert result["optimal_asking"] > A1_METRICS["pricing_spreads"]["asking_rent"]

    def test_b1_price_direction_decrease(self):
        """B1: 79% occ, asking $91 above comps — should recommend DECREASE."""
        result = compute_optimal_price(B1_METRICS, B1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        assert result["price_direction"] == "DECREASE"
        assert result["optimal_asking"] < B1_METRICS["pricing_spreads"]["asking_rent"]

    def test_recommended_is_conservative(self):
        """Recommended asking is halfway between current and optimal."""
        result = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        current = A1_METRICS["pricing_spreads"]["asking_rent"]
        optimal = result["optimal_asking"]
        expected_rec = (current + optimal) / 2
        assert abs(result["recommended_asking"] - expected_rec) < 1.0

    def test_comp_constraint(self):
        """Optimal must be within ±15% of comps."""
        result = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        comps = A1_METRICS["pricing_spreads"]["comps_rent"]
        assert result["optimal_asking"] <= comps * 1.15
        assert result["optimal_asking"] >= comps * 0.85

    def test_revenue_gap_is_positive_for_a1(self):
        """A1 is underpriced — gap should be positive."""
        result = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        assert result["revenue_gap_monthly"] > 0
```

- [ ] **Step 6: Run optimal price tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_revenue_optimizer.py::TestOptimalPrice -v`
Expected: FAIL — `ImportError: cannot import name 'compute_optimal_price'`

- [ ] **Step 7: Implement `compute_optimal_price()`**

Add to `backend/app/engine/revenue_optimizer.py`:

```python
def compute_optimal_price(
    unit_type_metrics: dict,
    elasticity: dict,
    seasonal_context: dict,
    zone_config: dict | None = None,
) -> dict:
    """Find the revenue-maximizing asking rent for a unit type.

    Sweeps ±10% from current asking, estimates occupancy at each price point
    using the implied elasticity, and finds the peak of rent × occupancy.

    Args:
        unit_type_metrics: Dict with occupancy_metrics, pricing_spreads, etc.
        elasticity: Output of compute_implied_elasticity().
        seasonal_context: Dict with season, seasonal_factor, months_to_peak.
        zone_config: Configurable zone boundaries (defaults if None).

    Returns:
        Dict with optimal_asking, revenue_gap, price_direction, etc.
    """
    if zone_config is None:
        zone_config = {
            "crisis_below": 0.82, "stressed_below": 0.89,
            "balanced_below": 0.94, "strong_below": 0.97,
        }

    occ = unit_type_metrics["occupancy_metrics"]
    ps = unit_type_metrics["pricing_spreads"]
    current_asking = ps["asking_rent"]
    comps = ps["comps_rent"]
    total_units = occ["total_units"]
    current_occ_rate = occ["occupancy_rate"]
    current_occupied = occ["occupied"]
    in_place = ps["in_place_rent"]

    # Current revenue
    current_monthly_revenue = in_place * current_occupied

    # Elasticity coefficient: occ change per 1% price change
    elast = elasticity.get("elasticity_coefficient", 0.0)
    if elast == 0:
        elast = 0.3  # conservative default when no data

    # Sweep ±10% from current asking in 0.5% steps
    best_revenue = 0.0
    best_price = current_asking
    for delta_pct in range(-20, 21):  # -10% to +10% in 0.5% steps
        pct = delta_pct * 0.005
        test_price = current_asking * (1 + pct)

        # Estimate occupancy at this price
        price_change_pct = pct * 100  # convert to "per 1%" units
        occ_delta = -elast * price_change_pct / 100  # negative because price up → occ down
        estimated_occ = min(1.0, max(0.0, current_occ_rate + occ_delta))
        estimated_occupied = round(estimated_occ * total_units)

        revenue = test_price * estimated_occupied
        if revenue > best_revenue:
            best_revenue = revenue
            best_price = test_price

    # Apply seasonal adjustment
    seasonal_factor = seasonal_context.get("seasonal_factor", 1.0)
    months_to_peak = seasonal_context.get("months_to_peak", 6)
    if months_to_peak <= 3:
        # Approaching peak — shift optimal up slightly
        seasonal_bump = best_price * 0.01 * (1 - seasonal_factor)
    elif months_to_peak >= 9:
        # Approaching off-peak — shift optimal down slightly
        seasonal_bump = -best_price * 0.01
    else:
        seasonal_bump = 0.0
    best_price += seasonal_bump

    # Comp constraint: ±15%
    comp_floor = comps * 0.85
    comp_ceiling = comps * 1.15
    comp_constrained = False
    if best_price > comp_ceiling:
        best_price = comp_ceiling
        comp_constrained = True
    elif best_price < comp_floor:
        best_price = comp_floor
        comp_constrained = True

    best_price = round(best_price)

    # Estimate revenue at optimal
    opt_price_change = (best_price - current_asking) / current_asking if current_asking > 0 else 0
    opt_occ_delta = -elast * opt_price_change
    opt_occ = min(1.0, max(0.0, current_occ_rate + opt_occ_delta))
    opt_occupied = round(opt_occ * total_units)
    optimal_monthly_revenue = best_price * opt_occupied

    # Revenue gap
    gap = optimal_monthly_revenue - current_monthly_revenue

    # Direction
    if best_price > current_asking * 1.02:
        direction = "INCREASE"
    elif best_price < current_asking * 0.98:
        direction = "DECREASE"
    else:
        direction = "HOLD"

    # Conservative recommended asking: halfway between current and optimal
    recommended = round((current_asking + best_price) / 2)

    return {
        "optimal_asking": best_price,
        "optimal_revenue_monthly": round(optimal_monthly_revenue, 2),
        "current_revenue_monthly": round(current_monthly_revenue, 2),
        "revenue_gap_monthly": round(gap, 2),
        "price_direction": direction,
        "recommended_asking": recommended,
        "confidence": elasticity.get("confidence", "LOW"),
        "seasonal_adjustment_applied": round(seasonal_bump, 2),
        "comp_constrained": comp_constrained,
    }
```

- [ ] **Step 8: Run optimal price tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_revenue_optimizer.py::TestOptimalPrice -v`
Expected: 6 passed

- [ ] **Step 9: Run all revenue optimizer tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_revenue_optimizer.py -v`
Expected: 11 passed

- [ ] **Step 10: Commit**

```
feat: add implied elasticity and optimal price engine functions

Pure functions that estimate price sensitivity from snapshot history
and compute revenue-maximizing asking rent per unit type.
```

---

## Task 2: Revenue Optimizer Engine — Gap Decomposition + Efficiency Score

**Files:**
- Modify: `backend/app/engine/revenue_optimizer.py`
- Modify: `backend/tests/test_revenue_optimizer.py`

- [ ] **Step 1: Write failing tests for revenue gap decomposition**

Add to `backend/tests/test_revenue_optimizer.py`:

```python
from app.engine.revenue_optimizer import decompose_revenue_gap

RENEWAL_ANALYSIS = {
    "upcoming_renewals_90d": 10,
    "net_monthly_capture": 508,
}

CONCESSION_DATA = {"total_concession_drag_monthly": 0}  # A1 has no active concessions


class TestRevenueGapDecomposition:
    def test_components_sum_to_total(self):
        optimal = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        gap = decompose_revenue_gap(A1_METRICS, optimal, RENEWAL_ANALYSIS, CONCESSION_DATA)
        component_sum = sum(c["amount"] for c in gap["gap_components"].values())
        # Components should approximately sum to total gap (may not be exact due to interaction)
        assert abs(component_sum - gap["total_gap_monthly"]) < gap["total_gap_monthly"] * 0.2

    def test_vacancy_cost_positive_for_a1(self):
        optimal = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        gap = decompose_revenue_gap(A1_METRICS, optimal, RENEWAL_ANALYSIS, CONCESSION_DATA)
        assert gap["gap_components"]["vacancy_cost"]["amount"] > 0
        assert gap["gap_components"]["vacancy_cost"]["lever"] == "FILL"

    def test_dominant_lever_for_a1(self):
        """A1: underpriced — dominant lever should be RENEW or REPRICE, not FILL."""
        optimal = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        gap = decompose_revenue_gap(A1_METRICS, optimal, RENEWAL_ANALYSIS, CONCESSION_DATA)
        assert gap["dominant_lever"] in ("RENEW", "REPRICE")

    def test_lever_ranking_ordered_by_amount(self):
        optimal = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        gap = decompose_revenue_gap(A1_METRICS, optimal, RENEWAL_ANALYSIS, CONCESSION_DATA)
        amounts = [gap["gap_components"][l]["amount"] for l in gap["lever_ranking"]]
        assert amounts == sorted(amounts, reverse=True)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_revenue_optimizer.py::TestRevenueGapDecomposition -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement `decompose_revenue_gap()`**

Add to `backend/app/engine/revenue_optimizer.py`:

```python
def decompose_revenue_gap(
    unit_type_metrics: dict,
    optimal: dict,
    renewal_analysis: dict,
    concession_data: dict,
) -> dict:
    """Break the total revenue gap into actionable lever components.

    Args:
        unit_type_metrics: Dict with occupancy, pricing, revenue metrics.
        optimal: Output of compute_optimal_price().
        renewal_analysis: Output of compute_renewal_opportunity().
        concession_data: Dict with total_concession_drag_monthly.

    Returns:
        Dict with current/optimal revenue, total gap, gap components by lever, dominant lever.
    """
    occ = unit_type_metrics["occupancy_metrics"]
    ps = unit_type_metrics["pricing_spreads"]
    vel = unit_type_metrics.get("velocity_metrics", {})

    current_asking = ps["asking_rent"]
    in_place = ps["in_place_rent"]
    occupied = occ["occupied"]
    vacant = occ["vacant"]
    total_units = occ["total_units"]
    avg_dom = vel.get("avg_dom", 30)

    optimal_asking = optimal["optimal_asking"]
    current_monthly = optimal["current_revenue_monthly"]
    optimal_monthly = optimal["optimal_revenue_monthly"]
    total_gap = optimal_monthly - current_monthly

    # Component 1: Vacancy cost — revenue lost to empty units
    vacancy_cost = vacant * current_asking  # monthly

    # Component 2: New lease underpricing — asking below optimal on new leases
    # Estimated new leases in next 30 days ≈ vacant (they need to be filled)
    asking_gap = max(0, optimal_asking - current_asking)
    new_lease_underpricing = asking_gap * vacant

    # Component 3: In-place underpricing — LTL across occupied units (capturable at renewal)
    ltl = unit_type_metrics.get("ltl_analysis", {})
    ltl_dollars = max(0, ltl.get("ltl_dollars", 0))
    in_place_underpricing = ltl_dollars * occupied

    # Component 4: Renewal opportunity — from renewal optimizer
    renewal_capture = renewal_analysis.get("net_monthly_capture", 0)

    # Component 5: Concession drag
    concession_drag = concession_data.get("total_concession_drag_monthly", 0)

    # Build components dict
    components = {
        "vacancy_cost": {
            "amount": round(vacancy_cost, 2),
            "lever": "FILL",
            "description": "Revenue lost to empty units",
        },
        "new_lease_underpricing": {
            "amount": round(new_lease_underpricing, 2),
            "lever": "REPRICE",
            "description": "Revenue lost from asking below optimal on new leases",
        },
        "in_place_underpricing": {
            "amount": round(in_place_underpricing, 2),
            "lever": "RENEW",
            "description": "Revenue gap in current leases, addressable at renewal",
        },
        "renewal_opportunity": {
            "amount": round(renewal_capture, 2),
            "lever": "RENEW",
            "description": "Capturable through upcoming renewal increases",
        },
        "concession_drag": {
            "amount": round(concession_drag, 2),
            "lever": "DE_CONCESSION",
            "description": "Revenue reduction from active concessions",
        },
    }

    # Rank by amount (descending)
    lever_ranking = sorted(components.keys(), key=lambda k: components[k]["amount"], reverse=True)
    dominant = components[lever_ranking[0]]["lever"] if lever_ranking else "FILL"

    return {
        "current_monthly_revenue": round(current_monthly, 2),
        "optimal_monthly_revenue": round(optimal_monthly, 2),
        "total_gap_monthly": round(total_gap, 2),
        "gap_components": components,
        "dominant_lever": dominant,
        "lever_ranking": lever_ranking,
    }
```

- [ ] **Step 4: Run gap decomposition tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_revenue_optimizer.py::TestRevenueGapDecomposition -v`
Expected: 4 passed

- [ ] **Step 5: Write failing tests for revenue efficiency score**

Add to `backend/tests/test_revenue_optimizer.py`:

```python
from app.engine.revenue_optimizer import compute_revenue_efficiency

DEFAULT_EFFICIENCY_CONFIG = {
    "crisis_below": 0.82,
    "stressed_below": 0.89,
    "balanced_below": 0.94,
    "strong_below": 0.97,
    "crisis_weights": [0.60, 0.15, 0.25],
    "stressed_weights": [0.45, 0.30, 0.25],
    "balanced_weights": [0.30, 0.35, 0.35],
    "strong_weights": [0.15, 0.45, 0.40],
    "full_weights": [0.10, 0.50, 0.40],
    "seasonal_weight_shift": 0.05,
}


class TestRevenueEfficiency:
    def test_returns_required_fields(self):
        optimal = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        result = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, A1_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert "revenue_efficiency_score" in result
        assert "grade" in result
        assert "dimensions" in result
        assert "occupancy_zone" in result

    def test_a1_grade_is_opportunity(self):
        """A1: 96% occ, underpriced → should be OPPORTUNITY (not OPTIMIZED)."""
        optimal = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        result = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, A1_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert result["grade"] in ("OPPORTUNITY", "IMBALANCED")
        assert result["revenue_efficiency_score"] < 85  # not OPTIMIZED

    def test_b1_grade_is_distressed_or_crisis(self):
        """B1: 79% occ, overpriced → should be CRISIS or DISTRESSED."""
        optimal = compute_optimal_price(B1_METRICS, B1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        result = compute_revenue_efficiency(
            B1_METRICS, optimal, B1_SNAPSHOTS, A1_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert result["grade"] in ("CRISIS", "DISTRESSED")

    def test_dynamic_weights_for_strong_occ(self):
        """A1 at 96% → Strong zone → pricing weight should be ~0.45."""
        optimal = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        result = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, A1_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert result["occupancy_zone"] == "STRONG"
        pricing_weight = result["dimensions"]["pricing_alignment"]["weight"]
        assert 0.40 <= pricing_weight <= 0.50

    def test_dynamic_weights_for_crisis_occ(self):
        """B1 at 79% → Crisis zone → occ weight should be ~0.60."""
        optimal = compute_optimal_price(B1_METRICS, B1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        result = compute_revenue_efficiency(
            B1_METRICS, optimal, B1_SNAPSHOTS, A1_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert result["occupancy_zone"] == "CRISIS"
        occ_weight = result["dimensions"]["occupancy_health"]["weight"]
        assert 0.55 <= occ_weight <= 0.65

    def test_score_is_0_to_100(self):
        optimal = compute_optimal_price(A1_METRICS, A1_ELASTICITY, A1_SEASONAL, DEFAULT_ZONES)
        result = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, A1_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert 0 <= result["revenue_efficiency_score"] <= 100
```

- [ ] **Step 6: Implement `compute_revenue_efficiency()`**

Add to `backend/app/engine/revenue_optimizer.py`. Implements:
- Three dimension scores (occupancy health, pricing alignment, rent roll momentum)
- Dynamic weight lookup by occupancy zone from config
- Seasonal weight shift (±5%)
- Grade mapping from composite score

The function takes `unit_type_metrics`, `optimal`, `snapshot_trends`, `seasonal_context`, and `zone_config` and returns the score dict as specified in the spec Section 1.4.

- [ ] **Step 7: Run all revenue efficiency tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_revenue_optimizer.py::TestRevenueEfficiency -v`
Expected: 6 passed

- [ ] **Step 8: Run full test file**

Run: `cd backend && .venv/bin/python -m pytest tests/test_revenue_optimizer.py -v`
Expected: 21 passed

- [ ] **Step 9: Commit**

```
feat: add revenue gap decomposition and efficiency scoring

Gap decomposition breaks revenue loss into 5 actionable levers.
Efficiency score uses dynamic weighting by occupancy zone.
```

---

## Task 3: Renewal Optimizer Engine

**Files:**
- Create: `backend/app/engine/renewal_optimizer.py`
- Create: `backend/tests/test_renewal_optimizer.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_renewal_optimizer.py`:

```python
"""Tests for renewal optimization engine."""
import pytest
from app.engine.renewal_optimizer import compute_renewal_opportunity

DEFAULT_RENEWAL_CONFIG = {
    "freeze_below_occupancy": 0.82,
    "make_ready_cost_estimate": 2500,
    "base_non_renewal_rate": 0.10,
    "increase_sensitivity_factor": 5.0,
    "max_turnover_probability": 0.60,
}

A1_METRICS = {
    "occupancy_metrics": {"occupancy_rate": 0.96, "total_units": 48, "occupied": 46, "vacant": 2},
    "pricing_spreads": {"asking_rent": 1365, "in_place_rent": 1269},
    "velocity_metrics": {"avg_dom": 24},
    "ltl_analysis": {"ltl_dollars": 96, "ltl_pct": 0.076, "ltl_direction": "UPSIDE"},
}

A1_ELASTICITY = {"elasticity_coefficient": 0.3, "confidence": "LOW"}
A1_SEASONAL = {"season": "SPRING_RAMP", "months_to_peak": 2}

# Units with upcoming lease_end for A1
A1_UNITS = [
    {"status": "occupied", "lease_end": "2026-04-15"},  # within 90 days
    {"status": "occupied", "lease_end": "2026-05-01"},  # within 90 days
    {"status": "occupied", "lease_end": "2026-06-01"},  # within 90 days
    {"status": "occupied", "lease_end": "2026-03-25"},  # within 90 days
    {"status": "occupied", "lease_end": "2026-04-20"},  # within 90 days
    {"status": "occupied", "lease_end": "2026-09-01"},  # NOT within 90 days
    {"status": "vacant", "lease_end": None},  # vacant — skip
]

B1_METRICS = {
    "occupancy_metrics": {"occupancy_rate": 0.79, "total_units": 24, "occupied": 19, "vacant": 5},
    "pricing_spreads": {"asking_rent": 1525, "in_place_rent": 1572},
    "velocity_metrics": {"avg_dom": 25},
    "ltl_analysis": {"ltl_dollars": -47, "ltl_pct": -0.030, "ltl_direction": "NEGATIVE"},
}


class TestRenewalOptimizer:
    def test_returns_required_fields(self):
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, A1_SEASONAL, A1_UNITS,
            "2026-03-18", DEFAULT_RENEWAL_CONFIG,
        )
        for field in ("upcoming_renewals_90d", "recommended_increase_pct",
                       "net_annual_capture", "estimated_turnover_probability"):
            assert field in result

    def test_a1_recommends_increase(self):
        """A1: 96% occ, 7.6% LTL, spring ramp → should recommend 4-6%."""
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, A1_SEASONAL, A1_UNITS,
            "2026-03-18", DEFAULT_RENEWAL_CONFIG,
        )
        assert result["recommended_increase_pct"] >= 0.03
        assert result["recommended_increase_pct"] <= 0.06
        assert result["net_annual_capture"] > 0

    def test_b1_recommends_freeze(self):
        """B1: 79% occ → below freeze threshold → 0% increase."""
        result = compute_renewal_opportunity(
            B1_METRICS, {"elasticity_coefficient": 1.2, "confidence": "MEDIUM"},
            A1_SEASONAL, [], "2026-03-18", DEFAULT_RENEWAL_CONFIG,
        )
        assert result["recommended_increase_pct"] == 0.0

    def test_upcoming_renewals_count(self):
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, A1_SEASONAL, A1_UNITS,
            "2026-03-18", DEFAULT_RENEWAL_CONFIG,
        )
        assert result["upcoming_renewals_90d"] == 5

    def test_turnover_probability_capped(self):
        """Even at extreme increase, turnover probability should not exceed max_turnover_cap."""
        config = {**DEFAULT_RENEWAL_CONFIG, "increase_sensitivity_factor": 50.0}
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, A1_SEASONAL, A1_UNITS,
            "2026-03-18", config,
        )
        assert result["estimated_turnover_probability"] <= 0.60

    def test_no_upcoming_renewals(self):
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, A1_SEASONAL, [],
            "2026-03-18", DEFAULT_RENEWAL_CONFIG,
        )
        assert result["upcoming_renewals_90d"] == 0
        assert result["net_annual_capture"] == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/bin/python -m pytest tests/test_renewal_optimizer.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement `compute_renewal_opportunity()`**

Create `backend/app/engine/renewal_optimizer.py` following the spec Section 2 model:
- Count upcoming renewals from unit dicts (occupied + lease_end within 90 days)
- Lookup recommended increase % from occupancy zone × LTL × season table
- Compute turnover probability with configurable sensitivity + max cap
- Compute net annual capture = gross capture − (turnover_prob × turnover_cost × renewals)

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_renewal_optimizer.py -v`
Expected: 6 passed

- [ ] **Step 5: Run full backend suite for regressions**

Run: `cd backend && .venv/bin/python -m pytest tests/ -q`
Expected: 203 existing + 27 new = 230+ passed

- [ ] **Step 6: Commit**

```
feat: add renewal optimizer engine function

Computes renewal increase recommendations with turnover cost model.
Configurable sensitivity factor and max turnover cap.
```

---

## Task 4: Config Model + Metrics Engine Integration

**Files:**
- Modify: `backend/app/models/config.py` (add JSONB field)
- Modify: `backend/app/services/metrics_engine.py` (extend `_units_to_dicts`, call new engine functions)
- Modify: `backend/tests/test_metrics_engine.py` (verify new sections)

- [ ] **Step 1: Store `revenue_efficiency_zones` in existing config structure**

No schema change needed. The `revenue_efficiency_zones` config is passed via the `config_dict` parameter that already flows through the system. The engine functions read zone boundaries from `config_dict.get("revenue_efficiency_zones", {})` with hardcoded defaults as fallback. Update `backend/app/seed/seed_config.py` to include the new keys in the demo client's seeded config:

```python
# Add to the seeded config dict for each property
"revenue_efficiency_zones": {
    "crisis_below": 0.82,
    "stressed_below": 0.89,
    "balanced_below": 0.94,
    "strong_below": 0.97,
    "crisis_weights": [0.60, 0.15, 0.25],
    "stressed_weights": [0.45, 0.30, 0.25],
    "balanced_weights": [0.30, 0.35, 0.35],
    "strong_weights": [0.15, 0.45, 0.40],
    "full_weights": [0.10, 0.50, 0.40],
    "seasonal_weight_shift": 0.05,
    "max_turnover_probability": 0.60,
}
```

Also add the new keys to `pricing_tolerance`, `renewal_policy`, and `concession_policy` JSONB fields in the seed data per spec Section 7.

- [ ] **Step 2: Extend `_units_to_dicts()` with concession fields**

In `backend/app/services/metrics_engine.py`, add to the dict comprehension in `_units_to_dicts()` (around line 17-37):

```python
"concession_active": u.concession_active,
"concession_type": u.concession_type,
"concession_value_monthly": u.concession_value_monthly,
```

- [ ] **Step 3: Wire new engine calls into `compute_property_metrics()`**

After the existing metric computation block (around line 123), add:

```python
from app.engine.revenue_optimizer import (
    compute_implied_elasticity, compute_optimal_price,
    decompose_revenue_gap, compute_revenue_efficiency,
)
from app.engine.renewal_optimizer import compute_renewal_opportunity

# Get zone config from client config or use defaults
zone_config = config_dict.get("revenue_efficiency_zones") or {}

# Per unit type, compute revenue optimization metrics
for ut_code, ut_metrics in metrics["unit_type_metrics"].items():
    snapshots_for_ut = [s for s in snapshot_data if s["unit_type_code"] == ut_code]
    comp_data_for_ut = [c for c in comp_data if c.get("unit_type_code") == ut_code]

    elasticity = compute_implied_elasticity(snapshots_for_ut, comp_data_for_ut)
    ut_metrics["elasticity"] = elasticity

    optimal = compute_optimal_price(ut_metrics, elasticity, ut_metrics["seasonal_context"], zone_config)
    ut_metrics["optimal_pricing"] = optimal

    # Filter units for this unit type to find upcoming renewals
    ut_units = [u for u in all_units_data if u.get("unit_type_code") == ut_code]
    renewal_config = config_dict.get("renewal_policy", {})
    renewal = compute_renewal_opportunity(
        ut_metrics, elasticity, ut_metrics["seasonal_context"],
        ut_units, str(reference_date), renewal_config,
    )
    ut_metrics["renewal_opportunity"] = renewal

    # Concession drag
    concession_drag = sum(
        u.get("concession_value_monthly", 0) or 0
        for u in ut_units if u.get("concession_active")
    )
    concession_data = {"total_concession_drag_monthly": concession_drag}

    gap = decompose_revenue_gap(ut_metrics, optimal, renewal, concession_data)
    ut_metrics["revenue_gap"] = gap

    efficiency = compute_revenue_efficiency(
        ut_metrics, optimal, snapshots_for_ut,
        ut_metrics["seasonal_context"], zone_config,
    )
    ut_metrics["revenue_efficiency"] = efficiency
```

- [ ] **Step 4: Write test verifying new sections**

Add to `backend/tests/test_metrics_engine.py`:

```python
class TestRevenueOptimizationIntegration:
    def test_metrics_include_elasticity(self, db, ref_date):
        metrics = compute_property_metrics(db, PROP_A_ID, CONFIG_DICT, ref_date)
        for ut_code, ut_m in metrics["unit_type_metrics"].items():
            assert "elasticity" in ut_m
            assert "confidence" in ut_m["elasticity"]

    def test_metrics_include_optimal_pricing(self, db, ref_date):
        metrics = compute_property_metrics(db, PROP_A_ID, CONFIG_DICT, ref_date)
        for ut_code, ut_m in metrics["unit_type_metrics"].items():
            assert "optimal_pricing" in ut_m
            assert "optimal_asking" in ut_m["optimal_pricing"]

    def test_metrics_include_revenue_gap(self, db, ref_date):
        metrics = compute_property_metrics(db, PROP_A_ID, CONFIG_DICT, ref_date)
        for ut_code, ut_m in metrics["unit_type_metrics"].items():
            assert "revenue_gap" in ut_m
            assert "dominant_lever" in ut_m["revenue_gap"]

    def test_metrics_include_revenue_efficiency(self, db, ref_date):
        metrics = compute_property_metrics(db, PROP_A_ID, CONFIG_DICT, ref_date)
        for ut_code, ut_m in metrics["unit_type_metrics"].items():
            assert "revenue_efficiency" in ut_m
            assert "grade" in ut_m["revenue_efficiency"]
```

- [ ] **Step 5: Run tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_metrics_engine.py -v`
Expected: All existing tests pass + 4 new tests pass

- [ ] **Step 6: Run full suite**

Run: `cd backend && .venv/bin/python -m pytest tests/ -q`
Expected: 234+ passed

- [ ] **Step 7: Commit**

```
feat: integrate revenue optimizer into metrics engine

Metrics now include elasticity, optimal pricing, revenue gap
decomposition, renewal opportunity, and revenue efficiency per unit type.
```

---

## Task 5: Flag Generator Rebalancing

**Files:**
- Modify: `backend/app/services/flag_generator.py`
- Modify: `backend/tests/test_flag_generator.py`

- [ ] **Step 1: Reclassify `OCCUPANCY_PUSH_ELIGIBLE` severity**

Change severity from `"POSITIVE"` to `"HIGH"` (around line 54-58).

- [ ] **Step 2: Tighten `RENEWAL_FREEZE_RECOMMENDED` threshold**

Change occupancy threshold from `0.88` to reading from config with default `0.82` (around line 216-223). Read from `config.get("renewal_policy", {}).get("freeze_below_occupancy", 0.82)`.

- [ ] **Step 3: Make `CONCESSION_TRIGGER` conditional**

Around line 144-153, add logic: if occupancy ≥ `config.get("concession_policy", {}).get("removal_occupancy_threshold", 0.93)`, generate `CONCESSION_REMOVAL_ELIGIBLE` flag instead.

- [ ] **Step 4: Add 6 new flag rules**

After the existing flag rules (before MAB_ELIGIBLE), add the 6 new flags as specified in spec Section 3. Each reads its threshold from the config dict with sensible defaults.

- [ ] **Step 5: Update expected flag counts in tests**

Update `backend/tests/test_flag_generator.py`:
- A1: 3 → 6 flags (add OCCUPANCY_PUSH_ELIGIBLE at HIGH, RENT_PUSH_OPPORTUNITY, HIGH_LTL_CAPTURE, RENEWAL_INCREASE_ELIGIBLE)
- A2: 7 → 6 flags (lose RENEWAL_FREEZE due to threshold change from 0.88→0.82; A2 at 0.86 no longer triggers)
- B1: 12 → 10 flags (some flags may change with reclassifications — verify against actual triggers)
- B2: 7 → 7 flags

- [ ] **Step 6: Add tests for new flags**

Add test methods for each new flag verifying: trigger conditions, severity, and that they DON'T fire when conditions aren't met.

- [ ] **Step 7: Run flag generator tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_flag_generator.py -v`
Expected: All pass with updated counts

- [ ] **Step 8: Run full suite**

Run: `cd backend && .venv/bin/python -m pytest tests/ -q`
Expected: All pass

- [ ] **Step 9: Commit**

```
feat: rebalance flag generator for revenue optimization

6 new revenue-capture flags, 3 reclassifications.
Flag ratio changes from 10:1 (down:up) to ~1.3:1.
```

---

## Task 6: Bidirectional Experiments + Action Plan

**Files:**
- Modify: `backend/app/services/action_plan_service.py`
- Modify: `backend/tests/test_action_plan.py`

- [ ] **Step 1: Write failing tests for bidirectional experiments**

Add to `backend/tests/test_action_plan.py`:

```python
class TestBidirectionalExperiments:
    def test_upward_direction_when_underpriced(self):
        """When asking < optimal AND occ ≥ 92%, direction = UP."""
        # ... provide A1-like metrics with optimal > asking and occ 96%
        assert design["direction"] == "UP"

    def test_downward_direction_when_overpriced(self):
        """When asking > optimal AND gap > 3%, direction = DOWN."""
        # ... provide B1-like metrics
        assert design["direction"] == "DOWN"

    def test_no_experiment_when_at_optimal(self):
        """When asking ≈ optimal (within 3%), no experiment recommended."""
        assert recommendation == "NOT_ELIGIBLE_AT_OPTIMAL"

    def test_upward_max_spread_tighter(self):
        """Upward experiments: max 5% or $75 (tighter than downward 6%/$100)."""
        # ... verify spread constraint

    def test_occupancy_gate_for_upward(self):
        """Don't test up when occ < 92%."""
        assert design["direction"] == "DOWN"  # despite asking < optimal

    def test_revenue_per_day_convergence_metric(self):
        """Convergence uses revenue_per_day = rent / (vacancy_days + 1)."""
        assert design["convergence_metric"] == "revenue_per_unit_per_day"

    def test_early_termination_for_upward(self):
        """Upward tests have 21-day early termination."""
        assert design["early_termination_days"] == 21
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement bidirectional experiment logic**

Modify `_design_experiment()` in `action_plan_service.py`:
- Add direction detection based on asking vs optimal price
- Add upward experiment arm design with tighter spread (5%/$75)
- Add revenue-per-day convergence fields to output
- Add early termination for upward tests (21 days)
- Add occupancy gate (92%) for upward direction

- [ ] **Step 4: Run tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_action_plan.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```
feat: add bidirectional experiment design

Experiments now test higher prices when occ ≥ 92% and asking < optimal.
Convergence metric changes from velocity to revenue-per-unit-per-day.
```

---

## Task 7: Diagnostic Service — Prompts + Fallback

**Files:**
- Modify: `backend/app/services/diagnostic_service.py`
- Modify: `backend/app/services/narrative_service.py`
- Modify: `backend/tests/test_diagnostic_service.py`

- [ ] **Step 1: Update `DIAGNOSIS_SYSTEM_PROMPT`**

Replace the flag-count scoring rubric with revenue-efficiency scoring guidance per spec Section 5. Claude receives pre-computed scores and grades — it adds judgment, not math.

- [ ] **Step 2: Update `ACTION_PLAN_SYSTEM_PROMPT`**

Replace "stabilization" framing with revenue optimization framing. Phase structure adapts to dominant problem (CRISIS→fill, OPPORTUNITY→push rents). Add new action types per spec Section 5.

- [ ] **Step 3: Update fallback diagnosis function**

Replace flag-counting fallback with revenue-gap-based fallback:
- Rank unit types by `revenue_gap.total_gap_monthly`
- For each, recommend `revenue_gap.dominant_lever` action with dollar amounts
- Grade from `revenue_efficiency.grade`

- [ ] **Step 4: Update narrative prompts**

In `narrative_service.py`, update `DIAGNOSTIC_NARRATIVE_PROMPT` and `ACTION_NARRATIVE_PROMPT` to reference revenue efficiency grades, gap decomposition, and renewal capture.

- [ ] **Step 5: Update diagnostic tests**

Modify `test_diagnostic_service.py` to expect revenue-efficiency-based grades and gap-based fallback recommendations.

- [ ] **Step 6: Run tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_diagnostic_service.py tests/test_narrative_service.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```
feat: update Claude prompts for revenue optimization

Diagnosis uses revenue efficiency scores, not flag counts.
Action plan adapts phase structure to dominant revenue lever.
Fallback produces gap-based recommendations with dollar amounts.
```

---

## Task 8: Viz Data + Slide Deck Services

**Files:**
- Modify: `backend/app/services/viz_data_service.py`
- Modify: `backend/app/services/slide_deck_service.py`
- Modify: `backend/tests/test_viz_data_service.py`

- [ ] **Step 1: Modify existing viz generators**

In `viz_data_service.py`:
- `generate_score_gauge()`: Zone labels → CRISIS/DISTRESSED/IMBALANCED/OPPORTUNITY/OPTIMIZED
- `generate_kpi_cards()`: 4 → 6 cards (add Revenue Gap, Renewal Opportunity)
- `generate_data_table()`: Add optimal_asking, revenue_gap, elasticity_confidence columns
- `generate_rent_waterfall()`: Add Optimal bar between Predicted and Asking
- `generate_line_charts()`: Add optimal price trend line

- [ ] **Step 2: Add new viz generators**

Add to `viz_data_service.py`:
- `generate_revenue_gap_waterfall(revenue_gap)`: Waterfall from Current → +Fill → +Reprice → +Renew → −Concessions → Optimal
- `generate_revenue_roadmap(revenue_gap, action_plan)`: Before/after bars with per-lever amounts
- `generate_dimension_breakdown(revenue_efficiency)`: Horizontal stacked bar of occ/pricing/momentum

- [ ] **Step 3: Remove `generate_stacked_bar()`**

Delete the function. Update any imports that reference it.

- [ ] **Step 4: Update slide deck assembly**

In `slide_deck_service.py`:
- Slide 2: Pass dimension breakdown to viz_data
- Slide 7: Replace `generate_stacked_bar()` call with `generate_revenue_gap_waterfall()`
- Slide 12: Call `generate_revenue_roadmap()` for per-lever before/after

- [ ] **Step 5: Update viz data tests**

Modify `test_viz_data_service.py` to verify:
- Score gauge has new zone labels
- KPI cards count is 6
- Rent waterfall includes Optimal bar
- Revenue gap waterfall returns correct structure
- Dimension breakdown returns 3 dimensions with weights

- [ ] **Step 6: Run tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_viz_data_service.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```
feat: restructure viz data and slide deck for revenue optimization

Score gauge, KPI cards, waterfalls, and trend charts now show
revenue-aware content. New revenue gap waterfall and dimension breakdown.
```

---

## Task 9: Portfolio Services Alignment

**Files:**
- Modify: `backend/app/engine/aggregator.py`
- Modify: `backend/app/services/portfolio_diagnostic_service.py`
- Modify: `backend/app/services/portfolio_viz_data_service.py`
- Modify: `backend/app/services/portfolio_slide_deck_service.py`
- Modify: `backend/tests/test_portfolio_diagnostic.py`

- [ ] **Step 1: Extend `aggregate_cross_property()` with revenue metrics**

In `aggregator.py`, after existing aggregation (line 176+), add:
- `total_revenue_gap`: sum of all unit type revenue gaps
- `total_optimal_revenue`: sum of per-unit-type optimal revenue
- `portfolio_revenue_efficiency`: `sum(current) / sum(optimal) × 100`
- `total_renewal_opportunity`: sum across unit types

- [ ] **Step 2: Update portfolio diagnostic prompts**

Align `portfolio_diagnostic_service.py` prompts with revenue-efficiency framing (same pattern as Task 7 but portfolio-scoped).

- [ ] **Step 3: Update portfolio viz data**

In `portfolio_viz_data_service.py`:
- Update `generate_portfolio_kpi_cards()` to include revenue gap and renewal opportunity
- Add `generate_portfolio_revenue_gap_waterfall()`
- Update `generate_portfolio_stacked_bar()` → replace with revenue gap waterfall or update to show revenue metrics

- [ ] **Step 4: Update portfolio slide deck**

Restructure portfolio slides to match per-property restructuring (same principle — unified revenue view).

- [ ] **Step 5: Run portfolio tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_portfolio_diagnostic.py -v`
Expected: All pass

- [ ] **Step 6: Run full suite**

Run: `cd backend && .venv/bin/python -m pytest tests/ -q`
Expected: 240+ passed

- [ ] **Step 7: Commit**

```
feat: align portfolio services with revenue optimization

Portfolio aggregation includes revenue gap, efficiency, and renewal
opportunity. Portfolio slides restructured for unified revenue view.
```

---

## Task 10: Frontend — Charts + Slide Components

**Files:**
- Create: `frontend/src/components/slideshow/charts/RevenueGapWaterfall.jsx`
- Create: `frontend/src/components/slideshow/charts/DimensionBreakdownChart.jsx`
- Create: `frontend/src/components/slideshow/charts/RevenueRoadmapBars.jsx`
- Modify: `frontend/src/components/slideshow/charts/ScoreGauge.jsx`
- Modify: `frontend/src/components/slideshow/charts/RentWaterfall.jsx`
- Modify: `frontend/src/components/slideshow/charts/BeforeAfter.jsx`
- Modify: 6 slide components (ExecutiveSummary, PortfolioSnapshot, PropertyDeepDive, TrendAnalysis, RevenueAtRisk, Summary)

- [ ] **Step 1: Create `RevenueGapWaterfall.jsx`**

New Recharts horizontal waterfall chart showing revenue gap decomposition. Data structure: array of `{label, amount, color, type}` segments from Current to Optimal.

- [ ] **Step 2: Create `DimensionBreakdownChart.jsx`**

New Recharts horizontal stacked bar showing three dimensions (occ_health, pricing_alignment, momentum) with weights and scores.

- [ ] **Step 3: Create `RevenueRoadmapBars.jsx`**

New component showing before/after revenue bars with per-lever contributions labeled.

- [ ] **Step 4: Update `ScoreGauge.jsx`**

Change zone labels from CRITICAL/ACTION/WATCH/HEALTHY to CRISIS/DISTRESSED/IMBALANCED/OPPORTUNITY/OPTIMIZED with updated colors.

- [ ] **Step 5: Update `RentWaterfall.jsx`**

Add Optimal bar with distinct color (#7C3AED purple) between Predicted and Asking.

- [ ] **Step 6: Update `BeforeAfter.jsx`**

Show revenue decomposition: per-lever dollar amounts instead of just occupancy before/after.

- [ ] **Step 7: Update slide components**

Update all 6 slide components to render the new chart components and data:
- `ExecutiveSummarySlide.jsx`: 6 KPI cards + dimension breakdown
- `PortfolioSnapshotSlide.jsx`: Revenue columns in data table
- `PropertyDeepDiveSlide.jsx`: Optimal bar in waterfall + dimension cards
- `TrendAnalysisSlide.jsx`: Optimal price trend line
- `RevenueAtRiskSlide.jsx`: Revenue gap waterfall replacing vacancy cost bar
- `SummarySlide.jsx`: Revenue roadmap

- [ ] **Step 8: Build frontend**

Run: `cd frontend && npx react-scripts build`
Expected: Compiled successfully

- [ ] **Step 9: Commit**

```
feat: add revenue optimization frontend components

3 new chart components (RevenueGapWaterfall, DimensionBreakdown,
RevenueRoadmapBars). 3 modified charts. 6 updated slide components.
```

---

## Task 11: Backward Compatibility + Full Verification

**Files:**
- Create: `backend/tests/test_backward_compatibility.py`

- [ ] **Step 1: Write backward compatibility tests**

Create `backend/tests/test_backward_compatibility.py`:

```python
"""Tests for graceful degradation with old metrics format."""
from app.services.slide_deck_service import assemble_slide_deck

OLD_METRICS = {
    "property_name": "Test Property",
    "unit_type_metrics": {
        "A1": {
            "occupancy_metrics": {"occupancy_rate": 0.96, "total_units": 48, "occupied": 46, "vacant": 2},
            "pricing_spreads": {"asking_rent": 1365, "predicted_rent": 1329, "comps_rent": 1353,
                                "base_rent": 1240, "amenity_price": 89, "in_place_rent": 1269},
            "revenue_metrics": {"daily_vacancy_burn": 91, "monthly_vacancy_cost": 2730},
            # NOTE: no elasticity, optimal_pricing, revenue_gap, revenue_efficiency sections
        }
    },
}


def test_slide_assembly_with_old_metrics():
    """Slide deck should build (degraded) even without new revenue sections."""
    deck = assemble_slide_deck(
        run_id="test",
        property_name="Test",
        metrics=OLD_METRICS,
        diagnosis={"unit_type_assessments": []},
        action_plan={"phases": []},
    )
    assert len(deck["slides"]) == 12
    for slide in deck["slides"]:
        assert "slide_number" in slide
```

- [ ] **Step 2: Run to verify**

Run: `cd backend && .venv/bin/python -m pytest tests/test_backward_compatibility.py -v`
Expected: Pass (may need to add `.get()` guards in slide deck service for new sections)

- [ ] **Step 3: Run full backend suite**

Run: `cd backend && .venv/bin/python -m pytest tests/ -v`
Expected: 250+ passed (203 existing + ~50 new)

- [ ] **Step 4: Build frontend**

Run: `cd frontend && npx react-scripts build`
Expected: Compiled successfully

- [ ] **Step 5: Manual verification**

Start backend + frontend:
```bash
cd backend && .venv/bin/uvicorn app.main:app --reload &
cd frontend && npm start &
```

Verify:
1. Login with demo@example.com / demo123
2. Run per-property diagnostic → slideshow opens with restructured slides
3. Slide 2: Revenue Efficiency gauge (not health score), 6 KPI cards including Revenue Gap
4. Slides 4-5: Rent waterfalls include Optimal bar; score cards show 3-dimension breakdown
5. Slide 7: Revenue gap waterfall (not vacancy cost bar) — shows Fill/Reprice/Renew/De-Concession levers
6. Slide 12: Revenue Roadmap with per-lever dollar amounts
7. Run Portfolio Diagnosis → portfolio slideshow with revenue efficiency ranking
8. Per-property diagnostic still works with correct grades (OPPORTUNITY for A1, CRISIS for B1)
9. Keyboard navigation works in both slideshows

- [ ] **Step 6: Update CLAUDE.md**

Update the following sections:
- Expected flag counts: A1=6, A2=6, B1=10, B2=7
- Unit type archetypes: Update expected grades to new system (OPTIMIZED/OPPORTUNITY/IMBALANCED/DISTRESSED/CRISIS)
- Slide deck description: 12 slides with revenue-aware content

- [ ] **Step 7: Update progress.md and decisions.md**

- [ ] **Step 8: Final commit**

```
feat: revenue optimization redesign complete

Full pipeline: implied elasticity → optimal pricing → revenue gap
decomposition → dynamic scoring → bidirectional experiments → renewal
optimization → restructured slides. All tests passing, frontend clean.
```
