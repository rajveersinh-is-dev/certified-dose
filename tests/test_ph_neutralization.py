"""Tests for CSTR pH neutralization process model and generalized reachability."""

import pytest

from certified_dose.certifier import CertificationStatus, CertifiedDoseWrapper
from certified_dose.intervals import Interval
from certified_dose.reachability import ReachabilityEngine
from examples.ph_neutralization import PHModelParameters, PHNeutralizationModel


def test_ph_neutralization_scalar_monotonicity() -> None:
    model = PHNeutralizationModel()

    base_disturbances = {
        "influent_ph": 10.2,
        "flow_rate": 100.0,
        "buffer_capacity": 0.0005,
    }

    # 1. Monotonicity with respect to acid dose: more acid = lower pH
    ph_low_dose = model.evaluate_scalar(100.0, base_disturbances)
    ph_high_dose = model.evaluate_scalar(300.0, base_disturbances)
    assert ph_high_dose < ph_low_dose

    # 2. Monotonicity with respect to influent pH: higher raw pH = higher effluent pH
    ph_low_raw = model.evaluate_scalar(
        150.0,
        {"influent_ph": 9.5, "flow_rate": 100.0, "buffer_capacity": 0.0005},
    )
    ph_high_raw = model.evaluate_scalar(
        150.0,
        {"influent_ph": 10.5, "flow_rate": 100.0, "buffer_capacity": 0.0005},
    )
    assert ph_high_raw > ph_low_raw

    # 3. Monotonicity with respect to flow rate: more alkaline flow = higher effluent pH
    ph_low_q = model.evaluate_scalar(
        150.0,
        {"influent_ph": 10.2, "flow_rate": 80.0, "buffer_capacity": 0.0005},
    )
    ph_high_q = model.evaluate_scalar(
        150.0,
        {"influent_ph": 10.2, "flow_rate": 120.0, "buffer_capacity": 0.0005},
    )
    assert ph_high_q > ph_low_q


def test_ph_neutralization_invalid_inputs() -> None:
    model = PHNeutralizationModel()
    valid_dist = {
        "influent_ph": 10.0,
        "flow_rate": 100.0,
        "buffer_capacity": 0.0005,
    }

    with pytest.raises(ValueError, match="Acid dose cannot be negative"):
        model.evaluate_scalar(-1.0, valid_dist)

    with pytest.raises(ValueError, match="out of range"):
        model.evaluate_scalar(
            50.0,
            {"influent_ph": 15.0, "flow_rate": 100.0, "buffer_capacity": 0.0005},
        )

    with pytest.raises(ValueError, match="Flow rate must be positive"):
        model.evaluate_scalar(
            50.0,
            {"influent_ph": 10.0, "flow_rate": -50.0, "buffer_capacity": 0.0005},
        )

    with pytest.raises(ValueError, match="Buffer capacity cannot be negative"):
        model.evaluate_scalar(
            50.0,
            {"influent_ph": 10.0, "flow_rate": 100.0, "buffer_capacity": -0.01},
        )


def test_ph_neutralization_reachability_fuzz_verification() -> None:
    model = PHNeutralizationModel()
    engine = ReachabilityEngine(model=model, safety_margin=0.03)

    disturbances = {
        "influent_ph": Interval(9.8, 10.4),
        "flow_rate": Interval(85.0, 115.0),
        "buffer_capacity": Interval(0.0003, 0.0007),
    }

    for test_dose in [0.0, 100.0, 250.0, 500.0]:
        res = engine.verify_against_monte_carlo(
            dose=test_dose,
            disturbances=disturbances,
            n_samples=1000,
            seed=42,
        )
        assert res["is_conservative"] is True
        assert res["margin_hi"] >= 0.0
        assert res["margin_lo"] >= 0.0


def test_ph_neutralization_certifier_wrapper() -> None:
    model = PHNeutralizationModel(PHModelParameters(c_acid_mol_per_l=1.0))
    engine = ReachabilityEngine(model=model, safety_margin=0.03)

    wrapper = CertifiedDoseWrapper(
        engine=engine,
        compliance_limit=8.50,
        dose_search_bounds=(0.0, 1000.0),
        fallback_dose=300.0,
    )

    disturbances = {
        "influent_ph": Interval(9.8, 10.4),
        "flow_rate": Interval(85.0, 115.0),
        "buffer_capacity": Interval(0.0003, 0.0007),
    }

    # 1. Zero dose is alkaline breach -> rejected and corrected
    res_zero = wrapper.certify_action(0.0, disturbances)
    assert res_zero.status == CertificationStatus.REJECTED_CORRECTED
    assert res_zero.certified_dose > 0.0

    # 2. Sufficient dose (300 mL/min) is safe -> accepted
    res_safe = wrapper.certify_action(300.0, disturbances)
    assert res_safe.status == CertificationStatus.ACCEPTED
    assert res_safe.certified_dose == 300.0
