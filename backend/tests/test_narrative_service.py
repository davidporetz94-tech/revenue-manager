"""Test narrative service — prompt construction, fallback, consistency checks."""
import json
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.database import SessionLocal
from app.models.property import Property
from app.models.config import ClientConfig
from app.services.metrics_engine import compute_property_metrics
from app.services.flag_generator import generate_flags
from app.services.narrative_service import (
    generate_narratives,
    validate_narrative_consistency,
    _generate_fallback_narratives,
)
from app.services.slide_deck_service import assemble_slide_deck
from app.services.claude_client import ClaudeClient, ClaudeAPIError

REF_DATE = date(2026, 3, 15)

# Mock Claude responses for narratives
MOCK_DIAG_NARRATIVE = {
    "slide_2_headline": "Your portfolio has 18 vacant units costing $27,330 per month with B1 in crisis.",
    "slide_2_findings": [
        "B1 asking $91 above every comp with 25% exposure",
        "B2 priced at comps but 6 units sitting vacant 28 days",
        "A1 healthy at 96% occupancy with $96 loss-to-lease upside",
    ],
    "slide_4_narrative": "Your A1 units are performing well at 96% occupancy with asking rent of $1,365 just $12 above comps. Your A2 units need attention at 86% occupancy with $235 daily vacancy burn.",
    "slide_5_narrative": "Your B1 units are in crisis at 79% occupancy, asking $1,525 which is $91 above every comp at $1,434. Exposure has hit 25% and is deteriorating. Your B2 units present a puzzle: priced competitively at $1,654 against $1,662 comps, yet 6 units sit vacant averaging 28 days.",
    "slide_6_narrative": "B1 occupancy has dropped from 88% to 79% in just 3 months while comps fell $41. A2 shows a concerning 6-point decline from 92% to 86%. A1 remains stable at 96%.",
    "slide_7_narrative": "Your portfolio burns $911 per day in vacancy costs totaling $27,330 per month. B2 carries the highest dollar exposure at $9,924 monthly despite being priced at comps.",
    "slide_11_narrative": "B2 tour conversion rates need investigation. If units are getting traffic but not converting, the issue is likely unit condition or leasing process rather than pricing.",
    "slide_12_summary": "Immediate action on B1 pricing and B2 experimentation can reduce your $911 daily burn rate. The 30-day plan targets $8,199 in monthly savings through strategic pricing adjustments.",
}

MOCK_ACTION_NARRATIVE = {
    "slide_8_narrative": "The 30-day plan addresses your $911 daily vacancy burn through 4 phases starting with B1 price reduction and B2 experimentation.",
    "slide_9_narrative": "In the first 3 days, reduce B1 asking from $1,525 to $1,475 and launch a three-arm experiment on B2 testing $1,654 control versus $1,600 price cut versus $1,654 with 2 weeks free.",
    "slide_10_narrative": "At Day 15, if 2 or more B1 units have leased at $1,475, hold that price. If zero have leased, reduce to $1,434 matching comps. For B2, if the price test arm leases faster, converge all units to $1,600.",
}


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def combined_metrics(db):
    all_ut = {}
    portfolio_total = {"total_units": 0, "total_vacant": 0, "total_monthly_vacancy_cost": 0}
    for code in ("PROP-A", "PROP-B"):
        prop = db.query(Property).filter_by(code=code).first()
        config = db.query(ClientConfig).filter_by(property_id=prop.id, is_active=True).first()
        cd = {k: getattr(config, k) or {} for k in [
            "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
            "concession_policy", "renewal_policy", "lease_term_policy",
            "experiment_policy", "amenity_benchmarks",
        ]}
        m = compute_property_metrics(db, str(prop.id), cd, REF_DATE)
        all_ut.update(m["unit_type_metrics"])
        pm = m["portfolio_metrics"]
        portfolio_total["total_units"] += pm["total_units"]
        portfolio_total["total_vacant"] += pm["total_vacant"]
        portfolio_total["total_monthly_vacancy_cost"] += pm["total_monthly_vacancy_cost"]
    total_occ = sum(m["occupancy_metrics"]["occupied"] for m in all_ut.values())
    portfolio_total["blended_occupancy"] = total_occ / portfolio_total["total_units"]
    portfolio_total["worst_performing_unit_type"] = "B1"
    portfolio_total["best_performing_unit_type"] = "A1"
    return {"unit_type_metrics": all_ut, "portfolio_metrics": portfolio_total}


