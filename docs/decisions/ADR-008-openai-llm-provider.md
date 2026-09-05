# ADR-008: OpenAI LLM Provider Integration with Instructor

## Status
Accepted

## Context
In MVP-2, RoadmapAI requires generative AI capabilities to analyze career/learning goals, infer required competencies, and construct sequenced learning phases, projects, and milestones.

Key requirements for this integration include:
1. **Strict Decoupling**: Application and domain layers must not be coupled to OpenAI or any proprietary client library.
2. **Deterministic Schemas**: The system cannot rely on free-form unstructured text generation, regular expression scrapers, or brittle JSON parsing. All agent outputs must conform to strictly typed Pydantic models.
3. **Robust Fault Tolerance**: The system must handle network timeouts, rate limits, authentication failures, and schema non-compliance with bounded retries and informative domain errors.
4. **Offline / Test Mode**: Unit and integration tests must run quickly, deterministically, and cost-free without hitting live external APIs.

## Decision
1. **Port Abstraction (LLMProvider)**:
   An application port interface LLMProvider is maintained in src/roadmap/application/ports/llm_provider.py. It defines an asynchronous/synchronous completion contract generate(messages, response_model, temperature, max_tokens) -> T parameterized by a generic Pydantic BaseModel type T.

2. **OpenAI + Instructor Adapter (OpenAIProvider)**:
   We implement OpenAIProvider in src/roadmap/infrastructure/llm/openai_provider.py using:
   - Official openai Python SDK.
   - instructor library (instructor.from_openai(OpenAI(...))) to guarantee JSON mode / tool-calling structured output validation against the target Pydantic schema.
   - Domain exception wrapping: OpenAI SDK exceptions are mapped cleanly to LLMAuthenticationError, LLMRateLimitError, LLMTimeoutError, or LLMProviderError.

3. **Fake LLM Provider (FakeLLMProvider)**:
   We implement a deterministic FakeLLMProvider in src/roadmap/infrastructure/llm/fake_provider.py. It inspects esponse_model and returns valid default fixtures for GoalAnalysisResult and RoadmapGenerationResult or can be pre-configured with custom canned responses or failure scenarios.

4. **Deterministic Validation Boundary**:
   The LLM is responsible for draft generation (GoalAnalysisResult, RoadmapGenerationResult), but **never** trusted for graph topological invariants or mathematical consistency:
   - Skill gaps are computed deterministically in Python (SkillGapAnalyzer).
   - Phase durations and prerequisite orderings are validated deterministically by RoadmapValidator.
   - On validation failure, a bounded retry loop (up to 3 attempts) sends corrective feedback to the LLM.

## Consequences

### Positive
- **Provider Portability**: Switching to Anthropic Claude, Google Gemini, or local models (via Ollama/vLLM) only requires implementing a new adapter conforming to LLMProvider.
- **Type Safety**: Agent outputs are statically validated through Pydantic and fully typed across use cases.
- **Fast, Reliable CI/CD**: Test suites execute completely offline via FakeLLMProvider in under 2 seconds without requiring API keys or incurring token costs.
- **Resilience**: Well-defined error hierarchies provide clean CLI user feedback rather than unhandled Python stack traces.

### Negative / Trade-offs
- instructor adds an extra dependency and abstraction layer over raw OpenAI API calls.
- Complex schemas may occasionally require prompt tuning or repair loops if the LLM struggles with nested constraints.
