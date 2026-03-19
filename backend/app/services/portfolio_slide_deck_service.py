"""Portfolio slide deck service — assembles portfolio-wide slide deck."""
from datetime import datetime

from app.services.portfolio_viz_data_service import (
    generate_portfolio_score_gauge,
    generate_portfolio_kpi_cards,
    generate_property_comparison_table,
    generate_property_ranking_cards,
    generate_portfolio_trend_lines,
    generate_portfolio_stacked_bar,
    generate_portfolio_revenue_gap_waterfall,
    generate_property_rent_waterfall,
    generate_property_line_charts,
    generate_portfolio_timeline,
    generate_portfolio_action_cards,
    generate_portfolio_flowcharts,
    generate_portfolio_investigation_table,
    generate_portfolio_before_after,
)
from app.services.portfolio_narrative_service import generate_portfolio_narratives


def _score_card_grade(occupancy: float) -> str:
    """Map occupancy to a grade label for display."""
    if occupancy >= 0.95:
        return "OPTIMIZED"
    if occupancy >= 0.90:
        return "OPPORTUNITY"
    if occupancy >= 0.85:
        return "ADJUSTING"
    if occupancy >= 0.80:
        return "DISTRESSED"
    return "CRISIS"


def _score_card_score(occupancy: float, daily_burn: float) -> int:
    """Compute a display score from occupancy and daily burn."""
    occ_score = min(occupancy * 100, 100)
    burn_penalty = min(daily_burn / 10, 30)
    return max(0, round(occ_score - burn_penalty))


