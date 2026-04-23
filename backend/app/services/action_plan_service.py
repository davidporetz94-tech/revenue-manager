"""Action plan service — pre-computes revenue math and experiment designs.

All dollar amounts are computed HERE in Python, never by Claude.
This service provides the facts that Claude weaves into a narrative.
"""
from app.engine.utils import round_half_up, safe_divide

# Upward experiment constraints (more conservative than downward)
_UP_MAX_SPREAD_PCT = 0.05
_UP_MAX_SPREAD_DOLLARS = 75
_UP_MIN_OCC_GATE = 0.92
_UP_EARLY_TERMINATION_DAYS = 21
_CRISIS_OCC_THRESHOLD = 0.82
_DIRECTION_GAP_THRESHOLD = 0.03
# Practical significance: 15%+ revenue-per-day difference
_CONVERGENCE_SIGNIFICANCE_PCT = 0.15


def build_action_plan_context(
    metrics: dict,
    all_flags: dict,
    config: dict,
) -> dict:
    """Build pre-computed context for the action plan Claude call.

    Computes all revenue math, experiment eligibility, and designs.

    Args:
        metrics: full metrics dict from compute_property_metrics.
        all_flags: dict of unit_type_code -> list of flags.
        config: client config dict.

    Returns:
        Dict with revenue_facts, experiment_eligibility, experiment_designs.
    """
    exp_policy = config.get("experiment_policy", {})
    min_vacant = exp_policy.get("min_vacant_for_experiment", 3)
    min_occ = exp_policy.get("min_occupancy_for_experiment", 0.75)
    max_spread_pct = exp_policy.get("max_price_spread_pct", 0.06)
    max_spread_dollars = exp_policy.get("max_price_spread_dollars", 100)
    obs_window = exp_policy.get("observation_window_days", 14)

    revenue_facts = _compute_revenue_facts(metrics)
    experiment_eligibility = {}
    experiment_designs = {}

    for code, m in metrics["unit_type_metrics"].items():
        flags = all_flags.get(code, [])
        flag_types = {f["type"] for f in flags}
        flag_severities = {f["severity"] for f in flags}

        occ = m["occupancy_metrics"]["occupancy_rate"]
        vacant = m["occupancy_metrics"]["vacant"]
        asking = m["pricing_spreads"]["asking_rent"]
        predicted = m["pricing_spreads"]["predicted_rent"]
        comps = m["pricing_spreads"]["comps_rent"]
        optimal_pricing = m.get("optimal_pricing")

        # Experiment eligibility check
        eligible = vacant >= min_vacant and occ >= min_occ
        has_critical = "CRITICAL" in flag_severities
        critical_count = sum(1 for f in flags if f["severity"] == "CRITICAL")

        # Suppress MAB for CRISIS/DISTRESSED grades — direct action only
        grade = m.get("revenue_efficiency", {}).get("grade", "")
        grade_suppressed = grade in ("CRISIS", "DISTRESSED")
        if grade_suppressed:
            eligible = False

        experiment_eligibility[code] = {
            "eligible": eligible,
            "vacant_units": vacant,
            "occupancy": occ,
            "min_vacant_met": vacant >= min_vacant,
            "min_occ_met": occ >= min_occ,
            "has_critical_flags": has_critical,
            "critical_count": critical_count,
            "grade_suppressed": grade_suppressed,
            "recommendation": _experiment_recommendation(
                eligible, has_critical, critical_count, vacant
            ),
        }

        # Design experiment if eligible
        if eligible:
            design = _design_experiment(
                code, vacant, asking, predicted, comps,
                max_spread_pct, max_spread_dollars, obs_window,
                has_critical, flag_types,
                optimal_pricing=optimal_pricing, occ=occ,
            )
            experiment_designs[code] = design

    return {
        "revenue_facts": revenue_facts,
        "experiment_eligibility": experiment_eligibility,
        "experiment_designs": experiment_designs,
    }


