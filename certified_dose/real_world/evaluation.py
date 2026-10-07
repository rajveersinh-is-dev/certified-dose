from __future__ import annotations

import time
from typing import Any

from certified_dose.certifier import CertificationStatus, CertifiedDoseWrapper
from certified_dose.controller import (
    AggressiveCostMinimizerController,
    HeuristicController,
    PlantState,
)
from certified_dose.process_model import SyntheticProcessModel
from certified_dose.reachability import ReachabilityEngine
from certified_dose.real_world.models import RealWorldDataset
from certified_dose.real_world.uncertainty import (
    InstrumentUncertaintySpecs,
    derive_disturbance_intervals,
)


def evaluate_dataset_on_pipeline(
    dataset: RealWorldDataset,
    compliance_limit: float = 1.0,
    uncertainty_specs: InstrumentUncertaintySpecs | None = None,
    max_records: int | None = None,
) -> dict[str, Any]:
    """Run operational water quality dataset through certification pipeline.

    Args:
        dataset: Loaded and validated RealWorldDataset.
        compliance_limit: Statutory effluent compliance threshold (NTU).
        uncertainty_specs: Sensor instrumentation measurement tolerances.
        max_records: Optional cap on evaluated records.

    Returns:
        Structured evaluation metrics and record analysis.
    """


    if uncertainty_specs is None:
        uncertainty_specs = InstrumentUncertaintySpecs()

    records = dataset.records[:max_records] if max_records else dataset.records
    total_records = len(records)
    if total_records == 0:
        return {"error": "Empty dataset"}

    model = SyntheticProcessModel()
    engine = ReachabilityEngine(model=model, safety_margin=0.02)
    wrapper = CertifiedDoseWrapper(
        engine=engine,
        compliance_limit=compliance_limit,
        fallback_dose=15.0,
        bisection_max_iter=25,
        max_computation_time_ms=50.0,
    )

    heuristic_ctrl = HeuristicController()
    aggressive_ctrl = AggressiveCostMinimizerController(aggression=0.70)

    q_nom = dataset.get_nominal_flow()

    heur_accepted = 0
    heur_corrected = 0
    heur_fallback = 0
    heur_outside_validity = 0
    heur_times: list[float] = []
    heur_doses: list[float] = []
    heur_applied_doses: list[float] = []

    aggr_accepted = 0
    aggr_corrected = 0
    aggr_fallback = 0
    aggr_outside_validity = 0
    aggr_times: list[float] = []
    aggr_doses: list[float] = []
    aggr_applied_doses: list[float] = []

    model_soundness_breaches = 0
    unverified_heuristic_violations = 0
    unverified_aggressive_violations = 0
    certified_heuristic_violations = 0
    certified_aggressive_violations = 0

    driver_counts: dict[str, int] = {}
    flagged_records: list[dict[str, Any]] = []

    for i, rec in enumerate(records):
        disturbances = derive_disturbance_intervals(
            rec, specs=uncertainty_specs, nominal_flow_cfs=q_nom
        )
        flow_norm = rec.flow_cfs / q_nom
        state = PlantState(
            turbidity=rec.turbidity_ntu,
            flow_rate=flow_norm,
            ph=rec.ph,
            temperature=rec.temperature_c,
            previous_dose=20.0,
        )

        # 1. Heuristic Controller
        d_heur = heuristic_ctrl.propose_dose(state)
        heur_doses.append(d_heur)

        t0 = time.perf_counter()
        res_heur = wrapper.certify_action(d_heur, disturbances)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        heur_times.append(dt_ms)
        heur_applied_doses.append(res_heur.certified_dose)

        if res_heur.status == CertificationStatus.ACCEPTED:
            heur_accepted += 1
        elif res_heur.status == CertificationStatus.REJECTED_CORRECTED:
            heur_corrected += 1
        elif res_heur.status == CertificationStatus.OUTSIDE_MODEL_VALIDITY:
            heur_outside_validity += 1
        else:
            heur_fallback += 1

        try:
            explanation = res_heur.explain()
            driver = explanation.top_contributor
            driver_counts[driver] = driver_counts.get(driver, 0) + 1
        except Exception:
            driver = "unknown"

        # 2. Aggressive Controller
        d_aggr = aggressive_ctrl.propose_dose(state)
        aggr_doses.append(d_aggr)

        t0 = time.perf_counter()
        res_aggr = wrapper.certify_action(d_aggr, disturbances)
        dt_aggr_ms = (time.perf_counter() - t0) * 1000.0
        aggr_times.append(dt_aggr_ms)
        aggr_applied_doses.append(res_aggr.certified_dose)

        if res_aggr.status == CertificationStatus.ACCEPTED:
            aggr_accepted += 1
        elif res_aggr.status == CertificationStatus.REJECTED_CORRECTED:
            aggr_corrected += 1
        elif res_aggr.status == CertificationStatus.OUTSIDE_MODEL_VALIDITY:
            aggr_outside_validity += 1
        else:
            aggr_fallback += 1

        # 3. Ground truth evaluation against model kinetics at true point disturbances
        # Skip for records where pH validity is exceeded (model output is misleading)
        if not res_heur.process_model_valid:
            # pH is outside validity window -- model output is not meaningful for
            # soundness checking. Soundness check is scoped to valid pH regime.
            pass
        else:
            true_disturbances = {
                "turbidity": rec.turbidity_ntu,
                "flow_rate": flow_norm,
                "ph": rec.ph,
                "temperature": rec.temperature_c,
            }
            y_naive_heur = model.evaluate_scalar(d_heur, true_disturbances)
            y_naive_aggr = model.evaluate_scalar(d_aggr, true_disturbances)
            y_cert_heur = model.evaluate_scalar(
                res_heur.certified_dose, true_disturbances
            )
            y_cert_aggr = model.evaluate_scalar(
                res_aggr.certified_dose, true_disturbances
            )

            if y_naive_heur > compliance_limit:
                unverified_heuristic_violations += 1
            if y_naive_aggr > compliance_limit:
                unverified_aggressive_violations += 1
            if y_cert_heur > compliance_limit:
                certified_heuristic_violations += 1
            if y_cert_aggr > compliance_limit:
                certified_aggressive_violations += 1

            if res_heur.reachable_set.hi < y_cert_heur - 1e-9:
                model_soundness_breaches += 1

        if (
            rec.turbidity_ntu > 80.0
            or rec.ph > 8.5
            or res_heur.status == CertificationStatus.FAILED_SAFE_FALLBACK
            or res_aggr.status == CertificationStatus.FAILED_SAFE_FALLBACK
            or res_heur.status == CertificationStatus.OUTSIDE_MODEL_VALIDITY
        ):
            flagged_records.append(
                {
                    "index": i,
                    "timestamp": rec.timestamp,
                    "turbidity_ntu": rec.turbidity_ntu,
                    "ph": rec.ph,
                    "temperature_c": rec.temperature_c,
                    "flow_cfs": rec.flow_cfs,
                    "heur_candidate_dose": round(d_heur, 2),
                    "heur_certified_dose": round(res_heur.certified_dose, 2),
                    "heur_status": res_heur.status.value,
                    "heur_upper_bound": round(res_heur.reachable_set.hi, 3),
                    "aggr_candidate_dose": round(d_aggr, 2),
                    "aggr_certified_dose": round(res_aggr.certified_dose, 2),
                    "aggr_status": res_aggr.status.value,
                    "primary_driver": driver,
                }
            )

    def _dist(vals: list[float]) -> dict[str, float]:
        s = sorted(vals)
        n = len(vals)
        return {
            "mean": round(sum(vals) / n, 4),
            "median": round(s[n // 2], 4),
            "p95": round(s[int(n * 0.95)], 4),
            "p99": round(s[int(n * 0.99)], 4),
            "max": round(s[-1], 4),
        }

    return {
        "site_id": dataset.site_id,
        "site_name": dataset.site_name,
        "total_records_evaluated": total_records,
        "nominal_flow_cfs": round(q_nom, 1),
        "compliance_limit_ntu": compliance_limit,
        "summary_statistics": dataset.summary_statistics(),
        "heuristic_controller": {
            "accepted_count": heur_accepted,
            "accepted_pct": round((heur_accepted / total_records) * 100.0, 2),
            "corrected_count": heur_corrected,
            "corrected_pct": round((heur_corrected / total_records) * 100.0, 2),
            "outside_validity_count": heur_outside_validity,
            "outside_validity_pct": round(
                (heur_outside_validity / total_records) * 100.0, 2
            ),
            "fallback_count": heur_fallback,
            "fallback_pct": round((heur_fallback / total_records) * 100.0, 2),
            "unverified_violations": unverified_heuristic_violations,
            "certified_violations": certified_heuristic_violations,
            "mean_candidate_dose_mg_l": round(sum(heur_doses) / total_records, 2),
            "mean_applied_dose_mg_l": round(sum(heur_applied_doses) / total_records, 2),
            "chemical_overhead_pct": round(
                ((sum(heur_applied_doses) - sum(heur_doses)) / sum(heur_doses)) * 100.0,
                2,
            ),
            "latency_ms": _dist(heur_times),
        },
        "aggressive_controller": {
            "accepted_count": aggr_accepted,
            "accepted_pct": round((aggr_accepted / total_records) * 100.0, 2),
            "corrected_count": aggr_corrected,
            "corrected_pct": round((aggr_corrected / total_records) * 100.0, 2),
            "outside_validity_count": aggr_outside_validity,
            "outside_validity_pct": round(
                (aggr_outside_validity / total_records) * 100.0, 2
            ),
            "fallback_count": aggr_fallback,
            "fallback_pct": round((aggr_fallback / total_records) * 100.0, 2),
            "unverified_violations": unverified_aggressive_violations,
            "certified_violations": certified_aggressive_violations,
            "mean_candidate_dose_mg_l": round(sum(aggr_doses) / total_records, 2),
            "mean_applied_dose_mg_l": round(sum(aggr_applied_doses) / total_records, 2),
            "latency_ms": _dist(aggr_times),
        },
        "soundness_checks": {
            "model_soundness_breaches": model_soundness_breaches,
            "guarantee_held": model_soundness_breaches == 0,
        },
        "uncertainty_attribution_drivers": driver_counts,
        "flagged_stress_events_count": len(flagged_records),
        "flagged_stress_events_sample": flagged_records[:10],
    }
