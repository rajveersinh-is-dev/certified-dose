"""Synthetic nonlinear wastewater coagulation process model.

DISCLOSURE & LIMITATIONS:
This process model is purely synthetic and designed for demonstration and research
purposes. It captures qualitative coagulation dynamics (diminishing returns,
optimal dosing window, overdosing restabilization, and hydraulic flow sensitivity),
but it is NOT calibrated to any physical plant or validated for real-world
regulatory compliance.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from certified_dose.intervals import Interval


class ProcessModel(ABC):
    """Abstract base class for physical process models evaluated by ReachabilityEngine.

    Any physical or chemical process (water treatment, bioreactor, chemical CSTR,
    thermal system) implements this interface to receive formal reachability
    safety certificates.
    """

    @property
    @abstractmethod
    def disturbance_names(self) -> tuple[str, ...]:
        """Names of required disturbance / environmental input variables."""
        ...

    @abstractmethod
    def evaluate_scalar(
        self,
        dose: float,
        *args: Any,
        **kwargs: Any,
    ) -> float:
        """Evaluates scalar process output given a candidate dose and disturbance values."""
        ...

    @abstractmethod
    def evaluate_interval(
        self,
        dose: float | Interval,
        *args: Any,
        **kwargs: Any,
    ) -> Interval:
        """Evaluates guaranteed enclosing output interval under bounded input intervals."""
        ...


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


class SyntheticProcessModel(ProcessModel):
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

    @property
    def disturbance_names(self) -> tuple[str, ...]:
        """Names of required disturbance variables."""
        return ("turbidity", "flow_rate", "ph", "temperature")

    def evaluate_scalar(
        self,
        dose: float,
        influent_turbidity: float | Mapping[str, float] | None = None,
        flow_rate: float | None = None,
        ph: float | None = None,
        temperature: float | None = None,
        *,
        disturbances: Mapping[str, float] | None = None,
    ) -> float:
        """Evaluates true scalar effluent turbidity.

        Supports invocation with either positional disturbance arguments or a
        `disturbances` mapping containing keys 'turbidity', 'flow_rate', 'ph', 'temperature'.

        Args:
            dose: Applied coagulant dose (mg/L, >= 0).
            influent_turbidity: Raw water influent turbidity (NTU, > 0) or disturbances mapping.
            flow_rate: Hydraulic flow rate (m3/h, > 0).
            ph: Raw water pH.
            temperature: Water temperature (deg C).
            disturbances: Optional keyword mapping of disturbance variables.

        Returns:
            Computed effluent turbidity (NTU).

        Raises:
            ValueError: If inputs are non-physical or missing.
        """
        if isinstance(influent_turbidity, Mapping):
            dist_map = influent_turbidity
        elif disturbances is not None:
            dist_map = disturbances
        else:
            if (
                influent_turbidity is None
                or flow_rate is None
                or ph is None
                or temperature is None
            ):
                raise ValueError("Missing required disturbance parameters")
            dist_map = {
                "turbidity": float(influent_turbidity),
                "flow_rate": float(flow_rate),
                "ph": float(ph),
                "temperature": float(temperature),
            }

        t_in = dist_map.get("turbidity", dist_map.get("influent_turbidity", 0.0))
        q = dist_map["flow_rate"]
        p_val = dist_map["ph"]
        temp = dist_map["temperature"]

        if dose < 0:
            raise ValueError(f"Coagulant dose cannot be negative: {dose}")
        if t_in <= 0:
            raise ValueError(f"Influent turbidity must be positive: {t_in}")
        if q <= 0:
            raise ValueError(f"Flow rate must be positive: {q}")

        p = self.params

        # Temperature correction factor on removal kinetics
        temp_factor = 1.0 + 0.015 * (p.temp_nom - temp)
        temp_factor = max(0.5, temp_factor)

        # pH penalty: deviation from optimal pH reduces efficiency
        ph_factor = 1.0 + 0.20 * ((p_val - p.ph_opt) ** 2)

        # Removal denominator term
        removal_denom = 1.0 + (p.c1 / (temp_factor * ph_factor)) * (dose**1.6)
        t_removal = p.t_floor + (t_in - p.t_floor) / removal_denom

        # Overdosing restabilization term
        flow_factor = (q / p.q_nom) ** 0.85
        t_overdose = p.c2 * (dose**2.1) * flow_factor * ph_factor

        effluent = t_removal + t_overdose
        return float(effluent)

    def evaluate_interval(
        self,
        dose: float | Interval,
        influent_turbidity: Interval | Mapping[str, Interval] | None = None,
        flow_rate: Interval | None = None,
        ph: Interval | None = None,
        temperature: Interval | None = None,
        *,
        disturbances: Mapping[str, Interval] | None = None,
    ) -> Interval:
        """Conservatively evaluates effluent turbidity over input disturbance intervals.

        Guarantees that for any scalar realization within the input intervals,
        the true output is contained within the returned output interval.

        Args:
            dose: Applied coagulant dose (scalar or Interval).
            influent_turbidity: Bounded interval of raw turbidity or disturbances mapping.
            flow_rate: Bounded interval of flow rate (m3/h).
            ph: Bounded interval of raw water pH.
            temperature: Bounded interval of water temperature (deg C).
            disturbances: Optional keyword mapping of disturbance intervals.

        Returns:
            Guaranteed enclosing Interval of effluent turbidity [T_eff_min, T_eff_max].

        Raises:
            ValueError: If intervals contain non-physical negative values or are missing.
        """
        if isinstance(influent_turbidity, Mapping):
            dist_map = influent_turbidity
        elif disturbances is not None:
            dist_map = disturbances
        else:
            if (
                influent_turbidity is None
                or flow_rate is None
                or ph is None
                or temperature is None
            ):
                raise ValueError("Missing required disturbance intervals")
            dist_map = {
                "turbidity": influent_turbidity,
                "flow_rate": flow_rate,
                "ph": ph,
                "temperature": temperature,
            }

        t_in_int = dist_map.get("turbidity", dist_map.get("influent_turbidity"))
        if t_in_int is None:
            raise KeyError("Missing required disturbance key: 'turbidity'")
        q_int = dist_map["flow_rate"]
        ph_int = dist_map["ph"]
        temp_int = dist_map["temperature"]

        p = self.params

        d_int = Interval(dose, dose) if isinstance(dose, (int, float)) else dose
        if d_int.lo < 0 or t_in_int.lo <= 0 or q_int.lo <= 0:
            raise ValueError("Physical inputs must be strictly non-negative")

        # 1. Temperature factor: [1 + 0.015 * (temp_nom - temp)]
        temp_diff = p.temp_nom - temp_int
        temp_factor = 1.0 + 0.015 * temp_diff
        temp_factor_lo = max(0.5, temp_factor.lo)
        temp_factor_hi = max(0.5, temp_factor.hi)
        temp_factor = Interval(temp_factor_lo, temp_factor_hi)

        # 2. pH penalty: 1.0 + 0.20 * (ph - ph_opt)^2
        ph_diff = ph_int - p.ph_opt
        ph_factor = 1.0 + 0.20 * (ph_diff**2)

        # 3. Removal term
        dose_term = d_int**1.6
        k_denom = temp_factor * ph_factor
        removal_denom = 1.0 + (p.c1 * dose_term) / k_denom
        t_removal = p.t_floor + (t_in_int - p.t_floor) / removal_denom

        # 4. Overdose term
        flow_ratio = q_int / p.q_nom
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
