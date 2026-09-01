"""Tests for benchmark and verification scripts."""

from benchmarks.large_scale_fuzz import run_large_scale_fuzzing


def test_large_scale_fuzzing_smoke() -> None:
    results = run_large_scale_fuzzing(total_trials=1000, n_scenarios=10, seed=123)
    assert results.soundness_verified
    assert results.violations_found == 0
    assert results.total_trials >= 1000
    assert results.min_conservatism_margin > 0.0
