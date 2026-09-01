"""Evaluation benchmark running real-world USGS operational data through certified-dose.

Evaluates:
1. USGS 04193500 (Maumee River at Waterville OH - Toledo Drinking Water Intake).
2. USGS 01184000 (Connecticut River at Thompsonville CT - Upland Water Source).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from certified_dose.real_world import (
    RealWorldDataset,
    evaluate_dataset_on_pipeline,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def run_benchmark() -> int:
    parser = argparse.ArgumentParser(
        description="Run certified-dose evaluation on real-world USGS datasets."
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/real_world",
        help="Directory containing cleaned CSV files.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="benchmarks/results_real_world.json",
        help="Output JSON path for results.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    results: dict[str, Any] = {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%SZ"),
        "datasets": {},
    }

    stations = [
        ("04193500", "Maumee River at Waterville OH (Toledo WTP Intake)"),
        ("01184000", "Connecticut River at Thompsonville CT"),
    ]

    for site_id, site_name in stations:
        csv_file = data_dir / f"usgs_{site_id}_cleaned.csv"
        if not csv_file.exists():
            logger.warning(
                "Cleaned CSV %s not found. Run scripts/fetch_real_world_data.py first.",
                csv_file,
            )
            continue

        logger.info("Evaluating %s: %s...", site_id, site_name)
        dataset = RealWorldDataset.from_csv(
            csv_file, site_id=site_id, site_name=site_name
        )
        report = evaluate_dataset_on_pipeline(dataset, compliance_limit=1.0)
        results["datasets"][site_id] = report

        heur = report["heuristic_controller"]
        aggr = report["aggressive_controller"]
        logger.info(
            "[%s] Evaluated %d records | Heuristic: Accepted=%s%%, Corrected=%s%%, Violations: %d -> %d",
            site_id,
            report["total_records_evaluated"],
            heur["accepted_pct"],
            heur["corrected_pct"],
            heur["unverified_violations"],
            heur["certified_violations"],
        )
        logger.info(
            "[%s] Aggressive: Accepted=%s%%, Corrected=%s%%, Violations: %d -> %d",
            site_id,
            aggr["accepted_pct"],
            aggr["corrected_pct"],
            aggr["unverified_violations"],
            aggr["certified_violations"],
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    logger.info("Saved full evaluation results to %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(run_benchmark())
