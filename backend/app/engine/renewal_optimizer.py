"""Renewal optimizer engine — renewal increase recommendations and revenue capture.

Pure function — no database access, no imports from services or models.
Only standard library + math.
"""
import math
from datetime import date, timedelta


# ============================================================
# Rounding Helper (round-half-up, not Python banker's rounding)
# ============================================================

def _round_half_up(x: float, decimals: int = 0) -> float:
    """Round using round-half-up convention for monetary calculations.

    Python's built-in round() uses banker's rounding (round-half-to-even),
    which can produce incorrect results for monetary values.
    """
    multiplier = 10 ** decimals
    return math.floor(x * multiplier + 0.5) / multiplier


# ============================================================
# Default Renewal Configuration
# ============================================================

_DEFAULT_RENEWAL_CONFIG: dict = {
    "freeze_below_occupancy": 0.82,
    "make_ready_cost_estimate": 2500,
    "base_non_renewal_rate": 0.10,
    "increase_sensitivity_factor": 5.0,
    "max_turnover_probability": 0.60,
    "crisis_below": 0.82,
    "stressed_below": 0.89,
    "balanced_below": 0.94,
    "strong_below": 0.97,
}


# ============================================================
# Internal Helpers
# ============================================================

def _parse_date(d: str | date | None) -> date | None:
    """Parse a date string (YYYY-MM-DD) or return a date object as-is.

    Args:
        d: Date string, date object, or None.

    Returns:
        A date object, or None if input is None or unparseable.
    """
    if d is None:
        return None
    if isinstance(d, date):
        return d
    try:
        parts = d.split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError, AttributeError):
        return None


def _count_upcoming_renewals(
    units_data: list[dict],
    reference: date,
    window_days: int = 90,
) -> int:
    """Count occupied units with lease_end within the renewal window.

    Args:
        units_data: List of unit dicts with at least status and lease_end.
        reference: The reference date to measure from.
        window_days: Number of days in the renewal window.

    Returns:
        Count of units eligible for renewal.
    """
    count = 0
    cutoff = reference + timedelta(days=window_days)
    for unit in units_data:
        if unit.get("status") != "occupied":
            continue
        lease_end = _parse_date(unit.get("lease_end"))
        if lease_end is None:
            continue
        if reference <= lease_end <= cutoff:
            count += 1
    return count


def _determine_occupancy_zone(
    occupancy_rate: float,
    config: dict,
) -> str:
    """Determine the occupancy zone from rate and config boundaries.

    Args:
        occupancy_rate: Current occupancy rate (0-1).
        config: Config dict with zone boundary keys.

    Returns:
        Zone string: CRISIS, STRESSED, BALANCED, STRONG, or FULL.
    """
    crisis = config.get("crisis_below", 0.82)
    stressed = config.get("stressed_below", 0.89)
    balanced = config.get("balanced_below", 0.94)
    strong = config.get("strong_below", 0.97)

    if occupancy_rate < crisis:
        return "CRISIS"
    elif occupancy_rate < stressed:
        return "STRESSED"
    elif occupancy_rate < balanced:
        return "BALANCED"
    elif occupancy_rate < strong:
        return "STRONG"
    else:
        return "FULL"


def _lookup_increase_pct(
    zone: str,
    ltl_pct: float,
    months_to_peak: int,
) -> float:
    """Look up the recommended renewal increase percentage from the decision table.

    Decision table:
        Strong/Full + LTL >5% + Peak (months_to_peak <= 3): 5.0%
        Strong/Full + LTL >5% + Off-peak: 3.5%
        Strong/Full + LTL <=5% + Any: 2.5%
        Balanced + LTL >5% + Peak: 3.5%
        Balanced + Any + Off-peak: 2.0%
        Stressed/Crisis + Any + Any: 0.0% (freeze)

    Args:
        zone: Occupancy zone string.
        ltl_pct: Loss-to-lease percentage (positive = upside).
        months_to_peak: Months until peak season.

    Returns:
        Recommended increase percentage.
    """
    is_peak = months_to_peak <= 3
    has_ltl_upside = ltl_pct > 0.05

    if zone in ("CRISIS", "STRESSED"):
        return 0.0

    if zone in ("STRONG", "FULL"):
        if has_ltl_upside:
            if is_peak:
                return 5.0
            else:
                return 3.5
        else:
            return 2.5

    # BALANCED
    if has_ltl_upside and is_peak:
        return 3.5
    else:
        return 2.0


