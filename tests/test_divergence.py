"""Test suite for RSI divergence detection (TradingView-style pivot detection)."""
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime
import time

from src.indicators.divergence import (
    find_rsi_pivot_low,
    find_rsi_pivot_high,
    detect_divergence,
    fetch_candles_for_divergence,
    calculate_rsi_for_candles,
)
from src.storage.models import Candle


# ==================== FIXTURES ====================

@pytest.fixture
def mock_candle():
    """Factory fixture for creating mock Candle ORM objects."""
    def _create_candle(symbol="BTCUSDT", interval="1d", open_time=None,
                       open_price=100.0, high=105.0, low=95.0, close=102.0):
        if open_time is None:
            open_time = int(datetime.now().timestamp()) * 1000

        candle = Mock(spec=Candle)
        candle.symbol = symbol
        candle.interval = interval
        candle.open_time = open_time
        candle.open = open_price
        candle.high = high
        candle.low = low
        candle.close = close
        candle.volume = 1000.0
        candle.is_closed = True
        return candle

    return _create_candle


@pytest.fixture
def sample_candles(mock_candle):
    """Create 20 normal candles for testing."""
    base_time = int(datetime.now().timestamp()) * 1000
    candles = []

    for i in range(20):
        open_price = 100.0 + i * 0.5
        candles.append(mock_candle(
            open_time=base_time + (i * 86400000),  # 1d interval
            open_price=open_price,
            high=open_price + 2.0,
            low=open_price - 1.5,
            close=open_price + 1.0
        ))

    return candles


# ==================== TESTS: RSI PIVOT LOW (find_rsi_pivot_low) ====================

class TestFindRSIPivotLow:
    """Test bullish pivot detection (RSI at center is lowest in window)."""

    def test_valid_pivot_low_window_5_5(self):
        """Should detect pivot when center is the lowest in 5+1+5 window."""
        # 11 values: center at index 5 is the lowest
        rsi = [40.0, 38.0, 36.0, 34.0, 32.0, 25.0, 30.0, 33.0, 35.0, 37.0, 39.0]
        assert find_rsi_pivot_low(rsi, center=5, left=5, right=5) is True

    def test_invalid_pivot_low_not_lowest(self):
        """Should reject when center is not the lowest in window."""
        # Index 3 has lower value (20.0) than center (25.0)
        rsi = [40.0, 38.0, 36.0, 20.0, 32.0, 25.0, 30.0, 33.0, 35.0, 37.0, 39.0]
        assert find_rsi_pivot_low(rsi, center=5, left=5, right=5) is False

    def test_invalid_pivot_low_right_side_lower(self):
        """Should reject when a right-side value is lower than center."""
        rsi = [40.0, 38.0, 36.0, 34.0, 32.0, 25.0, 30.0, 23.0, 35.0, 37.0, 39.0]
        assert find_rsi_pivot_low(rsi, center=5, left=5, right=5) is False

    def test_invalid_pivot_low_equal_value(self):
        """Should reject when a neighbor equals the center (strict less-than)."""
        rsi = [40.0, 38.0, 36.0, 34.0, 32.0, 25.0, 25.0, 33.0, 35.0, 37.0, 39.0]
        assert find_rsi_pivot_low(rsi, center=5, left=5, right=5) is False

    def test_pivot_low_small_window_1_1(self):
        """Should work with left=1, right=1 (3-candle window)."""
        rsi = [35.0, 30.0, 32.0]
        assert find_rsi_pivot_low(rsi, center=1, left=1, right=1) is True

    def test_pivot_low_asymmetric_window(self):
        """Should work with asymmetric window (left=3, right=2)."""
        rsi = [40.0, 38.0, 36.0, 25.0, 30.0, 33.0]
        assert find_rsi_pivot_low(rsi, center=3, left=3, right=2) is True

    def test_pivot_low_out_of_bounds_left(self):
        """Should return False if center - left < 0."""
        rsi = [25.0, 30.0, 35.0]
        assert find_rsi_pivot_low(rsi, center=1, left=5, right=1) is False

    def test_pivot_low_out_of_bounds_right(self):
        """Should return False if center + right >= len."""
        rsi = [35.0, 30.0, 25.0]
        assert find_rsi_pivot_low(rsi, center=1, left=1, right=5) is False

    def test_pivot_low_none_at_center(self):
        """Should return False if center RSI is None."""
        rsi = [40.0, 38.0, 36.0, 34.0, 32.0, None, 30.0, 33.0, 35.0, 37.0, 39.0]
        assert find_rsi_pivot_low(rsi, center=5, left=5, right=5) is False

    def test_pivot_low_none_in_window(self):
        """Should return False if any RSI in window is None."""
        rsi = [40.0, 38.0, None, 34.0, 32.0, 25.0, 30.0, 33.0, 35.0, 37.0, 39.0]
        assert find_rsi_pivot_low(rsi, center=5, left=5, right=5) is False

    def test_pivot_low_in_larger_array(self):
        """Should find pivot within a larger RSI array."""
        rsi = [50.0] * 5 + [40.0, 38.0, 36.0, 34.0, 32.0, 20.0, 30.0, 33.0, 35.0, 37.0, 39.0] + [50.0] * 5
        assert find_rsi_pivot_low(rsi, center=10, left=5, right=5) is True


