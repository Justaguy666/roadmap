"""
Prompt templates for Roadmap Generation.

Version: 1.0.0
Purpose: Guide LLM to design an end-to-end, phased learning curriculum
incorporating skill gaps, user time constraints, projects, and milestones.
"""

from __future__ import annotations

from roadmap.agents.schemas.goal_analysis import GoalAnalysisResult
from roadmap.agents.schemas.skill_gap import SkillGapAnalysisResult
from roadmap.domain.entities.user_profile import UserProfile

ROADMAP_GENERATION_SYSTEM_PROMPT = """You are a Principal Software Architect and Lead Curriculum Engineer.

YOUR MISSION:
Construct a personalized, chronological, phase-by-phase learning roadmap for a student aiming for a specific career role.
Every phase must be pedagogically sound: foundations first, followed by core principles, followed by applied frameworks and projects.

OUTPUT EXPECTATIONS:
1. Phased Architecture: Organize learning into 3 to 6 logical sequential phases (e.g. 'Phase 1: Systems & Core Language', 'Phase 2: Algorithms & Game Architecture', 'Phase 3: Engine Deep-Dive & Advanced Portfolio').
2. Phase Objectives: State clearly what the student will be capable of achieving by the end of each phase.
3. Realistic Durations: Estimate durations in weeks that realistically fit within the user's available study hours per day and target deadline.
4. Prerequisite Order:
   - Fundamental prerequisites MUST come in earlier phases or precede dependent skills.
   - Never introduce advanced topics before their prerequisites (e.g. don't schedule Custom Shaders before Linear Algebra and C++).
5. Milestone Checkpoints: Each phase MUST have at least 1 milestone with concrete, observable exit criteria (e.g. 'Can write an arena allocator without compiler warnings', 'Passes 100% of unit tests for custom Vector math').
6. Milestone Projects: Each phase should culminate in a substantial project that builds portfolio proof.

DOMAIN CONSTRAINTS:
- No empty phases: Every phase must contain at least 1 skill and 1 milestone.
- Realistic workload: Keep the pacing achievable given the student's study hours.
- Prerequisite validity: Only reference prerequisites that are either previously acquired or taught in an earlier/same phase.
- Positive non-negative numbers for all hours and weeks.

EXPLICIT NON-GOALS:
- Do NOT output unstructured or hand-waving text; strictly satisfy the structured schema.
- Do NOT skip hard fundamentals to jump straight into high-level libraries.
"""


def build_roadmap_generation_user_prompt(
    profile: UserProfile,
    goal_analysis: GoalAnalysisResult,
    skill_gaps: SkillGapAnalysisResult,
) -> str:
    """Construct the detailed prompt containing user context and analyzed gaps."""
    critical_gaps = [g.skill for g in skill_gaps.gaps if g.gap > 0 and g.priority.value == "critical"]
    high_gaps = [g.skill for g in skill_gaps.gaps if g.gap > 0 and g.priority.value == "high"]
    other_gaps = [g.skill for g in skill_gaps.gaps if g.gap > 0 and g.priority.value not in ("critical", "high")]
    mastered = [g.skill for g in skill_gaps.gaps if g.gap == 0]

    lines = [
        f"TARGET ROLE: {goal_analysis.target_role}",
        f"OVERALL GOAL: {goal_analysis.interpreted_goal}",
        f"USER AVAILABLE STUDY TIME: {profile.study_hours_per_day} hours/day (~{profile.study_hours_per_week} hours/week)",
        f"TARGET DEADLINE: {profile.deadline_months} months (~{profile.deadline_months * 4.33:.1f} weeks)",
        f"TOTAL HOURS BUDGET: ~{profile.total_available_hours:.0f} hours",
        "",
        "ASSESSED SKILL GAPS TO CLOSE:",
    ]

    if critical_gaps:
        lines.append(f"  - CRITICAL PRIORITY: {', '.join(critical_gaps)}")
    if high_gaps:
        lines.append(f"  - HIGH PRIORITY: {', '.join(high_gaps)}")
    if other_gaps:
        lines.append(f"  - MEDIUM/LOW PRIORITY: {', '.join(other_gaps)}")
    if mastered:
        lines.append(f"  - ALREADY PROFICIENT / NO GAP: {', '.join(mastered)} (Do NOT re-teach basics of these, leverage them!)")

    if profile.learning_preferences:
        lines.append(f"LEARNING STYLE PREFERENCES: {', '.join(profile.learning_preferences)}")
    if profile.constraints:
        lines.append(f"CONSTRAINTS: {'; '.join(profile.constraints)}")

    lines.extend([
        "",
        "Please generate a complete, phased learning roadmap tailored to this student's schedule and gaps.",
    ])

    return "\n".join(lines)
