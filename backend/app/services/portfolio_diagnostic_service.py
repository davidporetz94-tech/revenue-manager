"""Portfolio diagnostic service — orchestrates cross-property diagnosis.

Aggregates per-property diagnostics into a portfolio-level view with
revenue efficiency scoring, gap decomposition, and property ranking.
"""
import json
import logging

from app.services.claude_client import ClaudeClient, ClaudeAPIError
from app.engine.utils import safe_divide

logger = logging.getLogger(__name__)

PORTFOLIO_DIAGNOSIS_SYSTEM_PROMPT = """You are a senior multifamily portfolio strategist analyzing revenue performance across multiple properties. You receive aggregated revenue metrics, per-property revenue efficiency scores, and gap decompositions from a pricing engine.

INPUT DATA YOU RECEIVE:
- `aggregate`: portfolio-level totals including total_revenue_gap, portfolio_revenue_efficiency, total_renewal_opportunity.
- `properties`: per-property revenue efficiency, revenue gap, renewal opportunity, unit-type detail.
- `property_ranking`: properties ranked by revenue efficiency (worst first).

Produce a JSON portfolio diagnosis with:
1. Portfolio revenue efficiency score from the pre-computed `aggregate.portfolio_revenue_efficiency`.
2. Grade using the 5-zone system:
   - CRISIS (0-39): Multiple properties with dominant vacancy
   - DISTRESSED (40-54): Portfolio-wide pricing/vacancy pressure
   - IMBALANCED (55-69): Some properties dragging performance
   - OPPORTUNITY (70-84): Generally healthy, pricing upside exists
   - OPTIMIZED (85-100): Operating near the revenue frontier
3. Per-property assessments ranked by revenue gap (largest first).
4. Cross-property risks (cannibalization, submarket competition).
5. Top 3 priorities with dollar amounts from pre-computed gaps.

CRITICAL RULES:
- USE the pre-computed portfolio_revenue_efficiency score. Do NOT recalculate.
- Every dollar amount must come from the pre-computed facts provided.
- Rank properties by revenue gap (largest gap = highest priority).
- Identify cross-property risks (e.g., cutting rents at one property may pull comps down for another).

Output ONLY valid JSON matching this schema:
{
  "portfolio_score": "float (from aggregate.portfolio_revenue_efficiency)",
  "portfolio_grade": "OPTIMIZED|OPPORTUNITY|IMBALANCED|DISTRESSED|CRISIS",
  "portfolio_summary": "string",
  "property_assessments": [{
    "property_key": "string",
    "property_name": "string",
    "revenue_efficiency": "float",
    "revenue_gap": "float",
    "grade": "string",
    "dominant_issues": ["string"],
    "recommended_focus": "string"
  }],
  "cross_property_risks": ["string"],
  "top_3_priorities": [{
    "property": "string",
    "action": "string",
    "monthly_impact": "float"
  }],
  "portfolio_renewal_opportunity": {
    "total_annual": "float",
    "by_property": [{"property": "string", "annual_capture": "float"}]
  }
}"""

PORTFOLIO_ACTION_PLAN_SYSTEM_PROMPT = """You are a senior multifamily portfolio strategist. Given a portfolio diagnosis with revenue efficiency grades, revenue gap decompositions, and property rankings, produce a 30-day phased action plan ranked by revenue impact across properties.

PHASE STRUCTURE ADAPTS TO THE WORST PROPERTY GRADE:

CRISIS/DISTRESSED (score < 55):
- Phase 1 (Days 1-3): Triage worst properties — reduce asking, offer concessions
- Phase 2 (Days 4-14): Stabilize across portfolio, monitor velocity
- Phase 3 (Days 15-21): Evaluate fill progress, begin optimization at healthier properties
- Phase 4 (Days 22-30): Lock strategies, shift focus to renewals

IMBALANCED (score 55-69):
- Phase 1 (Days 1-3): Quick wins across properties — reprice, launch experiments
- Phase 2 (Days 4-14): Portfolio-wide experiment observation + renewal increases
- Phase 3 (Days 15-21): Converge experiments, cross-property evaluation
- Phase 4 (Days 22-30): Lock strategies, seasonal positioning

OPPORTUNITY/OPTIMIZED (score 70+):
- Phase 1 (Days 1-3): Implement renewal increases, remove concessions
- Phase 2 (Days 4-14): Test higher asking across properties
- Phase 3 (Days 15-21): Evaluate, seasonal positioning
- Phase 4 (Days 22-30): Maintain and monitor

CRITICAL RULES:
- All dollar amounts are pre-computed. Use them exactly.
- Actions ranked by revenue impact (largest gap properties first).
- Every action includes: property, lever, dollar impact, confidence, downside risk.
- Cross-property coordination: ensure repricing at one property does not undercut another.

Output ONLY valid JSON matching this schema:
{
  "phases": [{
    "phase_number": "int 1-4",
    "name": "string",
    "days": "string",
    "actions": [{
      "property": "string",
      "action_type": "string",
      "lever": "FILL|REPRICE|RENEW|DE_CONCESSION",
      "description": "string",
      "expected_impact_monthly": "float",
      "confidence": "HIGH|MEDIUM|LOW"
    }]
  }],
  "revenue_impact_summary": {
    "total_portfolio_gap_monthly": "float",
    "projected_capture_monthly": "float",
    "total_renewal_opportunity_annual": "float"
  }
}"""


