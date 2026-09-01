"""Continuous Stirred Tank Reactor (CSTR) pH neutralization process model.

Demonstrates that the certified-dose reachability engine is general-purpose
and domain-agnostic, applying formal interval safety guarantees to a classic
chemical engineering process with steep, logarithmic non-linearities.

Process Physics:
    Alkaline industrial wastewater (influent pH 9.0 - 11.5) enters a continuous
    stirred-tank reactor (CSTR) with flow rate Q (L/min) and carbonate/bicarbonate
    buffer capacity C_b (mol/L). Acid reagent (1.0 M HCl/H2SO4) is dosed at
    rate d (mL/min) to neutralize the effluent into the environmental discharge
    regulatory envelope (e.g. 6.0 <= pH <= 8.5).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from scipy.optimize import brentq

from certified_dose.intervals import Interval
from certified_dose.process_model import ProcessModel
from certified_dose.reachability import ReachabilityEngine

console = Console()


@dataclass(frozen=True)
class PHModelParameters:
    """Parameters governing CSTR acid-base neutralization kinetics."""

    c_acid_mol_per_l: float = 1.0  # 1.0 M acid titrant
    kw: float = 1.0e-14  # Water dissociation constant
    ka_bicarbonate: float = 4.5e-7  # Carbonic acid dissociation constant Ka1
    tank_volume_l: float = 500.0  # CSTR volume (L)


class PHNeutralizationModel(ProcessModel):
    """CSTR chemical neutralization process model implementing ProcessModel ABC.

    Evaluates effluent pH as a function of acid titrant dose (mL/min) and
    disturbances:
        - 'influent_ph': Raw wastewater stream pH (e.g. 9.0 to 11.5).
        - 'flow_rate': Wastewater flow rate Q (L/min, e.g. 50 to 200).
        - 'buffer_capacity': Bicarbonate buffer concentration (mol/L, e.g. 0.001 to 0.005).
    """

    def __init__(self, params: PHModelParameters | None = None) -> None:
        self.params: PHModelParameters = params or PHModelParameters()

    @property
    def disturbance_names(self) -> tuple[str, ...]:
        return ("influent_ph", "flow_rate", "buffer_capacity")

    def _solve_ph_from_proton_excess(self, w: float, cb: float) -> float:
        """Solves the electroneutrality charge-balance equation for pH.

        w = [H+] - Kw/[H+] - (Cb * Ka) / (Ka + [H+])
        """
        kw = self.params.kw
        ka = self.params.ka_bicarbonate

        # Residual function in log10(H+) space for numerical stability across 14 decades
        def residual(log10_h: float) -> float:
            h = 10.0**log10_h
            return h - (kw / h) - (cb * ka) / (ka + h) - w

        # Root lies in physical pH range [0, 14] -> log10(H+) in [-14, 0]
        sol_log10_h = brentq(residual, -14.0, 0.0)
        return float(-sol_log10_h)

    def evaluate_scalar(
        self,
        dose: float,
        disturbances: Mapping[str, float],
    ) -> float:
        """Evaluates steady-state effluent pH for scalar inputs.

        Args:
            dose: Acid dosing rate (mL/min, >= 0).
            disturbances: Mapping with 'influent_ph', 'flow_rate', 'buffer_capacity'.

        Returns:
            Effluent pH (dimensionless, 0 to 14).
        """
        if dose < 0:
            raise ValueError(f"Acid dose cannot be negative: {dose}")

        ph_in = float(disturbances["influent_ph"])
        q = float(disturbances["flow_rate"])
        cb = float(disturbances["buffer_capacity"])

        if not (0.0 <= ph_in <= 14.0):
            raise ValueError(f"Influent pH out of range [0, 14]: {ph_in}")
        if q <= 0:
            raise ValueError(f"Flow rate must be positive: {q}")
        if cb < 0:
            raise ValueError(f"Buffer capacity cannot be negative: {cb}")

        # 1. Total alkaline normality of influent: [OH-] from free pH + buffering capacity
        oh_free = 10.0 ** (ph_in - 14.0)
        n_base = oh_free + cb

        q_tot = q + (dose / 1000.0)

        # 2. Net proton excess invariant xi (mol/L)
        acid_addition_rate = (dose / 1000.0) * self.params.c_acid_mol_per_l
        base_influent_rate = q * n_base
        xi = (acid_addition_rate - base_influent_rate) / q_tot

        # 3. Exact solution of electroneutrality quadratic: [H+]^2 - xi*[H+] - Kw = 0
        kw = self.params.kw
        h_conc = (xi + math.sqrt(xi**2 + 4.0 * kw)) / 2.0
        effluent_ph = -math.log10(h_conc)
        return float(effluent_ph)

    def evaluate_interval(
        self,
        dose: float | Interval,
        disturbances: Mapping[str, Interval],
    ) -> Interval:
        """Conservatively evaluates effluent pH interval under bounded uncertainties.

        Exploits the proven monotonicity of the neutralization curve:
            - Effluent pH is strictly decreasing with acid dose d
            - Effluent pH is strictly increasing with influent pH
            - Effluent pH is strictly increasing with flow rate Q
            - Effluent pH is strictly increasing with buffer capacity Cb

        Returns:
            Guaranteed enclosing Interval of effluent pH [pH_min, pH_max].
        """
        d_int = Interval(dose, dose) if isinstance(dose, (int, float)) else dose
        ph_int = disturbances["influent_ph"]
        q_int = disturbances["flow_rate"]
        cb_int = disturbances["buffer_capacity"]

        # Maximum effluent pH occurs at minimum acid dose and maximum alkaline disturbance
        max_disturbances = {
            "influent_ph": ph_int.hi,
            "flow_rate": q_int.hi,
            "buffer_capacity": cb_int.hi,
        }
        ph_max = self.evaluate_scalar(d_int.lo, max_disturbances)

        # Minimum effluent pH occurs at maximum acid dose and minimum alkaline disturbance
        min_disturbances = {
            "influent_ph": ph_int.lo,
            "flow_rate": q_int.lo,
            "buffer_capacity": cb_int.lo,
        }
        ph_min = self.evaluate_scalar(d_int.hi, min_disturbances)

        return Interval(ph_min, ph_max)


def run_ph_demonstration() -> None:
    """Runs an interactive reachability demonstration for pH neutralization."""
    console.print(
        Panel.fit(
            "[bold cyan]certified-dose Process Neutralization Demonstration[/bold cyan]\n"
            "Domain: Continuous Stirred Tank Reactor (CSTR) Industrial Neutralization\n"
            "Goal: Certify acid dosing keeps effluent pH <= 8.5 regulatory discharge ceiling",
            title="[bold green]Domain Generalization Demonstration[/bold green]",
        )
    )

    model = PHNeutralizationModel()
    engine = ReachabilityEngine(model=model, safety_margin=0.05)

    # Operating conditions with sensor uncertainties
    # Raw wastewater is alkaline (pH 10.2 +/- 0.3)
    disturbances = {
        "influent_ph": Interval(9.9, 10.5),
        "flow_rate": Interval(90.0, 110.0),  # L/min (100 +/- 10%)
        "buffer_capacity": Interval(0.0004, 0.0006),  # mol/L buffer
    }

    test_doses = [0.0, 150.0, 350.0, 640.0, 750.0]  # mL/min acid
    compliance_ceiling = 8.50

    table = Table(title="Reachability Analysis for CSTR Acid Dosing")
    table.add_column("Acid Dose (mL/min)", justify="right", style="cyan")
    table.add_column("Reachable pH Envelope [lo, hi]", justify="center")
    table.add_column("Compliance (< 8.5 pH)", justify="center")
    table.add_column("Monte Carlo Fuzz Check", justify="center")

    for d in test_doses:
        r_set = engine.compute_reachable_set(d, disturbances)
        is_safe = r_set.hi <= compliance_ceiling

        fuzz_check = engine.verify_against_monte_carlo(
            d, disturbances, n_samples=2000, seed=42
        )
        fuzz_str = (
            "[bold green]Sound (margin: +{:.3f})[/bold green]".format(
                fuzz_check["margin_hi"]
            )
            if fuzz_check["is_conservative"]
            else "[bold red]VIOLATED[/bold red]"
        )

        status_str = (
            "[bold green]CERTIFIED SAFE[/bold green]"
            if is_safe
            else "[bold red]REJECTED (Alkaline Breach)[/bold red]"
        )

        table.add_row(
            f"{d:.1f}",
            f"[{r_set.lo:.2f}, {r_set.hi:.2f}]",
            status_str,
            fuzz_str,
        )

    console.print(table)


if __name__ == "__main__":
    run_ph_demonstration()
