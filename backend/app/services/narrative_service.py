"""Narrative service — generates per-slide narrative text via Claude API.

Two Claude calls:
1. Diagnostic narrative (slides 2-7, 11-12)
2. Action plan narrative (slides 8-10)

Fallback: template-based narratives when Claude is unavailable.
"""
import json
import logging
import re

from app.services.claude_client import ClaudeClient, ClaudeAPIError

logger = logging.getLogger(__name__)

DIAGNOSTIC_NARRATIVE_PROMPT = """You are a senior revenue management consultant presenting to a client VP of Operations. Generate narrative text for each slide of a pricing diagnostic presentation.

STYLE RULES:
- Address the client directly: "Your B1 units..." not "The B1 units..."
- Confident, specific, data-driven. No hedging.
- Plain text only — NO markdown formatting (no **bold**, no ## headers)
- Every dollar amount must come from the provided metrics. Do NOT invent numbers.
- Max 4 sentences per narrative block.
- Max 25 words per bullet point.

Output ONLY valid JSON with this schema:
{
  "slide_2_headline": "string (max 20 words, clear verdict)",
  "slide_2_findings": ["string", "string", "string"],
  "slide_4_narrative": "string (Property A analysis)",
  "slide_5_narrative": "string (Property B analysis, emphasize crisis)",
  "slide_6_narrative": "string (trend analysis insights)",
  "slide_7_narrative": "string (revenue at risk urgency)",
  "slide_11_narrative": "string (investigation priorities)",
  "slide_12_summary": "string (key takeaway and call to action)"
}"""

ACTION_NARRATIVE_PROMPT = """You are a senior revenue management consultant presenting a 30-day action plan to a client VP of Operations.

STYLE RULES:
- Address the client directly
- Use plain language: "If 2 of your 3 test units lease..." not "convergence criterion met"
- Explain WHY each action is recommended, not just WHAT
- Plain text only — NO markdown formatting
- Max 4 sentences per narrative block

Output ONLY valid JSON with this schema:
{
  "slide_8_narrative": "string (action plan overview and rationale)",
  "slide_9_narrative": "string (Phase 1 detail — what happens in first 3 days)",
  "slide_10_narrative": "string (Day 15 decision logic in plain language)"
}"""


def generate_narratives(
    diagnosis: dict,
    action_plan: dict,
    metrics: dict,
    claude_client: ClaudeClient | None = None,
) -> tuple[dict, bool]:
    """Generate per-slide narratives via Claude, with fallback.

    Args:
        diagnosis: diagnosis_json from diagnostic run.
        action_plan: action_plan_json from diagnostic run.
        metrics: metrics_json from diagnostic run.
        claude_client: optional client for testing.

    Returns:
        Tuple of (narratives_dict, is_fallback).
    """
    if claude_client is None:
        claude_client = ClaudeClient()

    try:
        # Call 1: Diagnostic narrative
        diag_user_msg = json.dumps({
            "diagnosis": diagnosis,
            "metrics_summary": _summarize_metrics(metrics),
        }, indent=2)

        diag_narratives = claude_client.call_json(
            DIAGNOSTIC_NARRATIVE_PROMPT, diag_user_msg
        )

        # Call 2: Action plan narrative
        action_user_msg = json.dumps({
            "action_plan": action_plan,
            "diagnosis_summary": _summarize_diagnosis(diagnosis),
        }, indent=2)

        action_narratives = claude_client.call_json(
            ACTION_NARRATIVE_PROMPT, action_user_msg
        )

        # Merge
        narratives = {**diag_narratives, **action_narratives}
        return narratives, False

    except (ClaudeAPIError, Exception) as e:
        logger.warning("Narrative generation failed, using fallback: %s", e)
        return _generate_fallback_narratives(diagnosis, action_plan, metrics), True


def validate_narrative_consistency(narratives: dict, metrics: dict) -> list[dict]:
    """Check that dollar amounts in narrative match known metrics.

    Returns list of inconsistencies found.
    """
    issues = []
    known_amounts = _extract_known_amounts(metrics)

    for key, text in narratives.items():
        if not isinstance(text, str):
            continue
        # Extract dollar amounts from narrative
        dollar_matches = re.findall(r'\$[\d,]+', text)
        for match in dollar_matches:
            amount = int(match.replace('$', '').replace(',', ''))
            if amount not in known_amounts and amount > 100:
                issues.append({
                    "slide": key,
                    "amount": match,
                    "status": "unverified",
                })

    return issues


def _summarize_metrics(metrics: dict) -> dict:
    """Create a concise metrics summary for the Claude prompt."""
    summary = {}
    for code, m in metrics.get("unit_type_metrics", {}).items():
        summary[code] = {
            "occupancy": m["occupancy_metrics"]["occupancy_rate"],
            "vacant": m["occupancy_metrics"]["vacant"],
            "exposure": m["exposure_metrics"]["total_exposure_pct"],
            "asking": m["pricing_spreads"]["asking_rent"],
            "comps": m["pricing_spreads"]["comps_rent"],
            "asking_vs_comps": m["pricing_spreads"]["asking_vs_comps_dollars"],
            "daily_burn": m["revenue_metrics"]["daily_vacancy_burn"],
            "monthly_cost": m["revenue_metrics"]["monthly_vacancy_cost"],
        }
    portfolio = metrics.get("portfolio_metrics", {})
    summary["portfolio"] = {
        "total_units": portfolio.get("total_units", 0),
        "total_vacant": portfolio.get("total_vacant", 0),
        "total_monthly_cost": portfolio.get("total_monthly_vacancy_cost", 0),
    }
    return summary


