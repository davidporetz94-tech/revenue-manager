"""Portfolio diagnostic service — orchestrates portfolio-wide pricing diagnostic.

Pipeline: for each property → metrics → flags → aggregate → Claude diagnosis → action plan → store.
"""
import json
import logging
import time
import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.property import Property
from app.models.config import ClientConfig
from app.models.diagnostic import DiagnosticRun, AuditLog
from app.services.metrics_engine import compute_property_metrics
from app.services.flag_generator import generate_flags
from app.services.claude_client import ClaudeClient, ClaudeAPIError
from app.engine.aggregator import aggregate_cross_property

logger = logging.getLogger(__name__)

PORTFOLIO_DIAGNOSIS_SYSTEM_PROMPT = """You are a senior multifamily revenue management analyst analyzing a multi-property portfolio. You receive aggregated metrics and flags for all properties, along with per-property breakdowns.

Produce a JSON diagnosis with:
1. Portfolio health score (0-100) reflecting the overall state
2. Per-property assessments with scores and grades
3. Cross-property patterns and comparisons
4. Prioritized recommendations across properties

SCORING RUBRIC:
- Multiple properties with CRITICAL flags, high vacancy → score 15-30
- One property below target, others stable → score 35-50
- All properties have concerns but none below target → score 50-65
- Minor issues across portfolio → score 65-80
- All properties healthy → score 80-95

CRITICAL RULES:
- Every dollar amount must come from the pre-computed facts. Do NOT invent numbers.
- Rank properties by priority (daily burn rate is the primary signal)
- Identify patterns that appear across multiple properties

TONE GUIDANCE:
- Use a professional consulting tone. Be direct and specific but NOT alarmist.
- Avoid words like: hemorrhaging, bleeding, crisis, dire, desperate, catastrophic, freefall.
- Instead use: below target, needs attention, priority action, opportunity cost, underperforming.
- Frame gaps as capturable revenue, not losses.

Output ONLY valid JSON matching this schema:
{
  "cross_property_assessment": {
    "summary": "string",
    "portfolio_score": "int 0-100",
    "property_rankings": [{"property": "string", "score": "int", "grade": "string", "daily_burn": "float"}],
    "cross_property_patterns": ["string"],
    "top_3_priorities": ["string"]
  },
  "property_assessments": [{
    "property_name": "string",
    "health_score": "int 0-100",
    "grade": "HEALTHY|WATCH|ACTION_NEEDED|CRITICAL",
    "key_findings": ["string"],
    "recommended_actions": [{
      "action_type": "string",
      "unit_type": "string",
      "description": "string",
      "priority": "int 1-5",
      "confidence": "HIGH|MEDIUM|LOW"
    }]
  }]
}"""

PORTFOLIO_ACTION_PLAN_SYSTEM_PROMPT = """You are a senior multifamily revenue management strategist creating a 30-day action plan for a multi-property portfolio. Actions must be prioritized ACROSS properties by impact (daily burn reduction).

The plan has 4 phases:
- Phase 1 (Days 1-3): Priority actions — address highest-impact properties first
- Phase 2 (Days 4-14): Calibrate & optimize across all properties
- Phase 3 (Days 15-21): Evaluate experiments, branch based on outcomes
- Phase 4 (Days 22-30): Lock strategies

CRITICAL RULES:
- All dollar amounts are pre-computed. Use them exactly.
- Actions must specify which property AND unit type they apply to
- Rank Phase 1 actions by daily burn impact (highest first)
- Phase 3 must include conditional branching per property

TONE GUIDANCE:
- Use a professional consulting tone. Be direct and specific but NOT alarmist.
- Avoid words like: hemorrhaging, bleeding, crisis, dire, desperate, catastrophic, freefall.
- Instead use: below target, needs attention, priority action, opportunity cost, underperforming.
- Frame actions as recommendations, not emergencies.

Output ONLY valid JSON matching this schema:
{
  "phases": [{
    "phase_number": "int 1-4",
    "name": "string",
    "days": "string",
    "actions": [{
      "id": "string",
      "property": "string",
      "unit_type": "string",
      "action_type": "string",
      "description": "string",
      "rationale": "string"
    }]
  }],
  "revenue_impact_summary": {
    "current_portfolio_daily_burn": "float",
    "current_portfolio_monthly_cost": "float",
    "projected_monthly_savings": "float"
  }
}"""


