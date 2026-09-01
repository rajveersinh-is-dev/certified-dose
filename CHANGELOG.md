# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-09-01

### Fixed
- **Interval Fractional Power Soundness**: Fixed bug in `Interval.__pow__` where negative fractional powers (e.g. `Interval(4.0, 9.0) ** -0.5`) resulted in reversed interval bounds or raised `ValueError`. Negative powers are now soundly inverted via `1.0 / (self ** (-exponent))`. Handled integer-valued floats (e.g. `2.0`) correctly when intervals straddle zero. Added regression test suite.

### Added
- **Formal Soundness Proof** (`docs/SOUNDNESS.md`): Mathematical proof sketch establishing that interval reachability propagation is a strict over-approximation of the process output. Proves that concurrent monotonicity of removal and restabilization kinetics with respect to pH penalty eliminates excess conservatism from shared variables (zero dependency loss).
- **10M+ Trial Empirical Verification Suite** (`benchmarks/large_scale_fuzz.py`): Vectorized brute-force Monte Carlo fuzzer validating reachability bounds over 10,000,000 trials across 1,000 scenarios with 0 violations and high throughput (>20M trials/sec).
- **Nightly Fuzzing CI Workflow** (`.github/workflows/nightly-fuzz.yml`): Daily automated CI run executing 10M+ trials independently from fast per-PR checks, with status badge in README.
- **Conservatism & Cost-Overhead Benchmark** (`benchmarks/conservatism_benchmark.py`): Parametric sweep across $\pm 5\%$ through $\pm 30\%$ disturbance uncertainty widths during storm surges. Quantifies chemical overhead (+4.5% to +25.4%) vs. naive violation elimination (25% to 0%).
- **3-Panel Publication Figure** (`docs/assets/benchmark_conservatism.png`): High-resolution visualization illustrating dosing setpoints, effluent compliance envelopes, and the cost-of-safety Pareto frontier.
- **Empirical Literature Validation Module** (`certified_dose/validation.py`): Direct statistical comparison of synthetic kinetics against published water treatment jar-testing data (Edwards 1997 / AWWA benchmark), demonstrating $R^2 = 0.9999$ and compliance-window $\text{RMSE} = 0.015\text{ NTU}$.
- **CLI Validation Subcommand** (`certified-dose validate`): Terminal diagnostics printing goodness-of-fit metrics and point-by-point jar-test comparisons.
- **Generic Process Model Interface** (`certified_dose.process_model.ProcessModel`): Abstract base class specifying `disturbance_names`, `evaluate_scalar`, and `evaluate_interval`, making `ReachabilityEngine` fully domain-agnostic.
- **CSTR pH Neutralization Example** (`examples/ph_neutralization.py`): Second complete physical process model demonstrating reachability analysis on continuous stirred-tank acid-base neutralization with logarithmic sensitivity, backed by dedicated tests (`tests/test_ph_neutralization.py`).
- **Packaging & Community Infrastructure**:
  - `CONTRIBUTING.md` developer guide and quality standards.
  - GitHub issue templates (`.github/ISSUE_TEMPLATE/`) for bug reports and feature requests.
  - Pull request template (`.github/pull_request_template.md`).
  - Streamlit cloud configuration (`.streamlit/config.toml`).
  - Automated pre-release publishing workflow to TestPyPI (`.github/workflows/publish-testpypi.yml`).

### Changed
- **Decoupled Reachability Engine**: `ReachabilityEngine` now dynamically checks and normalizes disturbances based on `model.disturbance_names`, accepting any process conforming to `ProcessModel`.
- **Refined Limitations Notice**: Updated `README.md` to precisely distinguish empirically validated steady-state kinetics from unvalidated plant hydraulic mixing and sensor transport lags, while preserving the core research/demonstration disclaimer.

## [0.1.0] - 2026-09-01

### Added
- **Interval Arithmetic Engine** (`certified_dose.intervals.Interval`): Rigorous closed real interval representation with conservative arithmetic operations (`+`, `-`, `*`, `/`, `**`), monotonic functions (`exp`, `log`, `sqrt`, `abs`), inclusion tests, and safety margin widening.
- **Affine Arithmetic Form** (`certified_dose.intervals.AffineForm`): First-order affine arithmetic tracking noise symbols to alleviate the interval wrapping effect on correlated variables.
- **Synthetic Wastewater Coagulation Process Model** (`certified_dose.process_model.SyntheticProcessModel`): Smooth non-linear dose-response model capturing under-dosing, optimal dosing, restabilization/over-dosing, and disturbance sensitivities (turbidity, flow rate, pH, temperature).
- **Reachability Analysis Engine** (`certified_dose.reachability.ReachabilityEngine`): Guaranteed reachability computation under bounded input disturbances with configurable safety margin and Monte Carlo fuzz verification.
- **Candidate Controllers** (`certified_dose.controller`): Protocol interface `BaseController`, baseline `HeuristicController`, cost-cutting `AggressiveCandidateController`, and adversarial test controllers.
- **Formal Safety Certifier** (`certified_dose.certifier.CertifiedDoseWrapper`): Wraps candidate controllers, verifies reachable output against regulatory compliance envelope, conducts bisection search for safe fallback doses, and implements fail-safe defaults on any numerical anomaly.
- **Closed-Loop Simulator** (`certified_dose.simulate.ClosedLoopSimulator`): Dynamic plant simulation under stochastic disturbances and storm surge scenarios.
- **CLI Interface** (`certified_dose.cli`): Command-line tool `certified-dose` supporting `simulate`, `check`, `dashboard`, and `version` subcommands.
- **Interactive Streamlit Dashboard** (`certified_dose.dashboard`): Visual exploration tool with uncertainty sliders, live time-series charts, reachability shaded envelopes, zero-violation KPI badges, and single-shot dose reachability inspector.
- **Docker Support**: Multi-stage `Dockerfile` and `docker-compose.yml` for zero-setup execution.
- **Documentation**: Comprehensive `README.md` with explicit research/demo disclosure, and `docs/methodology.md` explaining mathematical formulations.
- **Automated CI**: GitHub Actions matrix workflow verifying Python 3.11 and 3.12 with formatting (`black`), linting (`ruff`), strict type checking (`mypy`), and test coverage (`pytest` >= 90%).
