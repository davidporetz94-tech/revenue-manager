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

DIAGNOSIS_SYSTEM_PROMPT = """You are a senior multifamily revenue management analyst with 15+ years of institutional portfolio experience. You receive structured metrics and flags from a pricing engine, along with the client's business plan context and threshold configuration.

Produce a JSON diagnosis with:
1. Health score (0-100) per unit type WITH reasoning — score reflects alignment with CLIENT'S strategy
2. Grade: HEALTHY (80-100), WATCH (65-79), ACTION_NEEDED (40-64), CRITICAL (0-39)
3. Root cause analysis for underperforming unit types
4. Specific, actionable recommendations from the action taxonomy
5. Experiment designs where appropriate (MEDIUM confidence situations)

CRITICAL RULES:
- When a unit type has CRITICAL severity flags AND high confidence root cause, recommend DIRECT ACTION (price cut, concession), NOT an experiment. Experimenting during a crisis is irresponsible.
- When confidence is MEDIUM, prefer experiments over direct action.
- When confidence is LOW, prefer investigation.
- Never recommend experiments for unit types with < min_vacant_for_experiment vacant units.
- Every dollar amount in your response must come from the pre-computed facts provided. Do NOT invent numbers.

SCORING RUBRIC (mandatory — scores outside these ranges are invalid):

- 2+ CRITICAL flags AND occupancy below crisis threshold → score 15-30
- 1 CRITICAL flag OR 3+ HIGH flags → score 30-50
- Multiple HIGH + MEDIUM flags, no CRITICAL → score 45-60
- Mix of MEDIUM flags, possibly 1 HIGH → score 55-70
- Mostly LOW/POSITIVE flags, minor concerns only → score 70-85
- All metrics healthy, no flags requiring action → score 85-95

Pick a specific score within the range. Justify with the 2-3 most influential flags.
Identical inputs must produce scores within ±5 points across runs.

Expected ranges for reference (do NOT hardcode these — derive from the rules above):
- Unit type with 3 low-severity flags, 96% occ: 75-85
- Unit type with 7 flags including HIGH, 86% occ declining: 50-65
- Unit type with 12 flags including 2 CRITICAL, 79% occ: 20-35
- Unit type with 7 flags, zero CRITICAL, puzzle profile: 55-65

Action taxonomy:
- Pricing: REDUCE_ASKING_RENT, INCREASE_ASKING_RENT, HOLD_ASKING_RENT
- Concessions: OFFER_MOVE_IN_CONCESSION, OFFER_LOOK_AND_LEASE, REMOVE_CONCESSION
- Experiments: LAUNCH_PRICE_EXPERIMENT, LAUNCH_CONCESSION_EXPERIMENT, CONVERGE_EXPERIMENT
- Renewals: SET_RENEWAL_INCREASE, FREEZE_RENEWAL_INCREASES
- Lease terms: ADJUST_PREFERRED_LEASE_TERM, OFFER_SHORT_TERM_PREMIUM
- Audits: AUDIT_AMENITY_PRICING, INVESTIGATE_NON_PRICE_FACTORS

Output ONLY valid JSON matching this schema:
{
  "unit_type_assessments": [{
    "unit_type": "string",
    "health_score": "int 0-100",
    "score_reasoning": "string",
    "grade": "HEALTHY|WATCH|ACTION_NEEDED|CRITICAL",
    "root_cause": "string or null",
    "key_findings": ["string"],
    "anomalies": ["string"],
    "recommended_actions": [{
      "action_type": "string from taxonomy",
      "priority": "int 1-5",
      "description": "string",
      "target_value": "float or null",
      "expected_impact_monthly": "float or null",
      "confidence": "HIGH|MEDIUM|LOW",
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
    "cross_property_patterns": ["string"],
    "overall_portfolio_score": "int",
    "top_3_priorities": ["string"]
  },
  "further_investigation": [{"area": "string", "reason": "string", "data_needed": "string"}]
}"""

