"""Seed 156 units with data that reconciles exactly to the EliseAI Pricing Export.

Uses the "balancing unit" approach: generate N-1 units with realistic values,
then set the Nth unit's value to hit the exact aggregate target.

Reference date: March 15, 2026.

Export ground truth:
| Type | Total | Occ | Vac | ON | Base  | Amenity | InPlace | Asking | Executed | DOM      | DV       | Demand |
| A1   | 48    | 46  | 2   | 1  | 1240  | 89      | 1269    | 1365   | 1324     | 24 avg   | 17 avg   | 0.63   |
| A2   | 36    | 31  | 5   | 1  | 1275  | 83      | 1304    | 1411   | 1392     | 22 avg   | 16 avg   | 0.63   |
| B1   | 24    | 19  | 5   | 1  | 1405  | 125     | 1572    | 1525   | 1655     | 25 avg   | 20 avg   | 0.75   |
| B2   | 48    | 42  | 6   | 0  | 1465  | 118     | 1608    | 1654   | 1659     | 30 avg   | 28 avg   | 0.75   |
"""
import uuid
import math
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.engine.utils import round_half_up

from app.models.property import Unit


# Reference date for all calculations
REF_DATE = date(2026, 3, 15)


def _assign_amenities_a(unit_number: str, floor: int, idx_in_type: int,
                         total_in_type: int, is_prop_a: bool) -> dict:
    """Deterministic amenity assignment for Property A units."""
    amenities = {
        "premium_view": False,
        "high_floor": floor >= 3,
        "corner_unit": False,
        "in_unit_wd": False,
        "renovated": False,
        "patio_balcony": floor == 1,
        "ev_charging": False,
        "garage_parking": False,
    }

    # Corner units: first and last on each floor segment
    num = int(unit_number.split("-")[1])
    floor_offset = num % 100
    if floor_offset in (1, 16, 17, 28):
        amenities["corner_unit"] = True

    # ~42% have WD for Property A
    if idx_in_type % 5 in (0, 1):
        amenities["in_unit_wd"] = True

    # ~25% renovated
    if idx_in_type % 4 == 0:
        amenities["renovated"] = True

    return amenities


def _assign_amenities_b(unit_number: str, floor: int, idx_in_type: int,
                         total_in_type: int) -> dict:
    """Deterministic amenity assignment for Property B units."""
    amenities = {
        "premium_view": False,
        "high_floor": floor >= 3,
        "corner_unit": False,
        "in_unit_wd": False,
        "renovated": False,
        "patio_balcony": floor == 1,
        "ev_charging": False,
        "garage_parking": False,
    }

    num = int(unit_number.split("-")[1])
    floor_offset = num % 100
    if floor_offset in (1, 6, 7, 18):
        amenities["corner_unit"] = True

    # ~75% have WD
    if idx_in_type % 4 != 3:
        amenities["in_unit_wd"] = True

    # ~33% renovated
    if idx_in_type % 3 == 0:
        amenities["renovated"] = True

    # Some EV/garage for B
    if idx_in_type % 8 == 0:
        amenities["ev_charging"] = True
    if idx_in_type % 6 == 0:
        amenities["garage_parking"] = True

    return amenities


def _calc_amenity_premium(amenities: dict) -> float:
    """Calculate amenity premium from boolean flags."""
    premium = 0.0
    if amenities["premium_view"]:
        premium += 22
    if amenities["high_floor"]:
        premium += 30
    if amenities["corner_unit"]:
        premium += 15
    if amenities["in_unit_wd"]:
        premium += 80
    if amenities["renovated"]:
        premium += 45
    if amenities["patio_balcony"]:
        premium += 30
    if amenities["ev_charging"]:
        premium += 20
    if amenities["garage_parking"]:
        premium += 18
    return premium


def _build_unit_numbers_a1() -> list[tuple[str, int]]:
    """Generate A1 unit numbers: floors 1-3, units 01-16 per floor."""
    units = []
    for floor in range(1, 4):
        for u in range(1, 17):
            units.append((f"A-{floor}{u:02d}", floor))
    return units


def _build_unit_numbers_a2() -> list[tuple[str, int]]:
    """Generate A2 unit numbers: floors 1-3, units 17-28 per floor."""
    units = []
    for floor in range(1, 4):
        for u in range(17, 29):
            units.append((f"A-{floor}{u:02d}", floor))
    return units


