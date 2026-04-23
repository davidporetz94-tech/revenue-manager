"""Test action plan service — validates revenue math, experiment allocation, and phase sequencing."""
from datetime import date

import pytest

from app.database import SessionLocal
from app.models.property import Property
from app.models.config import ClientConfig
from app.services.metrics_engine import compute_property_metrics
from app.services.flag_generator import generate_flags
from app.services.action_plan_service import (
    build_action_plan_context,
    _detect_experiment_direction,
    _design_experiment,
)

REF_DATE = date(2026, 3, 15)


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


def _get_context(db, prop_code: str) -> dict:
    prop = db.query(Property).filter_by(code=prop_code).first()
    config = db.query(ClientConfig).filter_by(property_id=prop.id, is_active=True).first()
    config_dict = {k: getattr(config, k) or {} for k in [
        "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
        "concession_policy", "renewal_policy", "lease_term_policy",
        "experiment_policy", "amenity_benchmarks",
    ]}
    metrics = compute_property_metrics(db, str(prop.id), config_dict, REF_DATE)
    all_flags = {code: generate_flags(m, config_dict) for code, m in metrics["unit_type_metrics"].items()}
    return build_action_plan_context(metrics, all_flags, config_dict)


class TestRevenuemath:
    """Validate all revenue math is computed correctly in Python."""

    def test_a1_daily_burn(self, db):
        ctx = _get_context(db, "PROP-A")
        assert ctx["revenue_facts"]["unit_type_revenue"]["A1"]["daily_vacancy_burn"] == 91

    def test_a2_daily_burn(self, db):
        ctx = _get_context(db, "PROP-A")
        assert ctx["revenue_facts"]["unit_type_revenue"]["A2"]["daily_vacancy_burn"] == 235

    def test_b1_daily_burn(self, db):
        ctx = _get_context(db, "PROP-B")
        assert ctx["revenue_facts"]["unit_type_revenue"]["B1"]["daily_vacancy_burn"] == 254

    def test_b2_daily_burn(self, db):
        ctx = _get_context(db, "PROP-B")
        assert ctx["revenue_facts"]["unit_type_revenue"]["B2"]["daily_vacancy_burn"] == 331

    def test_property_b_total_daily_burn(self, db):
        ctx = _get_context(db, "PROP-B")
        assert ctx["revenue_facts"]["total_daily_burn"] == 254 + 331  # 585

    def test_property_b_monthly_cost(self, db):
        ctx = _get_context(db, "PROP-B")
        b1_cost = ctx["revenue_facts"]["unit_type_revenue"]["B1"]["monthly_vacancy_cost"]
        b2_cost = ctx["revenue_facts"]["unit_type_revenue"]["B2"]["monthly_vacancy_cost"]
        assert b1_cost == 7625  # 5 * 1525
        assert b2_cost == 9924  # 6 * 1654


class TestExperimentEligibility:
    """Validate experiment eligibility decisions."""

    def test_a1_not_eligible(self, db):
        """A1 has only 2 vacant — below min 3."""
        ctx = _get_context(db, "PROP-A")
        assert ctx["experiment_eligibility"]["A1"]["eligible"] is False
        assert ctx["experiment_eligibility"]["A1"]["recommendation"] == "NOT_ELIGIBLE_INSUFFICIENT_VACANT"

    def test_a2_eligible(self, db):
        """A2 has 5 vacant, 0.86 occ → eligible."""
        ctx = _get_context(db, "PROP-A")
        assert ctx["experiment_eligibility"]["A2"]["eligible"] is True
        assert ctx["experiment_eligibility"]["A2"]["recommendation"] == "RECOMMENDED"

    def test_b1_grade_suppressed(self, db):
        """B1 is CRISIS grade → experiment suppressed regardless of vacancy."""
        ctx = _get_context(db, "PROP-B")
        assert ctx["experiment_eligibility"]["B1"]["eligible"] is False
        assert ctx["experiment_eligibility"]["B1"]["grade_suppressed"] is True

    def test_b2_grade_suppressed(self, db):
        """B2 is DISTRESSED grade → experiment suppressed."""
        ctx = _get_context(db, "PROP-B")
        assert ctx["experiment_eligibility"]["B2"]["eligible"] is False
        assert ctx["experiment_eligibility"]["B2"]["grade_suppressed"] is True


