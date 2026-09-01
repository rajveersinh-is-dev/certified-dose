"""Tests for pH validity regime enforcement and out-of-range certification rejection."""

import pytest

from certified_dose.certifier import (
    CertificationStatus,
    CertifiedDoseWrapper,
)
from certified_dose.intervals import Interval
from certified_dose.process_model import (
    PhValidityStatus,
    SyntheticProcessModel,
)


class TestProcessModelPhValidity:
    """Direct tests of SyntheticProcessModel.check_ph_validity()."""

    @pytest.fixture
    def model(self) -> SyntheticProcessModel:
        return SyntheticProcessModel()

    @pytest.mark.parametrize(
        "ph_val",
        [5.0, 6.0, 7.0, 7.2, 7.5, 8.0],
    )
    def test_scalar_valid_regime(
        self, model: SyntheticProcessModel, ph_val: float
    ) -> None:
        """Scalar pH in [5.0, 8.0] must report VALID."""
        assert model.check_ph_validity(ph_val) == PhValidityStatus.VALID

    @pytest.mark.parametrize(
        "ph_val",
        [8.05, 8.2, 8.3, 8.49, 8.5],
    )
    def test_scalar_warning_regime(
        self, model: SyntheticProcessModel, ph_val: float
    ) -> None:
        """Scalar pH in (8.0, 8.5] must report WARNING (transitional)."""
        assert model.check_ph_validity(ph_val) == PhValidityStatus.WARNING

    @pytest.mark.parametrize(
        "ph_val",
        [4.99, 4.0, 3.0, 8.51, 8.7, 9.0, 9.3, 10.5],
    )
    def test_scalar_out_of_range_regime(
        self, model: SyntheticProcessModel, ph_val: float
    ) -> None:
        """Scalar pH < 5.0 or > 8.5 must report OUT_OF_RANGE."""
        assert model.check_ph_validity(ph_val) == PhValidityStatus.OUT_OF_RANGE

    def test_interval_fully_valid(self, model: SyntheticProcessModel) -> None:
        """Interval within [5.0, 8.0] must be VALID."""
        assert model.check_ph_validity(Interval(6.8, 7.6)) == PhValidityStatus.VALID
        assert model.check_ph_validity(Interval(5.0, 8.0)) == PhValidityStatus.VALID

    def test_interval_transitional_warning(self, model: SyntheticProcessModel) -> None:
        """Interval entering warning zone but not out-of-range must be WARNING."""
        assert model.check_ph_validity(Interval(7.5, 8.3)) == PhValidityStatus.WARNING
        assert model.check_ph_validity(Interval(8.1, 8.5)) == PhValidityStatus.WARNING

    def test_interval_out_of_range_high(self, model: SyntheticProcessModel) -> None:
        """Interval with upper bound > 8.5 must be OUT_OF_RANGE."""
        assert (
            model.check_ph_validity(Interval(8.0, 8.6)) == PhValidityStatus.OUT_OF_RANGE
        )
        assert (
            model.check_ph_validity(Interval(9.1, 9.5)) == PhValidityStatus.OUT_OF_RANGE
        )

    def test_interval_out_of_range_low(self, model: SyntheticProcessModel) -> None:
        """Interval with lower bound < 5.0 must be OUT_OF_RANGE."""
        assert (
            model.check_ph_validity(Interval(4.8, 6.0)) == PhValidityStatus.OUT_OF_RANGE
        )
        assert (
            model.check_ph_validity(Interval(3.5, 4.5)) == PhValidityStatus.OUT_OF_RANGE
        )


