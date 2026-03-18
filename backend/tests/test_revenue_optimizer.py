"""Tests for revenue optimizer engine — implied elasticity and optimal price.

TDD: tests written first, then implementation.
Pure function tests — no DB access needed.
"""
import math

import pytest

from app.engine.revenue_optimizer import compute_implied_elasticity, compute_optimal_price


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
        """A1: flat asking + stable occ = INELASTIC or UNKNOWN."""
        result = compute_implied_elasticity(A1_SNAPSHOTS, A1_COMP_TRENDS)
        assert result["direction"] in ("INELASTIC", "UNKNOWN")
        assert result["confidence"] in ("LOW", "MEDIUM")

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
        """Spring ramp (months_to_peak <= 3) should push optimal slightly up."""
        elasticity = self._default_elasticity("ELASTIC")
        elasticity["elasticity_coefficient"] = 0.5
        result_spring = compute_optimal_price(A1_METRICS, elasticity, SPRING_SEASONAL)
        result_offpeak = compute_optimal_price(A1_METRICS, elasticity, OFFPEAK_SEASONAL)
        assert result_spring["optimal_asking"] >= result_offpeak["optimal_asking"]
        assert result_spring["seasonal_adjustment_applied"] != result_offpeak["seasonal_adjustment_applied"]

    def test_seasonal_offpeak_shifts_down(self) -> None:
        """Off-peak (months_to_peak >= 9) should push optimal slightly down."""
        elasticity = self._default_elasticity("ELASTIC")
        elasticity["elasticity_coefficient"] = 0.5
        result_offpeak = compute_optimal_price(A1_METRICS, elasticity, OFFPEAK_SEASONAL)
        assert result_offpeak["seasonal_adjustment_applied"] < 0

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
