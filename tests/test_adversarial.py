"""Adversarial and extreme edge-case test suite for certified-dose.

Validates robustness and formal guarantees under:
1. Degenerate (zero-width) intervals and extremely wide uncertainty bounds.
2. Compliance boundary epsilon tests (doses exactly at and epsilon away from limit).
3. Numerical edge cases: extreme magnitudes (subnormals, large floats), NaN/Inf handling,
   and comprehensive exponent arithmetic (especially negative fractional and odd/even powers).
4. Correlated / non-independent sensor scenarios that violate the independence assumption.
"""

from __future__ import annotations

import math

import pytest

from certified_dose.certifier import (
    CertificationStatus,
    CertifiedDoseWrapper,
)
from certified_dose.intervals import Interval
from certified_dose.process_model import SyntheticProcessModel
from certified_dose.reachability import ReachabilityEngine

# =============================================================================
# 1. DEGENERATE AND EXTREMELY WIDE UNCERTAINTY BOUNDS
# =============================================================================


def test_degenerate_zero_width_intervals_collapse_to_scalar() -> None:
    """Degenerate intervals Interval(x, x) must equal exact scalar evaluation within safety margin."""
    model = SyntheticProcessModel()
    engine = ReachabilityEngine(model=model, safety_margin=0.0)

    dose = 18.0
    turb = 25.0
    flow = 1000.0
    ph_val = 7.2
    temp_val = 18.0

    scalar_effluent = model.evaluate_scalar(
        dose=dose,
        influent_turbidity=turb,
        flow_rate=flow,
        ph=ph_val,
        temperature=temp_val,
    )

    degenerate_state = {
        "turbidity": Interval(turb, turb),
        "flow_rate": Interval(flow, flow),
        "ph": Interval(ph_val, ph_val),
        "temperature": Interval(temp_val, temp_val),
    }

    reachable = engine.compute_reachable_set(dose=dose, disturbances=degenerate_state)

    # Width of reachable set for zero-width inputs with zero safety margin should be ~0.0
    assert reachable.width == pytest.approx(0.0, abs=1e-12)
    assert reachable.lo == pytest.approx(scalar_effluent, rel=1e-9)
    assert reachable.hi == pytest.approx(scalar_effluent, rel=1e-9)
    assert reachable.contains(scalar_effluent)


def test_extremely_wide_uncertainty_bounds_monotonic_and_sound() -> None:
    """Extremely wide disturbance intervals spanning orders of magnitude must not crash."""
    engine = ReachabilityEngine()
    wrapper = CertifiedDoseWrapper(engine=engine, compliance_limit=1.0)

    # Extreme physical domain bounds
    extreme_state = {
        "turbidity": Interval(0.01, 1000.0),
        "flow_rate": Interval(10.0, 10000.0),
        "ph": Interval(4.0, 10.0),
        "temperature": Interval(1.0, 40.0),
    }

    # Low dose cannot possibly clear 1000 NTU influent
    result_low = wrapper.certify_action(2.0, extreme_state)
    assert result_low.candidate_reachable_set is not None
    assert result_low.candidate_reachable_set.hi > 1.0
    assert result_low.status in (
        CertificationStatus.REJECTED_CORRECTED,
        CertificationStatus.FAILED_SAFE_FALLBACK,
    )

    # Verification: output bounds must remain finite, positive, and ordered
    r = result_low.candidate_reachable_set
    assert r.lo >= 0.0
    assert r.hi >= r.lo
    assert not math.isnan(r.lo)
    assert not math.isnan(r.hi)
    assert not math.isinf(r.hi)


# =============================================================================
# 2. COMPLIANCE LIMIT BOUNDARY EPSILON TESTING
# =============================================================================


def test_compliance_boundary_exact_and_epsilon_discrimination() -> None:
    """Certifier must strictly accept when worst-case <= limit and reject when > limit."""
    engine = ReachabilityEngine(safety_margin=0.0)
    state = {
        "turbidity": Interval(20.0, 20.0),
        "flow_rate": Interval(1000.0, 10000.0 / 10.0),
        "ph": Interval(7.2, 7.2),
        "temperature": Interval(18.0, 18.0),
    }

    dose = 20.0
    r = engine.compute_reachable_set(dose, state)
    exact_hi = r.hi

    # Case A: Limit exactly at reachable upper bound -> MUST BE ACCEPTED (hi <= limit)
    wrapper_exact = CertifiedDoseWrapper(engine=engine, compliance_limit=exact_hi)
    res_exact = wrapper_exact.certify_action(dose, state)
    assert res_exact.status == CertificationStatus.ACCEPTED
    assert res_exact.certified_dose == dose

    # Case B: Limit epsilon BELOW reachable upper bound -> MUST BE REJECTED
    eps = 1e-6
    wrapper_below = CertifiedDoseWrapper(engine=engine, compliance_limit=exact_hi - eps)
    res_below = wrapper_below.certify_action(dose, state)
    assert res_below.status != CertificationStatus.ACCEPTED
    assert res_below.was_intervened is True

    # Case C: Limit epsilon ABOVE reachable upper bound -> MUST BE ACCEPTED
    wrapper_above = CertifiedDoseWrapper(engine=engine, compliance_limit=exact_hi + eps)
    res_above = wrapper_above.certify_action(dose, state)
    assert res_above.status == CertificationStatus.ACCEPTED


