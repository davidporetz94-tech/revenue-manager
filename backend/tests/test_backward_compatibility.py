"""Tests for graceful degradation with old metrics format.

Verifies that slide deck assembly works with metrics dicts
that are MISSING the new revenue optimization sections:
- elasticity
- optimal_pricing
- revenue_gap
- revenue_efficiency
- renewal_opportunity

This ensures existing stored diagnostic runs don't crash.
"""
from unittest.mock import MagicMock

from app.services.slide_deck_service import assemble_slide_deck
from app.services.claude_client import ClaudeAPIError

# Metrics dict WITHOUT the new revenue optimization sections.
# Includes all fields that the original metrics engine produced,
# but none of the 5 new per-unit-type sections from the revenue optimizer.
OLD_METRICS = {
    "property_name": "Test Property",
    "unit_type_metrics": {
        "A1": {
            "occupancy_metrics": {
                "occupancy_rate": 0.96,
                "total_units": 48,
                "occupied": 46,
                "vacant": 2,
            },
            "exposure_metrics": {
                "total_exposure_pct": 0.06,
                "vacant_exposure_pct": 0.04,
            },
            "velocity_metrics": {"avg_dom": 24, "avg_days_vacant": 17},
            "pricing_spreads": {
                "asking_rent": 1365,
                "predicted_rent": 1329,
                "comps_rent": 1353,
                "base_rent": 1240,
                "amenity_price": 89,
                "in_place_rent": 1269,
                "executed_rent": 1324,
                "asking_vs_predicted_dollars": 36,
                "asking_vs_predicted_pct": 2.7,
                "asking_vs_comps_dollars": 12,
                "asking_vs_comps_pct": 0.9,
                "executed_vs_asking_dollars": -41,
                "executed_vs_asking_pct": -3.0,
                "loss_to_lease_dollars": 96,
                "loss_to_lease_pct": 7.6,
                "amenity_pct_of_predicted": 6.7,
            },
            "revenue_metrics": {
                "monthly_potential_revenue": 65520,
                "monthly_actual_revenue": 58374,
                "monthly_vacancy_cost": 2730,
                "accumulated_vacancy_cost": 2730,
                "daily_vacancy_burn": 91,
                "revenue_at_risk_30d": 2730,
                "price_reduction_breakeven_days": 13.2,
            },
            "demand_metrics": {"demand_score": 0.63},
            "lease_term_metrics": {},
            "trend_metrics": {"occupancy_trend": []},
            "seasonal_context": {
                "season": "SPRING_RAMP",
                "seasonal_factor": 0.98,
                "months_to_peak": 2,
            },
            "ltl_analysis": {
                "ltl_dollars": 96,
                "ltl_pct": 0.076,
                "ltl_direction": "UPSIDE",
            },
        },
    },
    "portfolio_metrics": {
        "total_units": 48,
        "total_vacant": 2,
        "blended_occupancy": 0.96,
        "total_monthly_vacancy_cost": 2730,
    },
}

OLD_DIAGNOSIS = {
    "unit_type_assessments": [
        {
            "unit_type": "A1",
            "health_score": 85,
            "grade": "HEALTHY",
            "key_findings": [],
            "recommended_actions": [],
        }
    ],
    "portfolio_assessment": {
        "summary": "test",
        "portfolio_score": 85,
        "overall_portfolio_score": 85,
    },
}

OLD_ACTION_PLAN = {
    "phases": [
        {"phase_number": 1, "name": "Immediate", "days": "1-3", "actions": []},
        {"phase_number": 2, "name": "Calibrate", "days": "4-14", "actions": []},
        {"phase_number": 3, "name": "Decision", "days": "15-21", "actions": []},
        {"phase_number": 4, "name": "Optimize", "days": "22-30", "actions": []},
    ],
}


def _make_failing_client() -> MagicMock:
    """Create a mock Claude client that forces fallback narratives."""
    client = MagicMock()
    client.call_json.side_effect = ClaudeAPIError("test: force fallback")
    return client


def _build_deck() -> dict:
    """Build slide deck with old metrics using mock client."""
    return assemble_slide_deck(
        run_id="test-old",
        property_name="Test Property",
        metrics=OLD_METRICS,
        diagnosis=OLD_DIAGNOSIS,
        action_plan=OLD_ACTION_PLAN,
        claude_client=_make_failing_client(),
    )


