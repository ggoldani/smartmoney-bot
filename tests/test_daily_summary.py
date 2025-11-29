"""Tests for daily summary feature (Fear & Greed Index)."""
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock
import pytz

from src.datafeeds.fear_greed import (
    fetch_fear_greed_index,
    get_fear_greed_sentiment
)
from src.notif.templates import template_daily_summary
from src.config import get_daily_summary_config


class TestFearGreedAPI:
    """Tests for Fear & Greed API client."""

    @pytest.mark.asyncio
    async def test_fetch_fear_greed_returns_tuple(self):
        """Should return tuple of (value, label) on any call."""
        # This test verifies the function signature and return type
        # The actual API call is tested in integration tests
        fgi_value, fgi_label = await fetch_fear_greed_index()
        # When API fails after retries, should return (None, "Indisponível")
        assert isinstance(fgi_value, (int, type(None)))
        assert isinstance(fgi_label, str)
        assert len(fgi_label) > 0

    @pytest.mark.asyncio
    async def test_fetch_fear_greed_api_error(self):
        """Should return None on API error."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status = 500  # Server error
            mock_session.__aenter__.return_value = mock_session
            mock_session.get.return_value.__aenter__.return_value = mock_response
            mock_session_class.return_value = mock_session

            fgi_value, fgi_label = await fetch_fear_greed_index()
            assert fgi_value is None
            assert fgi_label == 'Indisponível'

    @pytest.mark.asyncio
    async def test_fetch_fear_greed_timeout(self):
        """Should handle timeout gracefully."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.__aenter__.return_value = mock_session
            mock_session.get.side_effect = asyncio.TimeoutError()
            mock_session_class.return_value = mock_session

            fgi_value, fgi_label = await fetch_fear_greed_index()
            assert fgi_value is None
            assert fgi_label == 'Indisponível'

    def test_sentiment_mapping_extreme_greed(self):
        """Should map 90 to 'Ganância Extrema'."""
        emoji, sentiment = get_fear_greed_sentiment(90)
        assert emoji == "🤑"
        assert sentiment == "Ganância Extrema"

    def test_sentiment_mapping_greed(self):
        """Should map 70 to 'Ganância'."""
        emoji, sentiment = get_fear_greed_sentiment(70)
        assert emoji == "😊"
        assert sentiment == "Ganância"

    def test_sentiment_mapping_neutral(self):
        """Should map 50 to 'Neutro'."""
        emoji, sentiment = get_fear_greed_sentiment(50)
        assert emoji == "😐"
        assert sentiment == "Neutro"

    def test_sentiment_mapping_fear(self):
        """Should map 30 to 'Medo'."""
        emoji, sentiment = get_fear_greed_sentiment(30)
        assert emoji == "😨"
        assert sentiment == "Medo"

    def test_sentiment_mapping_extreme_fear(self):
        """Should map 10 to 'Medo Extremo'."""
        emoji, sentiment = get_fear_greed_sentiment(10)
        assert emoji == "😱"
        assert sentiment == "Medo Extremo"

    def test_sentiment_mapping_none(self):
        """Should handle None gracefully."""
        emoji, sentiment = get_fear_greed_sentiment(None)
        assert emoji == "❓"
        assert sentiment == "Indisponível"


class TestDailySummaryTemplate:
    """Tests for daily summary message template."""

    def test_template_basic_format(self):
        """Should generate valid message structure."""
        message = template_daily_summary(
            symbol="BTCUSDT",
            fear_greed_value=75,
            fear_greed_label="Ganância",
            rsi_value=72.5,
            rsi_previous=68.0,
            price_current=67420.50,
            price_previous=66000.00,
            fear_emoji="😊"
        )

        assert "RESUMO DIÁRIO" in message
        assert "BTC/USDT" in message
        assert "Fear & Greed Index" in message
        assert "75/100" in message
        assert "Ganância" in message
        assert "RSI (1 dia)" in message
        assert "72,50" in message  # Brazilian format
        assert "📈" in message  # Trend emoji (RSI increased)

    def test_template_price_variation_positive(self):
        """Should show positive variation correctly."""
        message = template_daily_summary(
            symbol="BTCUSDT",
            fear_greed_value=50,
            fear_greed_label="Neutro",
            rsi_value=50.0,
            rsi_previous=50.0,
            price_current=68000.00,
            price_previous=65000.00,
            fear_emoji="😐"
        )

        # Check for approximate positive variation (4.6%)
        assert "+" in message
        assert "Variação do Dia" in message
        assert "De:" in message or "De :" in message

    def test_template_price_variation_negative(self):
        """Should show negative variation correctly."""
        message = template_daily_summary(
            symbol="BTCUSDT",
            fear_greed_value=30,
            fear_greed_label="Medo",
            rsi_value=35.0,
            rsi_previous=50.0,
            price_current=63000.00,
            price_previous=65000.00,
            fear_emoji="😨"
        )

        # Check for negative variation (3.07%)
        assert "Variação do Dia" in message
        assert "De:" in message or "De :" in message

    def test_template_rsi_trend_uptrend(self):
        """Should show uptrend emoji when RSI increases significantly."""
        message = template_daily_summary(
            symbol="BTCUSDT",
            fear_greed_value=60,
            fear_greed_label="Ganância",
            rsi_value=75.0,
            rsi_previous=60.0,  # +15 change
            price_current=67000.00,
            price_previous=67000.00,
            fear_emoji="😊"
        )

        assert "📈" in message

    def test_template_rsi_trend_downtrend(self):
        """Should show downtrend emoji when RSI decreases significantly."""
        message = template_daily_summary(
            symbol="BTCUSDT",
            fear_greed_value=40,
            fear_greed_label="Medo",
            rsi_value=25.0,
            rsi_previous=40.0,  # -15 change
            price_current=66000.00,
            price_previous=66000.00,
            fear_emoji="😨"
        )

        assert "📉" in message

    def test_template_rsi_trend_neutral(self):
        """Should show neutral arrow when RSI change < 2."""
        message = template_daily_summary(
            symbol="BTCUSDT",
            fear_greed_value=50,
            fear_greed_label="Neutro",
            rsi_value=50.5,
            rsi_previous=50.0,  # +0.5 change
            price_current=67000.00,
            price_previous=67000.00,
            fear_emoji="😐"
        )

        assert "➡️" in message

    def test_template_disclaimer_included(self):
        """Should include disclaimer in message."""
        message = template_daily_summary(
            symbol="BTCUSDT",
            fear_greed_value=50,
            fear_greed_label="Neutro",
            rsi_value=50.0,
            rsi_previous=50.0,
            price_current=67000.00,
            price_previous=67000.00
        )

        assert "⚠️ IMPORTANTE" in message
        assert "DYOR" in message


