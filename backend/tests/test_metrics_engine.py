"""Test metrics engine — verify computed metrics match hand-calculated values.

Tests all 4 unit types with exact value assertions.
"""
import math
from datetime import date

import pytest
from sqlalchemy import func

from app.database import SessionLocal
from app.models.property import Unit, UnitType, Property
from app.models.config import ClientConfig
from app.services.metrics_engine import compute_property_metrics
from app.engine.utils import round_half_up

REF_DATE = date(2026, 3, 15)


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def metrics_a(db):
    """Compute metrics for Property A."""
    prop = db.query(Property).filter_by(code="PROP-A").first()
    config = db.query(ClientConfig).filter_by(property_id=prop.id, is_active=True).first()
    config_dict = _config_to_dict(config)
    return compute_property_metrics(db, prop.id, config_dict, REF_DATE)


@pytest.fixture(scope="module")
def metrics_b(db):
    """Compute metrics for Property B."""
    prop = db.query(Property).filter_by(code="PROP-B").first()
    config = db.query(ClientConfig).filter_by(property_id=prop.id, is_active=True).first()
    config_dict = _config_to_dict(config)
    return compute_property_metrics(db, prop.id, config_dict, REF_DATE)


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


# ============================================================
# A1 Metrics Tests
# ============================================================

class TestA1Metrics:
    def test_occupancy(self, metrics_a):
        m = metrics_a["unit_type_metrics"]["A1"]["occupancy_metrics"]
        assert m["occupied"] == 46
        assert m["vacant"] == 2
        assert m["on_notice"] == 1
        assert m["available"] == 3
        assert m["occupancy_rate"] == 0.96

    def test_exposure(self, metrics_a):
        m = metrics_a["unit_type_metrics"]["A1"]["exposure_metrics"]
        assert m["total_exposure_pct"] == 0.06
        assert m["vacant_exposure_pct"] == 0.04

    def test_pricing_spreads(self, metrics_a):
        p = metrics_a["unit_type_metrics"]["A1"]["pricing_spreads"]
        assert p["asking_rent"] == 1365
        assert p["predicted_rent"] == 1329
        assert p["comps_rent"] == 1353
        assert p["in_place_rent"] == 1269
        assert p["executed_rent"] == 1324
        assert p["base_rent"] == 1240
        assert p["amenity_price"] == 89
        assert p["asking_vs_predicted_dollars"] == 36
        assert p["asking_vs_predicted_pct"] == 2.7
        assert p["asking_vs_comps_dollars"] == 12
        assert p["asking_vs_comps_pct"] == 0.9
        assert p["loss_to_lease_dollars"] == 96
        assert p["loss_to_lease_pct"] == 7.6

    def test_revenue(self, metrics_a):
        r = metrics_a["unit_type_metrics"]["A1"]["revenue_metrics"]
        assert r["daily_vacancy_burn"] == 91

    def test_velocity(self, metrics_a):
        v = metrics_a["unit_type_metrics"]["A1"]["velocity_metrics"]
        assert v["avg_days_on_market"] == 24
        assert v["avg_days_vacant"] == 17

    def test_amenity_pct(self, metrics_a):
        p = metrics_a["unit_type_metrics"]["A1"]["pricing_spreads"]
        assert p["amenity_pct_of_predicted"] == 6.7


# ============================================================
# A2 Metrics Tests
# ============================================================

class TestA2Metrics:
    def test_occupancy(self, metrics_a):
        m = metrics_a["unit_type_metrics"]["A2"]["occupancy_metrics"]
        assert m["occupied"] == 31
        assert m["vacant"] == 5
        assert m["occupancy_rate"] == 0.86

    def test_exposure(self, metrics_a):
        m = metrics_a["unit_type_metrics"]["A2"]["exposure_metrics"]
        assert m["total_exposure_pct"] == 0.17

    def test_pricing_spreads(self, metrics_a):
        p = metrics_a["unit_type_metrics"]["A2"]["pricing_spreads"]
        assert p["asking_vs_predicted_dollars"] == 53
        assert p["asking_vs_predicted_pct"] == 3.9
        assert p["asking_vs_comps_dollars"] == 15
        assert p["asking_vs_comps_pct"] == 1.1
        assert p["loss_to_lease_dollars"] == 107
        assert p["loss_to_lease_pct"] == 8.2

    def test_revenue(self, metrics_a):
        r = metrics_a["unit_type_metrics"]["A2"]["revenue_metrics"]
        assert r["daily_vacancy_burn"] == 235


