"""Revenue metrics computation. Pure function — no DB access."""
from app.engine.utils import round_half_up, safe_divide


def compute_revenue_metrics(pricing_spreads: dict, occupancy_metrics: dict) -> dict:
    """Compute revenue metrics from pricing spreads and occupancy data.

    Key formulas:
    - daily_vacancy_burn = (asking_rent / 30) * vacant_units
    - revenue_at_risk_30d = daily_vacancy_burn * 30
    - monthly_vacancy_cost = asking_rent * vacant_units (simplified)
    - price_reduction_breakeven = (reduction * 12) / (asking_rent / 30)
      i.e., days faster fill needed to justify a $50/mo reduction

    Args:
        pricing_spreads: dict from compute_pricing_spreads.
        occupancy_metrics: dict from compute_occupancy_metrics.

    Returns:
        Dict with revenue_metrics fields.
    """
    asking = pricing_spreads["asking_rent"]
    in_place = pricing_spreads["in_place_rent"]
    vacant = occupancy_metrics["vacant"]
    occupied = occupancy_metrics["occupied"]
    total = occupied + vacant

    # Daily vacancy burn: (asking / 30) * vacant
    daily_rate = safe_divide(asking, 30)
    daily_vacancy_burn = round(daily_rate * vacant)

    # Revenue at risk over 30 days
    revenue_at_risk_30d = round(daily_vacancy_burn * 30)

    # Monthly potential (if fully leased at asking)
    monthly_potential = round(asking * total)

    # Monthly actual (occupied units at their current rent)
    monthly_actual = round(in_place * occupied) if in_place else 0

    # Monthly vacancy cost
    monthly_vacancy_cost = round(asking * vacant)

    # Accumulated vacancy cost (from avg days vacant)
    # Not computable without individual unit DV; use monthly as proxy
    accumulated = monthly_vacancy_cost

    # Price reduction breakeven: how many days faster must a unit fill
    # to justify a $50/month reduction?
    # breakeven_days = (reduction_per_month * 12) / daily_rate
    reduction = 50  # standard $50/mo reduction
    breakeven_days = round_half_up(
        safe_divide(reduction * 12, daily_rate), 1
    ) if daily_rate > 0 else 0.0

    return {
        "monthly_potential_revenue": monthly_potential,
        "monthly_actual_revenue": monthly_actual,
        "monthly_vacancy_cost": monthly_vacancy_cost,
        "accumulated_vacancy_cost": accumulated,
        "daily_vacancy_burn": daily_vacancy_burn,
        "revenue_at_risk_30d": revenue_at_risk_30d,
        "price_reduction_breakeven_days": breakeven_days,
    }
