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
