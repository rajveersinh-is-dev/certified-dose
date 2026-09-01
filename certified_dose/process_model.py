"""Synthetic nonlinear wastewater coagulation process model.

DISCLOSURE & LIMITATIONS:
This process model is purely synthetic and designed for demonstration and research
purposes. It captures qualitative coagulation dynamics (diminishing returns,
optimal dosing window, overdosing restabilization, and hydraulic flow sensitivity),
but it is NOT calibrated to any physical plant or validated for real-world
regulatory compliance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from certified_dose.intervals import Interval


@dataclass(frozen=True)
class ModelParameters:
    """Parameters governing the synthetic coagulation kinetics.

    Attributes:
        t_floor: Minimum attainable effluent turbidity (NTU) at ideal settling.
        c1: Removal kinetics rate coefficient.
        c2: Overdosing restabilization coefficient.
        q_nom: Nominal plant hydraulic flow rate (m3/h).
        ph_opt: Optimal coagulation pH (minimal required coagulant demand).
        temp_nom: Nominal water temperature (deg C).
    """

    t_floor: float = 0.12
    c1: float = 0.55
    c2: float = 0.00012
    q_nom: float = 1000.0
    ph_opt: float = 7.2
    temp_nom: float = 18.0


class SyntheticProcessModel:
    """Synthetic nonlinear coagulant dosing process model.

    Evaluates effluent turbidity (NTU) as a function of coagulant dose (mg/L)
    and environmental influent disturbances:
        - Influent turbidity (NTU)
        - Flow rate (m3/h)
        - pH
        - Water temperature (deg C)

    Supports evaluation on both scalar floats and Interval instances.
    """

    def __init__(self, params: ModelParameters | None = None) -> None:
        """Initializes the synthetic process model.

        Args:
            params: Kinetic and environmental parameters. Defaults to standard baseline.
        """
        self.params: ModelParameters = params or ModelParameters()

    def evaluate_scalar(
        self,
        dose: float,
        influent_turbidity: float,
        flow_rate: float,
        ph: float,
        temperature: float,
    ) -> float:
        """Evaluates true scalar effluent turbidity.

        Args:
            dose: Applied coagulant dose (mg/L, >= 0).
            influent_turbidity: Raw water influent turbidity (NTU, > 0).
            flow_rate: Hydraulic flow rate (m3/h, > 0).
            ph: Raw water pH.
            temperature: Water temperature (deg C).

        Returns:
            Computed effluent turbidity (NTU).

        Raises:
            ValueError: If inputs are non-physical (e.g. negative dose or turbidity).
        """
        if dose < 0:
            raise ValueError(f"Coagulant dose cannot be negative: {dose}")
        if influent_turbidity <= 0:
            raise ValueError(
                f"Influent turbidity must be positive: {influent_turbidity}"
            )
        if flow_rate <= 0:
            raise ValueError(f"Flow rate must be positive: {flow_rate}")

        p = self.params

        # Temperature correction factor on removal kinetics
        # Colder water slows coagulation hydrolyzation and flocs formation
        temp_factor = 1.0 + 0.015 * (p.temp_nom - temperature)
        temp_factor = max(0.5, temp_factor)

        # pH penalty: deviation from optimal pH reduces efficiency
        ph_factor = 1.0 + 0.20 * ((ph - p.ph_opt) ** 2)

        # Removal denominator term
        removal_denom = 1.0 + (p.c1 / (temp_factor * ph_factor)) * (dose**1.6)
        t_removal = p.t_floor + (influent_turbidity - p.t_floor) / removal_denom

        # Overdosing restabilization term: excess coagulant charges particles
        # Flow rate scales retention time in clarifiers
        flow_factor = (flow_rate / p.q_nom) ** 0.85
        t_overdose = p.c2 * (dose**2.1) * flow_factor * ph_factor

        effluent = t_removal + t_overdose
        return float(effluent)

    def evaluate_interval(
        self,
        dose: float | Interval,
        influent_turbidity: Interval,
        flow_rate: Interval,
        ph: Interval,
        temperature: Interval,
    ) -> Interval:
        """Conservatively evaluates effluent turbidity over input disturbance intervals.

        Guarantees that for any scalar realization within the input intervals,
        the true output is contained within the returned output interval.

        Args:
            dose: Applied coagulant dose (scalar or Interval).
            influent_turbidity: Bounded interval of raw water turbidity (NTU).
            flow_rate: Bounded interval of flow rate (m3/h).
            ph: Bounded interval of raw water pH.
            temperature: Bounded interval of water temperature (deg C).

        Returns:
            Guaranteed enclosing Interval of effluent turbidity [T_eff_min, T_eff_max].

        Raises:
            ValueError: If intervals contain non-physical negative values.
        """
        p = self.params

        d_int = Interval(dose, dose) if isinstance(dose, (int, float)) else dose
        if d_int.lo < 0 or influent_turbidity.lo <= 0 or flow_rate.lo <= 0:
            raise ValueError("Physical inputs must be strictly non-negative")

        # 1. Temperature factor: [1 + 0.015 * (temp_nom - temp)]
        # temp_nom - temperature is monotonic
        temp_diff = p.temp_nom - temperature
        temp_factor = 1.0 + 0.015 * temp_diff
        # Enforce minimum factor 0.5 conservatively
        temp_factor_lo = max(0.5, temp_factor.lo)
        temp_factor_hi = max(0.5, temp_factor.hi)
        temp_factor = Interval(temp_factor_lo, temp_factor_hi)

        # 2. pH penalty: 1.0 + 0.20 * (ph - ph_opt)^2
        ph_diff = ph - p.ph_opt
        ph_factor = 1.0 + 0.20 * (ph_diff**2)

        # 3. Removal term
        dose_term = d_int**1.6
        k_denom = temp_factor * ph_factor
        removal_denom = 1.0 + (p.c1 * dose_term) / k_denom
        t_removal = p.t_floor + (influent_turbidity - p.t_floor) / removal_denom

        # 4. Overdose term
        flow_ratio = flow_rate / p.q_nom
        flow_factor = flow_ratio**0.85
        overdose_dose = d_int**2.1
        t_overdose = (p.c2 * overdose_dose) * flow_factor * ph_factor

        effluent = t_removal + t_overdose
        return effluent

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Convenience dispatcher for scalar or interval evaluation."""
        if any(isinstance(a, Interval) for a in args) or any(
            isinstance(v, Interval) for v in kwargs.values()
        ):
            return self.evaluate_interval(*args, **kwargs)
        return self.evaluate_scalar(*args, **kwargs)
