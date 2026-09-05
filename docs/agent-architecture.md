# Agent Architecture

This document describes the agent architecture and structured output contracts introduced in **MVP-2**.

## Overview

In RoadmapAI, AI agents operate within the Application/Agent layer to transform user goals and profile context into validated learning roadmaps. 

Rather than allowing unbounded multi-agent conversations or brittle prompt engineering, agents in RoadmapAI strictly adhere to:
1. **Contract-First Design**: Communication with the LLM is governed by typed Pydantic output schemas via instructor.
2. **Deterministic Processing**: Graph construction, skill gap calculations, and invariant checks are computed using pure Python algorithms rather than LLM guesswork.
3. **Bounded Self-Correction**: When domain validation catches an error (e.g. invalid prerequisite ordering or non-positive durations), the system re-prompts the model with explicit diagnostics (up to 3 attempts).

`
+------------------+       +-------------------+       +-----------------------+
|   User Profile   | ----> |   GoalAnalyzer    | ----> |  GoalAnalysisResult   |
+------------------+       +-------------------+       +-----------------------+
                                                                   |
                                                                   v
+------------------+       +-------------------+       +-----------------------+
|  Deterministic   | <---- | SkillGapAnalyzer  | <---- |    Required Skills    |
| SkillGapAnalysis |       |  (Pure Python)    |       +-----------------------+
+------------------+       +-------------------+
         |
         v
+------------------+       +-------------------+       +-----------------------+
| RoadmapGenerator | ----> |  RoadmapValidator | ----> | Persist & CLI Display |
|  (OpenAI + Ins.) |       |  (Pure Python)    |       +-----------------------+
+------------------+       +-------------------+
`

---

## 1. Goal Analysis Agent

### Purpose
Extracts core competencies, essential prerequisite skills, and optional specializations from the user's free-text target career or objective.

### Schema Contract (src/roadmap/agents/schemas/goal_analysis.py)
- GoalAnalysisResult:
  - primary_career: string
  - 	arget_role_level: junior, mid, senior, lead, principal
  - summary: High-level summary of the career pathway
  - key_competencies: List of CompetencyDraft (category, description, importance)
  - equired_skills: List of RequiredSkillDraft (name, target_level, rationale, prerequisites, estimated_hours)
  - optional_skills: List of OptionalSkillDraft (name, target_level, rationale)

### Prompts
Located in src/roadmap/agents/prompts/goal_analysis.py.
- **System Prompt**: Enforces professional career advisory standards, realistic time estimates, and prerequisite chains.
- **User Prompt**: Supplies target goal, target role, weekly hours, timeline, and current skill baseline.

---

## 2. Skill Gap Analyzer (Deterministic)

### Purpose
Calculates the delta between what the user already knows (UserProfile.current_skills) and what the goal demands (RequiredSkillDraft).

### Logic (src/roadmap/domain/services/skill_gap_analyzer.py)
- Completely deterministic Python logic.
- Compares ordinal levels: NONE < BEGINNER < INTERMEDIATE < ADVANCED < EXPERT.
- Emits SkillGapAnalysisResult with categorized items (missing, gap, sufficient).

---

## 3. Roadmap Generation Agent

### Purpose
Synthesizes the goal analysis and computed skill gaps into a structured, chronological curriculum with sequential phases, milestones, capstone projects, and recommended resources.

### Schema Contract (src/roadmap/agents/schemas/roadmap_generation.py)
- RoadmapGenerationResult:
  - oadmap_title: string
  - oadmap_objective: string
  - 	otal_duration_weeks: integer (> 0)
  - phases: Ordered list of RoadmapPhaseDraft
    - phase_number: sequential 1..N
    - 	itle: string
    - duration_weeks: integer (> 0)
    - 	arget_skills: list of RoadmapSkillDraft
    - projects: list of RoadmapProjectDraft
    - milestones: list of RoadmapMilestoneDraft
    - esources: list of RoadmapResourceDraft
    - exit_criteria: list of criteria strings

### Prompts
Located in src/roadmap/agents/prompts/roadmap_generation.py.
- Enforces strict chronological progression where Phase N skills serve as prerequisites for Phase N+1.
- Mandates actionable portfolio projects with tangible deliverables for each phase.

---

## 4. Verification & Repair Loop

`
Agent Output Draft
       |
       v
RoadmapValidator (Domain Service)
       |
       +---> [Valid] ----------------------> Persist to Database
       |
       +---> [Violations Found]
                   |
                   +-- Retries < 3? --[Yes]--> Re-prompt LLM with Errors
                   |
                   +-- Retries == 3? -[No]---> Raise RoadmapValidationError
`

- Invariant checks:
  1. No zero or negative durations.
  2. Prerequisite ordering across phases (a prerequisite must be scheduled in the same or an earlier phase).
  3. No duplicate skills across the roadmap.
