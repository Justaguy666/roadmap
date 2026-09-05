"""
Google Gemini implementation of the LLMProvider port.

Uses the official google-genai SDK for native typed Pydantic completions.
All Gemini/Google API errors are translated to domain/application port exceptions.
"""

from __future__ import annotations

import json
import time
from typing import TypeVar

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError, ServerError
from pydantic import BaseModel, ValidationError

from roadmap.application.ports.llm_provider import (
    LLMAuthenticationError,
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMValidationError,
    MissingAPIKeyError,
)
from roadmap.config.settings import settings
from roadmap.shared.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


class GeminiProvider(LLMProvider):
    """
    Concrete adapter for Google Gemini utilizing native response_schema validation.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        resolved_key = api_key or settings.gemini_api_key
        if not resolved_key or not resolved_key.strip():
            raise MissingAPIKeyError(provider="Gemini", env_var="GEMINI_API_KEY")

        self.model = model or settings.llm_model or settings.gemini_model or DEFAULT_GEMINI_MODEL
        self.default_temperature = temperature if temperature is not None else settings.llm_temperature
        self.default_max_tokens = max_tokens or settings.llm_max_tokens
        self.default_max_retries = max_retries or settings.llm_max_retries

        self._client = genai.Client(api_key=resolved_key)

    def _split_messages(
        self, messages: list[LLMMessage]
    ) -> tuple[str | None, list[types.Content]]:
        """Extract system instruction and format user/assistant contents."""
        system_prompts: list[str] = []
        contents: list[types.Content] = []

        for m in messages:
            if m.role == "system":
                system_prompts.append(m.content)
            elif m.role == "assistant":
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=m.content)],
                    )
                )
            else:  # user
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=m.content)],
                    )
                )

        sys_instruction = "\n\n".join(system_prompts) if system_prompts else None
        return sys_instruction, contents

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
        sys_instruction, contents = self._split_messages(messages)
        temp = temperature if temperature is not None else self.default_temperature
        tokens = max_tokens or self.default_max_tokens
        retries = self.default_max_retries

        start_time = time.perf_counter()
        logger.info(
            "Requesting structured LLM completion with Gemini",
            model=self.model,
            response_model=response_model.__name__,
            num_messages=len(messages),
        )

        config = types.GenerateContentConfig(
            system_instruction=sys_instruction,
            temperature=temp,
            max_output_tokens=tokens,
            response_mime_type="application/json",
            response_schema=response_model,
        )

        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=config,
                )

                text_content = response.text
                if not text_content:
                    raise LLMValidationError(
                        model_name=self.model,
                        attempts=attempt,
                        last_error="Gemini returned empty response text",
                    )

                # Parse and validate with Pydantic
                try:
                    data = json.loads(text_content)
                    result = response_model.model_validate(data)
                except (json.JSONDecodeError, ValidationError) as ve:
                    raise LLMValidationError(
                        model_name=self.model,
                        attempts=attempt,
                        last_error=f"Failed to parse or validate schema: {ve}",
                    ) from ve

                elapsed = time.perf_counter() - start_time
                logger.info(
                    "Structured Gemini LLM completion successful",
                    model=self.model,
                    response_model=response_model.__name__,
                    duration_seconds=round(elapsed, 2),
                )
                return result

            except LLMValidationError as e:
                last_error = e
                logger.warning(
                    "Gemini validation error on attempt",
                    attempt=attempt,
                    max_retries=retries,
                    error=str(e),
                )
                if attempt == retries:
                    raise
            except ClientError as e:
                err_msg = str(e)
                logger.error("Gemini ClientError", error=err_msg, code=getattr(e, "code", None))
                code = getattr(e, "code", None)
                if code == 400 and ("API_KEY_INVALID" in err_msg or "INVALID_ARGUMENT" in err_msg):
                    raise LLMAuthenticationError(f"Gemini authentication failed: {err_msg}") from e
                if code in (401, 403):
                    raise LLMAuthenticationError(f"Gemini authentication failed: {err_msg}") from e
                if code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                    raise LLMRateLimitError(f"Gemini quota/rate limit exceeded: {err_msg}") from e
                raise LLMProviderError(f"Gemini Client error ({code}): {err_msg}") from e
            except ServerError as e:
                logger.error("Gemini ServerError", error=str(e))
                last_error = e
                if attempt == retries:
                    raise LLMProviderError(f"Gemini Server error: {e}") from e
            except APIError as e:
                logger.error("Gemini APIError", error=str(e))
                raise LLMProviderError(f"Gemini API error: {e}") from e
            except Exception as e:
                logger.error("Unexpected error during Gemini completion", error=str(e))
                raise LLMProviderError(f"Unexpected Gemini completion error: {e}") from e

        if last_error:
            raise last_error
        raise LLMProviderError("Gemini completion failed with unknown state")

    def complete_text(
        self,
        messages: list[LLMMessage],
        temperature: float | None = None,
    ) -> str:
        """Execute free-text completion without response schema enforcement."""
        sys_instruction, contents = self._split_messages(messages)
        temp = temperature if temperature is not None else self.default_temperature

        start_time = time.perf_counter()
        logger.info(
            "Requesting free-text LLM completion with Gemini",
            model=self.model,
            num_messages=len(messages),
        )

        config = types.GenerateContentConfig(
            system_instruction=sys_instruction,
            temperature=temp,
            max_output_tokens=self.default_max_tokens,
        )

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
            elapsed = time.perf_counter() - start_time
            content = response.text or ""
            logger.info(
                "Free-text Gemini LLM completion successful",
                model=self.model,
                duration_seconds=round(elapsed, 2),
            )
            return content
        except ClientError as e:
            code = getattr(e, "code", None)
            err_msg = str(e)
            if code in (401, 403) or "API_KEY_INVALID" in err_msg:
                raise LLMAuthenticationError(f"Gemini authentication failed: {err_msg}") from e
            if code == 429 or "RESOURCE_EXHAUSTED" in err_msg:
                raise LLMRateLimitError(f"Gemini quota/rate limit exceeded: {err_msg}") from e
            raise LLMProviderError(f"Gemini Client error: {err_msg}") from e
        except Exception as e:
            raise LLMProviderError(f"Gemini completion error: {e}") from e