ACTION_PLAN_SYSTEM_PROMPT = """You are a senior multifamily revenue management strategist. Given a diagnosis with health scores, root causes, and recommendations, produce a detailed 30-day phased action plan.

The plan has 4 phases:
- Phase 1 (Days 1-3): Immediate stabilization — address CRITICAL items and launch experiments
- Phase 2 (Days 4-14): Calibrate & optimize — secondary actions, audits, investigations
- Phase 3 (Days 15-21): Decision point — evaluate experiment results, branch based on outcomes
- Phase 4 (Days 22-30): Optimize — lock strategies based on Phase 3 outcomes

CRITICAL RULES:
- All dollar amounts are pre-computed and provided. Use them exactly as given.
- Phase 3 MUST include conditional branching (if experiment succeeded → X, else → Y)
- Revenue at risk figures come from the metrics — use them verbatim
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
      "description": "string",
      "target_value": "float or null",
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
    "projected_monthly_savings": "float",
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
            "experiment_policy", "amenity_benchmarks",
        ]
    }

    run = DiagnosticRun(
        id=uuid.uuid4(),
        property_id=property_id,
        organization_id=organization_id,
        scope="property",
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
    return json.dumps({
        "diagnosis": diagnosis,
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
    """Generate fallback diagnosis when Claude is unavailable."""
    assessments = []
    for code, m in metrics["unit_type_metrics"].items():
        flags = all_flags.get(code, [])
        critical_count = sum(1 for f in flags if f["severity"] == "CRITICAL")
        high_count = sum(1 for f in flags if f["severity"] == "HIGH")

        # Scoring rubric aligned with Claude prompt ranges
        if critical_count >= 2:
            score, grade = 25, "CRITICAL"  # 15-30 range
        elif critical_count >= 1 or high_count >= 3:
            score, grade = 40, "ACTION_NEEDED"  # 30-50 range
        elif high_count >= 1:
            score, grade = 60, "ACTION_NEEDED"  # 45-60 range (multiple HIGH+MEDIUM)
        elif len(flags) > 3:
            score, grade = 65, "WATCH"  # 55-70 range (mix of MEDIUM)
        elif len(flags) > 0:
            score, grade = 80, "HEALTHY"  # 70-85 range (minor concerns)
        else:
            score, grade = 90, "HEALTHY"  # 85-95 range (all healthy)

        occ = m["occupancy_metrics"]["occupancy_rate"]
        exp = m["exposure_metrics"]["total_exposure_pct"]

        assessments.append({
            "unit_type": code,
            "health_score": score,
            "score_reasoning": f"Based on {len(flags)} flags ({critical_count} critical, {high_count} high). Occupancy {occ}, exposure {exp}.",
            "grade": grade,
            "root_cause": f"{critical_count} critical and {high_count} high-severity flags detected." if critical_count + high_count > 0 else None,
            "key_findings": [f["type"] for f in flags[:5]],
            "anomalies": [],
            "recommended_actions": [],
            "experiment_design": {"recommended": False, "arms": [], "observation_window_days": 14, "convergence_rule": "", "rationale": "Fallback mode — Claude unavailable"},
        })

    return {
        "unit_type_assessments": assessments,
        "portfolio_assessment": {
            "summary": "Fallback diagnosis — Claude API unavailable",
            "cross_property_patterns": [],
            "overall_portfolio_score": 50,
            "top_3_priorities": [],
        },
        "further_investigation": [],
    }


def _fallback_action_plan(diagnosis: dict, metrics: dict, context: dict) -> dict:
    """Generate fallback action plan when Claude is unavailable."""
    return {
        "phases": [
            {"phase_number": 1, "name": "Immediate Review", "days": "1-3", "actions": []},
            {"phase_number": 2, "name": "Calibration", "days": "4-14", "actions": []},
            {"phase_number": 3, "name": "Decision Point", "days": "15-21", "actions": []},
            {"phase_number": 4, "name": "Optimization", "days": "22-30", "actions": []},
        ],
        "decision_points": [],
        "revenue_impact_summary": context["revenue_facts"],
        "experiment_summary": [],
    }
