"""Tests for renewal optimizer engine — renewal increase recommendations
and revenue capture potential.

TDD: tests written first, then implementation.
Pure function tests — no DB access needed.
"""
import math

import pytest

from app.engine.renewal_optimizer import compute_renewal_opportunity


# ============================================================
# Test Data
# ============================================================

A1_METRICS = {
    "occupancy_metrics": {"occupancy_rate": 0.96, "total_units": 48, "occupied": 46, "vacant": 2},
    "pricing_spreads": {"asking_rent": 1365, "in_place_rent": 1269},
    "velocity_metrics": {"avg_dom": 24},
    "ltl_analysis": {"ltl_dollars": 96, "ltl_pct": 0.076, "ltl_direction": "UPSIDE"},
}

B1_METRICS = {
    "occupancy_metrics": {"occupancy_rate": 0.79, "total_units": 24, "occupied": 19, "vacant": 5},
    "pricing_spreads": {"asking_rent": 1525, "in_place_rent": 1572},
    "velocity_metrics": {"avg_dom": 25},
    "ltl_analysis": {"ltl_dollars": -47, "ltl_pct": -0.030, "ltl_direction": "NEGATIVE"},
}

A1_ELASTICITY = {"elasticity_coefficient": 0.3, "confidence": "LOW"}
B1_ELASTICITY = {"elasticity_coefficient": 1.5, "confidence": "MEDIUM"}

SPRING_SEASONAL = {"season": "SPRING_RAMP", "seasonal_factor": 0.98, "months_to_peak": 2}
OFFPEAK_SEASONAL = {"season": "FALL_DECLINE", "seasonal_factor": 1.02, "months_to_peak": 9}

REFERENCE_DATE = "2026-03-18"

# Units with upcoming lease_end for A1
A1_UNITS = [
    {"status": "occupied", "lease_end": "2026-04-15"},   # 28 days out — YES
    {"status": "occupied", "lease_end": "2026-05-01"},   # 44 days out — YES
    {"status": "occupied", "lease_end": "2026-06-01"},   # 75 days out — YES
    {"status": "occupied", "lease_end": "2026-03-25"},   # 7 days out — YES
    {"status": "occupied", "lease_end": "2026-04-20"},   # 33 days out — YES
    {"status": "occupied", "lease_end": "2026-09-01"},   # NOT within 90 days
    {"status": "vacant", "lease_end": None},              # vacant — skip
]

# Units with no upcoming renewals
EMPTY_UNITS: list[dict] = []

NO_RENEWAL_UNITS = [
    {"status": "occupied", "lease_end": "2026-12-01"},   # way out
    {"status": "vacant", "lease_end": None},
]

DEFAULT_RENEWAL_CONFIG = {
    "freeze_below_occupancy": 0.82,
    "make_ready_cost_estimate": 2500,
    "base_non_renewal_rate": 0.10,
    "increase_sensitivity_factor": 5.0,
    "max_turnover_probability": 0.60,
    "crisis_below": 0.82,
    "stressed_below": 0.89,
    "balanced_below": 0.94,
    "strong_below": 0.97,
}

RENEWAL_REQUIRED_FIELDS = {
    "upcoming_renewals_90d",
    "recommended_increase_pct",
    "recommended_increase_dollars",
    "gross_annual_capture",
    "estimated_turnover_probability",
    "estimated_turnover_cost",
    "net_annual_capture",
    "net_monthly_capture",
    "confidence",
}


# ============================================================
# Tests
# ============================================================