def _compute_revenue_facts(metrics: dict) -> dict:
    """Compute all revenue facts from metrics -- deterministic Python math."""
    total_daily_burn = 0
    total_monthly_cost = 0
    unit_type_facts = {}

    for code, m in metrics["unit_type_metrics"].items():
        rev = m["revenue_metrics"]
        daily_burn = rev["daily_vacancy_burn"]
        monthly_cost = rev["monthly_vacancy_cost"]
        total_daily_burn += daily_burn
        total_monthly_cost += monthly_cost

        unit_type_facts[code] = {
            "daily_vacancy_burn": daily_burn,
            "monthly_vacancy_cost": monthly_cost,
            "revenue_at_risk_30d": rev["revenue_at_risk_30d"],
        }

    return {
        "unit_type_revenue": unit_type_facts,
        "total_daily_burn": total_daily_burn,
        "total_monthly_vacancy_cost": total_monthly_cost,
        "total_annual_cost": total_monthly_cost * 12,
    }


def _experiment_recommendation(
    eligible: bool, has_critical: bool, critical_count: int, vacant: int,
) -> str:
    """Determine experiment recommendation based on flags and eligibility."""
    if not eligible:
        if vacant < 3:
            return "NOT_ELIGIBLE_INSUFFICIENT_VACANT"
        return "NOT_ELIGIBLE_LOW_OCCUPANCY"

    if critical_count >= 2:
        return "ELIGIBLE_BUT_DIRECT_ACTION_PREFERRED"
    if has_critical:
        return "ELIGIBLE_BUT_CAUTION_CRITICAL_FLAGS"

    return "RECOMMENDED"


def _detect_experiment_direction(
    asking: float,
    occ: float,
    optimal_pricing: dict | None,
) -> str:
    """Determine experiment direction based on asking vs optimal price.

    Args:
        asking: current asking rent.
        occ: occupancy rate (0-1).
        optimal_pricing: dict with optimal_asking, price_direction, or None.

    Returns:
        One of: "UP", "DOWN", "NOT_ELIGIBLE_AT_OPTIMAL", "CRISIS_DIRECT_ACTION".
    """
    # No optimal pricing data: fall back to existing DOWN behavior
    if optimal_pricing is None:
        return "DOWN"

    optimal_asking = optimal_pricing.get("optimal_asking", 0.0)
    if optimal_asking <= 0:
        return "DOWN"

    # Crisis occupancy: skip experiment entirely, direct action
    if occ < _CRISIS_OCC_THRESHOLD:
        return "CRISIS_DIRECT_ACTION"

    gap_pct = abs(asking - optimal_asking) / optimal_asking

    # Near optimal: no experiment needed
    if gap_pct <= _DIRECTION_GAP_THRESHOLD:
        return "NOT_ELIGIBLE_AT_OPTIMAL"

    # Asking above optimal: test downward
    if asking > optimal_asking:
        return "DOWN"

    # Asking below optimal: test upward only if occupancy gate met
    if asking < optimal_asking and occ >= _UP_MIN_OCC_GATE:
        return "UP"

    # Below optimal but occupancy too low for upward: fall back to DOWN
    return "DOWN"


def _compute_revenue_per_day(monthly_rent: float, vacancy_days: float) -> float:
    """Compute revenue per unit per day for convergence metric.

    Args:
        monthly_rent: monthly rent amount.
        vacancy_days: average days vacant before lease.

    Returns:
        Revenue per unit per day.
    """
    return round_half_up(safe_divide(monthly_rent, vacancy_days + 1), 2)


def _design_experiment(
    code: str, vacant: int, asking: float, predicted: float,
    comps: float, max_spread_pct: float, max_spread_dollars: float,
    obs_window: int, has_critical: bool, flag_types: set,
    optimal_pricing: dict | None = None, occ: float = 0.0,
) -> dict:
    """Design an MAB experiment for a unit type.

    Supports both downward (overpriced) and upward (underpriced) experiments.
    Unit allocation: 2->1/1, 3->1/2, 4->2/2, 5->2/3, 6+->even or 3-way.

    Args:
        code: unit type code.
        vacant: number of vacant units.
        asking: current asking rent.
        predicted: predicted rent from hedonic model.
        comps: comp asking rent.
        max_spread_pct: max spread as fraction (e.g. 0.06).
        max_spread_dollars: max spread in dollars.
        obs_window: observation window in days.
        has_critical: whether unit type has critical flags.
        flag_types: set of flag type strings.
        optimal_pricing: optional dict with optimal_asking, price_direction.
        occ: current occupancy rate.

    Returns:
        Experiment design dict with arms, convergence, direction, etc.
    """
    direction = _detect_experiment_direction(asking, occ, optimal_pricing)

    # Crisis: fall back to DOWN design (experiment exists but recommendation is direct action)
    if direction == "CRISIS_DIRECT_ACTION":
        direction = "DOWN"

    # NOT_ELIGIBLE_AT_OPTIMAL: still design a DOWN experiment as fallback
    if direction == "NOT_ELIGIBLE_AT_OPTIMAL":
        direction = "DOWN"

    if direction == "UP":
        return _design_upward_experiment(
            code, vacant, asking, optimal_pricing, obs_window,
            has_critical, flag_types,
        )

    # DOWN: existing behavior
    return _design_downward_experiment(
        code, vacant, asking, predicted, comps,
        max_spread_pct, max_spread_dollars, obs_window,
        has_critical, flag_types,
    )


