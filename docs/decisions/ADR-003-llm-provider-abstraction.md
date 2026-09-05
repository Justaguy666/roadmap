# ADR-003 — LLM Provider Abstraction

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-05 |
| **Deciders** | Engineering team |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Context

RoadmapAI requires a Large Language Model (LLM) to:

1. Propose skill graphs (nodes + prerequisite edges) for a given learning goal.
2. Generate milestone breakdowns from a validated skill graph.
3. (MVP-2+) Drive research and critic agents in the multi-agent loop.

The LLM landscape is evolving rapidly. Provider APIs, pricing, and capability rankings change frequently. In 2024–2026 alone, serious alternatives to OpenAI's GPT-4 family emerged (Anthropic Claude 3.x, Google Gemini 1.5, Mistral Large, Meta LLaMA 3 via hosted APIs, etc.).

### Problem

If we call the OpenAI SDK directly from application or domain code, we face:

- **Vendor lock-in** — migrating to another provider requires modifying core business logic.
- **Testability** — unit tests for use-cases require a live API key or complex mocking of the OpenAI SDK.
- **Structured output fragility** — raw LLM text responses require bespoke JSON parsing with no validation, leading to runtime errors when the model varies its format.

### Options considered

1. **Call OpenAI SDK directly everywhere** — simple initially, brittle long-term.
2. **LangChain abstraction** — provides provider switching but adds a large dependency and its own abstraction leaks.
3. **Custom `LLMProvider` protocol + Instructor** — thin, purpose-built interface; Instructor handles structured output validation.
4. **LiteLLM** — unified API for 100+ LLM providers; heavier dependency but maximum flexibility.

---

## Decision

We define an `LLMProvider` **Protocol** in `domain/ports/llm_provider.py`. OpenAI is the initial concrete adapter. All LLM calls in the application layer go through this protocol.

### Protocol definition

```python
# domain/ports/llm_provider.py
from typing import Protocol, TypeVar, Type
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class LLMProvider(Protocol):
    """Abstract interface for all LLM interactions."""

    def complete(
        self,
        prompt: str,
        response_model: Type[T],
        *,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> T:
        """
        Send a prompt to the LLM and return a validated Pydantic model instance.
        Raises LLMError on provider failure.
        Raises ValidationError if the response cannot be parsed into response_model.
        """
        ...
```

### Instructor + Pydantic for structured outputs

All LLM calls use the [Instructor](https://github.com/jxnl/instructor) library to guarantee structured outputs. Instead of parsing raw text, the LLM is instructed (via function-calling or JSON mode) to return a specific schema, and Instructor validates the response against a Pydantic model automatically.

```python
# infrastructure/llm/openai_provider.py
import instructor
from openai import OpenAI
from pydantic import BaseModel
from typing import Type, TypeVar

T = TypeVar("T", bound=BaseModel)

class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self._client = instructor.from_openai(OpenAI(api_key=api_key))
        self._model = model

    def complete(self, prompt: str, response_model: Type[T], **kwargs) -> T:
        return self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            response_model=response_model,
            **kwargs,
        )
```

### Test double (fake adapter)

```python
# tests/fakes/fake_llm_provider.py
class FakeLLMProvider:
    """Returns pre-configured responses for testing. No network calls."""

    def __init__(self, responses: dict[Type, BaseModel]) -> None:
        self._responses = responses

    def complete(self, prompt: str, response_model: Type[T], **_) -> T:
        return self._responses[response_model]
```

### Adding a new provider

To add, e.g., Anthropic Claude:

1. Create `infrastructure/llm/anthropic_provider.py` implementing the `LLMProvider` protocol.
2. Update `settings.py` to accept `llm_provider: Literal["openai", "anthropic"] = "openai"`.
3. Update the composition root to inject the correct provider.
4. No changes to `domain/` or `application/`.

---

## Consequences

### Positive

- **Provider portability** — switching from OpenAI to any other provider is a 1-file change in infrastructure.
- **Structured, validated outputs** — Instructor + Pydantic eliminate JSON parsing bugs. If the LLM returns malformed output, a `ValidationError` is raised with a clear message, not a `KeyError` at runtime.
- **Testability** — application and domain tests inject `FakeLLMProvider`; no API key or network required.
- **Thin dependency** — the `LLMProvider` protocol is 15 lines of pure Python. Application code has no knowledge of `openai`, `anthropic`, or any SDK.
- **Automatic retry with Instructor** — Instructor supports automatic retry-with-feedback when validation fails, improving robustness with no additional code.

### Negative

- **Instructor dependency** — adds `instructor` and its transitive dependencies to the package. Currently well-maintained and widely adopted; accepted risk.
- **Protocol conformance is duck-typed** — Python `Protocol` does not enforce implementation at class definition time; it is checked at usage via `mypy`. Mypy must be run in CI to catch violations.
- **Response model proliferation** — every distinct LLM output requires its own Pydantic model. This is a net positive for clarity but adds file count.
- **Model-specific prompt tuning** — prompts optimised for GPT-4o may need adjustment for Claude or Gemini. Switching providers is easy; retuning prompts takes effort.

### Not decided here

- **Streaming responses** — the current protocol does not support streaming. This can be added as an optional method in a future ADR.
- **Embeddings** — a separate `EmbeddingProvider` protocol will be defined when semantic search or vector similarity is needed.
- **LiteLLM** — if we need to support 5+ providers simultaneously, migrating the OpenAI adapter to use LiteLLM as a universal proxy is a future option. The `LLMProvider` protocol makes this migration transparent to all callers.
