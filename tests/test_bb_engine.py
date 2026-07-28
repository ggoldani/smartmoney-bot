"""Tests for BB contratrend alert integration in AlertEngine."""
import pytest
from unittest.mock import patch, MagicMock
from src.rules.engine import AlertEngine


@pytest.fixture
def engine():
    """Create AlertEngine with mocked dependencies."""
    # NOTE: DivergenceProcessor is imported deferred inside __init__,
    # so we patch at the source module path.
    with patch("src.rules.engine.get_throttler"), \
         patch("src.rules.engine.get_rsi_config", return_value={"period": 14, "timeframes": ["1d", "1w", "1M"]}), \
         patch("src.rules.engine.get_breakout_config", return_value={"timeframes": ["1d"]}), \
         patch("src.rules.engine.get_alert_config", return_value={}), \
         patch("src.rules.engine.get_bollinger_config", return_value={
             "enabled": True, "timeframe": "1d", "period": 21, "std_mult": 2.0,
             "buffer_pct": 0.5, "trend": {"rsi_period": 14, "threshold": 50}
         }), \
         patch("src.rules.divergence_processor.DivergenceProcessor") as mock_div_proc:
        mock_div_proc.return_value.initialize_state = MagicMock()
        yield AlertEngine()


class TestCollectBBAlert:
    """Tests for _collect_bb_alert() state machine."""

    @patch.object(AlertEngine, "_determine_trend", return_value=("BEAR", 40.0))
    @patch("src.rules.engine.check_bb_breach")
    @patch("src.rules.engine.is_price_inside_bands", return_value=False)
    @patch("src.rules.engine.is_indicator_enabled", return_value=True)
    def test_short_alert_on_upper_breach_bear_trend(self, mock_enabled, mock_inside, mock_breach, mock_trend, engine):
        """Bear trend + upper breach → SHORT alert collected."""
        mock_breach.return_value = {
            "type": "UPPER", "symbol": "BTCUSDT", "interval": "1d",
            "price": 105.0, "bb_upper": 100.0, "bb_middle": 95.0, "effective_band": 100.5
        }
        with patch.object(engine, "_check_throttle_and_mark", return_value=True), \
             patch.object(engine, "_collect_single_alert") as mock_collect:
            engine._collect_bb_alert("BTCUSDT", "1d", 105.0, 1700000000)
            mock_collect.assert_called_once()
            args = mock_collect.call_args
            assert args.kwargs["condition"] == "SHORT"
            assert args.kwargs["alert_type"] == "BB"

    @patch.object(AlertEngine, "_determine_trend", return_value=("BULL", 60.0))
    @patch("src.rules.engine.check_bb_breach")
    @patch("src.rules.engine.is_price_inside_bands", return_value=False)
    @patch("src.rules.engine.is_indicator_enabled", return_value=True)
    def test_long_alert_on_lower_breach_bull_trend(self, mock_enabled, mock_inside, mock_breach, mock_trend, engine):
        mock_breach.return_value = {
            "type": "LOWER", "symbol": "BTCUSDT", "interval": "1d",
            "price": 95.0, "bb_lower": 100.0, "bb_middle": 105.0, "effective_band": 99.5
        }
        with patch.object(engine, "_check_throttle_and_mark", return_value=True), \
             patch.object(engine, "_collect_single_alert") as mock_collect:
            engine._collect_bb_alert("BTCUSDT", "1d", 95.0, 1700000000)
            mock_collect.assert_called_once()
            assert mock_collect.call_args.kwargs["condition"] == "LONG"

    @patch.object(AlertEngine, "_determine_trend", return_value=("BEAR", 40.0))
    @patch("src.rules.engine.check_bb_breach")
    @patch("src.rules.engine.is_price_inside_bands", return_value=False)
    @patch("src.rules.engine.is_indicator_enabled", return_value=True)
    def test_no_alert_breach_with_trend_not_against(self, mock_enabled, mock_inside, mock_breach, mock_trend, engine):
        """Bear trend + LOWER breach (with trend) → no alert."""
        mock_breach.return_value = {
            "type": "LOWER", "symbol": "BTCUSDT", "interval": "1d",
            "price": 95.0, "bb_lower": 100.0, "bb_middle": 105.0, "effective_band": 99.5
        }
        with patch.object(engine, "_collect_single_alert") as mock_collect:
            engine._collect_bb_alert("BTCUSDT", "1d", 95.0, 1700000000)
            mock_collect.assert_not_called()

    @patch.object(AlertEngine, "_determine_trend", return_value=(None, 50.0))
    @patch("src.rules.engine.check_bb_breach")
    @patch("src.rules.engine.is_price_inside_bands", return_value=False)
    @patch("src.rules.engine.is_indicator_enabled", return_value=True)
    def test_no_alert_neutral_trend(self, mock_enabled, mock_inside, mock_breach, mock_trend, engine):
        mock_breach.return_value = {"type": "UPPER", "price": 105.0}
        with patch.object(engine, "_collect_single_alert") as mock_collect:
            engine._collect_bb_alert("BTCUSDT", "1d", 105.0, 1700000000)
            mock_collect.assert_not_called()

    @patch("src.rules.engine.check_bb_breach")
    @patch("src.rules.engine.is_price_inside_bands", return_value=True)
    @patch("src.rules.engine.is_indicator_enabled", return_value=True)
    def test_state_reset_when_price_returns_inside(self, mock_enabled, mock_inside, mock_breach, engine):
        """When in breach state and price returns inside bands → state resets to None."""
        engine.last_condition[("BTCUSDT", "1d", "BB")] = "SHORT"
        engine._collect_bb_alert("BTCUSDT", "1d", 100.0, 1700000000)
        assert engine.last_condition[("BTCUSDT", "1d", "BB")] is None
        mock_breach.assert_not_called()  # doesn't even check breach when resetting

    @patch("src.rules.engine.check_bb_breach")
    @patch("src.rules.engine.is_price_inside_bands", return_value=False)
    @patch("src.rules.engine.is_indicator_enabled", return_value=True)
    def test_no_realert_while_still_breaching(self, mock_enabled, mock_inside, mock_breach, engine):
        """When in breach state and still outside bands → no new alert, no check_bb_breach."""
        engine.last_condition[("BTCUSDT", "1d", "BB")] = "SHORT"
        engine._collect_bb_alert("BTCUSDT", "1d", 105.0, 1700000000)
        mock_breach.assert_not_called()  # skipped because still breaching

    @patch("src.rules.engine.is_indicator_enabled", return_value=True)
    def test_disabled_skips(self, mock_enabled, engine):
        """When indicator disabled → no processing."""
        with patch("src.rules.engine.is_indicator_enabled", return_value=False):
            engine._collect_bb_alert("BTCUSDT", "1d", 105.0, 1700000000)
        # No exception, no state change

    @patch("src.rules.engine.is_indicator_enabled", return_value=True)
    def test_wrong_timeframe_skips(self, mock_enabled, engine):
        """BB only on configured timeframe (1d). 4h candle → skip."""
        with patch("src.rules.engine.check_bb_breach") as mock_breach:
            engine._collect_bb_alert("BTCUSDT", "4h", 105.0, 1700000000)
            mock_breach.assert_not_called()


