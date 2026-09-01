"""Command Line Interface for certified-dose.

Provides commands for running simulation benchmarks, verifying single-point
reachability bounds, and launching the interactive Streamlit dashboard.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from certified_dose import __version__
from certified_dose.certifier import CertifiedDoseWrapper
from certified_dose.intervals import Interval
from certified_dose.reachability import ReachabilityEngine
from certified_dose.simulate import simulate_closed_loop

app = typer.Typer(
    name="certified-dose",
    help="Formal reachability-analysis safety layer for chemical process dosing.",
    add_completion=False,
)
console = Console()


@app.command(name="simulate")
def simulate_cmd(
    steps: Annotated[
        int, typer.Option("--steps", "-n", help="Number of timesteps to simulate.")
    ] = 100,
    seed: Annotated[
        int, typer.Option("--seed", "-s", help="Random seed for disturbance noise.")
    ] = 42,
    limit: Annotated[
        float,
        typer.Option(
            "--limit", "-l", help="Effluent turbidity compliance ceiling (NTU)."
        ),
    ] = 1.0,
    uncertainty: Annotated[
        float,
        typer.Option(
            "--uncertainty",
            "-u",
            help="Fractional sensor uncertainty (e.g. 0.15 for +/-15%).",
        ),
    ] = 0.15,
    csv_export: Annotated[
        Path | None,
        typer.Option(
            "--csv-export", "-o", help="Optional path to write telemetry CSV."
        ),
    ] = None,
) -> None:
    """Run closed-loop simulation benchmark comparing candidate vs certified control."""
    console.print(
        Panel.fit(
            f"[bold cyan]certified-dose v{__version__}[/bold cyan]\n"
            f"[dim]Running {steps}-step closed-loop simulation (Seed: {seed}, Limit: {limit:.2f} NTU)[/dim]",
            title="[bold green]Simulation Benchmark[/bold green]",
        )
    )

    with console.status("[bold green]Executing formal reachability simulation..."):
        summary = simulate_closed_loop(
            n_steps=steps,
            seed=seed,
            compliance_limit=limit,
            uncertainty_pct=uncertainty,
        )

    # Optional CSV export
    if csv_export:
        csv_export.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_export, "w", newline="", encoding="utf-8") as f:
            records = summary.to_records_dict()
            if records:
                writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
                writer.writeheader()
                writer.writerows(records)
        console.print(
            f"[green]Telemetry successfully written to [bold]{csv_export}[/bold][/green]"
        )

    # Telemetry Table (First 8 steps and storm transitions)
    table = Table(title="Selected Closed-Loop Telemetry Steps")
    table.add_column("Step", justify="right", style="cyan")
    table.add_column("Turbidity (NTU)", justify="right")
    table.add_column("Candidate Dose", justify="right", style="magenta")
    table.add_column("Certified Dose", justify="right", style="bold green")
    table.add_column("Status", justify="center")
    table.add_column("Reachable Set (NTU)", justify="center")
    table.add_column("True Effluent (NTU)", justify="right")

    sample_records = (
        summary.records[:6] + [r for r in summary.records if r.was_intervened][:4]
    )
    # Remove duplicates preserving order
    seen_steps = set()
    display_records = []
    for r in sample_records:
        if r.step not in seen_steps:
            seen_steps.add(r.step)
            display_records.append(r)
    display_records.sort(key=lambda x: x.step)

    for r in display_records:
        status_color = "green" if not r.was_intervened else "yellow"
        eff_color = "red" if r.certified_effluent > limit else "green"
        table.add_row(
            str(r.step),
            f"{r.influent_turbidity:.1f}",
            f"{r.candidate_dose:.2f} mg/L",
            f"{r.certified_dose:.2f} mg/L",
            f"[{status_color}]{r.status}[/{status_color}]",
            f"[{r.reachable_lo:.2f}, {r.reachable_hi:.2f}]",
            f"[{eff_color}]{r.certified_effluent:.3f}[/{eff_color}]",
        )

    console.print(table)

    # Verification Summary Card
    cert_status = (
        "[bold green]PASSED (0 VIOLATIONS)[/bold green]"
        if summary.certified_violations == 0
        else f"[bold red]FAILED ({summary.certified_violations} VIOLATIONS)[/bold red]"
    )

    summary_text = (
        f"[bold]Total Control Steps:[/bold] {summary.total_steps}\n"
        f"[bold]Candidate Violations (Unchecked Controller):[/bold] [red]{summary.candidate_violations}[/red] "
        f"({(summary.candidate_violations / summary.total_steps) * 100:.1f}% failure rate)\n"
        f"[bold]Certified Violations (With Safety Layer):[/bold] {cert_status}\n"
        f"[bold]Interventions (Unsafe Doses Corrected):[/bold] [yellow]{summary.interventions}[/yellow] "
        f"({summary.intervention_rate_pct:.1f}% of steps)\n"
        f"[bold]Mean Candidate Dose:[/bold] {summary.mean_candidate_dose:.2f} mg/L\n"
        f"[bold]Mean Certified Dose:[/bold] {summary.mean_certified_dose:.2f} mg/L\n"
        f"[bold]Peak Candidate Effluent:[/bold] {summary.max_candidate_effluent:.3f} NTU\n"
        f"[bold]Peak Certified Effluent:[/bold] {summary.max_certified_effluent:.3f} NTU (Limit: {limit:.2f} NTU)"
    )
    console.print(
        Panel(
            summary_text,
            title="[bold]Compliance & Performance Summary[/bold]",
            expand=False,
        )
    )


@app.command(name="check")
def check_cmd(
    dose: Annotated[
        float, typer.Option("--dose", "-d", help="Candidate coagulant dose (mg/L).")
    ],
    turbidity: Annotated[
        float,
        typer.Option("--turbidity", "-t", help="Raw water influent turbidity (NTU)."),
    ] = 25.0,
    flow: Annotated[
        float, typer.Option("--flow", "-f", help="Plant hydraulic flow rate (m3/h).")
    ] = 1000.0,
    ph: Annotated[float, typer.Option("--ph", help="Influent pH.")] = 7.2,
    temp: Annotated[
        float, typer.Option("--temp", help="Water temperature (deg C).")
    ] = 18.0,
    limit: Annotated[
        float, typer.Option("--limit", "-l", help="Compliance ceiling (NTU).")
    ] = 1.0,
    uncertainty: Annotated[
        float,
        typer.Option("--uncertainty", "-u", help="Fractional uncertainty margin."),
    ] = 0.15,
) -> None:
    """Verify worst-case reachability envelope for a specific candidate dose."""
    engine = ReachabilityEngine()
    wrapper = CertifiedDoseWrapper(engine=engine, compliance_limit=limit)

    turb_interval = Interval(
        turbidity * (1.0 - uncertainty), turbidity * (1.0 + uncertainty)
    )
    flow_interval = Interval(
        flow * (1.0 - uncertainty * 0.7), flow * (1.0 + uncertainty * 0.7)
    )
    ph_interval = Interval(max(4.0, ph - 0.3), min(10.0, ph + 0.3))
    temp_interval = Interval(max(1.0, temp - 2.0), temp + 2.0)

    disturbances = {
        "turbidity": turb_interval,
        "flow_rate": flow_interval,
        "ph": ph_interval,
        "temperature": temp_interval,
    }

    result = wrapper.certify_action(dose, disturbances)
    r_set = result.reachable_set
    exp = result.explain()

    # Choose status color based on outcome
    if result.status.value == "ACCEPTED":
        status_color = "green"
    elif result.status.value == "OUTSIDE_MODEL_VALIDITY":
        status_color = "red"
    else:
        status_color = "yellow"

    console.print(
        Panel.fit(
            f"[bold]Candidate Dose:[/bold] {dose:.2f} mg/L\n"
            f"[bold]Influent Turbidity Range:[/bold] [{turb_interval.lo:.1f}, {turb_interval.hi:.1f}] NTU\n"
            f"[bold]Flow Rate Range:[/bold] [{flow_interval.lo:.0f}, {flow_interval.hi:.0f}] m3/h\n"
            f"[bold]pH Range:[/bold] [{ph_interval.lo:.2f}, {ph_interval.hi:.2f}]\n"
            f"[bold]Compliance Ceiling:[/bold] {limit:.2f} NTU\n\n"
            f"[bold]Certification Status:[/bold] [bold {status_color}]{result.status.value}[/]\n"
            f"[bold]Certified Output Action:[/bold] {result.certified_dose:.2f} mg/L\n"
            f"[bold]Process Model Valid:[/bold] {'[green]Yes[/green]' if result.process_model_valid else '[bold red]NO -- pH outside alum coagulation validity window[/bold red]'}\n"
            + (
                f"[bold]Worst-Case Reachable Effluent:[/bold] [{r_set.lo:.3f}, {'inf' if r_set.hi == float('inf') else f'{r_set.hi:.3f}'}] NTU\n"
                f"[bold]Safety Margin:[/bold] {exp.safety_margin:+.3f} NTU below compliance limit\n"
                if result.process_model_valid
                else "[dim]Reachable set computation skipped -- model validity exceeded.[/dim]\n"
            )
            + f"[bold]Binding Constraint:[/bold] {exp.binding_constraint}\n"
            f"[bold]Reason:[/bold] {result.reason[:200]}",
            title="[bold cyan]Reachability Verification Result[/bold cyan]",
        )
    )

    # For OUTSIDE_MODEL_VALIDITY, show a distinct prominent warning panel
    if result.status.value == "OUTSIDE_MODEL_VALIDITY":
        console.print(
            Panel(
                f"[bold red][!] PROCESS MODEL VALIDITY EXCEEDED [!][/bold red]\n\n"
                f"[bold]Problem:[/bold] {result.model_validity_reason}\n\n"
                f"[bold]Why this matters:[/bold] Above pH 8.5, aluminum in alum (Al2(SO4)3) does\n"
                f"NOT precipitate as insoluble Al(OH)3 floc. Instead, it hydrolyzes into soluble\n"
                f"aluminate (Al(OH)4-). The model's penalty for high pH demands MORE coagulant,\n"
                f"but at pH > 8.5 more alum causes dissolved aluminum breakthrough in treated water.\n\n"
                f"[bold]Required action:[/bold] Acid pre-treatment (H2SO4 or CO2 injection) or\n"
                f"raw water blending to return pH to the coagulation window [5.0, 8.0] BEFORE\n"
                f"relying on coagulant dosing.\n\n"
                f"[dim]The fallback dose {result.certified_dose:.2f} mg/L is applied conservatively,\n"
                f"but this is NOT a validated treatment response at pH > 8.5.[/dim]",
                title="[bold red]Single-Chemical Alum Model Validity Exceeded[/bold red]",
                border_style="red",
            )
        )

    if exp.sensitivities:
        sens_table = Table(
            title="Input Uncertainty Sensitivity Attribution (OAT Breakdown)"
        )
        sens_table.add_column("Disturbance Variable", style="cyan")
        sens_table.add_column("Input Interval", justify="center")
        sens_table.add_column("Partial Output Spread (NTU)", justify="right")
        sens_table.add_column("Uncertainty Share", justify="right", style="bold")
        sens_table.add_column("Impact Driver", justify="left")

        for s in exp.sensitivities:
            interval_str = (
                f"[{s.input_interval.lo:.2f}, {s.input_interval.hi:.2f}]"
                if s.input_interval
                else "N/A"
            )
            driver_str = (
                "[bold red]Primary Driver[/bold red]"
                if s.variable == exp.top_contributor
                and s.relative_contribution_pct > 30.0
                else "Secondary"
            )
            sens_table.add_row(
                s.variable,
                interval_str,
                f"{s.partial_output_width:.3f} NTU",
                f"{s.relative_contribution_pct:.1f}%",
                driver_str,
            )

        console.print(sens_table)

    console.print(
        Panel.fit(
            f"[bold yellow]Operator Actionable Guidance:[/bold yellow]\n{exp.operator_guidance}",
            title="[bold green]Operator Guidance[/bold green]",
        )
    )


@app.command(name="dashboard")
def dashboard_cmd(
    port: Annotated[
        int, typer.Option("--port", "-p", help="Port to bind dashboard to.")
    ] = 8501,
    host: Annotated[
        str, typer.Option("--host", "-h", help="Host address to bind to.")
    ] = "0.0.0.0",
) -> None:
    """Launch the interactive Streamlit reachability visualization dashboard."""
    dashboard_path = Path(__file__).parent / "dashboard.py"
    if not dashboard_path.exists():
        console.print(
            f"[red]Error: Dashboard script not found at {dashboard_path}[/red]"
        )
        raise typer.Exit(code=1)

    console.print(
        f"[bold green]Starting certified-dose Streamlit dashboard on http://{host}:{port}...[/bold green]"
    )
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(dashboard_path),
        "--server.port",
        str(port),
        "--server.address",
        host,
        "--browser.gatherUsageStats",
        "false",
    ]
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped by user.[/yellow]")


@app.command(name="validate")
def validate_cmd(
    dataset: str = typer.Option(
        "all",
        "--dataset",
        "-d",
        help="Benchmark literature dataset ('all', 'edwards_1997', 'van_benschoten_1990').",
    ),
) -> None:
    """Validate process model against published empirical jar-testing literature."""
    from certified_dose.validation import (
        BENCHMARK_DATASETS,
        ModelValidationReport,
        validate_all_datasets,
        validate_synthetic_model,
    )

    reports: list[ModelValidationReport] = []
    if dataset.lower() == "all":
        all_reps = validate_all_datasets()
        reports = list(all_reps.values())
    elif dataset.lower() in BENCHMARK_DATASETS:
        reports = [
            validate_synthetic_model(dataset=BENCHMARK_DATASETS[dataset.lower()])
        ]
    else:
        valid_keys = ", ".join(BENCHMARK_DATASETS.keys())
        console.print(
            f"[bold red]Unknown dataset:[/bold red] {dataset}. Available datasets: all, {valid_keys}"
        )
        raise typer.Exit(code=1)

    for report in reports:
        console.print(
            Panel.fit(
                f"[bold cyan]Model Empirical Validation Report[/bold cyan]\n"
                f"[dim]Reference Dataset: {report.citation}[/dim]\n\n"
                f"[bold]Goodness-of-Fit Metrics:[/bold]\n"
                f"  • R² Score: [bold green]{report.r2_score:.4f}[/bold green]\n"
                f"  • Overall RMSE: [bold green]{report.rmse_ntu:.4f} NTU[/bold green]\n"
                f"  • Mean Absolute Error (MAE): [bold green]{report.mae_ntu:.4f} NTU[/bold green]\n"
                f"  • Compliance Window RMSE (15-60 mg/L): [bold green]{report.compliance_zone_rmse_ntu:.4f} NTU[/bold green]\n"
                f"  • Max Residual: [yellow]{report.max_absolute_error_ntu:.4f} NTU[/yellow]\n\n"
                f"[bold]Divergence Analysis:[/bold]\n{report.divergence_summary}",
                title="[bold green]Literature Validation[/bold green]",
            )
        )

        table = Table(
            title=f"Point-by-Point Literature Comparison: {report.citation.split(',')[0]}"
        )
        table.add_column("Dose (mg/L)", justify="right", style="cyan")
        table.add_column("Measured (NTU)", justify="right")
        table.add_column("Predicted (NTU)", justify="right", style="bold green")
        table.add_column("Residual (NTU)", justify="right")
        table.add_column("Rel Error (%)", justify="right")

        for c in report.comparisons:
            table.add_row(
                f"{c.dose:.1f}",
                f"{c.measured_ntu:.2f}",
                f"{c.predicted_ntu:.2f}",
                f"{c.residual_ntu:+.3f}",
                f"{c.relative_error_pct:.1f}%",
            )

        console.print(table)
        console.print()


@app.command(name="version")
def version_cmd() -> None:
    """Display installed version and environment details."""
    console.print(
        f"[bold cyan]certified-dose[/bold cyan] version [bold]{__version__}[/bold]"
    )
    console.print(f"Python: {sys.version.split()[0]} ({sys.executable})")


def main() -> None:
    """Console script entry point."""
    app()


if __name__ == "__main__":
    main()
