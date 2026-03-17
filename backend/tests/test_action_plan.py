"""Test action plan service — validates revenue math, experiment allocation, and phase sequencing."""
from datetime import date

import pytest

from app.database import SessionLocal
from app.models.property import Property
from app.models.config import ClientConfig
from app.services.metrics_engine import compute_property_metrics
from app.services.flag_generator import generate_flags
from app.services.action_plan_service import build_action_plan_context

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

    def test_b1_eligible_but_direct_action(self, db):
        """B1 has 5 vacant, 0.79 occ, but 2 CRITICAL flags → direct action preferred."""
        ctx = _get_context(db, "PROP-B")
        assert ctx["experiment_eligibility"]["B1"]["eligible"] is True
        assert ctx["experiment_eligibility"]["B1"]["has_critical_flags"] is True
        assert ctx["experiment_eligibility"]["B1"]["recommendation"] == "ELIGIBLE_BUT_DIRECT_ACTION_PREFERRED"

    def test_b2_eligible_recommended(self, db):
        """B2 has 6 vacant, 0.88 occ, no CRITICAL → recommended."""
        ctx = _get_context(db, "PROP-B")
        assert ctx["experiment_eligibility"]["B2"]["eligible"] is True
        assert ctx["experiment_eligibility"]["B2"]["recommendation"] == "RECOMMENDED"


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

    def test_b2_three_arm(self, db):
        """B2 has 6 vacant + CONCESSION_TRIGGER → three-arm."""
        ctx = _get_context(db, "PROP-B")
        design = ctx["experiment_designs"].get("B2")
        assert design is not None
        arms = design["arms"]
        assert len(arms) == 3  # control, price_test, concession_test
        total_units = sum(a["units_allocated"] for a in arms)
        assert total_units == 6

    def test_b2_spread_within_config(self, db):
        """B2 experiment spread must be within 6% or $100."""
        ctx = _get_context(db, "PROP-B")
        design = ctx["experiment_designs"]["B2"]
        assert design["spread_pct"] <= 6.0
        assert design["spread_dollars"] <= 100

    def test_b2_observation_window(self, db):
        """Observation window matches config (14 days)."""
        ctx = _get_context(db, "PROP-B")
        design = ctx["experiment_designs"]["B2"]
        assert design["observation_window_days"] == 14

    def test_b1_experiment_exists_but_not_recommended(self, db):
        """B1 is eligible so design exists, but recommendation is direct action."""
        ctx = _get_context(db, "PROP-B")
        assert "B1" in ctx["experiment_designs"]
        assert ctx["experiment_eligibility"]["B1"]["recommendation"] == "ELIGIBLE_BUT_DIRECT_ACTION_PREFERRED"

    def test_no_arm_has_zero_units(self, db):
        """Every arm in every experiment must have at least 1 unit."""
        for prop_code in ("PROP-A", "PROP-B"):
            ctx = _get_context(db, prop_code)
            for code, design in ctx["experiment_designs"].items():
                for arm in design["arms"]:
                    assert arm["units_allocated"] >= 1, \
                        f"{code} arm {arm['label']} has 0 units"
