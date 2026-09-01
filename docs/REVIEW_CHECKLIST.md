# External Reviewer Checklist and Audit Guide

This checklist is provided for independent safety auditors, control systems researchers, and formal methods practitioners reviewing the **`certified-dose`** library.

---

## 1. Quick Verification Protocol (5-Minute Smoke Test)

Run the automated verification suite to confirm test coverage, typing, and mathematical guarantees:

```bash
# 1. Clone repository and install in editable mode with dev dependencies
git clone https://github.com/Raj123-0/certified-dose.git
cd certified-dose
pip install -e ".[dev,dashboard]"

# 2. Run static analysis and strict type checking
black --check certified_dose tests benchmarks
ruff check certified_dose tests benchmarks
mypy --strict certified_dose

# 3. Run full test suite with coverage enforcement (>90% gate)
pytest --cov=certified_dose --cov-report=term-missing --cov-fail-under=90 tests

# 4. Run adversarial edge cases and boundary tests
pytest tests/test_adversarial.py -v

# 5. Run literature validation across both empirical jar-testing benchmarks
certified-dose validate --dataset all

# 6. Run timing and latency benchmark
python benchmarks/latency_benchmark.py --quick
```

---

## 2. Structured Review Checklist

### A. Mathematical Soundness & Interval Arithmetic
- [ ] **Proof Verification ([`docs/SOUNDNESS.md`](SOUNDNESS.md))**:
  - [ ] Verify Theorem 1 (Fundamental Theorem of Interval Arithmetic).
  - [ ] Verify Theorem 2 (Monotonicity Concurrence on shared variable $\text{pH}$).
  - [ ] Confirm that endpoint evaluation of $`\phi_T(T)`$ and $`\phi_{\text{pH}}(\text{pH})`$ preserves inclusion monotonicity.
- [ ] **Interval Operators ([`certified_dose/intervals.py`](../certified_dose/intervals.py))**:
  - [ ] Check `Interval.__pow__` matrix for odd, even, fractional, and negative powers.
  - [ ] Inspect division by intervals containing zero (`ZeroDivisionError`).
  - [ ] Inspect subnormal float handling and IEEE 754 precision edges.
  - [ ] Review mutation testing kill rate (configured in [`cosmic-ray.toml`](../cosmic-ray.toml)).

### B. Safety Wrapper & Fail-Safe Architecture
- [ ] **Reachability Engine ([`certified_dose/reachability.py`](../certified_dose/reachability.py))**:
  - [ ] Confirm additive safety margin ($\delta = 0.02$) guarantees strict over-approximation under machine rounding.
  - [ ] Check one-at-a-time (OAT) sensitivity attribution algorithm (`compute_sensitivity_attribution`).
- [ ] **Certifier Wrapper ([`certified_dose/certifier.py`](../certified_dose/certifier.py))**:
  - [ ] Verify unconditional reversion to `fallback_dose` upon any caught exception.
  - [ ] Check rejection and correction logic when candidate dose violates compliance.
  - [ ] Verify that `disturbances` and `engine` are preserved in `CertificationResult` for explainability.
  - [ ] Verify `result.explain()` generates consistent constraint attribution and actionable operator guidance.

### C. Timing, Latency, and Termination Guarantees
- [ ] **Execution Timing ([`docs/TIMING.md`](TIMING.md))**:
  - [ ] Check that the forward reachability check has no unbounded loops or recursions ($\mathcal{O}(1)$ time complexity).
  - [ ] Confirm bisection search enforces `bisection_max_iter: int = 25`.
  - [ ] Confirm wall-clock timeout cap `max_computation_time_ms: float = 50.0` prevents control loop hanging.
  - [ ] Run [`benchmarks/latency_benchmark.py`](../benchmarks/latency_benchmark.py) to measure p99 and WCET on your architecture.

### D. Empirical Literature Fit
- [ ] **Literature Validation ([`certified_dose/validation.py`](../certified_dose/validation.py))**:
  - [ ] Review Dataset 1: Edwards (1997), *Journal AWWA* ($R^2 = 0.9999$).
  - [ ] Review Dataset 2: Van Benschoten & Edzwald (1990), *Water Research* ($R^2 = 0.9952$).
  - [ ] Inspect compliance zone ($15 - 60\text{ mg/L}$) RMSE ($< 0.10\text{ NTU}$).
  - [ ] Confirm that overdosing restabilization is conservatively over-approximated.

### E. Trust Assumptions & Threat Modeling
- [ ] **Trust Boundary ([`docs/THREAT_MODEL.md`](THREAT_MODEL.md))**:
  - [ ] Review Assumption 1 (Sensor Interval Inclosure) and failure modes under drifted sensors.
  - [ ] Review Assumption 2 (Kinetic Boundedness) and impact of unmodeled natural organic matter (NOM).
  - [ ] Review Assumption 3 (Actuator Tracking).
  - [ ] Confirm that `certified-dose` makes no cryptographic authentication claims.

### F. Regulatory Realism & Gaps
- [ ] **Regulatory Mapping ([`docs/REGULATORY_CONTEXT.md`](REGULATORY_CONTEXT.md))**:
  - [ ] Review comparison between instantaneous reachability vs EPA rolling 95th percentile standards.
  - [ ] Inspect gap analysis covering GAMP 5 validation, FDA 21 CFR Part 11 audit logging, and EPA QAPP.
  - [ ] Confirm the "Research and Demonstration Notice" is preserved and accurate.

---

## 3. High-Stress Verification Commands

For in-depth mathematical stress testing:

```bash
# 1. Run 10,000,000 trial Monte Carlo fuzzing verification
python benchmarks/large_scale_fuzz.py --trials 10000000 --scenarios 1000

# 2. Run conservatism & chemical overhead benchmark sweep
python benchmarks/conservatism_benchmark.py --steps 100 --seed 42

# 3. Run full latency benchmark (10,000 single checks + bisection sweeps)
python benchmarks/latency_benchmark.py
```

---

## 4. Submitting Review Feedback

We welcome critical analysis, counterexamples, proof critiques, and domain feedback from external reviewers:

1. **GitHub Issues**: File an issue tagged with `[External Review]` at [Issues](https://github.com/Raj123-0/certified-dose/issues).
2. **Issue Template**: Use the [External Review Feedback Template](https://github.com/Raj123-0/certified-dose/issues/new?template=review_feedback.md).
3. **P0 Vulnerability / Soundness Bug Reporting**:
   If you discover a mathematical violation (a parameter combination where true output exceeds the certified upper bound without fail-safe fallback), please report it immediately as a critical issue with reproduction steps.
