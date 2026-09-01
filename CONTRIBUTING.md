# Contributing to certified-dose

Thank you for your interest in contributing to **`certified-dose`**! We welcome contributions from process control engineers, formal methods researchers, hydrologists, and software engineers.

---

## Code of Conduct

We are committed to providing a friendly, safe, and welcoming environment for all contributors. Please treat everyone with respect and professional courtesy.

---

## Development Setup

### 1. Prerequisites
- Python 3.11 or 3.12
- Git
- `uv` (recommended) or `pip` + `venv`

### 2. Clone and Install
```bash
git clone https://github.com/Raj123-0/certified-dose.git
cd certified-dose

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with development and dashboard dependencies
pip install -e ".[dashboard,dev]"
```

---

## Development Workflow & Quality Gates

All contributions must pass strict automated gates before merging:

### 1. Code Formatting & Linting
We use [Black](https://github.com/psf/black) for formatting and [Ruff](https://github.com/astral-sh/ruff) for linting:
```bash
black certified_dose tests benchmarks examples
ruff check --fix certified_dose tests benchmarks examples
```

### 2. Strict Static Type Checking
All core code is type-checked in strict mode with [mypy](https://mypy-lang.org/):
```bash
mypy --strict certified_dose
```

### 3. Automated Test Suite & Coverage Gate
Code must achieve $\ge 90\%$ line coverage:
```bash
pytest --cov=certified_dose --cov-report=term-missing --cov-fail-under=90 tests
```

### 4. Empirical Soundness Fuzzing
When modifying reachability logic or intervals, run the Monte Carlo verification benchmark:
```bash
python benchmarks/large_scale_fuzz.py --trials 100000 --scenarios 100
```
Zero soundness violations are permitted.

---

## Submitting Pull Requests

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Commit your changes following [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat(...)`: New feature or capability
   - `fix(...)`: Bug fix or soundness correction
   - `docs(...)`: Documentation improvements
   - `test(...)`: Adding or refactoring tests
   - `perf(...)`: Performance optimization
3. Ensure all tests and lint checks pass locally.
4. Push your branch and open a Pull Request using the PR template.
