"""
Unit tests verifying Gemini structured output schema compatibility.
Ensures schemas sent to Google GenAI never contain forbidden keywords like exclusiveMinimum/exclusiveMaximum
and that Pydantic domain models properly enforce validation constraints.
"""

import pytest
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from roadmap.agents.schemas.roadmap_generation import (
    RoadmapGenerationResult,
    RoadmapPhaseDraft,
    RoadmapSkillDraft,
)
from roadmap.infrastructure.llm.gemini_provider import GeminiProvider


def test_roadmap_phase_draft_validates_duration() -> None:
    """Ensure RoadmapPhaseDraft validates minimum duration of 1.0 week."""
    skill = RoadmapSkillDraft(name="Python")
    with pytest.raises(ValidationError):
        RoadmapPhaseDraft(
            phase_name="Foundations",
            objective="Learn basics",
            estimated_duration_weeks=0.0,  # Must be >= 1.0
            skills=[skill],
        )

    phase = RoadmapPhaseDraft(
        phase_name="Foundations",
        objective="Learn basics",
        estimated_duration_weeks=1.0,
        skills=[skill],
    )
    assert phase.estimated_duration_weeks == 1.0


def test_gemini_provider_prepare_response_schema_removes_exclusive_bounds() -> None:
    """
    Ensure _prepare_response_schema converts any exclusiveMinimum / exclusiveMaximum
    into minimum / maximum and produces a valid types.Schema object.
    """
    class TestModelWithExclusive(BaseModel):
        val: float = Field(gt=0.0, lt=100.0)

    prepared = GeminiProvider._prepare_response_schema(TestModelWithExclusive)
    assert isinstance(prepared, types.Schema)
    assert prepared.properties is not None
    prop = prepared.properties["val"]
    assert prop.minimum == 0.0
    assert prop.maximum == 100.0


def test_roadmap_generation_result_gemini_schema_compatibility() -> None:
    """
    Ensure RoadmapGenerationResult can be prepared by GeminiProvider into a valid types.Schema
    without any extra_forbidden validation errors.
    """
    prepared = GeminiProvider._prepare_response_schema(RoadmapGenerationResult)
    assert isinstance(prepared, types.Schema)
    assert prepared.properties is not None
    assert "phases" in prepared.properties
