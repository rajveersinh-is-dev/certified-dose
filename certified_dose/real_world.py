"""Real-world operational water quality data ingestion and normalization.

Provides parsing, validation, and instrument-precision uncertainty derivation
for live operational telemetry streams (e.g. USGS continuous water quality stations).
"""

from __future__ import annotations

import csv
import io
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from certified_dose.intervals import Interval


@dataclass(frozen=True)
class RealWorldRecord:
    """A single aligned operational telemetry observation."""

    timestamp: str
    turbidity_ntu: float
    flow_cfs: float
    ph: float
    temperature_c: float
    site_id: str = ""
    site_name: str = ""

    def validate(self) -> None:
        """Validate physical plausibility."""
        if math.isnan(self.turbidity_ntu) or self.turbidity_ntu <= 0.0:
            msg = f"Invalid turbidity: {self.turbidity_ntu}"
            raise ValueError(msg)
        if math.isnan(self.ph) or not (0.0 <= self.ph <= 14.0):
            msg = f"Invalid pH: {self.ph}"
            raise ValueError(msg)
        if math.isnan(self.temperature_c) or not (-10.0 <= self.temperature_c <= 60.0):
            msg = f"Invalid temperature: {self.temperature_c}"
            raise ValueError(msg)
        if math.isnan(self.flow_cfs) or self.flow_cfs < 0.0:
            msg = f"Invalid flow: {self.flow_cfs}"
            raise ValueError(msg)


class TurbidityUncertaintyModel(str):
    """Turbidimeter field accuracy model selection.

    PROPORTIONAL_10PCT: Flat +/-10% of reading (or +/-0.50 NTU floor).
        This is the current default and matches a conservative interpretation
        of EPA Method 180.1 field optical tolerance. Reasonable for 0-100 NTU.

    PIECEWISE_EPA_RANGE: Three-tier piecewise model grounded in instrumentation
        literature and manufacturer specifications:
          - T <= 40 NTU: +/-5% of reading (EPA Method 180.1 validated range;
            laboratory and high-quality field instruments achieve ~2% but
            +/-5% conservatively accounts for field drift).
          - 40 < T <= 100 NTU: +/-10% of reading (EPA 180.1 recommends dilution
            above 40 NTU; multiple-scattering effects become non-negligible).
          - T > 100 NTU: +/-15% of reading (multiple scattering at high
            turbidity causes sub-linear signal response in nephelometric
            instruments; the true uncertainty is larger in absolute terms;
            Fondriest (2014) Environmental Measurement Systems; Hach 1720E
            spec sheet: +/-5% for 0-1000 NTU under lab conditions, but field
            studies suggest 10-20% at > 100 NTU with inline probes).

        Floor: +/-0.50 NTU minimum absolute error (applies at all ranges).

    References:
      - EPA Method 180.1 (1993): Validated for 0-40 NTU; requires dilution above 40 NTU.
      - ISO 7027:2016: Turbidity measurement standard (infrared preferred at high values).
      - Fondriest Environmental (2014). Turbidity, Total Suspended Solids & Water Clarity.
        Fundamentals of Environmental Measurements. fondriest.com.
      - Hach Company (2020). 1720E Process Turbidimeter Instrument Manual.
    """

    PROPORTIONAL_10PCT = "PROPORTIONAL_10PCT"
    PIECEWISE_EPA_RANGE = "PIECEWISE_EPA_RANGE"


@dataclass(frozen=True)
class InstrumentUncertaintySpecs:
    """Standard field instrumentation precision and measurement tolerances.

    Based on EPA Method 180.1 (Turbidity), EPA Method 150.1 (pH),
    and standard industrial flow/temperature sensor specifications.
    """

    turbidity_rel_error: float = 0.10  # +/- 10% optical field allowance (default)
    turbidity_min_abs_error: float = 0.50  # +/- 0.50 NTU floor (all models)
    ph_abs_error: float = 0.15  # +/- 0.15 pH units electrode drift
    temp_abs_error: float = 0.50  # +/- 0.50 C thermistor tolerance
    flow_rel_error: float = 0.05  # +/- 5.0% intake meter accuracy
    turbidity_model: str = TurbidityUncertaintyModel.PROPORTIONAL_10PCT