def generate_portfolio_diagnosis(
    cross_property_data: dict,
    claude_client: ClaudeClient | None = None,
) -> tuple[dict, bool]:
    """Generate portfolio-level diagnosis via Claude, with fallback.

    Args:
        cross_property_data: output of aggregate_cross_property().
        claude_client: optional client for testing.

    Returns:
        Tuple of (diagnosis_dict, is_fallback).
    """
    if claude_client is None:
        claude_client = ClaudeClient()

    user_msg = json.dumps({
        "aggregate": cross_property_data.get("aggregate", {}),
        "properties": {
            k: {
                "property_name": v.get("property_name", k),
                "revenue_efficiency": v.get("revenue_efficiency", 0),
                "revenue_gap": v.get("revenue_gap", 0),
                "renewal_opportunity": v.get("renewal_opportunity", 0),
                "total_units": v.get("total_units", 0),
                "total_vacant": v.get("total_vacant", 0),
            }
            for k, v in cross_property_data.get("properties", {}).items()
        },
        "property_ranking": cross_property_data.get("property_ranking", []),
    }, indent=2)

    try:
        diagnosis = claude_client.call_json(
            PORTFOLIO_DIAGNOSIS_SYSTEM_PROMPT, user_msg,
        )
        return diagnosis, False
    except (ClaudeAPIError, Exception) as e:
        logger.warning("Portfolio diagnosis failed, using fallback: %s", e)
        return _fallback_portfolio_diagnosis(cross_property_data), True


def generate_portfolio_action_plan(
    cross_property_data: dict,
    diagnosis: dict,
    claude_client: ClaudeClient | None = None,
) -> tuple[dict, bool]:
    """Generate portfolio-level action plan via Claude, with fallback.

    Args:
        cross_property_data: output of aggregate_cross_property().
        diagnosis: portfolio diagnosis dict.
        claude_client: optional client for testing.

    Returns:
        Tuple of (action_plan_dict, is_fallback).
    """
    if claude_client is None:
        claude_client = ClaudeClient()

    user_msg = json.dumps({
        "diagnosis": diagnosis,
        "aggregate": cross_property_data.get("aggregate", {}),
        "property_ranking": cross_property_data.get("property_ranking", []),
    }, indent=2)

    try:
        plan = claude_client.call_json(
            PORTFOLIO_ACTION_PLAN_SYSTEM_PROMPT, user_msg,
        )
        return plan, False
    except (ClaudeAPIError, Exception) as e:
        logger.warning("Portfolio action plan failed, using fallback: %s", e)
        return _fallback_portfolio_action_plan(cross_property_data, diagnosis), True


def _score_to_grade(score: float) -> str:
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


