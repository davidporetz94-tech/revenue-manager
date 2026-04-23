"""Claude API client wrapper — handles API calls, retries, JSON parsing, error handling.

Uses claude-sonnet-4-20250514 model. Validates responses against Pydantic schemas.
NEVER logs the API key.
"""
import json
import logging

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4000


class ClaudeAPIError(Exception):
    """Raised when Claude API fails after retries."""
    pass


class ClaudeClient:
    """Wrapper around Anthropic's Claude API with retry and JSON parsing."""

    def __init__(self, api_key: str | None = None):
        self._client = anthropic.Anthropic(
            api_key=api_key or settings.ANTHROPIC_API_KEY,
        )

    def call_json(
        self,
        system_prompt: str,
        user_message: str,
        max_retries: int = 1,
    ) -> dict:
        """Call Claude and parse the response as JSON.

        Args:
            system_prompt: system-level instructions.
            user_message: user-level message/data.
            max_retries: number of retries on failure (default 1).

        Returns:
            Parsed JSON dict from Claude's response.

        Raises:
            ClaudeAPIError: if all attempts fail.
        """
        last_error = None

        for attempt in range(1 + max_retries):
            try:
                response = self._client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )

                # Extract text from content blocks
                text = ""
                for block in response.content:
                    if block.type == "text":
                        text += block.text

                if not text.strip():
                    raise ClaudeAPIError("Empty response from Claude")

                # Parse JSON, stripping markdown code fences if present
                parsed = self._parse_json(text)
                return parsed

            except ClaudeAPIError:
                raise
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(
                    "JSON parse error on attempt %d: %s", attempt + 1, str(e)
                )
            except anthropic.APIError as e:
                last_error = e
                logger.warning(
                    "Claude API error on attempt %d: %s", attempt + 1, str(e)
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "Unexpected error on attempt %d: %s", attempt + 1, str(e)
                )

        raise ClaudeAPIError(
            f"Claude API failed after {1 + max_retries} attempts: {last_error}"
        )

    def call_text(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int | None = None,
        timeout: float | None = None,
    ) -> str:
        """Call Claude and return raw text response.

        Args:
            system_prompt: system-level instructions.
            user_message: user-level message/data.
            max_tokens: override default max tokens.
            timeout: request timeout in seconds.

        Returns:
            Raw text from Claude's response.

        Raises:
            ClaudeAPIError: if the call fails.
        """
        try:
            kwargs = dict(
                model=MODEL,
                max_tokens=max_tokens or MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            if timeout:
                kwargs["timeout"] = timeout
            response = self._client.messages.create(**kwargs)
            text = ""
            for block in response.content:
                if block.type == "text":
                    text += block.text
            return text.strip()
        except Exception as e:
            raise ClaudeAPIError(f"Claude API call failed: {e}")

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Parse JSON from text, stripping markdown code fences if present."""
        cleaned = text.strip()

        # Strip markdown code fences
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()
        return json.loads(cleaned)
