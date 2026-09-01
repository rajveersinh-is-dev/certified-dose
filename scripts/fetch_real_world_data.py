"""Reproducible ingestion script for real-world water quality operational data.

This script fetches continuous, real-time water quality monitoring telemetry
directly from the United States Geological Survey (USGS) National Water Information
System (NWIS) REST API.

Data Sources:
1. USGS 04193500 - MAUMEE RIVER AT WATERVILLE OH
   - Raw intake source for the City of Toledo Collins Park Water Treatment Plant.
   - Parameters: Turbidity (63680), Streamflow (00060), pH (00400), Temperature (00010).
2. USGS 01184000 - CONNECTICUT RIVER AT THOMPSONVILLE CT
   - Clean upland municipal drinking water supply source.
   - Parameters: Turbidity (63680), Streamflow (00060), pH (00400), Temperature (00010).

License:
   U.S. Geological Survey / U.S. Government Work (Public Domain).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

USGS_BASE_URL = "https://waterservices.usgs.gov/nwis/iv/"

DEFAULT_STATIONS = {
    "04193500": {
        "name": "Maumee River at Waterville OH",
        "description": "Primary surface drinking water intake for Toledo Collins Park Water Treatment Plant",
        "state": "OH",
        "parameters": ["00060", "00010", "00400", "63680"],
    },
    "01184000": {
        "name": "Connecticut River at Thompsonville CT",
        "description": "Regional municipal drinking water intake and upland river watershed",
        "state": "CT",
        "parameters": ["00060", "00010", "00400", "63680"],
    },
}

CODE_MAP = {
    "00010": "temperature_c",
    "00060": "flow_cfs",
    "00400": "ph",
    "63680": "turbidity_ntu",
}


def fetch_usgs_station_data(site_id: str, period_days: int = 30) -> dict[str, Any]:
    """Fetch instantaneous values from USGS NWIS REST API.

    Args:
        site_id: 8-digit USGS station number.
        period_days: Number of trailing days to fetch (e.g. 30 or 90).

    Returns:
        Parsed JSON dictionary from USGS.
    """
    params_str = ",".join(CODE_MAP.keys())
    url = f"{USGS_BASE_URL}?format=json&sites={site_id}&parameterCd={params_str}&period=P{period_days}D"
    logger.info("Fetching live data from USGS URL: %s", url)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "certified-dose-real-world-evaluation/0.3.0 (https://github.com/Raj123-0/certified-dose)"
        },
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            msg = f"USGS API returned HTTP status {resp.status}"
            raise RuntimeError(msg)
        content = resp.read().decode("utf-8")
        data: dict[str, Any] = json.loads(content)
        return data


def align_and_clean_usgs_series(
    raw_data: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Align multiple USGS parameter time series into synchronized records.

    Args:
        raw_data: Raw USGS JSON response.

    Returns:
        Tuple of (aligned_records, metadata).
    """
    time_series_list = raw_data.get("value", {}).get("timeSeries", [])
    if not time_series_list:
        return [], {}

    site_info = time_series_list[0].get("sourceInfo", {})
    metadata = {
        "site_code": site_info.get("siteCode", [{}])[0].get("value", "unknown"),
        "site_name": site_info.get("siteName", "Unknown Station"),
        "latitude": site_info.get("geoLocation", {})
        .get("geogLocation", {})
        .get("latitude"),
        "longitude": site_info.get("geoLocation", {})
        .get("geogLocation", {})
        .get("longitude"),
    }

    records_by_time: dict[str, dict[str, Any]] = {}

    for ts in time_series_list:
        var_codes = ts.get("variable", {}).get("variableCode", [])
        if not var_codes:
            continue
        param_code = var_codes[0].get("value")
        if param_code not in CODE_MAP:
            continue

        column_name = CODE_MAP[param_code]
        values = ts.get("values", [{}])[0].get("value", [])

        for pt in values:
            dt = pt.get("dateTime")
            raw_val = pt.get("value")
            if raw_val in (None, "", "-999999", "-999999.0"):
                continue

            try:
                numeric_val = float(raw_val)
            except (ValueError, TypeError):
                continue

            if dt not in records_by_time:
                records_by_time[dt] = {"timestamp": dt}
            records_by_time[dt][column_name] = numeric_val

    # Only retain records with all 4 required operational variables
    required_cols = {"temperature_c", "flow_cfs", "ph", "turbidity_ntu"}
    complete_records: list[dict[str, Any]] = []

    for dt in sorted(records_by_time.keys()):
        rec = records_by_time[dt]
        if required_cols.issubset(rec.keys()):
            # Filter out unphysical outliers/fault codes
            if (
                rec["turbidity_ntu"] >= 0.01
                and 0.0 < rec["ph"] < 14.0
                and -5.0 < rec["temperature_c"] < 50.0
                and rec["flow_cfs"] >= 0.0
            ):
                complete_records.append(rec)

    return complete_records, metadata


