from __future__ import annotations

import csv
import io
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("certified_dose.real_world")

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