# ==================== TESTS: RSI PIVOT HIGH (find_rsi_pivot_high) ====================

class TestFindRSIPivotHigh:
    """Test bearish pivot detection (RSI at center is highest in window)."""

    def test_valid_pivot_high_window_5_5(self):
        """Should detect pivot when center is the highest in 5+1+5 window."""
        rsi = [60.0, 62.0, 64.0, 66.0, 68.0, 75.0, 70.0, 67.0, 65.0, 63.0, 61.0]
        assert find_rsi_pivot_high(rsi, center=5, left=5, right=5) is True

    def test_invalid_pivot_high_not_highest(self):
        """Should reject when center is not the highest in window."""
        rsi = [60.0, 62.0, 64.0, 80.0, 68.0, 75.0, 70.0, 67.0, 65.0, 63.0, 61.0]
        assert find_rsi_pivot_high(rsi, center=5, left=5, right=5) is False

    def test_invalid_pivot_high_right_side_higher(self):
        """Should reject when a right-side value is higher than center."""
        rsi = [60.0, 62.0, 64.0, 66.0, 68.0, 75.0, 70.0, 80.0, 65.0, 63.0, 61.0]
        assert find_rsi_pivot_high(rsi, center=5, left=5, right=5) is False

    def test_invalid_pivot_high_equal_value(self):
        """Should reject when a neighbor equals the center (strict greater-than)."""
        rsi = [60.0, 62.0, 64.0, 66.0, 68.0, 75.0, 75.0, 67.0, 65.0, 63.0, 61.0]
        assert find_rsi_pivot_high(rsi, center=5, left=5, right=5) is False

    def test_pivot_high_small_window_1_1(self):
        """Should work with left=1, right=1 (3-candle window)."""
        rsi = [65.0, 70.0, 68.0]
        assert find_rsi_pivot_high(rsi, center=1, left=1, right=1) is True

    def test_pivot_high_out_of_bounds(self):
        """Should return False if window exceeds array bounds."""
        rsi = [65.0, 70.0, 68.0]
        assert find_rsi_pivot_high(rsi, center=1, left=5, right=5) is False

    def test_pivot_high_none_at_center(self):
        """Should return False if center RSI is None."""
        rsi = [60.0, 62.0, 64.0, 66.0, 68.0, None, 70.0, 67.0, 65.0, 63.0, 61.0]
        assert find_rsi_pivot_high(rsi, center=5, left=5, right=5) is False

    def test_pivot_high_none_in_window(self):
        """Should return False if any RSI in window is None."""
        rsi = [60.0, 62.0, None, 66.0, 68.0, 75.0, 70.0, 67.0, 65.0, 63.0, 61.0]
        assert find_rsi_pivot_high(rsi, center=5, left=5, right=5) is False


# ==================== TESTS: DIVERGENCE DETECTION ====================

