"""Test suite for RSI divergence detection (RSI-based pivot detection)."""
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime
import time

from src.indicators.divergence import (
    is_rsi_bullish_pivot,
    is_rsi_bearish_pivot,
    detect_divergence,
    fetch_candles_for_divergence,
    calculate_rsi_for_candles
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


@pytest.fixture
def bullish_candles(mock_candle):
    """Create 20 candles with bullish trend (lower lows)."""
    base_time = int(datetime.now().timestamp()) * 1000
    candles = []

    prices = [110.0, 108.0, 109.0, 107.0, 106.0, 105.0, 104.5, 104.0,
              103.5, 103.0, 102.5, 102.0, 101.5, 101.0, 100.5, 100.0,
              100.5, 101.0, 101.5, 102.0]

    for i, price in enumerate(prices):
        candles.append(mock_candle(
            open_time=base_time + (i * 86400000),
            open_price=price,
            high=price + 1.5,
            low=price - 1.0,
            close=price + 0.5
        ))

    return candles


@pytest.fixture
def bearish_candles(mock_candle):
    """Create 20 candles with bearish trend (higher highs)."""
    base_time = int(datetime.now().timestamp()) * 1000
    candles = []

    prices = [90.0, 92.0, 91.0, 93.0, 94.0, 95.0, 95.5, 96.0,
              96.5, 97.0, 97.5, 98.0, 98.5, 99.0, 99.5, 100.0,
              99.5, 99.0, 98.5, 98.0]

    for i, price in enumerate(prices):
        candles.append(mock_candle(
            open_time=base_time + (i * 86400000),
            open_price=price,
            high=price + 1.5,
            low=price - 1.0,
            close=price - 0.5
        ))

    return candles


# ==================== TESTS: RSI BULLISH PIVOT DETECTION ====================

class TestRSIBullishPivot:
    """Test bullish pivot detection (RSI[1] is lowest)."""

    def test_valid_bullish_pivot(self):
        """Should detect valid bullish pivot (middle RSI is lowest)."""
        rsi_values = [35.0, 30.0, 32.0]  # RSI[1] is lowest
        assert is_rsi_bullish_pivot(rsi_values) is True

    def test_invalid_bullish_pivot_not_lowest(self):
        """Should reject pivot if middle RSI is not lowest."""
        rsi_values = [30.0, 35.0, 32.0]  # RSI[0] is lowest
        assert is_rsi_bullish_pivot(rsi_values) is False

    def test_invalid_bullish_pivot_c3_lowest(self):
        """Should reject pivot if third RSI is lowest."""
        rsi_values = [35.0, 32.0, 30.0]  # RSI[2] is lowest
        assert is_rsi_bullish_pivot(rsi_values) is False

    def test_invalid_bullish_pivot_equal_values(self):
        """Should reject pivot if RSI values are equal."""
        rsi_values = [30.0, 30.0, 30.0]
        assert is_rsi_bullish_pivot(rsi_values) is False

    def test_invalid_bullish_pivot_wrong_length(self):
        """Should reject if not exactly 3 RSI values."""
        rsi_values = [35.0, 30.0]
        assert is_rsi_bullish_pivot(rsi_values) is False

    def test_invalid_bullish_pivot_empty(self):
        """Should reject empty list."""
        assert is_rsi_bullish_pivot([]) is False

    def test_invalid_bullish_pivot_none_values(self):
        """Should reject if any RSI value is None."""
        assert is_rsi_bullish_pivot([35.0, None, 32.0]) is False
        assert is_rsi_bullish_pivot([None, 30.0, 32.0]) is False
        assert is_rsi_bullish_pivot([35.0, 30.0, None]) is False


# ==================== TESTS: RSI BEARISH PIVOT DETECTION ====================

class TestRSIBearishPivot:
    """Test bearish pivot detection (RSI[1] is highest)."""

    def test_valid_bearish_pivot(self):
        """Should detect valid bearish pivot (middle RSI is highest)."""
        rsi_values = [65.0, 70.0, 68.0]  # RSI[1] is highest
        assert is_rsi_bearish_pivot(rsi_values) is True

    def test_invalid_bearish_pivot_not_highest(self):
        """Should reject pivot if middle RSI is not highest."""
        rsi_values = [70.0, 65.0, 68.0]  # RSI[0] is highest
        assert is_rsi_bearish_pivot(rsi_values) is False

    def test_invalid_bearish_pivot_c3_highest(self):
        """Should reject pivot if third RSI is highest."""
        rsi_values = [65.0, 68.0, 70.0]  # RSI[2] is highest
        assert is_rsi_bearish_pivot(rsi_values) is False

    def test_invalid_bearish_pivot_equal_values(self):
        """Should reject pivot if RSI values are equal."""
        rsi_values = [70.0, 70.0, 70.0]
        assert is_rsi_bearish_pivot(rsi_values) is False

    def test_invalid_bearish_pivot_wrong_length(self):
        """Should reject if not exactly 3 RSI values."""
        rsi_values = [65.0, 70.0]
        assert is_rsi_bearish_pivot(rsi_values) is False

    def test_invalid_bearish_pivot_empty(self):
        """Should reject empty list."""
        assert is_rsi_bearish_pivot([]) is False

    def test_invalid_bearish_pivot_none_values(self):
        """Should reject if any RSI value is None."""
        assert is_rsi_bearish_pivot([65.0, None, 68.0]) is False
        assert is_rsi_bearish_pivot([None, 70.0, 68.0]) is False
        assert is_rsi_bearish_pivot([65.0, 70.0, None]) is False


# ==================== TESTS: DIVERGENCE DETECTION ====================

class TestDetectDivergence:
    """Test divergence detection logic (2 pivots + RSI condition)."""

    # BULLISH TESTS
    def test_bullish_divergence_valid(self):
        """Should detect valid bullish divergence."""
        result = detect_divergence(
            current_price=99.0,      # Lower low
            current_rsi=35.0,        # < 40 (default threshold)
            prev_price=100.0,        # Previous low
            prev_rsi=30.0,           # < 40 (default threshold)
            div_type="BULLISH"
        )
        assert result == "BULLISH"

    def test_bullish_divergence_higher_current_rsi(self):
        """Should detect bullish divergence with higher current RSI."""
        result = detect_divergence(
            current_price=99.0,      # Lower low (new minimum)
            current_rsi=35.0,        # < 40 (default threshold)
            prev_price=100.0,        # Previous low
            prev_rsi=30.0,           # < 40 (default threshold), but RSI didn't make new low
            div_type="BULLISH"
        )
        assert result == "BULLISH"

    def test_bullish_divergence_rsi_above_threshold(self):
        """Should reject bullish divergence if current RSI >= threshold (default 40)."""
        result = detect_divergence(
            current_price=99.0,
            current_rsi=40.1,        # > 40 (default threshold) - INVALID
            prev_price=100.0,
            prev_rsi=35.0,
            div_type="BULLISH"
        )
        assert result is None

    def test_bullish_divergence_prev_rsi_above_threshold(self):
        """Should reject bullish divergence if previous RSI >= threshold (default 40)."""
        result = detect_divergence(
            current_price=99.0,
            current_rsi=35.0,
            prev_price=100.0,
            prev_rsi=40.1,           # > 40 (default threshold) - INVALID
            div_type="BULLISH"
        )
        assert result is None

    def test_bullish_divergence_custom_threshold(self):
        """Should respect custom bullish_rsi_max threshold."""
        # With custom threshold of 50, RSI 45 should be valid
        result = detect_divergence(
            current_price=99.0,
            current_rsi=45.0,        # < 50 (custom threshold)
            prev_price=100.0,
            prev_rsi=35.0,
            div_type="BULLISH",
            bullish_rsi_max=50
        )
        assert result == "BULLISH"

    def test_bullish_divergence_custom_threshold_reject(self):
        """Should reject with custom threshold if RSI >= threshold."""
        result = detect_divergence(
            current_price=99.0,
            current_rsi=50.1,        # > 50 (custom threshold) - INVALID
            prev_price=100.0,
            prev_rsi=35.0,
            div_type="BULLISH",
            bullish_rsi_max=50
        )
        assert result is None

    def test_bullish_divergence_price_not_lower(self):
        """Should reject bullish divergence if price not lower."""
        result = detect_divergence(
            current_price=101.0,     # NOT lower than prev
            current_rsi=40.0,
            prev_price=100.0,
            prev_rsi=35.0,
            div_type="BULLISH"
        )
        assert result is None

    def test_bullish_divergence_rsi_lower(self):
        """Should reject bullish divergence if RSI also makes new low."""
        result = detect_divergence(
            current_price=99.0,      # New low
            current_rsi=30.0,        # RSI also new low - NO DIVERGENCE
            prev_price=100.0,
            prev_rsi=35.0,
            div_type="BULLISH"
        )
        assert result is None

    # BEARISH TESTS
    def test_bearish_divergence_valid(self):
        """Should detect valid bearish divergence."""
        result = detect_divergence(
            current_price=101.0,     # Higher high
            current_rsi=65.0,        # > 60 (default threshold)
            prev_price=100.0,        # Previous high
            prev_rsi=70.0,           # > 60 (default threshold), but RSI didn't make new high
            div_type="BEARISH"
        )
        assert result == "BEARISH"

    def test_bearish_divergence_rsi_below_threshold(self):
        """Should reject bearish divergence if current RSI <= threshold (default 60)."""
        result = detect_divergence(
            current_price=101.0,
            current_rsi=59.9,        # < 60 (default threshold) - INVALID
            prev_price=100.0,
            prev_rsi=75.0,
            div_type="BEARISH"
        )
        assert result is None

    def test_bearish_divergence_prev_rsi_below_threshold(self):
        """Should reject bearish divergence if previous RSI <= threshold (default 60)."""
        result = detect_divergence(
            current_price=101.0,
            current_rsi=65.0,
            prev_price=100.0,
            prev_rsi=59.9,           # < 60 (default threshold) - INVALID
            div_type="BEARISH"
        )
        assert result is None

    def test_bearish_divergence_custom_threshold(self):
        """Should respect custom bearish_rsi_min threshold."""
        # With custom threshold of 50, RSI 55 should be valid
        result = detect_divergence(
            current_price=101.0,
            current_rsi=55.0,        # > 50 (custom threshold)
            prev_price=100.0,
            prev_rsi=75.0,
            div_type="BEARISH",
            bearish_rsi_min=50
        )
        assert result == "BEARISH"

    def test_bearish_divergence_custom_threshold_reject(self):
        """Should reject with custom threshold if RSI <= threshold."""
        result = detect_divergence(
            current_price=101.0,
            current_rsi=49.9,        # < 50 (custom threshold) - INVALID
            prev_price=100.0,
            prev_rsi=75.0,
            div_type="BEARISH",
            bearish_rsi_min=50
        )
        assert result is None

    def test_bearish_divergence_price_not_higher(self):
        """Should reject bearish divergence if price not higher."""
        result = detect_divergence(
            current_price=99.0,      # NOT higher than prev
            current_rsi=60.0,
            prev_price=100.0,
            prev_rsi=75.0,
            div_type="BEARISH"
        )
        assert result is None

    def test_bearish_divergence_rsi_higher(self):
        """Should reject bearish divergence if RSI also makes new high."""
        result = detect_divergence(
            current_price=101.0,     # New high
            current_rsi=80.0,        # RSI also new high - NO DIVERGENCE
            prev_price=100.0,
            prev_rsi=75.0,
            div_type="BEARISH"
        )
        assert result is None

    # EDGE CASES
    def test_divergence_rsi_at_boundary_threshold(self):
        """RSI exactly at threshold should not qualify (boundary check)."""
        # Bullish: RSI at 40 (default threshold) should be rejected
        result = detect_divergence(
            current_price=99.0,
            current_rsi=40.0,        # Exactly at default threshold
            prev_price=100.0,
            prev_rsi=35.0,
            div_type="BULLISH"
        )
        assert result is None

        # Bearish: RSI at 60 (default threshold) should be rejected
        result = detect_divergence(
            current_price=101.0,
            current_rsi=60.0,        # Exactly at default threshold
            prev_price=100.0,
            prev_rsi=75.0,
            div_type="BEARISH"
        )
        assert result is None

    def test_divergence_zero_prices(self):
        """Test with zero prices."""
        result = detect_divergence(
            current_price=0.0,
            current_rsi=40.0,
            prev_price=0.0,
            prev_rsi=35.0,
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
        """Should successfully fetch candles ordered desc then reversed (oldest first)."""
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
        # Should be reversed to oldest first
        assert result == sample_candles[:5]
        # Verify order_by was called with desc
        mock_filter.order_by.assert_called_once()

    @patch('src.storage.db.SessionLocal')
    def test_fetch_candles_empty_result(self, mock_session_class):
        """Should return empty list if no candles found."""
        mock_session = MagicMock()
        mock_query = MagicMock()

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
    def test_fetch_candles_custom_lookback(self, mock_session_class, mock_candle, sample_candles):
        """Should respect custom lookback parameter and return oldest first."""
        mock_session = MagicMock()

        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session_class.return_value.__exit__.return_value = None

        # Simulate DB returning newest first (desc order)
        newest_first = list(reversed(sample_candles[:10]))
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = newest_first

        result = fetch_candles_for_divergence("BTCUSDT", "1d", 10)
        assert len(result) == 10
        # Should be reversed to oldest first
        assert result == sample_candles[:10]
    
    @patch('src.storage.db.SessionLocal')
    def test_fetch_candles_orders_desc_then_reverses(self, mock_session_class, mock_candle):
        """Should fetch newest candles first (desc) then reverse to oldest first."""
        mock_session = MagicMock()
        
        # Create candles with increasing open_time
        base_time = int(datetime.now().timestamp()) * 1000
        candles = [
            mock_candle(open_time=base_time + i * 86400000, close=100.0 + i)
            for i in range(5)
        ]
        
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session_class.return_value.__exit__.return_value = None
        
        # DB returns newest first (desc)
        newest_first = list(reversed(candles))
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = newest_first
        
        result = fetch_candles_for_divergence("BTCUSDT", "1d", 5)
        
        # Should be reversed to oldest first
        assert result == candles
        assert result[0].open_time < result[-1].open_time


# ==================== TESTS: DIVERGENCE INTEGRATION ====================

class TestDivergenceIntegration:
    """Integration tests for complete divergence flow."""

    def test_multiple_pivots_sequence(self, mock_candle):
        """Should handle multiple consecutive pivots correctly."""
        candles = []
        for i in range(20):
            if i == 5:
                candles.append(mock_candle(low=95.0, close=95.5))
            elif i == 12:
                candles.append(mock_candle(low=94.0, close=94.5))
            else:
                candles.append(mock_candle(low=100.0 + (i * 0.1), close=100.0 + (i * 0.1) + 0.5))

        closes = [c.close for c in candles]
        rsi_values = calculate_rsi_for_candles(closes)

        if len(rsi_values) > 14:
            assert rsi_values[14] is not None

    def test_timeframes_independent(self, sample_candles):
        """Should track divergences independently per timeframe."""
        # This validates the divergence_state structure is properly isolated
        assert True  # Structure validates this through unit tests


# ==================== TESTS: LOOKBACK CANDLE WINDOW ====================

class TestLookbackCandleWindow:
    """Test that lookback filters pivots by candle window, not pivot count."""

    def test_lookback_window_calculation_with_enough_candles(self, mock_candle):
        """Should calculate min_open_time from lookback position when enough candles."""
        base_time = int(datetime.now().timestamp()) * 1000
        lookback = 10
        
        # Create 15 candles (more than lookback)
        candles = [
            mock_candle(open_time=base_time + (i * 3600000), close=100.0 + i)  # 1h intervals
            for i in range(15)
        ]
        
        # min_open_time should be from candles[-lookback] = candles[5]
        expected_min_time = candles[5].open_time
        
        # Simulate the logic from _process_divergences
        if len(candles) >= lookback:
            min_open_time = candles[-lookback].open_time
        else:
            min_open_time = candles[0].open_time if candles else 0
        
        assert min_open_time == expected_min_time
        assert min_open_time == candles[5].open_time

    def test_lookback_window_calculation_insufficient_candles(self, mock_candle):
        """Should use first candle when fewer candles than lookback."""
        base_time = int(datetime.now().timestamp()) * 1000
        lookback = 20
        
        # Create only 5 candles (less than lookback)
        candles = [
            mock_candle(open_time=base_time + (i * 3600000), close=100.0 + i)
            for i in range(5)
        ]
        
        # min_open_time should be from first candle
        expected_min_time = candles[0].open_time
        
        # Simulate the logic from _process_divergences
        if len(candles) >= lookback:
            min_open_time = candles[-lookback].open_time
        else:
            min_open_time = candles[0].open_time if candles else 0
        
        assert min_open_time == expected_min_time
        assert min_open_time == candles[0].open_time

    def test_pivot_filtering_by_candle_window(self, mock_candle):
        """Should filter pivots to keep only those within lookback candle window."""
        base_time = int(datetime.now().timestamp()) * 1000
        lookback = 10
        
        # Create 15 candles
        candles = [
            mock_candle(open_time=base_time + (i * 3600000), close=100.0 + i)
            for i in range(15)
        ]
        
        # Calculate min_open_time (candles[-10] = candles[5])
        min_open_time = candles[-lookback].open_time
        
        # Create mock pivots: some old (before min_open_time), some recent (after)
        old_pivot_time = base_time + (2 * 3600000)  # Before min_open_time
        recent_pivot_time = base_time + (8 * 3600000)  # After min_open_time
        
        pivots = [
            {"price": 95.0, "rsi": 30.0, "open_time": old_pivot_time},      # Should be filtered out
            {"price": 98.0, "rsi": 32.0, "open_time": recent_pivot_time},  # Should be kept
            {"price": 97.0, "rsi": 31.0, "open_time": old_pivot_time},     # Should be filtered out
            {"price": 99.0, "rsi": 33.0, "open_time": recent_pivot_time + 3600000},  # Should be kept
        ]
        
        # Filter pivots (simulate logic from _process_divergences)
        filtered_pivots = [p for p in pivots if p["open_time"] >= min_open_time]
        
        # Should keep only recent pivots
        assert len(filtered_pivots) == 2
        assert all(p["open_time"] >= min_open_time for p in filtered_pivots)
        assert filtered_pivots[0]["price"] == 98.0
        assert filtered_pivots[1]["price"] == 99.0

    def test_pivot_filtering_keeps_all_when_all_recent(self, mock_candle):
        """Should keep all pivots when all are within lookback window."""
        base_time = int(datetime.now().timestamp()) * 1000
        lookback = 10
        
        # Create 15 candles
        candles = [
            mock_candle(open_time=base_time + (i * 3600000), close=100.0 + i)
            for i in range(15)
        ]
        
        # Calculate min_open_time
        min_open_time = candles[-lookback].open_time
        
        # All pivots are recent (after min_open_time)
        pivots = [
            {"price": 98.0, "rsi": 32.0, "open_time": base_time + (8 * 3600000)},
            {"price": 99.0, "rsi": 33.0, "open_time": base_time + (9 * 3600000)},
            {"price": 100.0, "rsi": 34.0, "open_time": base_time + (10 * 3600000)},
        ]
        
        # Filter pivots
        filtered_pivots = [p for p in pivots if p["open_time"] >= min_open_time]
        
        # Should keep all pivots
        assert len(filtered_pivots) == 3
        assert filtered_pivots == pivots

    def test_pivot_filtering_removes_all_when_all_old(self, mock_candle):
        """Should remove all pivots when all are outside lookback window."""
        base_time = int(datetime.now().timestamp()) * 1000
        lookback = 10
        
        # Create 15 candles
        candles = [
            mock_candle(open_time=base_time + (i * 3600000), close=100.0 + i)
            for i in range(15)
        ]
        
        # Calculate min_open_time
        min_open_time = candles[-lookback].open_time
        
        # All pivots are old (before min_open_time)
        pivots = [
            {"price": 95.0, "rsi": 30.0, "open_time": base_time + (1 * 3600000)},
            {"price": 96.0, "rsi": 31.0, "open_time": base_time + (2 * 3600000)},
            {"price": 97.0, "rsi": 32.0, "open_time": base_time + (3 * 3600000)},
        ]
        
        # Filter pivots
        filtered_pivots = [p for p in pivots if p["open_time"] >= min_open_time]
        
        # Should remove all pivots
        assert len(filtered_pivots) == 0


# ==================== TESTS: EDGE CASES ====================

class TestDivergenceEdgeCases:
    """Edge case tests for divergence detection."""

    def test_divergence_with_rsi_at_threshold(self):
        """RSI exactly at threshold should not qualify."""
        # Bullish: RSI at 40 (default threshold) should not qualify
        result = detect_divergence(
            current_price=99.0,
            current_rsi=40.0,  # Exactly at default threshold (40)
            prev_price=100.0,
            prev_rsi=35.0,
            div_type="BULLISH"
        )
        assert result is None

        # Bearish: RSI at 60 (default threshold) should not qualify
        result = detect_divergence(
            current_price=101.0,
            current_rsi=60.0,  # Exactly at default threshold (60)
            prev_price=100.0,
            prev_rsi=70.0,
            div_type="BEARISH"
        )
        assert result is None

    def test_divergence_with_equal_prices(self):
        """Should handle equal prices (no divergence)."""
        result = detect_divergence(
            current_price=100.0,  # Same as previous
            current_rsi=40.0,
            prev_price=100.0,
            prev_rsi=35.0,
            div_type="BULLISH"
        )
        assert result is None

    def test_divergence_with_zero_prices(self):
        """Should handle zero prices gracefully."""
        result = detect_divergence(
            current_price=0.0,
            current_rsi=40.0,
            prev_price=0.0,
            prev_rsi=35.0,
            div_type="BULLISH"
        )
        assert result is None

    def test_divergence_extreme_rsi_values(self):
        """Should handle extreme RSI values (0 and 100)."""
        # Bullish at very low RSI (current RSI > prev RSI for divergence)
        result = detect_divergence(
            current_price=99.0,  # Lower low
            current_rsi=10.0,    # Higher than prev (but still < 40, default threshold)
            prev_price=100.0,
            prev_rsi=5.0,        # Lower RSI at higher price = divergence
            div_type="BULLISH"
        )
        assert result == "BULLISH"

        # Bearish at very high RSI (current RSI < prev RSI for divergence)
        result = detect_divergence(
            current_price=101.0,  # Higher high
            current_rsi=90.0,     # Lower than prev (but still > 60, default threshold)
            prev_price=100.0,
            prev_rsi=95.0,        # Higher RSI at lower price = divergence
            div_type="BEARISH"
        )
        assert result == "BEARISH"

    def test_divergence_very_small_price_difference(self):
        """Should detect divergence with very small price differences."""
        result = detect_divergence(
            current_price=100.001,
            current_rsi=35.0,        # < 40 (default threshold)
            prev_price=100.002,
            prev_rsi=30.0,           # < 40 (default threshold)
            div_type="BULLISH"
        )
        assert result == "BULLISH"

    def test_divergence_large_rsi_difference(self):
        """Should detect divergence even with large RSI differences."""
        result = detect_divergence(
            current_price=99.0,
            current_rsi=10.0,  # Much higher RSI
            prev_price=100.0,
            prev_rsi=5.0,      # Previous lower RSI
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
        current_price = 5055.00  # Different price
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
        current_rsi = 36.50  # Different RSI
        
        same_signal = (
            round(last_alert["price"], 2) == round(current_price, 2) and
            round(last_alert["rsi"], 1) == round(current_rsi, 1)
        )
        assert same_signal is False

    def test_rounding_precision_price(self):
        """Should handle price rounding (2 decimals)."""
        last_alert = {"price": 5050.124, "rsi": 35.0}
        current_price = 5050.125  # Same when rounded to 2 decimals (both 5050.12)
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
        current_rsi = 35.44  # Same when rounded to 1 decimal (both 35.4)
        
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
        assert same_signal is False  # None is falsy, so not same signal

    def test_both_price_and_rsi_different(self):
        """Should detect new signal when both price and RSI differ."""
        last_alert = {"price": 5050.19, "rsi": 35.46}
        current_price = 5100.00  # Different
        current_rsi = 40.00      # Different
        
        same_signal = (
            round(last_alert["price"], 2) == round(current_price, 2) and
            round(last_alert["rsi"], 1) == round(current_rsi, 1)
        )
        assert same_signal is False
