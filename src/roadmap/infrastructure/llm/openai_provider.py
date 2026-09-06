"""
OpenAI implementation of the LLMProvider port.

Uses official OpenAI Python SDK + Instructor for typed Pydantic completions.
All OpenAI-specific errors are translated to domain/application port exceptions.
"""

from __future__ import annotations

import time
from typing import TypeVar

import instructor
from instructor.core import InstructorRetryException
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from pydantic import BaseModel, ValidationError

from roadmap.application.ports.llm_provider import (
    LLMAuthenticationError,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
    MissingAPIKeyError,
)
from roadmap.config.settings import settings
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(LLMProvider):
    """
    Concrete adapter for OpenAI utilizing Instructor for guaranteed schema validation.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        resolved_key = api_key or settings.openai_api_key
        if not resolved_key or not resolved_key.strip():
            raise MissingAPIKeyError(provider="OpenAI", env_var="OPENAI_API_KEY")

        self.provider_name = "openai"
        self.model = model or settings.llm_model or settings.openai_model or "gpt-4o"
        self.model_name = self.model
        self.default_temperature = temperature if temperature is not None else settings.llm_temperature
        self.default_max_tokens = max_tokens or settings.llm_max_tokens
        self.default_max_retries = max_retries or settings.llm_max_retries

        self._raw_client = OpenAI(api_key=resolved_key)
        self._instructor_client = instructor.from_openai(self._raw_client)

    def complete(
        self,
        messages: list[LLMMessage],
        response_model: type[T],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> T:
        """
        Request structured completion validated against the response_model schema.
        Automatically retries on validation failure up to max_retries.
        """
        formatted_messages = [m.to_dict() for m in messages]
        temp = temperature if temperature is not None else self.default_temperature
        tokens = max_tokens or self.default_max_tokens
        retries = self.default_max_retries

        start_time = time.perf_counter()
        logger.info(
            "Requesting structured LLM completion",
            model=self.model,
            response_model=response_model.__name__,
            num_messages=len(messages),
        )

        try:
            result = self._instructor_client.chat.completions.create(
                model=self.model,
                response_model=response_model,
                messages=formatted_messages,  # type: ignore[arg-type]
                temperature=temp,
                max_tokens=tokens,
                max_retries=retries,
            )
            elapsed = time.perf_counter() - start_time
            logger.info(
                "Structured LLM completion successful",
                model=self.model,
                response_model=response_model.__name__,
                duration_seconds=round(elapsed, 2),
            )
            return result
        except AuthenticationError as e:
            logger.error("OpenAI authentication error", error=str(e))
            raise LLMAuthenticationError(f"OpenAI authentication failed: {e}") from e
        except RateLimitError as e:
            logger.error("OpenAI rate limit / quota exceeded", error=str(e))
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except APITimeoutError as e:
            logger.error("OpenAI request timed out", error=str(e))
            raise LLMTimeoutError(f"OpenAI request timed out: {e}") from e
        except (InstructorRetryException, ValidationError) as e:
            logger.error("LLM structured output validation failed", error=str(e))
            raise LLMValidationError(
                model_name=self.model,
                attempts=retries,
                last_error=str(e),
            ) from e
        except (APIConnectionError, APIError) as e:
            logger.error("OpenAI API error", error=str(e))
            raise LLMProviderError(f"OpenAI API error: {e}") from e
        except Exception as e:
            logger.error("Unexpected error during LLM completion", error=str(e))
            raise LLMProviderError(f"Unexpected LLM completion error: {e}") from e

    def complete_text(
        self,
        messages: list[LLMMessage],
        temperature: float | None = None,
    ) -> str:
        """Execute free-text completion without response schema enforcement."""
        formatted_messages = [m.to_dict() for m in messages]
        temp = temperature if temperature is not None else self.default_temperature

        start_time = time.perf_counter()
        logger.info(
            "Requesting free-text LLM completion",
            model=self.model,
            num_messages=len(messages),
        )

        try:
            resp = self._raw_client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,  # type: ignore[arg-type]
                temperature=temp,
            )
            elapsed = time.perf_counter() - start_time
            content = resp.choices[0].message.content or ""
            logger.info(
                "Free-text LLM completion successful",
                model=self.model,
                duration_seconds=round(elapsed, 2),
            )
            return content
        except AuthenticationError as e:
            raise LLMAuthenticationError(f"OpenAI authentication failed: {e}") from e
        except RateLimitError as e:
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}") from e
        except APITimeoutError as e:
            raise LLMTimeoutError(f"OpenAI request timed out: {e}") from e
        except Exception as e:
            raise LLMProviderError(f"OpenAI completion error: {e}") from e
