# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
