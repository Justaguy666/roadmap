"""
Application ports: LLMProvider interface.

The domain and application layers depend only on this protocol.
The concrete implementation (OpenAI, Anthropic, etc.) lives in
src/roadmap/infrastructure/llm/.

Design:
  - Typed structured output via Pydantic response_model
  - The implementation must validate and retry on schema errors
  - Never pass raw LLM text to application/domain logic
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

from roadmap.domain.value_objects.enums import FailureCategory

T = TypeVar("T", bound=BaseModel)


class LLMMessage:
    """A single message in an LLM conversation."""

    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content

    @staticmethod
    def system(content: str) -> LLMMessage:
        return LLMMessage("system", content)

    @staticmethod
    def user(content: str) -> LLMMessage:
        return LLMMessage("user", content)

    @staticmethod
    def assistant(content: str) -> LLMMessage:
        return LLMMessage("assistant", content)

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class LLMUsage:
    """Token usage metadata from an LLM call."""

    def __init__(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


class LLMProvider(Protocol):
    """
    Port interface for LLM providers.

    The implementation must:
    1. Accept a Pydantic model class as response_model.
    2. Return a fully validated instance of that model.
    3. Retry automatically on schema validation failure (up to max_retries).
    4. Never return unvalidated text as application state.
    """

    provider_name: str
    model_name: str

    def complete(
        self,
        messages: list[LLMMessage],
        response_model: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """
        Perform a structured completion and return a validated Pydantic model.

        Args:
            messages: Conversation messages.
            response_model: The Pydantic model class to validate the response against.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.

        Returns:
            A fully validated instance of response_model.

        Raises:
            LLMValidationError: If the response cannot be validated after max retries.
            LLMProviderError: If the API call fails permanently.
        """
        ...

    def complete_text(
        self,
        messages: list[LLMMessage],
        temperature: float | None = None,
    ) -> str:
        """
        Perform a free-text completion (for explanations, not structured data).

        Returns a raw string. Use only for user-facing explanations,
        never for driving application logic.
        """
        ...


class LLMProviderError(Exception):
    """Base exception raised when the LLM provider cannot complete a request."""

    failure_category: FailureCategory = FailureCategory.UNKNOWN_PROVIDER_ERROR


class MissingAPIKeyError(LLMProviderError):
    """Raised when an API key is required but missing."""

    failure_category = FailureCategory.AUTHENTICATION_ERROR

    def __init__(self, provider: str = "OpenAI", env_var: str = "OPENAI_API_KEY") -> None:
        self.provider = provider
        self.env_var = env_var
        super().__init__(
            f"{provider} API key not found. Please set the {env_var} environment variable "
            f"or specify it in your .env file."
        )


class LLMAuthenticationError(LLMProviderError):
    """Raised when authentication with the LLM provider fails."""

    failure_category = FailureCategory.AUTHENTICATION_ERROR


class LLMRateLimitError(LLMProviderError):
    """Raised when rate limits or quotas are exceeded."""

    failure_category = FailureCategory.PROVIDER_RATE_LIMITED

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMDailyQuotaExceededError(LLMRateLimitError):
    """Raised when the daily quota limit for the LLM model/project has been completely exhausted."""

    failure_category = FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED


class LLMTimeoutError(LLMProviderError):
    """Raised when the LLM request times out."""

    failure_category = FailureCategory.TRANSIENT_PROVIDER_ERROR


class LLMValidationError(LLMProviderError):
    """Raised when LLM output cannot be validated against the schema."""

    failure_category = FailureCategory.INVALID_REQUEST

    def __init__(self, model_name: str, attempts: int, last_error: str) -> None:
        self.model_name = model_name
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"LLM output for {model_name} failed validation after {attempts} attempts: {last_error}"
        )


class ApplicationBudgetExceededError(LLMProviderError):
    """Raised when the application request budget is exhausted before calling the provider."""

    failure_category = FailureCategory.APPLICATION_BUDGET_EXCEEDED

    def __init__(
        self,
        workflow: str,
        allocated: int,
        used: int,
        required: int = 1,
        message: str | None = None,
    ) -> None:
        self.workflow = workflow
        self.allocated = allocated
        self.used = used
        self.required = required
        msg = message or (
            f"LLM application budget exhausted for workflow '{workflow}'. "
            f"Allocated: {allocated}, Used: {used}, Required: {required}."
        )
        super().__init__(msg)


class ProviderQuotaUnavailableError(LLMProviderError):
    """Raised when the provider is in an active quota cooldown and cannot accept requests."""

    failure_category = FailureCategory.PROVIDER_DAILY_QUOTA_EXCEEDED

    def __init__(
        self,
        provider: str,
        model: str,
        message: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        msg = message or (
            f"Provider quota unavailable: {provider} daily quota for model '{model}' has been exhausted. "
            "No provider request was attempted."
        )
        super().__init__(msg)
