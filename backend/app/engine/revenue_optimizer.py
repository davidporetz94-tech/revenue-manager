"""Revenue optimizer engine — elasticity, optimal price, gap decomposition, efficiency scoring.

Pure functions — no database access, no imports from services or models.
Only standard library + math.
"""
import math


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
            "comp_corroborated": False,
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
            "comp_corroborated": False,
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
            "comp_corroborated": False,
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
            "comp_corroborated": False,
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

    # Comp corroboration: if comp rents moved in the same direction as asking
    # rents, that corroborates the signal and can bump confidence one level.
    notes_parts: list[str] = []
    comp_corroborated = False

    if comp_trends and len(comp_trends) >= 2:
        comp_rent_changes: list[float] = []
        for i in range(1, len(comp_trends)):
            prev_comp = _get_asking_rent(comp_trends[i - 1])
            curr_comp = _get_asking_rent(comp_trends[i])
            if prev_comp > 0:
                comp_rent_changes.append((curr_comp - prev_comp) / prev_comp * 100)

        if comp_rent_changes:
            avg_comp_direction = sum(comp_rent_changes) / len(comp_rent_changes)
            # Same direction = both positive or both negative
            same_direction = (avg_rent_direction > 0.05 and avg_comp_direction > 0.05) or \
                             (avg_rent_direction < -0.05 and avg_comp_direction < -0.05)

            if same_direction:
                comp_corroborated = True
                # Bump confidence one level
                levels_map = {"LOW": "MEDIUM", "MEDIUM": "HIGH", "HIGH": "HIGH"}
                confidence = levels_map[confidence]
                notes_parts.append(
                    f"comp corroboration: comps moved {avg_comp_direction:+.2f}%/mo "
                    f"(same direction as asking {avg_rent_direction:+.2f}%/mo) — confidence boosted"
                )
            else:
                notes_parts.append(
                    f"comp divergence: comps moved {avg_comp_direction:+.2f}%/mo "
                    f"vs asking {avg_rent_direction:+.2f}%/mo"
                )
    else:
        notes_parts.append("no comp trend data available for corroboration")

    notes_parts.append(f"Based on {len(elasticity_pairs)} month-over-month observation(s)")
    notes_parts.append(f"avg rent change: {avg_rent_direction:+.2f}%/mo")
    notes_parts.append(f"avg occ change: {avg_occ_change:+.4f}/mo")
    if not consistent:
        notes_parts.append("direction inconsistent across periods")

    return {
        "elasticity_coefficient": _round_half_up(abs(avg_elasticity), 4),
        "confidence": confidence,
        "data_points": n,
        "direction": direction,
        "comp_corroborated": comp_corroborated,
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
    seasonal_adjustment_pct = _compute_seasonal_adjustment(seasonal_context)
    price_before_seasonal = best_price
    best_price = best_price * (1 + seasonal_adjustment_pct / 100)
    seasonal_adjustment_dollars = _round_half_up(best_price - price_before_seasonal, 2)

    # Re-apply comp constraint after seasonal adjustment
    if comps_rent > 0:
        if best_price > comp_ceiling:
            best_price = comp_ceiling
            comp_constrained = True
            # Recalculate seasonal dollars if comp-capped
            seasonal_adjustment_dollars = _round_half_up(best_price - price_before_seasonal, 2)
        elif best_price < comp_floor:
            best_price = comp_floor
            comp_constrained = True
            seasonal_adjustment_dollars = _round_half_up(best_price - price_before_seasonal, 2)

    # Recalculate final revenue at adjusted price
    pct_from_current = (best_price - current_asking) / current_asking * 100 if current_asking > 0 else 0
    occ_delta = -elasticity_coeff * pct_from_current / 100
    final_occ = max(0.0, min(1.0, current_occ + occ_delta))
    optimal_revenue = best_price * total_units * final_occ

    # Round to nearest dollar
    optimal_asking = _round_half_up(best_price, 2)
    optimal_revenue_monthly = _round_half_up(optimal_revenue, 2)
    revenue_gap = _round_half_up(optimal_revenue - current_revenue, 2)

    # Conservative recommendation: halfway between current and optimal
    recommended_asking = _round_half_up((current_asking + optimal_asking) / 2, 2)

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
        "current_revenue_monthly": _round_half_up(current_revenue, 2),
        "revenue_gap_monthly": revenue_gap,
        "price_direction": price_direction,
        "recommended_asking": recommended_asking,
        "confidence": confidence,
        "seasonal_adjustment_applied": seasonal_adjustment_dollars,
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


# ============================================================
# decompose_revenue_gap
# ============================================================

def decompose_revenue_gap(
    unit_type_metrics: dict,
    optimal: dict,
    renewal_analysis: dict,
    concession_data: dict,
) -> dict:
    """Break total revenue gap into 5 actionable lever components.

    Each component identifies a specific lever (FILL, REPRICE, RENEW,
    DE_CONCESSION) and the monthly dollar amount addressable through that lever.

    Args:
        unit_type_metrics: Dict with occupancy_metrics, pricing_spreads, ltl_analysis.
        optimal: Output from compute_optimal_price.
        renewal_analysis: Dict with upcoming_renewals_90d, net_monthly_capture.
        concession_data: Dict with total_concession_drag_monthly.

    Returns:
        Dict with current/optimal revenue, total gap, gap_components,
        dominant_lever, and lever_ranking.
    """
    occ_metrics = unit_type_metrics.get("occupancy_metrics", {})
    pricing = unit_type_metrics.get("pricing_spreads", {})
    ltl = unit_type_metrics.get("ltl_analysis", {})

    occupied = occ_metrics.get("occupied", 0)
    vacant = occ_metrics.get("vacant", 0)
    current_asking = pricing.get("asking_rent", 0)
    in_place_rent = pricing.get("in_place_rent", 0)
    ltl_dollars = ltl.get("ltl_dollars", 0)

    optimal_asking = optimal.get("optimal_asking", current_asking)

    # Current monthly revenue: in-place rent x occupied units
    current_monthly_revenue = _round_half_up(in_place_rent * occupied, 2)

    # Optimal monthly revenue from optimizer output
    optimal_monthly_revenue = optimal.get("optimal_revenue_monthly", current_monthly_revenue)

    total_gap = _round_half_up(optimal_monthly_revenue - current_monthly_revenue, 2)

    # Component calculations
    vacancy_cost = _round_half_up(vacant * current_asking, 2)
    new_lease_underpricing = _round_half_up(
        max(0.0, optimal_asking - current_asking) * vacant, 2,
    )
    in_place_underpricing = _round_half_up(
        max(0.0, ltl_dollars) * occupied, 2,
    )
    renewal_opportunity = _round_half_up(
        renewal_analysis.get("net_monthly_capture", 0.0), 2,
    )
    concession_drag = _round_half_up(
        concession_data.get("total_concession_drag_monthly", 0.0), 2,
    )

    gap_components = {
        "vacancy_cost": {
            "amount": vacancy_cost,
            "lever": "FILL",
            "description": "Revenue lost to empty units",
        },
        "new_lease_underpricing": {
            "amount": new_lease_underpricing,
            "lever": "REPRICE",
            "description": "Revenue lost from asking below optimal on new leases",
        },
        "in_place_underpricing": {
            "amount": in_place_underpricing,
            "lever": "RENEW",
            "description": "Revenue gap in current leases, addressable at renewal",
        },
        "renewal_opportunity": {
            "amount": renewal_opportunity,
            "lever": "RENEW",
            "description": "Capturable through upcoming renewal increases",
        },
        "concession_drag": {
            "amount": concession_drag,
            "lever": "DE_CONCESSION",
            "description": "Revenue reduction from active concessions",
        },
    }

    # Rank components by amount descending
    lever_ranking = sorted(
        gap_components.keys(),
        key=lambda k: gap_components[k]["amount"],
        reverse=True,
    )

    # Dominant lever is the lever of the largest component
    dominant_lever = gap_components[lever_ranking[0]]["lever"]

    return {
        "current_monthly_revenue": current_monthly_revenue,
        "optimal_monthly_revenue": optimal_monthly_revenue,
        "total_gap_monthly": total_gap,
        "gap_components": gap_components,
        "dominant_lever": dominant_lever,
        "lever_ranking": lever_ranking,
    }


# ============================================================
# compute_revenue_efficiency
# ============================================================

def compute_revenue_efficiency(
    unit_type_metrics: dict,
    optimal: dict,
    snapshot_trends: list[dict],
    seasonal_context: dict,
    zone_config: dict | None = None,
    revenue_gap: dict | None = None,
) -> dict:
    """Compute a unified revenue efficiency score (0-100) with 4 dimensions.

    Four dimensions: occupancy health, pricing alignment, rent roll momentum,
    and revenue capture. Weights shift dynamically based on occupancy zone
    and seasonal context.

    The occupancy target is the client-configured market occupancy
    (zone_config["market_occupancy"]), not a hardcoded value.

    Args:
        unit_type_metrics: Dict with occupancy_metrics, pricing_spreads.
        optimal: Output from compute_optimal_price.
        snapshot_trends: Monthly snapshots for trend analysis.
        seasonal_context: Dict with season, seasonal_factor, months_to_peak.
        zone_config: Optional zone boundary and weight config.
        revenue_gap: Output from decompose_revenue_gap (optional).

    Returns:
        Dict with revenue_efficiency_score, grade, dimensions,
        dynamic_weights_reason, occupancy_zone.
    """
    config = {
        "crisis_below": 0.82,
        "stressed_below": 0.89,
        "balanced_below": 0.94,
        "strong_below": 0.97,
        "market_occupancy": 0.95,
        "crisis_weights": [0.50, 0.10, 0.20, 0.20],
        "stressed_weights": [0.35, 0.25, 0.20, 0.20],
        "balanced_weights": [0.25, 0.30, 0.25, 0.20],
        "strong_weights": [0.10, 0.35, 0.30, 0.25],
        "full_weights": [0.05, 0.35, 0.30, 0.30],
        "seasonal_weight_shift": 0.05,
    }
    if zone_config:
        config.update(zone_config)

    occ_metrics = unit_type_metrics.get("occupancy_metrics", {})
    pricing = unit_type_metrics.get("pricing_spreads", {})

    actual_occ = occ_metrics.get("occupancy_rate", occ_metrics.get("avg_occupancy", 0.0))
    current_asking = pricing.get("asking_rent", 0)
    optimal_asking = optimal.get("optimal_asking", current_asking)

    seasonal_factor = seasonal_context.get("seasonal_factor", 1.0)
    months_to_peak = seasonal_context.get("months_to_peak", 6)

    # --- Determine occupancy zone ---
    zone, base_weights = _determine_zone_and_weights(actual_occ, config)

    # --- Apply seasonal weight shift ---
    occ_w, pricing_w, momentum_w, gap_w = base_weights
    shift = config.get("seasonal_weight_shift", 0.05)
    weight_reason_parts = [f"zone={zone}"]

    if months_to_peak <= 3:
        # Approaching peak: shift from occ to pricing
        occ_w -= shift
        pricing_w += shift
        weight_reason_parts.append(f"spring shift: +{shift:.0%} pricing, -{shift:.0%} occ")
    elif months_to_peak >= 9:
        # Off-peak: shift from pricing to occ
        pricing_w -= shift
        occ_w += shift
        weight_reason_parts.append(f"off-peak shift: +{shift:.0%} occ, -{shift:.0%} pricing")
    else:
        weight_reason_parts.append("no seasonal shift")

    # --- Dimension 1: Occupancy Health ---
    # Use client-configured market occupancy, adjusted for season
    market_occ = config.get("market_occupancy", 0.95)
    target_occ = market_occ * seasonal_factor
    occ_score = max(0, min(100, int(_round_half_up(100 - (target_occ - actual_occ) * 500))))

    # --- Dimension 2: Pricing Alignment ---
    if optimal_asking > 0:
        price_gap_pct = abs(current_asking - optimal_asking) / optimal_asking
    else:
        price_gap_pct = 0.0
    pricing_score = max(0, min(100, int(_round_half_up(100 - price_gap_pct * 1000))))

    # --- Dimension 3: Rent Roll Momentum ---
    momentum_score = _compute_momentum_score(
        snapshot_trends, current_asking, optimal_asking,
    )

    # --- Dimension 4: Revenue Capture ---
    # Measures how much of the optimal revenue is actually being captured.
    # A unit type can have high occupancy and perfect pricing alignment
    # but still bleed revenue via loss-to-lease, vacancy cost, or suboptimal
    # renewal pricing. This dimension catches that.
    gap_score = _compute_revenue_gap_score(optimal, revenue_gap)

    # --- Composite score ---
    composite = (
        occ_score * occ_w
        + pricing_score * pricing_w
        + momentum_score * momentum_w
        + gap_score * gap_w
    )
    final_score = max(0, min(100, int(_round_half_up(composite))))

    # --- Grade mapping ---
    grade = _score_to_grade(final_score)

    return {
        "revenue_efficiency_score": final_score,
        "grade": grade,
        "dimensions": {
            "occupancy_health": {"score": occ_score, "weight": _round_half_up(occ_w, 2)},
            "pricing_alignment": {"score": pricing_score, "weight": _round_half_up(pricing_w, 2)},
            "rent_roll_momentum": {"score": momentum_score, "weight": _round_half_up(momentum_w, 2)},
            "revenue_capture": {"score": gap_score, "weight": _round_half_up(gap_w, 2)},
        },
        "dynamic_weights_reason": "; ".join(weight_reason_parts),
        "occupancy_zone": zone,
        "market_occupancy_target": _round_half_up(target_occ, 3),
    }


# ============================================================
# Internal Helpers
# ============================================================

def _determine_zone_and_weights(
    occupancy: float,
    config: dict,
) -> tuple[str, list[float]]:
    """Determine occupancy zone and base dynamic weights.

    Args:
        occupancy: Current occupancy rate.
        config: Zone config with boundaries and weight arrays.

    Returns:
        Tuple of (zone_name, [occ_weight, pricing_weight, momentum_weight, gap_weight]).
    """
    crisis = config.get("crisis_below", 0.82)
    stressed = config.get("stressed_below", 0.89)
    balanced = config.get("balanced_below", 0.94)
    strong = config.get("strong_below", 0.97)

    if occupancy < crisis:
        w = list(config.get("crisis_weights", [0.50, 0.10, 0.20, 0.20]))
        return "CRISIS", _ensure_4_weights(w)
    elif occupancy < stressed:
        w = list(config.get("stressed_weights", [0.35, 0.25, 0.20, 0.20]))
        return "STRESSED", _ensure_4_weights(w)
    elif occupancy < balanced:
        w = list(config.get("balanced_weights", [0.25, 0.30, 0.25, 0.20]))
        return "BALANCED", _ensure_4_weights(w)
    elif occupancy < strong:
        w = list(config.get("strong_weights", [0.10, 0.35, 0.30, 0.25]))
        return "STRONG", _ensure_4_weights(w)
    else:
        w = list(config.get("full_weights", [0.05, 0.35, 0.30, 0.30]))
        return "FULL", _ensure_4_weights(w)


def _ensure_4_weights(weights: list[float]) -> list[float]:
    """Ensure weight list has 4 elements for backward compatibility.

    Old configs have 3 weights [occ, pricing, momentum]. This adds a
    revenue_capture weight by redistributing from existing weights.

    Args:
        weights: List of 3 or 4 floats.

    Returns:
        List of 4 floats summing to ~1.0.
    """
    if len(weights) >= 4:
        return weights[:4]
    # Backward compat: add 4th weight by taking 0.20 from first two
    occ, pricing, momentum = weights[0], weights[1], weights[2]
    gap = 0.20
    scale = (1.0 - gap) / (occ + pricing + momentum) if (occ + pricing + momentum) > 0 else 1.0
    return [occ * scale, pricing * scale, momentum * scale, gap]


def _compute_revenue_gap_score(
    optimal: dict,
    revenue_gap: dict | None = None,
) -> int:
    """Compute revenue capture score (0-100) from revenue gap data.

    Measures how much of the optimal revenue is actually being captured.
    A gap of 0% → 100, 10% → 50, 20%+ → 0. Uses the total revenue gap
    relative to optimal monthly revenue.

    Args:
        optimal: Output from compute_optimal_price with revenue fields.
        revenue_gap: Output from decompose_revenue_gap (optional).

    Returns:
        Integer score 0-100.
    """
    optimal_rev = optimal.get("optimal_revenue_monthly", 0)
    if optimal_rev <= 0:
        return 50  # baseline when no data

    # Primary signal: revenue gap from optimizer
    gap_monthly = abs(optimal.get("revenue_gap_monthly", 0))

    # Secondary signal: if we have decomposed gap data, use total_gap
    # which includes vacancy, repricing, renewal, and concession components
    if revenue_gap:
        total_gap = abs(revenue_gap.get("total_gap_monthly", gap_monthly))
        gap_monthly = max(gap_monthly, total_gap)

    gap_ratio = gap_monthly / optimal_rev
    # 0% gap → 100, 10% → 70, 20% → 40, 33% → 0
    score = 100 - gap_ratio * 300
    return max(0, min(100, int(_round_half_up(score))))


def _compute_momentum_score(
    snapshot_trends: list[dict],
    current_asking: float,
    optimal_asking: float,
) -> int:
    """Compute rent roll momentum score (0-100) from snapshot trends.

    Uses first-to-last comparison of occupancy and asking rent over the
    trend window. Baseline is 50, adjusted up/down based on trend direction.

    Args:
        snapshot_trends: Monthly snapshots with occupancy and asking rent.
        current_asking: Current asking rent.
        optimal_asking: Optimal asking rent from optimizer.

    Returns:
        Integer score 0-100.
    """
    if len(snapshot_trends) < 2:
        return 50  # baseline when no trend data

    first = snapshot_trends[0]
    last = snapshot_trends[-1]

    first_occ = _get_occupancy(first)
    last_occ = _get_occupancy(last)
    first_rent = _get_asking_rent(first)
    last_rent = _get_asking_rent(last)

    score = 50.0  # baseline

    # Occupancy trend: +20 per +1% improvement, -20 per -1% decline
    occ_change = last_occ - first_occ
    occ_bonus = occ_change * 2000  # 0.01 change = +/- 20 points
    score += occ_bonus

    # Rent trend: only reward increases when NOT overpriced
    is_overpriced = current_asking > optimal_asking * 1.02  # 2% tolerance
    if first_rent > 0:
        rent_pct_change = (last_rent - first_rent) / first_rent
        if is_overpriced:
            # When overpriced, rent increases are bad (pushing further from optimal)
            rent_bonus = -rent_pct_change * 500  # penalize increases
        else:
            # When underpriced or aligned, rent increases are good
            rent_bonus = rent_pct_change * 500  # 1% = +5 points
        score += rent_bonus

    return max(0, min(100, int(_round_half_up(score))))


def _score_to_grade(score: int) -> str:
    """Map a numeric efficiency score (0-100) to a grade label.

    Args:
        score: Integer score 0-100.

    Returns:
        Grade string: OPTIMIZED|OPPORTUNITY|IMBALANCED|DISTRESSED|CRISIS.
    """
    if score >= 75:
        return "OPTIMIZED"
    elif score >= 60:
        return "OPPORTUNITY"
    elif score >= 45:
        return "IMBALANCED"
    elif score >= 30:
        return "DISTRESSED"
    else:
        return "CRISIS"


def _empty_result(current_revenue: float) -> dict:
    """Return a safe default result when inputs are invalid."""
    return {
        "optimal_asking": 0.0,
        "optimal_revenue_monthly": 0.0,
        "current_revenue_monthly": _round_half_up(current_revenue, 2),
        "revenue_gap_monthly": 0.0,
        "price_direction": "HOLD",
        "recommended_asking": 0.0,
        "confidence": "LOW",
        "seasonal_adjustment_applied": 0.0,
        "comp_constrained": False,
    }
