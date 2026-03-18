"""Portfolio narrative service — generates portfolio-level slide narrative text.

Two Claude calls:
1. Portfolio diagnostic narrative (portfolio overview, property analysis)
2. Portfolio action plan narrative (phased plan across properties)

Fallback: template-based narratives when Claude is unavailable.
"""
import json
import logging

from app.services.claude_client import ClaudeClient, ClaudeAPIError

logger = logging.getLogger(__name__)

PORTFOLIO_DIAGNOSTIC_NARRATIVE_PROMPT = """You are a senior portfolio strategist presenting a multi-property pricing diagnostic to a client VP of Operations.

INPUT CONTEXT:
- Portfolio revenue efficiency score and grade (5-zone: CRISIS/DISTRESSED/IMBALANCED/OPPORTUNITY/OPTIMIZED).
- Per-property revenue efficiency, revenue gap, and renewal opportunity.
- Properties ranked by revenue gap (largest first).

STYLE RULES:
- Address the client directly: "Your portfolio..." not "The portfolio..."
- Confident, specific, data-driven. No hedging.
- Plain text only. NO markdown formatting.
- Every dollar amount must come from the provided data. Do NOT invent numbers.
- Reference revenue efficiency grades, not just occupancy or vacancy.
- Quantify everything using gap decomposition and renewal capture amounts.
- Max 4 sentences per narrative block.

Output ONLY valid JSON with this schema:
{
  "slide_2_headline": "string (max 20 words, portfolio verdict referencing worst property grade)",
  "slide_2_findings": ["string", "string", "string"],
  "slide_4_narrative": "string (property ranking analysis — by revenue efficiency)",
  "slide_6_narrative": "string (revenue at risk — gap waterfall interpretation)",
  "slide_15_narrative": "string (portfolio revenue roadmap — per-lever capture amounts)"
}"""

PORTFOLIO_ACTION_NARRATIVE_PROMPT = """You are a senior portfolio strategist presenting a 30-day cross-property action plan.

INPUT CONTEXT:
- Portfolio action plan with phased actions across properties.
- Revenue impact summary with total gap and projected capture.
- Actions ranked by revenue impact (largest first).

STYLE RULES:
- Address the client directly.
- Frame actions by revenue lever: FILL, REPRICE, RENEW, DE_CONCESSION.
- Reference dollar amounts from the pre-computed data.
- Plain text only. NO markdown formatting.
- Max 4 sentences per narrative block.

Output ONLY valid JSON with this schema:
{
  "slide_8_narrative": "string (action plan overview: total capturable revenue + phase structure)",
  "slide_9_narrative": "string (Phase 1 detail: which properties, which levers)"
}"""


def generate_portfolio_narratives(
    cross_property_data: dict,
    diagnosis: dict,
    action_plan: dict,
    claude_client: ClaudeClient | None = None,
) -> tuple[dict, bool]:
    """Generate portfolio-level per-slide narratives via Claude, with fallback.

    Args:
        cross_property_data: output of aggregate_cross_property().
        diagnosis: portfolio diagnosis dict.
        action_plan: portfolio action plan dict.
        claude_client: optional client for testing.

    Returns:
        Tuple of (narratives_dict, is_fallback).
    """
    if claude_client is None:
        claude_client = ClaudeClient()

    try:
        diag_user_msg = json.dumps({
            "diagnosis": diagnosis,
            "aggregate": cross_property_data.get("aggregate", {}),
            "property_ranking": cross_property_data.get("property_ranking", []),
        }, indent=2)

        diag_narratives = claude_client.call_json(
            PORTFOLIO_DIAGNOSTIC_NARRATIVE_PROMPT, diag_user_msg,
        )

        action_user_msg = json.dumps({
            "action_plan": action_plan,
            "aggregate": cross_property_data.get("aggregate", {}),
        }, indent=2)

        action_narratives = claude_client.call_json(
            PORTFOLIO_ACTION_NARRATIVE_PROMPT, action_user_msg,
        )

        narratives = {**diag_narratives, **action_narratives}
        return narratives, False

    except (ClaudeAPIError, Exception) as e:
        logger.warning("Portfolio narrative generation failed, using fallback: %s", e)
        return _generate_fallback_portfolio_narratives(
            cross_property_data, diagnosis, action_plan,
        ), True


