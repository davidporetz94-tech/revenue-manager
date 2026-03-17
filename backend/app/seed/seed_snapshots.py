"""Seed 16 historical snapshots (4 unit types x 4 months).

Historical trends from spec:
A1: Dec(occ=0.98, ask=$1,345, comp=$1,340) Jan(0.96, $1,355, $1,348) Feb(0.96, $1,360, $1,351) Mar(0.96, $1,365, $1,353)
A2: Dec(0.92, $1,385, $1,380) Jan(0.89, $1,395, $1,388) Feb(0.86, $1,405, $1,393) Mar(0.86, $1,411, $1,396)
B1: Dec(0.88, $1,600, $1,475) Jan(0.83, $1,575, $1,460) Feb(0.79, $1,540, $1,445) Mar(0.79, $1,525, $1,434)
B2: Dec(0.90, $1,640, $1,650) Jan(0.90, $1,650, $1,655) Feb(0.88, $1,650, $1,660) Mar(0.88, $1,654, $1,662)
"""
import uuid
import math
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.snapshot import HistoricalSnapshot


def round_half_up(x: float, decimals: int = 0) -> float:
    multiplier = 10 ** decimals
    return math.floor(x * multiplier + 0.5) / multiplier


SNAPSHOT_DATA = {
    "A1": {
        "total": 48,
        "months": [
            {
                "date": date(2025, 12, 1), "occ": 0.98,
                "ask": 1345, "comp": 1340, "exec": 1310,
                "dom": 20, "demand": 0.60,
            },
            {
                "date": date(2026, 1, 1), "occ": 0.96,
                "ask": 1355, "comp": 1348, "exec": 1318,
                "dom": 22, "demand": 0.62,
            },
            {
                "date": date(2026, 2, 1), "occ": 0.96,
                "ask": 1360, "comp": 1351, "exec": 1320,
                "dom": 23, "demand": 0.63,
            },
            {
                "date": date(2026, 3, 1), "occ": 0.96,
                "ask": 1365, "comp": 1353, "exec": 1324,
                "dom": 24, "demand": 0.63,
            },
        ],
    },
    "A2": {
        "total": 36,
        "months": [
            {
                "date": date(2025, 12, 1), "occ": 0.92,
                "ask": 1385, "comp": 1380, "exec": 1380,
                "dom": 18, "demand": 0.60,
            },
            {
                "date": date(2026, 1, 1), "occ": 0.89,
                "ask": 1395, "comp": 1388, "exec": 1385,
                "dom": 20, "demand": 0.62,
            },
            {
                "date": date(2026, 2, 1), "occ": 0.86,
                "ask": 1405, "comp": 1393, "exec": 1390,
                "dom": 21, "demand": 0.63,
            },
            {
                "date": date(2026, 3, 1), "occ": 0.86,
                "ask": 1411, "comp": 1396, "exec": 1392,
                "dom": 22, "demand": 0.63,
            },
        ],
    },
    "B1": {
        "total": 24,
        "months": [
            {
                "date": date(2025, 12, 1), "occ": 0.88,
                "ask": 1600, "comp": 1475, "exec": 1670,
                "dom": 20, "demand": 0.70,
            },
            {
                "date": date(2026, 1, 1), "occ": 0.83,
                "ask": 1575, "comp": 1460, "exec": 1660,
                "dom": 22, "demand": 0.72,
            },
            {
                "date": date(2026, 2, 1), "occ": 0.79,
                "ask": 1540, "comp": 1445, "exec": 1655,
                "dom": 24, "demand": 0.74,
            },
            {
                "date": date(2026, 3, 1), "occ": 0.79,
                "ask": 1525, "comp": 1434, "exec": 1655,
                "dom": 25, "demand": 0.75,
            },
        ],
    },
    "B2": {
        "total": 48,
        "months": [
            {
                "date": date(2025, 12, 1), "occ": 0.90,
                "ask": 1640, "comp": 1650, "exec": 1650,
                "dom": 26, "demand": 0.72,
            },
            {
                "date": date(2026, 1, 1), "occ": 0.90,
                "ask": 1650, "comp": 1655, "exec": 1655,
                "dom": 28, "demand": 0.73,
            },
            {
                "date": date(2026, 2, 1), "occ": 0.88,
                "ask": 1650, "comp": 1660, "exec": 1658,
                "dom": 29, "demand": 0.74,
            },
            {
                "date": date(2026, 3, 1), "occ": 0.88,
                "ask": 1654, "comp": 1662, "exec": 1659,
                "dom": 30, "demand": 0.75,
            },
        ],
    },
}


def seed_snapshots(db: Session, ids: dict) -> None:
    """Seed 16 historical snapshots."""
    ut_map = {
        "A1": ids["ut_a1_id"],
        "A2": ids["ut_a2_id"],
        "B1": ids["ut_b1_id"],
        "B2": ids["ut_b2_id"],
    }

    for code, data in SNAPSHOT_DATA.items():
        total = data["total"]
        for m in data["months"]:
            occ_rate = m["occ"]
            occupied = round(total * occ_rate)
            vacant = total - occupied
            # Approximate on_notice (1 for most, 0 for B2 March)
            on_notice_est = 1 if code != "B2" else 0
            exposure = round_half_up((vacant + on_notice_est) / total, 2)

            snap = HistoricalSnapshot(
                id=uuid.uuid4(),
                unit_type_id=ut_map[code],
                snapshot_date=m["date"],
                total_units=total,
                occupied=occupied,
                vacant=vacant,
                on_notice=on_notice_est,
                occupancy_rate=occ_rate,
                avg_in_place_rent=None,  # not tracked historically at this granularity
                avg_asking_rent=float(m["ask"]),
                avg_executed_rent=float(m["exec"]),
                avg_days_on_market=m["dom"],
                exposure_pct=exposure,
                demand_score=m["demand"],
                comps_avg=float(m["comp"]),
                created_at=datetime.utcnow(),
            )
            db.add(snap)

    db.flush()
