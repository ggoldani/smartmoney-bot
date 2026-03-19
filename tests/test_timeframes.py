"""Tests for timeframe utility functions."""
import pytest
from src.utils.timeframes import interval_to_ms, INTERVAL_MS


class TestIntervalToMs:
    """Tests for interval_to_ms function."""

    def test_interval_to_ms_valid(self):
        """Verify all supported intervals return correct millisecond durations."""
        for interval, expected_ms in INTERVAL_MS.items():
            assert interval_to_ms(interval) == expected_ms

    @pytest.mark.parametrize("invalid_interval", [
        "1s",
        "invalid",
        "",
        "1y",
        "99m"
    ])
    def test_interval_to_ms_invalid(self, invalid_interval):
        """Verify unknown intervals raise ValueError with correct message."""
        with pytest.raises(ValueError) as excinfo:
            interval_to_ms(invalid_interval)
        assert f"Unknown interval: {invalid_interval}" in str(excinfo.value)
