"""Diagnostic service — orchestrates the full pricing diagnostic pipeline.

Pipeline: metrics → flags → Claude diagnosis → Claude action plan → store results.

All revenue math is computed in Python BEFORE Claude calls.
Claude generates text/structured JSON only — never dollar amounts.
"""
import json
import logging
import time
import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.property import Property, UnitType
from app.models.config import ClientConfig
from app.models.diagnostic import DiagnosticRun, AuditLog
from app.services.metrics_engine import compute_property_metrics
from app.services.flag_generator import generate_flags
from app.services.claude_client import ClaudeClient, ClaudeAPIError
from app.services.action_plan_service import build_action_plan_context

logger = logging.getLogger(__name__)

DIAGNOSIS_SYSTEM_PROMPT = """You are a senior multifamily revenue management analyst with 15+ years of institutional portfolio experience. You receive structured metrics, pre-computed revenue efficiency scores, and gap decompositions from a pricing engine, along with the client's business plan context and threshold configuration.

INPUT DATA YOU RECEIVE:
- `revenue_efficiency` per unit type: pre-computed score (0-100) and grade. DO NOT recompute these.
- `revenue_gap` per unit type: gap decomposition by lever (FILL, REPRICE, RENEW, DE_CONCESSION) with dollar amounts.
- `renewal_opportunity` per unit type: upcoming renewal count, recommended increase %, dollar capture.
- `elasticity` per unit type: price sensitivity coefficient with confidence level.
- `optimal_pricing` per unit type: revenue-maximizing asking rent.
- Flags from the flag generator (severity, type).

Produce a JSON diagnosis with:
1. Revenue efficiency score per unit type — USE the pre-computed `revenue_efficiency.revenue_efficiency_score` directly
2. Grade from pre-computed `revenue_efficiency.grade`:
   - CRISIS (0-39): Dominant vacancy, occupancy freefall
   - DISTRESSED (40-54): Mixed vacancy + pricing pressure
   - IMBALANCED (55-69): One dimension dragging performance
   - OPPORTUNITY (70-84): Healthy occupancy, pricing upside exists
   - OPTIMIZED (85-100): Operating near the revenue frontier
3. Root cause analysis: identify the DOMINANT revenue lever per unit type from `revenue_gap.dominant_lever`
4. Specific, actionable recommendations quantified in dollars from pre-computed gap components
5. Experiment designs where appropriate (MEDIUM confidence situations)

CRITICAL RULES:
- USE the pre-computed revenue_efficiency score and grade. Do NOT recalculate them.
- For CRISIS/DISTRESSED grades: recommend DIRECT ACTION, NOT experiments.
- For IMBALANCED with MEDIUM confidence: prefer experiments over direct action.
- For OPPORTUNITY/OPTIMIZED: recommend renewal increases, concession removal, or upward price tests.
- When elasticity confidence is LOW, recommend experimentation to gather data. State this explicitly.
- Every dollar amount in your response must come from the pre-computed facts provided. Do NOT invent numbers.
- Quantify every recommendation using pre-computed gap_components (e.g., "$X/mo from FILL lever").
- Cross-unit-type analysis: flag if repricing one unit type risks cannibalizing another (e.g., if cutting 2BR to near 1BR asking).
- Never recommend experiments for unit types with < min_vacant_for_experiment vacant units.

Action taxonomy:
- Pricing: REDUCE_ASKING_RENT, INCREASE_ASKING_RENT, HOLD_ASKING_RENT
- Pricing tests: TEST_HIGHER_ASKING, TEST_TERM_PREMIUM
- Concessions: OFFER_MOVE_IN_CONCESSION, OFFER_LOOK_AND_LEASE, REMOVE_CONCESSION
- Experiments: LAUNCH_PRICE_EXPERIMENT, LAUNCH_CONCESSION_EXPERIMENT, CONVERGE_EXPERIMENT
- Renewals: IMPLEMENT_RENEWAL_INCREASE, SET_RENEWAL_INCREASE, FREEZE_RENEWAL_INCREASES
- Lease terms: ADJUST_PREFERRED_LEASE_TERM, OFFER_SHORT_TERM_PREMIUM
- Audits: AUDIT_AMENITY_PRICING, INVESTIGATE_NON_PRICE_FACTORS

Output ONLY valid JSON matching this schema:
{
  "unit_type_assessments": [{
    "unit_type": "string",
    "health_score": "int 0-100 (from revenue_efficiency_score)",
    "grade": "OPTIMIZED|OPPORTUNITY|IMBALANCED|DISTRESSED|CRISIS",
    "score_reasoning": "string",
    "dominant_lever": "FILL|REPRICE|RENEW|DE_CONCESSION",
    "revenue_gap_monthly": "float (from revenue_gap.total_gap_monthly)",
    "root_cause": "string or null",
    "key_findings": ["string"],
    "anomalies": ["string"],
    "recommended_actions": [{
      "action_type": "string from taxonomy",
      "lever": "FILL|REPRICE|RENEW|DE_CONCESSION",
      "priority": "int 1-5",
      "description": "string",
      "target_value": "float or null",
      "expected_impact_monthly": "float (from gap_components)",
      "confidence": "HIGH|MEDIUM|LOW",
      "downside_risk": "string",
      "reasoning": "string"
    }],
    "experiment_design": {
      "recommended": "boolean",
      "arms": [{"label": "string", "price": "float", "units_allocated": "int"}],
      "observation_window_days": "int",
      "convergence_rule": "string",
      "rationale": "string"
    }
  }],
  "portfolio_assessment": {
    "summary": "string",
    "cross_unit_type_risks": ["string"],
    "overall_portfolio_score": "int",
    "top_3_priorities": ["string"]
  },
  "further_investigation": [{"area": "string", "reason": "string", "data_needed": "string"}]
}"""

