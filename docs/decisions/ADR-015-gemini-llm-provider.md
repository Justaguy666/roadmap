# ADR-015: Google Gemini (Google AI Studio) LLM Provider

## Status
Accepted

## Context
RoadmapAI was designed with a pluggable `LLMProvider` abstraction (`ADR-003`) to decouple the application and domain layers from specific AI model vendors. The initial implementation utilized OpenAI. Users requested support for Google Gemini via Google AI Studio as an alternative provider with lower latency, higher context capacity, and accessible pricing.

## Decision
1. Implement `GeminiProvider` conforming to the `LLMProvider` protocol interface using the official `google-genai` SDK.
2. Leverage Gemini’s native Pydantic schema validation:
   - `response_mime_type="application/json"`
   - `response_schema=response_model`
3. Translate Gemini system instructions and multi-turn message roles (`system`, `user`, `assistant` -> `model`).
4. Map `google.genai.errors` (`ClientError`, `ServerError`, `APIError`, HTTP 400/401/403/429) cleanly into domain exceptions:
   - `LLMAuthenticationError`
   - `LLMRateLimitError`
   - `LLMTimeoutError`
   - `LLMValidationError`
   - `LLMProviderError`
5. Make `gemini` the default provider option while retaining full `openai` and `mock` support.

## Consequences
### Positive
- Users can switch between Gemini and OpenAI seamlessly by setting `ROADMAP_LLM_PROVIDER=gemini` or `ROADMAP_LLM_PROVIDER=openai`.
- Native structured output eliminates external proxy dependencies.
- Zero changes to domain models or application use case services.

### Negative
- Requires maintaining two LLM provider adapters (`OpenAIProvider` and `GeminiProvider`) and dependencies.
