# Evaluator Agent & Bounded Revision Loop

## Architecture

The candidate roadmap undergoes iterative review before acceptance:

```
Candidate Roadmap Draft
         ?
  Deterministic DAG Validator  --[Invalid / Cycles]--+
         ?                                           ¦
  RoadmapEvaluator Agent (LLM) --[Issues Found]------¦
         ?                                           ?
  All Checks Passed? --[No]--> Feedback Revision Loop (Max 3 iterations)
         ? [Yes or Max Iterations Reached]
  Deterministic 7-Dimension Quality Scorer
         ?
  Persist Final Roadmap (vX) & Recommendations
```

## Evaluator Agent Checks
The `RoadmapEvaluator` acts as an independent adversarial critic assessing:
1. **Goal Alignment**: Does the roadmap fulfill the user's specific target role?
2. **Timeline Feasibility**: Is total study time realistic within available weekly hours?
3. **Pacing & Phase Progression**: Are phases logically sequenced from foundational to advanced?
4. **Coverage**: Are essential skills omitted or low-value skills overemphasized?

## Bounded Termination
The revision loop is strictly bounded ($\le 3$ iterations) to guarantee termination and deterministic execution time. If issues persist after 3 cycles, the highest-scoring candidate is accepted with transparent warnings logged.
