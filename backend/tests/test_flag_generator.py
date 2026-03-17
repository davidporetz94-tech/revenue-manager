"""Test flag generator — verify exact flag counts and types for all 4 unit types.

Expected flag counts with default config:
A1=3, A2=7, B1=12, B2=7
"""
from datetime import date

import pytest

from app.database import SessionLocal
from app.models.property import Property, UnitType
from app.models.config import ClientConfig
from app.services.metrics_engine import compute_property_metrics
from app.services.flag_generator import generate_flags

REF_DATE = date(2026, 3, 15)


def _config_to_dict(config: ClientConfig) -> dict:
    return {
        "occupancy_thresholds": config.occupancy_thresholds or {},
        "exposure_thresholds": config.exposure_thresholds or {},
        "pricing_tolerance": config.pricing_tolerance or {},
        "concession_policy": config.concession_policy or {},
        "renewal_policy": config.renewal_policy or {},
        "lease_term_policy": config.lease_term_policy or {},
        "experiment_policy": config.experiment_policy or {},
        "amenity_benchmarks": config.amenity_benchmarks or {},
    }


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def all_flags(db):
    """Compute flags for all 4 unit types with default config."""
    results = {}

    for prop_code in ("PROP-A", "PROP-B"):
        prop = db.query(Property).filter_by(code=prop_code).first()
        config = db.query(ClientConfig).filter_by(property_id=prop.id, is_active=True).first()
        config_dict = _config_to_dict(config)
        metrics = compute_property_metrics(db, prop.id, config_dict, REF_DATE)

        for ut_code, ut_metrics in metrics["unit_type_metrics"].items():
            flags = generate_flags(ut_metrics, config_dict)
            results[ut_code] = {
                "flags": flags,
                "flag_types": {f["type"] for f in flags},
                "count": len(flags),
                "metrics": ut_metrics,
                "config": config_dict,
            }

    return results


# ============================================================
# A1: Exactly 3 flags
# ============================================================

class TestA1Flags:
    def test_flag_count(self, all_flags):
        assert all_flags["A1"]["count"] == 3, \
            f"A1 flags: {[f['type'] for f in all_flags['A1']['flags']]}"

    def test_occupancy_push_eligible(self, all_flags):
        assert "OCCUPANCY_PUSH_ELIGIBLE" in all_flags["A1"]["flag_types"]

    def test_dom_above_threshold(self, all_flags):
        assert "DOM_ABOVE_THRESHOLD" in all_flags["A1"]["flag_types"]

    def test_executed_below_asking(self, all_flags):
        assert "EXECUTED_BELOW_ASKING" in all_flags["A1"]["flag_types"]

    def test_no_high_or_critical(self, all_flags):
        severities = {f["severity"] for f in all_flags["A1"]["flags"]}
        assert "HIGH" not in severities
        assert "CRITICAL" not in severities

    def test_push_eligible_is_positive(self, all_flags):
        push = [f for f in all_flags["A1"]["flags"] if f["type"] == "OCCUPANCY_PUSH_ELIGIBLE"]
        assert push[0]["severity"] == "POSITIVE"

    def test_mab_not_eligible(self, all_flags):
        """A1 has only 2 vacant — below min 3 for experiments."""
        assert "MAB_ELIGIBLE" not in all_flags["A1"]["flag_types"]


# ============================================================
# A2: Exactly 7 flags
# ============================================================

class TestA2Flags:
    def test_flag_count(self, all_flags):
        assert all_flags["A2"]["count"] == 7, \
            f"A2 flags: {[f['type'] for f in all_flags['A2']['flags']]}"

    def test_expected_flags(self, all_flags):
        expected = {
            "OCCUPANCY_BELOW_ACTION",
            "EXPOSURE_ACTION_NEEDED",
            "CONCESSION_TRIGGER",
            "HIGH_REVENUE_AT_RISK",
            "DOM_ABOVE_THRESHOLD",
            "RENEWAL_FREEZE_RECOMMENDED",
            "MAB_ELIGIBLE",
        }
        assert all_flags["A2"]["flag_types"] == expected

    def test_no_critical(self, all_flags):
        severities = {f["severity"] for f in all_flags["A2"]["flags"]}
        assert "CRITICAL" not in severities


# ============================================================
# B1: Exactly 12 flags
# ============================================================

class TestB1Flags:
    def test_flag_count(self, all_flags):
        assert all_flags["B1"]["count"] == 12, \
            f"B1 flags: {[f['type'] for f in all_flags['B1']['flags']]}"

    def test_two_critical(self, all_flags):
        critical = [f for f in all_flags["B1"]["flags"] if f["severity"] == "CRITICAL"]
        assert len(critical) == 2

    def test_critical_types(self, all_flags):
        critical_types = {f["type"] for f in all_flags["B1"]["flags"] if f["severity"] == "CRITICAL"}
        assert critical_types == {"OCCUPANCY_CRISIS", "EXPOSURE_CRISIS"}

    def test_expected_flags(self, all_flags):
        expected = {
            "OCCUPANCY_CRISIS",
            "EXPOSURE_CRISIS",
            "EXPOSURE_DETERIORATING",
            "ABOVE_COMP_PREMIUM_THRESHOLD",
            "CONCESSION_TRIGGER",
            "NEGATIVE_LTL",
            "EXECUTED_SIGNIFICANTLY_ABOVE_ASKING",
            "HIGH_REVENUE_AT_RISK",
            "DOM_ABOVE_THRESHOLD",
            "AMENITY_AUDIT_RECOMMENDED",
            "RENEWAL_FREEZE_RECOMMENDED",
            "MAB_ELIGIBLE",
        }
        assert all_flags["B1"]["flag_types"] == expected

    def test_negative_ltl_present(self, all_flags):
        """Only B1 has negative LTL (in-place > asking)."""
        assert "NEGATIVE_LTL" in all_flags["B1"]["flag_types"]

    def test_executed_significantly_above(self, all_flags):
        flag = [f for f in all_flags["B1"]["flags"]
                if f["type"] == "EXECUTED_SIGNIFICANTLY_ABOVE_ASKING"]
        assert len(flag) == 1
        assert flag[0]["value"] == 130

    def test_demand_divergence_not_present(self, all_flags):
        """B1 demand=0.75, occ=0.79 → gap=-0.04. Should NOT fire."""
        assert "DEMAND_OCCUPANCY_DIVERGENCE" not in all_flags["B1"]["flag_types"]