ACTION_PLAN_SYSTEM_PROMPT = """You are a senior multifamily revenue management strategist. Given a diagnosis with revenue efficiency grades, revenue gap decompositions, and recommendations, produce a detailed 30-day phased action plan.

PHASE STRUCTURE ADAPTS TO THE DOMINANT PROBLEM (from the diagnosis grades):

CRISIS/DISTRESSED (score < 55):
- Phase 1 (Days 1-3): Fill — reduce asking, offer concessions, stop the bleed
- Phase 2 (Days 4-14): Stabilize — monitor velocity, adjust if needed
- Phase 3 (Days 15-21): Evaluate fill progress, begin pricing optimization
- Phase 4 (Days 22-30): Optimize — renewals, remove concessions as occupancy recovers

IMBALANCED (score 55-69):
- Phase 1 (Days 1-3): Quick wins — reprice, launch experiments
- Phase 2 (Days 4-14): Experiment observation, renewal increases
- Phase 3 (Days 15-21): Converge experiments, evaluate renewal retention
- Phase 4 (Days 22-30): Lock strategies, begin upward price tests

OPPORTUNITY (score 70-84):
- Phase 1 (Days 1-3): Implement renewal increases, remove concessions
- Phase 2 (Days 4-14): Test higher asking on new leases
- Phase 3 (Days 15-21): Evaluate test results, seasonal positioning
- Phase 4 (Days 22-30): Lock optimal pricing, prepare for peak season

OPTIMIZED (score 85-100):
- Phase 1 (Days 1-3): Hold current pricing, document baseline
- Phase 2 (Days 4-14): Test term premium (longer lease at current vs shorter at lower)
- Phase 3 (Days 15-21): Seasonal positioning for peak
- Phase 4 (Days 22-30): Monitor and maintain

CRITICAL RULES:
- All dollar amounts are pre-computed and provided. Use them exactly as given.
- Every action must include: lever (FILL/REPRICE/RENEW/DE_CONCESSION), dollar impact, confidence, downside risk.
- Phase 3 MUST include conditional branching (if experiment succeeded → X, else → Y)
- Revenue gap figures come from the pre-computed gap_components — use them verbatim
- Experiment designs must match the diagnosis recommendations exactly

Output ONLY valid JSON matching this schema:
{
  "phases": [{
    "phase_number": "int 1-4",
    "name": "string",
    "days": "string (e.g., '1-3')",
    "actions": [{
      "id": "string (e.g., 'P1-1')",
      "unit_type": "string",
      "action_type": "string from taxonomy",
      "lever": "FILL|REPRICE|RENEW|DE_CONCESSION",
      "description": "string",
      "target_value": "float or null",
      "expected_impact_monthly": "float",
      "confidence": "HIGH|MEDIUM|LOW",
      "downside_risk": "string",
      "rationale": "string",
      "success_criteria": "string",
      "contingency": "string or null"
    }]
  }],
  "decision_points": [{
    "day": "int",
    "description": "string",
    "conditions": [{
      "if_condition": "string",
      "then_action": "string"
    }]
  }],
  "revenue_impact_summary": {
    "current_monthly_vacancy_cost": "float",
    "total_revenue_gap_monthly": "float",
    "projected_monthly_capture": "float",
    "daily_burn_rate": "float",
    "break_even_timeline_days": "int"
  },
  "experiment_summary": [{
    "unit_type": "string",
    "experiment_type": "string",
    "arms": [{"label": "string", "price": "float", "units": "int"}],
    "observation_days": "int",
    "convergence_rule": "string"
  }]
}"""