class TestSymbolRouting:
    """Tests for symbol routing via get_symbol_alerts()."""

    @patch("src.rules.engine.get_symbol_alerts", return_value=["bb"])
    @patch("src.rules.engine.is_indicator_enabled", return_value=True)
    def test_rsi_skipped_for_bb_only_symbol(self, mock_enabled, mock_alerts, engine):
        """BB-only symbol should skip RSI alert collection."""
        with patch.object(engine, "_check_throttle_and_mark") as mock_throttle:
            engine._collect_rsi_alert("ETHUSDT", "1d", 1700000000)
            mock_throttle.assert_not_called()

    @patch("src.rules.engine.get_symbol_alerts", return_value=["bb"])
    @patch("src.rules.engine.is_indicator_enabled", return_value=True)
    def test_breakout_skipped_for_bb_only_symbol(self, mock_enabled, mock_alerts, engine):
        with patch.object(engine, "_check_throttle_and_mark") as mock_throttle:
            engine._collect_breakout_alert("ETHUSDT", "1d", 100.0, 1700000000)
            mock_throttle.assert_not_called()

    @patch.object(AlertEngine, "_determine_trend", return_value=("BEAR", 40.0))
    @patch("src.rules.engine.get_symbol_alerts", return_value=["rsi", "breakout", "divergence", "bb"])
    @patch("src.rules.engine.is_indicator_enabled", return_value=True)
    def test_bb_runs_for_full_symbol(self, mock_enabled, mock_alerts, mock_trend, engine):
        """Full symbol (all alerts) should proceed to BB check."""
        with patch("src.rules.engine.check_bb_breach", return_value=None) as mock_breach:
            engine._collect_bb_alert("BTCUSDT", "1d", 100.0, 1700000000)
            mock_breach.assert_called_once()


class TestTrendFilterMensalOnly:
    """Tests for _determine_trend() using monthly RSI only."""

    @patch("src.rules.engine.analyze_rsi")
    def test_bull_trend_mensal_only(self, mock_rsi, engine):
        """RSI(1M) > 50 → BULL, no weekly check needed."""
        mock_rsi.return_value = {"rsi": 60.0}
        trend, rsi_val = engine._determine_trend("BTCUSDT")
        assert trend == "BULL"
        assert rsi_val == 60.0
        # Should call analyze_rsi only once (1M), not twice (1w + 1M)
        assert mock_rsi.call_count == 1
        mock_rsi.assert_called_with("BTCUSDT", "1M", period=14, _use_config=False)

    @patch("src.rules.engine.analyze_rsi")
    def test_bear_trend_mensal_only(self, mock_rsi, engine):
        mock_rsi.return_value = {"rsi": 40.0}
        trend, rsi_val = engine._determine_trend("BTCUSDT")
        assert trend == "BEAR"
        assert rsi_val == 40.0

    @patch("src.rules.engine.analyze_rsi")
    def test_neutral_exact_threshold(self, mock_rsi, engine):
        mock_rsi.return_value = {"rsi": 50.0}
        trend, rsi_val = engine._determine_trend("BTCUSDT")
        assert trend is None
        assert rsi_val == 50.0

    @patch("src.rules.engine.analyze_rsi")
    def test_neutral_insufficient_data(self, mock_rsi, engine):
        mock_rsi.return_value = None
        trend, rsi_val = engine._determine_trend("BTCUSDT")
        assert trend is None
        assert rsi_val is None
