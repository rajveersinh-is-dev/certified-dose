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

    console.print(
        Panel.fit(
            f"[bold]Candidate Dose:[/bold] {dose:.2f} mg/L\n"
            f"[bold]Influent Turbidity Range:[/bold] [{turb_interval.lo:.1f}, {turb_interval.hi:.1f}] NTU\n"
            f"[bold]Flow Rate Range:[/bold] [{flow_interval.lo:.0f}, {flow_interval.hi:.0f}] m3/h\n"
            f"[bold]Compliance Ceiling:[/bold] {limit:.2f} NTU\n\n"
            f"[bold]Worst-Case Reachable Effluent:[/bold] [{r_set.lo:.3f}, {r_set.hi:.3f}] NTU\n"
            f"[bold]Certification Status:[/bold] [bold {'green' if result.status == 'ACCEPTED' else 'yellow'}]{result.status.value}[/]\n"
            f"[bold]Certified Output Action:[/bold] {result.certified_dose:.2f} mg/L\n"
            f"[bold]Reason:[/bold] {result.reason}",
            title="[bold cyan]Reachability Verification Result[/bold cyan]",
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
