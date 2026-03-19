"""Portfolio narrative service — generates per-slide narrative text for portfolio diagnostics.

Two Claude calls: diagnostic narrative + action plan narrative.
Fallback: template-based narratives.
"""
import json
import logging

from app.services.claude_client import ClaudeClient, ClaudeAPIError

logger = logging.getLogger(__name__)

PORTFOLIO_DIAGNOSTIC_NARRATIVE_PROMPT = """You are a senior revenue management consultant presenting a portfolio-level pricing diagnostic to a client VP of Operations.

TONE RULES (mandatory):
- Use professional consulting tone. Be direct and specific but not alarmist.
- NEVER use hedging language
- NEVER use alarmist language — no "hemorrhaging", "crisis", "bleeding", "critical", "dire", "catastrophic"
- Use "below target", "needs attention", "underperforming" instead
- ALWAYS use direct statements with dollar amounts
- Address the client directly: "Your portfolio..."
- Active voice only
- Max 4 sentences per narrative block
- Plain text only — NO markdown

REVENUE METRICS TO REFERENCE:
- Revenue efficiency scores and grades (0-39 NEEDS ATTENTION, 40-54 UNDERPERFORMING, 55-69 ADJUSTING, 70-84 OPPORTUNITY, 85-100 OPTIMIZED)
- Revenue gap decomposition (vacancy cost, new lease underpricing, in-place underpricing, renewal opportunity, concession drag)
- Frame revenue gap as "capture opportunity" not "loss"

Output ONLY valid JSON:
{
  "slide_2_headline": "string (portfolio verdict referencing revenue gap as opportunity, max 20 words)",
  "slide_2_findings": ["string", "string", "string"],
  "slide_3_narrative": "string (property comparison insights including revenue efficiency)",
  "slide_4_narrative": "string (ranking analysis referencing revenue efficiency scores)",
  "slide_5_narrative": "string (trend analysis)",
  "slide_6_narrative": "string (revenue at risk — frame as capture opportunity, include revenue gap)",
  "slide_14_narrative": "string (investigation priorities)",
  "slide_15_summary": "string (portfolio call to action with revenue gap and efficiency)"
}"""

PORTFOLIO_ACTION_NARRATIVE_PROMPT = """You are a senior revenue management consultant presenting a 30-day portfolio-wide action plan.

TONE RULES (mandatory):
- Use professional consulting tone. Be direct and specific but not alarmist.
- NEVER use alarmist language — no "hemorrhaging", "crisis", "bleeding", "critical"
- Direct language with dollar amounts
- Actions specify property and unit type
- Frame actions in terms of revenue capture opportunity
- Plain text only — NO markdown
- Max 4 sentences per block

Output ONLY valid JSON:
{
  "slide_11_narrative": "string (action plan overview referencing revenue gap opportunity)",
  "slide_12_narrative": "string (Phase 1 detail)",
  "slide_13_narrative": "string (Day 15 decision logic)"
}"""


def generate_portfolio_narratives(
    diagnosis: dict,
    action_plan: dict,
    metrics: dict,
    claude_client: ClaudeClient | None = None,
) -> tuple[dict, bool]:
    """Generate per-slide narratives for portfolio diagnostic.

    Args:
        diagnosis: portfolio diagnosis JSON.
        action_plan: portfolio action plan JSON.
        metrics: portfolio aggregate metrics.
        claude_client: optional client for testing.

    Returns:
        Tuple of (narratives_dict, is_fallback).
    """
    if claude_client is None:
        claude_client = ClaudeClient()

    try:
        diag_msg = json.dumps(
            {
                "diagnosis": diagnosis,
                "aggregate": metrics.get("aggregate", {}),
            },
            indent=2,
        )
        diag_narratives = claude_client.call_json(
            PORTFOLIO_DIAGNOSTIC_NARRATIVE_PROMPT, diag_msg
        )

        action_msg = json.dumps(
            {
                "action_plan": action_plan,
                "diagnosis_summary": diagnosis.get("cross_property_assessment", {}),
            },
            indent=2,
        )
        action_narratives = claude_client.call_json(
            PORTFOLIO_ACTION_NARRATIVE_PROMPT, action_msg
        )

        return {**diag_narratives, **action_narratives}, False

    except (ClaudeAPIError, Exception) as e:
        logger.warning("Portfolio narrative generation failed, using fallback: %s", e)
        return _generate_fallback_narratives(diagnosis, action_plan, metrics), True


