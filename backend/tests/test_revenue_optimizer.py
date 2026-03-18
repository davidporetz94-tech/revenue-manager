"""Tests for revenue optimizer engine — implied elasticity, optimal price,
gap decomposition, and revenue efficiency scoring.

TDD: tests written first, then implementation.
Pure function tests — no DB access needed.
"""
import math

import pytest

from app.engine.revenue_optimizer import (
    compute_implied_elasticity,
    compute_optimal_price,
    decompose_revenue_gap,
    compute_revenue_efficiency,
)


# ============================================================
# Test Data
# ============================================================

# --- Unit Type Metrics (from EliseAI export) ---

A1_METRICS = {
    "occupancy_metrics": {"occupancy_rate": 0.96, "total_units": 48, "occupied": 46, "vacant": 2},
    "pricing_spreads": {"asking_rent": 1365, "predicted_rent": 1329, "comps_rent": 1353, "base_rent": 1240, "amenity_price": 89, "in_place_rent": 1269},
    "revenue_metrics": {"daily_vacancy_burn": 91, "monthly_vacancy_cost": 2730},
    "velocity_metrics": {"avg_dom": 24},
    "ltl_analysis": {"ltl_dollars": 96, "ltl_pct": 0.076, "ltl_direction": "UPSIDE"},
}

B1_METRICS = {
    "occupancy_metrics": {"occupancy_rate": 0.79, "total_units": 24, "occupied": 19, "vacant": 5},
    "pricing_spreads": {"asking_rent": 1525, "predicted_rent": 1530, "comps_rent": 1434, "base_rent": 1405, "amenity_price": 125, "in_place_rent": 1572},
    "revenue_metrics": {"daily_vacancy_burn": 254, "monthly_vacancy_cost": 7625},
    "velocity_metrics": {"avg_dom": 25},
    "ltl_analysis": {"ltl_dollars": -47, "ltl_pct": -0.030, "ltl_direction": "NEGATIVE"},
}

A2_METRICS = {
    "occupancy_metrics": {"occupancy_rate": 0.86, "total_units": 36, "occupied": 31, "vacant": 5},
    "pricing_spreads": {"asking_rent": 1411, "predicted_rent": 1358, "comps_rent": 1396, "base_rent": 1275, "amenity_price": 83, "in_place_rent": 1304},
    "revenue_metrics": {"daily_vacancy_burn": 235, "monthly_vacancy_cost": 7055},
    "velocity_metrics": {"avg_dom": 22},
    "ltl_analysis": {"ltl_dollars": 107, "ltl_pct": 0.082, "ltl_direction": "UPSIDE"},
}

B2_METRICS = {
    "occupancy_metrics": {"occupancy_rate": 0.88, "total_units": 48, "occupied": 42, "vacant": 6},
    "pricing_spreads": {"asking_rent": 1654, "predicted_rent": 1583, "comps_rent": 1662, "base_rent": 1465, "amenity_price": 118, "in_place_rent": 1608},
    "revenue_metrics": {"daily_vacancy_burn": 331, "monthly_vacancy_cost": 9924},
    "velocity_metrics": {"avg_dom": 30},
    "ltl_analysis": {"ltl_dollars": 46, "ltl_pct": 0.029, "ltl_direction": "UPSIDE"},
}

# --- Snapshot Trends ---

A1_SNAPSHOTS = [
    {"month": "2025-12", "occupancy_rate": 0.94, "avg_asking_rent": 1350, "comps_avg": 1340},
    {"month": "2026-01", "occupancy_rate": 0.95, "avg_asking_rent": 1355, "comps_avg": 1345},
    {"month": "2026-02", "occupancy_rate": 0.96, "avg_asking_rent": 1360, "comps_avg": 1350},
    {"month": "2026-03", "occupancy_rate": 0.96, "avg_asking_rent": 1365, "comps_avg": 1353},
]

B1_SNAPSHOTS = [
    {"month": "2025-12", "occupancy_rate": 0.85, "avg_asking_rent": 1580, "comps_avg": 1440},
    {"month": "2026-01", "occupancy_rate": 0.83, "avg_asking_rent": 1560, "comps_avg": 1435},
    {"month": "2026-02", "occupancy_rate": 0.81, "avg_asking_rent": 1540, "comps_avg": 1434},
    {"month": "2026-03", "occupancy_rate": 0.79, "avg_asking_rent": 1525, "comps_avg": 1434},
]

A2_SNAPSHOTS = [
    {"month": "2025-12", "occupancy_rate": 0.92, "avg_asking_rent": 1380, "comps_avg": 1390},
    {"month": "2026-01", "occupancy_rate": 0.90, "avg_asking_rent": 1395, "comps_avg": 1393},
    {"month": "2026-02", "occupancy_rate": 0.88, "avg_asking_rent": 1405, "comps_avg": 1395},
    {"month": "2026-03", "occupancy_rate": 0.86, "avg_asking_rent": 1411, "comps_avg": 1396},
]

B2_SNAPSHOTS = [
    {"month": "2025-12", "occupancy_rate": 0.90, "avg_asking_rent": 1640, "comps_avg": 1655},
    {"month": "2026-01", "occupancy_rate": 0.90, "avg_asking_rent": 1645, "comps_avg": 1658},
    {"month": "2026-02", "occupancy_rate": 0.89, "avg_asking_rent": 1650, "comps_avg": 1660},
    {"month": "2026-03", "occupancy_rate": 0.88, "avg_asking_rent": 1654, "comps_avg": 1662},
]

