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
            "severity": "HIGH",
        })
    elif occ < occ_t.get("crisis_below", 0.85):
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
            "severity": "CRITICAL",
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

    # --- Concession trigger (with conditional reclassification) ---
    conc_triggers = conc_t.get("concession_triggers", {})
    min_exp = conc_triggers.get("min_exposure_pct", 0.12)
    min_dom = conc_triggers.get("min_days_on_market", 21)
    removal_occ = conc_t.get("removal_occupancy_threshold", 0.93)
    if exp >= min_exp and dom >= min_dom:
        if occ >= removal_occ:
            # High occupancy: concessions should be removed, not added
            flags.append({
                "type": "CONCESSION_REMOVAL_ELIGIBLE",
                "value": {"exposure": exp, "dom": dom, "occupancy": occ},
                "threshold": {"min_exposure": min_exp, "min_dom": min_dom,
                              "removal_occupancy": removal_occ},
                "severity": "MEDIUM",
            })
        else:
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

    # --- Renewal freeze (config-driven threshold) ---
    freeze_below = renew_t.get("freeze_below_occupancy", 0.82)
    if occ < freeze_below:
        flags.append({
            "type": "RENEWAL_FREEZE_RECOMMENDED",
            "value": occ,
            "threshold": freeze_below,
            "severity": "MEDIUM",
        })

    # === New revenue optimization flags ===

    _append_revenue_optimization_flags(flags, metrics, config)

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


def _append_revenue_optimization_flags(
    flags: list[dict],
    metrics: dict,
    config: dict,
) -> None:
    """Append revenue optimization flags based on enriched metrics sections.

    Uses .get() with defaults for all new metrics sections so the generator
    remains backward-compatible with metrics dicts that lack these sections.

    Args:
        flags: Mutable list to append flags to.
        metrics: Complete metrics dict (may include elasticity, optimal_pricing,
                 renewal_opportunity, revenue_gap, revenue_efficiency sections).
        config: Client config dict.
    """
    occ = metrics["occupancy_metrics"]["occupancy_rate"]
    exp = metrics["exposure_metrics"]["total_exposure_pct"]
    pricing = metrics["pricing_spreads"]
    asking = pricing["asking_rent"]
    comps = pricing["comps_rent"]
    in_place = pricing["in_place_rent"]

    price_t = config.get("pricing_tolerance", {})
    conc_t = config.get("concession_policy", {})

    # New metrics sections (all optional, backward-compatible)
    optimal = metrics.get("optimal_pricing", {})
    renewal = metrics.get("renewal_opportunity", {})
    elasticity = metrics.get("elasticity", {})
    revenue_gap = metrics.get("revenue_gap", {})

    # LTL from ltl_analysis
    ltl = metrics.get("ltl_analysis", {})
    ltl_pct = ltl.get("ltl_pct", 0.0)

    # --- 1. RENT_PUSH_OPPORTUNITY (HIGH) ---
    # Trigger: occ >= 0.94 AND optimal_pricing exists AND asking < optimal by > gap threshold
    rent_push_gap = price_t.get("rent_push_gap_pct", 0.03)
    optimal_asking = optimal.get("optimal_asking", 0)
    if occ >= 0.94 and optimal_asking > 0 and asking > 0:
        gap_pct = safe_divide(optimal_asking - asking, asking)
        if gap_pct > rent_push_gap:
            flags.append({
                "type": "RENT_PUSH_OPPORTUNITY",
                "value": round_half_up(gap_pct * 100, 1),
                "threshold": rent_push_gap,
                "severity": "HIGH",
            })

    # --- 2. HIGH_LTL_CAPTURE (HIGH) ---
    # Trigger: LTL > 5% of in_place AND occ >= 0.88
    # Note: ltl_pct is stored as percentage points (e.g. 7.6 means 7.6%)
    if in_place > 0 and ltl_pct > 5.0 and occ >= 0.88:
        flags.append({
            "type": "HIGH_LTL_CAPTURE",
            "value": ltl_pct,
            "threshold": 5.0,
            "severity": "HIGH",
        })

    # --- 3. RENEWAL_INCREASE_ELIGIBLE (MEDIUM) ---
    # Trigger: upcoming_renewals_90d > 0 AND occ >= 0.90 AND LTL > 0
    upcoming_renewals = renewal.get("upcoming_renewals_90d", 0)
    if upcoming_renewals > 0 and occ >= 0.90 and ltl_pct > 0:
        flags.append({
            "type": "RENEWAL_INCREASE_ELIGIBLE",
            "value": {
                "upcoming_renewals": upcoming_renewals,
                "ltl_pct": round_half_up(ltl_pct * 100, 1),
            },
            "threshold": {"min_occupancy": 0.90, "min_ltl_pct": 0},
            "severity": "MEDIUM",
        })

    # --- 4. UNDERPRICED_VS_COMPS (MEDIUM) ---
    # Trigger: asking < comps by > threshold AND occ >= 0.90
    underpriced_threshold = price_t.get("underpriced_vs_comps_pct", 0.03)
    if comps > 0 and asking > 0 and occ >= 0.90:
        underpriced_pct = safe_divide(comps - asking, comps)
        if underpriced_pct > underpriced_threshold:
            flags.append({
                "type": "UNDERPRICED_VS_COMPS",
                "value": round_half_up(underpriced_pct * 100, 1),
                "threshold": underpriced_threshold,
                "severity": "MEDIUM",
            })

    # --- 5. CONCESSION_REMOVAL_ELIGIBLE (MEDIUM) ---
    # Trigger: concession units exist AND occ >= 0.93 AND exposure < 0.10
    # This fires independently of the CONCESSION_TRIGGER conditional above.
    # The conditional in the main body handles the case where concession
    # trigger conditions are met but occupancy is high enough to remove instead.
    # This rule catches the case where concessions exist at high occ even when
    # the concession trigger conditions (high exposure + high DOM) are NOT met.
    gap_components = revenue_gap.get("gap_components", {})
    concession_drag = gap_components.get("concession_drag", {}).get("amount", 0)
    removal_occ = conc_t.get("removal_occupancy_threshold", 0.93)
    if concession_drag > 0 and occ >= removal_occ and exp < 0.10:
        # Only append if not already added by the CONCESSION_TRIGGER conditional
        existing_types = {f["type"] for f in flags}
        if "CONCESSION_REMOVAL_ELIGIBLE" not in existing_types:
            flags.append({
                "type": "CONCESSION_REMOVAL_ELIGIBLE",
                "value": {
                    "concession_drag_monthly": concession_drag,
                    "occupancy": occ,
                    "exposure": exp,
                },
                "threshold": {
                    "min_occupancy": removal_occ,
                    "max_exposure": 0.10,
                },
                "severity": "MEDIUM",
            })

    # --- 6. ELASTICITY_WARNING (INFO) ---
    # Trigger: direction == "ELASTIC" AND confidence >= "MEDIUM"
    direction = elasticity.get("direction", "UNKNOWN")
    confidence = elasticity.get("confidence", "LOW")
    if direction == "ELASTIC" and confidence in ("MEDIUM", "HIGH"):
        flags.append({
            "type": "ELASTICITY_WARNING",
            "value": {
                "coefficient": elasticity.get("elasticity_coefficient", 0.0),
                "direction": direction,
            },
            "threshold": {"direction": "ELASTIC", "min_confidence": "MEDIUM"},
            "severity": "INFO",
        })
