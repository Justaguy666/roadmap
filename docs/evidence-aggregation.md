# Evidence Aggregation & Weighting Engine

## Mathematical Formulation

The evidence aggregator computes a composite evidence weight for each extracted claim using multi-dimensional scoring:

$$\text{Weight}(e) = \text{Reliability}(s) \times \text{Relevance}(e) \times \text{Confidence}(e) \times \text{Freshness}(s) + \text{DiversityBonus}$$

Where:
- $\text{Reliability}(s) \in [0.0, 1.0]$: Source quality (official documentation > engineering blog > forum).
- $\text{Relevance}(e) \in [0.0, 1.0]$: Relevance to the target topic or skill.
- $\text{Confidence}(e) \in [0.0, 1.0]$: Extracted claim certainty.
- $\text{Freshness}(s) \in [0.7, 1.0]$: Time decay penalty for sources older than 2 years.
- $\text{DiversityBonus} = 0.05 \times (\text{distinct source types} - 1)$ (capped at 0.15).

---

## Divergence & Caveat Detection

When aggregating claims for a skill, the engine analyzes sentiment and terminology to detect contradictions or cautions:
- **Caveats**: Flags mentions of steep learning curves, deprecations, ecosystem shifts, or prerequisites.
- **Contradiction Flagging**: Identifies conflicting recommendations across distinct sources and surfaces them to the LLM during candidate planning.