def derive_disturbance_intervals(
    record: RealWorldRecord,
    specs: InstrumentUncertaintySpecs | None = None,
    nominal_flow_cfs: float | None = None,
) -> dict[str, Interval]:
    """Derive certified bounded uncertainty intervals from a point sensor record.

    Args:
        record: Real-world operational telemetry observation.
        specs: Instrumentation tolerance specifications.
        nominal_flow_cfs: Plant nominal intake flow for normalization. If None,
            record.flow_cfs is used as baseline (flow factor = 1.0).

    Returns:
        Dictionary mapping disturbance variable names to certified Interval objects.
    """
    if specs is None:
        specs = InstrumentUncertaintySpecs()

    record.validate()

    # Turbidity interval: error model depends on specs.turbidity_model
    if specs.turbidity_model == TurbidityUncertaintyModel.PIECEWISE_EPA_RANGE:
        # Piecewise model grounded in EPA Method 180.1 validated range and
        # field instrumentation literature (see TurbidityUncertaintyModel docstring).
        t = record.turbidity_ntu
        if t <= 40.0:
            # EPA Method 180.1 validated range: +/-5% conservative field allowance
            rel_error = 0.05
        elif t <= 100.0:
            # Above EPA validated range; multiple-scattering begins: +/-10%
            rel_error = 0.10
        else:
            # High turbidity (>100 NTU): multiple-scattering dominant: +/-15%
            rel_error = 0.15
        turb_delta = max(specs.turbidity_min_abs_error, rel_error * t)
    else:
        # Default: flat proportional +/-10% (PROPORTIONAL_10PCT)
        turb_delta = max(
            specs.turbidity_min_abs_error,
            specs.turbidity_rel_error * record.turbidity_ntu,
        )

    turb_lo = max(0.01, record.turbidity_ntu - turb_delta)
    turb_hi = record.turbidity_ntu + turb_delta
    turb_interval = Interval(turb_lo, turb_hi)

    # pH interval: +/- abs_error, clamped to [0, 14]
    ph_lo = max(1.0, record.ph - specs.ph_abs_error)
    ph_hi = min(13.0, record.ph + specs.ph_abs_error)
    ph_interval = Interval(ph_lo, ph_hi)

    # Temperature interval: +/- abs_error, clamped to physical water range
    temp_lo = max(0.5, record.temperature_c - specs.temp_abs_error)
    temp_hi = min(45.0, record.temperature_c + specs.temp_abs_error)
    temp_interval = Interval(temp_lo, temp_hi)

    # Relative flow rate: normalized by nominal flow (Q / Q_nom)
    q_nom = (
        nominal_flow_cfs
        if (nominal_flow_cfs and nominal_flow_cfs > 0)
        else max(1.0, record.flow_cfs)
    )
    flow_delta = specs.flow_rel_error * record.flow_cfs
    flow_lo = max(0.05, (record.flow_cfs - flow_delta) / q_nom)
    flow_hi = max(flow_lo, (record.flow_cfs + flow_delta) / q_nom)
    flow_interval = Interval(flow_lo, flow_hi)

    return {
        "turbidity": turb_interval,
        "flow_rate": flow_interval,
        "ph": ph_interval,
        "temperature": temp_interval,
    }


@dataclass
class RealWorldDataset:
    """Container for a validated sequence of real-world operational records."""

    site_id: str
    site_name: str
    records: list[RealWorldRecord]
    metadata: dict[str, Any]

    @property
    def record_count(self) -> int:
        return len(self.records)

    def get_nominal_flow(self) -> float:
        """Compute median flow rate across dataset as nominal plant intake."""
        if not self.records:
            return 1000.0
        sorted_flows = sorted(r.flow_cfs for r in self.records)
        mid = len(sorted_flows) // 2
        return float(sorted_flows[mid])

    def summary_statistics(self) -> dict[str, dict[str, float]]:
        """Compute min, median, mean, and max for each measured variable."""
        if not self.records:
            return {}

        turbidities = [r.turbidity_ntu for r in self.records]
        flows = [r.flow_cfs for r in self.records]
        phs = [r.ph for r in self.records]
        temps = [r.temperature_c for r in self.records]

        def _stats(vals: list[float]) -> dict[str, float]:
            s = sorted(vals)
            n = len(vals)
            return {
                "min": s[0],
                "median": s[n // 2],
                "mean": sum(vals) / n,
                "max": s[-1],
            }

        return {
            "turbidity_ntu": _stats(turbidities),
            "flow_cfs": _stats(flows),
            "ph": _stats(phs),
            "temperature_c": _stats(temps),
        }

    @classmethod
    def from_csv(
        cls,
        csv_source: str | Path | io.StringIO,
        site_id: str = "",
        site_name: str = "",
    ) -> RealWorldDataset:
        """Parse cleaned CSV into RealWorldDataset."""
        records: list[RealWorldRecord] = []

        if isinstance(csv_source, (str, Path)) and Path(csv_source).exists():
            with open(csv_source, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(
                        RealWorldRecord(
                            timestamp=row["timestamp"],
                            turbidity_ntu=float(row["turbidity_ntu"]),
                            flow_cfs=float(row["flow_cfs"]),
                            ph=float(row["ph"]),
                            temperature_c=float(row["temperature_c"]),
                            site_id=site_id,
                            site_name=site_name,
                        )
                    )
        elif isinstance(csv_source, (io.StringIO, str)):
            buf = io.StringIO(csv_source) if isinstance(csv_source, str) else csv_source
            reader = csv.DictReader(buf)
            for row in reader:
                records.append(
                    RealWorldRecord(
                        timestamp=row["timestamp"],
                        turbidity_ntu=float(row["turbidity_ntu"]),
                        flow_cfs=float(row["flow_cfs"]),
                        ph=float(row["ph"]),
                        temperature_c=float(row["temperature_c"]),
                        site_id=site_id,
                        site_name=site_name,
                    )
                )

        return cls(
            site_id=site_id,
            site_name=site_name or site_id,
            records=records,
            metadata={"record_count": len(records)},
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
    import time

    from certified_dose.certifier import CertificationStatus, CertifiedDoseWrapper
    from certified_dose.controller import (
        AggressiveCostMinimizerController,
        HeuristicController,
        PlantState,
    )
    from certified_dose.process_model import SyntheticProcessModel
    from certified_dose.reachability import ReachabilityEngine

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
