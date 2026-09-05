# Market Research & Sample Integrity

RoadmapAI distinguishes carefully between **observed sample data** and universal industry claims.

## Honest Sample Statistics

Job market statistics in RoadmapAI explicitly state the sample size to prevent misleading hallucinations or false precision:

```
Observed Frequency = Mentions in Sample / Total Sampled Postings
```

The output always carries an explicit disclosure note:
> *"Note: Observed frequency represents the sampled job postings, not a complete census."*

## Skill Observation Object
Each skill observed during market analysis is structured as follows:

```json
{
  "skill_name": "C++",
  "sample_size": 15,
  "mentions": 14,
  "observed_frequency": 0.93,
  "supporting_evidence_ids": ["ev_1", "ev_2"]
}
```

This guarantees that:
1. No skill is claimed to be "in 95% of all jobs in the world" without explicitly stating the underlying sample size.
2. Every percentage shown in the CLI can be clicked or traced back to the exact URLs fetched.
