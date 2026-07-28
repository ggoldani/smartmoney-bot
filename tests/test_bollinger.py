"""Tests for Bollinger Bands indicator and BB contratrend alert integration."""
import pytest
from unittest.mock import patch, MagicMock


class TestBollingerConfig:
    """Tests for get_bollinger_config() helper."""

    def test_bollinger_config_returns_defaults(self, monkeypatch):
        """get_bollinger_config should return safe defaults when section missing."""
        from src.config import get_bollinger_config, reload_config
        # Force reload with default config (configs/free.yaml)
        monkeypatch.setenv("CONFIG_FILE", "./configs/free.yaml")
        reload_config()
        config = get_bollinger_config()
        assert config["enabled"] is True
        assert config["timeframe"] == "1d"
        assert config["period"] == 21
        assert config["std_mult"] == 2.0
        assert config["buffer_pct"] == 0.5
        assert config["trend"]["rsi_period"] == 14
        assert config["trend"]["threshold"] == 50

    def test_bollinger_config_validates_period(self, monkeypatch, tmp_path):
        """Period must be > 1."""
        import yaml
        config = {
            "bot": {"tier": "free", "version": "1.0.0", "name": "test"},
            "telegram": {"startup_message": True},
            "symbols": [{"name": "BTCUSDT", "timeframes": ["1d"]}],
            "indicators": {
                "rsi": {"period": 14, "overbought": 70, "oversold": 30, "timeframes": ["1d"]},
                "breakout": {"timeframes": ["1d"]},
                "bollinger": {"period": 0}  # invalid
            },
            "alerts": {"timezone": "America/Sao_Paulo"}
        }
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml.dump(config))
        monkeypatch.setenv("CONFIG_FILE", str(config_file))
        from src.config import reload_config, get_bollinger_config
        reload_config()
        cfg = get_bollinger_config()
        assert cfg["period"] == 21  # fallback default


class TestCalculateBB:
    """Tests for calculate_bb() pure function."""

    def test_bb_insufficient_data(self):
        """Should return None with < period closes."""
        from src.indicators.bollinger import calculate_bb
        result = calculate_bb([100.0, 101.0, 102.0], period=21)
        assert result is None

    def test_bb_with_exact_period(self):
        """Should calculate with exactly period closes."""
        from src.indicators.bollinger import calculate_bb
        closes = [100.0 + i * 0.5 for i in range(21)]
        result = calculate_bb(closes, period=21, std_mult=2.0)
        assert result is not None
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result
        assert result["upper"] > result["middle"] > result["lower"]

    def test_bb_symmetry(self):
        """Upper and lower should be equidistant from middle (constant volatility)."""
        from src.indicators.bollinger import calculate_bb
        # Constant spread → symmetric bands
        closes = [100.0, 101.0] * 11  # alternating, 22 values
        result = calculate_bb(closes, period=20, std_mult=2.0)
        assert result is not None
        spread_upper = result["upper"] - result["middle"]
        spread_lower = result["middle"] - result["lower"]
        assert abs(spread_upper - spread_lower) < 0.0001

    def test_bb_flat_market_narrow_bands(self):
        """Flat market should produce narrow bands."""
        from src.indicators.bollinger import calculate_bb
        closes = [100.0] * 21
        result = calculate_bb(closes, period=21, std_mult=2.0)
        assert result is not None
        assert result["upper"] == pytest.approx(100.0, abs=0.001)
        assert result["lower"] == pytest.approx(100.0, abs=0.001)

    def test_bb_std_mult_scales_bands(self):
        """Higher std_mult should produce wider bands."""
        from src.indicators.bollinger import calculate_bb
        closes = [100.0 + i for i in range(25)]
        result_2 = calculate_bb(closes, period=20, std_mult=2.0)
        result_3 = calculate_bb(closes, period=20, std_mult=3.0)
        width_2 = result_2["upper"] - result_2["lower"]
        width_3 = result_3["upper"] - result_3["lower"]
        assert width_3 > width_2


class TestCheckBBBreach:
    """Tests for check_bb_breach() with mocked DB."""

    @patch("src.indicators.bollinger.fetch_closed_candles_for_bb")
    def test_breach_upper_with_buffer(self, mock_fetch):
        """Should detect UPPER breach when price > upper_effective."""
        from src.indicators.bollinger import check_bb_breach
        # Construct closes so BB upper ≈ 110
        closes = [100.0] * 21
        mock_fetch.return_value = closes
        # With flat data, bands collapse to 100. buffer 0.5% → effective 100.5
        result = check_bb_breach("BTCUSDT", "1d", 105.0, period=21, buffer_pct=0.5)
        assert result is not None
        assert result["type"] == "UPPER"
        assert result["price"] == 105.0

    @patch("src.indicators.bollinger.fetch_closed_candles_for_bb")
    def test_breach_lower_with_buffer(self, mock_fetch):
        """Should detect LOWER breach when price < lower_effective."""
        from src.indicators.bollinger import check_bb_breach
        closes = [100.0] * 21
        mock_fetch.return_value = closes
        result = check_bb_breach("BTCUSDT", "1d", 95.0, period=21, buffer_pct=0.5)
        assert result is not None
        assert result["type"] == "LOWER"
        assert result["price"] == 95.0

    @patch("src.indicators.bollinger.fetch_closed_candles_for_bb")
    def test_no_breach_inside_bands(self, mock_fetch):
        """Should return None when price is inside bands."""
        from src.indicators.bollinger import check_bb_breach
        closes = [90.0, 110.0] * 11  # volatile, wide bands
        mock_fetch.return_value = closes
        result = check_bb_breach("BTCUSDT", "1d", 100.0, period=20, buffer_pct=0.5)
        assert result is None

    @patch("src.indicators.bollinger.fetch_closed_candles_for_bb")
    def test_buffer_prevents_marginal_breach(self, mock_fetch):
        """Price slightly above raw upper but below effective → no breach."""
        from src.indicators.bollinger import check_bb_breach
        closes = [100.0] * 21  # bands collapse to 100
        mock_fetch.return_value = closes
        # effective upper = 100 * 1.005 = 100.5
        result = check_bb_breach("BTCUSDT", "1d", 100.3, period=21, buffer_pct=0.5)
        assert result is None  # 100.3 < 100.5

    @patch("src.indicators.bollinger.fetch_closed_candles_for_bb")
    def test_insufficient_data_returns_none(self, mock_fetch):
        """Should return None with insufficient closed candles."""
        from src.indicators.bollinger import check_bb_breach
        mock_fetch.return_value = [100.0, 101.0]  # only 2
        result = check_bb_breach("BTCUSDT", "1d", 200.0, period=21)
        assert result is None


