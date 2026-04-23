"""Test flag generator — verify exact flag counts and types for all 4 unit types.

Expected flag counts with default config after revenue optimization rebalance:
A1=6, A2=7, B1=13, B2=7
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
        "revenue_efficiency_zones": config.revenue_efficiency_zones or {},
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
# A1: Exactly 6 flags (was 3 pre-rebalance)
# ============================================================

class TestA1Flags:
    def test_flag_count(self, all_flags):
        assert all_flags["A1"]["count"] == 6, \
            f"A1 flags: {[f['type'] for f in all_flags['A1']['flags']]}"

    def test_expected_flags(self, all_flags):
        expected = {
            "OCCUPANCY_PUSH_ELIGIBLE",
            "DOM_ABOVE_THRESHOLD",
            "EXECUTED_BELOW_ASKING",
            "RENT_PUSH_OPPORTUNITY",
            "HIGH_LTL_CAPTURE",
            "ELASTICITY_WARNING",
        }
        assert all_flags["A1"]["flag_types"] == expected

    def test_occupancy_push_eligible(self, all_flags):
        assert "OCCUPANCY_PUSH_ELIGIBLE" in all_flags["A1"]["flag_types"]

    def test_dom_above_threshold(self, all_flags):
        assert "DOM_ABOVE_THRESHOLD" in all_flags["A1"]["flag_types"]

    def test_executed_below_asking(self, all_flags):
        assert "EXECUTED_BELOW_ASKING" in all_flags["A1"]["flag_types"]

    def test_push_eligible_is_high(self, all_flags):
        """Reclassified from POSITIVE to HIGH — revenue opportunity, not trivia."""
        push = [f for f in all_flags["A1"]["flags"] if f["type"] == "OCCUPANCY_PUSH_ELIGIBLE"]
        assert push[0]["severity"] == "HIGH"

    def test_rent_push_opportunity(self, all_flags):
        """A1 has optimal asking > current asking by >3% — should trigger."""
        assert "RENT_PUSH_OPPORTUNITY" in all_flags["A1"]["flag_types"]
        flag = [f for f in all_flags["A1"]["flags"] if f["type"] == "RENT_PUSH_OPPORTUNITY"][0]
        assert flag["severity"] == "HIGH"

    def test_high_ltl_capture(self, all_flags):
        """A1 has 7.6% LTL and 96% occ — should trigger HIGH_LTL_CAPTURE."""
        assert "HIGH_LTL_CAPTURE" in all_flags["A1"]["flag_types"]
        flag = [f for f in all_flags["A1"]["flags"] if f["type"] == "HIGH_LTL_CAPTURE"][0]
        assert flag["severity"] == "HIGH"
        assert flag["value"] == 7.6

    def test_elasticity_warning(self, all_flags):
        """A1 elasticity is ELASTIC with HIGH confidence."""
        assert "ELASTICITY_WARNING" in all_flags["A1"]["flag_types"]
        flag = [f for f in all_flags["A1"]["flags"] if f["type"] == "ELASTICITY_WARNING"][0]
        assert flag["severity"] == "INFO"

    def test_no_renewal_increase_eligible(self, all_flags):
        """A1 has 0 upcoming renewals — should NOT trigger."""
        assert "RENEWAL_INCREASE_ELIGIBLE" not in all_flags["A1"]["flag_types"]

    def test_mab_not_eligible(self, all_flags):
        """A1 has only 2 vacant — below min 3 for experiments."""
        assert "MAB_ELIGIBLE" not in all_flags["A1"]["flag_types"]


# ============================================================
# A2: Exactly 7 flags (was 7 pre-rebalance, composition changed)
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
            "ELASTICITY_WARNING",
            "MAB_ELIGIBLE",
        }
        assert all_flags["A2"]["flag_types"] == expected

    def test_no_critical(self, all_flags):
        severities = {f["severity"] for f in all_flags["A2"]["flags"]}
        assert "CRITICAL" not in severities

    def test_no_renewal_freeze(self, all_flags):
        """Reclassified: threshold now 0.82 (from config), A2 at 0.86 no longer triggers."""
        assert "RENEWAL_FREEZE_RECOMMENDED" not in all_flags["A2"]["flag_types"]

    def test_no_high_ltl_capture(self, all_flags):
        """A2 LTL=8.2% but occ=0.86 < 0.88 gate — should NOT trigger."""
        assert "HIGH_LTL_CAPTURE" not in all_flags["A2"]["flag_types"]

    def test_elasticity_warning_present(self, all_flags):
        """A2 elasticity is ELASTIC with HIGH confidence — should trigger."""
        assert "ELASTICITY_WARNING" in all_flags["A2"]["flag_types"]


# ============================================================
# B1: Exactly 13 flags (was 12 pre-rebalance)
# ============================================================

class TestB1Flags:
    def test_flag_count(self, all_flags):
        assert all_flags["B1"]["count"] == 13, \
            f"B1 flags: {[f['type'] for f in all_flags['B1']['flags']]}"

    def test_three_critical(self, all_flags):
        critical = [f for f in all_flags["B1"]["flags"] if f["severity"] == "CRITICAL"]
        assert len(critical) == 3

    def test_critical_types(self, all_flags):
        critical_types = {f["type"] for f in all_flags["B1"]["flags"] if f["severity"] == "CRITICAL"}
        assert critical_types == {"OCCUPANCY_CRISIS", "EXPOSURE_CRISIS", "EXPOSURE_DETERIORATING"}

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
            "ELASTICITY_WARNING",
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
        """B1 demand=0.75, occ=0.79 -> gap=-0.04. Should NOT fire."""
        assert "DEMAND_OCCUPANCY_DIVERGENCE" not in all_flags["B1"]["flag_types"]

    def test_no_revenue_capture_flags(self, all_flags):
        """B1 occ too low for revenue-capture new flags."""
        for flag_type in ("RENT_PUSH_OPPORTUNITY", "HIGH_LTL_CAPTURE",
                          "RENEWAL_INCREASE_ELIGIBLE", "UNDERPRICED_VS_COMPS",
                          "CONCESSION_REMOVAL_ELIGIBLE"):
            assert flag_type not in all_flags["B1"]["flag_types"]

    def test_renewal_freeze_still_fires(self, all_flags):
        """B1 occ=0.79 < 0.82 freeze threshold — still fires."""
        assert "RENEWAL_FREEZE_RECOMMENDED" in all_flags["B1"]["flag_types"]

    def test_elasticity_warning(self, all_flags):
        """B1 elasticity is ELASTIC with HIGH confidence."""
        assert "ELASTICITY_WARNING" in all_flags["B1"]["flag_types"]


# ============================================================
# B2: Exactly 7 flags (unchanged count)
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

    def test_no_high_ltl_capture(self, all_flags):
        """B2 LTL=2.9% which is < 5% threshold — should NOT trigger."""
        assert "HIGH_LTL_CAPTURE" not in all_flags["B2"]["flag_types"]

    def test_no_renewal_increase_eligible(self, all_flags):
        """B2 occ=0.88 < 0.90 gate — should NOT trigger."""
        assert "RENEWAL_INCREASE_ELIGIBLE" not in all_flags["B2"]["flag_types"]

    def test_no_elasticity_warning(self, all_flags):
        """B2 elasticity direction is UNKNOWN — should NOT trigger."""
        assert "ELASTICITY_WARNING" not in all_flags["B2"]["flag_types"]


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

        # With crisis_below=0.72: B1 occ=0.79 is NOT below 0.72 -> no OCCUPANCY_CRISIS
        assert "OCCUPANCY_CRISIS" not in va_types
        # Instead should be OCCUPANCY_BELOW_ACTION (0.79 < 0.80)
        assert "OCCUPANCY_BELOW_ACTION" in va_types

        # With exposure crisis_above=0.25: B1 exp=0.25 is >= 0.25 -> EXPOSURE_CRISIS still fires
        assert "EXPOSURE_CRISIS" in va_types

        # Different flag types than default (OCCUPANCY_CRISIS -> OCCUPANCY_BELOW_ACTION)
        assert va_types != default_types


# ============================================================
# New flag-specific tests
# ============================================================

class TestReclassifications:
    def test_occupancy_push_is_high_not_positive(self, all_flags):
        """Reclassification #1: OCCUPANCY_PUSH_ELIGIBLE severity changed to HIGH."""
        push = [f for f in all_flags["A1"]["flags"] if f["type"] == "OCCUPANCY_PUSH_ELIGIBLE"]
        assert len(push) == 1
        assert push[0]["severity"] == "HIGH"

    def test_renewal_freeze_uses_config_threshold(self, all_flags):
        """Reclassification #2: RENEWAL_FREEZE now reads freeze_below_occupancy from config.

        Default is 0.82. A2 at 0.86 should NOT trigger. B1 at 0.79 still triggers.
        """
        assert "RENEWAL_FREEZE_RECOMMENDED" not in all_flags["A2"]["flag_types"]
        assert "RENEWAL_FREEZE_RECOMMENDED" in all_flags["B1"]["flag_types"]
        b1_freeze = [f for f in all_flags["B1"]["flags"]
                     if f["type"] == "RENEWAL_FREEZE_RECOMMENDED"][0]
        assert b1_freeze["threshold"] == 0.82

    def test_concession_trigger_fires_normally_at_low_occ(self, all_flags):
        """Reclassification #3: CONCESSION_TRIGGER still fires when occ < removal threshold."""
        # A2 (occ=0.86) and B1 (occ=0.79) should still get CONCESSION_TRIGGER
        assert "CONCESSION_TRIGGER" in all_flags["A2"]["flag_types"]
        assert "CONCESSION_TRIGGER" in all_flags["B1"]["flag_types"]