class TestFallbackNarratives:
    def test_fallback_generates_all_keys(self, combined_metrics):
        narratives = _generate_fallback_narratives({}, {}, combined_metrics)
        required_keys = [
            "slide_2_headline", "slide_2_findings",
            "slide_4_narrative", "slide_5_narrative",
            "slide_6_narrative", "slide_7_narrative",
            "slide_8_narrative", "slide_9_narrative", "slide_10_narrative",
            "slide_11_narrative", "slide_12_summary",
        ]
        for key in required_keys:
            assert key in narratives, f"Missing key: {key}"

    def test_fallback_headline_mentions_vacancy(self, combined_metrics):
        narratives = _generate_fallback_narratives({}, {}, combined_metrics)
        assert "18" in narratives["slide_2_headline"]  # 18 vacant units

    def test_fallback_slide7_mentions_daily_burn(self, combined_metrics):
        narratives = _generate_fallback_narratives({}, {}, combined_metrics)
        assert "911" in narratives["slide_7_narrative"]

    def test_fallback_findings_count(self, combined_metrics):
        narratives = _generate_fallback_narratives({}, {}, combined_metrics)
        assert len(narratives["slide_2_findings"]) == 3


class TestNarrativeConsistency:
    def test_valid_narrative_no_issues(self, combined_metrics):
        """A narrative with only known dollar amounts should have zero issues."""
        narrative = {
            "slide_5_narrative": "B1 asking $1,525 is $91 above comps at $1,434. Daily burn is $254.",
            "slide_7_narrative": "Total monthly vacancy cost is $27,330 at $911 per day.",
        }
        issues = validate_narrative_consistency(narrative, combined_metrics)
        assert len(issues) == 0

    def test_unknown_amount_flagged(self, combined_metrics):
        """A narrative with an invented dollar amount should be flagged."""
        narrative = {
            "slide_5_narrative": "B1 needs to reduce to $1,399 immediately.",
        }
        issues = validate_narrative_consistency(narrative, combined_metrics)
        flagged_amounts = [i["amount"] for i in issues]
        assert "$1,399" in flagged_amounts


class TestSlideDeckAssembly:
    def test_12_slides_with_fallback(self, combined_metrics):
        """Slide deck assembles 12 slides using fallback narratives."""
        mock_client = MagicMock(spec=ClaudeClient)
        mock_client.call_json.side_effect = ClaudeAPIError("mocked failure")

        deck = assemble_slide_deck(
            run_id="test-run-id",
            property_name="Test Property",
            metrics=combined_metrics,
            diagnosis={"unit_type_assessments": [], "portfolio_assessment": {"overall_portfolio_score": 50}, "further_investigation": []},
            action_plan={"phases": [{"phase_number": 1, "name": "P1", "days": "1-3", "actions": []}], "decision_points": [], "experiment_summary": []},
            claude_client=mock_client,
        )

        assert len(deck["slides"]) == 12
        assert deck["metadata"]["narrative_fallback"] is True

    def test_all_slides_have_narrative_and_viz(self, combined_metrics):
        """Every slide must have non-null narrative."""
        mock_client = MagicMock(spec=ClaudeClient)
        mock_client.call_json.side_effect = ClaudeAPIError("mocked failure")

        deck = assemble_slide_deck(
            run_id="test-run-id",
            property_name="Test Property",
            metrics=combined_metrics,
            diagnosis={"unit_type_assessments": [], "portfolio_assessment": {"overall_portfolio_score": 50}, "further_investigation": []},
            action_plan={"phases": [{"phase_number": 1, "name": "P1", "days": "1-3", "actions": []}], "decision_points": [], "experiment_summary": []},
            claude_client=mock_client,
        )

        for slide in deck["slides"]:
            assert slide["narrative"] is not None, f"Slide {slide['slide_number']} has null narrative"

    def test_slide_numbers_sequential(self, combined_metrics):
        mock_client = MagicMock(spec=ClaudeClient)
        mock_client.call_json.side_effect = ClaudeAPIError("mocked")
        deck = assemble_slide_deck(
            run_id="x", property_name="X", metrics=combined_metrics,
            diagnosis={"unit_type_assessments": [], "portfolio_assessment": {"overall_portfolio_score": 50}, "further_investigation": []},
            action_plan={"phases": [], "decision_points": [], "experiment_summary": []},
            claude_client=mock_client,
        )
        numbers = [s["slide_number"] for s in deck["slides"]]
        assert numbers == list(range(1, 13))

    def test_successful_narrative_generation(self, combined_metrics):
        """When Claude succeeds, narratives are populated from Claude response."""
        mock_client = MagicMock(spec=ClaudeClient)
        mock_client.call_json.side_effect = [MOCK_DIAG_NARRATIVE, MOCK_ACTION_NARRATIVE]

        deck = assemble_slide_deck(
            run_id="test-ok", property_name="Property B", metrics=combined_metrics,
            diagnosis={"unit_type_assessments": [], "portfolio_assessment": {"overall_portfolio_score": 42}, "further_investigation": []},
            action_plan={"phases": [{"phase_number": 1, "name": "Phase 1", "days": "1-3", "actions": []}], "decision_points": [], "experiment_summary": []},
            claude_client=mock_client,
        )

        assert deck["metadata"]["narrative_fallback"] is False
        # Check slide 5 narrative contains B1 content
        slide5 = deck["slides"][4]
        assert "$91" in slide5["narrative"]["analysis"]
        assert "$1,525" in slide5["narrative"]["analysis"]