class TestIsPriceInsideBands:
    """Tests for is_price_inside_bands() — anti-spam reset logic."""

    @patch("src.indicators.bollinger.fetch_closed_candles_for_bb")
    def test_price_inside_returns_true(self, mock_fetch):
        from src.indicators.bollinger import is_price_inside_bands
        closes = [90.0, 110.0] * 11
        mock_fetch.return_value = closes
        assert is_price_inside_bands("BTCUSDT", "1d", 100.0, period=20) is True

    @patch("src.indicators.bollinger.fetch_closed_candles_for_bb")
    def test_price_above_upper_returns_false(self, mock_fetch):
        from src.indicators.bollinger import is_price_inside_bands
        closes = [100.0] * 21  # bands at 100
        mock_fetch.return_value = closes
        assert is_price_inside_bands("BTCUSDT", "1d", 105.0, period=21) is False

    @patch("src.indicators.bollinger.fetch_closed_candles_for_bb")
    def test_price_below_lower_returns_false(self, mock_fetch):
        from src.indicators.bollinger import is_price_inside_bands
        closes = [100.0] * 21
        mock_fetch.return_value = closes
        assert is_price_inside_bands("BTCUSDT", "1d", 95.0, period=21) is False


class TestBBTemplates:
    """Tests for BB contratrend alert templates."""

    def test_template_bb_short(self):
        """template_bb_short should render SHORT contratrend alert."""
        from src.notif.templates import template_bb_short
        data = {
            "symbol": "BTCUSDT",
            "interval": "1d",
            "price": 67500.0,
            "bb_upper": 67000.0,
            "effective_band": 67335.0,
            "rsi_1M": 38.0,
        }
        result = template_bb_short(data)
        assert "SHORT" in result
        assert "BTC/USDT" in result
        assert "67.500" in result  # BR format
        assert "RSI" in result  # shows trend context

    def test_template_bb_long(self):
        """template_bb_long should render LONG contratrend alert."""
        from src.notif.templates import template_bb_long
        data = {
            "symbol": "BTCUSDT",
            "interval": "1d",
            "price": 94500.0,
            "bb_lower": 95000.0,
            "effective_band": 94525.0,
            "rsi_1M": 62.0,
        }
        result = template_bb_long(data)
        assert "LONG" in result
        assert "BTC/USDT" in result
        assert "94.500" in result

    def test_templates_include_disclaimer(self):
        """Both templates must include ALERT_DISCLAIMER."""
        from src.notif.templates import template_bb_short, template_bb_long, ALERT_DISCLAIMER
        data = {
            "symbol": "BTCUSDT", "interval": "1d", "price": 100.0,
            "bb_upper": 99.0, "effective_band": 99.5,
            "rsi_1M": 40.0,
        }
        assert ALERT_DISCLAIMER in template_bb_short(data)
        data_long = {**data, "bb_lower": 101.0}
        assert ALERT_DISCLAIMER in template_bb_long(data_long)


class TestBBMegaAlert:
    """Tests for BB block in mega-alert consolidation."""

    def test_mega_alert_includes_bb_short(self):
        """Mega-alert should render BB SHORT block."""
        from src.notif.templates import template_mega_alert
        alerts = [{
            "type": "BB", "condition": "SHORT",
            "symbol": "BTCUSDT", "interval": "1d",
            "price": 67500.0, "bb_upper": 67000.0,
            "effective_band": 67335.0,
            "rsi_1M": 38.0,
        }]
        result = template_mega_alert(alerts)
        assert "BB Contratrend SHORT" in result

    def test_mega_alert_includes_bb_long(self):
        from src.notif.templates import template_mega_alert
        alerts = [{
            "type": "BB", "condition": "LONG",
            "symbol": "BTCUSDT", "interval": "1d",
            "price": 94500.0, "bb_lower": 95000.0,
            "effective_band": 94525.0,
            "rsi_1M": 62.0,
        }]
        result = template_mega_alert(alerts)
        assert "BB Contratrend LONG" in result