def run_diagnostic(
    db: Session,
    property_id: str,
    user_id: str,
    organization_id: str,
    claude_client: ClaudeClient | None = None,
    reference_date: date | None = None,
) -> DiagnosticRun:
    """Run the full diagnostic pipeline for a property.

    Pipeline: metrics → flags → Claude diagnosis → action plan → store.

    Args:
        db: database session.
        property_id: UUID of property.
        user_id: UUID of user triggering the run.
        organization_id: UUID of the organization.
        claude_client: optional ClaudeClient (for testing with mocks).
        reference_date: optional date override.

    Returns:
        DiagnosticRun ORM object with all results.
    """
    if reference_date is None:
        reference_date = date.today()
    if claude_client is None:
        claude_client = ClaudeClient()

    total_start = time.perf_counter()

    # Create diagnostic run record
    prop = db.query(Property).filter_by(id=property_id).first()
    if not prop:
        raise ValueError(f"Property {property_id} not found")

    config = db.query(ClientConfig).filter_by(
        property_id=property_id, is_active=True
    ).first()
    if not config:
        raise ValueError(f"No active config for property {property_id}")

    config_dict = {
        k: getattr(config, k) or {}
        for k in [
            "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
            "concession_policy", "renewal_policy", "lease_term_policy",
            "experiment_policy", "amenity_benchmarks", "revenue_efficiency_zones",
        ]
    }

    run = DiagnosticRun(
        id=uuid.uuid4(),
        property_id=property_id,
        config_id=config.id,
        run_date=datetime.utcnow(),
        triggered_by=user_id,
        status="RUNNING",
    )
    db.add(run)
    db.flush()

    try:
        # Step 1: Compute metrics
        metrics_start = time.perf_counter()
        metrics = compute_property_metrics(db, property_id, config_dict, reference_date)
        run.metrics_compute_ms = int((time.perf_counter() - metrics_start) * 1000)
        run.metrics_json = metrics

        # Step 2: Generate flags for each unit type
        all_flags = {}
        for ut_code, ut_metrics in metrics["unit_type_metrics"].items():
            flags = generate_flags(ut_metrics, config_dict)
            all_flags[ut_code] = flags
        run.flags_json = all_flags

        db.flush()

        # Step 3: Build context for Claude
        action_plan_context = build_action_plan_context(metrics, all_flags, config_dict)

        # Step 4: Claude diagnosis call
        diagnosis_start = time.perf_counter()
        diagnosis_user_msg = _build_diagnosis_prompt(
            metrics, all_flags, config_dict, config, reference_date, action_plan_context
        )

        try:
            diagnosis = claude_client.call_json(
                DIAGNOSIS_SYSTEM_PROMPT, diagnosis_user_msg
            )
        except ClaudeAPIError as e:
            logger.error("Claude diagnosis failed: %s", e)
            diagnosis = _fallback_diagnosis(metrics, all_flags)

        run.diagnosis_api_ms = int((time.perf_counter() - diagnosis_start) * 1000)
        run.diagnosis_json = diagnosis

        db.flush()

        # Step 5: Claude action plan call
        action_start = time.perf_counter()
        action_user_msg = _build_action_plan_prompt(
            diagnosis, metrics, all_flags, config_dict, action_plan_context
        )

        try:
            action_plan = claude_client.call_json(
                ACTION_PLAN_SYSTEM_PROMPT, action_user_msg
            )
        except ClaudeAPIError as e:
            logger.error("Claude action plan failed: %s", e)
            action_plan = _fallback_action_plan(diagnosis, metrics, action_plan_context)

        run.action_plan_api_ms = int((time.perf_counter() - action_start) * 1000)
        run.action_plan_json = action_plan

        # Finalize
        run.status = "COMPLETED"
        run.total_ms = int((time.perf_counter() - total_start) * 1000)

    except Exception as e:
        run.status = "FAILED"
        run.error_message = str(e)[:2000]
        run.total_ms = int((time.perf_counter() - total_start) * 1000)
        logger.exception("Diagnostic run failed for property %s", property_id)

    db.flush()

    # Audit log entry
    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=organization_id,
        user_id=user_id,
        action="RUN_DIAGNOSTIC",
        entity_type="diagnostic_run",
        entity_id=str(run.id),
        details={
            "property_id": str(property_id),
            "status": run.status,
            "total_ms": run.total_ms,
        },
    )
    db.add(audit)
    db.flush()

    return run


