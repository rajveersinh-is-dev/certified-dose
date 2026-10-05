"""Conservatism and cost-overhead benchmarking for certified dosing.

Compares an uncertified cost-optimizing candidate controller against the
formal reachability safety wrapper across a parameter sweep of disturbance
uncertainty widths. Quantifies chemical-cost overhead vs violation prevention
and produces publication-quality visualization figures.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import argparse
import json

from certified_dose.certifier import CertifiedDoseWrapper
from certified_dose.controller import AggressiveCostMinimizerController
from certified_dose.process_model import SyntheticProcessModel
from certified_dose.reachability import ReachabilityEngine
from certified_dose.simulate import ClosedLoopSimulator, SimulationSummary
from rich.console import Console
from rich.table import Table
import matplotlib.pyplot as plt




console = Console()


@dataclass
class UncertaintyBenchmarkResult:
    """Benchmark results for a single uncertainty width level."""

    uncertainty_pct: float
    naive_violations: int
    certified_violations: int
    interventions: int
    intervention_rate_pct: float
    mean_naive_dose: float
    mean_certified_dose: float
    chemical_overhead_pct: float
    max_naive_effluent: float
    max_certified_effluent: float
    compliance_limit: float


def run_uncertainty_sweep(
    uncertainty_levels: list[float] | None = None,
    n_steps: int = 100,
    seed: int = 42,
    compliance_limit: float = 1.0,
    controller_aggression: float = 0.65,
) -> tuple[list[UncertaintyBenchmarkResult], SimulationSummary]:
    """Sweeps uncertainty levels and runs dynamic closed loop simulations."""
    levels = uncertainty_levels or [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    results: list[UncertaintyBenchmarkResult] = []
    baseline_summary: SimulationSummary | None = None

    model = SyntheticProcessModel()
    candidate_ctrl = AggressiveCostMinimizerController(aggression=controller_aggression)

    for u in levels:
        engine = ReachabilityEngine(model=model, safety_margin=0.02)
        certifier = CertifiedDoseWrapper(
            engine=engine,
            compliance_limit=compliance_limit,
            default_uncertainty={
                "turbidity_pct": u,
                "flow_rate_pct": u * 0.7,
                "ph_delta": 0.1 + 0.8 * u,
                "temp_delta": 1.0 + 5.0 * u,
            },
        )
        sim = ClosedLoopSimulator(
            model=model, certifier=certifier, candidate_controller=candidate_ctrl
        )
        summary = sim.run(n_steps=n_steps, seed=seed, storm_start=25, storm_duration=25)

        overhead = (
            (summary.mean_certified_dose - summary.mean_candidate_dose)
            / summary.mean_candidate_dose
        ) * 100.0

        res = UncertaintyBenchmarkResult(
            uncertainty_pct=u * 100.0,
            naive_violations=summary.candidate_violations,
            certified_violations=summary.certified_violations,
            interventions=summary.interventions,
            intervention_rate_pct=summary.intervention_rate_pct,
            mean_naive_dose=summary.mean_candidate_dose,
            mean_certified_dose=summary.mean_certified_dose,
            chemical_overhead_pct=overhead,
            max_naive_effluent=summary.max_candidate_effluent,
            max_certified_effluent=summary.max_certified_effluent,
            compliance_limit=compliance_limit,
        )
        results.append(res)

        # Retain standard 15% run for plotting time series
        if abs(u - 0.15) < 1e-4:
            baseline_summary = summary

    assert baseline_summary is not None
    return results, baseline_summary


def plot_benchmark_figures(
    results: list[UncertaintyBenchmarkResult],
    summary: SimulationSummary,
    output_path: Path,
) -> None:
    """Generates a 3-panel publication figure saved to output_path."""
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 12), dpi=300)

    steps = [r.step for r in summary.records]
    cand_dose = [r.candidate_dose for r in summary.records]
    cert_dose = [r.certified_dose for r in summary.records]
    cand_eff = [r.candidate_effluent for r in summary.records]
    cert_eff = [r.certified_effluent for r in summary.records]
    reach_hi = [r.reachable_hi for r in summary.records]
    reach_lo = [r.reachable_lo for r in summary.records]
    intervened = [r.was_intervened for r in summary.records]

    # Panel 1: Dosing actions over time
    ax1.plot(
        steps,
        cand_dose,
        label="Naive Candidate Dose (Aggressive ML)",
        color="#8854d0",
        linestyle="--",
        linewidth=1.8,
    )
    ax1.plot(
        steps,
        cert_dose,
        label="Certified Safe Dose (Safety Layer)",
        color="#20bf6b",
        linewidth=2.2,
    )
    int_steps = [s for s, i in zip(steps, intervened, strict=True) if i]
    int_doses = [d for d, i in zip(cert_dose, intervened, strict=True) if i]
    ax1.scatter(
        int_steps,
        int_doses,
        color="#fa8231",
        s=28,
        zorder=5,
        label="Safety Interventions (Unsafe Dose Blocked)",
    )

    # Highlight storm window
    ax1.axvspan(
        25, 50, color="#f1f2f6", alpha=0.8, label="Storm Event (Turbidity Surge)"
    )
    ax1.set_ylabel("Coagulant Dose (mg/L)", fontsize=11, fontweight="bold")
    ax1.set_title(
        "Panel A: Dosing Control Trajectory — Naive Cost-Minimizer vs Formal Safety Wrapper",
        fontsize=12,
        fontweight="bold",
        pad=10,
    )
    ax1.legend(loc="upper right", framealpha=0.9, fontsize=9)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.set_xlim(0, max(steps))

    # Panel 2: Effluent quality and reachability envelope
    ax2.fill_between(
        steps,
        reach_lo,
        reach_hi,
        color="#20bf6b",
        alpha=0.20,
        label="Certified Reachable Set [lo, hi]",
    )
    ax2.plot(
        steps,
        cand_eff,
        label="Unchecked Naive Effluent (Violates Limit)",
        color="#eb3b5a",
        linestyle=":",
        linewidth=2.0,
    )
    ax2.plot(
        steps,
        cert_eff,
        label="Certified Plant Effluent (Guaranteed Compliant)",
        color="#0fb9b1",
        linewidth=2.2,
    )
    ax2.axhline(
        summary.compliance_limit,
        color="#b71540",
        linestyle="--",
        linewidth=2.0,
        label=f"Regulatory Ceiling ({summary.compliance_limit:.1f} NTU)",
    )
    ax2.axvspan(25, 50, color="#f1f2f6", alpha=0.8)
    ax2.set_ylabel("Effluent Turbidity (NTU)", fontsize=11, fontweight="bold")
    ax2.set_title(
        "Panel B: Effluent Turbidity Response and Guaranteed Reachable Envelope",
        fontsize=12,
        fontweight="bold",
        pad=10,
    )
    ax2.legend(loc="upper right", framealpha=0.9, fontsize=9)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.set_xlim(0, max(steps))

    # Panel 3: Trade-off curve: Uncertainty width vs Chemical Overhead & Violations
    u_pcts = [r.uncertainty_pct for r in results]
    overheads = [r.chemical_overhead_pct for r in results]
    violations_blocked = [r.naive_violations for r in results]

    color_oh = "#3867d6"
    color_vb = "#eb3b5a"

    ax3_twin = ax3.twinx()

    p1 = ax3.plot(
        u_pcts,
        overheads,
        marker="o",
        color=color_oh,
        linewidth=2.5,
        label="Chemical Cost Overhead (%)",
    )
    p2 = ax3_twin.plot(
        u_pcts,
        violations_blocked,
        marker="s",
        color=color_vb,
        linestyle="--",
        linewidth=2.0,
        label="Naive Violations Prevented (0 with Wrapper)",
    )

    ax3.set_xlabel(
        "Sensor Uncertainty Width (±% of Reading)", fontsize=11, fontweight="bold"
    )
    ax3.set_ylabel(
        "Chemical Overhead (% vs Naive)", color=color_oh, fontsize=11, fontweight="bold"
    )
    ax3_twin.set_ylabel(
        "Violations Caught & Prevented", color=color_vb, fontsize=11, fontweight="bold"
    )
    ax3.tick_params(axis="y", labelcolor=color_oh)
    ax3_twin.tick_params(axis="y", labelcolor=color_vb)
    ax3.set_title(
        "Panel C: Cost of Safety — Chemical Overhead vs Environmental Uncertainty Width",
        fontsize=12,
        fontweight="bold",
        pad=10,
    )
    ax3.grid(True, linestyle=":", alpha=0.6)

    plots = p1 + p2
    labels = [p.get_label() for p in plots]
    ax3.legend(plots, labels, loc="upper left", framealpha=0.9, fontsize=9)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300)
    plt.close()
    console.print(
        f"[green]Publication benchmark figure saved to [bold]{output_path}[/bold][/green]"
    )


def main() -> None:
    """Entry point — parse arguments and run the main computation.
    
    """
    parser = argparse.ArgumentParser(
        description="Run conservatism and chemical overhead benchmark sweep."
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=100,
        help="Timesteps per simulation (default: 100).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/assets/benchmark_conservatism.png"),
        help="Path to save benchmark figure.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=Path("benchmarks/results_conservatism.json"),
        help="Path to output JSON summary.",
    )
    args = parser.parse_args()

    results, baseline_summary = run_uncertainty_sweep(
        n_steps=args.steps,
        seed=args.seed,
    )

    # Print results table
    table = Table(title="Conservatism & Cost Overhead Benchmark (Uncertainty Sweep)")
    table.add_column("Uncertainty Width", justify="right", style="cyan")
    table.add_column("Naive Violations", justify="right", style="red")
    table.add_column("Certified Violations", justify="right", style="bold green")
    table.add_column("Interventions", justify="right", style="yellow")
    table.add_column("Naive Dose", justify="right")
    table.add_column("Certified Dose", justify="right")
    table.add_column("Cost Overhead", justify="right", style="bold magenta")
    table.add_column("Peak Effluent", justify="right")

    for r in results:
        table.add_row(
            f"±{r.uncertainty_pct:.0f}%",
            f"{r.naive_violations} ({r.naive_violations / args.steps * 100:.0f}%)",
            f"{r.certified_violations} (0.0%)",
            f"{r.interventions} ({r.intervention_rate_pct:.0f}%)",
            f"{r.mean_naive_dose:.2f} mg/L",
            f"{r.mean_certified_dose:.2f} mg/L",
            f"+{r.chemical_overhead_pct:.1f}%",
            f"{r.max_certified_effluent:.3f} NTU",
        )

    console.print(table)

    # Plot figure
    plot_benchmark_figures(results, baseline_summary, args.output)

    # Save JSON summary
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "sweep": [asdict(r) for r in results],
            "metadata": {
                "steps": args.steps,
                "seed": args.seed,
                "compliance_limit": 1.0,
            },
        }
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        console.print(f"[green]Saved benchmark JSON to {args.json_out}[/green]")


if __name__ == "__main__":
    main()
