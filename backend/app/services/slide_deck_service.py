"""Slide deck assembly — combines narrative + viz_data + layout into 12 slides."""
from datetime import datetime

from app.services import viz_data_service as viz
from app.services.narrative_service import generate_narratives, validate_narrative_consistency


def assemble_slide_deck(
    run_id: str,
    property_name: str,
    metrics: dict,
    diagnosis: dict,
    action_plan: dict,
    config_id: str | None = None,
    claude_client=None,
) -> dict:
    """Assemble the complete 12-slide deck.

    Viz data is ALWAYS deterministic from metrics.
    Narrative is Claude-generated with fallback.

    Returns:
        Complete slide deck JSON.
    """
    narratives, is_fallback = generate_narratives(
        diagnosis, action_plan, metrics, claude_client
    )

    # Validate narrative consistency
    consistency_issues = validate_narrative_consistency(narratives, metrics)

    slides = [
        _slide_1_title(property_name),
        _slide_2_executive_summary(metrics, diagnosis, narratives),
        _slide_3_portfolio_snapshot(metrics),
        _slide_4_property_a(metrics, diagnosis, narratives),
        _slide_5_property_b(metrics, diagnosis, narratives),
        _slide_6_trends(metrics, narratives),
        _slide_7_revenue_analysis(metrics, narratives),
        _slide_8_action_overview(action_plan, narratives),
        _slide_9_phase1(action_plan, narratives),
        _slide_10_decision_tree(action_plan, narratives),
        _slide_11_investigation(diagnosis, narratives),
        _slide_12_revenue_roadmap(metrics, action_plan, narratives),
    ]

    return {
        "slides": slides,
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "property_name": property_name,
            "config_id": config_id,
            "run_id": run_id,
            "narrative_fallback": is_fallback,
            "consistency_issues": consistency_issues,
        },
    }


def _slide_1_title(property_name: str) -> dict:
    return {
        "slide_number": 1,
        "slide_type": "TITLE",
        "title": f"{property_name} — Pricing Health Diagnostic & 30-Day Action Plan",
        "narrative": {
            "subtitle": "March 2026",
            "prepared_for": property_name,
        },
        "viz_data": None,
        "layout": {"template": "title"},
    }


def _slide_2_executive_summary(metrics: dict, diagnosis: dict, narratives: dict) -> dict:
    return {
        "slide_number": 2,
        "slide_type": "EXECUTIVE_SUMMARY",
        "title": "Executive Summary",
        "narrative": {
            "headline": narratives.get("slide_2_headline", ""),
            "key_findings": narratives.get("slide_2_findings", []),
        },
        "viz_data": {
            "score_gauge": viz.generate_score_gauge(diagnosis, metrics),
            "kpi_cards": viz.generate_kpi_cards(metrics),
            "dimension_breakdown": viz.generate_dimension_breakdown(metrics),
        },
        "layout": {"template": "executive_summary", "components": ["score_gauge", "kpi_cards", "dimension_breakdown"]},
    }


def _slide_3_portfolio_snapshot(metrics: dict) -> dict:
    return {
        "slide_number": 3,
        "slide_type": "DATA_TABLE",
        "title": "Portfolio Snapshot",
        "narrative": {
            "description": "Complete rent roll summary matching the pricing export.",
        },
        "viz_data": {
            "data_table": viz.generate_data_table(metrics),
        },
        "layout": {"template": "data_table"},
    }


def _slide_4_property_a(metrics: dict, diagnosis: dict, narratives: dict) -> dict:
    return {
        "slide_number": 4,
        "slide_type": "PROPERTY_DEEP_DIVE",
        "title": "Property A — Deep Dive",
        "narrative": {
            "analysis": narratives.get("slide_4_narrative", ""),
        },
        "viz_data": {
            "score_cards": viz.generate_dual_score_card(diagnosis, "A"),
            "waterfall_a1": viz.generate_rent_waterfall("A1", metrics),
            "waterfall_a2": viz.generate_rent_waterfall("A2", metrics),
        },
        "layout": {"template": "property_deep_dive", "components": ["score_cards", "waterfall"]},
    }