def _build_diagnosis_prompt(
    metrics: dict, all_flags: dict, config_dict: dict,
    config: ClientConfig, reference_date: date, context: dict,
) -> str:
    """Build the user message for the Claude diagnosis call."""
    return json.dumps({
        "property_name": metrics["property_name"],
        "reference_date": reference_date.isoformat(),
        "business_context": {
            "investment_thesis": config.investment_thesis,
            "risk_profile": config.risk_profile,
            "hold_period_years": config.hold_period_years,
            "business_plan_summary": config.business_plan_summary,
        },
        "config_thresholds": config_dict,
        "unit_type_metrics": {
            code: {
                "occupancy": m["occupancy_metrics"],
                "exposure": m["exposure_metrics"],
                "pricing": m["pricing_spreads"],
                "revenue": m["revenue_metrics"],
                "velocity": m["velocity_metrics"],
                "demand": m["demand_metrics"],
                "revenue_efficiency": m.get("revenue_efficiency", {}),
                "revenue_gap": m.get("revenue_gap", {}),
                "renewal_opportunity": m.get("renewal_opportunity", {}),
                "elasticity": m.get("elasticity", {}),
                "optimal_pricing": m.get("optimal_pricing", {}),
            }
            for code, m in metrics["unit_type_metrics"].items()
        },
        "flags_by_unit_type": {
            code: [{"type": f["type"], "severity": f["severity"], "value": _safe_serialize(f["value"])}
                   for f in flags]
            for code, flags in all_flags.items()
        },
        "portfolio_metrics": metrics["portfolio_metrics"],
        "pre_computed_revenue_facts": context["revenue_facts"],
        "experiment_eligibility": context["experiment_eligibility"],
        "seasonal_context": "March 2026 — spring ramp, 2 months to peak season (May-Sep)",
    }, indent=2)


def _build_action_plan_prompt(
    diagnosis: dict, metrics: dict, all_flags: dict,
    config_dict: dict, context: dict,
) -> str:
    """Build the user message for the Claude action plan call."""
    # Include per-unit-type revenue gap and renewal data for action planning
    unit_type_gaps = {}
    for code, m in metrics["unit_type_metrics"].items():
        unit_type_gaps[code] = {
            "revenue_gap": m.get("revenue_gap", {}),
            "renewal_opportunity": m.get("renewal_opportunity", {}),
            "revenue_efficiency": m.get("revenue_efficiency", {}),
            "elasticity": m.get("elasticity", {}),
        }

    return json.dumps({
        "diagnosis": diagnosis,
        "unit_type_revenue_data": unit_type_gaps,
        "pre_computed_revenue_facts": context["revenue_facts"],
        "experiment_designs": context["experiment_designs"],
        "experiment_eligibility": context["experiment_eligibility"],
        "config_thresholds": config_dict,
        "portfolio_daily_burn": context["revenue_facts"].get("total_daily_burn", 0),
    }, indent=2)


def _safe_serialize(value):
    """Make flag values JSON-serializable."""
    if isinstance(value, dict):
        return {k: _safe_serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe_serialize(v) for v in value]
    return value