def _build_unit_numbers_b1() -> list[tuple[str, int]]:
    """Generate B1 unit numbers: floors 1-4, units 01-06 per floor."""
    units = []
    for floor in range(1, 5):
        for u in range(1, 7):
            units.append((f"B-{floor}{u:02d}", floor))
    return units


def _build_unit_numbers_b2() -> list[tuple[str, int]]:
    """Generate B2 unit numbers: floors 1-4, units 07-18 per floor."""
    units = []
    for floor in range(1, 5):
        for u in range(7, 19):
            units.append((f"B-{floor}{u:02d}", floor))
    return units


def _sqft_for_unit(sqft_min: int, sqft_max: int, idx: int, total: int) -> int:
    """Deterministic sqft based on position in unit list."""
    spread = sqft_max - sqft_min
    return sqft_min + int(spread * (idx / max(total - 1, 1)))


def seed_units(db: Session, ids: dict) -> None:
    """Seed all 156 units across 4 unit types with exact reconciliation."""
    _seed_unit_type(
        db, ids,
        unit_type_code="A1",
        property_id=ids["prop_a_id"],
        unit_type_id=ids["ut_a1_id"],
        build_numbers_fn=_build_unit_numbers_a1,
        is_prop_b=False,
        # Export values
        total=48, occupied=46, vacant=2, on_notice=1,
        base_rent=1240,
        target_amenity_avg=89, target_amenity_total=48 * 89,  # $4,272
        target_in_place_avg=1269, target_in_place_total=46 * 1269,  # $58,374
        target_asking=1365,
        target_executed_avg=1324,
        executed_values=[1290, 1310, 1340, 1356],
        dom_values=[15, 26, 31],  # 3 available (2 vacant + 1 on-notice)
        dv_values=[12, 22],  # 2 vacant
        sqft_min=600, sqft_max=650,
        on_notice_move_out_days=25,  # within 30d for exposure calcs
    )

    _seed_unit_type(
        db, ids,
        unit_type_code="A2",
        property_id=ids["prop_a_id"],
        unit_type_id=ids["ut_a2_id"],
        build_numbers_fn=_build_unit_numbers_a2,
        is_prop_b=False,
        total=36, occupied=31, vacant=5, on_notice=1,
        base_rent=1275,
        target_amenity_avg=83, target_amenity_total=36 * 83,  # $2,988
        target_in_place_avg=1304, target_in_place_total=31 * 1304,  # $40,424
        target_asking=1411,
        target_executed_avg=1392,
        executed_values=[1370, 1385, 1400, 1413],
        dom_values=[8, 14, 18, 24, 28, 40],  # 6 available (5 vacant + 1 on-notice)
        dv_values=[7, 10, 14, 22, 27],  # 5 vacant
        sqft_min=850, sqft_max=920,
        on_notice_move_out_days=25,
    )

    _seed_unit_type(
        db, ids,
        unit_type_code="B1",
        property_id=ids["prop_b_id"],
        unit_type_id=ids["ut_b1_id"],
        build_numbers_fn=_build_unit_numbers_b1,
        is_prop_b=True,
        total=24, occupied=19, vacant=5, on_notice=1,
        base_rent=1405,
        target_amenity_avg=125, target_amenity_total=24 * 125,  # $3,000
        target_in_place_avg=1572, target_in_place_total=19 * 1572,  # $29,868
        target_asking=1525,
        target_executed_avg=1655,
        executed_values=[1630, 1660, 1675],
        dom_values=[10, 18, 22, 28, 32, 40],  # 6 available (5 vacant + 1 on-notice)
        dv_values=[10, 15, 18, 25, 32],  # 5 vacant
        sqft_min=680, sqft_max=730,
        # B1 on-notice: move-out 31-60 days out → 30d exp=0.21, 60d=0.25
        on_notice_move_out_days=45,
    )

    _seed_unit_type(
        db, ids,
        unit_type_code="B2",
        property_id=ids["prop_b_id"],
        unit_type_id=ids["ut_b2_id"],
        build_numbers_fn=_build_unit_numbers_b2,
        is_prop_b=True,
        total=48, occupied=42, vacant=6, on_notice=0,
        base_rent=1465,
        target_amenity_avg=118, target_amenity_total=48 * 118,  # $5,664
        target_in_place_avg=1608, target_in_place_total=42 * 1608,  # $67,536
        target_asking=1654,
        target_executed_avg=1659,
        executed_values=[1640, 1650, 1660, 1670, 1675],
        dom_values=[18, 22, 28, 32, 36, 44],  # 6 available (6 vacant + 0 on-notice)
        dv_values=[16, 20, 26, 30, 34, 42],  # 6 vacant
        sqft_min=980, sqft_max=1050,
        on_notice_move_out_days=0,  # no on-notice for B2
    )

    db.flush()


