"""Revenue optimizer engine — implied elasticity and optimal price computation.

Pure functions — no database access, no imports from services or models.
Only standard library + math.
"""
import math


# ============================================================
# Default Zone Configuration
# ============================================================

DEFAULT_ZONE_CONFIG: dict = {
    "crisis_below": 0.82,
    "stressed_below": 0.90,
    "healthy_above": 0.94,
}


# ============================================================
# Field Accessors (handle naming convention variations)
# ============================================================

def _get_occupancy(snapshot: dict) -> float:
    """Extract occupancy from a snapshot, handling both field name conventions."""
    return snapshot.get("occupancy_rate", snapshot.get("avg_occupancy", 0.0))


def _get_asking_rent(snapshot: dict) -> float:
    """Extract asking rent from a snapshot, handling both field name conventions."""
    return snapshot.get("avg_asking_rent", snapshot.get("asking_rent", 0.0))


def _get_comp_rent(snapshot: dict) -> float:
    """Extract comp rent from a snapshot, handling both field name conventions."""
    return snapshot.get("comps_avg", snapshot.get("avg_comp_asking", 0.0))


# ============================================================
# compute_implied_elasticity
# ============================================================

def compute_implied_elasticity(
    snapshot_trends: list[dict],
    comp_trends: list[dict],
) -> dict:
    """Estimate price sensitivity per unit type from snapshot history.

    Computes month-over-month rent % changes and occupancy changes to derive
    a crude elasticity coefficient: how much does occupancy change per 1% price change?

    Args:
        snapshot_trends: Monthly snapshots with occupancy and asking rent data.
            Supports both 'occupancy_rate'/'avg_asking_rent' and
            'avg_occupancy'/'asking_rent' field naming conventions.
        comp_trends: Monthly comp data with asking rent.
            Supports both 'avg_asking_rent' and 'asking_rent' field names.

    Returns:
        Dict with elasticity_coefficient, confidence, data_points, direction, notes.
    """
    n = len(snapshot_trends)

    if n < 2:
        return {
            "elasticity_coefficient": 0.0,
            "confidence": "LOW",
            "data_points": n,
            "direction": "UNKNOWN",
            "notes": "Insufficient data points for elasticity estimation" if n == 0
                     else "Only one data point — cannot compute month-over-month changes",
        }

    # Compute month-over-month changes
    rent_pct_changes: list[float] = []
    occ_changes: list[float] = []

    for i in range(1, n):
        prev_rent = _get_asking_rent(snapshot_trends[i - 1])
        curr_rent = _get_asking_rent(snapshot_trends[i])
        prev_occ = _get_occupancy(snapshot_trends[i - 1])
        curr_occ = _get_occupancy(snapshot_trends[i])

        if prev_rent > 0:
            rent_pct_change = (curr_rent - prev_rent) / prev_rent * 100
            rent_pct_changes.append(rent_pct_change)

        occ_change = curr_occ - prev_occ
        occ_changes.append(occ_change)

    if not rent_pct_changes:
        return {
            "elasticity_coefficient": 0.0,
            "confidence": "LOW",
            "data_points": n,
            "direction": "UNKNOWN",
            "notes": "Could not compute rent changes — zero or missing rent data",
        }

    avg_rent_pct_change = sum(abs(x) for x in rent_pct_changes) / len(rent_pct_changes)
    avg_occ_change = sum(occ_changes) / len(occ_changes)
    avg_rent_direction = sum(rent_pct_changes) / len(rent_pct_changes)

    # If rent barely changed, we can't estimate elasticity meaningfully
    if avg_rent_pct_change < 0.2:
        return {
            "elasticity_coefficient": 0.0,
            "confidence": "LOW",
            "data_points": n,
            "direction": "INELASTIC" if abs(avg_occ_change) < 0.01 else "UNKNOWN",
            "notes": f"Asking rent barely changed (avg {avg_rent_pct_change:.3f}% per month) — insufficient signal",
        }

    # Compute elasticity coefficient: occ change per 1% rent change
    # Use signed values to capture direction
    # Positive coefficient = when rent goes up, occ goes down (normal demand curve)
    elasticity_pairs: list[float] = []
    for i in range(len(rent_pct_changes)):
        if abs(rent_pct_changes[i]) > 0.05:  # skip near-zero rent changes
            # Negate because higher rent → lower occ means positive elasticity
            e = -occ_changes[i] / rent_pct_changes[i] * 100
            elasticity_pairs.append(e)

    if not elasticity_pairs:
        return {
            "elasticity_coefficient": 0.0,
            "confidence": "LOW",
            "data_points": n,
            "direction": "UNKNOWN",
            "notes": "Rent changes too small to compute reliable elasticity pairs",
        }

    avg_elasticity = sum(elasticity_pairs) / len(elasticity_pairs)

    # Determine direction
    # The raw coefficient can be misleading when both rent and occ move in the
    # same direction. We need to also consider the *pattern* of change.
    #
    # Key patterns:
    #   rent UP   + occ DOWN  → classic ELASTIC (positive coefficient)
    #   rent DOWN + occ UP    → classic ELASTIC (positive coefficient)
    #   rent UP   + occ UP    → INELASTIC (strong market, negative coefficient)
    #   rent DOWN + occ DOWN  → ELASTIC (overpriced, cuts not enough — negative coeff
    #                           but domain interpretation is elastic)

    # Check for the "both declining" pattern: rent falling AND occ falling
    # This is a sign of overpricing in an elastic market
    both_declining = avg_rent_direction < -0.1 and avg_occ_change < -0.005

    if both_declining:
        # Rent cuts aren't stopping the bleed → highly elastic market
        direction = "ELASTIC"
        # Use absolute value since the market IS responding to price, just
        # starting from too high a point
        avg_elasticity = abs(avg_elasticity)
    elif avg_elasticity > 0.05:
        direction = "ELASTIC"
    elif avg_elasticity < -0.05:
        # Negative means occ went UP when rent went UP (unusual — strong market)
        direction = "INELASTIC"
    else:
        direction = "UNKNOWN"

    # Determine confidence
    # Check consistency: do all pairs agree on direction?
    consistent = all(e > 0 for e in elasticity_pairs) or all(e <= 0 for e in elasticity_pairs)

    if n >= 4 and consistent and avg_rent_pct_change >= 0.5:
        confidence = "HIGH"
    elif n >= 3 and avg_rent_pct_change >= 0.3:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    notes_parts = []
    notes_parts.append(f"Based on {len(elasticity_pairs)} month-over-month observation(s)")
    notes_parts.append(f"avg rent change: {avg_rent_direction:+.2f}%/mo")
    notes_parts.append(f"avg occ change: {avg_occ_change:+.4f}/mo")
    if not consistent:
        notes_parts.append("direction inconsistent across periods")

    return {
        "elasticity_coefficient": round(abs(avg_elasticity), 4),
        "confidence": confidence,
        "data_points": n,
        "direction": direction,
        "notes": "; ".join(notes_parts),
    }


