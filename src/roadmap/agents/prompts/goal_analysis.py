"""
Prompt templates for Goal Analysis.

Version: 1.0.0
Purpose: Guide LLM to infer standardized competencies and required skills
from a user's stated career or learning goal.
"""

from __future__ import annotations

from roadmap.domain.entities.user_profile import UserProfile

GOAL_ANALYSIS_SYSTEM_PROMPT = """You are an expert technical career architect and curriculum designer.

YOUR MISSION:
Analyze the user's target career or learning goal and infer a rigorous, industry-standard competency model.
Break down what a professional in this role genuinely needs to master.

OUTPUT EXPECTATIONS:
1. Standardized Target Role: Clearly resolve the professional title (e.g., 'Gameplay Programmer', 'ML Infrastructure Engineer').
2. Competencies: 3 to 6 major capability domains.
3. Required Skills: 6 to 15 core technical skills that are essential prerequisites for hireability or competency in this role.
4. Optional Skills: 2 to 5 complementary or stretch skills that differentiate candidates.
5. Key Assumptions: Explicitly state baseline assumptions regarding background, toolchains, or industry conventions.
6. Confidence: Rate your analysis confidence from 0.0 to 1.0.

DOMAIN CONSTRAINTS:
- Do NOT generate generic corporate buzzwords (e.g. 'Good communication'). Focus on technical competencies and foundational skills.
- Categorize skills accurately (e.g. 'programming', 'mathematics', 'algorithms', 'game engine', 'tools').
- Assign realistic target proficiency levels: 'familiar', 'learning', 'proficient', or 'mastered'.
- Respect the user's preferred technologies and industry if specified, but do not omit core fundamentals.

EXPLICIT NON-GOALS:
- Do NOT schedule phases or weeks here (that happens in roadmap generation).
- Do NOT calculate skill gap math against the user's current baseline (that is computed deterministically by the system).
- Do NOT hallucinate specific URLs for resources.
"""


def build_goal_analysis_user_prompt(profile: UserProfile) -> str:
    """Construct the dynamic user prompt for goal analysis."""
    lines = [
        f"USER TARGET GOAL: {profile.target_goal}",
    ]
    if profile.target_role:
        lines.append(f"SPECIFIED ROLE: {profile.target_role}")
    if profile.preferred_industry:
        lines.append(f"PREFERRED INDUSTRY: {profile.preferred_industry}")
    if profile.programming_languages:
        lines.append(f"KNOWN PROGRAMMING LANGUAGES: {', '.join(profile.programming_languages)}")
    if profile.current_skills:
        lines.append(f"REPORTED CURRENT SKILLS: {', '.join(profile.current_skills)}")
    if profile.preferred_technologies:
        lines.append(f"PREFERRED TECHNOLOGIES: {', '.join(profile.preferred_technologies)}")
    if profile.target_markets:
        lines.append(f"TARGET MARKETS: {', '.join(profile.target_markets)}")
    if profile.constraints:
        lines.append(f"CONSTRAINTS: {'; '.join(profile.constraints)}")

    lines.append(
        "\nPlease analyze this goal and produce a comprehensive, structured technical competency breakdown."
    )
    return "\n".join(lines)