def _seed_unit_type(
    db: Session, ids: dict,
    unit_type_code: str,
    property_id, unit_type_id,
    build_numbers_fn,
    is_prop_b: bool,
    total: int, occupied: int, vacant: int, on_notice: int,
    base_rent: float,
    target_amenity_avg: float, target_amenity_total: float,
    target_in_place_avg: float, target_in_place_total: float,
    target_asking: float,
    target_executed_avg: float,
    executed_values: list[float],
    dom_values: list[int],
    dv_values: list[int],
    sqft_min: int, sqft_max: int,
    on_notice_move_out_days: int,
) -> None:
    """Seed all units for a single unit type with exact aggregate reconciliation.

    The export's "Occupied" count INCLUDES on-notice units (they still pay rent).
    So in the DB: pure_occupied = occupied - on_notice.
    Total = pure_occupied + on_notice + vacant.
    In-place avg is over all rent-paying units (pure_occupied + on_notice = `occupied`).
    """

    unit_numbers = build_numbers_fn()
    assert len(unit_numbers) == total, f"{unit_type_code}: expected {total} units, got {len(unit_numbers)}"

    pure_occupied = occupied - on_notice  # units with status=OCCUPIED
    assert pure_occupied + on_notice + vacant == total, \
        f"{unit_type_code}: {pure_occupied}+{on_notice}+{vacant} != {total}"

    # --- Step 1: Compute amenity premiums using balancing approach ---
    raw_premiums = []
    for idx, (num, floor) in enumerate(unit_numbers):
        if is_prop_b:
            amenities = _assign_amenities_b(num, floor, idx, total)
        else:
            amenities = _assign_amenities_a(num, floor, idx, total, True)
        raw_premiums.append((amenities, _calc_amenity_premium(amenities)))

    # Scale premiums to hit exact total
    raw_total = sum(p for _, p in raw_premiums)
    if raw_total > 0:
        scale_factor = target_amenity_total / raw_total
    else:
        scale_factor = 1.0

    # Apply scaling and round, then adjust last unit to hit exact total
    final_premiums = []
    running_total = 0.0
    for i, (amenities, raw_p) in enumerate(raw_premiums):
        if i < total - 1:
            scaled = int(round_half_up(raw_p * scale_factor))
            final_premiums.append(scaled)
            running_total += scaled
        else:
            # Balancing unit
            final_premiums.append(target_amenity_total - running_total)

    # --- Step 2: Determine unit statuses ---
    # pure_occupied OCCUPIED, then vacant VACANT, then on_notice ON_NOTICE
    statuses = []
    for i in range(total):
        if i < pure_occupied:
            statuses.append("OCCUPIED")
        elif i < pure_occupied + vacant:
            statuses.append("VACANT")
        else:
            statuses.append("ON_NOTICE")

    # --- Step 3: Assign in-place rents ---
    # In-place avg covers ALL rent-paying units (OCCUPIED + ON_NOTICE = `occupied` from export)
    # We need: sum of all current_rents = target_in_place_total
    # Split: generate pure_occupied rents + on_notice rents that together average correctly
    all_renting_count = occupied  # pure_occupied + on_notice

    in_place_rents = []  # for pure_occupied units
    on_notice_rents = []  # for on_notice units

    if all_renting_count > 0:
        # Generate pure_occupied rents with vintage-based variation
        for i in range(pure_occupied):
            progress = i / max(pure_occupied - 1, 1) if pure_occupied > 1 else 0.5
            variation = (progress - 0.5) * 80  # +/-40 from avg
            rent = int(round_half_up(target_in_place_avg + variation))
            in_place_rents.append(rent)

        # ON_NOTICE units get rent near in-place avg
        for i in range(on_notice):
            on_notice_rents.append(int(round_half_up(target_in_place_avg)))

        # Balancing: adjust last pure_occupied rent to hit exact total
        current_sum = sum(in_place_rents) + sum(on_notice_rents)
        if pure_occupied > 0:
            in_place_rents[-1] += (target_in_place_total - current_sum)

    # --- Step 4: Assign asking rents for available units ---
    num_available = vacant + on_notice
    asking_rents = [float(target_asking)] * num_available

    # --- Step 5: Validate DOM and DV counts ---
    assert len(dom_values) == num_available, \
        f"{unit_type_code}: DOM count {len(dom_values)} != available {num_available}"
    assert len(dv_values) == vacant, \
        f"{unit_type_code}: DV count {len(dv_values)} != vacant {vacant}"

    # --- Step 6: Create all unit objects ---
    available_idx = 0  # index into dom_values and asking_rents
    vacant_idx = 0  # index into dv_values
    exec_idx = 0  # index into executed_values
    occ_idx = 0  # index into in_place_rents
    on_notice_idx = 0  # index into on_notice_rents
    exec_count = len(executed_values)

    units_to_add = []
    for i in range(total):
        unit_num, floor = unit_numbers[i]
        status = statuses[i]
        amenity_premium = float(final_premiums[i])
        predicted = base_rent + amenity_premium
        sqft = _sqft_for_unit(sqft_min, sqft_max, i, total)

        if is_prop_b:
            amenities = _assign_amenities_b(unit_num, floor, i, total)
        else:
            amenities = _assign_amenities_a(unit_num, floor, i, total, True)

        unit = Unit(
            id=uuid.uuid4(),
            unit_type_id=unit_type_id,
            property_id=property_id,
            unit_number=unit_num,
            floor=floor,
            sqft=sqft,
            premium_view=amenities["premium_view"],
            high_floor=amenities["high_floor"],
            corner_unit=amenities["corner_unit"],
            in_unit_wd=amenities["in_unit_wd"],
            renovated=amenities["renovated"],
            patio_balcony=amenities["patio_balcony"],
            ev_charging=amenities["ev_charging"],
            garage_parking=amenities["garage_parking"],
            amenity_premium=amenity_premium,
            predicted_rent=predicted,
            status=status,
        )

        if status == "OCCUPIED":
            unit.current_rent = float(in_place_rents[occ_idx])
            occ_idx += 1
            # Lease dates: varied start dates, all ending > 90 days from ref
            months_ago = 3 + (i % 10)
            unit.lease_start = REF_DATE - timedelta(days=30 * months_ago)
            unit.lease_end = REF_DATE + timedelta(days=91 + (i * 7) % 180)
            unit.tenant_id = f"T-{unit_type_code}-{i+1:03d}"

            # Assign executed rents to first exec_count occupied units
            if exec_idx < exec_count:
                unit.last_executed_rent = float(executed_values[exec_idx])
                # Recent execution dates (within 90 days)
                unit.last_executed_date = REF_DATE - timedelta(days=10 + exec_idx * 15)
                exec_idx += 1

        elif status == "VACANT":
            unit.asking_rent = float(asking_rents[available_idx])
            unit.days_on_market = dom_values[available_idx]
            unit.days_vacant = dv_values[vacant_idx]
            available_idx += 1
            vacant_idx += 1

        elif status == "ON_NOTICE":
            unit.current_rent = float(on_notice_rents[on_notice_idx])
            on_notice_idx += 1
            unit.asking_rent = float(asking_rents[available_idx])
            unit.days_on_market = dom_values[available_idx]
            unit.move_out_date = REF_DATE + timedelta(days=on_notice_move_out_days)
            unit.tenant_id = f"T-{unit_type_code}-ON-{on_notice_idx:03d}"
            unit.lease_start = REF_DATE - timedelta(days=365)
            unit.lease_end = REF_DATE + timedelta(days=on_notice_move_out_days)
            available_idx += 1

        units_to_add.append(unit)

    db.add_all(units_to_add)
