"""Candidate dosing controllers.

Provides swappable controller interfaces for proposing chemical dosing actions.
These represent black-box controllers (e.g. ML, heuristic, or cost-minimizing
agents) that optimize nominal performance but do not provide formal worst-case
safety guarantees on their own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PlantState:
    """Observed process state measurements.

    Attributes:
        turbidity: Measured influent turbidity (NTU).
        flow_rate: Measured hydraulic flow rate (m3/h).
        ph: Measured pH.
        temperature: Measured water temperature (deg C).
        previous_dose: The dose applied in the previous control step (mg/L).
    """

    turbidity: float
    flow_rate: float
    ph: float
    temperature: float
    previous_dose: float = 20.0


class BaseController(Protocol):
    """Protocol defining the interface for candidate dosing controllers."""

    def propose_dose(self, state: PlantState) -> float:
        """Proposes a coagulant dose setpoint for the current plant state.

        Args:
            state: Current measured plant state.

        Returns:
            Proposed chemical dose (mg/L).
        """
        ...


class HeuristicController:
    """Traditional empirical jar-test heuristic controller.

    Computes dose based on standard water treatment power-law relationships:
        dose = k * (turbidity)^0.55 * (flow / 1000)^0.2
    """

    def __init__(self, k_base: float = 4.2) -> None:
        """Initializes the heuristic controller.

        Args:
            k_base: Scaling gain calibrated to raw turbidity.
        """
        self.k_base = k_base

    def propose_dose(self, state: PlantState) -> float:
        """Proposes dose using empirical power-law formula."""
        t_term = max(1.0, state.turbidity) ** 0.55
        q_term = max(0.1, state.flow_rate / 1000.0) ** 0.20
        # Temperature compensation (colder water needs slightly more coagulant)
        temp_comp = 1.0 + 0.01 * (18.0 - state.temperature)
        dose = self.k_base * t_term * q_term * max(0.8, temp_comp)
        return float(max(0.0, dose))


class AggressiveCostMinimizerController:
    """Simulated ML/RL controller that aggressively minimizes chemical costs.

    Optimizes for chemical consumption by targeting the edge of the regulatory
    envelope (e.g. aiming for 0.85 NTU when limit is 1.0 NTU). Under nominal
    conditions it saves 30-40% chemical costs, but under sudden influent surges
    it routinely proposes under-doses that violate compliance without formal guards.
    """

    def __init__(self, target_effluent: float = 0.85, aggression: float = 0.65) -> None:
        """Initializes the cost-minimizing controller.

        Args:
            target_effluent: Target effluent turbidity (NTU).
            aggression: Chemical reduction multiplier (< 1.0 reduces dose).
        """
        self.target_effluent = target_effluent
        self.aggression = aggression

    def propose_dose(self, state: PlantState) -> float:
        """Proposes an aggressive low dose that prioritizes cost savings."""
        # Baseline estimate
        baseline = 3.8 * (max(1.0, state.turbidity) ** 0.52)
        # Aggressively scale down dose to save money
        shaved_dose = baseline * self.aggression
        return float(max(0.0, shaved_dose))


class AdversarialController:
    """Adversarial stress-test controller.

    Deliberately proposes extreme edge-case doses (0 mg/L or extreme overdosing)
    to verify that the certification layer unconditionally rejects dangerous actions.
    """

    def __init__(self, pattern: list[float] | None = None) -> None:
        """Initializes adversarial controller.

        Args:
            pattern: Cyclic list of test doses. Defaults to [0.0, 85.0, 1.5, 95.0].
        """
        self.pattern = pattern or [0.0, 85.0, 1.5, 95.0]
        self._index = 0

    def propose_dose(self, state: PlantState) -> float:
        """Proposes the next adversarial dose in sequence."""
        dose = self.pattern[self._index % len(self.pattern)]
        self._index += 1
        return float(dose)


class ConstantDoseController:
    """Fixed-recipe controller that always proposes a constant dose."""

    def __init__(self, fixed_dose: float = 24.0) -> None:
        """Initializes constant dose controller.

        Args:
            fixed_dose: Constant chemical dose setpoint (mg/L).
        """
        self.fixed_dose = float(fixed_dose)

    def propose_dose(self, state: PlantState) -> float:
        """Returns the constant dose."""
        return self.fixed_dose