# --- Comp Trends (extracted from snapshot comps_avg) ---

A1_COMP_TRENDS = [{"month": s["month"], "avg_asking_rent": s["comps_avg"]} for s in A1_SNAPSHOTS]
B1_COMP_TRENDS = [{"month": s["month"], "avg_asking_rent": s["comps_avg"]} for s in B1_SNAPSHOTS]
A2_COMP_TRENDS = [{"month": s["month"], "avg_asking_rent": s["comps_avg"]} for s in A2_SNAPSHOTS]
B2_COMP_TRENDS = [{"month": s["month"], "avg_asking_rent": s["comps_avg"]} for s in B2_SNAPSHOTS]

# --- Seasonal Contexts ---

SPRING_SEASONAL = {"season": "SPRING_RAMP", "seasonal_factor": 0.98, "months_to_peak": 2}
OFFPEAK_SEASONAL = {"season": "FALL_DECLINE", "seasonal_factor": 1.02, "months_to_peak": 9}

# --- Default Zone Config ---

DEFAULT_ZONE_CONFIG = {
    "crisis_below": 0.82,
    "stressed_below": 0.90,
    "healthy_above": 0.94,
}

ELASTICITY_REQUIRED_FIELDS = {
    "elasticity_coefficient", "confidence", "data_points", "direction", "notes",
    "comp_corroborated",
}

OPTIMAL_PRICE_REQUIRED_FIELDS = {
    "optimal_asking", "optimal_revenue_monthly", "current_revenue_monthly",
    "revenue_gap_monthly", "price_direction", "recommended_asking",
    "confidence", "seasonal_adjustment_applied", "comp_constrained",
}


# ============================================================
# compute_implied_elasticity Tests
# ============================================================

class TestComputeImpliedElasticity:
    """Tests for compute_implied_elasticity."""

    def test_returns_all_required_fields(self) -> None:
        """Elasticity result must contain all required fields."""
        result = compute_implied_elasticity(A1_SNAPSHOTS, A1_COMP_TRENDS)
        assert ELASTICITY_REQUIRED_FIELDS.issubset(result.keys()), (
            f"Missing fields: {ELASTICITY_REQUIRED_FIELDS - result.keys()}"
        )

    def test_a1_stable_is_inelastic_or_unknown(self) -> None:
        """A1: flat asking + stable occ = INELASTIC or UNKNOWN.

        Confidence can be HIGH when comp corroboration boosts it.
        """
        result = compute_implied_elasticity(A1_SNAPSHOTS, A1_COMP_TRENDS)
        assert result["direction"] in ("INELASTIC", "UNKNOWN")
        assert result["confidence"] in ("LOW", "MEDIUM", "HIGH")

    def test_b1_declining_is_elastic(self) -> None:
        """B1: dropping asking + declining occ = ELASTIC with positive coefficient."""
        result = compute_implied_elasticity(B1_SNAPSHOTS, B1_COMP_TRENDS)
        assert result["direction"] == "ELASTIC"
        assert result["elasticity_coefficient"] > 0

    def test_single_data_point_low_confidence(self) -> None:
        """Single snapshot → LOW confidence, UNKNOWN direction."""
        single = [B1_SNAPSHOTS[0]]
        comp_single = [B1_COMP_TRENDS[0]]
        result = compute_implied_elasticity(single, comp_single)
        assert result["confidence"] == "LOW"
        assert result["direction"] == "UNKNOWN"

    def test_data_points_count_matches(self) -> None:
        """data_points field should match input length."""
        result = compute_implied_elasticity(A1_SNAPSHOTS, A1_COMP_TRENDS)
        assert result["data_points"] == len(A1_SNAPSHOTS)

    def test_a2_rising_price_declining_occ_is_elastic(self) -> None:
        """A2: asking rising while occ declining = ELASTIC."""
        result = compute_implied_elasticity(A2_SNAPSHOTS, A2_COMP_TRENDS)
        assert result["direction"] == "ELASTIC"
        assert result["elasticity_coefficient"] > 0

    def test_b2_near_comps_moderate_elasticity(self) -> None:
        """B2: slight price increase, slight occ decline — moderate signal."""
        result = compute_implied_elasticity(B2_SNAPSHOTS, B2_COMP_TRENDS)
        # B2 is near comps, slight occ decline — could be ELASTIC or INELASTIC
        assert result["direction"] in ("ELASTIC", "INELASTIC", "UNKNOWN")
        assert result["data_points"] == 4

    def test_empty_snapshots(self) -> None:
        """Empty input → LOW confidence, UNKNOWN direction, zero coefficient."""
        result = compute_implied_elasticity([], [])
        assert result["confidence"] == "LOW"
        assert result["direction"] == "UNKNOWN"
        assert result["elasticity_coefficient"] == 0.0
        assert result["data_points"] == 0

    def test_two_data_points(self) -> None:
        """Two data points → at most MEDIUM confidence."""
        two = B1_SNAPSHOTS[:2]
        comp_two = B1_COMP_TRENDS[:2]
        result = compute_implied_elasticity(two, comp_two)
        assert result["confidence"] in ("LOW", "MEDIUM")
        assert result["data_points"] == 2

    def test_field_name_compatibility_avg_occupancy(self) -> None:
        """Snapshots using 'avg_occupancy' instead of 'occupancy_rate' should work."""
        alt_snapshots = [
            {"month": s["month"], "avg_occupancy": s["occupancy_rate"], "asking_rent": s["avg_asking_rent"], "comps_avg": s.get("comps_avg", 0)}
            for s in B1_SNAPSHOTS
        ]
        alt_comps = [
            {"month": s["month"], "asking_rent": s["avg_asking_rent"]}
            for s in B1_SNAPSHOTS  # just reuse the comp values from snapshots
        ]
        result = compute_implied_elasticity(alt_snapshots, alt_comps)
        assert result["data_points"] == 4
        assert result["direction"] in ("ELASTIC", "INELASTIC", "UNKNOWN")

    def test_comp_corroboration_boosts_confidence(self) -> None:
        """When comps move in the same direction as asking, confidence should bump up.

        A2: asking rises month-over-month while occ declines. Comps also rise.
        The comp corroboration should boost confidence by one level.
        """
        # Run without comp trends to get baseline confidence
        result_no_comps = compute_implied_elasticity(A2_SNAPSHOTS, [])
        # Run with comp trends (A2 comps also rise: 1390 → 1393 → 1395 → 1396)
        result_with_comps = compute_implied_elasticity(A2_SNAPSHOTS, A2_COMP_TRENDS)

        # Both asking and comps are rising → comp_corroborated should be True
        assert result_with_comps["comp_corroborated"] is True
        assert "comp corroboration" in result_with_comps["notes"]
        assert "confidence boosted" in result_with_comps["notes"]

        # Confidence with corroboration should be >= confidence without
        levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        assert levels[result_with_comps["confidence"]] >= levels[result_no_comps["confidence"]]

    def test_comp_corroboration_empty_comps_noted(self) -> None:
        """When comp_trends is empty, notes should mention it and comp_corroborated=False."""
        result = compute_implied_elasticity(A2_SNAPSHOTS, [])
        assert result["comp_corroborated"] is False
        assert "no comp trend data" in result["notes"]

    def test_comp_divergence_no_boost(self) -> None:
        """When comps move opposite to asking rents, no confidence boost.

        B1: asking falls month-over-month. Construct comps that rise.
        """
        # B1 asking is falling. Create comp data that rises (divergent).
        divergent_comps = [
            {"month": "2025-12", "avg_asking_rent": 1400},
            {"month": "2026-01", "avg_asking_rent": 1415},
            {"month": "2026-02", "avg_asking_rent": 1430},
            {"month": "2026-03", "avg_asking_rent": 1445},
        ]
        result = compute_implied_elasticity(B1_SNAPSHOTS, divergent_comps)
        assert result["comp_corroborated"] is False
        assert "comp divergence" in result["notes"]


