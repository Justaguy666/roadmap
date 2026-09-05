"""Prompts package for agents."""

from roadmap.agents.prompts.goal_analysis import (
    GOAL_ANALYSIS_SYSTEM_PROMPT,
    build_goal_analysis_user_prompt,
)
from roadmap.agents.prompts.roadmap_generation import (
    ROADMAP_GENERATION_SYSTEM_PROMPT,
    build_roadmap_generation_user_prompt,
)
from roadmap.agents.prompts.skill_analysis import (
    SKILL_ANALYSIS_SYSTEM_PROMPT,
    build_skill_context_prompt,
)

__all__ = [
    "GOAL_ANALYSIS_SYSTEM_PROMPT",
    "ROADMAP_GENERATION_SYSTEM_PROMPT",
    "SKILL_ANALYSIS_SYSTEM_PROMPT",
    "build_goal_analysis_user_prompt",
    "build_roadmap_generation_user_prompt",
    "build_skill_context_prompt",
]
