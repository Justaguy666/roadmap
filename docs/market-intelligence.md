# Market Intelligence & Observed Frequency Analysis

## Overview

The Market Intelligence service analyzes collected industry job postings and company tech stacks to calculate empirical demand statistics.

## Frequency Formulation

$$\text{Observed Sample Frequency} = \frac{\text{Postings Mentioning Skill}}{\text{Total Postings Analyzed}}$$

## Market Priority Tiers

1. **CRITICAL / CORE (Frequency $\ge 0.65$)**: Mandatory baseline requirements for the role.
2. **HIGH / IMPORTANT ($0.35 \le \text{Frequency} < 0.65$)**: Strongly preferred competencies across major employers.
3. **NICE-TO-HAVE / EMERGING ($0.15 \le \text{Frequency} < 0.35$)**: Specialized libraries or emerging tools.
4. **NICHE / SPECIALIZED ($\text{Frequency} < 0.15$)**: Highly context-dependent skills.

## Regional & Industry Segmentation
- Tracks hiring company presence (e.g. FAANG, startups, enterprise).
- Records sample count, sample period, and confidence intervals to prevent over-generalization on small sample sizes.