# ============================================================
# B2: Exactly 7 flags
# ============================================================

class TestB2Flags:
    def test_flag_count(self, all_flags):
        assert all_flags["B2"]["count"] == 7, \
            f"B2 flags: {[f['type'] for f in all_flags['B2']['flags']]}"

    def test_no_critical(self, all_flags):
        """B2 is a puzzle, not a crisis."""
        critical = [f for f in all_flags["B2"]["flags"] if f["severity"] == "CRITICAL"]
        assert len(critical) == 0

    def test_expected_flags(self, all_flags):
        expected = {
            "OCCUPANCY_BELOW_CONCERN",
            "EXPOSURE_CAUTION",
            "ASKING_ABOVE_PREDICTED_THRESHOLD",
            "DOM_ABOVE_THRESHOLD",
            "CONCESSION_TRIGGER",
            "HIGH_REVENUE_AT_RISK",
            "MAB_ELIGIBLE",
        }
        assert all_flags["B2"]["flag_types"] == expected

    def test_no_comp_premium_flag(self, all_flags):
        """B2 is -0.5% vs comps — should NOT trigger above-comp flag."""
        assert "ABOVE_COMP_PREMIUM_THRESHOLD" not in all_flags["B2"]["flag_types"]

    def test_exposure_not_deteriorating(self, all_flags):
        assert "EXPOSURE_DETERIORATING" not in all_flags["B2"]["flag_types"]


# ============================================================
# Config sensitivity test
# ============================================================

class TestConfigSensitivity:
    def test_different_config_different_flags(self, all_flags):
        """Same B1 metrics with a value-add config should produce different flags."""
        b1_metrics = all_flags["B1"]["metrics"]

        # Value-add config: higher tolerance for vacancy
        value_add_config = {
            "occupancy_thresholds": {
                "target_occupancy": 0.90,
                "push_pricing_above": 0.95,
                "concern_below": 0.85,
                "action_below": 0.80,
                "crisis_below": 0.72,  # lower crisis threshold
            },
            "exposure_thresholds": {
                "green_below": 0.08,
                "caution_below": 0.15,
                "action_below": 0.20,
                "crisis_above": 0.25,  # higher crisis threshold
            },
            "pricing_tolerance": {
                "max_premium_vs_comps_pct": 0.05,
                "max_discount_vs_comps_pct": 0.05,
                "max_asking_vs_predicted_pct": 0.04,
                "acceptable_days_on_market": 21,
            },
            "concession_policy": {
                "concessions_allowed": True,
                "max_concession_weeks_free": 8,
                "prefer_concession_over_base_cut": True,
                "concession_triggers": {"min_exposure_pct": 0.12, "min_days_on_market": 21},
            },
            "renewal_policy": {
                "max_renewal_increase_pct": 0.08,
                "retention_priority": "BALANCED",
                "turnover_cost_estimate": 1500,
                "never_increase_above_occupancy_threshold": 0.80,
            },
            "lease_term_policy": {
                "preferred_term_months": 14,
                "allow_month_to_month": True,
                "mtm_premium_pct": 0.30,
                "short_term_premium_pct": 0.10,
                "target_peak_expiration_pct": 0.60,
            },
            "experiment_policy": {
                "experiments_enabled": True,
                "max_price_spread_pct": 0.06,
                "max_price_spread_dollars": 100,
                "min_vacant_for_experiment": 3,
                "observation_window_days": 14,
                "auto_converge_enabled": False,
                "min_occupancy_for_experiment": 0.75,
            },
            "amenity_benchmarks": {
                "expected_amenity_pct_of_rent": 0.06,
                "amenity_audit_threshold_pct": 0.08,
            },
        }

        va_flags = generate_flags(b1_metrics, value_add_config)
        va_types = {f["type"] for f in va_flags}
        default_types = all_flags["B1"]["flag_types"]

        # With crisis_below=0.72: B1 occ=0.79 is NOT below 0.72 → no OCCUPANCY_CRISIS
        assert "OCCUPANCY_CRISIS" not in va_types
        # Instead should be OCCUPANCY_BELOW_ACTION (0.79 < 0.80)
        assert "OCCUPANCY_BELOW_ACTION" in va_types

        # With exposure crisis_above=0.25: B1 exp=0.25 is >= 0.25 → EXPOSURE_CRISIS still fires
        assert "EXPOSURE_CRISIS" in va_types

        # Different flag types than default (OCCUPANCY_CRISIS → OCCUPANCY_BELOW_ACTION)
        assert va_types != default_types
