## Description
Provide a concise explanation of what this PR does and why it is needed.

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue or soundness gap)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update
- [ ] Benchmark / performance enhancement

## Quality Checklist
- [ ] My code adheres to the project's formatting and style guidelines (`black`, `ruff`).
- [ ] I have verified strict static typing passes without errors (`mypy --strict certified_dose`).
- [ ] All unit tests pass with $\ge 90\%$ test coverage (`pytest --cov=certified_dose --cov-fail-under=90`).
- [ ] (If reachability or arithmetic logic was altered) Empirical fuzzing passes with 0 violations (`benchmarks/large_scale_fuzz.py`).
- [ ] I have updated `CHANGELOG.md` following Keep a Changelog conventions.
- [ ] I have updated documentation or docstrings where appropriate.