def save_dataset(
    output_dir: Path,
    site_id: str,
    raw_data: dict[str, Any],
    clean_records: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> tuple[Path, Path]:
    """Save raw JSON payload and cleaned aligned CSV.

    Args:
        output_dir: Target data directory.
        site_id: Station ID.
        raw_data: Raw JSON.
        clean_records: Cleaned aligned records.
        metadata: Station metadata.

    Returns:
        Tuple of (raw_path, csv_path).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_path = output_dir / f"usgs_{site_id}_raw.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, indent=2)

    csv_path = output_dir / f"usgs_{site_id}_cleaned.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["timestamp", "turbidity_ntu", "flow_cfs", "ph", "temperature_c"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in clean_records:
            writer.writerow(r)

    logger.info(
        "Saved %s: %d aligned records to %s and raw JSON to %s",
        site_id,
        len(clean_records),
        csv_path,
        raw_path,
    )
    return raw_path, csv_path


def write_readme(output_dir: Path, stations_meta: list[dict[str, Any]]) -> Path:
    """Generate data/real_world/README.md with provenance and licensing details."""
    readme_path = output_dir / "README.md"
    fetch_time = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# Real-World Water Quality Operational Telemetry Datasets",
        "",
        f"> **Provenance & Ingestion Log**: Fetched live via `scripts/fetch_real_world_data.py` on `{fetch_time}`.",
        "",
        "## 1. Overview & Provenance",
        "These datasets provide real-world, high-frequency continuous operational sensor telemetry",
        "collected by the **United States Geological Survey (USGS)** National Water Information System (NWIS).",
        "They capture the actual physical source water quality conditions entering municipal drinking water plants.",
        "",
        "### Included Stations:",
        "",
    ]

    for meta in stations_meta:
        lines.extend(
            [
                f"### USGS Station `{meta['site_code']}`: {meta['site_name']}",
                f"- **Station Name**: {meta['site_name']}",
                f"- **Coordinates**: Latitude `{meta['latitude']}`, Longitude `{meta['longitude']}`",
                f"- **Source Description**: {meta.get('description', 'USGS Streamgage and Water Quality Station')}",
                f"- **Source API URL**: `https://waterservices.usgs.gov/nwis/iv/?sites={meta['site_code']}&parameterCd=00060,00010,00400,63680`",
                "- **Sampling Frequency**: 15-minute continuous automated sensor records",
                f"- **Total Aligned Records**: {meta['record_count']:,}",
                f"- **Date Range**: `{meta['start_time']}` to `{meta['end_time']}`",
                "- **Parameters Included**:",
                "  1. `turbidity_ntu` (USGS Parameter `63680`): Formazin Nephelometric Units (FNU / NTU), 780-900nm near-IR optical detection.",
                "  2. `flow_cfs` (USGS Parameter `00060`): River streamflow / intake discharge in cubic feet per second ($ft^3/s$).",
                "  3. `ph` (USGS Parameter `00400`): Field unfiltered pH (standard units).",
                "  4. `temperature_c` (USGS Parameter `00010`): Water temperature in degrees Celsius ($^\\circ$C).",
                "",
            ]
        )

    lines.extend(
        [
            "## 2. Licensing & Terms of Use",
            "- **Publisher**: U.S. Geological Survey (USGS), U.S. Department of the Interior.",
            "- **License**: **Public Domain** (U.S. Government Work). Unrestricted public access and distribution under 17 U.S.C. § 105.",
            "- **Data Integrity Notice**: Raw sensor provisional data (`P` qualifier) may include sensor noise, diurnal algal fluctuations, calibration drift, and physical storm spikes.",
            "",
            "## 3. Instrument Precision & Uncertainty Derivation",
            "In `certified-dose`, point-in-time sensor readings are converted into bounded uncertainty intervals",
            "derived from published instrumentation precision specifications (EPA Method 180.1 / ISO 7027):",
            "- **Turbidity ($T_{\\text{in}}$)**: Optical field fouling allowance of $\\pm 10\\%$ of reading or $\\pm 0.5\\text{ NTU}$ (whichever is larger).",
            "- **pH**: Glass electrode liquid-junction and buffer drift of $\\pm 0.15\\text{ pH}$ units.",
            "- **Temperature ($T$)**: Industrial thermistor tolerance of $\\pm 0.5^\\circ\\text{C}$.",
            "- **Relative Flow ($Q/Q_{\\text{nom}}$)**: Intake flow meter tolerance of $\\pm 5.0\\%$.",
            "",
        ]
    )

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info("Wrote dataset documentation to %s", readme_path)
    return readme_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch real-world operational water quality data from USGS NWIS API."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of trailing days of telemetry to fetch (default: 30).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/real_world",
        help="Target output directory (default: data/real_world).",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stations_meta = []

    for site_id, info in DEFAULT_STATIONS.items():
        logger.info("Fetching data for %s (%s)...", site_id, info["name"])
        try:
            raw = fetch_usgs_station_data(site_id, period_days=args.days)
            clean, meta = align_and_clean_usgs_series(raw)
            meta["description"] = info["description"]
            meta["record_count"] = len(clean)
            meta["start_time"] = clean[0]["timestamp"] if clean else "N/A"
            meta["end_time"] = clean[-1]["timestamp"] if clean else "N/A"

            save_dataset(out_dir, site_id, raw, clean, meta)
            stations_meta.append(meta)
        except Exception as e:
            logger.error("Failed to fetch data for station %s: %s", site_id, e)

    if stations_meta:
        write_readme(out_dir, stations_meta)
        logger.info("Successfully ingested real-world datasets.")
        return 0

    logger.error("No stations could be fetched.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