# ============================================================
# compute_optimal_price
# ============================================================

def compute_optimal_price(
    unit_type_metrics: dict,
    elasticity: dict,
    seasonal_context: dict,
    zone_config: dict | None = None,
) -> dict:
    """Find the revenue-maximizing asking rent for a unit type.

    Sweeps +-10% from current asking in 0.5% steps, estimates occupancy at each
    price point using the elasticity coefficient, and finds the peak of
    rent x occupied_units. Constrained within +-15% of comps.

    Args:
        unit_type_metrics: Dict with occupancy_metrics, pricing_spreads, etc.
        elasticity: Output from compute_implied_elasticity.
        seasonal_context: Dict with season, seasonal_factor, months_to_peak.
        zone_config: Optional zone boundary config. Defaults applied if None.

    Returns:
        Dict with optimal_asking, revenue calculations, direction, confidence, etc.
    """
    config = {**DEFAULT_ZONE_CONFIG, **(zone_config or {})}

    # Extract metrics
    occ_metrics = unit_type_metrics.get("occupancy_metrics", {})
    pricing = unit_type_metrics.get("pricing_spreads", {})

    current_asking = pricing.get("asking_rent", 0)
    comps_rent = pricing.get("comps_rent", pricing.get("comps_avg", 0))
    total_units = occ_metrics.get("total_units", 0)
    current_occ = occ_metrics.get("occupancy_rate", occ_metrics.get("avg_occupancy", 0))

    elasticity_coeff = elasticity.get("elasticity_coefficient", 0.0)

    # Current revenue estimate
    current_occupied = total_units * current_occ
    current_revenue = current_asking * current_occupied

    if total_units == 0 or current_asking == 0:
        return _empty_result(current_revenue)

    # Comp constraints: +-15%
    comp_floor = comps_rent * 0.85 if comps_rent > 0 else 0
    comp_ceiling = comps_rent * 1.15 if comps_rent > 0 else float("inf")

    # Vacancy cost penalty thresholds from zone config
    crisis_threshold = config.get("crisis_below", 0.82)
    stressed_threshold = config.get("stressed_below", 0.90)

    # Sweep +-10% from current asking in 0.5% steps (41 price points)
    best_price = current_asking
    best_score = -float("inf")
    comp_constrained = False

    for step in range(-20, 21):  # -10% to +10% in 0.5% increments
        pct_change = step * 0.5  # percentage change from current
        candidate_price = current_asking * (1 + pct_change / 100)

        # Estimate occupancy at this price point
        # If price goes up by X%, occupancy drops by elasticity_coeff * X percentage points
        # (elasticity_coeff is occ change per 1% price change)
        occ_delta = -elasticity_coeff * pct_change / 100  # convert to occupancy points
        estimated_occ = current_occ + occ_delta

        # Clamp occupancy to [0, 1]
        estimated_occ = max(0.0, min(1.0, estimated_occ))

        estimated_occupied = total_units * estimated_occ
        estimated_revenue = candidate_price * estimated_occupied

        # Apply vacancy cost penalty — penalize prices that push occupancy
        # into stressed or crisis zones. This captures the real cost of
        # vacancies beyond lost rent (turns, marketing, deterioration).
        vacancy_penalty = _compute_vacancy_penalty(
            estimated_occ, candidate_price, total_units,
            crisis_threshold, stressed_threshold,
        )

        score = estimated_revenue - vacancy_penalty

        if score > best_score:
            best_score = score
            best_price = candidate_price
            best_revenue = estimated_revenue

    # Apply comp constraint
    if comps_rent > 0:
        if best_price > comp_ceiling:
            best_price = comp_ceiling
            comp_constrained = True
        elif best_price < comp_floor:
            best_price = comp_floor
            comp_constrained = True

    # Recalculate revenue at constrained price
    if comp_constrained:
        pct_from_current = (best_price - current_asking) / current_asking * 100
        occ_delta = -elasticity_coeff * pct_from_current / 100
        constrained_occ = max(0.0, min(1.0, current_occ + occ_delta))
        best_revenue = best_price * total_units * constrained_occ

    # Apply seasonal adjustment
    seasonal_adjustment = _compute_seasonal_adjustment(seasonal_context)
    best_price = best_price * (1 + seasonal_adjustment / 100)

    # Re-apply comp constraint after seasonal adjustment
    if comps_rent > 0:
        if best_price > comp_ceiling:
            best_price = comp_ceiling
            comp_constrained = True
        elif best_price < comp_floor:
            best_price = comp_floor
            comp_constrained = True

    # Recalculate final revenue at adjusted price
    pct_from_current = (best_price - current_asking) / current_asking * 100 if current_asking > 0 else 0
    occ_delta = -elasticity_coeff * pct_from_current / 100
    final_occ = max(0.0, min(1.0, current_occ + occ_delta))
    optimal_revenue = best_price * total_units * final_occ

    # Round to nearest dollar
    optimal_asking = round(best_price, 2)
    optimal_revenue_monthly = round(optimal_revenue, 2)
    revenue_gap = round(optimal_revenue - current_revenue, 2)

    # Conservative recommendation: halfway between current and optimal
    recommended_asking = round((current_asking + optimal_asking) / 2, 2)

    # Determine price direction
    pct_diff = (optimal_asking - current_asking) / current_asking * 100 if current_asking > 0 else 0
    if pct_diff > 2:
        price_direction = "INCREASE"
    elif pct_diff < -2:
        price_direction = "DECREASE"
    else:
        price_direction = "HOLD"

    # Determine confidence based on elasticity confidence and zone
    confidence = _determine_confidence(
        elasticity_confidence=elasticity.get("confidence", "LOW"),
        occupancy=current_occ,
        config=config,
    )

    return {
        "optimal_asking": optimal_asking,
        "optimal_revenue_monthly": optimal_revenue_monthly,
        "current_revenue_monthly": round(current_revenue, 2),
        "revenue_gap_monthly": revenue_gap,
        "price_direction": price_direction,
        "recommended_asking": recommended_asking,
        "confidence": confidence,
        "seasonal_adjustment_applied": seasonal_adjustment,
        "comp_constrained": comp_constrained,
    }


