from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from certified_dose.certifier.status import CertificationStatus
from certified_dose.intervals import Interval
from certified_dose.reachability import ReachabilityEngine, ReachableSet


@dataclass(frozen=True)
class SensitivityAttribution:
    """Attribution of output reachability uncertainty to an individual disturbance variable."""

    variable: str
    relative_contribution_pct: float
    partial_output_width: float
    input_interval: Interval | None = None


@dataclass(frozen=True)
class ExplanationReport:
    """Structured, operator-facing explanation of a certification decision."""

    status: CertificationStatus
    proposed_dose: float
    certified_dose: float
    compliance_limit: float
    worst_case_candidate: float | None
    worst_case_certified: float
    safety_margin: float
    violates_limit: bool
    summary: str
    binding_constraint: str
    top_contributor: str
    top_contributor_pct: float
    sensitivities: list[SensitivityAttribution]
    operator_guidance: str

    def to_dict(self) -> dict[str, Any]:
        """Converts explanation report to dictionary format."""
        return {
            "status": self.status.value,
            "proposed_dose": self.proposed_dose,
            "certified_dose": self.certified_dose,
            "compliance_limit": self.compliance_limit,
            "worst_case_candidate": self.worst_case_candidate,
            "worst_case_certified": self.worst_case_certified,
            "safety_margin": self.safety_margin,
            "violates_limit": self.violates_limit,
            "summary": self.summary,
            "binding_constraint": self.binding_constraint,
            "top_contributor": self.top_contributor,
            "top_contributor_pct": self.top_contributor_pct,
            "sensitivities": [
                {
                    "variable": s.variable,
                    "relative_contribution_pct": s.relative_contribution_pct,
                    "partial_output_width": s.partial_output_width,
                    "input_interval": (
                        [s.input_interval.lo, s.input_interval.hi]
                        if s.input_interval
                        else None
                    ),
                }
                for s in self.sensitivities
            ],
            "operator_guidance": self.operator_guidance,
        }

    def format_text(self) -> str:
        """Renders formatted multi-line text report suitable for console output."""
        lines = [
            f"Status: {self.status.value}",
            f"Binding Constraint: {self.binding_constraint}",
            f"Safety Margin: {self.safety_margin:+.3f} (limit = {self.compliance_limit:.2f})",
        ]
        if self.sensitivities:
            lines.append("Uncertainty Attribution:")
            for s in self.sensitivities:
                inp_desc = (
                    f" [{s.input_interval.lo:.2f}, {s.input_interval.hi:.2f}]"
                    if s.input_interval
                    else ""
                )
                lines.append(
                    f"  - {s.variable:12s}: {s.relative_contribution_pct:5.1f}% "
                    f"(output spread = {s.partial_output_width:.3f}){inp_desc}"
                )
        lines.append(f"Guidance: {self.operator_guidance}")
        return "\n".join(lines)

    def __str__(self) -> str:
        """Str.

        Returns:
            The computed result

        """
        return self.format_text()


