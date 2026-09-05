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


class MissingAPIKeyError(LLMProviderError):
    """Raised when an API key is required but missing."""

    def __init__(self, provider: str = "OpenAI", env_var: str = "OPENAI_API_KEY") -> None:
        self.provider = provider
        self.env_var = env_var
        super().__init__(
            f"{provider} API key not found. Please set the {env_var} environment variable "
            f"or specify it in your .env file."
        )


class LLMAuthenticationError(LLMProviderError):
    """Raised when authentication with the LLM provider fails."""


class LLMRateLimitError(LLMProviderError):
    """Raised when rate limits or quotas are exceeded."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMDailyQuotaExceededError(LLMRateLimitError):
    """Raised when the daily quota limit for the LLM model/project has been completely exhausted."""


class LLMTimeoutError(LLMProviderError):
    """Raised when the LLM request times out."""


class LLMValidationError(LLMProviderError):
    """Raised when LLM output cannot be validated against the schema."""

    def __init__(self, model_name: str, attempts: int, last_error: str) -> None:
        self.model_name = model_name
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"LLM output for {model_name} failed validation after {attempts} attempts: {last_error}"
        )
