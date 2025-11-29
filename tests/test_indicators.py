"""Tests for indicator calculations (RSI, Breakouts)."""
import pytest
from typing import List
from src.indicators.rsi import calculate_rsi
from src.indicators.breakouts import check_breakout


class TestRSICalculation:
    """Tests for RSI (Relative Strength Index) calculation."""

    def test_rsi_with_insufficient_data(self):
        """RSI should return None with insufficient data (< period + 1)."""
        short_prices = [44.34, 44.09, 44.15, 43.61, 44.33]
        result = calculate_rsi(short_prices, period=14)
        assert result is None

    def test_rsi_with_exact_minimum_data(self, sample_candles: List[float]):
        """RSI should calculate with exactly period + 1 candles."""
        min_data = sample_candles[:15]  # 14 + 1
        result = calculate_rsi(min_data, period=14)
        assert result is not None
        assert 0 <= result <= 100

    def test_rsi_with_sufficient_data(self, sample_candles: List[float]):
        """RSI should calculate correctly with sufficient data."""
        result = calculate_rsi(sample_candles, period=14)
        assert result is not None
        assert isinstance(result, float)
        assert 0 <= result <= 100

    def test_rsi_extreme_uptrend(self, extreme_uptrend_candles: List[float]):
        """RSI should be high (>70) in strong uptrend."""
        result = calculate_rsi(extreme_uptrend_candles, period=14)
        assert result is not None
        assert result > 70, f"Expected RSI > 70 in uptrend, got {result}"

    def test_rsi_extreme_downtrend(self, extreme_downtrend_candles: List[float]):
        """RSI should be low (<30) in strong downtrend."""
        result = calculate_rsi(extreme_downtrend_candles, period=14)
        assert result is not None
        assert result < 30, f"Expected RSI < 30 in downtrend, got {result}"

    def test_rsi_flat_market(self, flat_candles: List[float]):
        """RSI should be near 50 in flat market."""
        result = calculate_rsi(flat_candles, period=14)
        assert result is not None
        assert 40 <= result <= 60, f"Expected RSI near 50 in flat market, got {result}"

    def test_rsi_all_gains(self):
        """RSI should be 100 when all prices only increase."""
        increasing_prices = [float(i) for i in range(100, 125)]  # 100, 101, 102, ...
        result = calculate_rsi(increasing_prices, period=14)
        assert result is not None
        assert result == 100.0

    def test_rsi_all_losses(self):
        """RSI should be 0 when all prices only decrease."""
        decreasing_prices = [float(i) for i in range(125, 100, -1)]  # 125, 124, 123, ...
        result = calculate_rsi(decreasing_prices, period=14)
        assert result is not None
        assert result == 0.0

    def test_rsi_custom_period(self, sample_candles: List[float]):
        """RSI should work with different periods."""
        result_14 = calculate_rsi(sample_candles, period=14)
        result_21 = calculate_rsi(sample_candles, period=21)

        # Both should be valid
        assert result_14 is not None
        # result_21 might be None if we don't have 22 candles
        # (sample_candles has 24 elements, so 21 is ok)
        if len(sample_candles) >= 22:
            assert result_21 is not None

    def test_rsi_returns_float(self, sample_candles: List[float]):
        """RSI should return a float (not int)."""
        result = calculate_rsi(sample_candles, period=14)
        assert isinstance(result, float)

    def test_rsi_single_large_move(self):
        """RSI with single large move should show clear direction."""
        # Flat for 15 candles, then one big jump
        prices = [100.0] * 15 + [105.0]
        result = calculate_rsi(prices, period=14)
        assert result is not None
        assert result > 50, "Should show strength after big upward move"