def _fallback_diagnosis(metrics: dict, all_flags: dict) -> dict:
    """Generate fallback diagnosis when Claude is unavailable.

    Uses pre-computed revenue_efficiency scores and revenue_gap decomposition
    instead of flag-count heuristics. Falls back to flag-based scoring when
    revenue efficiency data is not present (backward compatibility).
    """
    assessments = []

    # Build list of (code, metrics) sorted by revenue gap descending
    sorted_units = sorted(
        metrics["unit_type_metrics"].items(),
        key=lambda item: item[1].get("revenue_gap", {}).get("total_gap_monthly", 0),
        reverse=True,
    )

    for code, m in sorted_units:
        flags = all_flags.get(code, [])
        efficiency = m.get("revenue_efficiency", {})
        gap = m.get("revenue_gap", {})
        renewal = m.get("renewal_opportunity", {})
        elasticity = m.get("elasticity", {})
        optimal = m.get("optimal_pricing", {})

        # Use pre-computed score/grade if available, else fall back to flags
        if efficiency and "revenue_efficiency_score" in efficiency:
            score = efficiency["revenue_efficiency_score"]
            grade = efficiency.get("grade", _score_to_fallback_grade(score))
        else:
            score, grade = _flag_based_score(flags)

        occ = m["occupancy_metrics"]["occupancy_rate"]
        occ_metrics = m["occupancy_metrics"]
        pricing = m["pricing_spreads"]

        # Build key findings from gap components
        key_findings = _build_key_findings(m, gap, renewal, efficiency, flags)

        # Build recommended actions from gap components
        dominant_lever = gap.get("dominant_lever", "FILL")
        gap_components = gap.get("gap_components", {})
        total_gap_monthly = gap.get("total_gap_monthly", 0)
        recommended_actions = _build_fallback_actions(
            code, grade, dominant_lever, gap_components,
            occ_metrics, pricing, optimal, renewal, elasticity,
        )

        assessments.append({
            "unit_type": code,
            "health_score": score,
            "grade": grade,
            "score_reasoning": _build_score_reasoning(efficiency, flags, occ),
            "dominant_lever": dominant_lever,
            "revenue_gap_monthly": total_gap_monthly,
            "root_cause": _build_root_cause(grade, dominant_lever, gap_components, pricing),
            "key_findings": key_findings,
            "anomalies": [],
            "recommended_actions": recommended_actions,
            "experiment_design": {
                "recommended": False, "arms": [],
                "observation_window_days": 14, "convergence_rule": "",
                "rationale": "Fallback mode — Claude unavailable",
            },
        })

    # Portfolio score: weighted average of unit type scores by total units
    total_units = sum(
        m["occupancy_metrics"].get("total_units", 0)
        for m in metrics["unit_type_metrics"].values()
    )
    if total_units > 0:
        portfolio_score = int(sum(
            a["health_score"] * metrics["unit_type_metrics"][a["unit_type"]]["occupancy_metrics"].get("total_units", 0)
            for a in assessments
        ) / total_units)
    else:
        portfolio_score = 50

    # Top 3 priorities: unit types with largest gaps
    top_3 = [
        f"{a['unit_type']}: {a['dominant_lever']} (${a['revenue_gap_monthly']:,.0f}/mo gap)"
        for a in assessments[:3]
        if a["revenue_gap_monthly"] > 0
    ]

    return {
        "unit_type_assessments": assessments,
        "portfolio_assessment": {
            "summary": "Fallback diagnosis — Claude API unavailable. Revenue efficiency analysis generated from pre-computed data.",
            "cross_unit_type_risks": [],
            "overall_portfolio_score": portfolio_score,
            "top_3_priorities": top_3,
        },
        "further_investigation": [],
    }


def _score_to_fallback_grade(score: int) -> str:
    """Map a numeric score to a revenue efficiency grade."""
    if score >= 85:
        return "OPTIMIZED"
    elif score >= 70:
        return "OPPORTUNITY"
    elif score >= 55:
        return "IMBALANCED"
    elif score >= 40:
        return "DISTRESSED"
    else:
        return "CRISIS"


def _flag_based_score(flags: list[dict]) -> tuple[int, str]:
    """Fall back to flag-count scoring when revenue efficiency is unavailable."""
    critical_count = sum(1 for f in flags if f["severity"] == "CRITICAL")
    high_count = sum(1 for f in flags if f["severity"] == "HIGH")

    if critical_count >= 2:
        return 25, "CRISIS"
    elif critical_count >= 1 or high_count >= 3:
        return 50, "DISTRESSED"
    elif high_count >= 1:
        return 65, "IMBALANCED"
    else:
        return 85, "OPTIMIZED"


def _build_score_reasoning(
    efficiency: dict, flags: list[dict], occ: float,
) -> str:
    """Build a human-readable score reasoning string."""
    if efficiency and "dimensions" in efficiency:
        dims = efficiency["dimensions"]
        parts = [
            f"Revenue efficiency score: {efficiency.get('revenue_efficiency_score', 'N/A')}",
            f"(occ_health={dims.get('occupancy_health', {}).get('score', 'N/A')},",
            f"pricing={dims.get('pricing_alignment', {}).get('score', 'N/A')},",
            f"momentum={dims.get('rent_roll_momentum', {}).get('score', 'N/A')})",
            f"Zone: {efficiency.get('occupancy_zone', 'N/A')}.",
        ]
        return " ".join(parts)
    critical_count = sum(1 for f in flags if f["severity"] == "CRITICAL")
    high_count = sum(1 for f in flags if f["severity"] == "HIGH")
    return f"Flag-based fallback: {len(flags)} flags ({critical_count} critical, {high_count} high). Occupancy {occ:.0%}."


