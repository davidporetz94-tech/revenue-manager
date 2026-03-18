"""Portfolio slide deck assembly — combines portfolio narrative + viz data into slides.

Multi-property version of slide_deck_service.py. Uses aggregate_cross_property()
output and portfolio-level services for diagnosis, viz, and narrative.
"""
from datetime import datetime

from app.services import portfolio_viz_data_service as pviz
from app.services.portfolio_narrative_service import generate_portfolio_narratives


def assemble_portfolio_slide_deck(
    cross_property_data: dict,
    diagnosis: dict,
    action_plan: dict,
    claude_client=None,
) -> dict:
    """Assemble the portfolio-level slide deck.

    Viz data is ALWAYS deterministic from aggregated metrics.
    Narrative is Claude-generated with fallback.

    Args:
        cross_property_data: output of aggregate_cross_property().
        diagnosis: portfolio diagnosis dict.
        action_plan: portfolio action plan dict.
        claude_client: optional ClaudeClient for testing.

    Returns:
        Complete portfolio slide deck JSON.
    """
    narratives, is_fallback = generate_portfolio_narratives(
        cross_property_data, diagnosis, action_plan, claude_client,
    )

    aggregate = cross_property_data.get("aggregate", {})

    slides = [
        _slide_1_title(),
        _slide_2_executive_summary(cross_property_data, diagnosis, narratives),
        _slide_3_kpi_detail(cross_property_data),
        _slide_4_property_ranking(cross_property_data, narratives),
        _slide_5_property_details(cross_property_data),
        _slide_6_revenue_at_risk(cross_property_data, narratives),
        _slide_7_revenue_stacked(cross_property_data),
        _slide_8_action_overview(action_plan, narratives),
        _slide_9_phase1(action_plan, narratives),
        _slide_10_phase2_3(action_plan),
        _slide_11_phase4(action_plan),
        _slide_12_renewal_opportunity(cross_property_data, diagnosis),
        _slide_13_cross_property_risks(diagnosis),
        _slide_14_investigation(diagnosis),
        _slide_15_revenue_roadmap(cross_property_data, action_plan, narratives),
    ]

    return {
        "slides": slides,
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "portfolio": True,
            "property_count": len(cross_property_data.get("properties", {})),
            "narrative_fallback": is_fallback,
        },
    }


def _slide_1_title() -> dict:
    """Slide 1: Portfolio title slide."""
    return {
        "slide_number": 1,
        "slide_type": "TITLE",
        "title": "Portfolio Pricing Health Diagnostic & 30-Day Action Plan",
        "narrative": {
            "subtitle": "March 2026",
            "prepared_for": "Portfolio Overview",
        },
        "viz_data": None,
        "layout": {"template": "title"},
    }


def _slide_2_executive_summary(
    cross_property_data: dict, diagnosis: dict, narratives: dict,
) -> dict:
    """Slide 2: Executive Summary with revenue efficiency gauge + 6 KPI cards."""
    return {
        "slide_number": 2,
        "slide_type": "EXECUTIVE_SUMMARY",
        "title": "Portfolio Executive Summary",
        "narrative": {
            "headline": narratives.get("slide_2_headline", ""),
            "key_findings": narratives.get("slide_2_findings", []),
        },
        "viz_data": {
            "score_gauge": pviz.generate_portfolio_score_gauge(cross_property_data),
            "kpi_cards": pviz.generate_portfolio_kpi_cards(cross_property_data),
        },
        "layout": {
            "template": "executive_summary",
            "components": ["score_gauge", "kpi_cards"],
        },
    }


def _slide_3_kpi_detail(cross_property_data: dict) -> dict:
    """Slide 3: Detailed KPI breakdown."""
    aggregate = cross_property_data.get("aggregate", {})
    return {
        "slide_number": 3,
        "slide_type": "KPI_DETAIL",
        "title": "Portfolio Key Metrics",
        "narrative": {
            "description": "Aggregated revenue metrics across all properties.",
        },
        "viz_data": {
            "aggregate": aggregate,
        },
        "layout": {"template": "kpi_detail"},
    }


def _slide_4_property_ranking(
    cross_property_data: dict, narratives: dict,
) -> dict:
    """Slide 4: Property Ranking by revenue efficiency."""
    return {
        "slide_number": 4,
        "slide_type": "PROPERTY_RANKING",
        "title": "Property Ranking by Revenue Efficiency",
        "narrative": {
            "analysis": narratives.get("slide_4_narrative", ""),
        },
        "viz_data": {
            "ranking_cards": pviz.generate_property_ranking_cards(cross_property_data),
        },
        "layout": {
            "template": "property_ranking",
            "components": ["ranking_cards"],
        },
    }


