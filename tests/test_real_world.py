"""Unit tests for real-world operational data ingestion, validation, and benchmarking.

Ensures that all parsing, normalization, instrument tolerance derivations,
and pipeline evaluations execute offline with zero live network calls.
"""

from __future__ import annotations

import io

import pytest

from certified_dose.real_world import (
    InstrumentUncertaintySpecs,
    RealWorldDataset,
    RealWorldRecord,
    derive_disturbance_intervals,
    evaluate_dataset_on_pipeline,
)

MOCK_CSV = """timestamp,turbidity_ntu,flow_cfs,ph,temperature_c
2026-08-02T12:45:00.000-04:00,13.2,504.0,8.4,23.9
2026-08-02T13:00:00.000-04:00,14.5,504.0,8.5,24.1
2026-08-02T13:15:00.000-04:00,25.0,1200.0,7.8,22.5
2026-08-02T13:30:00.000-04:00,85.0,4500.0,8.9,25.0
2026-08-02T13:45:00.000-04:00,5.0,300.0,7.2,18.0
"""


def test_real_world_record_validation() -> None:
    """Test physical range validation on operational telemetry records."""
    valid = RealWorldRecord(
        timestamp="2026-08-02T12:45:00Z",
        turbidity_ntu=15.0,
        flow_cfs=500.0,
        ph=7.5,
        temperature_c=22.0,
        site_id="04193500",
    )
    valid.validate()

    with pytest.raises(ValueError, match="Invalid turbidity"):
        RealWorldRecord("t", -1.0, 500.0, 7.5, 22.0).validate()

    with pytest.raises(ValueError, match="Invalid pH"):
        RealWorldRecord("t", 15.0, 500.0, 15.0, 22.0).validate()

    with pytest.raises(ValueError, match="Invalid temperature"):
        RealWorldRecord("t", 15.0, 500.0, 7.5, -20.0).validate()

    with pytest.raises(ValueError, match="Invalid flow"):
        RealWorldRecord("t", 15.0, -10.0, 7.5, 22.0).validate()


def test_derive_disturbance_intervals_instrument_specs() -> None:
    """Test derivation of bounded uncertainty intervals from sensor precision."""
    rec = RealWorldRecord(
        timestamp="2026-08-02T12:45:00Z",
        turbidity_ntu=20.0,
        flow_cfs=1000.0,
        ph=7.4,
        temperature_c=20.0,
    )
    specs = InstrumentUncertaintySpecs(
        turbidity_rel_error=0.10,
        turbidity_min_abs_error=0.50,
        ph_abs_error=0.15,
        temp_abs_error=0.50,
        flow_rel_error=0.05,
    )
    dists = derive_disturbance_intervals(rec, specs=specs, nominal_flow_cfs=1000.0)

    # Turbidity: 20 +/- (0.10 * 20 = 2.0) -> [18.0, 22.0]
    assert dists["turbidity"].lo == pytest.approx(18.0)
    assert dists["turbidity"].hi == pytest.approx(22.0)

    # pH: 7.4 +/- 0.15 -> [7.25, 7.55]
    assert dists["ph"].lo == pytest.approx(7.25)
    assert dists["ph"].hi == pytest.approx(7.55)

    # Temperature: 20.0 +/- 0.5 -> [19.5, 20.5]
    assert dists["temperature"].lo == pytest.approx(19.5)
    assert dists["temperature"].hi == pytest.approx(20.5)

    # Flow: 1000 +/- 5% relative to 1000 -> [0.95, 1.05]
    assert dists["flow_rate"].lo == pytest.approx(0.95)
    assert dists["flow_rate"].hi == pytest.approx(1.05)


def test_derive_disturbance_intervals_small_turbidity_floor() -> None:
    """Ensure minimum absolute error floor applies when turbidity is very low."""
    rec = RealWorldRecord(
        timestamp="2026-08-02T12:45:00Z",
        turbidity_ntu=1.0,
        flow_cfs=500.0,
        ph=7.0,
        temperature_c=15.0,
    )
    specs = InstrumentUncertaintySpecs(
        turbidity_rel_error=0.10,  # 0.10 * 1.0 = 0.10
        turbidity_min_abs_error=0.50,  # Floor is 0.50
    )
    dists = derive_disturbance_intervals(rec, specs=specs)
    assert dists["turbidity"].lo == pytest.approx(0.50)
    assert dists["turbidity"].hi == pytest.approx(1.50)


def test_real_world_dataset_from_csv() -> None:
    """Test loading and summary statistics on CSV dataset."""
    dataset = RealWorldDataset.from_csv(
        io.StringIO(MOCK_CSV), site_id="test_site", site_name="Test Station"
    )
    assert dataset.record_count == 5
    assert dataset.site_id == "test_site"

    stats = dataset.summary_statistics()
    assert stats["turbidity_ntu"]["min"] == pytest.approx(5.0)
    assert stats["turbidity_ntu"]["max"] == pytest.approx(85.0)
    assert stats["ph"]["min"] == pytest.approx(7.2)
    assert stats["ph"]["max"] == pytest.approx(8.9)


def test_evaluate_dataset_on_pipeline() -> None:
    """Test end-to-end evaluation pipeline on mock real-world dataset."""
    dataset = RealWorldDataset.from_csv(
        io.StringIO(MOCK_CSV), site_id="04193500", site_name="Maumee River"
    )
    report = evaluate_dataset_on_pipeline(dataset, compliance_limit=1.0)

    assert report["total_records_evaluated"] == 5
    assert report["soundness_checks"]["guarantee_held"] is True
    assert report["heuristic_controller"]["certified_violations"] == 0
    assert report["aggressive_controller"]["certified_violations"] == 0

    heur = report["heuristic_controller"]
    assert (
        heur["accepted_count"]
        + heur["corrected_count"]
        + heur["outside_validity_count"]
        + heur["fallback_count"]
        == 5
    )
    assert heur["outside_validity_count"] == 3