def assemble_portfolio_slide_deck(
    run_id: str,
    metrics: dict,
    diagnosis: dict,
    action_plan: dict,
    claude_client=None,
) -> dict:
    """Assemble the portfolio slide deck.

    Args:
        run_id: diagnostic run ID.
        metrics: portfolio aggregate metrics (from aggregate_cross_property).
        diagnosis: portfolio diagnosis JSON.
        action_plan: portfolio action plan JSON.
        claude_client: optional Claude client for narrative generation.

    Returns:
        Dict with 'slides' list and 'metadata'.
    """
    narratives, is_fallback = generate_portfolio_narratives(
        diagnosis, action_plan, metrics, claude_client
    )

    properties = metrics.get("properties", {})
    aggregate = metrics.get("aggregate", {})

    slides = []

    # Slide 1: Title
    slides.append({
        "slide_number": 1,
        "slide_type": "PORTFOLIO_TITLE",
        "title": "Portfolio Pricing Analysis",
        "narrative": {
            "subtitle": (
                f"{len(properties)} Properties "
                f"— {aggregate.get('total_units', 0)} Units "
                f"— March 2026"
            ),
        },
        "viz_data": None,
        "layout": {"template": "title", "components": ["title", "subtitle"]},
    })

    # Slide 2: Executive Summary
    # Frontend reads narrative.key_findings (not findings)
    slides.append({
        "slide_number": 2,
        "slide_type": "PORTFOLIO_EXECUTIVE_SUMMARY",
        "title": "Executive Summary",
        "narrative": {
            "headline": narratives.get("slide_2_headline", ""),
            "key_findings": narratives.get("slide_2_findings", []),
        },
        "viz_data": {
            "score_gauge": generate_portfolio_score_gauge(diagnosis, aggregate),
            "kpi_cards": generate_portfolio_kpi_cards(aggregate),
        },
        "layout": {
            "template": "executive_summary",
            "components": ["score_gauge", "kpi_cards", "headline", "findings"],
        },
    })

    # Slide 3: Portfolio Snapshot (property comparison)
    slides.append({
        "slide_number": 3,
        "slide_type": "PORTFOLIO_SNAPSHOT",
        "title": "Portfolio Snapshot",
        "narrative": {"text": narratives.get("slide_3_narrative", "")},
        "viz_data": {
            "comparison_table": generate_property_comparison_table(properties),
        },
        "layout": {"template": "data_table", "components": ["table", "narrative"]},
    })

    # Slide 4: Property Ranking
    slides.append({
        "slide_number": 4,
        "slide_type": "PROPERTY_RANKING",
        "title": "Property Health Ranking",
        "narrative": {"text": narratives.get("slide_4_narrative", "")},
        "viz_data": {
            "ranking_cards": generate_property_ranking_cards(
                diagnosis,
                property_ranking=metrics.get("property_ranking"),
            ),
        },
        "layout": {"template": "ranking", "components": ["cards", "narrative"]},
    })

    # Slide 5: Portfolio Trends
    slides.append({
        "slide_number": 5,
        "slide_type": "PORTFOLIO_TRENDS",
        "title": "Portfolio Trends",
        "narrative": {"text": narratives.get("slide_5_narrative", "")},
        "viz_data": generate_portfolio_trend_lines(properties),
        "layout": {
            "template": "trends",
            "components": ["line_charts", "narrative"],
        },
    })

    # Slide 6: Revenue at Risk
    # Frontend reads viz.revenue_gap_waterfall (segments) and narrative.analysis
    stacked_bar = generate_portfolio_stacked_bar(properties)
    slides.append({
        "slide_number": 6,
        "slide_type": "PORTFOLIO_REVENUE_AT_RISK",
        "title": "Revenue at Risk",
        "narrative": {"analysis": narratives.get("slide_6_narrative", "")},
        "viz_data": {
            "stacked_bar": stacked_bar,
            "daily_burn": {
                "daily_amount": round(aggregate.get("total_monthly_vacancy_cost", 0) / 30, 2),
                "monthly_amount": aggregate.get("total_monthly_vacancy_cost", 0),
                "annual_amount": aggregate.get("total_monthly_vacancy_cost", 0) * 12,
            },
            "revenue_gap_waterfall": generate_portfolio_revenue_gap_waterfall(
                stacked_bar, aggregate
            ),
            "revenue_gap_total": aggregate.get("total_revenue_gap", 0),
            "revenue_efficiency": aggregate.get("portfolio_revenue_efficiency", 0),
        },
        "layout": {
            "template": "revenue_at_risk",
            "components": ["stacked_bar", "counter", "narrative"],
        },
    })

    # Slides 7+: Property Deep Dives (2 per property)
    slide_num = 7
    for prop_name, pdata in properties.items():
        ut_metrics = pdata["unit_type_metrics"]

        # Deep dive slide (waterfalls)
        # Frontend reads card.grade, card.score, card.key_metric and narrative.analysis
        viz: dict = {"score_cards": []}
        for code, m in ut_metrics.items():
            ps = m["pricing_spreads"]
            viz[f"waterfall_{code.lower()}"] = generate_property_rent_waterfall(
                code,
                ps["base_rent"],
                ps["amenity_price"],
                ps["predicted_rent"],
                ps["asking_rent"],
                ps["comps_rent"],
            )
            occ = m["occupancy_metrics"]["occupancy_rate"]
            daily_burn = m["revenue_metrics"]["daily_vacancy_burn"]
            vacant = m["occupancy_metrics"]["vacant"]
            viz["score_cards"].append({
                "unit_type": code,
                "occupancy": occ,
                "vacant": vacant,
                "daily_burn": daily_burn,
                "grade": _score_card_grade(occ),
                "score": _score_card_score(occ, daily_burn),
                "key_metric": (
                    f"{round(occ * 100)}% occupancy, "
                    f"{vacant} vacant, "
                    f"${daily_burn}/day burn"
                ),
            })

        slides.append({
            "slide_number": slide_num,
            "slide_type": "PROPERTY_DEEP_DIVE",
            "title": f"{prop_name} Deep Dive",
            "narrative": {"analysis": f"{prop_name} unit type analysis."},
            "viz_data": viz,
            "layout": {
                "template": "property_deep_dive",
                "components": ["score_cards", "waterfalls"],
            },
        })
        slide_num += 1

        # Trend slide for this property — use TREND_ANALYSIS type
        trend_viz = generate_property_line_charts(ut_metrics)
        slides.append({
            "slide_number": slide_num,
            "slide_type": "TREND_ANALYSIS",
            "title": f"{prop_name} Trends",
            "narrative": {"analysis": f"{prop_name} 4-month trend analysis."},
            "viz_data": {"line_charts": trend_viz},
            "layout": {
                "template": "trend_analysis",
                "components": ["line_charts"],
            },
        })
        slide_num += 1

    # Action Plan slides
    phases = action_plan.get("phases", [])
    # Slide 11: Action Plan Overview — frontend reads viz.timeline
    slides.append({
        "slide_number": slide_num,
        "slide_type": "PORTFOLIO_ACTION_PLAN",
        "title": "30-Day Portfolio Action Plan",
        "narrative": {"overview": narratives.get("slide_11_narrative", "")},
        "viz_data": {
            "timeline": generate_portfolio_timeline(phases),
            "phases": phases,
        },
        "layout": {
            "template": "action_plan",
            "components": ["timeline", "narrative"],
        },
    })
    slide_num += 1

    # Slide 12: Phase 1 Detail — frontend reads viz.action_cards and narrative.detail
    phase1_actions = phases[0].get("actions", []) if phases else []
    slides.append({
        "slide_number": slide_num,
        "slide_type": "PORTFOLIO_PHASE_DETAIL",
        "title": "Phase 1: Immediate Actions",
        "narrative": {"detail": narratives.get("slide_12_narrative", "")},
        "viz_data": {
            "action_cards": generate_portfolio_action_cards(phase1_actions),
            "actions": phase1_actions,
        },
        "layout": {
            "template": "phase_detail",
            "components": ["action_cards", "narrative"],
        },
    })
    slide_num += 1

    # Slide 13: Decision Point — frontend reads viz.flowcharts and narrative.explanation
    slides.append({
        "slide_number": slide_num,
        "slide_type": "PORTFOLIO_DECISION_POINT",
        "title": "Day 15 Decision Points",
        "narrative": {"explanation": narratives.get("slide_13_narrative", "")},
        "viz_data": {
            "flowcharts": generate_portfolio_flowcharts(phases),
        },
        "layout": {
            "template": "decision_tree",
            "components": ["flowchart", "narrative"],
        },
    })
    slide_num += 1

    # Slide 14: Investigation — frontend reads viz.investigation_table and narrative.overview
    slides.append({
        "slide_number": slide_num,
        "slide_type": "PORTFOLIO_INVESTIGATION",
        "title": "Further Investigation",
        "narrative": {"overview": narratives.get("slide_14_narrative", "")},
        "viz_data": {
            "investigation_table": generate_portfolio_investigation_table(
                properties, diagnosis
            ),
        },
        "layout": {
            "template": "investigation",
            "components": ["table", "narrative"],
        },
    })
    slide_num += 1

    # Slide 15: Summary — frontend reads viz.before_after and narrative.summary
    slides.append({
        "slide_number": slide_num,
        "slide_type": "PORTFOLIO_SUMMARY",
        "title": "Summary & Next Steps",
        "narrative": {"summary": narratives.get("slide_15_summary", "")},
        "viz_data": {
            "before_after": generate_portfolio_before_after(aggregate),
            "daily_burn": round(aggregate.get("total_monthly_vacancy_cost", 0) / 30, 2),
            "monthly_cost": aggregate.get("total_monthly_vacancy_cost", 0),
            "property_count": len(properties),
            "total_vacant": aggregate.get("total_vacant", 0),
            "revenue_gap": aggregate.get("total_revenue_gap", 0),
            "revenue_efficiency": aggregate.get("portfolio_revenue_efficiency", 0),
        },
        "layout": {
            "template": "summary",
            "components": ["before_after", "narrative"],
        },
    })

    return {
        "slides": slides,
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "scope": "portfolio",
            "property_count": aggregate.get("property_count", 0),
            "run_id": run_id,
            "narrative_fallback": is_fallback,
        },
    }