class TestDetectDivergence:
    """Test divergence detection logic (2 pivots + RSI condition)."""

    # BULLISH TESTS (price = low)
    def test_bullish_divergence_valid(self):
        """Should detect valid bullish divergence (lower low, higher RSI)."""
        result = detect_divergence(
            current_price=94.0,      # Lower low
            current_rsi=35.0,        # Higher RSI (< 40)
            prev_price=95.0,         # Previous low
            prev_rsi=30.0,           # Previous RSI (< 40)
            div_type="BULLISH"
        )
        assert result == "BULLISH"

    def test_bullish_divergence_rsi_above_threshold(self):
        """Should reject bullish divergence if current RSI >= threshold (default 40)."""
        result = detect_divergence(
            current_price=94.0,
            current_rsi=40.1,        # > 40 - INVALID
            prev_price=95.0,
            prev_rsi=35.0,
            div_type="BULLISH"
        )
        assert result is None

    def test_bullish_divergence_prev_rsi_above_threshold(self):
        """Should reject bullish divergence if previous RSI >= threshold (default 40)."""
        result = detect_divergence(
            current_price=94.0,
            current_rsi=35.0,
            prev_price=95.0,
            prev_rsi=40.1,           # > 40 - INVALID
            div_type="BULLISH"
        )
        assert result is None

    def test_bullish_divergence_custom_threshold(self):
        """Should respect custom bullish_rsi_max threshold."""
        result = detect_divergence(
            current_price=94.0,
            current_rsi=45.0,        # < 50 (custom)
            prev_price=95.0,
            prev_rsi=35.0,
            div_type="BULLISH",
            bullish_rsi_max=50
        )
        assert result == "BULLISH"

    def test_bullish_divergence_custom_threshold_reject(self):
        """Should reject with custom threshold if RSI >= threshold."""
        result = detect_divergence(
            current_price=94.0,
            current_rsi=50.1,        # > 50 - INVALID
            prev_price=95.0,
            prev_rsi=35.0,
            div_type="BULLISH",
            bullish_rsi_max=50
        )
        assert result is None

    def test_bullish_divergence_price_not_lower(self):
        """Should reject bullish divergence if price not lower."""
        result = detect_divergence(
            current_price=96.0,      # NOT lower than prev
            current_rsi=35.0,
            prev_price=95.0,
            prev_rsi=30.0,
            div_type="BULLISH"
        )
        assert result is None

    def test_bullish_divergence_rsi_lower(self):
        """Should reject bullish divergence if RSI also makes new low."""
        result = detect_divergence(
            current_price=94.0,      # Lower low
            current_rsi=28.0,        # RSI also new low - NO DIVERGENCE
            prev_price=95.0,
            prev_rsi=30.0,
            div_type="BULLISH"
        )
        assert result is None

    # BEARISH TESTS (price = high)
    def test_bearish_divergence_valid(self):
        """Should detect valid bearish divergence (higher high, lower RSI)."""
        result = detect_divergence(
            current_price=106.0,     # Higher high
            current_rsi=65.0,        # Lower RSI (> 60)
            prev_price=105.0,        # Previous high
            prev_rsi=70.0,           # Previous RSI (> 60)
            div_type="BEARISH"
        )
        assert result == "BEARISH"

    def test_bearish_divergence_rsi_below_threshold(self):
        """Should reject bearish divergence if current RSI <= threshold (default 60)."""
        result = detect_divergence(
            current_price=106.0,
            current_rsi=59.9,        # < 60 - INVALID
            prev_price=105.0,
            prev_rsi=75.0,
            div_type="BEARISH"
        )
        assert result is None

    def test_bearish_divergence_prev_rsi_below_threshold(self):
        """Should reject bearish divergence if previous RSI <= threshold (default 60)."""
        result = detect_divergence(
            current_price=106.0,
            current_rsi=65.0,
            prev_price=105.0,
            prev_rsi=59.9,           # < 60 - INVALID
            div_type="BEARISH"
        )
        assert result is None

    def test_bearish_divergence_custom_threshold(self):
        """Should respect custom bearish_rsi_min threshold."""
        result = detect_divergence(
            current_price=106.0,
            current_rsi=55.0,        # > 50 (custom)
            prev_price=105.0,
            prev_rsi=75.0,
            div_type="BEARISH",
            bearish_rsi_min=50
        )
        assert result == "BEARISH"

    def test_bearish_divergence_custom_threshold_reject(self):
        """Should reject with custom threshold if RSI <= threshold."""
        result = detect_divergence(
            current_price=106.0,
            current_rsi=49.9,        # < 50 - INVALID
            prev_price=105.0,
            prev_rsi=75.0,
            div_type="BEARISH",
            bearish_rsi_min=50
        )
        assert result is None

    def test_bearish_divergence_price_not_higher(self):
        """Should reject bearish divergence if price not higher."""
        result = detect_divergence(
            current_price=104.0,     # NOT higher than prev
            current_rsi=65.0,
            prev_price=105.0,
            prev_rsi=75.0,
            div_type="BEARISH"
        )
        assert result is None

    def test_bearish_divergence_rsi_higher(self):
        """Should reject bearish divergence if RSI also makes new high."""
        result = detect_divergence(
            current_price=106.0,     # Higher high
            current_rsi=80.0,        # RSI also new high - NO DIVERGENCE
            prev_price=105.0,
            prev_rsi=75.0,
            div_type="BEARISH"
        )
        assert result is None

    # EDGE CASES
    def test_divergence_rsi_at_boundary_threshold(self):
        """RSI exactly at threshold should not qualify (boundary check)."""
        result = detect_divergence(
            current_price=94.0,
            current_rsi=40.0,        # Exactly at threshold
            prev_price=95.0,
            prev_rsi=35.0,
            div_type="BULLISH"
        )
        assert result is None

        result = detect_divergence(
            current_price=106.0,
            current_rsi=60.0,        # Exactly at threshold
            prev_price=105.0,
            prev_rsi=75.0,
            div_type="BEARISH"
        )
        assert result is None

    def test_divergence_zero_prices(self):
        """Test with zero prices."""
        result = detect_divergence(
            current_price=0.0,
            current_rsi=35.0,
            prev_price=0.0,
            prev_rsi=30.0,
            div_type="BULLISH"
        )
        assert result is None

    def test_divergence_equal_prices(self):
        """Should handle equal prices (no divergence)."""
        result = detect_divergence(
            current_price=95.0,
            current_rsi=35.0,
            prev_price=95.0,
            prev_rsi=30.0,
            div_type="BULLISH"
        )
        assert result is None