def _build_root_cause(
    grade: str, dominant_lever: str,
    gap_components: dict, pricing: dict,
) -> str | None:
    """Build a root cause string from grade and gap data."""
    if grade in ("OPTIMIZED", "OPPORTUNITY"):
        return None

    lever_descriptions = {
        "FILL": "Vacancy is the dominant revenue drain",
        "REPRICE": "Asking rent misalignment with optimal pricing",
        "RENEW": "In-place rent below market, addressable at renewal",
        "DE_CONCESSION": "Active concessions reducing effective rent",
    }

    cause = lever_descriptions.get(dominant_lever, "Multiple factors")

    # Add dollar context from largest component
    largest_amount = 0
    largest_name = ""
    for name, comp in gap_components.items():
        amt = comp.get("amount", 0)
        if amt > largest_amount:
            largest_amount = amt
            largest_name = name

    if largest_amount > 0:
        cause += f" — ${largest_amount:,.0f}/mo from {largest_name.replace('_', ' ')}"

    return cause


def _build_key_findings(
    m: dict, gap: dict, renewal: dict,
    efficiency: dict, flags: list[dict],
) -> list[str]:
    """Build key findings list from pre-computed data."""
    findings = []

    total_gap = gap.get("total_gap_monthly", 0)
    if total_gap > 0:
        findings.append(f"Revenue gap: ${total_gap:,.0f}/mo")

    dominant = gap.get("dominant_lever")
    if dominant:
        findings.append(f"Dominant lever: {dominant}")

    gap_components = gap.get("gap_components", {})
    vacancy_cost = gap_components.get("vacancy_cost", {}).get("amount", 0)
    if vacancy_cost > 0:
        findings.append(f"Vacancy cost: ${vacancy_cost:,.0f}/mo")

    renewal_count = renewal.get("upcoming_renewals_90d", 0)
    if renewal_count > 0:
        increase_pct = renewal.get("recommended_increase_pct", 0)
        capture = renewal.get("net_monthly_capture", 0)
        findings.append(
            f"{renewal_count} renewals in 90d, {increase_pct}% increase = ${capture:,.0f}/mo capture"
        )

    grade = efficiency.get("grade", "")
    if grade:
        findings.append(f"Grade: {grade}")

    # Add top flag types if we have room
    for f in flags[:2]:
        if len(findings) < 7:
            findings.append(f["type"])

    return findings[:7]


