"""Lease term metrics computation. Pure function — no DB access."""
from datetime import date
from collections import defaultdict

from app.engine.utils import round_half_up, safe_divide


def compute_lease_term_metrics(units_data: list[dict], config: dict,
                                reference_date: date) -> dict:
    """Compute lease expiration distribution and recommended terms.

    Peak season = May through September.

    Args:
        units_data: list of unit dicts with lease_end dates.
        config: client config dict with lease_term_policy.
        reference_date: current date.

    Returns:
        Dict with lease_term_metrics fields.
    """
    lease_term_policy = config.get("lease_term_policy", {})
    preferred_term = lease_term_policy.get("preferred_term_months", 14)
    target_peak_pct = lease_term_policy.get("target_peak_expiration_pct", 0.60)

    # Count expirations by month
    expiration_dist: dict[str, int] = defaultdict(int)
    occupied_with_lease = []

    for u in units_data:
        if u["status"] in ("OCCUPIED", "ON_NOTICE") and u.get("lease_end"):
            lease_end = u["lease_end"]
            month_key = f"{lease_end.year}-{lease_end.month:02d}"
            expiration_dist[month_key] += 1
            occupied_with_lease.append(u)

    # Peak season (May-Sep) expiration percentage
    peak_months = {5, 6, 7, 8, 9}
    peak_count = sum(
        1 for u in occupied_with_lease
        if u.get("lease_end") and u["lease_end"].month in peak_months
    )
    total_with_lease = len(occupied_with_lease)
    peak_pct = round_half_up(safe_divide(peak_count, total_with_lease), 2)

    # Recommended new lease term: prefer config's preferred term
    recommended_term = preferred_term

    return {
        "expiration_distribution": dict(expiration_dist),
        "peak_season_expiration_pct": peak_pct,
        "recommended_new_lease_term_months": recommended_term,
    }
