"""
Unit tests for GeminiProvider and error mapping.

Verifies that Gemini-specific exceptions are properly caught
and mapped to domain/application port exceptions.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from google.genai.errors import APIError, ClientError

from roadmap.agents.schemas.goal_analysis import (
    CompetencyDraft,
    GoalAnalysisResult,
    RequiredSkillDraft,
)
from roadmap.application.ports.llm_provider import (
    LLMAuthenticationError,
    LLMMessage,
    LLMProviderError,
    LLMRateLimitError,
    LLMValidationError,
    MissingAPIKeyError,
)
from roadmap.infrastructure.llm.gemini_provider import DEFAULT_GEMINI_MODEL, GeminiProvider


class TestGeminiProviderInitialization:
    def test_missing_api_key_raises_error(self) -> None:
        with patch("roadmap.infrastructure.llm.gemini_provider.settings") as mock_settings:
            mock_settings.gemini_api_key = ""
            with pytest.raises(MissingAPIKeyError) as exc_info:
                GeminiProvider(api_key="")
            assert "GEMINI_API_KEY" in str(exc_info.value)

    def test_explicit_key_accepted(self) -> None:
        with patch("roadmap.infrastructure.llm.gemini_provider.genai.Client") as mock_client, \
             patch("roadmap.infrastructure.llm.gemini_provider.settings") as mock_settings:
            mock_settings.llm_model = ""
            mock_settings.gemini_model = DEFAULT_GEMINI_MODEL
            provider = GeminiProvider(api_key="gemini-test-key-123")
            assert provider.model == DEFAULT_GEMINI_MODEL
            mock_client.assert_called_once_with(api_key="gemini-test-key-123")


class TestGeminiProviderCompletions:
    @pytest.fixture
    def mock_provider(self) -> GeminiProvider:
        with patch("roadmap.infrastructure.llm.gemini_provider.genai.Client") as mock_client:
            mock_instance = MagicMock()
            mock_client.return_value = mock_instance
            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_instance
            return provider

    def test_successful_complete(self, mock_provider: GeminiProvider) -> None:
        dummy_data = {
            "interpreted_goal": "Become a senior backend developer.",
            "target_role": "Backend Engineer",
            "competencies": [
                CompetencyDraft(
                    name="API Design",
                    description="Building RESTful services",
                    skill_names=["FastAPI"],
                ).model_dump()
            ],
            "required_skills": [
                RequiredSkillDraft(
                    name="Python",
                    description="Core programming language",
                ).model_dump()
            ],
            "confidence": 0.9,
        }
        mock_resp = MagicMock()
        mock_resp.text = json.dumps(dummy_data)
        mock_provider._client.models.generate_content.return_value = mock_resp

        result = mock_provider.complete(
            messages=[
                LLMMessage.system("You are a career expert."),
                LLMMessage.user("I want to become a backend engineer."),
            ],
            response_model=GoalAnalysisResult,
        )

        assert isinstance(result, GoalAnalysisResult)
        assert result.target_role == "Backend Engineer"
        assert result.interpreted_goal == "Become a senior backend developer."

    def test_complete_text_successful(self, mock_provider: GeminiProvider) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "Here is an explanation of Python."
        mock_provider._client.models.generate_content.return_value = mock_resp

        text = mock_provider.complete_text(
            messages=[LLMMessage.user("Explain Python")]
        )
        assert text == "Here is an explanation of Python."

    def test_authentication_error_mapped(self, mock_provider: GeminiProvider) -> None:
        mock_provider._client.models.generate_content.side_effect = ClientError(
            400,
            {"error": {"message": "API_KEY_INVALID: The provided API key is invalid."}},
        )
        with pytest.raises(LLMAuthenticationError) as exc_info:
            mock_provider.complete(
                messages=[LLMMessage.user("Hello")],
                response_model=GoalAnalysisResult,
            )
        assert "authentication failed" in str(exc_info.value)

    def test_rate_limit_error_mapped(self, mock_provider: GeminiProvider) -> None:
        mock_provider._client.models.generate_content.side_effect = ClientError(
            429,
            {"error": {"message": "RESOURCE_EXHAUSTED: Quota exceeded"}},
        )
        with pytest.raises(LLMRateLimitError) as exc_info:
            mock_provider.complete(
                messages=[LLMMessage.user("Hello")],
                response_model=GoalAnalysisResult,
            )
        assert "quota/rate limit exceeded" in str(exc_info.value)

    def test_validation_error_on_invalid_json(self, mock_provider: GeminiProvider) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "invalid json {{"
        mock_provider._client.models.generate_content.return_value = mock_resp

        with pytest.raises(LLMValidationError) as exc_info:
            mock_provider.complete(
                messages=[LLMMessage.user("Hello")],
                response_model=GoalAnalysisResult,
            )
        assert "Failed to parse or validate schema" in str(exc_info.value)

    def test_generic_api_error_mapped(self, mock_provider: GeminiProvider) -> None:
        mock_provider._client.models.generate_content.side_effect = APIError(
            500,
            {"error": {"message": "Unknown Google API error"}},
        )
        with pytest.raises(LLMProviderError):
            mock_provider.complete(
                messages=[LLMMessage.user("Hello")],
                response_model=GoalAnalysisResult,
            )
