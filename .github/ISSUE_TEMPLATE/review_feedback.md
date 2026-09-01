---
name: External Review Feedback
about: Provide review comments, mathematical soundness feedback, or audit findings.
title: "[External Review]: "
labels: ["external-review", "triage"]
assignees: []
---

## Reviewer Profile
- **Affiliation / Background** (e.g. academic, control engineer, formal methods, water treatment operator):
- **Relevant Standards or Areas Evaluated** (e.g. Interval Arithmetic, Soundness Proof, Timing, Threat Model):

## Scope of Inspection
Please check the areas you reviewed:
- [ ] Soundness proof ([`docs/SOUNDNESS.md`](https://github.com/Raj123-0/certified-dose/blob/main/docs/SOUNDNESS.md))
- [ ] Core interval arithmetic implementation (`certified_dose/intervals.py`)
- [ ] Adversarial and property-based test suites (`tests/test_adversarial.py`)
- [ ] Empirical literature validation (`certified_dose/validation.py`)
- [ ] Worst-case execution latency guarantees ([`docs/TIMING.md`](https://github.com/Raj123-0/certified-dose/blob/main/docs/TIMING.md))
- [ ] Cyber-physical threat model ([`docs/THREAT_MODEL.md`](https://github.com/Raj123-0/certified-dose/blob/main/docs/THREAT_MODEL.md))
- [ ] Regulatory gap analysis ([`docs/REGULATORY_CONTEXT.md`](https://github.com/Raj123-0/certified-dose/blob/main/docs/REGULATORY_CONTEXT.md))

## Summary of Findings
A concise summary of your assessment, strengths identified, and primary concerns.

## Detailed Observations & Recommendations
1. **Observation 1**:
   - *Impact*:
   - *Suggested Improvement*:

2. **Observation 2**:
   - *Impact*:
   - *Suggested Improvement*:

## Counterexamples or Mathematical Discrepancies (if any)
If you found an edge case or bound violation, please provide reproduction code:
```python
# Minimal reproduction script
```

## Additional Context
Any additional links, literature citations, or industrial standards relevant to your review.