def _summarize_diagnosis(diagnosis: dict) -> dict:
    """Create a concise diagnosis summary for the action plan narrative prompt."""
    if not diagnosis:
        return {}
    assessments = {}
    for a in diagnosis.get("unit_type_assessments", []):
        assessments[a["unit_type"]] = {
            "grade": a.get("grade"),
            "score": a.get("health_score"),
            "root_cause": a.get("root_cause"),
        }
    return assessments


def _extract_known_amounts(metrics: dict) -> set[int]:
    """Extract all known dollar amounts from metrics for consistency checking."""
    amounts = set()
    for code, m in metrics.get("unit_type_metrics", {}).items():
        p = m["pricing_spreads"]
        r = m["revenue_metrics"]
        for val in [p["asking_rent"], p["predicted_rent"], p["comps_rent"],
                    p["in_place_rent"], p["executed_rent"], p["base_rent"],
                    p["amenity_price"], abs(p["asking_vs_comps_dollars"]),
                    abs(p["asking_vs_predicted_dollars"]), abs(p["loss_to_lease_dollars"]),
                    r["daily_vacancy_burn"], r["monthly_vacancy_cost"],
                    r["revenue_at_risk_30d"]]:
            amounts.add(int(abs(val)))

    # Portfolio totals
    portfolio = metrics.get("portfolio_metrics", {})
    amounts.add(int(portfolio.get("total_monthly_vacancy_cost", 0)))

    # Total daily burn
    total_daily = sum(m["revenue_metrics"]["daily_vacancy_burn"] for m in metrics.get("unit_type_metrics", {}).values())
    amounts.add(int(total_daily))
    amounts.add(int(total_daily * 30))
    amounts.add(int(total_daily * 365))

    return amounts


def _generate_fallback_narratives(diagnosis: dict, action_plan: dict, metrics: dict) -> dict:
    """Generate template-based fallback narratives from metrics data."""
    narratives = {}

    # Metrics summary
    ut_metrics = metrics.get("unit_type_metrics", {})
    portfolio = metrics.get("portfolio_metrics", {})
    total_vacant = portfolio.get("total_vacant", 0)
    total_monthly = portfolio.get("total_monthly_vacancy_cost", 0)

    # Slide 2
    worst = portfolio.get("worst_performing_unit_type", "")
    narratives["slide_2_headline"] = f"Your portfolio has {total_vacant} vacant units costing ${total_monthly:,.0f} per month in lost revenue."
    narratives["slide_2_findings"] = [
        f"{total_vacant} total vacant units across the portfolio",
        f"${total_monthly:,.0f} monthly vacancy cost",
        f"{worst} is the worst-performing unit type" if worst else "Review needed",
    ]

    # Per-property narratives
    for prop_code, ut_codes in [("A", ["A1", "A2"]), ("B", ["B1", "B2"])]:
        slide_key = "slide_4_narrative" if prop_code == "A" else "slide_5_narrative"
        parts = []
        for code in ut_codes:
            m = ut_metrics.get(code)
            if not m:
                continue
            occ = m["occupancy_metrics"]["occupancy_rate"]
            vacant = m["occupancy_metrics"]["vacant"]
            exp = m["exposure_metrics"]["total_exposure_pct"]
            asking = m["pricing_spreads"]["asking_rent"]
            comps = m["pricing_spreads"]["comps_rent"]
            diff = asking - comps
            parts.append(
                f"Your {code} units have {occ:.0%} occupancy with {vacant} vacant units "
                f"and {exp:.0%} total exposure. Asking rent is ${asking:,.0f}, "
                f"{'$' + str(abs(diff)) + ' above' if diff > 0 else '$' + str(abs(diff)) + ' below'} "
                f"comp average of ${comps:,.0f}."
            )
        narratives[slide_key] = " ".join(parts)

    # Trend
    narratives["slide_6_narrative"] = "Review the 4-month trend data to identify occupancy and pricing trajectories for each unit type."

    # Revenue at risk
    total_daily = sum(m["revenue_metrics"]["daily_vacancy_burn"] for m in ut_metrics.values())
    narratives["slide_7_narrative"] = (
        f"Your portfolio is burning ${total_daily:,.0f} per day in vacancy costs, "
        f"totaling ${total_monthly:,.0f} per month. Immediate action on the highest-burn unit types will reduce this exposure."
    )

    # Action plan slides
    narratives["slide_8_narrative"] = "The 30-day action plan is structured in 4 phases with a Day 15 decision point to evaluate results and adjust strategy."
    narratives["slide_9_narrative"] = "Phase 1 focuses on immediate stabilization actions for the most critical unit types."
    narratives["slide_10_narrative"] = "At Day 15, evaluate experiment results and occupancy trends to determine next steps for each unit type."

    # Investigation
    narratives["slide_11_narrative"] = "Several areas require further investigation to confirm root causes and optimize the action plan."
    narratives["slide_12_summary"] = (
        f"Your portfolio requires immediate attention on {total_vacant} vacant units. "
        f"The 30-day plan targets a ${int(total_monthly * 0.3):,.0f} monthly savings through pricing adjustments and experiments."
    )

    return narratives