# =============================================================================
# 3. NUMERICAL EDGE CASES & ARITHMETIC EXTREMES
# =============================================================================


def test_interval_subnormal_and_extreme_magnitudes() -> None:
    """Interval arithmetic should preserve monotonicity and bounds on extreme magnitudes."""
    subnormal = 1e-300
    int_small = Interval(subnormal, 2 * subnormal)
    assert int_small.lo > 0.0
    assert int_small.width == pytest.approx(subnormal, rel=1e-6)

    # Addition and scaling
    doubled = int_small + int_small
    assert doubled.lo == pytest.approx(2 * subnormal, rel=1e-6)
    assert doubled.hi == pytest.approx(4 * subnormal, rel=1e-6)

    # Very large numbers
    int_large = Interval(1e140, 2e140)
    int_div = int_large / int_large
    assert int_div.lo == pytest.approx(0.5, rel=1e-6)
    assert int_div.hi == pytest.approx(2.0, rel=1e-6)


def test_interval_pow_comprehensive_matrix() -> None:
    """Exhaustively tests Interval.__pow__ across positive, negative, integer, float, and zero powers."""
    # 1. Zero exponent
    assert (Interval(-5.0, 5.0) ** 0) == Interval(1.0, 1.0)
    assert (Interval(0.0, 10.0) ** 0) == Interval(1.0, 1.0)

    # 2. Exponent 1
    assert (Interval(-3.0, 7.0) ** 1) == Interval(-3.0, 7.0)

    # 3. Even positive integer power straddling zero
    p_even = Interval(-4.0, 2.0) ** 2
    assert p_even.lo == 0.0
    assert p_even.hi == 16.0

    # 4. Even positive float power straddling zero
    p_even_float = Interval(-4.0, 2.0) ** 2.0
    assert p_even_float.lo == 0.0
    assert p_even_float.hi == 16.0

    # 5. Odd positive integer power
    p_odd = Interval(-3.0, 2.0) ** 3
    assert p_odd.lo == -27.0
    assert p_odd.hi == 8.0

    # 6. Negative integer power on strictly positive interval
    p_neg_int = Interval(2.0, 4.0) ** -2
    assert p_neg_int.lo == pytest.approx(1.0 / 16.0)
    assert p_neg_int.hi == pytest.approx(1.0 / 4.0)

    # 7. Negative fractional power on strictly positive interval (v0.2.0 fix verification)
    p_neg_frac = Interval(4.0, 9.0) ** -0.5
    assert p_neg_frac.lo == pytest.approx(1.0 / 3.0)
    assert p_neg_frac.hi == pytest.approx(1.0 / 2.0)

    # 8. Fractional power with zero lower bound
    p_sqrt_zero = Interval(0.0, 16.0) ** 0.5
    assert p_sqrt_zero.lo == 0.0
    assert p_sqrt_zero.hi == 4.0

    # 9. Fractional power on negative interval must raise ValueError
    with pytest.raises(ValueError, match="Fractional power not defined for negative"):
        _ = Interval(-4.0, -1.0) ** 0.5

    # 10. Negative power on interval containing zero must raise ZeroDivisionError
    with pytest.raises(ZeroDivisionError, match="unbounded"):
        _ = Interval(-1.0, 2.0) ** -1

    with pytest.raises(ZeroDivisionError, match="unbounded"):
        _ = Interval(0.0, 5.0) ** -0.5


