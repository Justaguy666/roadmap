"""
Unit tests for OpenAIProvider and error mapping.

Verifies that OpenAI-specific exceptions are properly caught
and mapped to domain/application port exceptions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from openai import APIError, APITimeoutError, AuthenticationError, RateLimitError

from roadmap.agents.schemas.goal_analysis import GoalAnalysisResult
from roadmap.application.ports.llm_provider import (
    LLMAuthenticationError,
    LLMMessage,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    MissingAPIKeyError,
)
from roadmap.infrastructure.llm.openai_provider import OpenAIProvider


class TestOpenAIProviderInitialization:
    def test_missing_api_key_raises_error(self) -> None:
        with patch("roadmap.infrastructure.llm.openai_provider.settings") as mock_settings:
            mock_settings.openai_api_key = ""
            with pytest.raises(MissingAPIKeyError) as exc_info:
                OpenAIProvider(api_key="")
            assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_explicit_key_accepted(self) -> None:
        with patch("roadmap.infrastructure.llm.openai_provider.OpenAI") as mock_openai, \
             patch("roadmap.infrastructure.llm.openai_provider.instructor"):
            provider = OpenAIProvider(api_key="sk-testkey123")
            assert provider.model == "gpt-4o"
            mock_openai.assert_called_once_with(api_key="sk-testkey123")


class TestOpenAIProviderErrorMapping:
    @pytest.fixture
    def mock_provider(self) -> OpenAIProvider:
        with patch("roadmap.infrastructure.llm.openai_provider.OpenAI"), \
             patch("roadmap.infrastructure.llm.openai_provider.instructor") as mock_instructor:
            mock_inst = MagicMock()
            mock_instructor.from_openai.return_value = mock_inst
            provider = OpenAIProvider(api_key="sk-test")
            provider._instructor_client = mock_inst
            return provider

    def test_authentication_error_mapped(self, mock_provider: OpenAIProvider) -> None:
        mock_provider._instructor_client.chat.completions.create.side_effect = AuthenticationError(
            message="Invalid API Key", response=MagicMock(), body=None
        )
        with pytest.raises(LLMAuthenticationError) as exc_info:
            mock_provider.complete(
                messages=[LLMMessage.user("Hello")],
                response_model=GoalAnalysisResult,
            )
        assert "authentication failed" in str(exc_info.value)

    def test_rate_limit_error_mapped(self, mock_provider: OpenAIProvider) -> None:
        mock_provider._instructor_client.chat.completions.create.side_effect = RateLimitError(
            message="Rate limit exceeded", response=MagicMock(), body=None
        )
        with pytest.raises(LLMRateLimitError) as exc_info:
            mock_provider.complete(
                messages=[LLMMessage.user("Hello")],
                response_model=GoalAnalysisResult,
            )
        assert "rate limit" in str(exc_info.value)

    def test_timeout_error_mapped(self, mock_provider: OpenAIProvider) -> None:
        mock_provider._instructor_client.chat.completions.create.side_effect = APITimeoutError(
            request=MagicMock()
        )
        with pytest.raises(LLMTimeoutError) as exc_info:
            mock_provider.complete(
                messages=[LLMMessage.user("Hello")],
                response_model=GoalAnalysisResult,
            )
        assert "timed out" in str(exc_info.value)

    def test_generic_api_error_mapped(self, mock_provider: OpenAIProvider) -> None:
        mock_provider._instructor_client.chat.completions.create.side_effect = APIError(
            message="Internal Server Error", request=MagicMock(), body=None
        )
        with pytest.raises(LLMProviderError):
            mock_provider.complete(
                messages=[LLMMessage.user("Hello")],
                response_model=GoalAnalysisResult,
            )