def _slide_5_property_b(metrics: dict, diagnosis: dict, narratives: dict) -> dict:
    return {
        "slide_number": 5,
        "slide_type": "PROPERTY_DEEP_DIVE",
        "title": "Property B — Deep Dive",
        "narrative": {
            "analysis": narratives.get("slide_5_narrative", ""),
        },
        "viz_data": {
            "score_cards": viz.generate_dual_score_card(diagnosis, "B"),
            "waterfall_b1": viz.generate_rent_waterfall("B1", metrics),
            "waterfall_b2": viz.generate_rent_waterfall("B2", metrics),
        },
        "layout": {"template": "property_deep_dive", "components": ["score_cards", "waterfall"]},
    }


def _slide_6_trends(metrics: dict, narratives: dict) -> dict:
    return {
        "slide_number": 6,
        "slide_type": "TREND_ANALYSIS",
        "title": "4-Month Trend Analysis",
        "narrative": {
            "analysis": narratives.get("slide_6_narrative", ""),
        },
        "viz_data": {
            "line_charts": viz.generate_line_charts(metrics),
        },
        "layout": {"template": "trend_analysis", "components": ["line_charts"]},
    }


def _slide_7_revenue_analysis(metrics: dict, narratives: dict) -> dict:
    return {
        "slide_number": 7,
        "slide_type": "REVENUE_ANALYSIS",
        "title": "Revenue Analysis",
        "narrative": {
            "analysis": narratives.get("slide_7_narrative", ""),
        },
        "viz_data": {
            "revenue_gap_waterfall": viz.generate_revenue_gap_waterfall(metrics),
            "daily_burn": viz.generate_daily_burn_counter(metrics),
        },
        "layout": {"template": "revenue_analysis", "components": ["revenue_gap_waterfall", "daily_burn"]},
    }


def _slide_8_action_overview(action_plan: dict, narratives: dict) -> dict:
    return {
        "slide_number": 8,
        "slide_type": "ACTION_PLAN_OVERVIEW",
        "title": "30-Day Action Plan",
        "narrative": {
            "overview": narratives.get("slide_8_narrative", ""),
        },
        "viz_data": {
            "timeline": viz.generate_timeline(action_plan),
        },
        "layout": {"template": "action_overview", "components": ["timeline"]},
    }


def _slide_9_phase1(action_plan: dict, narratives: dict) -> dict:
    return {
        "slide_number": 9,
        "slide_type": "PHASE_DETAIL",
        "title": "Phase 1: Immediate Actions (Days 1-3)",
        "narrative": {
            "detail": narratives.get("slide_9_narrative", ""),
        },
        "viz_data": {
            "action_cards": viz.generate_action_cards(action_plan),
            "experiment_diagrams": viz.generate_experiment_diagram(action_plan),
        },
        "layout": {"template": "phase_detail", "components": ["action_cards", "experiment_diagrams"]},
    }


def _slide_10_decision_tree(action_plan: dict, narratives: dict) -> dict:
    return {
        "slide_number": 10,
        "slide_type": "DECISION_TREE",
        "title": "Day 15 Decision Point",
        "narrative": {
            "explanation": narratives.get("slide_10_narrative", ""),
        },
        "viz_data": {
            "flowcharts": viz.generate_decision_flowchart(action_plan),
        },
        "layout": {"template": "decision_tree", "components": ["flowcharts"]},
    }


def _slide_11_investigation(diagnosis: dict, narratives: dict) -> dict:
    return {
        "slide_number": 11,
        "slide_type": "INVESTIGATION",
        "title": "Further Investigation",
        "narrative": {
            "overview": narratives.get("slide_11_narrative", ""),
        },
        "viz_data": {
            "investigation_table": viz.generate_investigation_table(diagnosis),
        },
        "layout": {"template": "investigation", "components": ["investigation_table"]},
    }


def _slide_12_revenue_roadmap(metrics: dict, action_plan: dict, narratives: dict) -> dict:
    return {
        "slide_number": 12,
        "slide_type": "REVENUE_ROADMAP",
        "title": "Revenue Roadmap",
        "narrative": {
            "summary": narratives.get("slide_12_summary", ""),
        },
        "viz_data": {
            "before_after": viz.generate_before_after(metrics, action_plan),
            "revenue_roadmap": viz.generate_revenue_roadmap(metrics, action_plan),
        },
        "layout": {"template": "revenue_roadmap", "components": ["before_after", "revenue_roadmap"]},
    }
