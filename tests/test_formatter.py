"""Tests for Brazilian formatting utilities."""
import pytest
from datetime import datetime, timezone
import pytz
from src.notif.formatter import (
    format_price_br,
    format_percentage_br,
    format_rsi_value,
    format_datetime_br,
    format_timestamp_br,
    format_symbol_display,
    format_timeframe_display,
    get_brazil_time
)


class TestPriceFormatting:
    """Tests for Brazilian price formatting ($1.234,56)."""

    def test_format_price_simple(self):
        """Format simple price."""
        result = format_price_br(100.50)
        assert result == "$100,50"

    def test_format_price_thousands(self):
        """Format price with thousands separator."""
        result = format_price_br(1234.56)
        assert result == "$1.234,56"

    def test_format_price_millions(self):
        """Format price with millions (Bitcoin realistic)."""
        result = format_price_br(67420.50)
        assert result == "$67.420,50"

    def test_format_price_zero(self):
        """Format zero price."""
        result = format_price_br(0.0)
        assert result == "$0,00"

    def test_format_price_fractional(self):
        """Format price with small fractional part."""
        result = format_price_br(45000.99)
        assert result == "$45.000,99"

    def test_format_price_high_precision(self):
        """Format price with high precision (truncated to 2 decimals)."""
        result = format_price_br(45000.12345)
        assert result == "$45.000,12"

    def test_format_price_large_number(self):
        """Format very large price."""
        result = format_price_br(1234567.89)
        assert result == "$1.234.567,89"

    def test_format_price_dollar_prefix(self):
        """Price should have dollar sign prefix."""
        result = format_price_br(100.0)
        assert result.startswith("$")


class TestPercentageFormatting:
    """Tests for Brazilian percentage formatting (0,15%)."""

    def test_format_percentage_decimal(self):
        """Format percentage."""
        result = format_percentage_br(0.15)
        assert result == "0,15%"

    def test_format_percentage_whole(self):
        """Format whole percentage."""
        result = format_percentage_br(50.0)
        assert result == "50,00%"

    def test_format_percentage_high(self):
        """Format high percentage."""
        result = format_percentage_br(99.99)
        assert result == "99,99%"

    def test_format_percentage_zero(self):
        """Format zero percentage."""
        result = format_percentage_br(0.0)
        assert result == "0,00%"

    def test_format_percentage_fractional(self):
        """Format small fractional percentage."""
        result = format_percentage_br(0.1)
        assert result == "0,10%"

    def test_format_percentage_suffix(self):
        """Percentage should have percent suffix."""
        result = format_percentage_br(50.0)
        assert result.endswith("%")


class TestRSIFormatting:
    """Tests for RSI value formatting."""

    def test_format_rsi_normal(self):
        """Format RSI value."""
        result = format_rsi_value(50.0)
        assert result == "50,00"

    def test_format_rsi_overbought(self):
        """Format overbought RSI (>70)."""
        result = format_rsi_value(75.30)
        assert result == "75,30"

    def test_format_rsi_oversold(self):
        """Format oversold RSI (<30)."""
        result = format_rsi_value(25.80)
        assert result == "25,80"

    def test_format_rsi_extreme_high(self):
        """Format extreme RSI (>85)."""
        result = format_rsi_value(95.50)
        assert result == "95,50"

    def test_format_rsi_minimum(self):
        """Format minimum RSI (0)."""
        result = format_rsi_value(0.0)
        assert result == "0,00"

    def test_format_rsi_maximum(self):
        """Format maximum RSI (100)."""
        result = format_rsi_value(100.0)
        assert result == "100,00"

    def test_format_rsi_uses_comma_decimal(self):
        """RSI should use comma as decimal separator."""
        result = format_rsi_value(70.50)
        assert "," in result
        assert "." not in result


class TestDateTimeFormatting:
    """Tests for Brazilian datetime formatting (11/11/2025 11:30 BRT)."""

    def test_format_datetime_none(self):
        """Format None should use current time."""
        result = format_datetime_br(None)
        assert "BRT" in result
        assert "/" in result  # DD/MM/YYYY format
        assert ":" in result  # HH:MM format

    def test_format_datetime_current(self):
        """Format current time in BRT."""
        result = format_datetime_br()
        assert "BRT" in result
        assert "/" in result
        assert ":" in result

    def test_format_datetime_utc_input(self):
        """Format UTC datetime to BRT."""
        utc_time = datetime(2025, 11, 11, 14, 30, tzinfo=timezone.utc)
        result = format_datetime_br(utc_time)
        assert "BRT" in result
        # 14:30 UTC = 11:30 BRT (UTC-3)
        assert "11:30 BRT" in result

    def test_format_datetime_naive_input(self):
        """Format naive datetime (assumes UTC)."""
        naive_time = datetime(2025, 11, 11, 14, 30)
        result = format_datetime_br(naive_time)
        assert "BRT" in result
        assert "11:30 BRT" in result

    def test_format_datetime_brt_input(self):
        """Format datetime already in BRT."""
        brt = pytz.timezone('America/Sao_Paulo')
        brt_time = datetime(2025, 11, 11, 11, 30, tzinfo=brt)
        result = format_datetime_br(brt_time)
        assert "11/11/2025 11:30 BRT" in result

    def test_format_datetime_format_pattern(self):
        """Format should follow DD/MM/YYYY HH:MM BRT pattern."""
        utc_time = datetime(2025, 1, 5, 14, 30, tzinfo=timezone.utc)
        result = format_datetime_br(utc_time)
        # 14:30 UTC = 11:30 BRT
        assert "05/01/2025 11:30 BRT" in result


