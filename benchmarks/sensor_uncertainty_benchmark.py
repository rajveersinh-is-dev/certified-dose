"""Benchmark analyzing sensitivity of certification outcomes to sensor uncertainty models.

Compares:
1. Flat proportional 5% (optimistic field specification)
2. Flat proportional 10% (current default model)
3. Flat proportional 15% (conservative field specification)
4. Piecewise EPA Method 180.1 tiered model:
   - T <= 40 NTU: +/-5% (validated EPA 180.1 optical range)
   - 40 < T <= 100 NTU: +/-10% (transitional)
   - T > 100 NTU: +/-15% (multiple-scattering degradation)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from certified_dose.real_world import (
    InstrumentUncertaintySpecs,
    RealWorldDataset,
    TurbidityUncertaintyModel,
    evaluate_dataset_on_pipeline,
)


def run_sensor_uncertainty_sweep() -> dict[str, Any]:
    data_dir = Path("data/real_world")
    stations = [
        ("04193500", "Maumee River at Waterville OH"),
        ("01184000", "Connecticut River at Thompsonville CT"),
    ]

    models = [
        (
            "proportional_5pct",
            InstrumentUncertaintySpecs(
                turbidity_rel_error=0.05,
                turbidity_model=TurbidityUncertaintyModel.PROPORTIONAL_10PCT,
            ),
        ),
        (
            "proportional_10pct_default",
            InstrumentUncertaintySpecs(
                turbidity_rel_error=0.10,
                turbidity_model=TurbidityUncertaintyModel.PROPORTIONAL_10PCT,
            ),
        ),
        (
            "proportional_15pct",
            InstrumentUncertaintySpecs(
                turbidity_rel_error=0.15,
                turbidity_model=TurbidityUncertaintyModel.PROPORTIONAL_10PCT,
            ),
        ),
        (
            "piecewise_epa_range",
            InstrumentUncertaintySpecs(
                turbidity_model=TurbidityUncertaintyModel.PIECEWISE_EPA_RANGE,
            ),
        ),
    ]

    sweep_results: dict[str, Any] = {}

    for site_id, site_name in stations:
        csv_file = data_dir / f"usgs_{site_id}_cleaned.csv"
        if not csv_file.exists():
            continue

        dataset = RealWorldDataset.from_csv(
            csv_file, site_id=site_id, site_name=site_name
        )
        site_results: dict[str, Any] = {}

        for model_name, specs in models:
            res = evaluate_dataset_on_pipeline(dataset, uncertainty_specs=specs)
            heur = res["heuristic_controller"]
            aggr = res["aggressive_controller"]
            site_results[model_name] = {
                "heuristic": {
                    "accepted_count": heur["accepted_count"],
                    "accepted_pct": heur["accepted_pct"],
                    "corrected_count": heur["corrected_count"],
                    "corrected_pct": heur["corrected_pct"],
                    "outside_validity_count": heur["outside_validity_count"],
                    "outside_validity_pct": heur["outside_validity_pct"],
                    "chemical_overhead_pct": heur["chemical_overhead_pct"],
                    "mean_applied_dose": heur["mean_applied_dose_mg_l"],
                },
                "aggressive": {
                    "accepted_count": aggr["accepted_count"],
                    "accepted_pct": aggr["accepted_pct"],
                    "corrected_count": aggr["corrected_count"],
                    "corrected_pct": aggr["corrected_pct"],
                    "outside_validity_count": aggr["outside_validity_count"],
                    "outside_validity_pct": aggr["outside_validity_pct"],
                    "mean_applied_dose": aggr["mean_applied_dose_mg_l"],
                },
            }

        sweep_results[site_id] = site_results

    out_file = Path("benchmarks/results_sensor_uncertainty.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(sweep_results, f, indent=2)

    return sweep_results


if __name__ == "__main__":
    results = run_sensor_uncertainty_sweep()
    for site, site_data in results.items():
        print(f"=== {site} ===")
        for model, data in site_data.items():
            h = data["heuristic"]
            print(
                f"  {model:28s} | Acc: {h['accepted_pct']:5.2f}% | "
                f"Corr: {h['corrected_pct']:5.2f}% | "
                f"OOB: {h['outside_validity_pct']:5.2f}% | "
                f"Overhead: {h['chemical_overhead_pct']:5.2f}% | "
                f"Mean Dose: {h['mean_applied_dose']:.2f} mg/L"
            )