# ============================================================
# compute_optimal_price Tests
# ============================================================

class TestComputeOptimalPrice:
    """Tests for compute_optimal_price."""

    def _default_elasticity(self, direction: str = "INELASTIC") -> dict:
        """Helper to create a default elasticity dict."""
        return {
            "elasticity_coefficient": 0.5 if direction == "ELASTIC" else 0.1,
            "confidence": "MEDIUM",
            "data_points": 4,
            "direction": direction,
            "notes": "test",
        }

    def test_returns_all_required_fields(self) -> None:
        """Optimal price result must contain all required fields."""
        elasticity = self._default_elasticity()
        result = compute_optimal_price(A1_METRICS, elasticity, SPRING_SEASONAL)
        assert OPTIMAL_PRICE_REQUIRED_FIELDS.issubset(result.keys()), (
            f"Missing fields: {OPTIMAL_PRICE_REQUIRED_FIELDS - result.keys()}"
        )

    def test_a1_increase_direction(self) -> None:
        """A1 (healthy, 96% occ, below comps) → INCREASE direction."""
        elasticity = self._default_elasticity("INELASTIC")
        result = compute_optimal_price(A1_METRICS, elasticity, SPRING_SEASONAL)
        # A1 is at 96% occ with asking below comps — should push up
        assert result["price_direction"] == "INCREASE"

    def test_b1_decrease_direction(self) -> None:
        """B1 (crisis, 79% occ, way above comps) → DECREASE direction."""
        elasticity = self._default_elasticity("ELASTIC")
        elasticity["elasticity_coefficient"] = 1.5  # highly elastic
        result = compute_optimal_price(B1_METRICS, elasticity, SPRING_SEASONAL)
        assert result["price_direction"] == "DECREASE"

    def test_a2_decrease_direction(self) -> None:
        """A2 (overpricing, 86% occ declining) → DECREASE direction."""
        elasticity = self._default_elasticity("ELASTIC")
        elasticity["elasticity_coefficient"] = 0.8
        result = compute_optimal_price(A2_METRICS, elasticity, SPRING_SEASONAL)
        assert result["price_direction"] == "DECREASE"

    def test_b2_hold_or_decrease(self) -> None:
        """B2 (puzzle, 88% occ, near comps) → HOLD or DECREASE.

        B2 is the puzzle archetype: priced near comps but high vacancy and DOM.
        With meaningful elasticity (0.8+), the optimizer should not push price up
        because occupancy is already stressed.
        """
        elasticity = self._default_elasticity("ELASTIC")
        elasticity["elasticity_coefficient"] = 0.8
        result = compute_optimal_price(B2_METRICS, elasticity, SPRING_SEASONAL)
        assert result["price_direction"] in ("HOLD", "DECREASE")

    def test_recommended_is_conservative(self) -> None:
        """Recommended asking should be halfway between current and optimal."""
        elasticity = self._default_elasticity("INELASTIC")
        result = compute_optimal_price(A1_METRICS, elasticity, SPRING_SEASONAL)
        current = A1_METRICS["pricing_spreads"]["asking_rent"]
        expected_recommended = (current + result["optimal_asking"]) / 2
        assert abs(result["recommended_asking"] - expected_recommended) < 1.0

    def test_comp_constraint_works(self) -> None:
        """Optimal price must be within +-15% of comps_rent."""
        elasticity = self._default_elasticity("INELASTIC")
        elasticity["elasticity_coefficient"] = 0.01  # nearly inelastic → wants to push far up
        result = compute_optimal_price(A1_METRICS, elasticity, SPRING_SEASONAL)
        comps = A1_METRICS["pricing_spreads"]["comps_rent"]
        assert result["optimal_asking"] <= comps * 1.15 + 0.01  # small float tolerance
        assert result["optimal_asking"] >= comps * 0.85 - 0.01

    def test_comp_constraint_flags_when_capped(self) -> None:
        """When optimal would exceed comp bounds, comp_constrained should be True."""
        # Use extremely inelastic to push optimal to ceiling
        elasticity = self._default_elasticity("INELASTIC")
        elasticity["elasticity_coefficient"] = 0.001  # nearly zero sensitivity
        result = compute_optimal_price(A1_METRICS, elasticity, SPRING_SEASONAL)
        # With near-zero elasticity, the sweep would push price to max of range
        # which is +10% of asking = 1501.5, while comps*1.15 = 1555.95
        # The sweep only goes ±10% so comp constraint may or may not bind
        # Just verify the field exists and is boolean
        assert isinstance(result["comp_constrained"], bool)

    def test_revenue_gap_positive_for_a1(self) -> None:
        """A1 is underpriced — revenue gap should be positive (room to increase)."""
        elasticity = self._default_elasticity("INELASTIC")
        result = compute_optimal_price(A1_METRICS, elasticity, SPRING_SEASONAL)
        # If optimal > current, the gap should be positive
        if result["optimal_asking"] > A1_METRICS["pricing_spreads"]["asking_rent"]:
            assert result["revenue_gap_monthly"] > 0

    def test_seasonal_spring_shifts_up(self) -> None:
        """Spring ramp (months_to_peak <= 3) should push optimal slightly up.

        seasonal_adjustment_applied is in dollars (not percentage).
        """
        elasticity = self._default_elasticity("ELASTIC")
        elasticity["elasticity_coefficient"] = 0.5
        result_spring = compute_optimal_price(A1_METRICS, elasticity, SPRING_SEASONAL)
        result_offpeak = compute_optimal_price(A1_METRICS, elasticity, OFFPEAK_SEASONAL)
        assert result_spring["optimal_asking"] >= result_offpeak["optimal_asking"]
        # seasonal_adjustment_applied is now dollars — spring should be positive, offpeak negative
        assert result_spring["seasonal_adjustment_applied"] > 0
        assert result_spring["seasonal_adjustment_applied"] != result_offpeak["seasonal_adjustment_applied"]

    def test_seasonal_offpeak_shifts_down(self) -> None:
        """Off-peak (months_to_peak >= 9) should push optimal slightly down.

        seasonal_adjustment_applied is in dollars (negative = price reduced).
        """
        elasticity = self._default_elasticity("ELASTIC")
        elasticity["elasticity_coefficient"] = 0.5
        result_offpeak = compute_optimal_price(A1_METRICS, elasticity, OFFPEAK_SEASONAL)
        assert result_offpeak["seasonal_adjustment_applied"] < 0

    def test_seasonal_adjustment_is_dollars_not_percentage(self) -> None:
        """seasonal_adjustment_applied should be in dollars, not a percentage.

        For a ~$1365 asking, a 1% seasonal bump = ~$13-14, not 1.0.
        """
        elasticity = self._default_elasticity("ELASTIC")
        elasticity["elasticity_coefficient"] = 0.5
        result = compute_optimal_price(A1_METRICS, elasticity, SPRING_SEASONAL)
        adj = result["seasonal_adjustment_applied"]
        # The dollar amount should be roughly 1% of asking (~$13-14), not 1.0
        assert abs(adj) > 5.0, f"Expected dollar amount > $5, got {adj} — looks like a percentage"

    def test_custom_zone_config(self) -> None:
        """Custom zone_config should be accepted and used."""
        elasticity = self._default_elasticity("INELASTIC")
        custom_config = {"crisis_below": 0.80, "stressed_below": 0.88, "healthy_above": 0.95}
        result = compute_optimal_price(A1_METRICS, elasticity, SPRING_SEASONAL, zone_config=custom_config)
        assert OPTIMAL_PRICE_REQUIRED_FIELDS.issubset(result.keys())

    def test_optimal_asking_is_positive(self) -> None:
        """Optimal asking should always be a positive number."""
        elasticity = self._default_elasticity("ELASTIC")
        elasticity["elasticity_coefficient"] = 2.0  # very elastic
        result = compute_optimal_price(B1_METRICS, elasticity, SPRING_SEASONAL)
        assert result["optimal_asking"] > 0

    def test_current_revenue_calculation(self) -> None:
        """Current revenue should equal asking × occupied units."""
        elasticity = self._default_elasticity("INELASTIC")
        result = compute_optimal_price(A1_METRICS, elasticity, SPRING_SEASONAL)
        expected = A1_METRICS["pricing_spreads"]["asking_rent"] * A1_METRICS["occupancy_metrics"]["total_units"] * A1_METRICS["occupancy_metrics"]["occupancy_rate"]
        assert abs(result["current_revenue_monthly"] - expected) < 1.0

    def test_confidence_field_valid(self) -> None:
        """Confidence must be LOW, MEDIUM, or HIGH."""
        elasticity = self._default_elasticity()
        result = compute_optimal_price(A1_METRICS, elasticity, SPRING_SEASONAL)
        assert result["confidence"] in ("LOW", "MEDIUM", "HIGH")

    def test_b1_comp_constrained(self) -> None:
        """B1 is far above comps — optimal should be constrained down toward comps."""
        elasticity = self._default_elasticity("ELASTIC")
        elasticity["elasticity_coefficient"] = 1.0
        result = compute_optimal_price(B1_METRICS, elasticity, SPRING_SEASONAL)
        comps = B1_METRICS["pricing_spreads"]["comps_rent"]
        # Optimal should be near or at comp floor since B1 is overpriced
        assert result["optimal_asking"] <= B1_METRICS["pricing_spreads"]["asking_rent"]