# ============================================================
# Internal Helpers
# ============================================================

def _compute_vacancy_penalty(
    estimated_occ: float,
    candidate_price: float,
    total_units: int,
    crisis_threshold: float,
    stressed_threshold: float,
) -> float:
    """Compute a vacancy cost penalty for the revenue sweep.

    When occupancy drops into stressed or crisis territory, each vacant unit
    carries additional costs beyond lost rent: turns, marketing, deterioration,
    and community reputation damage. This penalty makes the optimizer prefer
    higher-occupancy solutions when occupancy is already stressed.

    Args:
        estimated_occ: Estimated occupancy at the candidate price.
        candidate_price: The candidate asking rent.
        total_units: Total number of units.
        crisis_threshold: Occupancy below this is crisis zone.
        stressed_threshold: Occupancy below this is stressed zone.

    Returns:
        Monthly penalty amount in dollars.
    """
    if estimated_occ >= stressed_threshold:
        return 0.0

    vacant_units = total_units * (1 - estimated_occ)

    if estimated_occ < crisis_threshold:
        # Crisis zone: heavy penalty — each vacant unit costs ~50% of asking
        # per month in hidden costs (turns, marketing, deterioration)
        penalty_per_unit = candidate_price * 0.50
    else:
        # Stressed zone: moderate penalty — each vacant unit costs ~25% of asking
        penalty_per_unit = candidate_price * 0.25

    return vacant_units * penalty_per_unit