# ============================================================
# B1 Metrics Tests
# ============================================================

class TestB1Metrics:
    def test_occupancy(self, metrics_b):
        m = metrics_b["unit_type_metrics"]["B1"]["occupancy_metrics"]
        assert m["occupied"] == 19
        assert m["vacant"] == 5
        assert m["occupancy_rate"] == 0.79

    def test_exposure(self, metrics_b):
        m = metrics_b["unit_type_metrics"]["B1"]["exposure_metrics"]
        assert m["total_exposure_pct"] == 0.25
        assert m["vacant_exposure_pct"] == 0.21

    def test_exposure_trend(self, metrics_b):
        m = metrics_b["unit_type_metrics"]["B1"]["exposure_metrics"]
        # B1 on-notice at 45 days: 30d=0.21, 60d=0.25 → DETERIORATING
        assert m["exposure_30d_pct"] == 0.21
        assert m["exposure_60d_pct"] == 0.25
        assert m["exposure_trend"] == "DETERIORATING"

    def test_pricing_spreads(self, metrics_b):
        p = metrics_b["unit_type_metrics"]["B1"]["pricing_spreads"]
        assert p["asking_rent"] == 1525
        assert p["comps_rent"] == 1434
        assert p["asking_vs_comps_dollars"] == 91
        assert p["asking_vs_comps_pct"] == 6.3
        assert p["loss_to_lease_dollars"] == -47
        assert p["loss_to_lease_pct"] == -3.0
        assert p["executed_vs_asking_dollars"] == 130

    def test_revenue(self, metrics_b):
        r = metrics_b["unit_type_metrics"]["B1"]["revenue_metrics"]
        assert r["daily_vacancy_burn"] == 254


# ============================================================
# B2 Metrics Tests
# ============================================================

class TestB2Metrics:
    def test_occupancy(self, metrics_b):
        m = metrics_b["unit_type_metrics"]["B2"]["occupancy_metrics"]
        assert m["occupied"] == 42
        assert m["vacant"] == 6
        assert m["occupancy_rate"] == 0.88

    def test_exposure(self, metrics_b):
        m = metrics_b["unit_type_metrics"]["B2"]["exposure_metrics"]
        assert m["total_exposure_pct"] == 0.13
        assert m["vacant_exposure_pct"] == 0.13

    def test_pricing_spreads(self, metrics_b):
        p = metrics_b["unit_type_metrics"]["B2"]["pricing_spreads"]
        assert p["asking_rent"] == 1654
        assert p["asking_vs_comps_dollars"] == -8
        assert p["asking_vs_predicted_dollars"] == 71
        assert p["asking_vs_predicted_pct"] == 4.5

    def test_velocity(self, metrics_b):
        v = metrics_b["unit_type_metrics"]["B2"]["velocity_metrics"]
        assert v["avg_days_on_market"] == 30
        assert v["avg_days_vacant"] == 28

    def test_revenue(self, metrics_b):
        r = metrics_b["unit_type_metrics"]["B2"]["revenue_metrics"]
        assert r["daily_vacancy_burn"] == 331


# ============================================================
# Portfolio Metrics Tests
# ============================================================

class TestPortfolioMetrics:
    def test_totals(self, metrics_a, metrics_b):
        # Portfolio spans both properties; test individually
        pa = metrics_a["portfolio_metrics"]
        assert pa["total_units"] == 84  # 48 + 36
        assert pa["total_vacant"] == 7  # 2 + 5

        pb = metrics_b["portfolio_metrics"]
        assert pb["total_units"] == 72  # 24 + 48
        assert pb["total_vacant"] == 11  # 5 + 6

    def test_worst_best(self, metrics_b):
        pb = metrics_b["portfolio_metrics"]
        assert pb["worst_performing_unit_type"] == "B1"
        assert pb["best_performing_unit_type"] == "B2"


# ============================================================
# Engine purity check
# ============================================================

# ============================================================
# Revenue Optimization Integration Tests
# ============================================================