def _build_fallback_actions(
    code: str, grade: str, dominant_lever: str,
    gap_components: dict, occ_metrics: dict, pricing: dict,
    optimal: dict, renewal: dict, elasticity: dict,
) -> list[dict]:
    """Build recommended actions from gap components and grade."""
    actions = []
    occ = occ_metrics.get("occupancy_rate", 0)
    asking = pricing.get("asking_rent", 0)
    optimal_asking = optimal.get("optimal_asking", asking)
    confidence = optimal.get("confidence", "LOW")

    vacancy_gap = gap_components.get("vacancy_cost", {}).get("amount", 0)
    reprice_gap = gap_components.get("new_lease_underpricing", {}).get("amount", 0)
    renewal_gap = gap_components.get("renewal_opportunity", {}).get("amount", 0)
    concession_gap = gap_components.get("concession_drag", {}).get("amount", 0)

    priority = 1

    # CRISIS/DISTRESSED: focus on fill
    if grade in ("CRISIS", "DISTRESSED"):
        if asking > optimal_asking and optimal_asking > 0:
            actions.append({
                "action_type": "REDUCE_ASKING_RENT",
                "lever": "REPRICE",
                "priority": priority,
                "description": f"Reduce asking from ${asking:,.0f} to ${optimal.get('recommended_asking', asking):,.0f}",
                "target_value": optimal.get("recommended_asking"),
                "expected_impact_monthly": reprice_gap + vacancy_gap,
                "confidence": confidence,
                "downside_risk": "May lower in-place renewal benchmarks",
                "reasoning": f"Grade {grade}: fill is priority. Asking above optimal by ${asking - optimal_asking:,.0f}.",
            })
            priority += 1
        if vacancy_gap > 0:
            actions.append({
                "action_type": "OFFER_MOVE_IN_CONCESSION",
                "lever": "FILL",
                "priority": priority,
                "description": f"Offer move-in concession on {occ_metrics.get('vacant', 0)} vacant units",
                "target_value": None,
                "expected_impact_monthly": vacancy_gap,
                "confidence": "HIGH",
                "downside_risk": "Concession drag if market improves",
                "reasoning": f"${vacancy_gap:,.0f}/mo vacancy cost. Concessions accelerate fill.",
            })
            priority += 1
        actions.append({
            "action_type": "FREEZE_RENEWAL_INCREASES",
            "lever": "RENEW",
            "priority": priority,
            "description": "Freeze all renewal increases during crisis",
            "target_value": None,
            "expected_impact_monthly": 0,
            "confidence": "HIGH",
            "downside_risk": "Miss renewal revenue capture opportunity",
            "reasoning": f"Grade {grade}: retain existing tenants while stabilizing.",
        })

    # IMBALANCED: quick wins + experiments
    elif grade == "IMBALANCED":
        if dominant_lever == "REPRICE" and reprice_gap > 0:
            if asking > optimal_asking:
                actions.append({
                    "action_type": "REDUCE_ASKING_RENT",
                    "lever": "REPRICE",
                    "priority": priority,
                    "description": f"Reduce asking from ${asking:,.0f} toward ${optimal.get('recommended_asking', asking):,.0f}",
                    "target_value": optimal.get("recommended_asking"),
                    "expected_impact_monthly": reprice_gap,
                    "confidence": confidence,
                    "downside_risk": "May overshoot if demand improves seasonally",
                    "reasoning": f"Dominant lever is REPRICE: ${reprice_gap:,.0f}/mo gap.",
                })
                priority += 1
        if elasticity.get("confidence") == "LOW":
            actions.append({
                "action_type": "LAUNCH_PRICE_EXPERIMENT",
                "lever": "REPRICE",
                "priority": priority,
                "description": "Launch price experiment to establish elasticity",
                "target_value": optimal.get("recommended_asking"),
                "expected_impact_monthly": reprice_gap,
                "confidence": "LOW",
                "downside_risk": "Experiment delays may extend vacancy",
                "reasoning": "Elasticity confidence LOW — experimentation recommended to gather data.",
            })
            priority += 1
        if renewal_gap > 0:
            actions.append({
                "action_type": "IMPLEMENT_RENEWAL_INCREASE",
                "lever": "RENEW",
                "priority": priority,
                "description": f"Implement {renewal.get('recommended_increase_pct', 0)}% renewal increase (${renewal.get('recommended_increase_dollars', 0):,.0f}/unit)",
                "target_value": renewal.get("recommended_increase_pct"),
                "expected_impact_monthly": renewal_gap,
                "confidence": renewal.get("confidence", "LOW"),
                "downside_risk": "Turnover risk if increase too aggressive",
                "reasoning": f"${renewal_gap:,.0f}/mo capturable from {renewal.get('upcoming_renewals_90d', 0)} upcoming renewals.",
            })

    # OPPORTUNITY: push rents + renewals
    elif grade == "OPPORTUNITY":
        if renewal_gap > 0:
            actions.append({
                "action_type": "IMPLEMENT_RENEWAL_INCREASE",
                "lever": "RENEW",
                "priority": priority,
                "description": f"Implement {renewal.get('recommended_increase_pct', 0)}% renewal increase (${renewal.get('recommended_increase_dollars', 0):,.0f}/unit)",
                "target_value": renewal.get("recommended_increase_pct"),
                "expected_impact_monthly": renewal_gap,
                "confidence": renewal.get("confidence", "MEDIUM"),
                "downside_risk": "Turnover risk if market softens",
                "reasoning": f"${renewal_gap:,.0f}/mo capturable. Grade OPPORTUNITY supports increases.",
            })
            priority += 1
        if concession_gap > 0:
            actions.append({
                "action_type": "REMOVE_CONCESSION",
                "lever": "DE_CONCESSION",
                "priority": priority,
                "description": f"Remove active concessions (${concession_gap:,.0f}/mo drag)",
                "target_value": None,
                "expected_impact_monthly": concession_gap,
                "confidence": "MEDIUM",
                "downside_risk": "May slow leasing velocity",
                "reasoning": f"Occupancy {occ:.0%} supports concession removal.",
            })
            priority += 1
        if asking < optimal_asking and occ >= 0.92:
            actions.append({
                "action_type": "INCREASE_ASKING_RENT",
                "lever": "REPRICE",
                "priority": priority,
                "description": f"Increase asking from ${asking:,.0f} toward ${optimal.get('recommended_asking', asking):,.0f}",
                "target_value": optimal.get("recommended_asking"),
                "expected_impact_monthly": reprice_gap,
                "confidence": confidence,
                "downside_risk": "May slow velocity if market is more elastic than estimated",
                "reasoning": f"Asking ${asking - optimal_asking:,.0f} below optimal with {occ:.0%} occupancy.",
            })
        elif asking < optimal_asking:
            actions.append({
                "action_type": "TEST_HIGHER_ASKING",
                "lever": "REPRICE",
                "priority": priority,
                "description": f"Test higher asking: ${optimal.get('recommended_asking', asking):,.0f} on select units",
                "target_value": optimal.get("recommended_asking"),
                "expected_impact_monthly": reprice_gap,
                "confidence": "MEDIUM",
                "downside_risk": "Test units may sit longer",
                "reasoning": f"Asking below optimal but occ {occ:.0%} < 92% — test before committing.",
            })

    # OPTIMIZED: hold + seasonal positioning
    elif grade == "OPTIMIZED":
        actions.append({
            "action_type": "HOLD_ASKING_RENT",
            "lever": "REPRICE",
            "priority": priority,
            "description": f"Hold asking at ${asking:,.0f} — near revenue frontier",
            "target_value": asking,
            "expected_impact_monthly": 0,
            "confidence": "HIGH",
            "downside_risk": "May miss upside if demand surge",
            "reasoning": f"Grade OPTIMIZED: currently maximizing revenue.",
        })
        priority += 1
        if renewal_gap > 0:
            actions.append({
                "action_type": "IMPLEMENT_RENEWAL_INCREASE",
                "lever": "RENEW",
                "priority": priority,
                "description": f"Implement {renewal.get('recommended_increase_pct', 0)}% renewal increase",
                "target_value": renewal.get("recommended_increase_pct"),
                "expected_impact_monthly": renewal_gap,
                "confidence": renewal.get("confidence", "MEDIUM"),
                "downside_risk": "Turnover risk",
                "reasoning": f"${renewal_gap:,.0f}/mo capturable. Strong occupancy supports increases.",
            })
            priority += 1
        actions.append({
            "action_type": "TEST_TERM_PREMIUM",
            "lever": "REPRICE",
            "priority": priority,
            "description": "Test longer lease at current rent vs shorter at lower",
            "target_value": None,
            "expected_impact_monthly": 0,
            "confidence": "MEDIUM",
            "downside_risk": "May reduce flexibility",
            "reasoning": "Optimized units benefit from lease-term experimentation.",
        })

    return actions


