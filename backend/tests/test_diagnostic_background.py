"""Test diagnostic background run lifecycle — property and portfolio.

These tests verify the diagnostic pipeline completes (or fails gracefully)
using mocked Claude calls, without requiring a live database.
"""
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.database import SessionLocal
from app.models.property import Property
from app.models.config import ClientConfig
from app.services.diagnostic_service import run_diagnostic
from app.services.claude_client import ClaudeClient, ClaudeAPIError


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def prop_b(db):
    return db.query(Property).filter_by(code="PROP-B").first()


class TestBackgroundPropertyRun:
    """Test property diagnostic run lifecycle with mocked Claude."""

    def test_background_run_completes(self, db, prop_b):
        """A diagnostic run with mocked Claude should reach COMPLETED status."""
        mock_client = MagicMock(spec=ClaudeClient)
        mock_client.call_json.return_value = {
            "unit_type_assessments": [
                {
                    "unit_type": "B1",
                    "health_score": 30,
                    "grade": "CRISIS",
                    "score_reasoning": "test",
                    "dominant_lever": "FILL",
                    "revenue_gap_monthly": 7625,
                    "root_cause": "vacancy",
                    "key_findings": ["test"],
                    "anomalies": [],
                    "recommended_actions": [],
                    "experiment_design": {
                        "recommended": False, "arms": [],
                        "observation_window_days": 14, "convergence_rule": "",
                        "rationale": "test",
                    },
                },
                {
                    "unit_type": "B2",
                    "health_score": 55,
                    "grade": "IMBALANCED",
                    "score_reasoning": "test",
                    "dominant_lever": "REPRICE",
                    "revenue_gap_monthly": 3000,
                    "root_cause": None,
                    "key_findings": ["test"],
                    "anomalies": [],
                    "recommended_actions": [],
                    "experiment_design": {
                        "recommended": False, "arms": [],
                        "observation_window_days": 14, "convergence_rule": "",
                        "rationale": "test",
                    },
                },
            ],
            "portfolio_assessment": {
                "summary": "test",
                "cross_unit_type_risks": [],
                "overall_portfolio_score": 45,
                "top_3_priorities": [],
            },
            "further_investigation": [],
        }

        from app.models.user import User
        user = db.query(User).filter_by(email="demo@example.com").first()

        result = run_diagnostic(
            db=db,
            property_id=str(prop_b.id),
            user_id=str(user.id),
            organization_id=str(user.organization_id),
            claude_client=mock_client,
            reference_date=date(2026, 3, 15),
        )

        assert result.status == "COMPLETED"
        assert result.metrics_json is not None
        assert result.flags_json is not None
        assert result.diagnosis_json is not None
        assert result.action_plan_json is not None
        assert result.total_ms is not None
        assert result.total_ms > 0

        # Cleanup
        db.rollback()

    def test_background_run_generic_exception_fails(self, db, prop_b):
        """Generic Exception (not ClaudeAPIError) results in FAILED status."""
        mock_client = MagicMock(spec=ClaudeClient)
        mock_client.call_json.side_effect = Exception("Simulated crash")

        from app.models.user import User
        user = db.query(User).filter_by(email="demo@example.com").first()

        result = run_diagnostic(
            db=db,
            property_id=str(prop_b.id),
            user_id=str(user.id),
            organization_id=str(user.organization_id),
            claude_client=mock_client,
            reference_date=date(2026, 3, 15),
        )

        assert result.status == "FAILED"
        assert result.error_message is not None

        db.rollback()

    def test_background_run_claude_api_error_uses_fallback(self, db, prop_b):
        """ClaudeAPIError triggers fallback diagnosis, not FAILED status."""
        mock_client = MagicMock(spec=ClaudeClient)
        mock_client.call_json.side_effect = ClaudeAPIError("API down")

        from app.models.user import User
        user = db.query(User).filter_by(email="demo@example.com").first()

        result = run_diagnostic(
            db=db,
            property_id=str(prop_b.id),
            user_id=str(user.id),
            organization_id=str(user.organization_id),
            claude_client=mock_client,
            reference_date=date(2026, 3, 15),
        )

        assert result.status == "COMPLETED"
        assert result.diagnosis_json is not None
        # Fallback diagnosis has specific structure
        assessments = result.diagnosis_json.get("unit_type_assessments", [])
        assert len(assessments) > 0

        db.rollback()


class TestBackgroundPortfolioRun:
    """Test portfolio diagnostic run lifecycle."""

    def test_portfolio_run_completes(self, db):
        """Portfolio diagnostic with mocked Claude completes."""
        from app.models.user import User
        from app.services.portfolio_diagnostic_service import run_portfolio_diagnostic

        user = db.query(User).filter_by(email="demo@example.com").first()

        mock_client = MagicMock(spec=ClaudeClient)
        mock_client.call_json.return_value = {
            "property_assessments": [],
            "portfolio_summary": {"total_gap": 0, "priorities": []},
            "phases": [
                {"phase_number": 1, "name": "Test", "days": "1-3", "actions": []},
            ],
        }

        result = run_portfolio_diagnostic(
            db=db,
            organization_id=str(user.organization_id),
            user_id=str(user.id),
            claude_client=mock_client,
        )

        assert result.status == "COMPLETED"
        assert result.scope == "portfolio"
        assert result.metrics_json is not None

        db.rollback()
