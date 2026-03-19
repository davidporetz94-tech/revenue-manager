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

INPUT CONTEXT:
- Each unit type has a revenue efficiency grade: OPTIMIZED, OPPORTUNITY, IMBALANCED, DISTRESSED, or CRISIS.
- Each unit type has a revenue gap decomposition showing gaps by lever: FILL, REPRICE, RENEW, DE_CONCESSION.
- Renewal capture opportunities are pre-computed with specific dollar amounts.
- Use these archetypes to frame your narrative:
  - HIGH OCC + UNDERPRICED: "push rents" — frame as upside capture opportunity
  - DECLINING OCC: "rebalance" — frame as pricing misalignment needing correction
  - CRISIS: "fill" — frame as vacancy that needs priority attention
  - PUZZLE (priced at comps but not leasing): "investigate + test" — frame as non-price friction

STYLE RULES:
- Professional consulting tone — direct, specific, never alarmist.
- Address the client directly: "Your B1 units..." not "The B1 units..."
- Confident, specific, data-driven. No hedging.
- Plain text only — NO markdown formatting (no **bold**, no ## headers)
- Every dollar amount must come from the provided metrics. Do NOT invent numbers.
- Reference revenue efficiency grades, not just occupancy numbers.
- Quantify recommendations using gap decomposition levers and dollar amounts.
- Max 4 sentences per narrative block.
- Max 25 words per bullet point.
- Avoid words like: hemorrhaging, bleeding, crisis, dire, desperate, catastrophic, freefall.
- Instead use: below target, needs attention, priority action, opportunity cost, underperforming.
- Frame gaps as capturable revenue, not losses.

Output ONLY valid JSON with this schema:
{
  "slide_2_headline": "string (max 20 words, clear verdict referencing worst grade)",
  "slide_2_findings": ["string", "string", "string"],
  "slide_4_narrative": "string (Property A analysis — grade + dominant lever + dollar impact)",
  "slide_5_narrative": "string (Property B analysis — grade + dominant lever + dollar impact)",
  "slide_6_narrative": "string (trend analysis — momentum dimension insights)",
  "slide_7_narrative": "string (revenue gap urgency — total gap with lever breakdown)",
  "slide_11_narrative": "string (investigation priorities — low-confidence areas)",
  "slide_12_summary": "string (key takeaway: total capturable revenue + top 2 actions)"
}"""

ACTION_NARRATIVE_PROMPT = """You are a senior revenue management consultant presenting a 30-day action plan to a client VP of Operations.

INPUT CONTEXT:
- The action plan phases adapt to the dominant grade: CRISIS units get "fill" phases, OPPORTUNITY units get "push rents" phases.
- Every action has a lever (FILL/REPRICE/RENEW/DE_CONCESSION), dollar impact, confidence, and downside risk.
- Renewal capture opportunities have specific dollar amounts and turnover risk estimates.

STYLE RULES:
- Professional consulting tone — direct, specific, never alarmist.
- Address the client directly
- Use plain language: "If 2 of your 3 test units lease..." not "convergence criterion met"
- Explain WHY each action is recommended using the revenue lever framework
- Reference dollar amounts from the revenue gap decomposition
- Frame renewals as a revenue capture opportunity, not just retention
- Plain text only — NO markdown formatting
- Max 4 sentences per narrative block
- Avoid words like: hemorrhaging, bleeding, crisis, dire, desperate, catastrophic, freefall.
- Frame actions as recommendations, not emergencies.

Output ONLY valid JSON with this schema:
{
  "slide_8_narrative": "string (action plan overview: total capturable revenue + phase structure rationale)",
  "slide_9_narrative": "string (Phase 1 detail: what happens in first 3 days, which levers activate)",
  "slide_10_narrative": "string (Day 15 decision logic: experiment results + renewal evaluation)"
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
        unit_summary = {
            "occupancy": m["occupancy_metrics"]["occupancy_rate"],
            "vacant": m["occupancy_metrics"]["vacant"],
            "exposure": m["exposure_metrics"]["total_exposure_pct"],
            "asking": m["pricing_spreads"]["asking_rent"],
            "comps": m["pricing_spreads"]["comps_rent"],
            "asking_vs_comps": m["pricing_spreads"]["asking_vs_comps_dollars"],
            "daily_burn": m["revenue_metrics"]["daily_vacancy_burn"],
            "monthly_cost": m["revenue_metrics"]["monthly_vacancy_cost"],
        }
        # Include revenue optimization data when available
        efficiency = m.get("revenue_efficiency", {})
        if efficiency:
            unit_summary["revenue_efficiency_grade"] = efficiency.get("grade")
            unit_summary["revenue_efficiency_score"] = efficiency.get("revenue_efficiency_score")

        gap = m.get("revenue_gap", {})
        if gap:
            unit_summary["revenue_gap_monthly"] = gap.get("total_gap_monthly", 0)
            unit_summary["dominant_lever"] = gap.get("dominant_lever")

        renewal = m.get("renewal_opportunity", {})
        if renewal:
            unit_summary["upcoming_renewals"] = renewal.get("upcoming_renewals_90d", 0)
            unit_summary["renewal_capture_monthly"] = renewal.get("net_monthly_capture", 0)

        summary[code] = unit_summary

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
            "dominant_lever": a.get("dominant_lever"),
            "revenue_gap_monthly": a.get("revenue_gap_monthly", 0),
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

        # Revenue gap amounts
        gap = m.get("revenue_gap", {})
        if gap:
            for val in [gap.get("total_gap_monthly", 0),
                        gap.get("current_monthly_revenue", 0),
                        gap.get("optimal_monthly_revenue", 0)]:
                if val:
                    amounts.add(int(abs(val)))
            for comp in gap.get("gap_components", {}).values():
                amt = comp.get("amount", 0)
                if amt:
                    amounts.add(int(abs(amt)))

        # Optimal pricing amounts
        opt = m.get("optimal_pricing", {})
        if opt:
            for val in [opt.get("optimal_asking", 0),
                        opt.get("recommended_asking", 0),
                        opt.get("revenue_gap_monthly", 0)]:
                if val:
                    amounts.add(int(abs(val)))

        # Renewal amounts
        renewal = m.get("renewal_opportunity", {})
        if renewal:
            for val in [renewal.get("net_monthly_capture", 0),
                        renewal.get("gross_annual_capture", 0),
                        renewal.get("recommended_increase_dollars", 0)]:
                if val:
                    amounts.add(int(abs(val)))

    # Portfolio totals
    portfolio = metrics.get("portfolio_metrics", {})
    amounts.add(int(portfolio.get("total_monthly_vacancy_cost", 0)))

    # Total daily burn
    total_daily = sum(m["revenue_metrics"]["daily_vacancy_burn"] for m in metrics.get("unit_type_metrics", {}).values())
    amounts.add(int(total_daily))
    amounts.add(int(total_daily * 30))
    amounts.add(int(total_daily * 365))

    # Total revenue gap
    total_gap = sum(
        m.get("revenue_gap", {}).get("total_gap_monthly", 0)
        for m in metrics.get("unit_type_metrics", {}).values()
    )
    if total_gap:
        amounts.add(int(abs(total_gap)))

    return amounts


def _generate_fallback_narratives(diagnosis: dict, action_plan: dict, metrics: dict) -> dict:
    """Generate template-based fallback narratives from metrics data.

    References revenue efficiency grades and gap decomposition levers
    when available, falling back to vacancy-only metrics otherwise.
    """
    narratives = {}

    # Metrics summary
    ut_metrics = metrics.get("unit_type_metrics", {})
    portfolio = metrics.get("portfolio_metrics", {})
    total_vacant = portfolio.get("total_vacant", 0)
    total_monthly = portfolio.get("total_monthly_vacancy_cost", 0)

    # Compute total revenue gap across all unit types
    total_gap = sum(
        m.get("revenue_gap", {}).get("total_gap_monthly", 0)
        for m in ut_metrics.values()
    )

    # Find worst grade
    worst_grade = "OPTIMIZED"
    worst_unit = ""
    grade_order = {"CRISIS": 0, "DISTRESSED": 1, "IMBALANCED": 2, "OPPORTUNITY": 3, "OPTIMIZED": 4}
    for code, m in ut_metrics.items():
        g = m.get("revenue_efficiency", {}).get("grade", "OPTIMIZED")
        if grade_order.get(g, 4) < grade_order.get(worst_grade, 4):
            worst_grade = g
            worst_unit = code

    # Slide 2
    if total_gap > 0:
        narratives["slide_2_headline"] = (
            f"Your portfolio has ${total_gap:,.0f} per month in capturable revenue "
            f"with {worst_unit} rated {worst_grade}."
        )
    else:
        narratives["slide_2_headline"] = (
            f"Your portfolio has {total_vacant} vacant units costing "
            f"${total_monthly:,.0f} per month in lost revenue."
        )

    # Build findings from top 3 unit types by gap
    sorted_by_gap = sorted(
        ut_metrics.items(),
        key=lambda item: item[1].get("revenue_gap", {}).get("total_gap_monthly", 0),
        reverse=True,
    )
    findings = []
    for code, m in sorted_by_gap[:3]:
        eff = m.get("revenue_efficiency", {})
        gap = m.get("revenue_gap", {})
        grade = eff.get("grade", "N/A")
        gap_monthly = gap.get("total_gap_monthly", 0)
        dominant = gap.get("dominant_lever", "FILL")
        if gap_monthly > 0:
            findings.append(f"{code} rated {grade}: ${gap_monthly:,.0f}/mo gap, dominant lever {dominant}")
        else:
            occ = m["occupancy_metrics"]["occupancy_rate"]
            findings.append(f"{code} rated {grade}: {occ:.0%} occupancy")

    # Pad to 3 if needed
    while len(findings) < 3:
        findings.append(f"${total_monthly:,.0f} monthly vacancy cost")

    narratives["slide_2_findings"] = findings[:3]

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
            asking = m["pricing_spreads"]["asking_rent"]
            comps = m["pricing_spreads"]["comps_rent"]
            diff = asking - comps
            eff = m.get("revenue_efficiency", {})
            grade = eff.get("grade", "N/A")
            gap = m.get("revenue_gap", {})
            dominant = gap.get("dominant_lever", "FILL")
            gap_monthly = gap.get("total_gap_monthly", 0)

            part = (
                f"Your {code} units are rated {grade} at {occ:.0%} occupancy "
                f"with {vacant} vacant. Asking ${asking:,.0f} is "
                f"{'$' + str(abs(int(diff))) + ' above' if diff > 0 else '$' + str(abs(int(diff))) + ' below'} "
                f"comps at ${comps:,.0f}."
            )
            if gap_monthly > 0:
                part += f" Revenue gap: ${gap_monthly:,.0f}/mo via {dominant}."
            parts.append(part)
        narratives[slide_key] = " ".join(parts)

    # Trend
    narratives["slide_6_narrative"] = (
        "Review the 4-month trend data to identify occupancy and pricing trajectories. "
        "Rent roll momentum scores reflect whether each unit type is improving or deteriorating."
    )

    # Revenue gap breakdown
    total_daily = sum(m["revenue_metrics"]["daily_vacancy_burn"] for m in ut_metrics.values())
    if total_gap > 0:
        narratives["slide_7_narrative"] = (
            f"Your portfolio has ${total_gap:,.0f} per month in total revenue gap "
            f"with ${total_daily:,.0f} per day in vacancy cost alone. "
            f"The gap breaks down across FILL, REPRICE, RENEW, and DE_CONCESSION levers."
        )
    else:
        narratives["slide_7_narrative"] = (
            f"Your portfolio has ${total_daily:,.0f} per day in vacancy costs, "
            f"totaling ${total_monthly:,.0f} per month. "
            f"Priority action on the highest-cost unit types will reduce this exposure."
        )

    # Action plan slides — adapt framing to worst grade
    if worst_grade in ("CRISIS", "DISTRESSED"):
        narratives["slide_8_narrative"] = (
            "The 30-day plan prioritizes filling vacancies first, then optimizing pricing. "
            "Phase 1 addresses the vacancy cost before moving to strategic positioning."
        )
        narratives["slide_9_narrative"] = (
            "Phase 1 focuses on priority fill actions: price reductions and concessions "
            "for the unit types that need the most attention."
        )
    elif worst_grade == "IMBALANCED":
        narratives["slide_8_narrative"] = (
            "The 30-day plan targets quick pricing wins first, then uses experiments "
            "and renewals to close the remaining gap."
        )
        narratives["slide_9_narrative"] = (
            "Phase 1 launches repricing adjustments and price experiments "
            "to rebalance underperforming unit types."
        )
    else:
        narratives["slide_8_narrative"] = (
            "The 30-day plan captures renewal revenue and tests upward pricing "
            "while maintaining strong occupancy."
        )
        narratives["slide_9_narrative"] = (
            "Phase 1 implements renewal increases and removes unnecessary concessions "
            "where occupancy supports it."
        )

    narratives["slide_10_narrative"] = (
        "At Day 15, evaluate experiment results and renewal retention rates "
        "to determine next steps for each unit type."
    )

    # Investigation
    narratives["slide_11_narrative"] = (
        "Several areas require further investigation, particularly unit types "
        "with low elasticity confidence where experimentation is needed."
    )

    if total_gap > 0:
        narratives["slide_12_summary"] = (
            f"Your portfolio has ${total_gap:,.0f} per month in capturable revenue. "
            f"The 30-day plan activates FILL, REPRICE, RENEW, and DE_CONCESSION levers "
            f"to close this gap systematically."
        )
    else:
        narratives["slide_12_summary"] = (
            f"Your portfolio requires immediate attention on {total_vacant} vacant units. "
            f"The 30-day plan targets a ${int(total_monthly * 0.3):,.0f} monthly savings "
            f"through pricing adjustments and experiments."
        )

    return narratives