def test_nan_and_inf_handling_and_fail_safe() -> None:
    """Certifier must unconditionally trigger fail-safe fallback when NaN or Inf is encountered."""
    wrapper = CertifiedDoseWrapper(fallback_dose=24.0, compliance_limit=1.0)
    state = {
        "turbidity": Interval(20.0, 25.0),
        "flow_rate": Interval(900.0, 1100.0),
        "ph": Interval(7.1, 7.3),
        "temperature": Interval(16.0, 18.0),
    }

    # NaN proposed dose
    res_nan = wrapper.certify_action(float("nan"), state)
    assert res_nan.status == CertificationStatus.FAILED_SAFE_FALLBACK
    assert res_nan.certified_dose == 24.0

    # Inf proposed dose
    res_inf = wrapper.certify_action(float("inf"), state)
    assert res_inf.status == CertificationStatus.FAILED_SAFE_FALLBACK
    assert res_inf.certified_dose == 24.0

    # Negative proposed dose
    res_neg = wrapper.certify_action(-5.0, state)
    assert res_neg.status == CertificationStatus.FAILED_SAFE_FALLBACK
    assert res_neg.certified_dose == 24.0

    # Interval bound with NaN must be rejected during interval creation
    with pytest.raises(ValueError, match="Interval bounds cannot be NaN"):
        _ = Interval(float("nan"), 10.0)

    with pytest.raises(ValueError, match="Interval bounds cannot be NaN"):
        _ = Interval(1.0, float("nan"))


# =============================================================================
# 4. CORRELATED / NON-INDEPENDENT SENSOR SCENARIOS
# =============================================================================


def test_correlated_sensors_soundness_and_conservatism_analysis() -> None:
    """When inputs are physically correlated (e.g. Q = f(T_in)), interval bounds remain sound.

    Mathematical Basis:
    Standard interval arithmetic assumes an axis-aligned bounding hyper-rectangle:
        B = [T_in_min, T_in_max] x [Q_min, Q_max]
    If physical correlation restricts state to a 1D curve M = {(T_in, Q(T_in))} in B,
    then M is a subset of B.
    By Moore's natural interval inclusion property:
        f(M) is a subset of f(B) is a subset of [y_min, y_max].
    Therefore, the reachable set computed assuming independence is GUARANTEED to
    over-approximate all correlated physical states (strictly sound).
    """
    model = SyntheticProcessModel()
    engine = ReachabilityEngine(model=model, safety_margin=0.0)

    dose = 18.0
    t_min, t_max = 20.0, 35.0

    # Physical correlation: during storm surge, flow rate increases linearly with runoff turbidity:
    # Q(t) = 800.0 + 8.0 * t
    def storm_flow(t: float) -> float:
        return 800.0 + 8.0 * t

    q_min = storm_flow(t_min)  # 960.0
    q_max = storm_flow(t_max)  # 1080.0
    ph_val = 7.3
    temp_val = 16.0

    # 1. Compute reachability set using bounding box (assumes independent intervals)
    box_state = {
        "turbidity": Interval(t_min, t_max),
        "flow_rate": Interval(q_min, q_max),
        "ph": Interval(ph_val, ph_val),
        "temperature": Interval(temp_val, temp_val),
    }
    reachable_box = engine.compute_reachable_set(dose=dose, disturbances=box_state)

    # 2. Sample 1000 points along the true correlated manifold M
    import numpy as np

    turb_samples = np.linspace(t_min, t_max, 1000)
    flow_samples = storm_flow(turb_samples)

    true_effluents = [
        model.evaluate_scalar(
            dose=dose,
            influent_turbidity=float(t),
            flow_rate=float(q),
            ph=ph_val,
            temperature=temp_val,
        )
        for t, q in zip(turb_samples, flow_samples, strict=True)
    ]

    min_true = min(true_effluents)
    max_true = max(true_effluents)

    # Soundness verification: every correlated point must lie inside the box reachable set
    # (accounting for IEEE 754 1-ULP roundoff when safety_margin=0.0)
    assert (
        min_true >= reachable_box.lo - 1e-12
    ), f"Correlated lower bound {min_true} violated box lo {reachable_box.lo}"
    assert (
        max_true <= reachable_box.hi + 1e-12
    ), f"Correlated upper bound {max_true} violated box hi {reachable_box.hi}"

    # With the standard default safety margin (0.02 NTU), strictly max_true < reachable.hi
    reachable_with_margin = ReachabilityEngine(model=model).compute_reachable_set(
        dose=dose, disturbances=box_state
    )
    assert max_true < reachable_with_margin.hi
    assert min_true > reachable_with_margin.lo

    # Conservatism quantification: box bounds are slightly wider than the true 1D manifold
    excess_conservatism = reachable_box.hi - max_true
    assert excess_conservatism >= -1e-12
    # For this system, the excess conservatism from the box approximation is small (<0.05 NTU)
    assert excess_conservatism < 0.05