def _design_upward_experiment(
    code: str, vacant: int, asking: float,
    optimal_pricing: dict, obs_window: int,
    has_critical: bool, flag_types: set,
) -> dict:
    """Design an upward (price increase) experiment.

    Conservative: test arm is halfway between current asking and optimal.
    Max spread: 5% or $75, whichever is tighter.

    Args:
        code: unit type code.
        vacant: number of vacant units.
        asking: current asking rent.
        optimal_pricing: dict with optimal_asking.
        obs_window: observation window in days.
        has_critical: whether unit type has critical flags.
        flag_types: set of flag type strings.

    Returns:
        Experiment design dict for upward experiment.
    """
    optimal_asking = optimal_pricing.get("optimal_asking", asking)
    control_price = asking

    # Test arm: halfway between current and optimal (conservative)
    test_price = round((asking + optimal_asking) / 2)

    # Enforce upward max spread: 5% or $75, whichever is tighter
    spread = abs(test_price - control_price)
    pct_spread = safe_divide(spread, control_price)

    if pct_spread > _UP_MAX_SPREAD_PCT or spread > _UP_MAX_SPREAD_DOLLARS:
        max_by_pct = round(control_price * _UP_MAX_SPREAD_PCT)
        max_dollars = _UP_MAX_SPREAD_DOLLARS
        capped_spread = min(max_by_pct, max_dollars)
        test_price = round(control_price + capped_spread)

    # Re-check spread is meaningful (at least $20 upward)
    if abs(test_price - control_price) < 20:
        test_price = round(control_price + 50)

    # Unit allocation (same logic as downward)
    arms = _allocate_arms(vacant, control_price, test_price, flag_types)

    # Convergence rule: revenue per unit per day
    convergence = (
        f"Compare revenue per unit per day: monthly_rent / (vacancy_days + 1). "
        f"Practical significance: 15%+ difference in revenue-per-day. "
        f"If no application on test arm after {_UP_EARLY_TERMINATION_DAYS} days, revert to control price. "
        f"If no difference after {obs_window} days, hold control price."
    )

    # Revenue-per-day estimates (assuming average 20-day vacancy for control)
    avg_vacancy_days = 20.0
    rpd_control = _compute_revenue_per_day(control_price, avg_vacancy_days)
    rpd_test = _compute_revenue_per_day(test_price, avg_vacancy_days)

    final_spread = abs(test_price - control_price)
    return {
        "arms": arms,
        "observation_window_days": obs_window,
        "convergence_rule": convergence,
        "control_price": control_price,
        "test_price": test_price,
        "spread_dollars": final_spread,
        "spread_pct": round_half_up(
            safe_divide(final_spread, control_price) * 100, 1,
        ),
        "direction": "UP",
        "convergence_metric": "revenue_per_unit_per_day",
        "revenue_per_day_control_estimate": rpd_control,
        "revenue_per_day_test_estimate": rpd_test,
        "early_termination_days": _UP_EARLY_TERMINATION_DAYS,
    }