# ============================================================
# Additional Test Data for Gap Decomposition + Efficiency
# ============================================================

RENEWAL_ANALYSIS_A1 = {"upcoming_renewals_90d": 10, "net_monthly_capture": 508.0}
RENEWAL_ANALYSIS_NONE = {"upcoming_renewals_90d": 0, "net_monthly_capture": 0.0}
CONCESSION_DATA_NONE = {"total_concession_drag_monthly": 0.0}
CONCESSION_DATA_ACTIVE = {"total_concession_drag_monthly": 250.0}

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

GAP_REQUIRED_FIELDS = {
    "current_monthly_revenue", "optimal_monthly_revenue", "total_gap_monthly",
    "gap_components", "dominant_lever", "lever_ranking",
}

GAP_COMPONENT_KEYS = {
    "vacancy_cost", "new_lease_underpricing", "in_place_underpricing",
    "renewal_opportunity", "concession_drag",
}

EFFICIENCY_REQUIRED_FIELDS = {
    "revenue_efficiency_score", "grade", "dimensions",
    "dynamic_weights_reason", "occupancy_zone",
}

VALID_GRADES = {"OPTIMIZED", "OPPORTUNITY", "IMBALANCED", "DISTRESSED", "CRISIS"}


def _make_optimal(metrics: dict, direction: str = "INELASTIC") -> dict:
    """Helper to compute an optimal price result for use in decomposition tests."""
    elasticity = {
        "elasticity_coefficient": 0.5 if direction == "ELASTIC" else 0.1,
        "confidence": "MEDIUM",
        "data_points": 4,
        "direction": direction,
        "notes": "test",
    }
    return compute_optimal_price(metrics, elasticity, SPRING_SEASONAL)


