"""Seed comp properties, comp unit types, and comp rent time series.

9 comp properties total (4 for Property A, 5 for Property B).
Each comp has 2 comp_unit_types (matching A1/A2 or B1/B2).
4 months of rent observations per comp_unit_type = 72 comp_rents total.

March 2026 averages must match export Comps column:
A1=$1,353, A2=$1,396, B1=$1,434, B2=$1,662
"""
import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.comp import CompProperty, CompUnitType, CompRent

# Comp rent time series from the spec
COMP_DATA = {
    "A": {
        "comps": [
            {"name": "Riverside Terrace", "units": 120, "built": 2008, "class": "B+", "dist": 0.8},
            {"name": "Willow Creek", "units": 96, "built": 2012, "class": "B+", "dist": 1.2},
            {"name": "Oakmont Village", "units": 144, "built": 2003, "class": "B", "dist": 0.5},
            {"name": "Elm Street Residences", "units": 72, "built": 2018, "class": "A-", "dist": 1.5},
        ],
        "A1_rents": {
            date(2025, 12, 1): [1320, 1350, 1275, 1415],
            date(2026, 1, 1): [1330, 1358, 1282, 1422],
            date(2026, 2, 1): [1335, 1365, 1290, 1414],
            date(2026, 3, 1): [1340, 1370, 1295, 1407],
        },
        "A2_rents": {
            date(2025, 12, 1): [1325, 1365, 1395, 1435],
            date(2026, 1, 1): [1335, 1372, 1400, 1445],
            date(2026, 2, 1): [1340, 1378, 1405, 1449],
            date(2026, 3, 1): [1345, 1380, 1410, 1449],
        },
    },
    "B": {
        "comps": [
            {"name": "The Meridian", "units": 180, "built": 2019, "class": "A-", "dist": 0.6},
            {"name": "Harbor View Lofts", "units": 90, "built": 2015, "class": "B+", "dist": 0.9},
            {"name": "Parkside Commons", "units": 144, "built": 2010, "class": "B+", "dist": 1.1},
            {"name": "Azure Tower", "units": 200, "built": 2022, "class": "A", "dist": 1.4},
            {"name": "Beacon Hill", "units": 108, "built": 2013, "class": "B", "dist": 0.7},
        ],
        "B1_rents": {
            date(2025, 12, 1): [1510, 1485, 1420, 1530, 1430],
            date(2026, 1, 1): [1490, 1465, 1400, 1520, 1425],
            date(2026, 2, 1): [1475, 1450, 1390, 1500, 1410],
            date(2026, 3, 1): [1460, 1435, 1380, 1485, 1410],
        },
        "B2_rents": {
            date(2025, 12, 1): [1675, 1650, 1580, 1710, 1635],
            date(2026, 1, 1): [1680, 1660, 1585, 1715, 1635],
            date(2026, 2, 1): [1688, 1665, 1590, 1718, 1639],
            date(2026, 3, 1): [1690, 1665, 1595, 1720, 1640],
        },
    },
}


def seed_comps(db: Session, ids: dict) -> None:
    """Seed 9 comp properties with 72 rent observations."""

    # Property A comps
    _seed_comps_for_property(
        db,
        property_id=ids["prop_a_id"],
        ut1_id=ids["ut_a1_id"],
        ut2_id=ids["ut_a2_id"],
        ut1_bed=1, ut1_bath=1,
        ut2_bed=2, ut2_bath=1,
        comps=COMP_DATA["A"]["comps"],
        ut1_rents=COMP_DATA["A"]["A1_rents"],
        ut2_rents=COMP_DATA["A"]["A2_rents"],
        submarket="Maplewood Gardens",
    )

    # Property B comps
    _seed_comps_for_property(
        db,
        property_id=ids["prop_b_id"],
        ut1_id=ids["ut_b1_id"],
        ut2_id=ids["ut_b2_id"],
        ut1_bed=1, ut1_bath=1,
        ut2_bed=2, ut2_bath=2,
        comps=COMP_DATA["B"]["comps"],
        ut1_rents=COMP_DATA["B"]["B1_rents"],
        ut2_rents=COMP_DATA["B"]["B2_rents"],
        submarket="Harbor Point",
    )

    db.flush()


def _seed_comps_for_property(
    db: Session,
    property_id,
    ut1_id, ut2_id,
    ut1_bed: int, ut1_bath: int,
    ut2_bed: int, ut2_bath: int,
    comps: list[dict],
    ut1_rents: dict,
    ut2_rents: dict,
    submarket: str,
) -> None:
    for comp_info in comps:
        comp_prop = CompProperty(
            id=uuid.uuid4(),
            property_id=property_id,
            name=comp_info["name"],
            address=f"{comp_info['name']} Address",
            submarket=submarket,
            total_units=comp_info["units"],
            year_built=comp_info["built"],
            property_class=comp_info["class"],
            distance_miles=comp_info["dist"],
            data_source="apartments.com",
            is_active=True,
            last_refreshed_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        db.add(comp_prop)
        db.flush()

        comp_idx = comps.index(comp_info)

        # Unit type 1
        cut1 = CompUnitType(
            id=uuid.uuid4(),
            comp_property_id=comp_prop.id,
            subject_unit_type_id=ut1_id,
            bed=ut1_bed,
            bath=ut1_bath,
            sqft_range="600-700",
            relevance_score=0.85,
        )
        db.add(cut1)
        db.flush()

        for obs_date, rents in ut1_rents.items():
            cr = CompRent(
                id=uuid.uuid4(),
                comp_unit_type_id=cut1.id,
                observation_date=obs_date,
                asking_rent=float(rents[comp_idx]),
                data_source="apartments.com",
                created_at=datetime.utcnow(),
            )
            db.add(cr)

        # Unit type 2
        cut2 = CompUnitType(
            id=uuid.uuid4(),
            comp_property_id=comp_prop.id,
            subject_unit_type_id=ut2_id,
            bed=ut2_bed,
            bath=ut2_bath,
            sqft_range="850-1050",
            relevance_score=0.80,
        )
        db.add(cut2)
        db.flush()

        for obs_date, rents in ut2_rents.items():
            cr = CompRent(
                id=uuid.uuid4(),
                comp_unit_type_id=cut2.id,
                observation_date=obs_date,
                asking_rent=float(rents[comp_idx]),
                data_source="apartments.com",
                created_at=datetime.utcnow(),
            )
            db.add(cr)
