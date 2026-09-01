"""Formal reachability certifier and safety wrapper.

Enforces worst-case regulatory compliance guarantees over proposed dosing actions.
If a proposed dose cannot be formally proven to keep the output reachable set
within the regulatory envelope, the certifier either corrects the dose via
bounded bisection search or falls back to a guaranteed conservative default.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from certified_dose.controller import BaseController, PlantState
from certified_dose.intervals import Interval
from certified_dose.process_model import PhValidityStatus, SyntheticProcessModel
from certified_dose.reachability import ReachabilityEngine, ReachableSet

logger = logging.getLogger("certified_dose.certifier")


class CertificationStatus(StrEnum):
    """Outcome status of the formal certification check.

    ACCEPTED: Proposed dose was verified safe within the compliance envelope.

    REJECTED_CORRECTED: Proposed dose violated the compliance envelope; a safe
        replacement dose was found via bisection search.

    FAILED_SAFE_FALLBACK: Computation failed or timed out; the conservative
        fallback dose was applied as a fail-safe.

    OUTSIDE_MODEL_VALIDITY: The pH disturbance interval lies outside the
        valid operating range for the single-chemical alum coagulation model.
        The model cannot make a trustworthy safety claim at all -- not that
        there is no safe dose, but that the model's assumptions about aluminum
        speciation are violated and any certification would be meaningless.
        This is distinct from FAILED_SAFE_FALLBACK (computational failure)
        and REJECTED_CORRECTED (correctable dose problem). The correct
        operator response is acid pre-treatment or pH adjustment to re-enter
        the alum coagulation window, NOT increasing coagulant dose.
    """

    ACCEPTED = "ACCEPTED"
    REJECTED_CORRECTED = "REJECTED_CORRECTED"
    FAILED_SAFE_FALLBACK = "FAILED_SAFE_FALLBACK"
    OUTSIDE_MODEL_VALIDITY = "OUTSIDE_MODEL_VALIDITY"


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


class CertifiedDoseWrapper:
    """Formal safety wrapper that wraps any candidate controller.

    Guarantees that applied dosing actions keep the process output within the
    compliance envelope for all bounded input uncertainties, or unconditionally
    reverts to a conservative fail-safe dose.
    """

    def __init__(
        self,
        engine: ReachabilityEngine | None = None,
        compliance_limit: float = 1.0,
        fallback_dose: float = 24.0,
        enable_bisection: bool = True,
        dose_search_bounds: tuple[float, float] = (5.0, 50.0),
        bisection_max_iter: int = 25,
        max_computation_time_ms: float = 50.0,
        default_uncertainty: dict[str, float] | None = None,
    ) -> None:
        """Initializes the certified dosing wrapper.

        Args:
            engine: ReachabilityEngine instance. Defaults to default engine.
            compliance_limit: Regulatory ceiling for effluent turbidity (NTU).
            fallback_dose: Default conservative dose applied on failure or unresolvable surge.
            enable_bisection: If True, search for a valid safe dose when candidate is rejected.
            dose_search_bounds: (min_dose, max_dose) search range for bisection.
            bisection_max_iter: Strict upper bound on bisection iterations to prevent hangs.
            max_computation_time_ms: Hard wall-clock latency cap for bisection search (ms).
            default_uncertainty: Relative fractional sensor uncertainty (+/- fraction).
                Defaults to 15% turbidity, 10% flow, 0.3 pH, 2.0 C temp.
        """
        if compliance_limit <= 0:
            raise ValueError(f"Compliance limit must be positive: {compliance_limit}")
        if fallback_dose < 0:
            raise ValueError(f"Fallback dose cannot be negative: {fallback_dose}")
        if dose_search_bounds[0] > dose_search_bounds[1]:
            raise ValueError("Invalid dose search bounds: min > max")
        if bisection_max_iter < 0:
            raise ValueError(
                f"bisection_max_iter cannot be negative: {bisection_max_iter}"
            )
        if max_computation_time_ms <= 0:
            raise ValueError(
                f"Max computation time must be positive: {max_computation_time_ms}"
            )

        self.engine: ReachabilityEngine = engine or ReachabilityEngine()
        self.compliance_limit: float = float(compliance_limit)
        self.fallback_dose: float = float(fallback_dose)
        self.enable_bisection: bool = enable_bisection
        self.dose_search_bounds: tuple[float, float] = dose_search_bounds
        self.bisection_max_iter: int = bisection_max_iter
        self.max_computation_time_ms: float = float(max_computation_time_ms)

        # Default relative uncertainty margins
        self.default_uncertainty: dict[str, float] = default_uncertainty or {
            "turbidity_pct": 0.15,  # +/- 15%
            "flow_rate_pct": 0.10,  # +/- 10%
            "ph_delta": 0.30,  # +/- 0.3 pH units
            "temp_delta": 2.0,  # +/- 2.0 deg C
        }

    def build_disturbance_intervals(
        self, state: PlantState, custom_uncertainty: dict[str, float] | None = None
    ) -> dict[str, Interval]:
        """Constructs conservative disturbance intervals around measured state.

        Args:
            state: Point sensor measurements.
            custom_uncertainty: Optional overrides for uncertainty parameters.

        Returns:
            Dictionary of Interval objects for each disturbance variable.
        """
        u = {**self.default_uncertainty, **(custom_uncertainty or {})}

        turb_delta = state.turbidity * u.get("turbidity_pct", 0.15)
        flow_delta = state.flow_rate * u.get("flow_rate_pct", 0.10)
        ph_delta = u.get("ph_delta", 0.30)
        temp_delta = u.get("temp_delta", 2.0)

        return {
            "turbidity": Interval(
                max(0.1, state.turbidity - turb_delta), state.turbidity + turb_delta
            ),
            "flow_rate": Interval(
                max(10.0, state.flow_rate - flow_delta), state.flow_rate + flow_delta
            ),
            "ph": Interval(
                max(4.0, state.ph - ph_delta), min(10.0, state.ph + ph_delta)
            ),
            "temperature": Interval(
                max(1.0, state.temperature - temp_delta), state.temperature + temp_delta
            ),
        }

    def certify_action(
        self,
        proposed_dose: float,
        disturbances: Mapping[str, Interval],
    ) -> CertificationResult:
        """Formally verifies or corrects a candidate dosing action.

        Guarantees fail-safe behavior: any numerical failure, unhandled exception,
        or unbounded result immediately defaults to fallback_dose.

        Args:
            proposed_dose: Candidate dose proposed by an unverified controller.
            disturbances: Disturbance uncertainty intervals.

        Returns:
            CertificationResult with certified dose, safety proof, and reasoning.
        """
        start_time = time.perf_counter()
        candidate_reachable: ReachableSet | None = None

        try:
            # 1. Sanity check proposed dose
            if (
                math.isnan(proposed_dose)
                or math.isinf(proposed_dose)
                or proposed_dose < 0
            ):
                logger.warning(
                    "Invalid proposed dose %s. Triggering safe fallback.", proposed_dose
                )
                return self._trigger_fallback(
                    proposed_dose=proposed_dose,
                    disturbances=disturbances,
                    reason=f"Non-physical proposed dose value: {proposed_dose}",
                    elapsed_ms=(time.perf_counter() - start_time) * 1000.0,
                    candidate_set=None,
                )

            # 1.5 Check pH validity window for single-chemical alum coagulation model.
            # This must happen BEFORE computing the reachable set because if the pH
            # interval is in the aluminate-dominant regime (> 8.5), the process model's
            # phi_pH penalty is qualitatively backwards: more alum at pH 9.3 causes
            # dissolved aluminum breakthrough, not better turbidity removal. Any
            # certification issued in this regime would be misleading, not just
            # conservative. We refuse to certify and return OUTSIDE_MODEL_VALIDITY.
            if "ph" in disturbances:
                ph_input = disturbances["ph"]
                if isinstance(self.engine.model, SyntheticProcessModel):
                    ph_validity = self.engine.model.check_ph_validity(ph_input)
                    if ph_validity == PhValidityStatus.OUT_OF_RANGE:
                        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                        ph_lo = (
                            ph_input.lo
                            if isinstance(ph_input, Interval)
                            else float(ph_input)
                        )
                        ph_hi = (
                            ph_input.hi
                            if isinstance(ph_input, Interval)
                            else float(ph_input)
                        )
                        validity_reason = (
                            f"pH interval [{ph_lo:.2f}, {ph_hi:.2f}] exceeds the alum "
                            f"coagulation validity window [5.0, 8.0] (out-of-range boundary: 8.5). "
                            f"Above pH 8.5, aluminum speciation shifts to soluble aluminate "
                            f"Al(OH)4- and the model phi_pH penalty is qualitatively incorrect."
                        )
                        logger.warning(
                            "pH interval [%.2f, %.2f] outside model validity. "
                            "Returning OUTSIDE_MODEL_VALIDITY.",
                            ph_lo,
                            ph_hi,
                        )
                        # Build a placeholder ReachableSet using fallback dose for consistent API
                        placeholder_set = ReachableSet(
                            lo=0.0,
                            hi=float("inf"),
                            dose=self.fallback_dose,
                            disturbances={
                                k: (
                                    v
                                    if isinstance(v, Interval)
                                    else Interval(float(v), float(v))
                                )
                                for k, v in disturbances.items()
                            },
                            safety_margin=self.engine.safety_margin,
                        )
                        return CertificationResult(
                            certified_dose=self.fallback_dose,
                            status=CertificationStatus.OUTSIDE_MODEL_VALIDITY,
                            proposed_dose=proposed_dose,
                            reachable_set=placeholder_set,
                            candidate_reachable_set=None,
                            compliance_limit=self.compliance_limit,
                            reason=(
                                f"pH out of model validity range. {validity_reason} "
                                f"Fallback dose {self.fallback_dose:.2f} mg/L applied conservatively "
                                f"but is NOT a validated treatment response at this pH."
                            ),
                            computation_time_ms=elapsed_ms,
                            disturbances={
                                k: (
                                    v
                                    if isinstance(v, Interval)
                                    else Interval(float(v), float(v))
                                )
                                for k, v in disturbances.items()
                            },
                            engine=self.engine,
                            process_model_valid=False,
                            model_validity_reason=validity_reason,
                        )

            # 2. Compute reachable set for proposed dose
            candidate_reachable = self.engine.compute_reachable_set(
                dose=proposed_dose, disturbances=disturbances
            )

            # 3. Check compliance condition: worst-case high must be <= limit
            if candidate_reachable.hi <= self.compliance_limit:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return CertificationResult(
                    certified_dose=proposed_dose,
                    status=CertificationStatus.ACCEPTED,
                    proposed_dose=proposed_dose,
                    reachable_set=candidate_reachable,
                    candidate_reachable_set=candidate_reachable,
                    compliance_limit=self.compliance_limit,
                    reason=(
                        f"Candidate dose {proposed_dose:.2f} mg/L certified safe. "
                        f"Worst-case effluent {candidate_reachable.hi:.3f} NTU <= limit {self.compliance_limit:.2f} NTU."
                    ),
                    computation_time_ms=elapsed_ms,
                    disturbances=dict(disturbances),
                    engine=self.engine,
                )

            # 4. Proposed dose violated compliance envelope: attempt correction
            logger.info(
                "Proposed dose %.2f mg/L rejected (worst-case %.3f NTU > %.2f limit). Correcting.",
                proposed_dose,
                candidate_reachable.hi,
                self.compliance_limit,
            )

            if self.enable_bisection and self.bisection_max_iter > 0:
                corrected_dose, corrected_reachable = self._find_safe_dose(
                    disturbances, start_time=start_time
                )
                if (
                    corrected_dose is not None
                    and corrected_reachable is not None
                    and corrected_reachable.hi <= self.compliance_limit
                ):
                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    return CertificationResult(
                        certified_dose=corrected_dose,
                        status=CertificationStatus.REJECTED_CORRECTED,
                        proposed_dose=proposed_dose,
                        reachable_set=corrected_reachable,
                        candidate_reachable_set=candidate_reachable,
                        compliance_limit=self.compliance_limit,
                        reason=(
                            f"Proposed dose {proposed_dose:.2f} mg/L rejected (worst-case {candidate_reachable.hi:.3f} NTU). "
                            f"Corrected to safe dose {corrected_dose:.2f} mg/L (worst-case {corrected_reachable.hi:.3f} NTU)."
                        ),
                        computation_time_ms=elapsed_ms,
                        disturbances=dict(disturbances),
                        engine=self.engine,
                    )

            # 5. If correction disabled, timed out, or could not find safe dose, fall back
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            if elapsed_ms >= self.max_computation_time_ms:
                fallback_reason = (
                    f"Bisection search time budget exceeded ({elapsed_ms:.2f} ms >= {self.max_computation_time_ms:.1f} ms limit). "
                    f"Reverted to fail-safe default dose."
                )
            elif not self.enable_bisection or self.bisection_max_iter == 0:
                fallback_reason = (
                    f"Candidate dose {proposed_dose:.2f} mg/L breached envelope "
                    f"and fallback search is disabled or iteration cap is zero."
                )
            else:
                fallback_reason = (
                    f"Candidate dose {proposed_dose:.2f} mg/L breached envelope "
                    f"and search could not find a compliant operating point within {self.bisection_max_iter} iterations."
                )

            return self._trigger_fallback(
                proposed_dose=proposed_dose,
                disturbances=disturbances,
                reason=fallback_reason,
                elapsed_ms=elapsed_ms,
                candidate_set=candidate_reachable,
            )

        except Exception as exc:
            # Strict fail-safe guarantee: catch all exceptions, log, and return fallback
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.exception(
                "Critical error during dosing certification: %s. Reverting to fail-safe default.",
                exc,
            )
            return self._trigger_fallback(
                proposed_dose=proposed_dose,
                disturbances=disturbances,
                reason=f"Fail-safe activated due to computational exception: {type(exc).__name__}: {exc}",
                elapsed_ms=elapsed_ms,
                candidate_set=candidate_reachable,
            )

    def _find_safe_dose(
        self,
        disturbances: Mapping[str, Interval],
        start_time: float | None = None,
    ) -> tuple[float | None, ReachableSet | None]:
        """Searches for a certified safe dose within bounds.

        Performs a bounded discrete search over candidate setpoints to identify
        the lowest effective dose whose reachable upper bound satisfies compliance.

        Bounded loop guarantees termination within bisection_max_iter steps and
        max_computation_time_ms wall-clock budget.
        """
        if self.bisection_max_iter <= 0:
            return None, None

        lo_bound, hi_bound = self.dose_search_bounds
        n_coarse = min(15, self.bisection_max_iter)
        candidates = [
            lo_bound + (hi_bound - lo_bound) * (i / max(1, n_coarse - 1))
            for i in range(n_coarse)
        ]

        best_dose: float | None = None
        best_reachable: ReachableSet | None = None
        best_effluent_hi = float("inf")

        for d in candidates:
            if start_time is not None:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                if elapsed_ms >= self.max_computation_time_ms:
                    logger.warning(
                        "Bisection coarse search exceeded time budget (%.2f ms >= %.2f ms). Aborting.",
                        elapsed_ms,
                        self.max_computation_time_ms,
                    )
                    return None, None

            try:
                r = self.engine.compute_reachable_set(d, disturbances)
                if r.hi <= self.compliance_limit:
                    if best_dose is None or d < best_dose:
                        best_dose = d
                        best_reachable = r
                if r.hi < best_effluent_hi:
                    best_effluent_hi = r.hi
            except Exception:
                continue

        # If coarse safe dose found, refine via bisection within remaining iteration budget
        n_refine = max(0, self.bisection_max_iter - n_coarse)
        if best_dose is not None and n_refine > 0:
            fine_lo = max(lo_bound, best_dose - 5.0)
            fine_hi = best_dose
            for _ in range(n_refine):
                if start_time is not None:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                    if elapsed_ms >= self.max_computation_time_ms:
                        logger.warning(
                            "Bisection fine search exceeded time budget (%.2f ms >= %.2f ms). Aborting.",
                            elapsed_ms,
                            self.max_computation_time_ms,
                        )
                        return None, None

                mid = (fine_lo + fine_hi) / 2.0
                try:
                    r_mid = self.engine.compute_reachable_set(mid, disturbances)
                    if r_mid.hi <= self.compliance_limit:
                        best_dose = mid
                        best_reachable = r_mid
                        fine_hi = mid
                    else:
                        fine_lo = mid
                except Exception:
                    fine_lo = mid

        return best_dose, best_reachable

    def _trigger_fallback(
        self,
        proposed_dose: float,
        disturbances: Mapping[str, Interval],
        reason: str,
        elapsed_ms: float,
        candidate_set: ReachableSet | None,
    ) -> CertificationResult:
        """Constructs a fail-safe fallback result."""
        try:
            fallback_reachable = self.engine.compute_reachable_set(
                self.fallback_dose, disturbances
            )
        except Exception:
            # Fallback if disturbance interval evaluation itself fails
            fallback_reachable = ReachableSet(
                lo=0.0,
                hi=self.compliance_limit,
                dose=self.fallback_dose,
                disturbances=dict(disturbances),
                safety_margin=self.engine.safety_margin,
            )

        return CertificationResult(
            certified_dose=self.fallback_dose,
            status=CertificationStatus.FAILED_SAFE_FALLBACK,
            proposed_dose=proposed_dose,
            reachable_set=fallback_reachable,
            candidate_reachable_set=candidate_set,
            compliance_limit=self.compliance_limit,
            reason=f"FAIL-SAFE DEFAULT APPLIED ({self.fallback_dose:.2f} mg/L): {reason}",
            computation_time_ms=elapsed_ms,
            disturbances=dict(disturbances),
            engine=self.engine,
        )

    def wrap_controller(self, controller: BaseController) -> WrappedControllerProtocol:
        """Returns an integrated controller object implementing the certified policy."""
        return WrappedControllerProtocol(self, controller)


class WrappedControllerProtocol:
    """Wrapper encapsulating candidate controller and safety certifier."""

    def __init__(
        self, certifier: CertifiedDoseWrapper, candidate_controller: BaseController
    ) -> None:
        self.certifier = certifier
        self.candidate_controller = candidate_controller

    def step(
        self, state: PlantState, custom_uncertainty: dict[str, float] | None = None
    ) -> tuple[float, CertificationResult]:
        """Proposes, certifies, and returns the verified action."""
        proposed = self.candidate_controller.propose_dose(state)
        disturbances = self.certifier.build_disturbance_intervals(
            state, custom_uncertainty
        )
        result = self.certifier.certify_action(proposed, disturbances)
        return result.certified_dose, result
