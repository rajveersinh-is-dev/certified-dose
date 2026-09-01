"""Tests for formal safety certifier and fail-safe fallback logic."""

from unittest.mock import MagicMock

import pytest

from certified_dose.certifier import (
    CertificationStatus,
    CertifiedDoseWrapper,
)
from certified_dose.controller import HeuristicController, PlantState
from certified_dose.intervals import Interval
from certified_dose.reachability import ReachabilityEngine


@pytest.fixture
def default_disturbances() -> dict[str, Interval]:
    return {
        "turbidity": Interval(20.0, 26.0),
        "flow_rate": Interval(900.0, 1100.0),
        "ph": Interval(7.1, 7.5),
        "temperature": Interval(16.0, 19.0),
    }


def test_certifier_accepts_safe_dose(default_disturbances: dict[str, Interval]) -> None:
    wrapper = CertifiedDoseWrapper(compliance_limit=1.0)

    # 22 mg/L is well within optimal window
    result = wrapper.certify_action(
        proposed_dose=22.0, disturbances=default_disturbances
    )

    assert result.status == CertificationStatus.ACCEPTED
    assert result.certified_dose == 22.0
    assert not result.was_intervened
    assert result.reachable_set.hi <= 1.0


def test_certifier_rejects_and_corrects_underdose(
    default_disturbances: dict[str, Interval],
) -> None:
    wrapper = CertifiedDoseWrapper(compliance_limit=1.0)

    # 6.0 mg/L is an unsafe under-dose
    result = wrapper.certify_action(
        proposed_dose=6.0, disturbances=default_disturbances
    )

    assert result.status == CertificationStatus.REJECTED_CORRECTED
    assert result.was_intervened
    assert result.proposed_dose == 6.0
    assert result.certified_dose > 6.0  # Corrected upward
    assert result.reachable_set.hi <= 1.0  # Corrected dose meets envelope


def test_certifier_rejects_and_corrects_overdose(
    default_disturbances: dict[str, Interval],
) -> None:
    wrapper = CertifiedDoseWrapper(compliance_limit=1.0)

    # 85.0 mg/L is severe overdosing causing restabilization
    result = wrapper.certify_action(
        proposed_dose=85.0, disturbances=default_disturbances
    )

    assert result.status == CertificationStatus.REJECTED_CORRECTED
    assert result.was_intervened
    assert result.certified_dose < 85.0  # Corrected downward to safe operating window
    assert result.reachable_set.hi <= 1.0


def test_certifier_fail_safe_on_nan_and_inf(
    default_disturbances: dict[str, Interval],
) -> None:
    wrapper = CertifiedDoseWrapper(compliance_limit=1.0, fallback_dose=24.0)

    # Test NaN
    res_nan = wrapper.certify_action(
        proposed_dose=float("nan"), disturbances=default_disturbances
    )
    assert res_nan.status == CertificationStatus.FAILED_SAFE_FALLBACK
    assert res_nan.certified_dose == 24.0

    # Test +Inf
    res_inf = wrapper.certify_action(
        proposed_dose=float("inf"), disturbances=default_disturbances
    )
    assert res_inf.status == CertificationStatus.FAILED_SAFE_FALLBACK
    assert res_inf.certified_dose == 24.0

    # Test negative dose
    res_neg = wrapper.certify_action(
        proposed_dose=-5.0, disturbances=default_disturbances
    )
    assert res_neg.status == CertificationStatus.FAILED_SAFE_FALLBACK
    assert res_neg.certified_dose == 24.0


def test_certifier_fail_safe_on_computational_exception(
    default_disturbances: dict[str, Interval],
) -> None:
    """Verifies that any unexpected runtime error in reachability engine triggers safe fallback."""
    mock_engine = MagicMock(spec=ReachabilityEngine)
    mock_engine.compute_reachable_set.side_effect = RuntimeError(
        "Simulated numerical overflow"
    )
    mock_engine.safety_margin = 0.02

    wrapper = CertifiedDoseWrapper(engine=mock_engine, fallback_dose=25.0)

    # Must never raise exception out of safety boundary
    result = wrapper.certify_action(
        proposed_dose=18.0, disturbances=default_disturbances
    )
    assert result.status == CertificationStatus.FAILED_SAFE_FALLBACK
    assert result.certified_dose == 25.0
    assert "Fail-safe activated" in result.reason


def test_wrapped_controller_protocol() -> None:
    wrapper = CertifiedDoseWrapper(compliance_limit=1.0)
    cand_controller = HeuristicController(k_base=4.0)
    wrapped = wrapper.wrap_controller(cand_controller)

    state = PlantState(
        turbidity=25.0,
        flow_rate=1000.0,
        ph=7.2,
        temperature=18.0,
    )

    dose, cert_res = wrapped.step(state)
    assert isinstance(dose, float)
    assert dose > 0.0
    assert cert_res.reachable_set.hi <= 1.0


def test_certifier_bisection_timeout_and_iteration_caps(
    default_disturbances: dict[str, Interval],
) -> None:
    """Verifies that exceeding time budget or zero iteration limit forces fail-safe fallback."""
    # 1. Invalid arguments
    with pytest.raises(ValueError, match="Max computation time must be positive"):
        _ = CertifiedDoseWrapper(max_computation_time_ms=-1.0)

    with pytest.raises(ValueError, match="bisection_max_iter cannot be negative"):
        _ = CertifiedDoseWrapper(bisection_max_iter=-5)

    # 2. Hard timeout cap (e.g. 0.0001 ms budget forces immediate timeout during search)
    wrapper_timeout = CertifiedDoseWrapper(
        fallback_dose=24.0,
        compliance_limit=1.0,
        max_computation_time_ms=0.000001,  # Sub-nanosecond budget
    )
    # Propose unsafe dose (2.0 mg/L) requiring bisection search
    res_timeout = wrapper_timeout.certify_action(2.0, default_disturbances)
    assert res_timeout.status == CertificationStatus.FAILED_SAFE_FALLBACK
    assert res_timeout.certified_dose == 24.0
    assert "budget exceeded" in res_timeout.reason

    # 3. Zero iteration cap
    wrapper_zero_iter = CertifiedDoseWrapper(
        fallback_dose=24.0,
        compliance_limit=1.0,
        bisection_max_iter=0,
    )
    res_zero = wrapper_zero_iter.certify_action(2.0, default_disturbances)
    assert res_zero.status == CertificationStatus.FAILED_SAFE_FALLBACK
    assert res_zero.certified_dose == 24.0
    assert "iteration cap is zero" in res_zero.reason
