"""Tests for LLM failure classification mapping across exception types."""


from roadmap.application.ports.llm_provider import (
    ApplicationBudgetExceededError,
    LLMAuthenticationError,
    LLMDailyQuotaExceededError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
    MissingAPIKeyError,
    ProviderQuotaUnavailableError,
)
from roadmap.domain.value_objects.enums import FailureCategory


def test_exception_failure_categories() -> None:
    assert LLMProviderError.failure_category == FailureCategory.UNKNOWN_PROVIDER_ERROR
    assert MissingAPIKeyError.failure_category == FailureCategory.AUTHENTICATION_ERROR
    assert LLMAuthenticationError.failure_category == FailureCategory.AUTHENTICATION_ERROR
    assert LLMRateLimitError.failure_category == FailureCategory.PROVIDER_RATE_LIMITED
    assert LLMDailyQuotaExceededError.failure_category == FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED
    assert LLMTimeoutError.failure_category == FailureCategory.TRANSIENT_PROVIDER_ERROR
    assert LLMValidationError.failure_category == FailureCategory.INVALID_REQUEST
    assert ApplicationBudgetExceededError.failure_category == FailureCategory.APPLICATION_BUDGET_EXCEEDED
    assert ProviderQuotaUnavailableError.failure_category == FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED


def test_exception_instances_have_category() -> None:
    e1 = ApplicationBudgetExceededError(workflow="research", allocated=5, used=5)
    assert e1.failure_category == FailureCategory.APPLICATION_BUDGET_EXCEEDED

    e2 = ProviderQuotaUnavailableError(provider="gemini", model="gemini-3.7-flash")
    assert e2.failure_category == FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED
