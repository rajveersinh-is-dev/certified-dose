"""Tests for sensor uncertainty models, including piecewise EPA Method 180.1 tiered bounds."""

import pytest

from certified_dose.real_world import (
    InstrumentUncertaintySpecs,
    RealWorldRecord,
    TurbidityUncertaintyModel,
    derive_disturbance_intervals,
)


class TestTurbidityUncertaintyModels:
    """Tests verifying proportional vs piecewise turbidity uncertainty intervals."""

    def _make_record(self, turbidity: float) -> RealWorldRecord:
        return RealWorldRecord(
            timestamp="2024-06-01T12:00:00Z",
            turbidity_ntu=turbidity,
            flow_cfs=1000.0,
            ph=7.2,
            temperature_c=18.0,
        )

    def test_proportional_model_default(self) -> None:
        """Default proportional model applies +/-10% (or +/-0.5 NTU floor)."""
        specs = InstrumentUncertaintySpecs(
            turbidity_model=TurbidityUncertaintyModel.PROPORTIONAL_10PCT
        )

        # Low turbidity: 0.50 NTU floor dominates when 10% of 2.0 = 0.2 < 0.50
        rec_low = self._make_record(2.0)
        dist_low = derive_disturbance_intervals(rec_low, specs=specs)
        assert pytest.approx(dist_low["turbidity"].lo, rel=1e-3) == 1.50
        assert pytest.approx(dist_low["turbidity"].hi, rel=1e-3) == 2.50

        # Mid turbidity: 10% of 50.0 = 5.0 NTU
        rec_mid = self._make_record(50.0)
        dist_mid = derive_disturbance_intervals(rec_mid, specs=specs)
        assert pytest.approx(dist_mid["turbidity"].lo, rel=1e-3) == 45.0
        assert pytest.approx(dist_mid["turbidity"].hi, rel=1e-3) == 55.0

        # High turbidity: 10% of 200.0 = 20.0 NTU
        rec_high = self._make_record(200.0)
        dist_high = derive_disturbance_intervals(rec_high, specs=specs)
        assert pytest.approx(dist_high["turbidity"].lo, rel=1e-3) == 180.0
        assert pytest.approx(dist_high["turbidity"].hi, rel=1e-3) == 220.0

    def test_piecewise_epa_range_model(self) -> None:
        """Piecewise tiered model applies 5% (T <= 40), 10% (40 < T <= 100), 15% (T > 100)."""
        specs = InstrumentUncertaintySpecs(
            turbidity_model=TurbidityUncertaintyModel.PIECEWISE_EPA_RANGE
        )

        # Tier 1: T <= 40 NTU -> 5% of reading
        # For T = 20.0 NTU: 5% of 20 = 1.0 NTU (> 0.50 floor)
        rec_t1 = self._make_record(20.0)
        dist_t1 = derive_disturbance_intervals(rec_t1, specs=specs)
        assert pytest.approx(dist_t1["turbidity"].lo, rel=1e-3) == 19.0
        assert pytest.approx(dist_t1["turbidity"].hi, rel=1e-3) == 21.0

        # Tier 1 floor test: T = 2.0 NTU -> 5% is 0.10, floor 0.50 dominates
        rec_floor = self._make_record(2.0)
        dist_floor = derive_disturbance_intervals(rec_floor, specs=specs)
        assert pytest.approx(dist_floor["turbidity"].lo, rel=1e-3) == 1.50
        assert pytest.approx(dist_floor["turbidity"].hi, rel=1e-3) == 2.50

        # Boundary T = 40.0: 5% of 40 = 2.0 NTU
        rec_40 = self._make_record(40.0)
        dist_40 = derive_disturbance_intervals(rec_40, specs=specs)
        assert pytest.approx(dist_40["turbidity"].lo, rel=1e-3) == 38.0
        assert pytest.approx(dist_40["turbidity"].hi, rel=1e-3) == 42.0

        # Tier 2: 40 < T <= 100 NTU -> 10% of reading
        # For T = 60.0 NTU: 10% of 60 = 6.0 NTU
        rec_t2 = self._make_record(60.0)
        dist_t2 = derive_disturbance_intervals(rec_t2, specs=specs)
        assert pytest.approx(dist_t2["turbidity"].lo, rel=1e-3) == 54.0
        assert pytest.approx(dist_t2["turbidity"].hi, rel=1e-3) == 66.0

        # Boundary T = 100.0: 10% of 100 = 10.0 NTU
        rec_100 = self._make_record(100.0)
        dist_100 = derive_disturbance_intervals(rec_100, specs=specs)
        assert pytest.approx(dist_100["turbidity"].lo, rel=1e-3) == 90.0
        assert pytest.approx(dist_100["turbidity"].hi, rel=1e-3) == 110.0

        # Tier 3: T > 100 NTU -> 15% of reading (multiple scattering)
        # For T = 200.0 NTU: 15% of 200 = 30.0 NTU
        rec_t3 = self._make_record(200.0)
        dist_t3 = derive_disturbance_intervals(rec_t3, specs=specs)
        assert pytest.approx(dist_t3["turbidity"].lo, rel=1e-3) == 170.0
        assert pytest.approx(dist_t3["turbidity"].hi, rel=1e-3) == 230.0