class TestExperimentDesigns:
    """Validate experiment arm allocation and constraints."""

    def test_a2_two_arm(self, db):
        """A2 has 5 vacant, no CONCESSION_TRIGGER... wait, A2 DOES have it."""
        ctx = _get_context(db, "PROP-A")
        design = ctx["experiment_designs"].get("A2")
        assert design is not None
        arms = design["arms"]
        # A2 has 5 vacant + CONCESSION_TRIGGER flag, but < 6 for 3-arm
        total_units = sum(a["units_allocated"] for a in arms)
        assert total_units == 5

    def test_b2_no_experiment_design_grade_suppressed(self, db):
        """B2 is DISTRESSED grade → no experiment design generated."""
        ctx = _get_context(db, "PROP-B")
        assert "B2" not in ctx["experiment_designs"]
        assert ctx["experiment_eligibility"]["B2"]["eligible"] is False

    def test_b1_no_experiment_design_grade_suppressed(self, db):
        """B1 is CRISIS grade → no experiment design generated."""
        ctx = _get_context(db, "PROP-B")
        assert "B1" not in ctx["experiment_designs"]
        assert ctx["experiment_eligibility"]["B1"]["eligible"] is False

    def test_no_arm_has_zero_units(self, db):
        """Every arm in every experiment must have at least 1 unit."""
        for prop_code in ("PROP-A", "PROP-B"):
            ctx = _get_context(db, prop_code)
            for code, design in ctx["experiment_designs"].items():
                for arm in design["arms"]:
                    assert arm["units_allocated"] >= 1, \
                        f"{code} arm {arm['label']} has 0 units"