class TestNewFlagGating:
    """Verify that new flags respect their occupancy gates."""

    def test_rent_push_requires_high_occ(self, all_flags):
        """RENT_PUSH_OPPORTUNITY requires occ >= 0.94."""
        # A1 (0.96) has it, A2/B1/B2 do not
        assert "RENT_PUSH_OPPORTUNITY" in all_flags["A1"]["flag_types"]
        assert "RENT_PUSH_OPPORTUNITY" not in all_flags["A2"]["flag_types"]
        assert "RENT_PUSH_OPPORTUNITY" not in all_flags["B1"]["flag_types"]
        assert "RENT_PUSH_OPPORTUNITY" not in all_flags["B2"]["flag_types"]

    def test_high_ltl_capture_requires_occ_and_ltl(self, all_flags):
        """HIGH_LTL_CAPTURE requires LTL > 5% and occ >= 0.88."""
        # A1 (7.6% LTL, 0.96 occ) has it
        assert "HIGH_LTL_CAPTURE" in all_flags["A1"]["flag_types"]
        # A2 (8.2% LTL, 0.86 occ) blocked by occ gate
        assert "HIGH_LTL_CAPTURE" not in all_flags["A2"]["flag_types"]
        # B1 (negative LTL) blocked by LTL gate
        assert "HIGH_LTL_CAPTURE" not in all_flags["B1"]["flag_types"]
        # B2 (2.9% LTL) blocked by LTL threshold
        assert "HIGH_LTL_CAPTURE" not in all_flags["B2"]["flag_types"]

    def test_elasticity_warning_requires_elastic_and_confidence(self, all_flags):
        """ELASTICITY_WARNING requires direction=ELASTIC and confidence >= MEDIUM."""
        # A1, A2, B1 all have ELASTIC + HIGH
        assert "ELASTICITY_WARNING" in all_flags["A1"]["flag_types"]
        assert "ELASTICITY_WARNING" in all_flags["A2"]["flag_types"]
        assert "ELASTICITY_WARNING" in all_flags["B1"]["flag_types"]
        # B2 direction is UNKNOWN
        assert "ELASTICITY_WARNING" not in all_flags["B2"]["flag_types"]
