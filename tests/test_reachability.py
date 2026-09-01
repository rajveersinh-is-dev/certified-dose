"""Tests for process model and reachability analysis engine."""

import pytest

from certified_dose.intervals import Interval
from certified_dose.process_model import SyntheticProcessModel
from certified_dose.reachability import ReachabilityEngine


def test_process_model_scalar_behavior() -> None:
    model = SyntheticProcessModel()

    # 1. Zero dose should yield approximately raw turbidity (no removal)
    turb_zero = model.evaluate_scalar(
        dose=0.0, influent_turbidity=30.0, flow_rate=1000.0, ph=7.2, temperature=18.0
    )
    assert abs(turb_zero - 30.0) < 1e-4

    # 2. Optimal dose should significantly reduce turbidity
    turb_opt = model.evaluate_scalar(
        dose=20.0, influent_turbidity=30.0, flow_rate=1000.0, ph=7.2, temperature=18.0
    )
    assert turb_opt < 1.0

    # 3. Severe overdosing causes restabilization (effluent increases again)
    turb_over = model.evaluate_scalar(
        dose=70.0, influent_turbidity=30.0, flow_rate=1000.0, ph=7.2, temperature=18.0
    )
    assert turb_over > turb_opt


def test_process_model_invalid_inputs() -> None:
    model = SyntheticProcessModel()

    with pytest.raises(ValueError, match="cannot be negative"):
        model.evaluate_scalar(
            dose=-1.0,
            influent_turbidity=20.0,
            flow_rate=1000.0,
            ph=7.2,
            temperature=18.0,
        )

    with pytest.raises(ValueError, match="must be positive"):
        model.evaluate_scalar(
            dose=10.0,
            influent_turbidity=-5.0,
            flow_rate=1000.0,
            ph=7.2,
            temperature=18.0,
        )


def test_reachability_engine_basic() -> None:
    engine = ReachabilityEngine(safety_margin=0.03)

    disturbances = {
        "turbidity": Interval(20.0, 30.0),
        "flow_rate": Interval(900.0, 1100.0),
        "ph": Interval(7.0, 7.4),
        "temperature": Interval(15.0, 20.0),
    }

    r_set = engine.compute_reachable_set(dose=22.0, disturbances=disturbances)
    assert r_set.lo >= 0.0
    assert r_set.hi > r_set.lo
    assert r_set.dose == 22.0
    assert r_set.safety_margin == 0.03
    assert r_set.contains(r_set.lo + 0.1)
    assert r_set.interval.lo == r_set.lo
    assert not r_set.violates_limit(10.0)
    assert r_set.violates_limit(0.1)

    # Missing disturbance key
    with pytest.raises(KeyError, match="Missing required disturbance"):
        engine.compute_reachable_set(
            dose=20.0, disturbances={"turbidity": Interval(20.0, 30.0)}
        )

    # Invalid disturbance type
    with pytest.raises(TypeError, match="must be float or Interval"):
        engine.compute_reachable_set(
            dose=20.0,
            disturbances={
                "turbidity": "invalid",
                "flow_rate": 1000.0,
                "ph": 7.2,
                "temperature": 18.0,
            },  # type: ignore[dict-item]
        )

    # Safety margin negative
    with pytest.raises(ValueError, match="cannot be negative"):
        ReachabilityEngine(safety_margin=-0.01)


def test_process_model_call_dispatcher() -> None:
    model = SyntheticProcessModel()
    # Scalar via __call__
    scalar_res = model(
        dose=20.0, influent_turbidity=25.0, flow_rate=1000.0, ph=7.2, temperature=18.0
    )
    assert isinstance(scalar_res, float)

    # Interval via __call__
    int_res = model(
        dose=20.0,
        influent_turbidity=Interval(20.0, 30.0),
        flow_rate=Interval(900.0, 1100.0),
        ph=Interval(7.0, 7.4),
        temperature=Interval(16.0, 19.0),
    )
    assert isinstance(int_res, Interval)


@pytest.mark.parametrize("test_dose", [8.0, 18.0, 26.0, 45.0])
def test_fuzz_reachability_conservativeness_against_monte_carlo(
    test_dose: float,
) -> None:
    """Fuzz test verifying that the interval reachable set bounds 1,000 Monte Carlo samples."""
    engine = ReachabilityEngine(safety_margin=0.02)

    disturbances = {
        "turbidity": Interval(18.0, 35.0),
        "flow_rate": Interval(850.0, 1150.0),
        "ph": Interval(6.9, 7.6),
        "temperature": Interval(12.0, 22.0),
    }

    result = engine.verify_against_monte_carlo(
        dose=test_dose, disturbances=disturbances, n_samples=1000, seed=123
    )

    assert result["is_conservative"], (
        f"Conservativeness violated for dose {test_dose}! "
        f"MC range [{result['mc_min']:.4f}, {result['mc_max']:.4f}], "
        f"Reachable interval [{result['reachable_lo']:.4f}, {result['reachable_hi']:.4f}]"
    )
    assert result["margin_hi"] >= 0.0
