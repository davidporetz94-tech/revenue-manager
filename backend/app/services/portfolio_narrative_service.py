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
- NEVER use hedging language
- ALWAYS use direct statements with dollar amounts
- Address the client directly: "Your portfolio..."
- Active voice only
- Max 4 sentences per narrative block
- Plain text only — NO markdown

Output ONLY valid JSON:
{
  "slide_2_headline": "string (portfolio verdict, max 20 words)",
  "slide_2_findings": ["string", "string", "string"],
  "slide_3_narrative": "string (property comparison insights)",
  "slide_4_narrative": "string (ranking analysis)",
  "slide_5_narrative": "string (trend analysis)",
  "slide_6_narrative": "string (revenue at risk urgency)",
  "slide_14_narrative": "string (investigation priorities)",
  "slide_15_summary": "string (portfolio call to action)"
}"""

PORTFOLIO_ACTION_NARRATIVE_PROMPT = """You are a senior revenue management consultant presenting a 30-day portfolio-wide action plan.

TONE RULES (mandatory):
- Direct language with dollar amounts
- Actions specify property and unit type
- Plain text only — NO markdown
- Max 4 sentences per block

Output ONLY valid JSON:
{
  "slide_11_narrative": "string (action plan overview)",
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
    total_vacant = agg.get("total_vacant", 0)
    total_daily = agg.get("total_daily_burn", 0)
    total_monthly = agg.get("total_monthly_cost", 0)
    prop_count = agg.get("property_count", 0)
    worst = agg.get("worst_property", "")

    return {
        "slide_2_headline": (
            f"Your {prop_count}-property portfolio has {total_vacant} "
            f"vacant units burning ${total_daily:,.0f} per day."
        ),
        "slide_2_findings": [
            f"{total_vacant} total vacant units across {prop_count} properties",
            f"${total_monthly:,.0f} monthly vacancy cost",
            (
                f"{worst} requires immediate attention"
                if worst
                else "Review all properties"
            ),
        ],
        "slide_3_narrative": (
            f"Your portfolio spans {prop_count} properties with "
            f"{agg.get('total_units', 0)} total units. Daily burn of "
            f"${total_daily:,.0f} is concentrated in {worst}."
        ),
        "slide_4_narrative": (
            f"{worst} ranks lowest in portfolio health. Address its vacancy "
            f"first to reduce the largest share of your ${total_daily:,.0f}/day burn."
        ),
        "slide_5_narrative": (
            "Occupancy trends across your portfolio show diverging trajectories. "
            "Focus on properties with declining occupancy before spring leasing season."
        ),
        "slide_6_narrative": (
            f"Your portfolio is burning ${total_daily:,.0f} per day — "
            f"${total_monthly:,.0f} per month. {worst} accounts for the largest share."
        ),
        "slide_11_narrative": (
            f"This plan targets your ${total_daily:,.0f}/day portfolio burn with "
            f"phased actions across all {prop_count} properties, prioritized by "
            "daily burn impact."
        ),
        "slide_12_narrative": (
            "Day 1: Address the highest-burn property first with direct price "
            "cuts where confidence is high, experiments where it's not."
        ),
        "slide_13_narrative": (
            "Day 15: Evaluate results property by property. Lock winning "
            "strategies, escalate or pivot where experiments didn't converge."
        ),
        "slide_14_narrative": (
            "Several areas require cross-property investigation — unit condition, "
            "listing quality, and tour conversion rates."
        ),
        "slide_15_summary": (
            f"Your portfolio requires coordinated action across {prop_count} "
            f"properties. The 30-day plan targets "
            f"${int(total_monthly * 0.3):,.0f} monthly savings."
        ),
    }
