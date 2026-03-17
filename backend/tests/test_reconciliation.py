"""Reconciliation tests — verify all seeded data matches the EliseAI Pricing Export exactly.

56+ assertions across 4 unit types, plus comp averages and snapshot checks.
Uses round_half_up for all percentage comparisons.
"""
import math
from datetime import date

import pytest
from sqlalchemy import func, and_

from app.database import SessionLocal
from app.models.property import Unit, UnitType, Property
from app.models.comp import CompRent, CompUnitType
from app.models.snapshot import HistoricalSnapshot
from app.models.config import ClientConfig
from app.models.user import User, Organization


def round_half_up(x: float, decimals: int = 0) -> float:
    multiplier = 10 ** decimals
    return math.floor(x * multiplier + 0.5) / multiplier


# Ground truth from the EliseAI Pricing Export
EXPORT = {
    "A1": {
        "total": 48, "occupied": 46, "vacant": 2, "on_notice": 1,
        "base_rent": 1240, "amenity_avg": 89,
        "in_place_avg": 1269, "asking_avg": 1365,
        "executed_avg": 1324, "executed_values": [1290, 1310, 1340, 1356],
        "dom_avg": 24, "dom_values": [15, 26, 31],
        "dv_avg": 17, "dv_values": [12, 22],
        "demand": 0.63,
        "total_exp": 0.06, "vacant_exp": 0.04,
        "occ_rate": 0.96,
        "predicted": 1329,  # base + amenity = 1240 + 89
        "comps_avg": 1353,
    },
    "A2": {
        "total": 36, "occupied": 31, "vacant": 5, "on_notice": 1,
        "base_rent": 1275, "amenity_avg": 83,
        "in_place_avg": 1304, "asking_avg": 1411,
        "executed_avg": 1392, "executed_values": [1370, 1385, 1400, 1413],
        "dom_avg": 22, "dom_values": [8, 14, 18, 24, 28, 40],
        "dv_avg": 16, "dv_values": [7, 10, 14, 22, 27],
        "demand": 0.63,
        "total_exp": 0.17, "vacant_exp": 0.14,
        "occ_rate": 0.86,
        "predicted": 1358,
        "comps_avg": 1396,
    },
    "B1": {
        "total": 24, "occupied": 19, "vacant": 5, "on_notice": 1,
        "base_rent": 1405, "amenity_avg": 125,
        "in_place_avg": 1572, "asking_avg": 1525,
        "executed_avg": 1655, "executed_values": [1630, 1660, 1675],
        "dom_avg": 25, "dom_values": [10, 18, 22, 28, 32, 40],
        "dv_avg": 20, "dv_values": [10, 15, 18, 25, 32],
        "demand": 0.75,
        "total_exp": 0.25, "vacant_exp": 0.21,
        "occ_rate": 0.79,
        "predicted": 1530,
        "comps_avg": 1434,
    },
    "B2": {
        "total": 48, "occupied": 42, "vacant": 6, "on_notice": 0,
        "base_rent": 1465, "amenity_avg": 118,
        "in_place_avg": 1608, "asking_avg": 1654,
        "executed_avg": 1659, "executed_values": [1640, 1650, 1660, 1670, 1675],
        "dom_avg": 30, "dom_values": [18, 22, 28, 32, 36, 44],
        "dv_avg": 28, "dv_values": [16, 20, 26, 30, 34, 42],
        "demand": 0.75,
        "total_exp": 0.13, "vacant_exp": 0.13,
        "occ_rate": 0.88,
        "predicted": 1583,
        "comps_avg": 1662,
    },
}


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


