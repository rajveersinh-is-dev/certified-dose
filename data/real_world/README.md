# Real-World Water Quality Operational Telemetry Datasets

> **Provenance & Ingestion Log**: Fetched live via `scripts/fetch_real_world_data.py` on `2026-09-01 16:33:20 UTC`.

## 1. Overview & Provenance
These datasets provide real-world, high-frequency continuous operational sensor telemetry
collected by the **United States Geological Survey (USGS)** National Water Information System (NWIS).
They capture the actual physical source water quality conditions entering municipal drinking water plants.

### Included Stations:

### USGS Station `04193500`: Maumee River at Waterville OH
- **Station Name**: Maumee River at Waterville OH
- **Coordinates**: Latitude `41.5000526`, Longitude `-83.7127145`
- **Source Description**: Primary surface drinking water intake for Toledo Collins Park Water Treatment Plant
- **Source API URL**: `https://waterservices.usgs.gov/nwis/iv/?sites=04193500&parameterCd=00060,00010,00400,63680`
- **Sampling Frequency**: 15-minute continuous automated sensor records
- **Total Aligned Records**: 2,862
- **Date Range**: `2026-08-02T12:45:00.000-04:00` to `2026-09-01T12:00:00.000-04:00`
- **Parameters Included**:
  1. `turbidity_ntu` (USGS Parameter `63680`): Formazin Nephelometric Units (FNU / NTU), 780-900nm near-IR optical detection.
  2. `flow_cfs` (USGS Parameter `00060`): River streamflow / intake discharge in cubic feet per second ($ft^3/s$).
  3. `ph` (USGS Parameter `00400`): Field unfiltered pH (standard units).
  4. `temperature_c` (USGS Parameter `00010`): Water temperature in degrees Celsius ($^\circ$C).

### USGS Station `01184000`: CONNECTICUT RIVER AT THOMPSONVILLE, CT
- **Station Name**: CONNECTICUT RIVER AT THOMPSONVILLE, CT
- **Coordinates**: Latitude `41.98720462`, Longitude `-72.60534826`
- **Source Description**: Regional municipal drinking water intake and upland river watershed
- **Source API URL**: `https://waterservices.usgs.gov/nwis/iv/?sites=01184000&parameterCd=00060,00010,00400,63680`
- **Sampling Frequency**: 15-minute continuous automated sensor records
- **Total Aligned Records**: 2,865
- **Date Range**: `2026-08-02T12:45:00.000-04:00` to `2026-09-01T11:30:00.000-04:00`
- **Parameters Included**:
  1. `turbidity_ntu` (USGS Parameter `63680`): Formazin Nephelometric Units (FNU / NTU), 780-900nm near-IR optical detection.
  2. `flow_cfs` (USGS Parameter `00060`): River streamflow / intake discharge in cubic feet per second ($ft^3/s$).
  3. `ph` (USGS Parameter `00400`): Field unfiltered pH (standard units).
  4. `temperature_c` (USGS Parameter `00010`): Water temperature in degrees Celsius ($^\circ$C).

## 2. Licensing & Terms of Use
- **Publisher**: U.S. Geological Survey (USGS), U.S. Department of the Interior.
- **License**: **Public Domain** (U.S. Government Work). Unrestricted public access and distribution under 17 U.S.C. § 105.
- **Data Integrity Notice**: Raw sensor provisional data (`P` qualifier) may include sensor noise, diurnal algal fluctuations, calibration drift, and physical storm spikes.

## 3. Instrument Precision & Uncertainty Derivation
In `certified-dose`, point-in-time sensor readings are converted into bounded uncertainty intervals
derived from published instrumentation precision specifications (EPA Method 180.1 / ISO 7027):
- **Turbidity ($`T_{\text{in}}`$)**: Optical field fouling allowance of $\pm 10\%$ of reading or $\pm 0.5\text{ NTU}$ (whichever is larger).
- **pH**: Glass electrode liquid-junction and buffer drift of $\pm 0.15\text{ pH}$ units.
- **Temperature ($T$)**: Industrial thermistor tolerance of $\pm 0.5^\circ\text{C}$.
- **Relative Flow ($`Q/Q_{\text{nom}}`$)**: Intake flow meter tolerance of $\pm 5.0\%$.
