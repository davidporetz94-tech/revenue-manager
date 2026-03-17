"""Exposure metrics computation. Pure function — no DB access."""
from datetime import date, timedelta

from app.engine.utils import round_half_up, safe_divide


def compute_exposure_metrics(units_data: list[dict], reference_date: date) -> dict:
    """Compute exposure metrics including forward-looking 30/60/90d windows.

    Forward-looking exposure = (vacant + on_notice moving within window +
    occupied with lease_end within window) / total.

    Args:
        units_data: list of unit dicts with status, move_out_date, lease_end.
        reference_date: date for forward-looking calculations.

    Returns:
        Dict with exposure_metrics fields.
    """
    total = len(units_data)
    if total == 0:
        return {
            "total_exposure_pct": 0.0, "vacant_exposure_pct": 0.0,
            "exposure_30d_pct": 0.0, "exposure_60d_pct": 0.0,
            "exposure_90d_pct": 0.0, "exposure_trend": "STABLE",
        }

    vacant = sum(1 for u in units_data if u["status"] == "VACANT")
    on_notice = sum(1 for u in units_data if u["status"] == "ON_NOTICE")

    total_exposure = round_half_up(safe_divide(vacant + on_notice, total), 2)
    vacant_exposure = round_half_up(safe_divide(vacant, total), 2)

    # Forward-looking: count units that will be available within each window
    def _exposure_at_window(days: int) -> float:
        cutoff = reference_date + timedelta(days=days)
        count = vacant  # currently vacant are always counted

        for u in units_data:
            if u["status"] == "ON_NOTICE":
                move_out = u.get("move_out_date")
                if move_out and move_out <= cutoff:
                    count += 1
            elif u["status"] == "OCCUPIED":
                lease_end = u.get("lease_end")
                if lease_end and lease_end <= cutoff:
                    count += 1

        return round_half_up(safe_divide(count, total), 2)

    exp_30d = _exposure_at_window(30)
    exp_60d = _exposure_at_window(60)
    exp_90d = _exposure_at_window(90)

    # Exposure trend: deteriorating if 90d > 30d
    if exp_90d > exp_30d:
        trend = "DETERIORATING"
    elif exp_90d < exp_30d:
        trend = "IMPROVING"
    else:
        trend = "STABLE"

    return {
        "total_exposure_pct": total_exposure,
        "vacant_exposure_pct": vacant_exposure,
        "exposure_30d_pct": exp_30d,
        "exposure_60d_pct": exp_60d,
        "exposure_90d_pct": exp_90d,
        "exposure_trend": trend,
    }
