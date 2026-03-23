"""Test chat API endpoint — Claude Q&A over property metrics."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.diagnostic import AuditLog
from app.services.claude_client import ClaudeClient, ClaudeAPIError

client = TestClient(app)


@pytest.fixture(scope="module")
def prop_id():
    """Get first property ID for chat tests."""
    res = client.get("/api/v1/properties")
    return res.json()[0]["id"]


class TestChatEndpoint:
    """Test /properties/{id}/chat endpoint."""

    @patch("app.api.chat.ClaudeClient")
    def test_chat_returns_response(self, MockClaudeClient, prop_id):
        """Chat returns structured response with sources."""
        mock_instance = MagicMock()
        mock_instance.call_text.return_value = "Your B1 units have 79% occupancy."
        MockClaudeClient.return_value = mock_instance

        res = client.post(f"/api/v1/properties/{prop_id}/chat", json={
            "message": "What's the occupancy for B1?",
        })
        assert res.status_code == 200
        data = res.json()
        assert "response" in data
        assert "sources" in data
        assert "metrics" in data["sources"]
        assert "flags" in data["sources"]

    @patch("app.api.chat.ClaudeClient")
    def test_chat_claude_failure_fallback(self, MockClaudeClient, prop_id):
        """When Claude fails, fallback text is returned."""
        mock_instance = MagicMock()
        mock_instance.call_text.side_effect = ClaudeAPIError("API down")
        MockClaudeClient.return_value = mock_instance

        res = client.post(f"/api/v1/properties/{prop_id}/chat", json={
            "message": "Tell me about pricing.",
        })
        assert res.status_code == 200
        data = res.json()
        assert "unable to analyze" in data["response"].lower()

    @patch("app.api.chat.ClaudeClient")
    def test_chat_returns_200_with_valid_shape(self, MockClaudeClient, prop_id):
        """Chat endpoint returns 200 with response and sources fields."""
        mock_instance = MagicMock()
        mock_instance.call_text.return_value = "Test response for audit."
        MockClaudeClient.return_value = mock_instance

        res = client.post(f"/api/v1/properties/{prop_id}/chat", json={
            "message": "Test audit query",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["response"] == "Test response for audit."
        assert isinstance(data["sources"], list)
        assert len(data["sources"]) >= 2  # at least metrics + flags

    def test_chat_invalid_property_404(self):
        """Non-existent property returns 404."""
        res = client.post(
            "/api/v1/properties/00000000-0000-0000-0000-000000000000/chat",
            json={"message": "hello"},
        )
        assert res.status_code == 404

    def test_chat_metrics_summary_construction(self, prop_id):
        """Verify _build_metrics_summary output shape."""
        from app.api.chat import _build_metrics_summary
        from app.services.metrics_engine import compute_property_metrics
        from app.models.config import ClientConfig
        from datetime import date

        db = SessionLocal()
        config = db.query(ClientConfig).filter_by(
            property_id=prop_id, is_active=True
        ).first()
        config_dict = {
            k: getattr(config, k) or {}
            for k in [
                "occupancy_thresholds", "exposure_thresholds", "pricing_tolerance",
                "concession_policy", "renewal_policy", "lease_term_policy",
                "experiment_policy", "amenity_benchmarks",
            ]
        }
        metrics = compute_property_metrics(db, prop_id, config_dict, date(2026, 3, 15))
        db.close()

        summary = _build_metrics_summary(metrics)
        assert len(summary) >= 1
        for code, data in summary.items():
            assert "occupancy" in data
            assert "asking" in data
            assert "daily_burn" in data
            assert "dom" in data
            # Revenue optimization fields
            assert "optimal_asking" in data
            assert "elasticity_direction" in data
            assert "revenue_gap_monthly" in data
            assert "grade" in data
            assert "gap_components" in data