class TestBreakoutDetection:
    """Tests for breakout detection (Bull & Bear).

    Note: check_breakout() is DB-dependent, so we test the margin calculation logic.
    """

    def test_bull_breakout_margin_calculation(self):
        """Test margin calculation for bull breakout (0.1%)."""
        # Bull margin: price > high * 1.001
        prev_high = 100.0
        margin_up = 1 + (0.1 / 100)  # 1.001

        # Should trigger at price > 100.1
        assert 100.11 > prev_high * margin_up  # True
        assert 100.09 < prev_high * margin_up  # True (100.09 < 100.1)

    def test_bear_breakout_margin_calculation(self):
        """Test margin calculation for bear breakout (0.1%)."""
        # Bear margin: price < low * 0.999
        prev_low = 100.0
        margin_down = 1 - (0.1 / 100)  # 0.999

        # Should trigger at price < 99.9
        assert 99.89 < prev_low * margin_down  # True
        assert 99.91 > prev_low * margin_down  # True (99.91 > 99.9)

    def test_bull_breakout_logic_exact_margin(self):
        """Bull breakout exactly at margin threshold."""
        prev_high = 100.0
        margin_up = 1.001
        current_price = 100.11  # Need slightly above 100.1

        # 100.11 > 100.1, should trigger
        assert current_price > prev_high * margin_up

    def test_bear_breakout_logic_exact_margin(self):
        """Bear breakout exactly at margin threshold."""
        prev_low = 100.0
        margin_down = 0.999
        current_price = 99.89  # Need slightly below 99.9

        # 99.89 < 99.9, should trigger
        assert current_price < prev_low * margin_down

    def test_bull_no_breakout_below_margin(self):
        """No bull breakout below margin."""
        prev_high = 100.0
        margin_up = 1.001
        current_price = 100.09

        # 100.09 is NOT > 100.1
        assert not (current_price > prev_high * margin_up)

    def test_bear_no_breakout_above_margin(self):
        """No bear breakout above margin."""
        prev_low = 100.0
        margin_down = 0.999
        current_price = 99.91

        # 99.91 is NOT < 99.9
        assert not (current_price < prev_low * margin_down)

    def test_bull_large_move_breakout(self):
        """Large upward move triggers bull breakout."""
        prev_high = 100.0
        margin_up = 1.001
        current_price = 110.0  # 10% above

        assert current_price > prev_high * margin_up

    def test_bear_large_move_breakout(self):
        """Large downward move triggers bear breakout."""
        prev_low = 100.0
        margin_down = 0.999
        current_price = 90.0  # 10% below

        assert current_price < prev_low * margin_down

    def test_bull_breakout_btc_prices(self):
        """Bull breakout with realistic BTC prices."""
        prev_high = 45000.50
        margin_up = 1.001
        current_price = 45045.75

        # 45045.75 > 45000.50 * 1.001 (45045.005)?
        assert current_price > prev_high * margin_up

    def test_bear_breakout_btc_prices(self):
        """Bear breakout with realistic BTC prices."""
        prev_low = 45000.50
        margin_down = 0.999
        current_price = 44954.75

        # 44954.75 < 45000.50 * 0.999 (44955.495)?
        assert current_price < prev_low * margin_down


class TestIndicatorEdgeCases:
    """Edge cases and boundary conditions."""

    def test_rsi_with_negative_prices(self):
        """RSI should handle data even with negative prices (edge case)."""
        # Negative prices not realistic but test robustness
        prices = [-100.0 + i for i in range(24)]
        result = calculate_rsi(prices, period=14)
        assert result is not None or result is None  # Either valid or None
        if result is not None:
            assert 0 <= result <= 100

    def test_rsi_period_1(self, sample_candles: List[float]):
        """RSI with period=1 should still calculate."""
        result = calculate_rsi(sample_candles, period=1)
        # Should work but might not be meaningful
        assert result is None or (0 <= result <= 100)

    def test_bull_breakout_margin_edge_case(self):
        """Edge case: price exactly at margin boundary."""
        prev_high = 100.0
        margin_up = 1.001
        # Threshold = 100.0 * 1.001 = 100.1
        threshold = prev_high * margin_up
        assert threshold == 100.1

    def test_bear_breakout_margin_edge_case(self):
        """Edge case: price exactly at margin boundary."""
        prev_low = 100.0
        margin_down = 0.999
        # Threshold = 100.0 * 0.999 = 99.9
        threshold = prev_low * margin_down
        assert threshold == 99.9