class TestTimestampFormatting:
    """Tests for Unix timestamp formatting."""

    def test_format_timestamp_ms(self):
        """Format timestamp in milliseconds."""
        # 2025-01-01 12:00:00 UTC = 1735718400000 ms
        timestamp_ms = 1735718400000
        result = format_timestamp_br(timestamp_ms)
        assert "BRT" in result
        assert "/" in result
        assert ":" in result

    def test_format_timestamp_zero(self):
        """Format timestamp zero (1970-01-01)."""
        timestamp_ms = 0
        result = format_timestamp_br(timestamp_ms)
        assert "BRT" in result
        # 00:00 UTC = -03:00 BRT (previous day in BRT)
        assert "1969" in result or "1970" in result


class TestSymbolDisplay:
    """Tests for trading pair symbol formatting."""

    def test_format_symbol_usdt(self):
        """Format BTCUSDT -> BTC/USDT."""
        result = format_symbol_display("BTCUSDT")
        assert result == "BTC/USDT"

    def test_format_symbol_usdt_other(self):
        """Format ETHUSDT -> ETH/USDT."""
        result = format_symbol_display("ETHUSDT")
        assert result == "ETH/USDT"

    def test_format_symbol_btc_pair(self):
        """Format ETHBTC -> ETH/BTC."""
        result = format_symbol_display("ETHBTC")
        assert result == "ETH/BTC"

    def test_format_symbol_eth_pair(self):
        """Format LINKETH -> LINK/ETH."""
        result = format_symbol_display("LINKETH")
        assert result == "LINK/ETH"

    def test_format_symbol_unknown(self):
        """Format unknown symbol returns as-is."""
        result = format_symbol_display("XYZ")
        assert result == "XYZ"

    def test_format_symbol_short(self):
        """Format short symbol."""
        result = format_symbol_display("BTCUSD")
        assert result == "BTCUSD"  # No match, returns as-is


class TestTimeframeDisplay:
    """Tests for timeframe formatting in Portuguese."""

    def test_format_tf_1_minute(self):
        """Format 1m -> 1 minuto."""
        result = format_timeframe_display("1m")
        assert result == "1 minuto"

    def test_format_tf_5_minutes(self):
        """Format 5m -> 5 minutos."""
        result = format_timeframe_display("5m")
        assert result == "5 minutos"

    def test_format_tf_15_minutes(self):
        """Format 15m -> 15 minutos."""
        result = format_timeframe_display("15m")
        assert result == "15 minutos"

    def test_format_tf_1_hour(self):
        """Format 1h -> 1 hora."""
        result = format_timeframe_display("1h")
        assert result == "1 hora"

    def test_format_tf_4_hours(self):
        """Format 4h -> 4 horas."""
        result = format_timeframe_display("4h")
        assert result == "4 horas"

    def test_format_tf_1_day(self):
        """Format 1d -> 1 dia."""
        result = format_timeframe_display("1d")
        assert result == "1 dia"

    def test_format_tf_1_week(self):
        """Format 1w -> 1 semana."""
        result = format_timeframe_display("1w")
        assert result == "1 semana"

    def test_format_tf_1_month(self):
        """Format 1M -> 1 mês."""
        result = format_timeframe_display("1M")
        assert result == "1 mês"

    def test_format_tf_unknown(self):
        """Format unknown timeframe returns as-is."""
        result = format_timeframe_display("99m")
        assert result == "99m"

    def test_format_tf_portuguese_output(self):
        """Timeframe output should be in Portuguese."""
        result = format_timeframe_display("4h")
        assert "horas" in result


class TestBrazilTime:
    """Tests for Brazil time utilities."""

    def test_get_brazil_time_returns_datetime(self):
        """get_brazil_time should return datetime object."""
        result = get_brazil_time()
        assert isinstance(result, datetime)

    def test_get_brazil_time_has_timezone(self):
        """get_brazil_time should have timezone info (BRT)."""
        result = get_brazil_time()
        assert result.tzinfo is not None
        assert "Sao_Paulo" in str(result.tzinfo)

    def test_get_brazil_time_is_recent(self):
        """get_brazil_time should return recent time (within 1 minute)."""
        import time
        before = datetime.now(tz=timezone.utc).timestamp()
        result = get_brazil_time()
        after = datetime.now(tz=timezone.utc).timestamp()

        result_ts = result.timestamp()
        # Should be within ±1 minute
        assert before - 60 <= result_ts <= after + 60


class TestFormattingEdgeCases:
    """Edge cases and boundary conditions."""

    def test_price_formatting_negative(self):
        """Handle negative price (edge case)."""
        result = format_price_br(-100.50)
        assert "$" in result
        assert "-" in result

    def test_percentage_negative(self):
        """Handle negative percentage."""
        result = format_percentage_br(-0.5)
        assert "-" in result
        assert "%" in result

    def test_rsi_out_of_bounds(self):
        """RSI value out of normal bounds (edge case)."""
        # RSI should be 0-100, but test outside
        result = format_rsi_value(150.0)
        assert "150,00" in result

    def test_symbol_lowercase(self):
        """Format lowercase symbol."""
        result = format_symbol_display("btcusdt")
        assert result == "btcusdt"  # No match (case-sensitive)

    def test_timeframe_case_sensitive(self):
        """Timeframe format is case-sensitive."""
        result = format_timeframe_display("1H")
        assert result == "1H"  # No match (should be lowercase)
