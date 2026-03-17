"""Occupancy metrics computation. Pure function — no DB access."""
from app.engine.utils import round_half_up, safe_divide


def compute_occupancy_metrics(units_data: list[dict]) -> dict:
    """Compute occupancy metrics from unit-level data.

    Args:
        units_data: list of unit dicts with at least 'status' field.
            Status values: OCCUPIED, VACANT, ON_NOTICE.
            Export convention: 'occupied' includes ON_NOTICE (they still pay rent).

    Returns:
        Dict with occupancy_metrics fields.
    """
    total = len(units_data)
    if total == 0:
        return {
            "occupied": 0, "vacant": 0, "on_notice": 0, "available": 0,
            "occupancy_rate": 0.0, "vacancy_rate": 0.0,
        }

    occupied_count = sum(1 for u in units_data if u["status"] in ("OCCUPIED", "ON_NOTICE"))
    vacant_count = sum(1 for u in units_data if u["status"] == "VACANT")
    on_notice_count = sum(1 for u in units_data if u["status"] == "ON_NOTICE")
    available = vacant_count + on_notice_count

    occupancy_rate = round_half_up(safe_divide(occupied_count, total), 2)
    vacancy_rate = round_half_up(safe_divide(vacant_count, total), 2)

    return {
        "occupied": occupied_count,
        "vacant": vacant_count,
        "on_notice": on_notice_count,
        "available": available,
        "occupancy_rate": occupancy_rate,
        "vacancy_rate": vacancy_rate,
    }
