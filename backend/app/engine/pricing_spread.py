"""Pricing spread and loss-to-lease computation. Pure function — no DB access."""
from app.engine.utils import round_half_up, safe_avg, safe_divide


def compute_pricing_spreads(units_data: list[dict], comps_avg: float,
                             base_rent: float, reference_date=None) -> dict:
    """Compute all pricing spread metrics.

    Args:
        units_data: list of unit dicts.
        comps_avg: average comp asking rent for this unit type.
        base_rent: base rent for this unit type.
        reference_date: for executed rent filtering (within 90 days).

    Returns:
        Dict with pricing_spreads fields.
    """
    from datetime import timedelta

    # Asking rent: average of available units (VACANT + ON_NOTICE)
    asking_rents = [u["asking_rent"] for u in units_data
                    if u["status"] in ("VACANT", "ON_NOTICE") and u.get("asking_rent")]
    asking_rent = round(safe_avg(asking_rents)) if asking_rents else 0.0

    # Predicted rent: average across ALL units
    predicted_rents = [u["predicted_rent"] for u in units_data if u.get("predicted_rent")]
    predicted_rent = round(safe_avg(predicted_rents)) if predicted_rents else 0.0

    # In-place rent: average of occupied units (OCCUPIED + ON_NOTICE)
    in_place_rents = [u["current_rent"] for u in units_data
                      if u["status"] in ("OCCUPIED", "ON_NOTICE") and u.get("current_rent")]
    in_place_rent = round(safe_avg(in_place_rents)) if in_place_rents else 0.0

    # Executed rent: average of recent executions (within 90 days)
    exec_rents = []
    for u in units_data:
        if u.get("last_executed_rent") and u.get("last_executed_date"):
            if reference_date:
                cutoff = reference_date - timedelta(days=90)
                if u["last_executed_date"] >= cutoff:
                    exec_rents.append(u["last_executed_rent"])
            else:
                exec_rents.append(u["last_executed_rent"])
    executed_rent = round(safe_avg(exec_rents)) if exec_rents else 0.0

    # Amenity price: average amenity premium
    amenity_prices = [u["amenity_premium"] for u in units_data if u.get("amenity_premium") is not None]
    amenity_price = round(safe_avg(amenity_prices)) if amenity_prices else 0.0

    # Spreads
    asking_vs_predicted_dollars = round(asking_rent - predicted_rent)
    asking_vs_predicted_pct = round_half_up(
        safe_divide(asking_rent - predicted_rent, predicted_rent) * 100, 1
    ) if predicted_rent else 0.0

    asking_vs_comps_dollars = round(asking_rent - comps_avg)
    asking_vs_comps_pct = round_half_up(
        safe_divide(asking_rent - comps_avg, comps_avg) * 100, 1
    ) if comps_avg else 0.0

    executed_vs_asking_dollars = round(executed_rent - asking_rent) if executed_rent else 0.0
    executed_vs_asking_pct = round_half_up(
        safe_divide(executed_rent - asking_rent, asking_rent) * 100, 1
    ) if asking_rent and executed_rent else 0.0

    # Loss to lease: gap between market (asking) and in-place
    ltl_dollars = round(asking_rent - in_place_rent) if in_place_rent else 0.0
    ltl_pct = round_half_up(
        safe_divide(asking_rent - in_place_rent, in_place_rent) * 100, 1
    ) if in_place_rent else 0.0

    # Amenity as % of predicted
    amenity_pct = round_half_up(
        safe_divide(amenity_price, predicted_rent) * 100, 1
    ) if predicted_rent else 0.0

    return {
        "asking_rent": asking_rent,
        "predicted_rent": predicted_rent,
        "comps_rent": comps_avg,
        "in_place_rent": in_place_rent,
        "executed_rent": executed_rent,
        "base_rent": base_rent,
        "amenity_price": amenity_price,
        "asking_vs_predicted_dollars": asking_vs_predicted_dollars,
        "asking_vs_predicted_pct": asking_vs_predicted_pct,
        "asking_vs_comps_dollars": asking_vs_comps_dollars,
        "asking_vs_comps_pct": asking_vs_comps_pct,
        "executed_vs_asking_dollars": executed_vs_asking_dollars,
        "executed_vs_asking_pct": executed_vs_asking_pct,
        "loss_to_lease_dollars": ltl_dollars,
        "loss_to_lease_pct": ltl_pct,
        "amenity_pct_of_predicted": amenity_pct,
    }