def test_slide_assembly_with_old_metrics():
    """Slide deck builds (degraded) without new revenue sections."""
    deck = _build_deck()
    assert "slides" in deck
    assert len(deck["slides"]) == 12
    for slide in deck["slides"]:
        assert "slide_number" in slide
        assert "slide_type" in slide
        assert "title" in slide


def test_old_metrics_score_gauge_fallback():
    """Score gauge falls back to diagnosis score when no revenue_efficiency."""
    deck = _build_deck()
    slide_2 = deck["slides"][1]
    assert "viz_data" in slide_2
    # Should not crash, should produce some score gauge
    assert slide_2["viz_data"].get("score_gauge") is not None
    # Should fall back to diagnosis portfolio score (85)
    assert slide_2["viz_data"]["score_gauge"]["score"] == 85


def test_old_metrics_kpi_cards():
    """KPI cards work with old metrics (show 0 for new fields)."""
    deck = _build_deck()
    slide_2 = deck["slides"][1]
    kpi = slide_2["viz_data"].get("kpi_cards", [])
    assert len(kpi) == 6  # all 6 cards present, new ones show zero


def test_old_metrics_dimension_breakdown_defaults():
    """Dimension breakdown uses defaults when revenue_efficiency missing."""
    deck = _build_deck()
    slide_2 = deck["slides"][1]
    breakdown = slide_2["viz_data"].get("dimension_breakdown")
    assert breakdown is not None
    # Should have 3 dimensions with default scores
    assert len(breakdown["dimensions"]) == 3
    # Should default to 50 when no revenue_efficiency section
    assert breakdown["composite_score"] == 50


def test_old_metrics_revenue_gap_waterfall_zeros():
    """Revenue gap waterfall returns zero segments when revenue_gap missing."""
    deck = _build_deck()
    slide_7 = deck["slides"][6]
    waterfall = slide_7["viz_data"].get("revenue_gap_waterfall")
    assert waterfall is not None
    assert "segments" in waterfall
    # All values should be 0 since no revenue_gap section
    for seg in waterfall["segments"]:
        assert seg["value"] == 0


def test_old_metrics_revenue_roadmap_zeros():
    """Revenue roadmap returns zero values when revenue_gap missing."""
    deck = _build_deck()
    slide_12 = deck["slides"][11]
    roadmap = slide_12["viz_data"].get("revenue_roadmap")
    assert roadmap is not None
    assert roadmap["current_monthly"] == 0
    assert roadmap["projected_monthly"] == 0


def test_old_metrics_data_table_fallback():
    """Data table uses asking as optimal when optimal_pricing missing."""
    deck = _build_deck()
    slide_3 = deck["slides"][2]
    table = slide_3["viz_data"].get("data_table")
    assert table is not None
    assert len(table["rows"]) == 4  # All 4 unit types from EXPORT_DATA
    # For A1, optimal_asking should fall back to asking (1365 from EXPORT_DATA)
    a1_row = table["rows"][0]
    assert a1_row["optimal_asking"] == a1_row["asking"]


def test_old_metrics_waterfall_no_optimal_bar():
    """Rent waterfall omits Optimal bar when optimal_pricing missing."""
    deck = _build_deck()
    slide_4 = deck["slides"][3]
    waterfall_a1 = slide_4["viz_data"].get("waterfall_a1", [])
    labels = [bar["label"] for bar in waterfall_a1]
    assert "Optimal" not in labels  # No optimal bar without optimal_pricing


def test_old_metrics_narrative_fallback():
    """Narrative generation uses fallback with old metrics (mock client fails)."""
    deck = _build_deck()
    metadata = deck.get("metadata", {})
    # Should have used fallback since mock client raises ClaudeAPIError
    assert metadata.get("narrative_fallback") is True


def test_old_metrics_all_slides_have_layout():
    """Every slide has a layout template, even with degraded data."""
    deck = _build_deck()
    for slide in deck["slides"]:
        assert "layout" in slide, f"Slide {slide['slide_number']} missing layout"
        assert "template" in slide["layout"], (
            f"Slide {slide['slide_number']} missing layout template"
        )
