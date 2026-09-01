from pathlib import Path

from benchmarks.conservatism_benchmark import (
    plot_benchmark_figures,
    run_uncertainty_sweep,
)
from benchmarks.large_scale_fuzz import run_large_scale_fuzzing


def test_large_scale_fuzzing_smoke() -> None:
    results = run_large_scale_fuzzing(total_trials=1000, n_scenarios=10, seed=123)
    assert results.soundness_verified
    assert results.violations_found == 0
    assert results.total_trials >= 1000
    assert results.min_conservatism_margin > 0.0


def test_conservatism_benchmark_smoke(tmp_path: Path) -> None:
    results, summary = run_uncertainty_sweep(
        uncertainty_levels=[0.10, 0.15],
        n_steps=10,
        seed=1,
    )
    assert len(results) == 2
    assert results[0].certified_violations == 0
    assert results[1].certified_violations == 0

    img_path = tmp_path / "test_benchmark.png"
    plot_benchmark_figures(results, summary, img_path)
    assert img_path.exists()
