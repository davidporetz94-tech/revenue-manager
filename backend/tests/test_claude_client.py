"""Test Claude API client — JSON parsing, retry logic, error handling.

Mocks the Anthropic API to avoid live API calls in tests.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.claude_client import ClaudeClient, ClaudeAPIError


class TestJSONParsing:
    def test_parse_clean_json(self):
        text = '{"key": "value", "num": 42}'
        result = ClaudeClient._parse_json(text)
        assert result == {"key": "value", "num": 42}

    def test_parse_json_with_code_fences(self):
        text = '```json\n{"key": "value"}\n```'
        result = ClaudeClient._parse_json(text)
        assert result == {"key": "value"}

    def test_parse_json_with_plain_fences(self):
        text = '```\n{"key": "value"}\n```'
        result = ClaudeClient._parse_json(text)
        assert result == {"key": "value"}

    def test_parse_json_with_whitespace(self):
        text = '\n  {"key": "value"}  \n'
        result = ClaudeClient._parse_json(text)
        assert result == {"key": "value"}

    def test_parse_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            ClaudeClient._parse_json("not json at all")


class TestCallJSON:
    def _mock_response(self, text: str):
        """Create a mock Anthropic response."""
        block = MagicMock()
        block.type = "text"
        block.text = text
        response = MagicMock()
        response.content = [block]
        return response

    @patch("app.services.claude_client.anthropic.Anthropic")
    def test_successful_call(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = self._mock_response(
            '{"diagnosis": "healthy", "score": 85}'
        )

        client = ClaudeClient(api_key="test-key")
        result = client.call_json("system prompt", "user message")

        assert result == {"diagnosis": "healthy", "score": 85}
        mock_client.messages.create.assert_called_once()

    @patch("app.services.claude_client.anthropic.Anthropic")
    def test_retry_on_json_error(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # First call returns invalid JSON, second returns valid
        mock_client.messages.create.side_effect = [
            self._mock_response("not valid json"),
            self._mock_response('{"valid": true}'),
        ]

        client = ClaudeClient(api_key="test-key")
        result = client.call_json("system", "user", max_retries=1)
        assert result == {"valid": True}
        assert mock_client.messages.create.call_count == 2

    @patch("app.services.claude_client.anthropic.Anthropic")
    def test_raises_after_all_retries(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # Both calls return invalid JSON
        mock_client.messages.create.side_effect = [
            self._mock_response("bad json 1"),
            self._mock_response("bad json 2"),
        ]

        client = ClaudeClient(api_key="test-key")
        with pytest.raises(ClaudeAPIError):
            client.call_json("system", "user", max_retries=1)

    @patch("app.services.claude_client.anthropic.Anthropic")
    def test_handles_code_fences_in_response(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = self._mock_response(
            '```json\n{"fenced": true}\n```'
        )

        client = ClaudeClient(api_key="test-key")
        result = client.call_json("system", "user")
        assert result == {"fenced": True}

    @patch("app.services.claude_client.anthropic.Anthropic")
    def test_empty_response_raises(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = self._mock_response("")

        client = ClaudeClient(api_key="test-key")
        with pytest.raises(ClaudeAPIError, match="Empty response"):
            client.call_json("system", "user")