def _fallback_action_plan(diagnosis: dict, metrics: dict, context: dict) -> dict:
    """Generate fallback action plan when Claude is unavailable.

    Phase naming adapts to worst grade in the diagnosis.
    """
    # Determine worst grade for phase structure
    assessments = diagnosis.get("unit_type_assessments", [])
    grade_order = {"CRISIS": 0, "DISTRESSED": 1, "IMBALANCED": 2, "OPPORTUNITY": 3, "OPTIMIZED": 4}
    worst_grade = "OPTIMIZED"
    for a in assessments:
        g = a.get("grade", "OPTIMIZED")
        if grade_order.get(g, 4) < grade_order.get(worst_grade, 4):
            worst_grade = g

    # Phase names adapt to dominant problem
    phase_names = {
        "CRISIS": ["Fill Vacancies", "Stabilize", "Evaluate & Optimize", "Lock Strategy"],
        "DISTRESSED": ["Fill Vacancies", "Stabilize", "Evaluate & Optimize", "Lock Strategy"],
        "IMBALANCED": ["Quick Wins", "Experiment & Renew", "Converge", "Lock Strategy"],
        "OPPORTUNITY": ["Renewal Increases", "Test Higher Asking", "Seasonal Positioning", "Maintain"],
        "OPTIMIZED": ["Hold & Document", "Term Premium Tests", "Seasonal Positioning", "Maintain"],
    }
    names = phase_names.get(worst_grade, phase_names["IMBALANCED"])

    # Compute total revenue gap
    total_gap = sum(
        m.get("revenue_gap", {}).get("total_gap_monthly", 0)
        for m in metrics["unit_type_metrics"].values()
    )

    return {
        "phases": [
            {"phase_number": 1, "name": names[0], "days": "1-3", "actions": []},
            {"phase_number": 2, "name": names[1], "days": "4-14", "actions": []},
            {"phase_number": 3, "name": names[2], "days": "15-21", "actions": []},
            {"phase_number": 4, "name": names[3], "days": "22-30", "actions": []},
        ],
        "decision_points": [],
        "revenue_impact_summary": {
            **context["revenue_facts"],
            "total_revenue_gap_monthly": total_gap,
        },
        "experiment_summary": [],
    }
