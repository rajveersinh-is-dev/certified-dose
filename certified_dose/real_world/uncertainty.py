from __future__ import annotations

from dataclasses import dataclass

from certified_dose.intervals import Interval
from certified_dose.real_world.models import RealWorldRecord


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