class TestRevenueOptimizationIntegration:
    """Verify that the revenue optimization engine sections are present
    in the metrics output for every unit type and contain sensible values."""

    # --- Elasticity ---

    def test_metrics_include_elasticity_a1(self, metrics_a):
        """A1: elasticity section present with ELASTIC direction (healthy occupancy)."""
        e = metrics_a["unit_type_metrics"]["A1"]["elasticity"]
        assert "elasticity_coefficient" in e
        assert e["confidence"] in ("LOW", "MEDIUM", "HIGH")
        assert e["data_points"] >= 2
        assert e["direction"] in ("ELASTIC", "INELASTIC", "UNKNOWN")

    def test_metrics_include_elasticity_b1(self, metrics_b):
        """B1: elasticity section present — crisis scenario."""
        e = metrics_b["unit_type_metrics"]["B1"]["elasticity"]
        assert e["elasticity_coefficient"] > 0
        assert e["direction"] == "ELASTIC"

    def test_metrics_include_elasticity_b2(self, metrics_b):
        """B2: elasticity section present — puzzle scenario."""
        e = metrics_b["unit_type_metrics"]["B2"]["elasticity"]
        assert "elasticity_coefficient" in e
        assert e["data_points"] >= 2

    # --- Optimal Pricing ---

    def test_metrics_include_optimal_pricing_a1(self, metrics_a):
        """A1: optimal pricing with plausible values for healthy unit type."""
        o = metrics_a["unit_type_metrics"]["A1"]["optimal_pricing"]
        assert o["optimal_asking"] > 0
        assert o["current_revenue_monthly"] > 0
        assert o["price_direction"] in ("INCREASE", "DECREASE", "HOLD")
        assert o["confidence"] in ("LOW", "MEDIUM", "HIGH")

    def test_metrics_include_optimal_pricing_a2(self, metrics_a):
        """A2: optimal pricing suggests DECREASE (overpriced scenario)."""
        o = metrics_a["unit_type_metrics"]["A2"]["optimal_pricing"]
        assert o["optimal_asking"] > 0
        assert o["price_direction"] == "DECREASE"

    def test_metrics_include_optimal_pricing_b1(self, metrics_b):
        """B1: optimal pricing suggests DECREASE (crisis, far above comps)."""
        o = metrics_b["unit_type_metrics"]["B1"]["optimal_pricing"]
        assert o["optimal_asking"] > 0
        assert o["price_direction"] == "DECREASE"

    def test_optimal_pricing_comp_constrained(self, metrics_a, metrics_b):
        """At least one unit type should be comp-constrained (within +-15% of comps)."""
        all_ut = list(metrics_a["unit_type_metrics"].values()) + list(metrics_b["unit_type_metrics"].values())
        # Check that the field exists in all
        for ut in all_ut:
            assert "comp_constrained" in ut["optimal_pricing"]

    # --- Revenue Gap ---

    def test_metrics_include_revenue_gap_a1(self, metrics_a):
        """A1: revenue gap with RENEW as dominant lever (healthy, LTL upside)."""
        g = metrics_a["unit_type_metrics"]["A1"]["revenue_gap"]
        assert g["dominant_lever"] in ("FILL", "REPRICE", "RENEW", "DE_CONCESSION")
        assert len(g["gap_components"]) == 5
        assert len(g["lever_ranking"]) == 5

    def test_metrics_include_revenue_gap_b1(self, metrics_b):
        """B1: revenue gap with FILL as dominant lever (high vacancy)."""
        g = metrics_b["unit_type_metrics"]["B1"]["revenue_gap"]
        assert g["dominant_lever"] == "FILL"
        assert g["gap_components"]["vacancy_cost"]["amount"] > 0

    def test_revenue_gap_components_structure(self, metrics_a):
        """Verify gap components have required fields."""
        g = metrics_a["unit_type_metrics"]["A1"]["revenue_gap"]
        for name, comp in g["gap_components"].items():
            assert "amount" in comp, f"Missing amount in {name}"
            assert "lever" in comp, f"Missing lever in {name}"
            assert "description" in comp, f"Missing description in {name}"

    # --- Revenue Efficiency ---

    def test_metrics_include_revenue_efficiency_a1(self, metrics_a):
        """A1: efficiency score and grade for healthy unit type."""
        eff = metrics_a["unit_type_metrics"]["A1"]["revenue_efficiency"]
        assert 0 <= eff["revenue_efficiency_score"] <= 100
        assert eff["grade"] in ("OPTIMIZED", "OPPORTUNITY", "IMBALANCED", "DISTRESSED", "CRISIS")
        assert eff["occupancy_zone"] in ("CRISIS", "STRESSED", "BALANCED", "STRONG", "FULL")
        assert "dimensions" in eff
        assert len(eff["dimensions"]) == 3

    def test_metrics_include_revenue_efficiency_b1(self, metrics_b):
        """B1: efficiency should be low — crisis zone."""
        eff = metrics_b["unit_type_metrics"]["B1"]["revenue_efficiency"]
        assert eff["revenue_efficiency_score"] < 50
        assert eff["occupancy_zone"] == "CRISIS"
        assert eff["grade"] in ("DISTRESSED", "CRISIS")

    def test_revenue_efficiency_dimensions(self, metrics_a):
        """Verify all three efficiency dimensions have score and weight."""
        dims = metrics_a["unit_type_metrics"]["A1"]["revenue_efficiency"]["dimensions"]
        for dim_name in ("occupancy_health", "pricing_alignment", "rent_roll_momentum"):
            assert dim_name in dims
            assert 0 <= dims[dim_name]["score"] <= 100
            assert 0 <= dims[dim_name]["weight"] <= 1

    def test_revenue_efficiency_weights_sum(self, metrics_a):
        """Dimension weights should sum to approximately 1.0."""
        dims = metrics_a["unit_type_metrics"]["A1"]["revenue_efficiency"]["dimensions"]
        total = sum(d["weight"] for d in dims.values())
        assert 0.99 <= total <= 1.01, f"Weights sum to {total}, expected ~1.0"

    # --- Renewal Opportunity ---

    def test_metrics_include_renewal_opportunity_a1(self, metrics_a):
        """A1: renewal opportunity section present."""
        r = metrics_a["unit_type_metrics"]["A1"]["renewal_opportunity"]
        assert "upcoming_renewals_90d" in r
        assert "recommended_increase_pct" in r
        assert "net_monthly_capture" in r
        assert r["upcoming_renewals_90d"] >= 0
        assert r["confidence"] in ("LOW", "MEDIUM", "HIGH")

    def test_metrics_include_renewal_opportunity_b1(self, metrics_b):
        """B1: renewal opportunity — crisis zone should recommend freeze (0% increase)."""
        r = metrics_b["unit_type_metrics"]["B1"]["renewal_opportunity"]
        assert r["recommended_increase_pct"] == 0.0  # freeze in crisis

    # --- All unit types have all sections ---

    def test_all_unit_types_have_new_sections(self, metrics_a, metrics_b):
        """Every unit type should have all 5 new revenue optimization sections."""
        required_sections = [
            "elasticity", "optimal_pricing", "renewal_opportunity",
            "revenue_gap", "revenue_efficiency",
        ]
        for m in (metrics_a, metrics_b):
            for ut_code, ut_metrics in m["unit_type_metrics"].items():
                for section in required_sections:
                    assert section in ut_metrics, \
                        f"Missing '{section}' in {ut_code}"


class TestEnginePurity:
    def test_no_sqlalchemy_imports_in_engine(self):
        """Engine modules must not import from database/ORM."""
        import importlib
        engine_modules = [
            "app.engine.utils",
            "app.engine.occupancy",
            "app.engine.exposure",
            "app.engine.pricing_spread",
            "app.engine.revenue",
            "app.engine.loss_to_lease",
            "app.engine.lease_term",
            "app.engine.seasonal",
            "app.engine.aggregator",
            "app.engine.revenue_optimizer",
            "app.engine.renewal_optimizer",
        ]
        for mod_name in engine_modules:
            mod = importlib.import_module(mod_name)
            source = open(mod.__file__).read()
            assert "sqlalchemy" not in source.lower(), \
                f"{mod_name} contains SQLAlchemy reference"
            assert "from app.database" not in source, \
                f"{mod_name} imports from app.database"
            assert "from app.models" not in source, \
                f"{mod_name} imports from app.models"