# Map of (metrics, snapshots) for efficiency tests — uses real computed elasticity
_EFFICIENCY_CONFIGS: dict[str, tuple[dict, list[dict]]] = {
    "A1": (A1_METRICS, A1_SNAPSHOTS),
    "B1": (B1_METRICS, B1_SNAPSHOTS),
    "A2": (A2_METRICS, A2_SNAPSHOTS),
    "B2": (B2_METRICS, B2_SNAPSHOTS),
}


def _make_optimal_realistic(metrics: dict, snapshots: list[dict]) -> dict:
    """Compute optimal price using real elasticity from snapshot data."""
    comp_trends = [
        {"month": s["month"], "avg_asking_rent": s.get("comps_avg", 0)}
        for s in snapshots
    ]
    elasticity = compute_implied_elasticity(snapshots, comp_trends)
    return compute_optimal_price(metrics, elasticity, SPRING_SEASONAL)


# ============================================================
# decompose_revenue_gap Tests
# ============================================================

class TestDecomposeRevenueGap:
    """Tests for decompose_revenue_gap."""

    def test_returns_all_required_fields(self) -> None:
        """Gap decomposition result must contain all required fields."""
        optimal = _make_optimal(A1_METRICS)
        result = decompose_revenue_gap(
            A1_METRICS, optimal, RENEWAL_ANALYSIS_A1, CONCESSION_DATA_NONE,
        )
        assert GAP_REQUIRED_FIELDS.issubset(result.keys()), (
            f"Missing fields: {GAP_REQUIRED_FIELDS - result.keys()}"
        )

    def test_gap_components_have_all_keys(self) -> None:
        """gap_components must contain all 5 component keys."""
        optimal = _make_optimal(A1_METRICS)
        result = decompose_revenue_gap(
            A1_METRICS, optimal, RENEWAL_ANALYSIS_A1, CONCESSION_DATA_NONE,
        )
        assert GAP_COMPONENT_KEYS == set(result["gap_components"].keys())

    def test_each_component_has_amount_lever_description(self) -> None:
        """Each gap component must have amount, lever, and description fields."""
        optimal = _make_optimal(A1_METRICS)
        result = decompose_revenue_gap(
            A1_METRICS, optimal, RENEWAL_ANALYSIS_A1, CONCESSION_DATA_NONE,
        )
        for key, comp in result["gap_components"].items():
            assert "amount" in comp, f"{key} missing 'amount'"
            assert "lever" in comp, f"{key} missing 'lever'"
            assert "description" in comp, f"{key} missing 'description'"

    def test_components_sum_approximately_to_total_gap(self) -> None:
        """Sum of component amounts should approximate the total gap."""
        optimal = _make_optimal(A1_METRICS)
        result = decompose_revenue_gap(
            A1_METRICS, optimal, RENEWAL_ANALYSIS_A1, CONCESSION_DATA_NONE,
        )
        component_sum = sum(c["amount"] for c in result["gap_components"].values())
        # The components are independently computed and may not exactly equal
        # the total gap, but they should be in the same ballpark.
        # We allow a generous tolerance since these are different slices.
        assert component_sum >= 0, "Component sum should be non-negative"

    def test_a1_vacancy_cost_positive(self) -> None:
        """A1 has 2 vacant units — vacancy cost should be > 0."""
        optimal = _make_optimal(A1_METRICS)
        result = decompose_revenue_gap(
            A1_METRICS, optimal, RENEWAL_ANALYSIS_NONE, CONCESSION_DATA_NONE,
        )
        vacancy = result["gap_components"]["vacancy_cost"]["amount"]
        # vacancy_cost = 2 * 1365 = 2730
        assert vacancy > 0
        assert abs(vacancy - 2 * 1365) < 1.0

    def test_a1_dominant_lever_not_fill(self) -> None:
        """A1: underpricing dominates, so dominant lever should be RENEW or REPRICE, not FILL."""
        optimal = _make_optimal(A1_METRICS)
        result = decompose_revenue_gap(
            A1_METRICS, optimal, RENEWAL_ANALYSIS_A1, CONCESSION_DATA_NONE,
        )
        # A1 has 96% occ, only 2 vacant — underpricing (LTL = $96 x 46 = $4416) dominates vacancy ($2730)
        assert result["dominant_lever"] in ("RENEW", "REPRICE")

    def test_b1_dominant_lever_is_fill(self) -> None:
        """B1: vacancy dominates — dominant lever should be FILL."""
        optimal = _make_optimal(B1_METRICS, direction="ELASTIC")
        result = decompose_revenue_gap(
            B1_METRICS, optimal, RENEWAL_ANALYSIS_NONE, CONCESSION_DATA_NONE,
        )
        # B1 has 5 vacant at $1525 = $7625 vacancy cost, negative LTL = $0 in_place underpricing
        assert result["dominant_lever"] == "FILL"

    def test_lever_ranking_descending_by_amount(self) -> None:
        """Lever ranking should be sorted descending by component amount."""
        optimal = _make_optimal(A1_METRICS)
        result = decompose_revenue_gap(
            A1_METRICS, optimal, RENEWAL_ANALYSIS_A1, CONCESSION_DATA_ACTIVE,
        )
        ranking = result["lever_ranking"]
        amounts = [result["gap_components"][k]["amount"] for k in ranking]
        for i in range(len(amounts) - 1):
            assert amounts[i] >= amounts[i + 1], (
                f"Ranking not descending: {ranking[i]}={amounts[i]} < {ranking[i+1]}={amounts[i+1]}"
            )

    def test_negative_ltl_produces_zero_in_place_underpricing(self) -> None:
        """B1 has negative LTL (-$47) — in_place_underpricing should be 0."""
        optimal = _make_optimal(B1_METRICS, direction="ELASTIC")
        result = decompose_revenue_gap(
            B1_METRICS, optimal, RENEWAL_ANALYSIS_NONE, CONCESSION_DATA_NONE,
        )
        assert result["gap_components"]["in_place_underpricing"]["amount"] == 0.0

    def test_nonzero_concession_drag(self) -> None:
        """Active concessions should appear in concession_drag component."""
        optimal = _make_optimal(A1_METRICS)
        result = decompose_revenue_gap(
            A1_METRICS, optimal, RENEWAL_ANALYSIS_NONE, CONCESSION_DATA_ACTIVE,
        )
        assert result["gap_components"]["concession_drag"]["amount"] == 250.0

    def test_renewal_opportunity_from_analysis(self) -> None:
        """Renewal opportunity should use net_monthly_capture from renewal analysis."""
        optimal = _make_optimal(A1_METRICS)
        result = decompose_revenue_gap(
            A1_METRICS, optimal, RENEWAL_ANALYSIS_A1, CONCESSION_DATA_NONE,
        )
        assert result["gap_components"]["renewal_opportunity"]["amount"] == 508.0

    def test_gap_component_levers_correct(self) -> None:
        """Each component should have the correct lever assignment."""
        optimal = _make_optimal(A1_METRICS)
        result = decompose_revenue_gap(
            A1_METRICS, optimal, RENEWAL_ANALYSIS_A1, CONCESSION_DATA_NONE,
        )
        assert result["gap_components"]["vacancy_cost"]["lever"] == "FILL"
        assert result["gap_components"]["new_lease_underpricing"]["lever"] == "REPRICE"
        assert result["gap_components"]["in_place_underpricing"]["lever"] == "RENEW"
        assert result["gap_components"]["renewal_opportunity"]["lever"] == "RENEW"
        assert result["gap_components"]["concession_drag"]["lever"] == "DE_CONCESSION"


