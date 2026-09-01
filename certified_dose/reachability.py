"""Reachability analysis engine for bounding process output variables.

Propagates bounded input uncertainties through the nonlinear process model
using conservative interval arithmetic, computing the guaranteed enclosing set
of possible effluent states.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from certified_dose.intervals import Interval
from certified_dose.process_model import SyntheticProcessModel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReachableSet:
    """Guaranteed reachability envelope for an output variable.

    Attributes:
        lo: Minimum reachable output value.
        hi: Maximum reachable output value (worst-case upper bound).
        dose: The candidate coagulant dose evaluated.
        disturbances: The input disturbance intervals used.
        safety_margin: The applied conservativeness margin.
    """

    lo: float
    hi: float
    dose: float
    disturbances: dict[str, Interval]
    safety_margin: float

    @property
    def interval(self) -> Interval:
        """Returns the reachable set as an Interval."""
        return Interval(self.lo, self.hi)

    def contains(self, value: float) -> bool:
        """Checks if a scalar value is contained in the reachable set."""
        return self.lo <= value <= self.hi

    def violates_limit(self, limit: float) -> bool:
        """Checks if the worst-case reachable bound violates a regulatory limit."""
        return self.hi > limit


class ReachabilityEngine:
    """Computes guaranteed output reachable sets under bounded input uncertainty.

    Guarantees conservative over-approximation: for all possible realizations
    of disturbances within their specified intervals, the true process output
    is guaranteed to lie within [reachable.lo, reachable.hi].
    """

    def __init__(
        self,
        model: SyntheticProcessModel | None = None,
        safety_margin: float = 0.02,
    ) -> None:
        """Initializes the reachability engine.

        Args:
            model: Process model instance. Defaults to SyntheticProcessModel().
            safety_margin: Additive margin (NTU) to widen the reachable set,
                compensating for floating-point rounding and linearization errors.
        """
        if safety_margin < 0:
            raise ValueError(f"Safety margin cannot be negative: {safety_margin}")
        self.model: SyntheticProcessModel = model or SyntheticProcessModel()
        self.safety_margin: float = float(safety_margin)

    def compute_reachable_set(
        self,
        dose: float,
        disturbances: Mapping[str, Interval | float],
    ) -> ReachableSet:
        """Computes the guaranteed reachable set for a given candidate dose.

        Args:
            dose: Proposed coagulant dose (mg/L).
            disturbances: Mapping containing disturbance intervals or floats:
                - 'turbidity' (NTU)
                - 'flow_rate' (m3/h)
                - 'ph'
                - 'temperature' (deg C)

        Returns:
            ReachableSet containing [lo, hi] bounds and metadata.

        Raises:
            KeyError: If required disturbance variables are missing.
            ValueError: If inputs are invalid or out of physical bounds.
        """
        required_keys = ("turbidity", "flow_rate", "ph", "temperature")
        normalized: dict[str, Interval] = {}

        for key in required_keys:
            if key not in disturbances:
                raise KeyError(f"Missing required disturbance input: '{key}'")
            val = disturbances[key]
            if isinstance(val, (int, float)):
                normalized[key] = Interval(float(val), float(val))
            elif isinstance(val, Interval):
                normalized[key] = val
            else:
                raise TypeError(
                    f"Disturbance '{key}' must be float or Interval, got {type(val)}"
                )

        raw_interval: Interval = self.model.evaluate_interval(
            dose=dose,
            influent_turbidity=normalized["turbidity"],
            flow_rate=normalized["flow_rate"],
            ph=normalized["ph"],
            temperature=normalized["temperature"],
        )

        # Apply safety margin: widen the envelope to guarantee conservativeness
        widened = raw_interval.widen(self.safety_margin)
        # Effluent turbidity is physically non-negative
        bounded_lo = max(0.0, widened.lo)
        bounded_hi = widened.hi

        return ReachableSet(
            lo=bounded_lo,
            hi=bounded_hi,
            dose=float(dose),
            disturbances=normalized,
            safety_margin=self.safety_margin,
        )

    def verify_against_monte_carlo(
        self,
        dose: float,
        disturbances: Mapping[str, Interval],
        n_samples: int = 1000,
        seed: int | None = 42,
    ) -> dict[str, Any]:
        """Fuzz-verifies conservativeness by comparing with Monte Carlo sampling.

        Generates n_samples random realizations uniformly distributed within the
        disturbance intervals and asserts that the interval reachable set
        strictly bounds all sampled outcomes.

        Args:
            dose: Candidate dose to test.
            disturbances: Input disturbance intervals.
            n_samples: Number of random evaluation points.
            seed: Random seed for reproducibility.

        Returns:
            Dictionary with verification results and statistics:
                - 'is_conservative': bool (True if all samples <= reachable.hi)
                - 'mc_min': float
                - 'mc_max': float
                - 'reachable_lo': float
                - 'reachable_hi': float
                - 'margin_hi': float (reachable_hi - mc_max, >= 0 if sound)
        """
        rng = np.random.default_rng(seed)
        reachable = self.compute_reachable_set(dose, disturbances)

        t_samples = rng.uniform(
            disturbances["turbidity"].lo, disturbances["turbidity"].hi, n_samples
        )
        q_samples = rng.uniform(
            disturbances["flow_rate"].lo, disturbances["flow_rate"].hi, n_samples
        )
        ph_samples = rng.uniform(
            disturbances["ph"].lo, disturbances["ph"].hi, n_samples
        )
        temp_samples = rng.uniform(
            disturbances["temperature"].lo, disturbances["temperature"].hi, n_samples
        )

        outputs = [
            self.model.evaluate_scalar(
                dose=dose,
                influent_turbidity=float(t_samples[i]),
                flow_rate=float(q_samples[i]),
                ph=float(ph_samples[i]),
                temperature=float(temp_samples[i]),
            )
            for i in range(n_samples)
        ]

        mc_min = float(min(outputs))
        mc_max = float(max(outputs))

        # Check soundness: interval must contain all samples
        is_conservative = (reachable.lo <= mc_min + 1e-9) and (
            mc_max <= reachable.hi + 1e-9
        )

        return {
            "is_conservative": is_conservative,
            "mc_min": mc_min,
            "mc_max": mc_max,
            "reachable_lo": reachable.lo,
            "reachable_hi": reachable.hi,
            "margin_hi": reachable.hi - mc_max,
            "margin_lo": mc_min - reachable.lo,
        }