@dataclass(frozen=True)
class CertificationResult:
    """Detailed record of a dosing certification decision.

    Attributes:
        certified_dose: The final safe dose to apply (mg/L).
        status: Certification outcome (ACCEPTED, REJECTED_CORRECTED,
            FAILED_SAFE_FALLBACK, or OUTSIDE_MODEL_VALIDITY).
        proposed_dose: The original candidate dose proposed by the controller.
        reachable_set: Guaranteed output reachable interval [lo, hi] for the certified dose.
        candidate_reachable_set: Guaranteed output interval for the proposed dose (if computed).
        compliance_limit: The regulatory compliance limit enforced (NTU).
        reason: Human-readable explanation of the certification decision.
        computation_time_ms: Wall-clock computation duration in milliseconds.
        disturbances: Normalized disturbance intervals evaluated.
        engine: Reference to the reachability engine used.
        process_model_valid: False when the pH disturbance interval falls outside the
            physically valid range for the single-chemical alum coagulation model.
            When False, the certification is OUTSIDE_MODEL_VALIDITY and no reachability
            claim can be made. Distinct from FAILED_SAFE_FALLBACK (computational error).
        model_validity_reason: Human-readable explanation of why the model is or is not
            valid at the evaluated operating point.
    """

    certified_dose: float
    status: CertificationStatus
    proposed_dose: float
    reachable_set: ReachableSet
    candidate_reachable_set: ReachableSet | None
    compliance_limit: float
    reason: str
    computation_time_ms: float
    disturbances: Mapping[str, Interval] | None = None
    engine: ReachabilityEngine | None = None
    process_model_valid: bool = True
    model_validity_reason: str = ""

    @property
    def was_intervened(self) -> bool:
        """Returns True if the safety wrapper modified or rejected the proposed dose."""
        return self.status != CertificationStatus.ACCEPTED

    def explain(
        self,
        engine: ReachabilityEngine | None = None,
        disturbances: Mapping[str, Interval] | None = None,
    ) -> ExplanationReport:
        """Generates an operator-facing explainability report detailing constraints and sensitivity.

        Breaks down:
        1. Which constraint was binding or would have been violated.
        2. Sensitivity attribution: which disturbance variable drove output interval uncertainty.
        3. Effective safety margin against the compliance envelope.
        4. Concrete operator guidance on how to act.
        """
        eng = engine or self.engine
        dist = disturbances or self.disturbances

        worst_cand = (
            self.candidate_reachable_set.hi if self.candidate_reachable_set else None
        )
        worst_cert = self.reachable_set.hi
        violates = worst_cand is not None and worst_cand > self.compliance_limit
        margin = self.compliance_limit - worst_cert

        # Binding constraint statement
        if violates and worst_cand is not None:
            binding = (
                f"Effluent turbidity limit = {self.compliance_limit:.2f} NTU. "
                f"Proposed dose worst-case: {worst_cand:.3f} NTU (+{worst_cand - self.compliance_limit:.3f} NTU violation)."
            )
        else:
            binding = (
                f"Effluent turbidity limit = {self.compliance_limit:.2f} NTU. "
                f"Worst-case certified effluent: {worst_cert:.3f} NTU ({margin:.3f} NTU below limit)."
            )

        # Sensitivity attribution
        sensitivities: list[SensitivityAttribution] = []
        top_var = "none"
        top_pct = 0.0

        if eng is not None and dist is not None:
            target_dose = (
                self.proposed_dose
                if self.candidate_reachable_set
                else self.certified_dose
            )
            raw_sens = eng.compute_sensitivity_attribution(target_dose, dist)
            for var_name, (pct, width) in sorted(
                raw_sens.items(), key=lambda x: x[1][0], reverse=True
            ):
                interval_val = dist.get(var_name)
                sensitivities.append(
                    SensitivityAttribution(
                        variable=var_name,
                        relative_contribution_pct=pct,
                        partial_output_width=width,
                        input_interval=(
                            interval_val if isinstance(interval_val, Interval) else None
                        ),
                    )
                )
            if sensitivities:
                top_var = sensitivities[0].variable
                top_pct = sensitivities[0].relative_contribution_pct

        # For OUTSIDE_MODEL_VALIDITY, override binding constraint to explain the chemistry
        if self.status == CertificationStatus.OUTSIDE_MODEL_VALIDITY:
            binding = (
                f"Process model validity failure -- single-chemical alum coagulation model "
                f"requires pH in [5.0, 8.0]. {self.model_validity_reason} "
                f"The model cannot make a trustworthy claim at this pH."
            )

        # Operator guidance
        if self.status == CertificationStatus.ACCEPTED:
            guidance = (
                f"Candidate dose {self.proposed_dose:.2f} mg/L is verified safe. "
                f"Operating with {margin:.3f} NTU headroom below regulatory limit."
            )
        elif self.status == CertificationStatus.REJECTED_CORRECTED:
            if top_var != "none" and top_pct > 30.0:
                guidance = (
                    f"Candidate dose rejected. {top_var.replace('_', ' ').capitalize()} uncertainty "
                    f"accounts for {top_pct:.1f}% of output spread. Narrowing {top_var} sensor "
                    f"uncertainty via calibration would permit a dose closer to {self.proposed_dose:.2f} mg/L."
                )
            else:
                guidance = f"Candidate dose rejected. Corrected to certified safe setpoint {self.certified_dose:.2f} mg/L."
        elif self.status == CertificationStatus.OUTSIDE_MODEL_VALIDITY:
            guidance = (
                f"PROCESS MODEL VALIDITY EXCEEDED -- No certification possible. "
                f"{self.model_validity_reason} "
                f"At this pH, aluminum hydrolyzes into soluble aluminate Al(OH)4- rather than "
                f"precipitating as Al(OH)3. Increasing the coagulant dose will worsen dissolved "
                f"aluminum breakthrough, not improve turbidity removal. "
                f"Required operator action: acid pre-treatment (H2SO4 or CO2 injection) or "
                f"raw water blending to lower pH back into the alum coagulation window [5.0, 8.0] "
                f"before relying on coagulant dosing. The fallback dose {self.certified_dose:.2f} mg/L "
                f"is applied conservatively but is NOT a validated treatment response at this pH."
            )
        else:  # FAILED_SAFE_FALLBACK
            guidance = (
                f"Emergency fail-safe activated ({self.certified_dose:.2f} mg/L). "
                f"Investigate process model validity, communication timeout, or extreme disturbance surge."
            )

        return ExplanationReport(
            status=self.status,
            proposed_dose=self.proposed_dose,
            certified_dose=self.certified_dose,
            compliance_limit=self.compliance_limit,
            worst_case_candidate=worst_cand,
            worst_case_certified=worst_cert,
            safety_margin=margin,
            violates_limit=violates,
            summary=self.reason,
            binding_constraint=binding,
            top_contributor=top_var,
            top_contributor_pct=top_pct,
            sensitivities=sensitivities,
            operator_guidance=guidance,
        )