class TestComputeRenewalOpportunity:
    """Tests for compute_renewal_opportunity."""

    def test_returns_all_required_fields(self) -> None:
        """Renewal result must contain all required fields."""
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert RENEWAL_REQUIRED_FIELDS.issubset(result.keys()), (
            f"Missing fields: {RENEWAL_REQUIRED_FIELDS - result.keys()}"
        )

    def test_a1_recommends_increase_4_to_6_pct(self) -> None:
        """A1 (96% occ, 7.6% LTL upside, spring peak) -> 4-6% increase."""
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert 4.0 <= result["recommended_increase_pct"] <= 6.0, (
            f"Expected 4-6%, got {result['recommended_increase_pct']}%"
        )

    def test_b1_recommends_freeze(self) -> None:
        """B1 (79% occ) -> 0% increase (freeze)."""
        result = compute_renewal_opportunity(
            B1_METRICS, B1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert result["recommended_increase_pct"] == 0.0
        assert result["recommended_increase_dollars"] == 0.0

    def test_upcoming_renewals_count(self) -> None:
        """A1_UNITS should have exactly 5 upcoming renewals within 90 days."""
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert result["upcoming_renewals_90d"] == 5

    def test_turnover_probability_capped(self) -> None:
        """Turnover probability must not exceed max_turnover_probability."""
        extreme_config = {
            **DEFAULT_RENEWAL_CONFIG,
            "increase_sensitivity_factor": 100.0,  # extreme sensitivity
        }
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, extreme_config,
        )
        assert result["estimated_turnover_probability"] <= extreme_config["max_turnover_probability"]

    def test_no_upcoming_renewals_zero_capture_low_confidence(self) -> None:
        """No upcoming renewals -> 0 capture, LOW confidence."""
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            NO_RENEWAL_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert result["upcoming_renewals_90d"] == 0
        assert result["gross_annual_capture"] == 0.0
        assert result["net_annual_capture"] == 0.0
        assert result["net_monthly_capture"] == 0.0
        assert result["confidence"] == "LOW"

    def test_net_annual_capture_positive_for_a1(self) -> None:
        """A1 should have positive net annual capture (revenue from renewals)."""
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert result["net_annual_capture"] > 0

    def test_offpeak_lower_increase_than_peak(self) -> None:
        """Off-peak season -> lower recommended increase than peak for same unit type."""
        result_peak = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        result_offpeak = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, OFFPEAK_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert result_peak["recommended_increase_pct"] > result_offpeak["recommended_increase_pct"], (
            f"Peak ({result_peak['recommended_increase_pct']}%) should be > "
            f"off-peak ({result_offpeak['recommended_increase_pct']}%)"
        )

    def test_ltl_below_5pct_lower_increase(self) -> None:
        """LTL < 5% -> lower increase recommendation."""
        # Modify A1 metrics to have LTL below 5%
        low_ltl_metrics = {
            **A1_METRICS,
            "ltl_analysis": {"ltl_dollars": 50, "ltl_pct": 0.04, "ltl_direction": "UPSIDE"},
        }
        result_high_ltl = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        result_low_ltl = compute_renewal_opportunity(
            low_ltl_metrics, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert result_high_ltl["recommended_increase_pct"] > result_low_ltl["recommended_increase_pct"], (
            f"High LTL ({result_high_ltl['recommended_increase_pct']}%) should be > "
            f"low LTL ({result_low_ltl['recommended_increase_pct']}%)"
        )

    def test_confidence_inherited_from_elasticity(self) -> None:
        """Confidence should match elasticity confidence when renewals exist."""
        high_conf_elasticity = {"elasticity_coefficient": 0.3, "confidence": "HIGH"}
        result = compute_renewal_opportunity(
            A1_METRICS, high_conf_elasticity, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert result["confidence"] == "HIGH"

    def test_confidence_downgraded_to_low_without_renewals(self) -> None:
        """Even with HIGH elasticity confidence, no renewals -> LOW."""
        high_conf_elasticity = {"elasticity_coefficient": 0.3, "confidence": "HIGH"}
        result = compute_renewal_opportunity(
            A1_METRICS, high_conf_elasticity, SPRING_SEASONAL,
            NO_RENEWAL_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert result["confidence"] == "LOW"

    def test_increase_dollars_matches_pct(self) -> None:
        """recommended_increase_dollars should equal pct * in_place_rent."""
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        in_place = A1_METRICS["pricing_spreads"]["in_place_rent"]
        expected_dollars = result["recommended_increase_pct"] / 100 * in_place
        # Allow small rounding tolerance
        assert abs(result["recommended_increase_dollars"] - expected_dollars) < 1.0, (
            f"Expected ~{expected_dollars:.2f}, got {result['recommended_increase_dollars']}"
        )

    def test_gross_annual_capture_formula(self) -> None:
        """gross_annual = increase_dollars * renewals * 12."""
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        expected_gross = (
            result["recommended_increase_dollars"]
            * result["upcoming_renewals_90d"]
            * 12
        )
        assert abs(result["gross_annual_capture"] - expected_gross) < 1.0

    def test_net_less_than_gross(self) -> None:
        """Net annual capture should be less than or equal to gross."""
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert result["net_annual_capture"] <= result["gross_annual_capture"]

    def test_net_monthly_is_annual_divided_by_12(self) -> None:
        """net_monthly_capture = net_annual_capture / 12."""
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        if result["net_annual_capture"] > 0:
            expected_monthly = result["net_annual_capture"] / 12
            assert abs(result["net_monthly_capture"] - expected_monthly) < 1.0

    def test_empty_units_list(self) -> None:
        """Empty units list -> 0 renewals, 0 capture."""
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            EMPTY_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert result["upcoming_renewals_90d"] == 0
        assert result["net_annual_capture"] == 0.0

    def test_default_config_applied_when_empty(self) -> None:
        """Function should work with empty renewal_config (use defaults)."""
        result = compute_renewal_opportunity(
            A1_METRICS, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, {},
        )
        assert RENEWAL_REQUIRED_FIELDS.issubset(result.keys())

    def test_balanced_zone_peak_with_ltl_upside(self) -> None:
        """Balanced zone (89-94%) with LTL upside and peak -> 3-4%."""
        balanced_metrics = {
            "occupancy_metrics": {"occupancy_rate": 0.91, "total_units": 36, "occupied": 33, "vacant": 3},
            "pricing_spreads": {"asking_rent": 1400, "in_place_rent": 1300},
            "velocity_metrics": {"avg_dom": 20},
            "ltl_analysis": {"ltl_dollars": 100, "ltl_pct": 0.077, "ltl_direction": "UPSIDE"},
        }
        result = compute_renewal_opportunity(
            balanced_metrics, A1_ELASTICITY, SPRING_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert 3.0 <= result["recommended_increase_pct"] <= 4.0, (
            f"Expected 3-4%, got {result['recommended_increase_pct']}%"
        )

    def test_balanced_zone_offpeak(self) -> None:
        """Balanced zone (89-94%) off-peak -> 1-3% (use 2%)."""
        balanced_metrics = {
            "occupancy_metrics": {"occupancy_rate": 0.91, "total_units": 36, "occupied": 33, "vacant": 3},
            "pricing_spreads": {"asking_rent": 1400, "in_place_rent": 1300},
            "velocity_metrics": {"avg_dom": 20},
            "ltl_analysis": {"ltl_dollars": 100, "ltl_pct": 0.077, "ltl_direction": "UPSIDE"},
        }
        result = compute_renewal_opportunity(
            balanced_metrics, A1_ELASTICITY, OFFPEAK_SEASONAL,
            A1_UNITS, REFERENCE_DATE, DEFAULT_RENEWAL_CONFIG,
        )
        assert 1.0 <= result["recommended_increase_pct"] <= 3.0, (
            f"Expected 1-3%, got {result['recommended_increase_pct']}%"
        )