def _design_downward_experiment(
    code: str, vacant: int, asking: float, predicted: float,
    comps: float, max_spread_pct: float, max_spread_dollars: float,
    obs_window: int, has_critical: bool, flag_types: set,
) -> dict:
    """Design a downward (price reduction) experiment.

    Preserves existing behavior for overpriced units.

    Args:
        code: unit type code.
        vacant: number of vacant units.
        asking: current asking rent.
        predicted: predicted rent from hedonic model.
        comps: comp asking rent.
        max_spread_pct: max spread as fraction (e.g. 0.06).
        max_spread_dollars: max spread in dollars.
        obs_window: observation window in days.
        has_critical: whether unit type has critical flags.
        flag_types: set of flag type strings.

    Returns:
        Experiment design dict for downward experiment.
    """
    # Determine test price (existing logic)
    control_price = asking
    test_price = round(predicted)  # default: test at predicted

    # Use comps if asking is significantly above comps
    if asking > comps and comps > 0:
        if (asking - comps) / comps > 0.03:
            test_price = round(comps)

    # Enforce max spread
    spread = abs(control_price - test_price)
    pct_spread = safe_divide(spread, control_price)

    if pct_spread > max_spread_pct:
        max_by_pct = round(control_price * max_spread_pct)
        test_price = round(control_price - min(max_by_pct, max_spread_dollars))
    if spread > max_spread_dollars:
        test_price = round(control_price - max_spread_dollars)

    # Re-check spread is meaningful (at least $20)
    if abs(control_price - test_price) < 20:
        test_price = round(control_price - 50)

    # Ensure test_price > 0
    test_price = max(test_price, round(control_price * 0.90))

    # Unit allocation
    arms = _allocate_arms(vacant, control_price, test_price, flag_types)

    # Convergence rule: revenue per unit per day
    convergence = (
        f"Compare revenue per unit per day: monthly_rent / (vacancy_days + 1). "
        f"Practical significance: 15%+ difference in revenue-per-day. "
        f"If no difference after {obs_window} days, hold control price. "
        f"If neither arm leases, escalate to non-price investigation. "
        f"Early termination: accept any application on any unit."
    )

    # Revenue-per-day estimates (assuming average 20-day vacancy for control)
    avg_vacancy_days = 20.0
    rpd_control = _compute_revenue_per_day(control_price, avg_vacancy_days)
    rpd_test = _compute_revenue_per_day(test_price, avg_vacancy_days)

    return {
        "arms": arms,
        "observation_window_days": obs_window,
        "convergence_rule": convergence,
        "control_price": control_price,
        "test_price": test_price,
        "spread_dollars": abs(control_price - test_price),
        "spread_pct": round_half_up(
            safe_divide(abs(control_price - test_price), control_price) * 100, 1,
        ),
        "direction": "DOWN",
        "convergence_metric": "revenue_per_unit_per_day",
        "revenue_per_day_control_estimate": rpd_control,
        "revenue_per_day_test_estimate": rpd_test,
        "early_termination_days": 0,
    }


def _allocate_arms(
    vacant: int, control_price: float, test_price: float, flag_types: set,
) -> list[dict]:
    """Allocate vacant units to experiment arms.

    Rules: 2->1/1, 3->1/2, 4->2/2, 5->2/3, 6+->even or 3-way.
    Three-arm when 6+ vacant and concession testing is indicated.
    """
    # Determine if three-arm (concession test)
    use_three_arm = vacant >= 6 and "CONCESSION_TRIGGER" in flag_types

    if use_three_arm:
        # Three-arm: control, price test, concession test
        per_arm = vacant // 3
        remainder = vacant % 3
        control_units = per_arm
        test_units = per_arm
        concession_units = per_arm + remainder

        # Concession: same asking + weeks free
        concession_price = control_price
        concession_note = (
            f"${control_price:.0f} + 2 weeks free "
            f"(net effective ~${control_price * 10 / 12:.0f})"
        )

        return [
            {"label": "control", "price": control_price,
             "units_allocated": control_units},
            {"label": "price_test", "price": test_price,
             "units_allocated": test_units},
            {"label": "concession_test", "price": control_price,
             "units_allocated": concession_units,
             "concession": "2 weeks free",
             "net_effective": round(control_price * 10 / 12)},
        ]
    else:
        # Two-arm: control vs test
        if vacant == 2:
            control_units, test_units = 1, 1
        elif vacant == 3:
            control_units, test_units = 1, 2
        elif vacant == 4:
            control_units, test_units = 2, 2
        elif vacant == 5:
            control_units, test_units = 2, 3
        else:
            # 6+: even split
            control_units = vacant // 2
            test_units = vacant - control_units

        return [
            {"label": "control", "price": control_price,
             "units_allocated": control_units},
            {"label": "test", "price": test_price,
             "units_allocated": test_units},
        ]
