"""
Pydantic schemas for research planning, evidence extraction, and market intelligence.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchQuery(BaseModel):
    """A generated search query targeted at market data or learning resources."""

    query: str = Field(min_length=3, max_length=200, description="Exact search phrase")
    query_type: str = Field(
        description="market | resource",
        pattern=r"^(market|resource)$",
    )
    focus: str = Field(description="Target skill, role, or curriculum topic")


class ResearchPlan(BaseModel):
    """Structured plan of queries formulated by the research agent."""

    topic: str = Field(min_length=3, max_length=200)
    target_market: str = Field(default="", max_length=100)
    queries: list[ResearchQuery] = Field(min_length=1, max_length=10)


class ExtractedClaimDraft(BaseModel):
    """An individual claim extracted from a document."""

    claim: str = Field(min_length=5, max_length=1000, description="The concrete statement or requirement")
    related_skills: list[str] = Field(min_length=1, description="Associated skill names")
    source_type: str = Field(
        default="other",
        description="job_posting | official_documentation | university_curriculum | technical_article | course | other",
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    relevance: float = Field(default=0.8, ge=0.0, le=1.0)


class EvidenceExtractionResult(BaseModel):
    """Batch of claims extracted from a fetched web page."""

    source_title: str = Field(default="")
    detected_source_type: str = Field(default="other")
    claims: list[ExtractedClaimDraft] = Field(default_factory=list)


class PageExtractionResult(BaseModel):
    """Extraction result for an individual document within a multi-document batch."""

    page_index: int = Field(ge=0, description="0-indexed document sequence in the batch")
    url: str = Field(description="URL of the document")
    source_title: str = Field(default="")
    detected_source_type: str = Field(
        default="other",
        description="job_posting | company_career_page | official_documentation | university_curriculum | technical_article | course | other",
    )
    claims: list[ExtractedClaimDraft] = Field(default_factory=list)


class BatchEvidenceExtractionResult(BaseModel):
    """Structured extraction result across multiple batched web documents."""

    documents: list[PageExtractionResult] = Field(default_factory=list)


class MarketSkillObservation(BaseModel):
    """Empirical observation of a skill across sampled job postings."""

    skill_name: str = Field(min_length=1)
    sample_size: int = Field(ge=1, description="Total postings inspected in the sample")
    mentions: int = Field(ge=0, description="Number of sampled postings mentioning this skill")
    observed_frequency: float = Field(ge=0.0, le=1.0, description="mentions / sample_size")
    sample_notes: str = Field(default="Observed sample from search results, not industry-wide census")
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class MarketResearchResult(BaseModel):
    """Structured synthesis of market research."""

    target_role: str = Field(min_length=2)
    target_market: str = Field(default="")
    total_postings_sampled: int = Field(ge=0)
    key_findings: list[str] = Field(default_factory=list)
    skill_observations: list[MarketSkillObservation] = Field(default_factory=list)


class RecommendedResourceDraft(BaseModel):
    """A learning resource discovered during research."""

    title: str = Field(min_length=2)
    url: str = Field(min_length=5)
    provider: str = Field(default="")
    resource_type: str = Field(default="course")
    difficulty: str = Field(default="familiar")
    related_skill: str = Field(min_length=1)
    rationale: str = Field(default="")
    estimated_hours: float = Field(default=10.0, ge=0.0)


class ResourceResearchResult(BaseModel):
    """Structured synthesis of learning resource research."""

    target_skills: list[str] = Field(default_factory=list)
    resources: list[RecommendedResourceDraft] = Field(default_factory=list)