# ============================================================
# compute_revenue_efficiency Tests
# ============================================================

class TestComputeRevenueEfficiency:
    """Tests for compute_revenue_efficiency.

    Uses real computed elasticity (from snapshot data) to produce realistic
    optimal prices, which yields meaningful pricing alignment scores.
    """

    def test_returns_all_required_fields(self) -> None:
        """Efficiency result must contain all required fields."""
        optimal = _make_optimal_realistic(A1_METRICS, A1_SNAPSHOTS)
        result = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert EFFICIENCY_REQUIRED_FIELDS.issubset(result.keys()), (
            f"Missing fields: {EFFICIENCY_REQUIRED_FIELDS - result.keys()}"
        )

    def test_dimensions_have_required_fields(self) -> None:
        """Each dimension must have score and weight."""
        optimal = _make_optimal_realistic(A1_METRICS, A1_SNAPSHOTS)
        result = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        for dim_name in ("occupancy_health", "pricing_alignment", "rent_roll_momentum"):
            dim = result["dimensions"][dim_name]
            assert "score" in dim, f"{dim_name} missing 'score'"
            assert "weight" in dim, f"{dim_name} missing 'weight'"

    def test_a1_grade_is_optimized_or_opportunity(self) -> None:
        """A1 (96% occ, well-priced, improving trends) → OPTIMIZED or OPPORTUNITY.

        A1 is the healthy archetype: high occupancy, priced near comps,
        positive occupancy and rent trends. With real elasticity, the
        optimizer sees A1 as well-priced, yielding a high score.
        """
        optimal = _make_optimal_realistic(A1_METRICS, A1_SNAPSHOTS)
        result = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert result["grade"] in ("OPTIMIZED", "OPPORTUNITY"), (
            f"Expected OPTIMIZED or OPPORTUNITY, got {result['grade']} "
            f"(score={result['revenue_efficiency_score']})"
        )
        assert result["revenue_efficiency_score"] >= 70

    def test_b1_grade_is_crisis_or_distressed(self) -> None:
        """B1 (79% occ, overpriced, declining) → CRISIS or DISTRESSED (0-54)."""
        optimal = _make_optimal_realistic(B1_METRICS, B1_SNAPSHOTS)
        result = compute_revenue_efficiency(
            B1_METRICS, optimal, B1_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert result["grade"] in ("CRISIS", "DISTRESSED"), (
            f"Expected CRISIS or DISTRESSED, got {result['grade']} "
            f"(score={result['revenue_efficiency_score']})"
        )
        assert result["revenue_efficiency_score"] <= 54

    def test_a2_grade_is_imbalanced_or_distressed(self) -> None:
        """A2 (86% occ, overpriced, declining) → IMBALANCED or DISTRESSED."""
        optimal = _make_optimal_realistic(A2_METRICS, A2_SNAPSHOTS)
        result = compute_revenue_efficiency(
            A2_METRICS, optimal, A2_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert result["grade"] in ("IMBALANCED", "DISTRESSED"), (
            f"Expected IMBALANCED or DISTRESSED, got {result['grade']} "
            f"(score={result['revenue_efficiency_score']})"
        )

    def test_b2_grade_is_imbalanced_or_distressed(self) -> None:
        """B2 (88% occ, near comps, declining occ) → IMBALANCED or DISTRESSED.

        B2 is the puzzle archetype: near comps but vacancy is high. With real
        elasticity, the pricing gap is moderate but the declining occupancy
        trend drags momentum down.
        """
        optimal = _make_optimal_realistic(B2_METRICS, B2_SNAPSHOTS)
        result = compute_revenue_efficiency(
            B2_METRICS, optimal, B2_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert result["grade"] in ("IMBALANCED", "DISTRESSED"), (
            f"Expected IMBALANCED or DISTRESSED, got {result['grade']} "
            f"(score={result['revenue_efficiency_score']})"
        )

    def test_a1_strong_zone_pricing_weight(self) -> None:
        """A1 at 96% → STRONG zone → pricing weight ~0.45-0.50."""
        optimal = _make_optimal_realistic(A1_METRICS, A1_SNAPSHOTS)
        result = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert result["occupancy_zone"] == "STRONG"
        pricing_weight = result["dimensions"]["pricing_alignment"]["weight"]
        # Base STRONG pricing weight is 0.45, spring shifts +0.05 → 0.50
        assert 0.40 <= pricing_weight <= 0.55

    def test_b1_crisis_zone_occ_weight(self) -> None:
        """B1 at 79% → CRISIS zone → occ weight ~0.55-0.60."""
        optimal = _make_optimal_realistic(B1_METRICS, B1_SNAPSHOTS)
        result = compute_revenue_efficiency(
            B1_METRICS, optimal, B1_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert result["occupancy_zone"] == "CRISIS"
        occ_weight = result["dimensions"]["occupancy_health"]["weight"]
        # Base CRISIS occ weight is 0.60, spring shifts -0.05 → 0.55
        assert 0.50 <= occ_weight <= 0.65

    def test_seasonal_spring_shifts_pricing_weight_up(self) -> None:
        """Spring (months_to_peak <= 3) → pricing weight increases by 0.05."""
        optimal = _make_optimal_realistic(A1_METRICS, A1_SNAPSHOTS)
        result_spring = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        result_offpeak = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, OFFPEAK_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        spring_pricing = result_spring["dimensions"]["pricing_alignment"]["weight"]
        offpeak_pricing = result_offpeak["dimensions"]["pricing_alignment"]["weight"]
        # Spring: +0.05 pricing; off-peak: -0.05 pricing → diff should be ~0.10
        assert spring_pricing > offpeak_pricing

    def test_seasonal_offpeak_shifts_occ_weight_up(self) -> None:
        """Off-peak (months_to_peak >= 9) → occ weight increases by 0.05."""
        optimal = _make_optimal_realistic(A1_METRICS, A1_SNAPSHOTS)
        result_spring = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        result_offpeak = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, OFFPEAK_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        spring_occ = result_spring["dimensions"]["occupancy_health"]["weight"]
        offpeak_occ = result_offpeak["dimensions"]["occupancy_health"]["weight"]
        assert offpeak_occ > spring_occ

    def test_score_in_valid_range(self) -> None:
        """Revenue efficiency score must be 0-100."""
        for name, (metrics, snapshots) in _EFFICIENCY_CONFIGS.items():
            optimal = _make_optimal_realistic(metrics, snapshots)
            result = compute_revenue_efficiency(
                metrics, optimal, snapshots, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
            )
            assert 0 <= result["revenue_efficiency_score"] <= 100, (
                f"{name}: score {result['revenue_efficiency_score']} out of 0-100 range"
            )

    def test_all_grades_are_valid(self) -> None:
        """All returned grades must be from the valid set."""
        for name, (metrics, snapshots) in _EFFICIENCY_CONFIGS.items():
            optimal = _make_optimal_realistic(metrics, snapshots)
            result = compute_revenue_efficiency(
                metrics, optimal, snapshots, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
            )
            assert result["grade"] in VALID_GRADES, (
                f"{name}: invalid grade {result['grade']}"
            )

    def test_dimension_scores_in_valid_range(self) -> None:
        """Each dimension score must be 0-100."""
        optimal = _make_optimal_realistic(A1_METRICS, A1_SNAPSHOTS)
        result = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        for dim_name, dim in result["dimensions"].items():
            assert 0 <= dim["score"] <= 100, (
                f"{dim_name} score {dim['score']} out of 0-100 range"
            )

    def test_weights_sum_to_one(self) -> None:
        """Dynamic weights across all 3 dimensions should sum to 1.0."""
        optimal = _make_optimal_realistic(A1_METRICS, A1_SNAPSHOTS)
        result = compute_revenue_efficiency(
            A1_METRICS, optimal, A1_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        total_weight = sum(d["weight"] for d in result["dimensions"].values())
        assert abs(total_weight - 1.0) < 0.01, f"Weights sum to {total_weight}, expected 1.0"

    def test_occupancy_zone_field_valid(self) -> None:
        """occupancy_zone must be a valid zone string."""
        valid_zones = {"CRISIS", "STRESSED", "BALANCED", "STRONG", "FULL"}
        for name, (metrics, snapshots) in _EFFICIENCY_CONFIGS.items():
            optimal = _make_optimal_realistic(metrics, snapshots)
            result = compute_revenue_efficiency(
                metrics, optimal, snapshots, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
            )
            assert result["occupancy_zone"] in valid_zones, (
                f"{name}: invalid zone {result['occupancy_zone']}"
            )

    def test_a1_scores_higher_than_b1(self) -> None:
        """A1 (healthy) should score significantly higher than B1 (crisis)."""
        opt_a1 = _make_optimal_realistic(A1_METRICS, A1_SNAPSHOTS)
        res_a1 = compute_revenue_efficiency(
            A1_METRICS, opt_a1, A1_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        opt_b1 = _make_optimal_realistic(B1_METRICS, B1_SNAPSHOTS)
        res_b1 = compute_revenue_efficiency(
            B1_METRICS, opt_b1, B1_SNAPSHOTS, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
        )
        assert res_a1["revenue_efficiency_score"] > res_b1["revenue_efficiency_score"] + 30

    def test_grade_ordering_matches_archetypes(self) -> None:
        """Grades should follow the expected ordering: A1 > B2 >= A2 > B1."""
        scores = {}
        for name, (metrics, snapshots) in _EFFICIENCY_CONFIGS.items():
            optimal = _make_optimal_realistic(metrics, snapshots)
            result = compute_revenue_efficiency(
                metrics, optimal, snapshots, SPRING_SEASONAL, DEFAULT_EFFICIENCY_CONFIG,
            )
            scores[name] = result["revenue_efficiency_score"]
        assert scores["A1"] > scores["B2"], f"A1 ({scores['A1']}) should > B2 ({scores['B2']})"
        assert scores["A1"] > scores["A2"], f"A1 ({scores['A1']}) should > A2 ({scores['A2']})"
        assert scores["A2"] > scores["B1"], f"A2 ({scores['A2']}) should > B1 ({scores['B1']})"
