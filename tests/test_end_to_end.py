"""End-to-end integration tests for closed-loop reachability certification."""

from certified_dose.certifier import CertifiedDoseWrapper
from certified_dose.controller import (
    AdversarialController,
)
from certified_dose.process_model import SyntheticProcessModel
from certified_dose.reachability import ReachabilityEngine
from certified_dose.simulate import ClosedLoopSimulator, simulate_closed_loop


def test_end_to_end_closed_loop_safety_guarantee() -> None:
    """Runs 150 timesteps with aggressive cost-minimizing controller and storm event.

    Asserts:
    1. Candidate controller deliberately breaches compliance due to aggressive chemical shaving.
    2. Formal safety certifier catches all violations.
    3. Certified plant exhibits ZERO compliance violations throughout the entire run.
    """
    summary = simulate_closed_loop(
        n_steps=150,
        seed=42,
        compliance_limit=1.0,
        uncertainty_pct=0.15,
    )

    assert summary.total_steps == 150
    # Candidate controller alone would have caused violations
    assert (
        summary.candidate_violations > 0
    ), "Test prerequisite: Candidate must trigger violations"

    # Certified controller MUST have exactly 0 violations
    assert (
        summary.certified_violations == 0
    ), f"Safety guarantee breached! Observed {summary.certified_violations} certified violations."

    # All certified true effluent values must be <= 1.0
    for record in summary.records:
        assert (
            record.certified_effluent <= 1.0
        ), f"Step {record.step}: True effluent {record.certified_effluent:.4f} > 1.0 limit!"
        assert not record.certified_violated

    # Verify that interventions occurred
    assert summary.interventions > 0
    assert summary.intervention_rate_pct > 0.0


def test_end_to_end_adversarial_controller_stress_test() -> None:
    """Stress tests the certifier against an adversarial controller proposing extreme actions."""
    model = SyntheticProcessModel()
    certifier = CertifiedDoseWrapper(
        engine=ReachabilityEngine(model=model, safety_margin=0.02),
        compliance_limit=1.0,
        fallback_dose=24.0,
    )
    adversary = AdversarialController(pattern=[0.0, 95.0, 1.0, 80.0, 3.0])

    simulator = ClosedLoopSimulator(
        model=model,
        certifier=certifier,
        candidate_controller=adversary,
    )

    summary = simulator.run(n_steps=50, seed=99)

    # 100% of adversarial doses should have breached compliance without certifier
    assert summary.candidate_violations > 30

    # With certifier: ZERO violations
    assert summary.certified_violations == 0
    assert all(r.certified_effluent <= 1.0 for r in summary.records)


def test_simulation_summary_serialization() -> None:
    summary = simulate_closed_loop(n_steps=10, seed=1)
    records = summary.to_records_dict()
    assert len(records) == 10
    assert isinstance(records[0], dict)
    assert "certified_dose" in records[0]