def _generate_fallback_portfolio_narratives(
    cross_property_data: dict,
    diagnosis: dict,
    action_plan: dict,
) -> dict:
    """Generate template-based fallback narratives for portfolio slides.

    References revenue efficiency, gap decomposition, and renewal capture
    when available. Falls back to vacancy-only language otherwise.
    """
    narratives = {}

    aggregate = cross_property_data.get("aggregate", {})
    properties = cross_property_data.get("properties", {})
    ranking = cross_property_data.get("property_ranking", [])

    total_gap = aggregate.get("total_revenue_gap", 0)
    total_renewal = aggregate.get("total_renewal_opportunity", 0)
    rev_efficiency = aggregate.get("portfolio_revenue_efficiency", 0)
    total_vacant = aggregate.get("total_vacant", 0)
    total_vacancy_cost = aggregate.get("total_monthly_vacancy_cost", 0)

    # Determine worst property grade
    worst_grade = "OPTIMIZED"
    worst_property = ""
    grade_order = {"CRISIS": 0, "DISTRESSED": 1, "IMBALANCED": 2, "OPPORTUNITY": 3, "OPTIMIZED": 4}

    for pa in diagnosis.get("property_assessments", []):
        g = pa.get("grade", "OPTIMIZED")
        if grade_order.get(g, 4) < grade_order.get(worst_grade, 4):
            worst_grade = g
            worst_property = pa.get("property_name", "")

    # Slide 2: headline
    if total_gap > 0:
        narratives["slide_2_headline"] = (
            f"Your portfolio has ${total_gap:,.0f}/mo in capturable revenue "
            f"at {rev_efficiency:.1f}% efficiency."
        )
    else:
        narratives["slide_2_headline"] = (
            f"Your portfolio has {total_vacant} vacant units costing "
            f"${total_vacancy_cost:,.0f}/mo."
        )

    # Slide 2: findings from top properties by gap
    findings = []
    sorted_by_gap = sorted(
        properties.items(),
        key=lambda item: item[1].get("revenue_gap", 0),
        reverse=True,
    )
    for prop_key, prop_data in sorted_by_gap[:3]:
        gap = prop_data.get("revenue_gap", 0)
        eff = prop_data.get("revenue_efficiency", 0)
        name = prop_data.get("property_name", prop_key)
        if gap > 0:
            findings.append(f"{name}: ${gap:,.0f}/mo gap at {eff:.1f}% efficiency")
        else:
            findings.append(f"{name}: {eff:.1f}% revenue efficiency")
    while len(findings) < 3:
        findings.append(f"Portfolio total: ${total_vacancy_cost:,.0f}/mo vacancy cost")
    narratives["slide_2_findings"] = findings[:3]

    # Slide 4: property ranking analysis
    if ranking:
        worst = ranking[0]
        narratives["slide_4_narrative"] = (
            f"Properties ranked by revenue efficiency. "
            f"{worst.get('property_name', '')} is the lowest at "
            f"{worst.get('revenue_efficiency', 0):.1f}% with "
            f"${worst.get('revenue_gap', 0):,.0f}/mo in revenue gap."
        )
    else:
        narratives["slide_4_narrative"] = "No property ranking data available."

    # Slide 6: revenue at risk
    if total_gap > 0:
        narratives["slide_6_narrative"] = (
            f"Your portfolio has ${total_gap:,.0f}/mo in total revenue gap "
            f"with ${total_vacancy_cost:,.0f}/mo in vacancy costs alone. "
            f"Revenue efficiency sits at {rev_efficiency:.1f}%."
        )
    else:
        narratives["slide_6_narrative"] = (
            f"Your portfolio vacancy costs total ${total_vacancy_cost:,.0f}/mo "
            f"across {total_vacant} vacant units."
        )

    # Slide 8: action plan overview
    if worst_grade in ("CRISIS", "DISTRESSED"):
        narratives["slide_8_narrative"] = (
            f"The 30-day plan prioritizes filling vacancies at {worst_property} first, "
            f"then optimizing pricing across the portfolio."
        )
    elif worst_grade == "IMBALANCED":
        narratives["slide_8_narrative"] = (
            "The 30-day plan targets quick pricing wins across properties, "
            "then uses experiments and renewals to close remaining gaps."
        )
    else:
        narratives["slide_8_narrative"] = (
            "The 30-day plan captures renewal revenue and tests upward pricing "
            "across the portfolio while maintaining strong occupancy."
        )

    # Slide 9: Phase 1 detail
    narratives["slide_9_narrative"] = (
        "Phase 1 focuses on the highest-impact actions at the properties "
        "with the largest revenue gaps."
    )

    # Slide 15: revenue roadmap
    if total_gap > 0 or total_renewal > 0:
        narratives["slide_15_narrative"] = (
            f"Your portfolio has ${total_gap:,.0f}/mo in gap to close "
            f"and ${total_renewal:,.0f}/yr in renewal capture opportunity. "
            f"Activating FILL, REPRICE, RENEW, and DE_CONCESSION levers "
            f"across properties will move efficiency from {rev_efficiency:.1f}% toward the frontier."
        )
    else:
        narratives["slide_15_narrative"] = (
            f"Your portfolio is operating at {rev_efficiency:.1f}% efficiency. "
            f"Continued monitoring and seasonal adjustments will maintain performance."
        )

    return narratives