class TestBidirectionalExperiments:
    """Validate bidirectional experiment design — upward and downward."""

    def test_upward_direction_when_underpriced(self):
        """A1-like scenario: occ 96%, asking < optimal → direction UP."""
        # Synthetic: 96% occ, asking $1365, optimal $1427 (gap ~4.5%)
        optimal_pricing = {"optimal_asking": 1427.0, "price_direction": "INCREASE"}
        direction = _detect_experiment_direction(
            asking=1365.0, occ=0.96, optimal_pricing=optimal_pricing,
        )
        assert direction == "UP"

    def test_downward_direction_when_overpriced(self, db):
        """A2: occ 86%, asking > optimal → direction DOWN."""
        ctx = _get_context(db, "PROP-A")
        design = ctx["experiment_designs"].get("A2")
        assert design is not None
        assert design["direction"] == "DOWN"

    def test_no_experiment_at_optimal(self):
        """When asking within 3% of optimal, direction is NOT_ELIGIBLE_AT_OPTIMAL."""
        # asking=1400, optimal=1420 → gap = 1.4% < 3%
        optimal_pricing = {"optimal_asking": 1420.0, "price_direction": "HOLD"}
        direction = _detect_experiment_direction(
            asking=1400.0, occ=0.90, optimal_pricing=optimal_pricing,
        )
        assert direction == "NOT_ELIGIBLE_AT_OPTIMAL"

    def test_upward_max_spread_5pct(self):
        """Upward spread capped at 5% or $75, whichever is tighter."""
        # asking=1200, optimal=1500 → uncapped midpoint would be 1350 (12.5% above asking)
        # Max 5% of 1200 = $60, max $75. Tighter = $60. So test = 1200 + 60 = 1260.
        optimal_pricing = {"optimal_asking": 1500.0, "price_direction": "INCREASE"}
        design = _design_experiment(
            code="TEST", vacant=4, asking=1200.0, predicted=1300.0,
            comps=1350.0, max_spread_pct=0.06, max_spread_dollars=100,
            obs_window=14, has_critical=False, flag_types=set(),
            optimal_pricing=optimal_pricing, occ=0.95,
        )
        assert design["direction"] == "UP"
        assert design["spread_pct"] <= 5.0
        assert design["spread_dollars"] <= 75

    def test_occupancy_gate_prevents_upward(self):
        """Low occ blocks UP direction — uses unit test instead of B2 (now grade-suppressed)."""
        optimal_pricing = {"optimal_asking": 1838.0, "price_direction": "INCREASE"}
        direction = _detect_experiment_direction(
            asking=1654.0, occ=0.88, optimal_pricing=optimal_pricing,
        )
        # occ 0.88 < 0.92 gate → falls to DOWN
        assert direction == "DOWN"

    def test_convergence_metric_is_revenue_per_day(self, db):
        """All experiment outputs include revenue_per_unit_per_day convergence metric."""
        for prop_code in ("PROP-A", "PROP-B"):
            ctx = _get_context(db, prop_code)
            for code, design in ctx["experiment_designs"].items():
                assert design["convergence_metric"] == "revenue_per_unit_per_day"
                assert "revenue_per_day_control_estimate" in design
                assert "revenue_per_day_test_estimate" in design

    def test_early_termination_for_upward(self):
        """Upward tests have 21-day early termination."""
        optimal_pricing = {"optimal_asking": 1500.0, "price_direction": "INCREASE"}
        design = _design_experiment(
            code="TEST", vacant=4, asking=1350.0, predicted=1400.0,
            comps=1450.0, max_spread_pct=0.06, max_spread_dollars=100,
            obs_window=14, has_critical=False, flag_types=set(),
            optimal_pricing=optimal_pricing, occ=0.95,
        )
        assert design["direction"] == "UP"
        assert design["early_termination_days"] == 21

    def test_crisis_skips_experiment(self):
        """Below 82% occ with optimal_pricing: direction is CRISIS_DIRECT_ACTION."""
        optimal_pricing = {"optimal_asking": 1400.0, "price_direction": "DECREASE"}
        direction = _detect_experiment_direction(
            asking=1500.0, occ=0.78, optimal_pricing=optimal_pricing,
        )
        assert direction == "CRISIS_DIRECT_ACTION"

    def test_downward_unchanged_for_overpriced(self, db):
        """Existing downward behavior preserved: A2 test price < control price."""
        ctx = _get_context(db, "PROP-A")
        design = ctx["experiment_designs"]["A2"]
        assert design["direction"] == "DOWN"
        assert design["test_price"] < design["control_price"]
        # Early termination not set for downward experiments
        assert design["early_termination_days"] == 0

    def test_upward_test_price_is_halfway(self):
        """UP test arm: halfway between current asking and optimal."""
        # asking=1300, optimal=1400 → midpoint=1350
        optimal_pricing = {"optimal_asking": 1400.0, "price_direction": "INCREASE"}
        design = _design_experiment(
            code="TEST", vacant=4, asking=1300.0, predicted=1350.0,
            comps=1380.0, max_spread_pct=0.06, max_spread_dollars=100,
            obs_window=14, has_critical=False, flag_types=set(),
            optimal_pricing=optimal_pricing, occ=0.95,
        )
        assert design["direction"] == "UP"
        assert design["test_price"] == 1350  # halfway(1300, 1400)
        assert design["control_price"] == 1300.0

    def test_fallback_to_down_without_optimal_pricing(self):
        """Without optimal_pricing section, fall back to existing DOWN behavior."""
        direction = _detect_experiment_direction(
            asking=1400.0, occ=0.90, optimal_pricing=None,
        )
        assert direction == "DOWN"