def _fallback_portfolio_diagnosis(cross_property_data: dict) -> dict:
    """Generate fallback portfolio diagnosis from pre-computed data.

    Uses revenue gap decomposition to rank properties by gap (largest first).
    """
    aggregate = cross_property_data.get("aggregate", {})
    properties = cross_property_data.get("properties", {})
    ranking = cross_property_data.get("property_ranking", [])

    portfolio_score = aggregate.get("portfolio_revenue_efficiency", 0)
    portfolio_grade = _score_to_grade(portfolio_score)

    # Per-property assessments sorted by revenue gap descending
    property_assessments = []
    sorted_props = sorted(
        properties.items(),
        key=lambda item: item[1].get("revenue_gap", 0),
        reverse=True,
    )

    for prop_key, prop_data in sorted_props:
        rev_eff = prop_data.get("revenue_efficiency", 0)
        gap = prop_data.get("revenue_gap", 0)
        grade = _score_to_grade(rev_eff)

        issues = []
        if gap > 0:
            issues.append(f"${gap:,.0f}/mo revenue gap")
        vacancy_cost = prop_data.get("total_monthly_vacancy_cost", 0)
        if vacancy_cost > 0:
            issues.append(f"${vacancy_cost:,.0f}/mo vacancy cost")
        renewal = prop_data.get("renewal_opportunity", 0)
        if renewal > 0:
            issues.append(f"${renewal:,.0f}/yr renewal opportunity")

        property_assessments.append({
            "property_key": prop_key,
            "property_name": prop_data.get("property_name", prop_key),
            "revenue_efficiency": rev_eff,
            "revenue_gap": gap,
            "grade": grade,
            "dominant_issues": issues[:3],
            "recommended_focus": (
                "Fill vacancies" if grade in ("CRISIS", "DISTRESSED")
                else "Reprice and experiment" if grade == "IMBALANCED"
                else "Capture renewals and test upside" if grade == "OPPORTUNITY"
                else "Maintain and monitor"
            ),
        })

    # Top 3 priorities from ranked properties
    top_3 = []
    for prop in ranking[:3]:
        gap = prop.get("revenue_gap", 0)
        if gap > 0:
            top_3.append({
                "property": prop.get("property_name", prop.get("property_key", "")),
                "action": f"Close ${gap:,.0f}/mo revenue gap",
                "monthly_impact": gap,
            })

    # Renewal summary by property
    renewal_by_prop = []
    for prop_key, prop_data in properties.items():
        annual = prop_data.get("renewal_opportunity", 0)
        if annual > 0:
            renewal_by_prop.append({
                "property": prop_data.get("property_name", prop_key),
                "annual_capture": annual,
            })

    return {
        "portfolio_score": portfolio_score,
        "portfolio_grade": portfolio_grade,
        "portfolio_summary": (
            f"Fallback diagnosis. Portfolio revenue efficiency: {portfolio_score:.1f}% "
            f"({portfolio_grade}). Total gap: ${aggregate.get('total_revenue_gap', 0):,.0f}/mo."
        ),
        "property_assessments": property_assessments,
        "cross_property_risks": [],
        "top_3_priorities": top_3,
        "portfolio_renewal_opportunity": {
            "total_annual": aggregate.get("total_renewal_opportunity", 0),
            "by_property": renewal_by_prop,
        },
    }


def _fallback_portfolio_action_plan(
    cross_property_data: dict, diagnosis: dict,
) -> dict:
    """Generate fallback portfolio action plan from pre-computed data.

    Phase naming adapts to worst property grade in the diagnosis.
    """
    aggregate = cross_property_data.get("aggregate", {})

    # Determine worst grade
    grade_order = {"CRISIS": 0, "DISTRESSED": 1, "IMBALANCED": 2, "OPPORTUNITY": 3, "OPTIMIZED": 4}
    worst_grade = "OPTIMIZED"
    for pa in diagnosis.get("property_assessments", []):
        g = pa.get("grade", "OPTIMIZED")
        if grade_order.get(g, 4) < grade_order.get(worst_grade, 4):
            worst_grade = g

    phase_names = {
        "CRISIS": ["Triage Worst Properties", "Stabilize Portfolio", "Evaluate & Optimize", "Lock Strategy"],
        "DISTRESSED": ["Triage Worst Properties", "Stabilize Portfolio", "Evaluate & Optimize", "Lock Strategy"],
        "IMBALANCED": ["Quick Wins", "Experiment & Renew", "Converge", "Lock Strategy"],
        "OPPORTUNITY": ["Renewal Increases", "Test Higher Asking", "Seasonal Positioning", "Maintain"],
        "OPTIMIZED": ["Hold & Document", "Term Premium Tests", "Seasonal Positioning", "Maintain"],
    }
    names = phase_names.get(worst_grade, phase_names["IMBALANCED"])

    total_gap = aggregate.get("total_revenue_gap", 0)
    total_renewal = aggregate.get("total_renewal_opportunity", 0)

    return {
        "phases": [
            {"phase_number": 1, "name": names[0], "days": "1-3", "actions": []},
            {"phase_number": 2, "name": names[1], "days": "4-14", "actions": []},
            {"phase_number": 3, "name": names[2], "days": "15-21", "actions": []},
            {"phase_number": 4, "name": names[3], "days": "22-30", "actions": []},
        ],
        "revenue_impact_summary": {
            "total_portfolio_gap_monthly": total_gap,
            "projected_capture_monthly": total_gap * 0.5,
            "total_renewal_opportunity_annual": total_renewal,
        },
    }
