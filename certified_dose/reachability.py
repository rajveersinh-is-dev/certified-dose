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
from certified_dose.process_model import ProcessModel, SyntheticProcessModel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReachableSet:
    """Represents the guaranteed bounding interval of effluent concentration.

    Attributes:
        lo: Lower bound of attainable effluent concentration.
        hi: Worst-case upper bound of attainable effluent concentration.
        dose: Applied candidate dose.
        disturbances: Disturbance intervals used for the reachability computation.
        safety_margin: Additive margin applied for numerical safety.
    """

    lo: float
    hi: float
    dose: float
    disturbances: Mapping[str, Interval]
    safety_margin: float

    @property
    def interval(self) -> Interval:
        """Returns the reachability set as an Interval instance."""
        return Interval(self.lo, self.hi)

    @property
    def width(self) -> float:
        """Width of the uncertainty envelope."""
        return self.hi - self.lo

    def contains(self, value: float) -> bool:
        """Checks if a scalar value is contained within the reachable bounds."""
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
        model: ProcessModel | None = None,
        safety_margin: float = 0.02,
    ) -> None:
        """Initializes the reachability engine.

        Args:
            model: Process model instance. Defaults to SyntheticProcessModel().
            safety_margin: Additive margin to widen the reachable set,
                compensating for floating-point rounding and linearization errors.
        """
        if safety_margin < 0:
            raise ValueError(f"Safety margin cannot be negative: {safety_margin}")
        self.model: ProcessModel = (
            model if model is not None else SyntheticProcessModel()
        )
        self.safety_margin: float = float(safety_margin)

    def compute_reachable_set(
        self,
        dose: float,
        disturbances: Mapping[str, Interval | float],
        compliance_limit: float = 1.0,
    ) -> ReachableSet:
        """Computes the guaranteed reachable set for a given candidate dose.

        Args:
            dose: Proposed chemical or control dose.
            disturbances: Mapping containing disturbance intervals or floats for each
                variable specified in self.model.disturbance_names.
            compliance_limit: Regulatory limit for checking safety.

        Returns:
            ReachableSet containing [lo, hi] bounds and metadata.

        Raises:
            KeyError: If required disturbance variables are missing.
            ValueError: If inputs are invalid or out of physical bounds.
        """
        normalized: dict[str, Interval] = {}

        for key in self.model.disturbance_names:
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
            disturbances=normalized,
        )

        # Apply safety margin: widen the envelope to guarantee conservativeness
        widened = raw_interval.widen(self.safety_margin)
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

        samples: dict[str, np.ndarray] = {
            key: rng.uniform(disturbances[key].lo, disturbances[key].hi, n_samples)
            for key in self.model.disturbance_names
        }

        outputs = [
            self.model.evaluate_scalar(
                dose=dose,
                disturbances={
                    key: float(samples[key][i]) for key in self.model.disturbance_names
                },
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