def _compute_seasonal_adjustment(seasonal_context: dict) -> float:
    """Compute seasonal price adjustment percentage.

    Approaching peak (months_to_peak <= 3): bump up 1%.
    Off-peak (months_to_peak >= 9): bump down 1%.
    Otherwise: no adjustment.

    Returns:
        Adjustment as a percentage (e.g., 1.0 means +1%, -1.0 means -1%).
    """
    months_to_peak = seasonal_context.get("months_to_peak", 6)

    if months_to_peak <= 3:
        return 1.0  # +1% approaching peak
    elif months_to_peak >= 9:
        return -1.0  # -1% during off-peak
    else:
        return 0.0


def _determine_confidence(
    elasticity_confidence: str,
    occupancy: float,
    config: dict,
) -> str:
    """Determine confidence level for optimal price recommendation.

    Higher confidence when:
    - Elasticity data is strong
    - Occupancy is clearly in a defined zone (not borderline)

    Args:
        elasticity_confidence: Confidence from elasticity computation.
        occupancy: Current occupancy rate.
        config: Zone config with crisis_below, stressed_below, healthy_above.

    Returns:
        'LOW', 'MEDIUM', or 'HIGH'.
    """
    # Start with elasticity confidence as baseline
    levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    base = levels.get(elasticity_confidence, 0)

    # Boost if occupancy is clearly in a zone (not borderline)
    crisis = config.get("crisis_below", 0.82)
    stressed = config.get("stressed_below", 0.90)
    healthy = config.get("healthy_above", 0.94)

    # Clear zones give more confidence
    if occupancy < crisis - 0.03 or occupancy > healthy + 0.03:
        base = min(base + 1, 2)
    elif stressed - 0.02 < occupancy < stressed + 0.02:
        # Borderline stressed — less confident
        base = max(base - 1, 0)

    reverse = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
    return reverse[base]


def _empty_result(current_revenue: float) -> dict:
    """Return a safe default result when inputs are invalid."""
    return {
        "optimal_asking": 0.0,
        "optimal_revenue_monthly": 0.0,
        "current_revenue_monthly": round(current_revenue, 2),
        "revenue_gap_monthly": 0.0,
        "price_direction": "HOLD",
        "recommended_asking": 0.0,
        "confidence": "LOW",
        "seasonal_adjustment_applied": 0.0,
        "comp_constrained": False,
    }
