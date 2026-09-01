"""Closed-loop dynamic plant simulation for certified dosing.

Simulates time-series plant operations under realistic environmental disturbances
(diurnal flow shifts, temperature variations, and storm-induced turbidity surges).
Records performance comparison between raw candidate controllers and the formal
reachability safety layer.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from certified_dose.certifier import CertifiedDoseWrapper
from certified_dose.controller import (
    AggressiveCostMinimizerController,
    BaseController,
    PlantState,
)
from certified_dose.intervals import Interval
from certified_dose.process_model import SyntheticProcessModel


@dataclass(frozen=True)
class SimulationRecord:
    """Telemetry data captured at each simulation control step."""

    step: int
    influent_turbidity: float
    flow_rate: float
    ph: float
    temperature: float
    candidate_dose: float
    certified_dose: float
    was_intervened: bool
    status: str
    candidate_effluent: float
    certified_effluent: float
    reachable_lo: float
    reachable_hi: float
    compliance_limit: float
    candidate_violated: bool
    certified_violated: bool


@dataclass
class SimulationSummary:
    """Aggregate metrics and performance statistics for a simulation run."""

    total_steps: int
    candidate_violations: int
    certified_violations: int
    interventions: int
    intervention_rate_pct: float
    mean_candidate_dose: float
    mean_certified_dose: float
    max_candidate_effluent: float
    max_certified_effluent: float
    compliance_limit: float
    records: list[SimulationRecord]

    def to_records_dict(self) -> list[dict[str, Any]]:
        """Converts step records to a list of standard dictionaries."""
        return [asdict(r) for r in self.records]


class ClosedLoopSimulator:
    """Orchestrates closed-loop simulation of plant dynamics and dosing safety."""

    def __init__(
        self,
        model: SyntheticProcessModel | None = None,
        certifier: CertifiedDoseWrapper | None = None,
        candidate_controller: BaseController | None = None,
    ) -> None:
        """Initializes the closed loop simulator.

        Args:
            model: Process kinetics model. Defaults to SyntheticProcessModel().
            certifier: Safety certifier wrapper. Defaults to standard wrapper.
            candidate_controller: Dosing policy. Defaults to AggressiveCostMinimizerController().
        """
        self.model: SyntheticProcessModel = model or SyntheticProcessModel()
        self.certifier: CertifiedDoseWrapper = certifier or CertifiedDoseWrapper(
            engine=None, compliance_limit=1.0
        )
        self.candidate_controller: BaseController = (
            candidate_controller or AggressiveCostMinimizerController()
        )

    def run(
        self,
        n_steps: int = 100,
        seed: int = 42,
        storm_start: int = 25,
        storm_duration: int = 20,
        uncertainty_override: dict[str, float] | None = None,
    ) -> SimulationSummary:
        """Executes the closed loop simulation over n_steps.

        Args:
            n_steps: Total timesteps to simulate.
            seed: Random seed for disturbance noise.
            storm_start: Step index where high-turbidity storm surge initiates.
            storm_duration: Duration in timesteps of storm event.
            uncertainty_override: Custom sensor uncertainty configuration.

        Returns:
            SimulationSummary containing full telemetry and compliance verification.
        """
        rng = np.random.default_rng(seed)
        records: list[SimulationRecord] = []

        # Baseline conditions
        base_turb = 24.0
        base_flow = 1000.0
        base_ph = 7.3
        base_temp = 17.5

        turb_noise = 0.0
        applied_dose = 22.0

        for step in range(n_steps):
            # Diurnal sinusoidal variation in flow and temperature
            hour_angle = (step % 24) * (2.0 * math.pi / 24.0)
            diurnal_flow = 120.0 * math.sin(hour_angle - math.pi / 2.0)
            diurnal_temp = 1.5 * math.sin(hour_angle - math.pi)

            # Storm event injection
            is_storm = storm_start <= step < (storm_start + storm_duration)
            storm_turb_boost = 35.0 if is_storm else 0.0
            storm_flow_boost = 250.0 if is_storm else 0.0

            # Autoregressive disturbance noise
            turb_noise = 0.7 * turb_noise + rng.normal(0.0, 1.8)
            flow_noise = rng.normal(0.0, 25.0)
            ph_noise = rng.normal(0.0, 0.04)

            # True realized plant state
            true_turbidity = max(5.0, base_turb + storm_turb_boost + turb_noise)
            true_flow = max(
                200.0, base_flow + diurnal_flow + storm_flow_boost + flow_noise
            )
            true_ph = max(6.0, min(8.5, base_ph + ph_noise))
            true_temp = max(4.0, min(30.0, base_temp + diurnal_temp))

            state = PlantState(
                turbidity=true_turbidity,
                flow_rate=true_flow,
                ph=true_ph,
                temperature=true_temp,
                previous_dose=applied_dose,
            )

            # 1. Candidate controller proposes an unverified dose
            proposed_dose = self.candidate_controller.propose_dose(state)

            # 2. Build disturbance intervals reflecting sensor uncertainty
            disturbances: dict[str, Interval] = (
                self.certifier.build_disturbance_intervals(state, uncertainty_override)
            )

            # 3. Certify candidate action
            cert_result = self.certifier.certify_action(proposed_dose, disturbances)
            certified_dose = cert_result.certified_dose
            applied_dose = certified_dose

            # 4. Evaluate true physical plant response under BOTH actions
            candidate_effluent = self.model.evaluate_scalar(
                dose=proposed_dose,
                influent_turbidity=true_turbidity,
                flow_rate=true_flow,
                ph=true_ph,
                temperature=true_temp,
            )

            certified_effluent = self.model.evaluate_scalar(
                dose=certified_dose,
                influent_turbidity=true_turbidity,
                flow_rate=true_flow,
                ph=true_ph,
                temperature=true_temp,
            )

            limit = self.certifier.compliance_limit
            candidate_violated = candidate_effluent > limit
            certified_violated = certified_effluent > limit

            record = SimulationRecord(
                step=step,
                influent_turbidity=true_turbidity,
                flow_rate=true_flow,
                ph=true_ph,
                temperature=true_temp,
                candidate_dose=proposed_dose,
                certified_dose=certified_dose,
                was_intervened=cert_result.was_intervened,
                status=cert_result.status.value,
                candidate_effluent=candidate_effluent,
                certified_effluent=certified_effluent,
                reachable_lo=cert_result.reachable_set.lo,
                reachable_hi=cert_result.reachable_set.hi,
                compliance_limit=limit,
                candidate_violated=candidate_violated,
                certified_violated=certified_violated,
            )
            records.append(record)

        # Aggregate metrics
        cand_violations = sum(1 for r in records if r.candidate_violated)
        cert_violations = sum(1 for r in records if r.certified_violated)
        interventions = sum(1 for r in records if r.was_intervened)

        return SimulationSummary(
            total_steps=n_steps,
            candidate_violations=cand_violations,
            certified_violations=cert_violations,
            interventions=interventions,
            intervention_rate_pct=(interventions / n_steps) * 100.0,
            mean_candidate_dose=float(np.mean([r.candidate_dose for r in records])),
            mean_certified_dose=float(np.mean([r.certified_dose for r in records])),
            max_candidate_effluent=float(max(r.candidate_effluent for r in records)),
            max_certified_effluent=float(max(r.certified_effluent for r in records)),
            compliance_limit=self.certifier.compliance_limit,
            records=records,
        )


def simulate_closed_loop(
    n_steps: int = 100,
    seed: int = 42,
    compliance_limit: float = 1.0,
    uncertainty_pct: float = 0.15,
) -> SimulationSummary:
    """Functional convenience wrapper to run a closed-loop simulation."""
    model = SyntheticProcessModel()
    certifier = CertifiedDoseWrapper(
        engine=None,
        compliance_limit=compliance_limit,
        default_uncertainty={
            "turbidity_pct": uncertainty_pct,
            "flow_rate_pct": uncertainty_pct * 0.7,
            "ph_delta": 0.30,
            "temp_delta": 2.0,
        },
    )
    simulator = ClosedLoopSimulator(model=model, certifier=certifier)
    return simulator.run(n_steps=n_steps, seed=seed)