class TestUnitCounts:
    """Verify status counts match the export for each unit type."""

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_total_count(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        total = db.query(func.count(Unit.id)).filter_by(unit_type_id=ut.id).scalar()
        assert total == EXPORT[code]["total"], f"{code} total: {total} != {EXPORT[code]['total']}"

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_occupied_count(self, db, code):
        """Occupied in export includes ON_NOTICE units."""
        ut = db.query(UnitType).filter_by(code=code).first()
        occ = db.query(func.count(Unit.id)).filter(
            Unit.unit_type_id == ut.id,
            Unit.status.in_(["OCCUPIED", "ON_NOTICE"])
        ).scalar()
        assert occ == EXPORT[code]["occupied"], f"{code} occupied: {occ} != {EXPORT[code]['occupied']}"

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_vacant_count(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        vac = db.query(func.count(Unit.id)).filter(
            Unit.unit_type_id == ut.id, Unit.status == "VACANT"
        ).scalar()
        assert vac == EXPORT[code]["vacant"]

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_on_notice_count(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        on = db.query(func.count(Unit.id)).filter(
            Unit.unit_type_id == ut.id, Unit.status == "ON_NOTICE"
        ).scalar()
        assert on == EXPORT[code]["on_notice"]


class TestRentAverages:
    """Verify rent averages match the export."""

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_in_place_avg(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        avg = db.query(func.avg(Unit.current_rent)).filter(
            Unit.unit_type_id == ut.id,
            Unit.status.in_(["OCCUPIED", "ON_NOTICE"])
        ).scalar()
        assert round(avg) == EXPORT[code]["in_place_avg"], \
            f"{code} in-place: {avg:.2f} != {EXPORT[code]['in_place_avg']}"

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_asking_avg(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        avg = db.query(func.avg(Unit.asking_rent)).filter(
            Unit.unit_type_id == ut.id,
            Unit.status.in_(["VACANT", "ON_NOTICE"])
        ).scalar()
        assert round(avg) == EXPORT[code]["asking_avg"], \
            f"{code} asking: {avg:.2f} != {EXPORT[code]['asking_avg']}"

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_amenity_avg(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        avg = db.query(func.avg(Unit.amenity_premium)).filter(
            Unit.unit_type_id == ut.id
        ).scalar()
        assert round(avg) == EXPORT[code]["amenity_avg"], \
            f"{code} amenity: {avg:.2f} != {EXPORT[code]['amenity_avg']}"

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_base_rent_uniform(self, db, code):
        """All units in a type should have the same base_rent (via unit_type)."""
        ut = db.query(UnitType).filter_by(code=code).first()
        assert ut.base_rent == EXPORT[code]["base_rent"]

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_executed_avg(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        avg = db.query(func.avg(Unit.last_executed_rent)).filter(
            Unit.unit_type_id == ut.id,
            Unit.last_executed_rent.isnot(None)
        ).scalar()
        assert round(avg) == EXPORT[code]["executed_avg"], \
            f"{code} executed: {avg:.2f} != {EXPORT[code]['executed_avg']}"


class TestDOMandDV:
    """Verify Days on Market and Days Vacant averages."""

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_dom_avg(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        avg = db.query(func.avg(Unit.days_on_market)).filter(
            Unit.unit_type_id == ut.id,
            Unit.status.in_(["VACANT", "ON_NOTICE"])
        ).scalar()
        assert round(avg) == EXPORT[code]["dom_avg"], \
            f"{code} DOM: {avg:.2f} != {EXPORT[code]['dom_avg']}"

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_dv_avg(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        avg = db.query(func.avg(Unit.days_vacant)).filter(
            Unit.unit_type_id == ut.id,
            Unit.status == "VACANT"
        ).scalar()
        assert round(avg) == EXPORT[code]["dv_avg"], \
            f"{code} DV: {avg:.2f} != {EXPORT[code]['dv_avg']}"


class TestExposure:
    """Verify exposure percentages using round_half_up."""

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_total_exposure(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        vac = db.query(func.count(Unit.id)).filter(
            Unit.unit_type_id == ut.id, Unit.status == "VACANT"
        ).scalar()
        on = db.query(func.count(Unit.id)).filter(
            Unit.unit_type_id == ut.id, Unit.status == "ON_NOTICE"
        ).scalar()
        total = EXPORT[code]["total"]
        exp = round_half_up((vac + on) / total, 2)
        assert exp == EXPORT[code]["total_exp"], \
            f"{code} total exp: {exp} != {EXPORT[code]['total_exp']}"

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_vacant_exposure(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        vac = db.query(func.count(Unit.id)).filter(
            Unit.unit_type_id == ut.id, Unit.status == "VACANT"
        ).scalar()
        total = EXPORT[code]["total"]
        exp = round_half_up(vac / total, 2)
        assert exp == EXPORT[code]["vacant_exp"], \
            f"{code} vacant exp: {exp} != {EXPORT[code]['vacant_exp']}"


class TestPredictedRent:
    """Verify predicted_rent = base_rent + amenity_premium for EVERY unit."""

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_predicted_equals_base_plus_amenity(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        units = db.query(Unit).filter_by(unit_type_id=ut.id).all()
        for unit in units:
            expected = ut.base_rent + unit.amenity_premium
            assert unit.predicted_rent == expected, \
                f"{unit.unit_number}: predicted {unit.predicted_rent} != {expected}"


class TestCompAverages:
    """Verify comp rent averages for March 2026 match export."""

    @pytest.mark.parametrize("code,expected", [
        ("A1", 1353), ("A2", 1396), ("B1", 1434), ("B2", 1662),
    ])
    def test_comp_averages(self, db, code, expected):
        ut = db.query(UnitType).filter_by(code=code).first()
        avg = db.query(func.avg(CompRent.asking_rent)).join(CompUnitType).filter(
            CompUnitType.subject_unit_type_id == ut.id,
            CompRent.observation_date == date(2026, 3, 1)
        ).scalar()
        assert round(avg) == expected, f"{code} comp avg: {avg:.2f} != {expected}"


class TestSnapshotMarchMatchesRentRoll:
    """Verify March 2026 snapshot values match current rent roll aggregates."""

    @pytest.mark.parametrize("code", ["A1", "A2", "B1", "B2"])
    def test_snapshot_march_matches_rent_roll(self, db, code):
        ut = db.query(UnitType).filter_by(code=code).first()
        snap = db.query(HistoricalSnapshot).filter(
            HistoricalSnapshot.unit_type_id == ut.id,
            HistoricalSnapshot.snapshot_date == date(2026, 3, 1)
        ).first()
        assert snap is not None, f"No March snapshot for {code}"

        # Occupancy rate should match export
        assert snap.occupancy_rate == EXPORT[code]["occ_rate"]

        # Asking rent should match export
        assert snap.avg_asking_rent == EXPORT[code]["asking_avg"]

        # Comps avg should match export
        assert snap.comps_avg == EXPORT[code]["comps_avg"]


class TestDataIntegrity:
    """Additional data integrity checks."""

    def test_total_unit_count(self, db):
        total = db.query(func.count(Unit.id)).scalar()
        assert total == 156

    def test_comp_rent_count(self, db):
        total = db.query(func.count(CompRent.id)).scalar()
        assert total == 72

    def test_snapshot_count(self, db):
        total = db.query(func.count(HistoricalSnapshot.id)).scalar()
        assert total == 16

    def test_config_count(self, db):
        total = db.query(func.count(ClientConfig.id)).filter_by(is_active=True).scalar()
        assert total == 2

    def test_demo_user_exists(self, db):
        user = db.query(User).filter_by(email="demo@example.com").first()
        assert user is not None
        assert user.role == "admin"

    def test_no_negative_amenity_premium(self, db):
        bad = db.query(func.count(Unit.id)).filter(Unit.amenity_premium < 0).scalar()
        assert bad == 0

    def test_b1_inplace_above_asking(self, db):
        """B1's in-place avg ($1,572) should be above asking ($1,525)."""
        ut = db.query(UnitType).filter_by(code="B1").first()
        ip_avg = db.query(func.avg(Unit.current_rent)).filter(
            Unit.unit_type_id == ut.id,
            Unit.status.in_(["OCCUPIED", "ON_NOTICE"])
        ).scalar()
        ask_avg = db.query(func.avg(Unit.asking_rent)).filter(
            Unit.unit_type_id == ut.id,
            Unit.status.in_(["VACANT", "ON_NOTICE"])
        ).scalar()
        assert ip_avg > ask_avg, f"B1 in-place {ip_avg} should be > asking {ask_avg}"