def _generate_fallback_narratives(
    diagnosis: dict,
    action_plan: dict,
    metrics: dict,
) -> dict:
    """Template-based fallback narratives for portfolio slides."""
    agg = metrics.get("aggregate", {})
    properties = metrics.get("properties", {})
    property_ranking = metrics.get("property_ranking", [])

    total_units = agg.get("total_units", 0)
    total_vacant = agg.get("total_vacant", 0)
    total_monthly_vacancy = agg.get("total_monthly_vacancy_cost", 0)
    total_daily = round(total_monthly_vacancy / 30, 2) if total_monthly_vacancy else 0
    total_revenue_gap = agg.get("total_revenue_gap", 0)
    rev_efficiency = agg.get("portfolio_revenue_efficiency", 0)
    prop_count = len(properties)

    # Determine worst property from ranking (sorted worst-first)
    worst = property_ranking[0].get("property_name", "") if property_ranking else ""

    # Revenue efficiency grade
    if rev_efficiency >= 85:
        grade = "OPTIMIZED"
    elif rev_efficiency >= 70:
        grade = "OPPORTUNITY"
    elif rev_efficiency >= 55:
        grade = "ADJUSTING"
    elif rev_efficiency >= 40:
        grade = "UNDERPERFORMING"
    else:
        grade = "NEEDS ATTENTION"

    # Per-property efficiency summaries for findings
    prop_findings = []
    for r in property_ranking:
        pname = r.get("property_name", "")
        peff = r.get("revenue_efficiency", 0)
        pgap = r.get("revenue_gap", 0)
        prop_findings.append(
            f"{pname}: {peff:.0f}% revenue efficiency, ${pgap:,.0f}/mo gap"
        )

    return {
        "slide_2_headline": (
            f"Your portfolio has a ${total_revenue_gap:,.0f}/month "
            f"revenue capture opportunity across {prop_count} properties."
        ),
        "slide_2_findings": [
            (
                f"Portfolio revenue efficiency is {rev_efficiency:.0f}% ({grade}) "
                f"across {total_units} units"
            ),
            f"${total_revenue_gap:,.0f}/mo total revenue gap with ${total_monthly_vacancy:,.0f}/mo vacancy cost",
        ] + prop_findings[:1],
        "slide_3_narrative": (
            f"Your portfolio spans {prop_count} properties with "
            f"{total_units} total units and {total_vacant} vacancies. "
            f"Revenue efficiency is {rev_efficiency:.0f}% with a "
            f"${total_revenue_gap:,.0f}/mo capture opportunity."
        ),
        "slide_4_narrative": (
            f"{worst} has the lowest revenue efficiency in the portfolio. "
            f"Addressing pricing alignment and vacancy there will have the "
            f"highest impact on closing the ${total_revenue_gap:,.0f}/mo gap."
        ),
        "slide_5_narrative": (
            "Occupancy trends across your portfolio show diverging trajectories. "
            "Focus on properties with declining occupancy before spring leasing season."
        ),
        "slide_6_narrative": (
            f"Your portfolio has ${total_revenue_gap:,.0f}/mo in revenue gap "
            f"and ${total_monthly_vacancy:,.0f}/mo in vacancy cost. "
            f"{worst} accounts for the largest share of the opportunity."
        ),
        "slide_11_narrative": (
            f"This plan targets the ${total_revenue_gap:,.0f}/mo revenue gap with "
            f"phased actions across all {prop_count} properties, prioritized by "
            "revenue efficiency impact."
        ),
        "slide_12_narrative": (
            "Day 1: Address the lowest-efficiency property first with pricing "
            "adjustments where confidence is high, experiments where it is not."
        ),
        "slide_13_narrative": (
            "Day 15: Evaluate results property by property. Lock winning "
            "strategies, escalate or pivot where experiments did not converge."
        ),
        "slide_14_narrative": (
            "Several areas require cross-property investigation — pricing alignment, "
            "lease velocity, and renewal conversion rates."
        ),
        "slide_15_summary": (
            f"Your portfolio scores {rev_efficiency:.0f}% revenue efficiency "
            f"with a ${total_revenue_gap:,.0f}/mo capture opportunity. "
            f"The 30-day plan targets coordinated action across {prop_count} properties."
        ),
    }