def run_portfolio_diagnostic(
    db: Session,
    organization_id: str,
    user_id: str,
    claude_client: ClaudeClient | None = None,
    reference_date: date | None = None,
) -> DiagnosticRun:
    """Run the full portfolio diagnostic pipeline.

    Args:
        db: database session.
        organization_id: UUID of the organization.
        user_id: UUID of user triggering the run.
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

    # Create portfolio diagnostic run
    run = DiagnosticRun(
        id=uuid.uuid4(),
        property_id=None,
        organization_id=organization_id,
        scope="portfolio",
        config_id=None,
        run_date=datetime.utcnow(),
        triggered_by=user_id,
        status="RUNNING",
    )
    db.add(run)
    db.flush()

    try:
        # Step 1: Compute metrics for all properties
        metrics_start = time.perf_counter()
        props = db.query(Property).filter_by(organization_id=organization_id).all()

        all_property_data = []
        skipped = []
        for prop in props:
            config = db.query(ClientConfig).filter_by(
                property_id=prop.id, is_active=True
            ).first()
            if not config:
                skipped.append(prop.name)
                logger.warning("Skipping property %s — no active config", prop.name)
                continue

            config_dict = {
                k: getattr(config, k) or {}
                for k in [
                    "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
                    "concession_policy", "renewal_policy", "lease_term_policy",
                    "experiment_policy", "amenity_benchmarks",
                ]
            }
            metrics = compute_property_metrics(db, str(prop.id), config_dict, reference_date)

            prop_flags = {}
            for ut_code, ut_metrics in metrics["unit_type_metrics"].items():
                prop_flags[ut_code] = generate_flags(ut_metrics, config_dict)

            all_property_data.append({"metrics": metrics, "flags": prop_flags})

        if not all_property_data:
            raise ValueError("No properties with active configs found")

        # Step 2: Aggregate across properties
        # Convert list format to dict format expected by aggregate_cross_property
        property_metrics_dict = {}
        for entry in all_property_data:
            m = entry["metrics"]
            prop_name = m.get("property_name", f"Property_{len(property_metrics_dict)}")
            property_metrics_dict[prop_name] = m
        portfolio_metrics = aggregate_cross_property(property_metrics_dict)
        run.metrics_compute_ms = int((time.perf_counter() - metrics_start) * 1000)
        run.metrics_json = portfolio_metrics

        # Flatten flags for storage
        all_flags = {}
        for entry in all_property_data:
            m = entry["metrics"]
            prop_name = m.get("property_name", "Unknown")
            all_flags[prop_name] = entry["flags"]
        run.flags_json = all_flags
        db.flush()

        # Step 3: Claude diagnosis
        diagnosis_start = time.perf_counter()
        diagnosis_msg = json.dumps({
            "aggregate": portfolio_metrics["aggregate"],
            "properties": {
                name: {
                    "unit_type_metrics": {
                        code: {
                            "occupancy": m["occupancy_metrics"],
                            "exposure": m["exposure_metrics"],
                            "pricing": m["pricing_spreads"],
                            "revenue": m["revenue_metrics"],
                        }
                        for code, m in pdata["unit_type_metrics"].items()
                    },
                    "portfolio_metrics": pdata["portfolio_metrics"],
                }
                for name, pdata in portfolio_metrics["properties"].items()
            },
            "flags_by_property": {
                name: {
                    code: [{"type": f["type"], "severity": f["severity"]} for f in flags]
                    for code, flags in prop_flags.items()
                }
                for name, prop_flags in all_flags.items()
            },
        }, indent=2)

        try:
            diagnosis = claude_client.call_json(PORTFOLIO_DIAGNOSIS_SYSTEM_PROMPT, diagnosis_msg)
        except (ClaudeAPIError, Exception) as e:
            logger.error("Portfolio Claude diagnosis failed: %s", e)
            diagnosis = _fallback_portfolio_diagnosis(portfolio_metrics)

        run.diagnosis_api_ms = int((time.perf_counter() - diagnosis_start) * 1000)
        run.diagnosis_json = diagnosis
        db.flush()

        # Step 4: Claude action plan
        action_start = time.perf_counter()
        # Compute per-property revenue facts for action planning
        revenue_facts_by_property = {}
        for pdata in all_property_data:
            prop_metrics = pdata["metrics"]
            prop_name = prop_metrics.get("property_name", "Unknown")
            daily_burn = sum(
                m["revenue_metrics"]["daily_vacancy_burn"]
                for m in prop_metrics["unit_type_metrics"].values()
            )
            gap_components = {}
            for code, m in prop_metrics["unit_type_metrics"].items():
                gap = m.get("revenue_gap", {}).get("gap_components", {})
                gap_components[code] = {
                    lever: comp.get("amount", 0)
                    for lever, comp in gap.items()
                }
            revenue_facts_by_property[prop_name] = {
                "daily_burn": daily_burn,
                "gap_components_by_unit_type": gap_components,
            }

        action_msg = json.dumps({
            "diagnosis": diagnosis,
            "aggregate": portfolio_metrics["aggregate"],
            "revenue_facts_by_property": revenue_facts_by_property,
        }, indent=2)

        try:
            action_plan = claude_client.call_json(PORTFOLIO_ACTION_PLAN_SYSTEM_PROMPT, action_msg)
        except (ClaudeAPIError, Exception) as e:
            logger.error("Portfolio Claude action plan failed: %s", e)
            action_plan = _fallback_portfolio_action_plan(portfolio_metrics)

        run.action_plan_api_ms = int((time.perf_counter() - action_start) * 1000)
        run.action_plan_json = action_plan

        run.status = "COMPLETED"
        run.total_ms = int((time.perf_counter() - total_start) * 1000)

    except Exception as e:
        run.status = "FAILED"
        run.error_message = str(e)[:2000]
        run.total_ms = int((time.perf_counter() - total_start) * 1000)
        logger.exception("Portfolio diagnostic failed for org %s", organization_id)

    db.flush()

    # Audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=organization_id,
        user_id=user_id,
        action="RUN_PORTFOLIO_DIAGNOSTIC",
        entity_type="diagnostic_run",
        entity_id=str(run.id),
        details={
            "scope": "portfolio",
            "property_count": len(all_property_data) if 'all_property_data' in dir() else 0,
            "properties_skipped": skipped if 'skipped' in dir() else [],
            "status": run.status,
            "total_ms": run.total_ms,
        },
    )
    db.add(audit)
    db.flush()

    return run


def _fallback_portfolio_diagnosis(portfolio_metrics: dict) -> dict:
    """Generate fallback portfolio diagnosis when Claude is unavailable."""
    agg = portfolio_metrics["aggregate"]

    # Use revenue efficiency if available, else fall back to occupancy-based scoring
    portfolio_score = agg.get("portfolio_revenue_efficiency", 0)
    if portfolio_score == 0:
        occ = agg.get("blended_occupancy", 0)
        if occ < 0.80:
            portfolio_score = 30
        elif occ < 0.85:
            portfolio_score = 45
        elif occ < 0.90:
            portfolio_score = 55
        elif occ < 0.95:
            portfolio_score = 70
        else:
            portfolio_score = 85

    property_assessments = []
    property_rankings = []
    for prop_name, pdata in portfolio_metrics["properties"].items():
        prop_occ_rate = 0
        prop_vacant = pdata.get("total_vacant", 0)
        prop_rev_eff = pdata.get("revenue_efficiency", 0)
        prop_gap = pdata.get("revenue_gap", 0)
        pm = pdata.get("portfolio_metrics", {})
        prop_occ_rate = pm.get("blended_occupancy", 0)

        prop_vacancy_cost = pdata.get("total_monthly_vacancy_cost", 0)

        # Use revenue efficiency for grade if available
        if prop_rev_eff >= 85:
            score, grade = int(prop_rev_eff), "OPTIMIZED"
        elif prop_rev_eff >= 70:
            score, grade = int(prop_rev_eff), "OPPORTUNITY"
        elif prop_rev_eff >= 55:
            score, grade = int(prop_rev_eff), "IMBALANCED"
        elif prop_rev_eff >= 40:
            score, grade = int(prop_rev_eff), "DISTRESSED"
        elif prop_rev_eff > 0:
            score, grade = int(prop_rev_eff), "CRISIS"
        else:
            # Fallback to occupancy-based
            if prop_occ_rate < 0.82:
                score, grade = 35, "CRISIS"
            elif prop_occ_rate < 0.90:
                score, grade = 55, "IMBALANCED"
            elif prop_occ_rate < 0.95:
                score, grade = 72, "OPPORTUNITY"
            else:
                score, grade = 85, "OPTIMIZED"

        property_assessments.append({
            "property_name": prop_name,
            "health_score": score,
            "grade": grade,
            "key_findings": [
                f"{prop_vacant} vacant units, {prop_occ_rate:.0%} occupancy",
                f"Revenue gap: ${prop_gap:,.0f}/mo",
                f"Revenue efficiency: {prop_rev_eff:.0f}%",
            ],
            "recommended_actions": [],
        })
        property_rankings.append({
            "property": prop_name,
            "score": score,
            "grade": grade,
            "revenue_gap": prop_gap,
        })

    property_rankings.sort(key=lambda x: x["score"])

    total_gap = agg.get("total_revenue_gap", 0)
    total_renewal = agg.get("total_renewal_opportunity", 0)
    prop_count = len(portfolio_metrics["properties"])

    return {
        "cross_property_assessment": {
            "summary": f"Portfolio has {agg.get('total_vacant', 0)} vacant units across {prop_count} properties. Revenue gap: ${total_gap:,.0f}/mo.",
            "portfolio_score": portfolio_score,
            "property_rankings": property_rankings,
            "cross_property_patterns": [],
            "top_3_priorities": [
                f"Total revenue gap: ${total_gap:,.0f}/mo",
                f"Renewal opportunity: ${total_renewal:,.0f}/yr",
                f"Blended occupancy: {agg.get('blended_occupancy', 0):.0%}",
            ],
        },
        "property_assessments": property_assessments,
    }


def _fallback_portfolio_action_plan(portfolio_metrics: dict) -> dict:
    """Generate fallback portfolio action plan when Claude is unavailable."""
    agg = portfolio_metrics["aggregate"]
    return {
        "phases": [
            {"phase_number": 1, "name": "Priority Actions", "days": "1-3", "actions": []},
            {"phase_number": 2, "name": "Calibration", "days": "4-14", "actions": []},
            {"phase_number": 3, "name": "Decision Point", "days": "15-21", "actions": []},
            {"phase_number": 4, "name": "Optimization", "days": "22-30", "actions": []},
        ],
        "revenue_impact_summary": {
            "total_revenue_gap_monthly": agg.get("total_revenue_gap", 0),
            "total_renewal_opportunity": agg.get("total_renewal_opportunity", 0),
            "portfolio_revenue_efficiency": agg.get("portfolio_revenue_efficiency", 0),
            "total_monthly_vacancy_cost": agg.get("total_monthly_vacancy_cost", 0),
        },
    }
