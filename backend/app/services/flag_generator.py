"""Flag generator — Layer 1.5 of the pricing engine.

Takes metrics JSON + client_config JSON → structured flags list.
Each flag: {type, value, threshold, severity}.

All thresholds come from config — ZERO hardcoded values.
Flags are facts, not judgments. Judgment is Layer 3's job.
"""
from app.engine.utils import round_half_up, safe_divide


def generate_flags(metrics: dict, config: dict) -> list[dict]:
    """Generate flags by comparing metrics against config thresholds.

    Args:
        metrics: complete metrics dict from the aggregator.
        config: client config dict with all threshold sections.

    Returns:
        List of flag dicts, each with type, value, threshold, severity.
    """
    flags = []

    occ = metrics["occupancy_metrics"]["occupancy_rate"]
    exp = metrics["exposure_metrics"]["total_exposure_pct"]
    exp_30d = metrics["exposure_metrics"]["exposure_30d_pct"]
    exp_90d = metrics["exposure_metrics"]["exposure_90d_pct"]

    pricing = metrics["pricing_spreads"]
    asking = pricing["asking_rent"]
    predicted = pricing["predicted_rent"]
    comps = pricing["comps_rent"]
    in_place = pricing["in_place_rent"]
    executed = pricing["executed_rent"]
    amenity = pricing["amenity_price"]
    dom = metrics["velocity_metrics"]["avg_days_on_market"]
    vacant = metrics["occupancy_metrics"]["vacant"]

    demand = metrics["demand_metrics"]["demand_score"]
    daily_burn = metrics["revenue_metrics"]["daily_vacancy_burn"]

    # Config sections
    occ_t = config.get("occupancy_thresholds", {})
    exp_t = config.get("exposure_thresholds", {})
    price_t = config.get("pricing_tolerance", {})
    conc_t = config.get("concession_policy", {})
    renew_t = config.get("renewal_policy", {})
    exp_pol = config.get("experiment_policy", {})
    amenity_t = config.get("amenity_benchmarks", {})

    # --- Occupancy flags (mutually exclusive bands) ---
    if occ >= occ_t.get("push_pricing_above", 0.96):
        flags.append({
            "type": "OCCUPANCY_PUSH_ELIGIBLE",
            "value": occ,
            "threshold": occ_t.get("push_pricing_above"),
            "severity": "POSITIVE",
        })
    elif occ < occ_t.get("crisis_below", 0.82):
        flags.append({
            "type": "OCCUPANCY_CRISIS",
            "value": occ,
            "threshold": occ_t.get("crisis_below"),
            "severity": "CRITICAL",
        })
    elif occ < occ_t.get("action_below", 0.88):
        flags.append({
            "type": "OCCUPANCY_BELOW_ACTION",
            "value": occ,
            "threshold": occ_t.get("action_below"),
            "severity": "HIGH",
        })
    elif occ < occ_t.get("concern_below", 0.92):
        flags.append({
            "type": "OCCUPANCY_BELOW_CONCERN",
            "value": occ,
            "threshold": occ_t.get("concern_below"),
            "severity": "MEDIUM",
        })

    # --- Exposure flags (mutually exclusive bands) ---
    if exp >= exp_t.get("crisis_above", 0.20):
        flags.append({
            "type": "EXPOSURE_CRISIS",
            "value": exp,
            "threshold": exp_t.get("crisis_above"),
            "severity": "CRITICAL",
        })
    elif exp >= exp_t.get("action_below", 0.15):
        flags.append({
            "type": "EXPOSURE_ACTION_NEEDED",
            "value": exp,
            "threshold": exp_t.get("action_below"),
            "severity": "HIGH",
        })
    elif exp >= exp_t.get("caution_below", 0.10):
        flags.append({
            "type": "EXPOSURE_CAUTION",
            "value": exp,
            "threshold": exp_t.get("caution_below"),
            "severity": "MEDIUM",
        })

    # --- Exposure trend ---
    if exp_90d > exp_30d:
        flags.append({
            "type": "EXPOSURE_DETERIORATING",
            "value": {"30d": exp_30d, "90d": exp_90d},
            "threshold": "90d > 30d",
            "severity": "HIGH",
        })

    # --- Pricing flags ---
    if comps > 0:
        premium_pct = safe_divide(asking - comps, comps)
        if premium_pct > price_t.get("max_premium_vs_comps_pct", 0.05):
            flags.append({
                "type": "ABOVE_COMP_PREMIUM_THRESHOLD",
                "value": round_half_up(premium_pct * 100, 1),
                "threshold": price_t.get("max_premium_vs_comps_pct"),
                "severity": "HIGH",
            })

    if predicted > 0:
        asking_vs_pred_pct = safe_divide(asking - predicted, predicted)
        if asking_vs_pred_pct > price_t.get("max_asking_vs_predicted_pct", 0.04):
            flags.append({
                "type": "ASKING_ABOVE_PREDICTED_THRESHOLD",
                "value": round_half_up(asking_vs_pred_pct * 100, 1),
                "threshold": price_t.get("max_asking_vs_predicted_pct"),
                "severity": "MEDIUM",
            })

    # --- Velocity flags ---
    if dom > price_t.get("acceptable_days_on_market", 21):
        flags.append({
            "type": "DOM_ABOVE_THRESHOLD",
            "value": dom,
            "threshold": price_t.get("acceptable_days_on_market"),
            "severity": "MEDIUM",
        })

    # --- Concession trigger ---
    conc_triggers = conc_t.get("concession_triggers", {})
    min_exp = conc_triggers.get("min_exposure_pct", 0.12)
    min_dom = conc_triggers.get("min_days_on_market", 21)
    if exp >= min_exp and dom >= min_dom:
        flags.append({
            "type": "CONCESSION_TRIGGER",
            "value": {"exposure": exp, "dom": dom},
            "threshold": {"min_exposure": min_exp, "min_dom": min_dom},
            "severity": "HIGH",
        })

    # --- Loss to lease ---
    if in_place > 0:
        ltl_ratio = safe_divide(asking - in_place, in_place)
        if ltl_ratio < 0:
            flags.append({
                "type": "NEGATIVE_LTL",
                "value": round_half_up(ltl_ratio * 100, 1),
                "threshold": 0,
                "severity": "HIGH",
            })

    # --- Executed vs asking ---
    if executed > 0 and asking > 0:
        exec_diff = executed - asking
        if exec_diff > 50:
            flags.append({
                "type": "EXECUTED_SIGNIFICANTLY_ABOVE_ASKING",
                "value": exec_diff,
                "threshold": 50,
                "severity": "HIGH",
            })
        elif exec_diff < -30:
            flags.append({
                "type": "EXECUTED_BELOW_ASKING",
                "value": exec_diff,
                "threshold": -30,
                "severity": "LOW",
            })

    # --- Amenity audit ---
    if predicted > 0:
        amenity_ratio = safe_divide(amenity, predicted)
        if amenity_ratio > amenity_t.get("amenity_audit_threshold_pct", 0.08):
            flags.append({
                "type": "AMENITY_AUDIT_RECOMMENDED",
                "value": round_half_up(amenity_ratio * 100, 1),
                "threshold": amenity_t.get("amenity_audit_threshold_pct"),
                "severity": "MEDIUM",
            })

    # --- Demand-occupancy divergence ---
    divergence = demand - occ
    if divergence > 0.05 and occ < occ_t.get("concern_below", 0.92):
        flags.append({
            "type": "DEMAND_OCCUPANCY_DIVERGENCE",
            "value": round_half_up(divergence, 2),
            "threshold": 0.05,
            "severity": "HIGH",
        })

    # --- Revenue at risk ---
    monthly_burn = daily_burn * 30
    if monthly_burn > 5000:
        flags.append({
            "type": "HIGH_REVENUE_AT_RISK",
            "value": monthly_burn,
            "threshold": 5000,
            "severity": "HIGH",
        })

    # --- Renewal freeze ---
    never_increase_above = renew_t.get("never_increase_above_occupancy_threshold", 0.88)
    if occ < never_increase_above:
        flags.append({
            "type": "RENEWAL_FREEZE_RECOMMENDED",
            "value": occ,
            "threshold": never_increase_above,
            "severity": "MEDIUM",
        })

    # --- MAB eligibility ---
    min_vacant = exp_pol.get("min_vacant_for_experiment", 3)
    min_occ = exp_pol.get("min_occupancy_for_experiment", 0.75)
    if vacant >= min_vacant and occ >= min_occ:
        flags.append({
            "type": "MAB_ELIGIBLE",
            "value": {"vacant": vacant, "occupancy": occ},
            "threshold": {"min_vacant": min_vacant, "min_occupancy": min_occ},
            "severity": "INFO",
        })

    return flags
