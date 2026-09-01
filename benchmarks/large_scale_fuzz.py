"""Large-scale empirical fuzzing and soundness stress testing.

Generates 10,000,000+ brute-force Monte Carlo realizations across diverse
operating scenarios, verifying that formal interval reachability bounds are
never violated by any physically admissible input perturbation.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from certified_dose.intervals import Interval
from certified_dose.process_model import SyntheticProcessModel
from certified_dose.reachability import ReachabilityEngine

console = Console()


@dataclass
class FuzzResults:
    """Summary of large-scale fuzzing verification."""

    total_trials: int
    total_scenarios: int
    samples_per_scenario: int
    violations_found: int
    min_conservatism_margin: float
    mean_conservatism_margin: float
    max_conservatism_margin: float
    elapsed_seconds: float
    throughput_trials_per_sec: float
    soundness_verified: bool


def evaluate_process_model_vectorized(
    dose: float,
    turbidity: np.ndarray,
    flow: np.ndarray,
    ph: np.ndarray,
    temp: np.ndarray,
    model: SyntheticProcessModel,
) -> np.ndarray:
    """Vectorized evaluation of the process model for high-throughput fuzzing."""
    p = model.params

    temp_factor = np.maximum(0.5, 1.0 + 0.015 * (p.temp_nom - temp))
    ph_factor = 1.0 + 0.20 * ((ph - p.ph_opt) ** 2)

    removal_denom = 1.0 + (p.c1 / (temp_factor * ph_factor)) * (dose**1.6)
    t_removal = p.t_floor + (turbidity - p.t_floor) / removal_denom

    flow_factor = (flow / p.q_nom) ** 0.85
    t_overdose = p.c2 * (dose**2.1) * flow_factor * ph_factor

    return t_removal + t_overdose


def run_large_scale_fuzzing(
    total_trials: int = 10_000_000,
    n_scenarios: int = 1_000,
    safety_margin: float = 0.02,
    seed: int = 42,
) -> FuzzResults:
    """Runs large-scale Monte Carlo fuzzing against interval reachability upper bounds."""
    rng = np.random.default_rng(seed)
    model = SyntheticProcessModel()
    engine = ReachabilityEngine(model=model, safety_margin=safety_margin)

    samples_per_scenario = int(np.ceil(total_trials / n_scenarios))
    actual_total_trials = n_scenarios * samples_per_scenario

    console.print(
        Panel.fit(
            f"[bold cyan]certified-dose Empirical Soundness Verification at Scale[/bold cyan]\n"
            f"Target Trials: [bold]{actual_total_trials:,}[/bold] | "
            f"Scenarios: [bold]{n_scenarios:,}[/bold] | "
            f"Samples/Scenario: [bold]{samples_per_scenario:,}[/bold]\n"
            f"Safety Margin: [bold]{safety_margin} NTU[/bold] | Seed: [bold]{seed}[/bold]",
            title="[bold green]Fuzzing Engine Pre-flight[/bold green]",
        )
    )

    violations = 0
    margins: list[float] = []

    start_time = time.perf_counter()

    for sc in range(n_scenarios):
        # 1. Sample scenario operating point
        base_turb = rng.uniform(10.0, 75.0)
        base_flow = rng.uniform(650.0, 1400.0)
        base_ph = rng.uniform(6.6, 8.2)
        base_temp = rng.uniform(6.0, 28.0)

        # 2. Sample uncertainty bounds (5% to 25% relative width)
        turb_frac = rng.uniform(0.08, 0.22)
        flow_frac = rng.uniform(0.05, 0.15)
        ph_noise = rng.uniform(0.15, 0.45)
        temp_noise = rng.uniform(1.0, 3.5)

        turb_interval = Interval(
            max(1.0, base_turb * (1.0 - turb_frac)), base_turb * (1.0 + turb_frac)
        )
        flow_interval = Interval(
            max(100.0, base_flow * (1.0 - flow_frac)), base_flow * (1.0 + flow_frac)
        )
        ph_interval = Interval(
            max(5.0, base_ph - ph_noise), min(9.5, base_ph + ph_noise)
        )
        temp_interval = Interval(
            max(1.0, base_temp - temp_noise), base_temp + temp_noise
        )

        disturbances = {
            "turbidity": turb_interval,
            "flow_rate": flow_interval,
            "ph": ph_interval,
            "temperature": temp_interval,
        }

        # 3. Test dose level (sweep through under-dose, nominal, and over-dose)
        dose = float(rng.uniform(3.0, 65.0))

        # 4. Compute formal reachable set
        reachable = engine.compute_reachable_set(dose, disturbances)
        r_hi = reachable.hi

        # 5. Draw vectorized random disturbance realizations
        s_turb = rng.uniform(turb_interval.lo, turb_interval.hi, samples_per_scenario)
        s_flow = rng.uniform(flow_interval.lo, flow_interval.hi, samples_per_scenario)
        s_ph = rng.uniform(ph_interval.lo, ph_interval.hi, samples_per_scenario)
        s_temp = rng.uniform(temp_interval.lo, temp_interval.hi, samples_per_scenario)

        # 6. Vectorized evaluation
        effluents = evaluate_process_model_vectorized(
            dose, s_turb, s_flow, s_ph, s_temp, model
        )
        sample_max = float(np.max(effluents))

        # 7. Check soundness: certified upper bound must envelope true maximum
        margin = r_hi - sample_max
        margins.append(margin)

        if margin < -1e-9:
            violations += 1
            console.print(
                f"[red]VIOLATION DETECTED in scenario {sc}! "
                f"Sample max: {sample_max:.5f} > Reachable hi: {r_hi:.5f} (margin: {margin:.5e})[/red]"
            )

    elapsed = time.perf_counter() - start_time
    throughput = actual_total_trials / elapsed if elapsed > 0 else 0.0

    min_margin = float(min(margins))
    mean_margin = float(np.mean(margins))
    max_margin = float(max(margins))

    soundness_verified = violations == 0

    return FuzzResults(
        total_trials=actual_total_trials,
        total_scenarios=n_scenarios,
        samples_per_scenario=samples_per_scenario,
        violations_found=violations,
        min_conservatism_margin=min_margin,
        mean_conservatism_margin=mean_margin,
        max_conservatism_margin=max_margin,
        elapsed_seconds=elapsed,
        throughput_trials_per_sec=throughput,
        soundness_verified=soundness_verified,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run large-scale Monte Carlo fuzzing verification."
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=10_000_000,
        help="Total Monte Carlo trials to run (default: 10,000,000).",
    )
    parser.add_argument(
        "--scenarios",
        type=int,
        default=1_000,
        help="Number of distinct operating scenarios (default: 1,000).",
    )
    parser.add_argument(
        "--safety-margin",
        type=float,
        default=0.02,
        help="Additive safety margin (NTU).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to output results JSON.",
    )
    args = parser.parse_args()

    results = run_large_scale_fuzzing(
        total_trials=args.trials,
        n_scenarios=args.scenarios,
        safety_margin=args.safety_margin,
        seed=args.seed,
    )

    # Print summary table
    table = Table(title="Large-Scale Empirical Verification Summary")
    table.add_column("Metric", style="cyan", justify="left")
    table.add_column("Value", style="bold green", justify="right")

    table.add_row("Total Monte Carlo Trials", f"{results.total_trials:,}")
    table.add_row("Scenarios Tested", f"{results.total_scenarios:,}")
    table.add_row("Samples per Scenario", f"{results.samples_per_scenario:,}")
    table.add_row(
        "Soundness Violations",
        f"[bold {'green' if results.violations_found == 0 else 'red'}]{results.violations_found}[/]",
    )
    table.add_row(
        "Min Conservatism Margin", f"{results.min_conservatism_margin:.5f} NTU"
    )
    table.add_row(
        "Mean Conservatism Margin", f"{results.mean_conservatism_margin:.5f} NTU"
    )
    table.add_row(
        "Max Conservatism Margin", f"{results.max_conservatism_margin:.5f} NTU"
    )
    table.add_row("Execution Duration", f"{results.elapsed_seconds:.2f} s")
    table.add_row(
        "Sampling Throughput", f"{results.throughput_trials_per_sec:,.0f} trials/s"
    )
    table.add_row(
        "Empirical Soundness Verdict",
        (
            "[bold green]PASSED (100% SOUND)[/bold green]"
            if results.soundness_verified
            else "[bold red]FAILED[/bold red]"
        ),
    )

    console.print(table)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(asdict(results), f, indent=2)
        console.print(f"[green]Saved summary JSON to {args.json_out}[/green]")

    if not results.soundness_verified:
        console.print(
            "[bold red]CRITICAL FAILURE: Soundness violations detected![/bold red]"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
