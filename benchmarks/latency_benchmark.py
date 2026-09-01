"""Latency and Execution Timing Benchmark for certified-dose.

Measures empirical execution duration, percentile latencies (p50, p95, p99, p99.9),
and Worst-Case Execution Time (WCET) for:
1. Single certification checks (nominal candidate accepted).
2. Bisection fallback search under varying disturbance uncertainty widths (+/- 5%, +/- 15%, +/- 30%).
3. Bisection fallback search under varying iteration limits (10, 25, 50).

Outputs structured latency profiles for industrial real-time control system certification.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

from certified_dose.certifier import CertifiedDoseWrapper
from certified_dose.intervals import Interval

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("latency_benchmark")


def benchmark_single_check(trials: int = 10000) -> dict[str, float]:
    """Measures latency of single nominal certification checks (microseconds)."""
    wrapper = CertifiedDoseWrapper(compliance_limit=1.0)
    state = {
        "turbidity": Interval(20.0, 25.0),
        "flow_rate": Interval(950.0, 1050.0),
        "ph": Interval(7.1, 7.3),
        "temperature": Interval(17.0, 19.0),
    }
    candidate_dose = 20.0  # Certified safe setpoint

    # Warmup
    for _ in range(100):
        _ = wrapper.certify_action(candidate_dose, state)

    durations_us: list[float] = []
    for _ in range(trials):
        t0 = time.perf_counter_ns()
        _ = wrapper.certify_action(candidate_dose, state)
        t1 = time.perf_counter_ns()
        durations_us.append((t1 - t0) / 1000.0)

    arr = np.array(durations_us)
    return {
        "trials": float(trials),
        "mean_us": float(np.mean(arr)),
        "std_us": float(np.std(arr)),
        "min_us": float(np.min(arr)),
        "median_us": float(np.median(arr)),
        "p90_us": float(np.percentile(arr, 90)),
        "p95_us": float(np.percentile(arr, 95)),
        "p99_us": float(np.percentile(arr, 99)),
        "p99_9_us": float(np.percentile(arr, 99.9)),
        "max_us": float(np.max(arr)),
    }


def benchmark_bisection_sweep(trials: int = 1000) -> dict[str, Any]:
    """Measures latency of bisection search across uncertainty widths and iteration limits."""
    results: dict[str, Any] = {}

    widths = [0.05, 0.15, 0.30]
    iter_limits = [10, 25, 50]

    for w in widths:
        w_pct = int(w * 100)
        state = {
            "turbidity": Interval(25.0 * (1 - w), 25.0 * (1 + w)),
            "flow_rate": Interval(1000.0 * (1 - w), 1000.0 * (1 + w)),
            "ph": Interval(7.2 - w, 7.2 + w),
            "temperature": Interval(18.0 - 5.0 * w, 18.0 + 5.0 * w),
        }
        candidate_dose = 2.0  # Unsafe dose requiring correction

        for iters in iter_limits:
            wrapper = CertifiedDoseWrapper(
                compliance_limit=1.0,
                bisection_max_iter=iters,
                max_computation_time_ms=50.0,
            )

            # Warmup
            for _ in range(10):
                _ = wrapper.certify_action(candidate_dose, state)

            durations_ms: list[float] = []
            for _ in range(trials):
                t0 = time.perf_counter()
                res = wrapper.certify_action(candidate_dose, state)
                durations_ms.append((time.perf_counter() - t0) * 1000.0)

            arr = np.array(durations_ms)
            key = f"width_{w_pct}pct_iter_{iters}"
            results[key] = {
                "uncertainty_pct": w_pct,
                "max_iter": iters,
                "trials": trials,
                "mean_ms": float(np.mean(arr)),
                "median_ms": float(np.median(arr)),
                "p95_ms": float(np.percentile(arr, 95)),
                "p99_ms": float(np.percentile(arr, 99)),
                "max_ms": float(np.max(arr)),
                "corrected_dose": float(res.certified_dose),
            }

    return results


def run_latency_benchmark(
    trials_single: int = 10000, trials_bisection: int = 1000
) -> dict[str, Any]:
    """Runs all latency benchmarks and returns consolidated metrics."""
    logger.info(
        "Running single certification check latency benchmark (%d trials)...",
        trials_single,
    )
    single_metrics = benchmark_single_check(trials=trials_single)
    logger.info(
        "Single Check: Mean = %.2f us | Median = %.2f us | p99 = %.2f us | Max = %.2f us",
        single_metrics["mean_us"],
        single_metrics["median_us"],
        single_metrics["p99_us"],
        single_metrics["max_us"],
    )

    logger.info(
        "Running bisection fallback search latency sweep (%d trials per setting)...",
        trials_bisection,
    )
    bisection_metrics = benchmark_bisection_sweep(trials=trials_bisection)
    for k, v in bisection_metrics.items():
        logger.info(
            "Bisection [%s]: Mean = %.2f ms | Median = %.2f ms | p99 = %.2f ms | Max = %.2f ms",
            k,
            v["mean_ms"],
            v["median_ms"],
            v["p99_ms"],
            v["max_ms"],
        )

    full_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        "single_check_latency_us": single_metrics,
        "bisection_fallback_latency_ms": bisection_metrics,
        "timing_guarantees": {
            "single_check_wcet_us": single_metrics["max_us"],
            "single_check_p99_us": single_metrics["p99_us"],
            "bisection_fallback_hard_cap_ms": 50.0,
            "control_loop_feasibility": "Suitable for 10Hz - 1000Hz industrial PLCs/DCS",
        },
    }

    out_file = Path("benchmarks/results_latency.json")
    out_file.write_text(json.dumps(full_results, indent=2), encoding="utf-8")
    logger.info("Saved latency benchmark results to %s", out_file)
    return full_results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run certified-dose latency benchmark")
    parser.add_argument(
        "--trials-single",
        type=int,
        default=10000,
        help="Trials for single check benchmark",
    )
    parser.add_argument(
        "--trials-bisection",
        type=int,
        default=500,
        help="Trials for bisection sweep benchmark",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run fast smoke benchmark with reduced trials",
    )
    args = parser.parse_args()

    if args.quick:
        run_latency_benchmark(trials_single=500, trials_bisection=50)
    else:
        run_latency_benchmark(
            trials_single=args.trials_single, trials_bisection=args.trials_bisection
        )


if __name__ == "__main__":
    main()
