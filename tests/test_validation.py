"""Tests for empirical literature validation module."""

from certified_dose.validation import (
    EmpiricalDataset,
    ModelValidationReport,
    validate_synthetic_model,
)


def test_validate_synthetic_model_metrics() -> None:
    report = validate_synthetic_model()

    assert isinstance(report, ModelValidationReport)
    assert report.n_points == 12
    # Empirical jar-testing fit quality
    assert report.r2_score > 0.99
    assert report.rmse_ntu < 0.10
    assert report.mae_ntu < 0.05
    assert report.compliance_zone_rmse_ntu < 0.05

    # Check serialization
    d = report.to_dict()
    assert "r2_score" in d
    assert len(d["comparisons"]) == 12


def test_validation_custom_dataset() -> None:
    custom_data = EmpiricalDataset(
        doses=(0.0, 20.0, 40.0),
        effluents_ntu=(28.5, 0.6, 0.55),
    )
    report = validate_synthetic_model(dataset=custom_data)
    assert report.n_points == 3
    assert report.rmse_ntu < 0.05


def test_validate_all_datasets() -> None:
    from certified_dose.validation import BENCHMARK_DATASETS, validate_all_datasets

    reports = validate_all_datasets()
    assert len(reports) == 2
    assert "edwards_1997" in reports
    assert "van_benschoten_1990" in reports

    edwards_rep = reports["edwards_1997"]
    assert edwards_rep.r2_score > 0.999
    assert edwards_rep.compliance_zone_rmse_ntu < 0.02

    vb_rep = reports["van_benschoten_1990"]
    assert vb_rep.r2_score > 0.99
    assert vb_rep.compliance_zone_rmse_ntu < 0.10
    assert vb_rep.n_points == len(BENCHMARK_DATASETS["van_benschoten_1990"].doses)
