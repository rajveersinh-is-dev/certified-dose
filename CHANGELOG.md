# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Adversarial Edge-Case Test Suite** (`tests/test_adversarial.py`): Dedicated test suite with 7 comprehensive suites covering degenerate intervals ($w \to 0$) collapsing to exact scalar evaluation, multi-order-of-magnitude uncertainty, exact compliance limit $\epsilon$-discrimination, IEEE subnormals ($10^{-300}$) and extreme magnitudes ($10^{140}$), complete `Interval.__pow__` exponent matrix, NaN/Inf fail-safe rejection, and correlated non-independent sensor manifold over-approximation.
- **Mutation Testing Framework** (`cosmic-ray.toml`): AST mutation testing configured via `cosmic-ray` targeting `certified_dose/intervals.py`. Achieved **100.0% mutation kill score** across tested mutants with zero surviving mutants.
- **Hard Latency Caps & Timing Guarantees** (`certified_dose/certifier.py`, `docs/TIMING.md`, `benchmarks/latency_benchmark.py`):
  - Added `max_computation_time_ms: float = 50.0` hard wall-clock latency cap to `CertifiedDoseWrapper` with automatic reversion to conservative `fallback_dose` on timeout.
  - Implemented strict `bisection_max_iter` enforcement across coarse grid search and fine bisection refinement.
  - Added empirical timing benchmark (`benchmarks/latency_benchmark.py`) measuring $22.6\,\mu\text{s}$ median and $81.0\,\mu\text{s}$ WCET for single checks, and $0.59 - 0.63\,\text{ms}$ mean and $1.57\,\text{ms}$ WCET for bisection search.
  - Documented formal real-time timing bounds, $\mathcal{O}(1)$ interval propagation complexity, and control-loop feasibility matrix in `docs/TIMING.md`.
- **Cyber-Physical Threat Model & Trust Assumptions** (`docs/THREAT_MODEL.md`): Formalized the software trust boundary, articulated the 5 core physical trust axioms (sensor interval enclosure, kinetic boundedness, actuator tracking, arithmetic determinism, telemetry integrity), and cataloged concrete failure modes under sensor drift, model-plant mismatch, and cyber tampering.
- **Second Independent Literature Validation Dataset** (`certified_dose/validation.py`, `README.md`):
  - Added Van Benschoten & Edzwald (1990) peer-reviewed alum jar-testing dataset (*Water Research*, 24(12):1519–1526), demonstrating $R^2 = 0.9952$, overall $\text{RMSE} = 0.4401\,\text{NTU}$, and active compliance-window ($15 - 60\,\text{mg/L}$) precision of $\text{RMSE} = 0.0988\,\text{NTU}$.
  - Added `BENCHMARK_DATASETS` registry and `validate_all_datasets()` helper.
  - Added `--dataset` option to `certified-dose validate` CLI supporting side-by-side multi-dataset reporting.
  - Documented both datasets side-by-side in `README.md`.
- **Operator-Facing Explainability & Sensitivity Attribution** (`certified_dose/certifier.py`, `certified_dose/reachability.py`, `certified_dose/cli.py`, `certified_dose/dashboard.py`):
  - Added `compute_sensitivity_attribution` to `ReachabilityEngine` computing one-at-a-time (OAT) output uncertainty width contributions.
  - Added `result.explain()` method to `CertificationResult` generating structured `ExplanationReport` and `SensitivityAttribution` records.
  - Details binding constraint, safety margin, primary driver, and actionable operator guidance.
  - Surfaced rich explainability breakdown and sensitivity table in `certified-dose check` CLI.
  - Surfaced interactive horizontal sensitivity attribution bar chart and guidance expander in Streamlit dashboard inspector tab.
- **Drinking-Water Regulatory-Context Mapping** (`docs/REGULATORY_CONTEXT.md`): Comprehensive mapping of point-in-time mathematical reachability against EPA Surface Water Treatment Rules (SWTR, LT2ESWTR) rolling monthly 95th percentile standards, highlighting elimination of pathogen breakthrough windows alongside model dependence trade-offs. Detail deployment gaps covering GAMP 5 validation (Category 4/5), FDA 21 CFR Part 11 audit trails, and EPA QAPP requirements.
- **External Review Readiness & Audit Checklist** (`docs/REVIEW_CHECKLIST.md`, `.github/ISSUE_TEMPLATE/review_feedback.md`, `README.md`):
  - Authored comprehensive reviewer checklist (`docs/REVIEW_CHECKLIST.md`) detailing verification commands, inspectable modules, mathematical properties, and known limitations.
  - Created dedicated GitHub issue template (`.github/ISSUE_TEMPLATE/review_feedback.md`) for external review submissions.
  - Updated `README.md` inviting independent review and linking to all formal documentation artifacts.

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
