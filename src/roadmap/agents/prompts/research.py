"""
Prompts for Research Agent: query planning, evidence extraction, and synthesis.
"""

from __future__ import annotations

# ── Query Planning ────────────────────────────────────────────────────────────

RESEARCH_PLAN_SYSTEM_PROMPT = """You are the Senior Research Strategist for RoadmapAI.
Your mission is to formulate targeted, high-signal web search queries to research:
1. Real-world market hiring requirements, job postings, and company career requirements.
2. Official technical documentation, university curricula, reputable textbooks, and industry-standard courses.

Rules:
- Generate 3 to 6 specific, targeted search queries.
- Include targeted geographical context (target_market) if specified.
- Avoid generic queries like 'learn programming'. Instead formulate queries like:
  - 'gameplay programmer C++ requirements Unreal Engine 5'
  - 'gameplay programmer job description linear algebra physics'
  - 'Unreal Engine 5 C++ gameplay architecture official documentation'
  - 'computer science game programming university curriculum syllabus'
- Categorize each query as either 'market' or 'resource'.
"""


def build_research_plan_prompt(
    topic: str,
    target_market: str = "",
    focus_skills: list[str] | None = None,
) -> str:
    parts = [
        f"Research Topic / Target Career: {topic}",
    ]
    if target_market:
        parts.append(f"Target Geographic or Industry Market: {target_market}")
    if focus_skills:
        parts.append(f"Focus Skills to investigate: {', '.join(focus_skills)}")

    parts.append(
        "\nGenerate a structured ResearchPlan with high-yield search queries balancing market requirements and learning resources."
    )
    return "\n".join(parts)


# ── Evidence Extraction ───────────────────────────────────────────────────────

EVIDENCE_EXTRACTION_SYSTEM_PROMPT = """You are an Evidence Extraction Agent for RoadmapAI.
Your task is to analyze readable web page text retrieved from search results and extract verifiable, concrete claims.

Rules:
1. Extract only facts, concrete skill requirements, tool versions, and curriculum topics stated in the text.
2. Ground each claim in the text. Never hallucinate or extrapolate statistics not present.
3. Classify source type accurately:
   - job_posting: Specific job opening or hiring description
   - company_career_page: Studio/company overview of role requirements
   - official_documentation: Official engine/language/framework docs
   - university_curriculum: College course, syllabus, lecture series
   - industry_report / survey: Developer survey, market research
   - technical_article: Blog post or guide
   - course: Online course description
   - other
4. Assign realistic confidence (0.0 to 1.0) and relevance (0.0 to 1.0).
5. Associate each claim with one or more skill names (e.g. ['C++', 'Unreal Engine 5', 'Linear Algebra']).
"""


def build_evidence_extraction_prompt(
    url: str,
    title: str,
    text_content: str,
    target_goal: str = "",
) -> str:
    return (
        f"Target Goal / Topic: {target_goal or 'Technical Career'}\n"
        f"Document Title: {title}\n"
        f"Source URL: {url}\n\n"
        f"--- Document Content ---\n"
        f"{text_content}\n"
        f"--- End Document ---\n\n"
        "Extract key evidence claims and classify the source."
    )
