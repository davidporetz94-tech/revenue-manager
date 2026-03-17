"""Seasonal context computation. Pure function — no DB access."""
from datetime import date


def compute_seasonal_context(reference_date: date) -> dict:
    """Compute seasonal context for the reference date.

    Peak leasing season: May through September.
    Spring ramp: March-April.
    Off-peak: October-February.

    Returns:
        Dict with seasonal context information.
    """
    month = reference_date.month

    if month in (5, 6, 7, 8, 9):
        season = "PEAK"
        description = "Peak leasing season — highest demand and pricing power"
    elif month in (3, 4):
        season = "SPRING_RAMP"
        description = "Spring ramp-up — demand accelerating toward peak season"
    elif month in (10, 11):
        season = "FALL_DECEL"
        description = "Fall deceleration — demand declining from peak"
    else:
        season = "OFF_PEAK"
        description = "Off-peak season — lowest demand, concessions more common"

    # Seasonal adjustment factor (approximate)
    seasonal_factors = {
        1: 0.93, 2: 0.95, 3: 0.98, 4: 1.02,
        5: 1.05, 6: 1.07, 7: 1.06, 8: 1.04,
        9: 1.01, 10: 0.97, 11: 0.94, 12: 0.92,
    }

    return {
        "season": season,
        "description": description,
        "month": month,
        "seasonal_factor": seasonal_factors.get(month, 1.0),
        "months_to_peak": max(0, 5 - month) if month <= 5 else max(0, 17 - month),
    }