def _slide_5_property_details(cross_property_data: dict) -> dict:
    """Slide 5: Per-property detail summary."""
    properties = cross_property_data.get("properties", {})
    detail = []
    for prop_key, prop_data in properties.items():
        detail.append({
            "property_name": prop_data.get("property_name", prop_key),
            "revenue_efficiency": prop_data.get("revenue_efficiency", 0),
            "revenue_gap": prop_data.get("revenue_gap", 0),
            "total_units": prop_data.get("total_units", 0),
            "total_vacant": prop_data.get("total_vacant", 0),
            "renewal_opportunity": prop_data.get("renewal_opportunity", 0),
        })

    return {
        "slide_number": 5,
        "slide_type": "PROPERTY_DETAILS",
        "title": "Per-Property Detail",
        "narrative": {
            "description": "Revenue metrics for each property in the portfolio.",
        },
        "viz_data": {
            "property_details": detail,
        },
        "layout": {"template": "property_details"},
    }


def _slide_6_revenue_at_risk(
    cross_property_data: dict, narratives: dict,
) -> dict:
    """Slide 6: Revenue at Risk — gap waterfall across properties."""
    return {
        "slide_number": 6,
        "slide_type": "REVENUE_AT_RISK",
        "title": "Revenue at Risk",
        "narrative": {
            "analysis": narratives.get("slide_6_narrative", ""),
        },
        "viz_data": {
            "revenue_gap_waterfall": pviz.generate_portfolio_revenue_gap_waterfall(
                cross_property_data,
            ),
        },
        "layout": {
            "template": "revenue_at_risk",
            "components": ["revenue_gap_waterfall"],
        },
    }


def _slide_7_revenue_stacked(cross_property_data: dict) -> dict:
    """Slide 7: Revenue metrics stacked bar by property."""
    return {
        "slide_number": 7,
        "slide_type": "REVENUE_STACKED_BAR",
        "title": "Revenue by Property",
        "narrative": {
            "description": "Current revenue, gap, and renewal opportunity by property.",
        },
        "viz_data": {
            "stacked_bar": pviz.generate_portfolio_revenue_stacked_bar(
                cross_property_data,
            ),
        },
        "layout": {
            "template": "revenue_stacked_bar",
            "components": ["stacked_bar"],
        },
    }


def _slide_8_action_overview(action_plan: dict, narratives: dict) -> dict:
    """Slide 8: 30-day action plan overview."""
    phases = action_plan.get("phases", [])
    colors = ["#DC2626", "#D97706", "#7C3AED", "#059669"]
    timeline = []
    for phase in phases:
        timeline.append({
            "phase": phase.get("phase_number", 0),
            "title": phase.get("name", ""),
            "days": phase.get("days", ""),
            "actions_count": len(phase.get("actions", [])),
            "color": colors[phase.get("phase_number", 1) - 1] if phase.get("phase_number", 1) <= 4 else "#6B7280",
        })

    return {
        "slide_number": 8,
        "slide_type": "ACTION_PLAN_OVERVIEW",
        "title": "Portfolio 30-Day Action Plan",
        "narrative": {
            "overview": narratives.get("slide_8_narrative", ""),
        },
        "viz_data": {
            "timeline": timeline,
        },
        "layout": {
            "template": "action_overview",
            "components": ["timeline"],
        },
    }


def _slide_9_phase1(action_plan: dict, narratives: dict) -> dict:
    """Slide 9: Phase 1 immediate actions."""
    phases = action_plan.get("phases", [])
    phase1_actions = phases[0].get("actions", []) if phases else []

    return {
        "slide_number": 9,
        "slide_type": "PHASE_DETAIL",
        "title": "Phase 1: Immediate Actions (Days 1-3)",
        "narrative": {
            "detail": narratives.get("slide_9_narrative", ""),
        },
        "viz_data": {
            "action_cards": [
                {
                    "property": a.get("property", ""),
                    "action_type": a.get("action_type", ""),
                    "lever": a.get("lever", ""),
                    "description": a.get("description", ""),
                    "expected_impact": a.get("expected_impact_monthly", 0),
                }
                for a in phase1_actions
            ],
        },
        "layout": {
            "template": "phase_detail",
            "components": ["action_cards"],
        },
    }


def _slide_10_phase2_3(action_plan: dict) -> dict:
    """Slide 10: Phases 2-3 overview."""
    phases = action_plan.get("phases", [])
    phase2_actions = phases[1].get("actions", []) if len(phases) > 1 else []
    phase3_actions = phases[2].get("actions", []) if len(phases) > 2 else []

    return {
        "slide_number": 10,
        "slide_type": "PHASE_DETAIL",
        "title": "Phases 2-3: Monitor & Converge (Days 4-21)",
        "narrative": {
            "description": "Execute experiments, monitor velocity, converge on optimal strategies.",
        },
        "viz_data": {
            "phase_2_actions": len(phase2_actions),
            "phase_3_actions": len(phase3_actions),
        },
        "layout": {"template": "phase_detail"},
    }


