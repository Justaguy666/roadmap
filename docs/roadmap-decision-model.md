# Roadmap Decision Model & 7-Dimension Quality Scoring

## Multi-Factor Skill Scoring

Each skill is scored using a composite decision model:

$$\text{Score} = 0.25 \cdot M + 0.25 \cdot G + 0.20 \cdot K + 0.15 \cdot P + 0.10 \cdot V + 0.05 \cdot T$$

Where:
- $M$: Market Relevance (observed frequency in industry job listings)
- $G$: Goal Alignment (role match from goal analysis)
- $K$: Skill Gap Distance (target level - current level)
- $P$: Prerequisite Importance (number of dependent downstream skills)
- $V$: Portfolio / Practical Value (demonstrable project utility)
- $T$: Time Cost Feasibility (fit within user timeline budget)

## 7-Dimension Roadmap Quality Scoring

Roadmap quality is assessed objectively across 7 dimensions (0-100 total score):
1. **Goal Alignment (20%)**: Direct match with target role competencies.
2. **Market Alignment (20%)**: Representation of high-frequency market demands.
3. **Evidence Strength (15%)**: Ratio of skills grounded in authoritative citations.
4. **Dependency Correctness (15%)**: Strict acyclicity and valid prerequisite ordering.
5. **Time Feasibility (10%)**: Total estimated hours vs user time budget.
6. **Portfolio Value (10%)**: High-impact, portfolio-worthy project milestones.
7. **Scope Efficiency (10%)**: Minimization of redundant or low-impact concepts.
