"""Loss-to-lease analysis. Pure function — no DB access.

LTL is already computed in pricing_spread.py as part of the spreads.
This module provides additional LTL analysis helpers.
"""
from app.engine.utils import round_half_up, safe_divide


def compute_ltl_analysis(pricing_spreads: dict) -> dict:
    """Extended loss-to-lease analysis beyond basic spread.

    Returns:
        Dict with ltl analysis: direction, annual_impact, etc.
    """
    ltl_dollars = pricing_spreads["loss_to_lease_dollars"]
    ltl_pct = pricing_spreads["loss_to_lease_pct"]
    in_place = pricing_spreads["in_place_rent"]

    if ltl_dollars > 0:
        direction = "UPSIDE"
    elif ltl_dollars < 0:
        direction = "NEGATIVE"
    else:
        direction = "ALIGNED"

    # Annual impact per unit
    annual_impact = ltl_dollars * 12

    return {
        "ltl_dollars": ltl_dollars,
        "ltl_pct": ltl_pct,
        "ltl_direction": direction,
        "ltl_annual_impact_per_unit": annual_impact,
    }