# ============================================================
# Main Function
# ============================================================

def compute_renewal_opportunity(
    unit_type_metrics: dict,
    elasticity: dict,
    seasonal_context: dict,
    units_data: list[dict],
    reference_date: str,
    renewal_config: dict,
) -> dict:
    """Compute renewal increase recommendations and revenue capture potential.

    Pure function — no DB access, no service imports.

    Args:
        unit_type_metrics: Dict with occupancy_metrics, pricing_spreads,
            velocity_metrics, ltl_analysis.
        elasticity: Output of compute_implied_elasticity().
        seasonal_context: Dict with season, seasonal_factor, months_to_peak.
        units_data: List of unit dicts with at least status and lease_end.
        reference_date: String date (e.g., "2026-03-18").
        renewal_config: Dict with configurable parameters (all have defaults).

    Returns:
        Dict with renewal recommendation fields including recommended_increase_pct,
        gross/net capture, turnover estimates, and confidence.
    """
    # Merge config with defaults
    config = {**_DEFAULT_RENEWAL_CONFIG, **(renewal_config or {})}

    # Parse reference date
    ref_date = _parse_date(reference_date)
    if ref_date is None:
        ref_date = date.today()

    # Extract metrics
    occ_metrics = unit_type_metrics.get("occupancy_metrics", {})
    pricing = unit_type_metrics.get("pricing_spreads", {})
    velocity = unit_type_metrics.get("velocity_metrics", {})
    ltl = unit_type_metrics.get("ltl_analysis", {})

    occupancy_rate = occ_metrics.get("occupancy_rate", 0.0)
    in_place_rent = pricing.get("in_place_rent", 0.0)
    asking_rent = pricing.get("asking_rent", 0.0)
    avg_dom = velocity.get("avg_dom", 30)
    ltl_pct = ltl.get("ltl_pct", 0.0)

    months_to_peak = seasonal_context.get("months_to_peak", 6)

    # Step 1: Count upcoming renewals
    upcoming_renewals = _count_upcoming_renewals(units_data, ref_date)

    # Step 2: Determine occupancy zone
    zone = _determine_occupancy_zone(occupancy_rate, config)

    # Step 3: Lookup recommended increase
    increase_pct = _lookup_increase_pct(zone, ltl_pct, months_to_peak)
    increase_dollars = _round_half_up(increase_pct / 100 * in_place_rent, 2)

    # Step 4: Turnover cost model
    base_rate = config.get("base_non_renewal_rate", 0.10)
    sensitivity = config.get("increase_sensitivity_factor", 5.0)
    max_cap = config.get("max_turnover_probability", 0.60)
    make_ready_cost = config.get("make_ready_cost_estimate", 2500)

    turnover_probability = min(
        max_cap,
        base_rate * (1 + increase_pct * sensitivity / 100),
    )
    turnover_probability = _round_half_up(turnover_probability, 4)

    turnover_cost_per_unit = _round_half_up(
        avg_dom * (asking_rent / 30) + make_ready_cost, 2,
    )

    # Revenue capture
    gross_annual = _round_half_up(increase_dollars * upcoming_renewals * 12, 2)
    estimated_turnover_cost = _round_half_up(
        turnover_probability * turnover_cost_per_unit * upcoming_renewals, 2,
    )
    net_annual = _round_half_up(gross_annual - estimated_turnover_cost, 2)
    net_monthly = _round_half_up(net_annual / 12, 2) if net_annual != 0 else 0.0

    # Step 5: Confidence
    if upcoming_renewals == 0:
        confidence = "LOW"
    else:
        confidence = elasticity.get("confidence", "LOW")

    return {
        "upcoming_renewals_90d": upcoming_renewals,
        "recommended_increase_pct": increase_pct,
        "recommended_increase_dollars": increase_dollars,
        "gross_annual_capture": gross_annual,
        "estimated_turnover_probability": turnover_probability,
        "estimated_turnover_cost": estimated_turnover_cost,
        "net_annual_capture": net_annual,
        "net_monthly_capture": net_monthly,
        "confidence": confidence,
    }