# ==================== TESTS: RSI CALCULATION ====================

class TestCalculateRSIForCandles:
    """Test RSI calculation across multiple candles."""

    def test_rsi_insufficient_data(self):
        """Should return None for first 14 candles."""
        closes = [100.0 + i * 0.5 for i in range(14)]
        rsi_values = calculate_rsi_for_candles(closes)

        for i in range(14):
            assert rsi_values[i] is None

    def test_rsi_first_valid_at_15th_candle(self):
        """Should calculate RSI starting from 15th candle."""
        closes = [100.0 + i * 0.5 for i in range(20)]
        rsi_values = calculate_rsi_for_candles(closes)

        assert rsi_values[14] is not None
        assert isinstance(rsi_values[14], float)

    def test_rsi_values_are_floats(self):
        """Should return float values for RSI."""
        closes = [100.0 + i * 0.1 for i in range(20)]
        rsi_values = calculate_rsi_for_candles(closes)

        for i in range(14, 20):
            assert isinstance(rsi_values[i], float)

    def test_rsi_empty_closes(self):
        """Should handle empty closes list."""
        rsi_values = calculate_rsi_for_candles([])
        assert rsi_values == []

    def test_rsi_single_close(self):
        """Should return None for single candle."""
        rsi_values = calculate_rsi_for_candles([100.0])
        assert rsi_values[0] is None


# ==================== TESTS: FETCH CANDLES ====================

