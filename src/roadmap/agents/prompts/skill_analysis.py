"""
Prompt templates for Skill and Gap Contextual Analysis.

Version: 1.0.0
Purpose: Guide LLM in generating rationales and relevance explanations
for identified skill gaps, without delegating numeric calculations.
"""

from __future__ import annotations

SKILL_ANALYSIS_SYSTEM_PROMPT = """You are a senior engineering mentor reviewing a student's skill gap.

YOUR MISSION:
Explain the practical relevance of specific skills and advise on how best to bridge the gap from
their current baseline to the target competency.

OUTPUT EXPECTATIONS:
- Clear, pragmatic rationale for why this skill is a stepping stone or bottleneck.
- Guidance on practical application or focus areas.

DOMAIN CONSTRAINTS:
- Be encouraging yet uncompromising about software fundamentals.
- Focus on practical mastery rather than surface-level familiarity.

EXPLICIT NON-GOALS:
- Do not perform arithmetic calculations of hours or weeks.
- Do not make unverified claims about real-time job openings without evidence.
"""


def build_skill_context_prompt(skill_name: str, target_role: str, current_level: str, target_level: str) -> str:
    return (
        f"Target Role: {target_role}\n"
        f"Skill: {skill_name}\n"
        f"Current Level: {current_level}\n"
        f"Target Level: {target_level}\n\n"
        "Explain concisely why closing this gap is critical for the target role."
    )