def _slide_11_phase4(action_plan: dict) -> dict:
    """Slide 11: Phase 4 lock strategies."""
    phases = action_plan.get("phases", [])
    phase4_actions = phases[3].get("actions", []) if len(phases) > 3 else []

    return {
        "slide_number": 11,
        "slide_type": "PHASE_DETAIL",
        "title": "Phase 4: Lock Strategy (Days 22-30)",
        "narrative": {
            "description": "Lock winning strategies, prepare for peak season.",
        },
        "viz_data": {
            "phase_4_actions": len(phase4_actions),
        },
        "layout": {"template": "phase_detail"},
    }


def _slide_12_renewal_opportunity(
    cross_property_data: dict, diagnosis: dict,
) -> dict:
    """Slide 12: Renewal opportunity across portfolio."""
    aggregate = cross_property_data.get("aggregate", {})
    total_renewal = aggregate.get("total_renewal_opportunity", 0)

    renewal_data = diagnosis.get("portfolio_renewal_opportunity", {})
    by_property = renewal_data.get("by_property", [])

    return {
        "slide_number": 12,
        "slide_type": "RENEWAL_OPPORTUNITY",
        "title": "Renewal Revenue Capture",
        "narrative": {
            "description": f"${total_renewal:,.0f}/yr in portfolio-wide renewal opportunity.",
        },
        "viz_data": {
            "total_annual": total_renewal,
            "by_property": by_property,
        },
        "layout": {
            "template": "renewal_opportunity",
            "components": ["renewal_bars"],
        },
    }


def _slide_13_cross_property_risks(diagnosis: dict) -> dict:
    """Slide 13: Cross-property risks."""
    risks = diagnosis.get("cross_property_risks", [])
    return {
        "slide_number": 13,
        "slide_type": "RISK_ANALYSIS",
        "title": "Cross-Property Risks",
        "narrative": {
            "description": "Risks from coordinated pricing actions across properties.",
        },
        "viz_data": {
            "risks": risks,
        },
        "layout": {"template": "risk_analysis"},
    }


def _slide_14_investigation(diagnosis: dict) -> dict:
    """Slide 14: Further investigation areas."""
    return {
        "slide_number": 14,
        "slide_type": "INVESTIGATION",
        "title": "Further Investigation",
        "narrative": {
            "description": "Areas requiring additional data or analysis.",
        },
        "viz_data": {
            "items": [],
        },
        "layout": {"template": "investigation"},
    }


def _slide_15_revenue_roadmap(
    cross_property_data: dict, action_plan: dict, narratives: dict,
) -> dict:
    """Slide 15: Revenue Roadmap with per-lever amounts across properties."""
    aggregate = cross_property_data.get("aggregate", {})
    properties = cross_property_data.get("properties", {})

    current_revenue = aggregate.get("total_current_revenue", 0)
    optimal_revenue = aggregate.get("total_optimal_revenue", 0)
    total_gap = aggregate.get("total_revenue_gap", 0)
    total_renewal = aggregate.get("total_renewal_opportunity", 0)

    # Aggregate lever amounts across all properties' unit types
    total_vacancy = 0.0
    total_reprice = 0.0
    total_renewal_lever = 0.0
    total_concession = 0.0

    for _prop_key, prop_data in properties.items():
        for _code, m in prop_data.get("unit_type_metrics", {}).items():
            gap = m.get("revenue_gap", {})
            components = gap.get("gap_components", {})
            total_vacancy += components.get("vacancy_cost", {}).get("amount", 0)
            total_reprice += components.get("new_lease_underpricing", {}).get("amount", 0)
            total_renewal_lever += components.get("renewal_opportunity", {}).get("amount", 0)
            total_concession += components.get("concession_drag", {}).get("amount", 0)

    # Projected = current + all levers, capped at optimal
    projected = current_revenue + total_vacancy + total_reprice + total_renewal_lever - total_concession
    if optimal_revenue > 0:
        projected = min(projected, optimal_revenue)

    impact_summary = action_plan.get("revenue_impact_summary", {})

    return {
        "slide_number": 15,
        "slide_type": "REVENUE_ROADMAP",
        "title": "Portfolio Revenue Roadmap",
        "narrative": {
            "summary": narratives.get("slide_15_narrative", ""),
        },
        "viz_data": {
            "current_monthly": current_revenue,
            "projected_monthly": projected,
            "optimal_monthly": optimal_revenue,
            "levers": [
                {"label": "Fill Vacant Units", "amount": total_vacancy, "lever": "FILL"},
                {"label": "Reprice New Leases", "amount": total_reprice, "lever": "REPRICE"},
                {"label": "Capture Renewals", "amount": total_renewal_lever, "lever": "RENEW"},
                {"label": "Remove Concessions", "amount": total_concession, "lever": "DE_CONCESSION"},
            ],
            "total_gap_monthly": total_gap,
            "total_renewal_annual": total_renewal,
            "impact_summary": impact_summary,
        },
        "layout": {
            "template": "revenue_roadmap",
            "components": ["before_after", "lever_breakdown"],
        },
    }