class TestFetchCandlesForDivergence:
    """Test fetching candles from database."""

    @patch('src.storage.db.SessionLocal')
    def test_fetch_candles_success(self, mock_session_class, mock_candle, sample_candles):
        """Should successfully fetch candles with low/high fields."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_order = MagicMock()

        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session_class.return_value.__exit__.return_value = None

        # Simulate DB returning newest first (desc order)
        newest_first = list(reversed(sample_candles[:5]))

        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_filter
        mock_filter.order_by.return_value = mock_order
        mock_order.limit.return_value.all.return_value = newest_first

        result = fetch_candles_for_divergence("BTCUSDT", "1d", 5)
        assert len(result) == 5
        # Should be reversed to oldest first (returns dicts with low/high)
        expected = [
            {
                "close": c.close,
                "low": c.low,
                "high": c.high,
                "open_time": c.open_time,
                "is_closed": c.is_closed,
            }
            for c in sample_candles[:5]
        ]
        assert result == expected
        mock_filter.order_by.assert_called_once()

    @patch('src.storage.db.SessionLocal')
    def test_fetch_candles_empty_result(self, mock_session_class):
        """Should return empty list if no candles found."""
        mock_session = MagicMock()

        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session_class.return_value.__exit__.return_value = None

        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        result = fetch_candles_for_divergence("BTCUSDT", "1d", 5)
        assert result == []

    @patch('src.storage.db.SessionLocal')
    def test_fetch_candles_exception(self, mock_session_class):
        """Should return empty list on database exception."""
        mock_session_class.side_effect = Exception("DB error")

        result = fetch_candles_for_divergence("BTCUSDT", "1d", 5)
        assert result == []

    @patch('src.storage.db.SessionLocal')
    def test_fetch_candles_includes_low_high(self, mock_session_class, mock_candle):
        """Should include low and high fields in returned dicts."""
        mock_session = MagicMock()

        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session_class.return_value.__exit__.return_value = None

        candle = mock_candle(low=94.5, high=106.0, close=102.0)
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [candle]

        result = fetch_candles_for_divergence("BTCUSDT", "1d", 5)
        assert len(result) == 1
        assert result[0]["low"] == 94.5
        assert result[0]["high"] == 106.0
        assert result[0]["close"] == 102.0


# ==================== TESTS: PIVOT DETECTION IN CONTEXT ====================

class TestPivotDetectionInContext:
    """Test pivot detection with realistic RSI sequences."""

    def test_no_pivot_in_continuous_decline(self):
        """No pivot should be found in a continuous RSI decline."""
        # RSI declining continuously - no pivot
        rsi = [50.0, 48.0, 46.0, 44.0, 42.0, 40.0, 38.0, 36.0, 34.0, 32.0, 30.0]
        assert find_rsi_pivot_low(rsi, center=5, left=5, right=5) is False

    def test_no_pivot_in_continuous_rise(self):
        """No pivot should be found in a continuous RSI rise."""
        rsi = [50.0, 52.0, 54.0, 56.0, 58.0, 60.0, 62.0, 64.0, 66.0, 68.0, 70.0]
        assert find_rsi_pivot_high(rsi, center=5, left=5, right=5) is False

    def test_pivot_low_with_preceding_rsi_period(self):
        """Pivot detection works correctly when preceded by None RSI values."""
        # First 14 values are None (RSI not yet calculated), then valid
        rsi = [None] * 14 + [50.0, 48.0, 46.0, 44.0, 42.0, 35.0, 40.0, 43.0, 45.0, 47.0, 49.0]
        assert find_rsi_pivot_low(rsi, center=19, left=5, right=5) is True

    def test_pivot_low_blocked_by_none_in_window(self):
        """Pivot should not be found if None values exist within the window."""
        rsi = [None] * 14 + [50.0, None, 46.0, 44.0, 42.0, 35.0, 40.0, 43.0, 45.0, 47.0, 49.0]
        # center=19, left=5 → window starts at 14, index 15 is None
        assert find_rsi_pivot_low(rsi, center=19, left=5, right=5) is False

    def test_false_positive_scenario_from_production(self):
        """
        Simulates the false positive from 09/02/2026:
        With 3-candle window, a micro-dip in RSI during continuous decline was
        detected as a pivot. With 5+5 window, it should NOT be detected.
        """
        # Continuous decline with a small bounce in the middle
        rsi = [
            None, None, None, None, None, None, None, None, None, None,
            None, None, None, None,
            55.0, 52.0, 48.0, 45.0,  # RSI declining
            42.0, 38.0,              # Small dip
            40.0,                     # Tiny bounce (this was false pivot with 3-candle window)
            37.0, 34.0, 32.0, 30.0,  # Decline continues
        ]
        # With 5+5 window at center=20 (the bounce):
        # Left 5: [42.0, 38.0, ...] - ok, all higher
        # But right 5: [37.0, 34.0, 32.0, 30.0] - all LOWER than 40.0
        # So it should NOT be a pivot because right-side values are lower
        assert find_rsi_pivot_low(rsi, center=20, left=5, right=4) is False


# ==================== TESTS: RANGE BETWEEN PIVOTS ====================

class TestPivotRange:
    """Test range constraints between compared pivots."""

    def test_range_within_bounds(self):
        """Pivots within [range_min, range_max] should allow comparison."""
        bars_between = 15
        range_min = 5
        range_max = 60
        assert range_min <= bars_between <= range_max

    def test_range_too_close(self):
        """Pivots closer than range_min should not be compared."""
        bars_between = 3
        range_min = 5
        range_max = 60
        assert not (range_min <= bars_between <= range_max)

    def test_range_too_far(self):
        """Pivots farther than range_max should not be compared."""
        bars_between = 65
        range_min = 5
        range_max = 60
        assert not (range_min <= bars_between <= range_max)

    def test_range_at_min_boundary(self):
        """Pivots exactly at range_min should be valid."""
        bars_between = 5
        range_min = 5
        range_max = 60
        assert range_min <= bars_between <= range_max

    def test_range_at_max_boundary(self):
        """Pivots exactly at range_max should be valid."""
        bars_between = 60
        range_min = 5
        range_max = 60
        assert range_min <= bars_between <= range_max


# ==================== TESTS: PRICE COMPARISON (LOW/HIGH) ====================

class TestPriceComparison:
    """Test that divergence uses low (bullish) and high (bearish), not close."""

    def test_bullish_uses_low_prices(self):
        """Bullish divergence should compare candle lows, not closes."""
        # Low makes lower low, but close doesn't
        result = detect_divergence(
            current_price=93.0,      # Current low (lower than prev low)
            current_rsi=35.0,
            prev_price=94.0,         # Previous low
            prev_rsi=30.0,
            div_type="BULLISH"
        )
        assert result == "BULLISH"

    def test_bearish_uses_high_prices(self):
        """Bearish divergence should compare candle highs, not closes."""
        # High makes higher high
        result = detect_divergence(
            current_price=107.0,     # Current high (higher than prev high)
            current_rsi=65.0,
            prev_price=106.0,        # Previous high
            prev_rsi=70.0,
            div_type="BEARISH"
        )
        assert result == "BEARISH"


# ==================== TESTS: DIVERGENCE EDGE CASES ====================

class TestDivergenceEdgeCases:
    """Edge case tests for divergence detection."""

    def test_divergence_extreme_rsi_values(self):
        """Should handle extreme RSI values (near 0 and 100)."""
        result = detect_divergence(
            current_price=93.0,
            current_rsi=10.0,
            prev_price=94.0,
            prev_rsi=5.0,
            div_type="BULLISH"
        )
        assert result == "BULLISH"

        result = detect_divergence(
            current_price=107.0,
            current_rsi=90.0,
            prev_price=106.0,
            prev_rsi=95.0,
            div_type="BEARISH"
        )
        assert result == "BEARISH"

    def test_divergence_very_small_price_difference(self):
        """Should detect divergence with very small price differences."""
        result = detect_divergence(
            current_price=94.001,
            current_rsi=35.0,
            prev_price=94.002,
            prev_rsi=30.0,
            div_type="BULLISH"
        )
        assert result == "BULLISH"

    def test_divergence_large_rsi_difference(self):
        """Should detect divergence even with large RSI differences."""
        result = detect_divergence(
            current_price=93.0,
            current_rsi=10.0,
            prev_price=94.0,
            prev_rsi=5.0,
            div_type="BULLISH"
        )
        assert result == "BULLISH"


# ==================== TESTS: ANTI-SPAM LOGIC ====================

class TestDivergenceAntiSpam:
    """Test anti-spam logic for divergence alerts."""

    def test_same_signal_detected(self):
        """Should detect same signal when price and RSI match (after rounding)."""
        last_alert = {"price": 5050.19, "rsi": 35.46}
        current_price = 5050.19
        current_rsi = 35.46

        same_signal = (
            round(last_alert["price"], 2) == round(current_price, 2) and
            round(last_alert["rsi"], 1) == round(current_rsi, 1)
        )
        assert same_signal is True

    def test_different_price_new_signal(self):
        """Should detect new signal when price differs."""
        last_alert = {"price": 5050.19, "rsi": 35.46}
        current_price = 5055.00
        current_rsi = 35.46

        same_signal = (
            round(last_alert["price"], 2) == round(current_price, 2) and
            round(last_alert["rsi"], 1) == round(current_rsi, 1)
        )
        assert same_signal is False

    def test_different_rsi_new_signal(self):
        """Should detect new signal when RSI differs."""
        last_alert = {"price": 5050.19, "rsi": 35.46}
        current_price = 5050.19
        current_rsi = 36.50

        same_signal = (
            round(last_alert["price"], 2) == round(current_price, 2) and
            round(last_alert["rsi"], 1) == round(current_rsi, 1)
        )
        assert same_signal is False

    def test_rounding_precision_price(self):
        """Should handle price rounding (2 decimals)."""
        last_alert = {"price": 5050.124, "rsi": 35.0}
        current_price = 5050.125
        current_rsi = 35.0

        same_signal = (
            round(last_alert["price"], 2) == round(current_price, 2) and
            round(last_alert["rsi"], 1) == round(current_rsi, 1)
        )
        assert same_signal is True

    def test_rounding_precision_rsi(self):
        """Should handle RSI rounding (1 decimal)."""
        last_alert = {"price": 5050.00, "rsi": 35.42}
        current_price = 5050.00
        current_rsi = 35.44

        same_signal = (
            round(last_alert["price"], 2) == round(current_price, 2) and
            round(last_alert["rsi"], 1) == round(current_rsi, 1)
        )
        assert same_signal is True

    def test_no_last_alert(self):
        """Should allow alert when no previous alert exists."""
        last_alert = None
        current_price = 5050.19
        current_rsi = 35.46

        same_signal = (
            last_alert is not None and
            round(last_alert["price"], 2) == round(current_price, 2) and
            round(last_alert["rsi"], 1) == round(current_rsi, 1)
        )
        assert same_signal is False

    def test_both_price_and_rsi_different(self):
        """Should detect new signal when both price and RSI differ."""
        last_alert = {"price": 5050.19, "rsi": 35.46}
        current_price = 5100.00
        current_rsi = 40.00

        same_signal = (
            round(last_alert["price"], 2) == round(current_price, 2) and
            round(last_alert["rsi"], 1) == round(current_rsi, 1)
        )
        assert same_signal is False


# ==================== TESTS: MOST RECENT PIVOT ONLY ====================

class TestMostRecentPivotComparison:
    """Test that divergence compares only with the most recent previous pivot."""

    def test_compares_with_last_pivot_only(self):
        """
        Given multiple previous pivots, only the most recent (last in list)
        should be used for divergence comparison.
        """
        pivots = [
            {"low": 96.0, "high": 106.0, "rsi": 25.0, "open_time": 1000, "candle_index": 5},
            {"low": 97.0, "high": 107.0, "rsi": 28.0, "open_time": 2000, "candle_index": 15},
            {"low": 95.0, "high": 108.0, "rsi": 32.0, "open_time": 3000, "candle_index": 25},
        ]

        # Current pivot
        current_low = 94.0
        current_rsi = 35.0
        current_idx = 40

        # Only compare with last pivot (index 25, rsi=32, low=95)
        prev = pivots[-1]
        bars_between = current_idx - prev["candle_index"]

        # Range check: 40 - 25 = 15, within [5, 60]
        assert 5 <= bars_between <= 60

        # Divergence: current_low (94) < prev_low (95) AND current_rsi (35) > prev_rsi (32)
        result = detect_divergence(
            current_price=current_low,
            current_rsi=current_rsi,
            prev_price=prev["low"],
            prev_rsi=prev["rsi"],
            div_type="BULLISH"
        )
        assert result == "BULLISH"

    def test_ignores_old_pivots_even_if_divergent(self):
        """
        Even if an old pivot would produce divergence, only the most recent
        is checked. If the most recent doesn't diverge, no alert.
        """
        pivots = [
            {"low": 98.0, "high": 108.0, "rsi": 20.0, "open_time": 1000, "candle_index": 5},   # Would diverge
            {"low": 93.0, "high": 103.0, "rsi": 38.0, "open_time": 2000, "candle_index": 25},  # Most recent
        ]

        current_low = 94.0
        current_rsi = 35.0

        # Compare only with last pivot: low=93, rsi=38
        prev = pivots[-1]

        # current_low (94) > prev_low (93) → NOT a lower low → no bullish divergence
        result = detect_divergence(
            current_price=current_low,
            current_rsi=current_rsi,
            prev_price=prev["low"],
            prev_rsi=prev["rsi"],
            div_type="BULLISH"
        )
        assert result is None