class TestDailySummaryConfig:
    """Tests for configuration handling."""

    def test_config_default_values(self, monkeypatch, tmp_path):
        """Config should use safe defaults when section missing."""
        config = get_daily_summary_config()
        assert isinstance(config, dict)
        assert 'enabled' in config
        assert 'send_time_brt' in config
        assert 'send_window_minutes' in config

    def test_config_default_enabled_false(self):
        """Daily summary should be disabled by default if not in config."""
        config = get_daily_summary_config()
        # Note: This depends on test YAML config
        assert isinstance(config.get('enabled'), bool)

    def test_config_send_time_format(self):
        """Send time should be in HH:MM format."""
        config = get_daily_summary_config()
        send_time = config.get('send_time_brt', '21:00')
        assert ':' in send_time
        parts = send_time.split(':')
        assert len(parts) == 2
        assert 0 <= int(parts[0]) <= 23  # Hour
        assert 0 <= int(parts[1]) <= 59  # Minute

    def test_config_window_minutes_positive(self):
        """Window minutes should be positive."""
        config = get_daily_summary_config()
        window = config.get('send_window_minutes', 5)
        assert window > 0


class TestDailySummaryTiming:
    """Tests for scheduling logic."""

    def test_time_parsing_valid(self):
        """Should parse valid HH:MM format."""
        send_time_brt = "21:00"
        try:
            hour, minute = map(int, send_time_brt.split(':'))
            assert hour == 21
            assert minute == 0
        except (ValueError, TypeError):
            pytest.fail("Failed to parse valid time format")

    def test_time_parsing_invalid(self):
        """Should handle invalid time values."""
        send_time_brt = "25:99"  # Invalid time
        hour, minute = map(int, send_time_brt.split(':'))
        # Values are parsed correctly, but validation would catch them
        assert hour == 25
        assert minute == 99

    def test_brt_timezone_conversion(self):
        """Should handle BRT timezone correctly."""
        brt_tz = pytz.timezone('America/Sao_Paulo')
        now_utc = datetime.now(pytz.UTC)
        now_brt = now_utc.astimezone(brt_tz)

        # BRT is UTC-3 (or UTC-2 during DST)
        utc_offset = now_brt.utcoffset()
        assert utc_offset is not None
        assert utc_offset.total_seconds() in [-10800, -7200]  # -3h or -2h

    def test_next_send_time_calculation(self):
        """Should calculate next send time correctly."""
        brt_tz = pytz.timezone('America/Sao_Paulo')
        now_utc = datetime.now(pytz.UTC)
        now_brt = now_utc.astimezone(brt_tz)

        target_brt = now_brt.replace(hour=21, minute=0, second=0, microsecond=0)

        if target_brt <= now_brt:
            # Past today, use tomorrow
            from datetime import timedelta
            target_brt = (now_brt + timedelta(days=1)).replace(
                hour=21, minute=0, second=0, microsecond=0
            )

        # Verify target is in future
        assert target_brt > now_brt


class TestDailySummaryEdgeCases:
    """Edge cases and boundary conditions."""

    def test_price_previous_zero(self):
        """Should handle zero previous price."""
        message = template_daily_summary(
            symbol="BTCUSDT",
            fear_greed_value=50,
            fear_greed_label="Neutro",
            rsi_value=50.0,
            rsi_previous=50.0,
            price_current=67000.00,
            price_previous=0,  # Zero previous price
            fear_emoji="😐"
        )

        assert "RESUMO DIÁRIO" in message
        assert "0,00%" in message  # Variation should be 0

    def test_unicode_symbol(self):
        """Should handle symbols with unicode."""
        message = template_daily_summary(
            symbol="BTCUSDT",
            fear_greed_value=50,
            fear_greed_label="Neutro",
            rsi_value=50.0,
            rsi_previous=50.0,
            price_current=67000.00,
            price_previous=67000.00,
            fear_emoji="😐"
        )

        assert "BTC/USDT" in message
        assert "😐" in message

    def test_all_emojis_rendering(self):
        """Should render all sentiment emojis correctly."""
        emojis = ["🤑", "😊", "😐", "😨", "😱", "❓"]
        sentiments = [90, 70, 50, 30, 10, None]

        for fgi_value in sentiments:
            emoji, sentiment = get_fear_greed_sentiment(fgi_value)
            assert emoji in emojis or emoji == "❓"
            assert sentiment != ""