class TestCertifierPhValidityEnforcement:
    """Integration tests verifying CertifiedDoseWrapper behavior at pH boundaries."""

    @pytest.fixture
    def wrapper(self) -> CertifiedDoseWrapper:
        return CertifiedDoseWrapper(compliance_limit=1.0, fallback_dose=15.0)

    @pytest.fixture
    def standard_disturbances(self) -> dict[str, Interval]:
        return {
            "turbidity": Interval(20.0, 26.0),
            "flow_rate": Interval(900.0, 1100.0),
            "ph": Interval(7.0, 7.4),
            "temperature": Interval(15.0, 18.0),
        }

    def test_certify_action_valid_ph_normal(
        self, wrapper: CertifiedDoseWrapper, standard_disturbances: dict[str, Interval]
    ) -> None:
        """Within valid pH window, certification operates normally."""
        result = wrapper.certify_action(22.0, standard_disturbances)
        assert result.process_model_valid is True
        assert result.model_validity_reason == ""
        assert result.status in (
            CertificationStatus.ACCEPTED,
            CertificationStatus.REJECTED_CORRECTED,
        )

    def test_certify_action_high_ph_refusal(
        self, wrapper: CertifiedDoseWrapper, standard_disturbances: dict[str, Interval]
    ) -> None:
        """At high pH (e.g. Maumee River summer bloom pH ~9.3), certifier refuses certification."""
        high_ph_dist = dict(standard_disturbances)
        high_ph_dist["ph"] = Interval(9.0, 9.45)

        result = wrapper.certify_action(20.0, high_ph_dist)

        assert result.status == CertificationStatus.OUTSIDE_MODEL_VALIDITY
        assert result.process_model_valid is False
        assert result.certified_dose == wrapper.fallback_dose
        assert "aluminate" in result.model_validity_reason.lower()
        assert (
            "5.0, 8.0" in result.model_validity_reason
            or "8.5" in result.model_validity_reason
        )
        assert result.candidate_reachable_set is None

    def test_certify_action_low_ph_refusal(
        self, wrapper: CertifiedDoseWrapper, standard_disturbances: dict[str, Interval]
    ) -> None:
        """At low pH (< 5.0), certifier refuses single-chemical alum certification."""
        low_ph_dist = dict(standard_disturbances)
        low_ph_dist["ph"] = Interval(4.0, 4.8)

        result = wrapper.certify_action(20.0, low_ph_dist)

        assert result.status == CertificationStatus.OUTSIDE_MODEL_VALIDITY
        assert result.process_model_valid is False
        assert result.certified_dose == wrapper.fallback_dose

    def test_exact_boundary_conditions(
        self, wrapper: CertifiedDoseWrapper, standard_disturbances: dict[str, Interval]
    ) -> None:
        """Tests precise boundary behavior around 8.5."""
        # Just at/below 8.5: warning regime in model, certifier still evaluates
        d_warn = dict(standard_disturbances)
        d_warn["ph"] = Interval(7.5, 8.5)
        res_warn = wrapper.certify_action(25.0, d_warn)
        assert res_warn.process_model_valid is True
        assert res_warn.status != CertificationStatus.OUTSIDE_MODEL_VALIDITY

        # Just above 8.5: out-of-range boundary exceeded
        d_oob = dict(standard_disturbances)
        d_oob["ph"] = Interval(7.5, 8.51)
        res_oob = wrapper.certify_action(25.0, d_oob)
        assert res_oob.process_model_valid is False
        assert res_oob.status == CertificationStatus.OUTSIDE_MODEL_VALIDITY

    def test_explain_output_for_outside_model_validity(
        self, wrapper: CertifiedDoseWrapper, standard_disturbances: dict[str, Interval]
    ) -> None:
        """Explanation report contains actionable chemical guidance when OUTSIDE_MODEL_VALIDITY."""
        high_ph_dist = dict(standard_disturbances)
        high_ph_dist["ph"] = Interval(8.8, 9.2)

        result = wrapper.certify_action(15.0, high_ph_dist)
        assert result.status == CertificationStatus.OUTSIDE_MODEL_VALIDITY

        exp = result.explain()
        assert exp.status == CertificationStatus.OUTSIDE_MODEL_VALIDITY
        assert "validity" in exp.binding_constraint.lower()
        assert "acid pre-treatment" in exp.operator_guidance.lower()
        assert "aluminate" in exp.operator_guidance.lower()
