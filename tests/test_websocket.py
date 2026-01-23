"""Test suite for WebSocket functionality (multi-symbol support)."""
import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
import urllib.parse
import time

from src.datafeeds.binance_ws import (
    normalize_kline,
    _multi_stream_url,
    _kline_stream,
    _should_save_candle,
    BINANCE_WS_COMBINED,
    SAVE_THROTTLE_SECONDS
)


# ==================== TESTS: NORMALIZE KLINE ====================

class TestNormalizeKline:
    """Test kline normalization extracting symbol from payload."""

    def test_normalize_kline_extracts_symbol_from_payload(self):
        """Should extract symbol from payload k['s'] field."""
        data = {
            "k": {
                "s": "btcusdt",  # Lowercase from Binance
                "i": "1h",
                "t": 1609459200000,
                "T": 1609462800000,
                "o": "100.0",
                "h": "105.0",
                "l": "95.0",
                "c": "102.0",
                "v": "1000.0",
                "x": True
            }
        }
        
        result = normalize_kline(data)
        
        assert result["symbol"] == "BTCUSDT"  # Should be uppercase
        assert result["interval"] == "1h"
        assert result["open_time"] == 1609459200000
        assert result["close_time"] == 1609462800000
        assert result["open"] == 100.0
        assert result["high"] == 105.0
        assert result["low"] == 95.0
        assert result["close"] == 102.0
        assert result["volume"] == 1000.0
        assert result["is_closed"] is True

    def test_normalize_kline_uppercase_symbol(self):
        """Should convert symbol to uppercase."""
        data = {
            "k": {
                "s": "paxgusdt",
                "i": "4h",
                "t": 1609459200000,
                "T": 1609473600000,
                "o": "2000.0",
                "h": "2010.0",
                "l": "1990.0",
                "c": "2005.0",
                "v": "500.0",
                "x": False
            }
        }
        
        result = normalize_kline(data)
        
        assert result["symbol"] == "PAXGUSDT"
        assert result["is_closed"] is False

    def test_normalize_kline_different_intervals(self):
        """Should handle different interval types."""
        intervals = ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]
        
        for interval in intervals:
            data = {
                "k": {
                    "s": "btcusdt",
                    "i": interval,
                    "t": 1609459200000,
                    "T": 1609459200000,
                    "o": "100.0",
                    "h": "100.0",
                    "l": "100.0",
                    "c": "100.0",
                    "v": "0.0",
                    "x": True
                }
            }
            
            result = normalize_kline(data)
            assert result["interval"] == interval

    def test_normalize_kline_numeric_types(self):
        """Should convert all numeric fields to correct types."""
        data = {
            "k": {
                "s": "btcusdt",
                "i": "1h",
                "t": "1609459200000",  # String from JSON
                "T": "1609462800000",
                "o": "100.5",
                "h": "105.75",
                "l": "95.25",
                "c": "102.0",
                "v": "1234.567",
                "x": "true"  # String boolean
            }
        }
        
        result = normalize_kline(data)
        
        assert isinstance(result["open_time"], int)
        assert isinstance(result["close_time"], int)
        assert isinstance(result["open"], float)
        assert isinstance(result["high"], float)
        assert isinstance(result["low"], float)
        assert isinstance(result["close"], float)
        assert isinstance(result["volume"], float)
        assert isinstance(result["is_closed"], bool)


# ==================== TESTS: MULTI STREAM URL ====================

class TestMultiStreamUrl:
    """Test multi-symbol stream URL construction."""

    def test_multi_stream_url_single_symbol(self):
        """Should build URL for single symbol with multiple timeframes."""
        config = [{"name": "BTCUSDT", "timeframes": ["1h", "4h", "1d"]}]
        
        url = _multi_stream_url(config)
        
        assert url.startswith(BINANCE_WS_COMBINED)
        assert "streams=" in url
        
        # Parse query string
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        streams = params["streams"][0].split("/")
        
        assert "btcusdt@kline_1h" in streams
        assert "btcusdt@kline_4h" in streams
        assert "btcusdt@kline_1d" in streams
        assert len(streams) == 3

    def test_multi_stream_url_multiple_symbols(self):
        """Should build URL for multiple symbols."""
        config = [
            {"name": "BTCUSDT", "timeframes": ["1h", "4h"]},
            {"name": "PAXGUSDT", "timeframes": ["4h", "1d"]}
        ]
        
        url = _multi_stream_url(config)
        
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        streams = params["streams"][0].split("/")
        
        assert "btcusdt@kline_1h" in streams
        assert "btcusdt@kline_4h" in streams
        assert "paxgusdt@kline_4h" in streams
        assert "paxgusdt@kline_1d" in streams
        assert len(streams) == 4

    def test_multi_stream_url_lowercase_symbols(self):
        """Should convert symbols to lowercase in URL."""
        config = [{"name": "BTCUSDT", "timeframes": ["1h"]}]
        
        url = _multi_stream_url(config)
        
        assert "btcusdt" in url.lower()
        assert "BTCUSDT" not in url  # Should be lowercase

    def test_multi_stream_url_empty_config(self):
        """Should handle empty config gracefully."""
        config = []
        
        url = _multi_stream_url(config)
        
        assert url.startswith(BINANCE_WS_COMBINED)
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        # When empty, streams will be empty string
        if "streams" in params:
            streams = params["streams"][0].split("/")
            assert streams == [""] or streams == []
        else:
            # If no streams param, that's also valid (empty config)
            assert True

    def test_multi_stream_url_single_timeframe(self):
        """Should handle single timeframe per symbol."""
        config = [
            {"name": "BTCUSDT", "timeframes": ["1d"]},
            {"name": "ETHUSDT", "timeframes": ["1w"]}
        ]
        
        url = _multi_stream_url(config)
        
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        streams = params["streams"][0].split("/")
        
        assert "btcusdt@kline_1d" in streams
        assert "ethusdt@kline_1w" in streams
        assert len(streams) == 2

    def test_multi_stream_url_many_timeframes(self):
        """Should handle many timeframes for one symbol."""
        config = [{"name": "BTCUSDT", "timeframes": ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]}]
        
        url = _multi_stream_url(config)
        
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        streams = params["streams"][0].split("/")
        
        assert len(streams) == 8
        assert all("btcusdt@kline_" in s for s in streams)

    def test_multi_stream_url_special_characters(self):
        """Should handle symbols with special characters correctly."""
        config = [{"name": "1000SHIBUSDT", "timeframes": ["1h"]}]
        
        url = _multi_stream_url(config)
        
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        streams = params["streams"][0].split("/")
        
        assert "1000shibusdt@kline_1h" in streams


# ==================== TESTS: KLINE STREAM ====================

class TestKlineStream:
    """Test kline stream URL construction."""

    def test_kline_stream_lowercase(self):
        """Should convert symbol to lowercase."""
        result = _kline_stream("BTCUSDT", "1h")
        assert result == "btcusdt@kline_1h"

    def test_kline_stream_different_intervals(self):
        """Should handle different intervals."""
        intervals = ["1m", "5m", "15m", "1h", "4h", "1d", "1w", "1M"]
        for interval in intervals:
            result = _kline_stream("BTCUSDT", interval)
            assert result == f"btcusdt@kline_{interval}"

    def test_kline_stream_special_symbols(self):
        """Should handle special symbols."""
        result = _kline_stream("1000SHIBUSDT", "1h")
        assert result == "1000shibusdt@kline_1h"


# ==================== TESTS: SHOULD SAVE CANDLE ====================

class TestShouldSaveCandle:
    """Test candle save throttling logic."""

    def test_should_save_closed_candle(self):
        """Should always save closed candles."""
        event = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "open_time": 1609459200000,
            "is_closed": True
        }
        assert _should_save_candle(event) is True

    def test_should_save_open_candle_first_time(self):
        """Should save open candle on first check."""
        event = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "open_time": 1609459200000,
            "is_closed": False
        }
        assert _should_save_candle(event) is True

    def test_should_not_save_open_candle_within_throttle(self):
        """Should not save open candle within throttle period."""
        event = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "open_time": 1609459200000,
            "is_closed": False
        }
        # First save
        _should_save_candle(event)
        # Immediately try again - should be throttled
        assert _should_save_candle(event) is False

    def test_should_save_open_candle_after_throttle(self):
        """Should save open candle after throttle period."""
        event = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "open_time": 1609459200000,
            "is_closed": False
        }
        # First save
        _should_save_candle(event)
        # Wait for throttle period
        time.sleep(SAVE_THROTTLE_SECONDS + 0.1)
        # Should save again
        assert _should_save_candle(event) is True

    def test_should_save_different_candles_independently(self):
        """Should track throttle per candle independently."""
        event1 = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "open_time": 1609459200000,
            "is_closed": False
        }
        event2 = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "open_time": 1609462800000,  # Different candle
            "is_closed": False
        }
        # Save first candle
        _should_save_candle(event1)
        # Second candle should still save (different key)
        assert _should_save_candle(event2) is True


# ==================== TESTS: INTEGRATION ====================

class TestWebSocketIntegration:
    """Integration tests for WebSocket multi-symbol functionality."""

    def test_normalize_kline_with_multi_symbol_payload(self):
        """Should correctly extract different symbols from payloads."""
        symbols = ["BTCUSDT", "PAXGUSDT", "ETHUSDT"]
        
        for symbol in symbols:
            data = {
                "k": {
                    "s": symbol.lower(),
                    "i": "1h",
                    "t": 1609459200000,
                    "T": 1609462800000,
                    "o": "100.0",
                    "h": "100.0",
                    "l": "100.0",
                    "c": "100.0",
                    "v": "0.0",
                    "x": True
                }
            }
            
            result = normalize_kline(data)
            assert result["symbol"] == symbol

    def test_multi_stream_url_realistic_config(self):
        """Should build URL matching real-world config format."""
        config = [
            {"name": "BTCUSDT", "timeframes": ["1h", "4h", "1d", "1w", "1M"]},
            {"name": "PAXGUSDT", "timeframes": ["4h", "1d", "1w"]}
        ]
        
        url = _multi_stream_url(config)
        
        # Verify structure
        assert url.startswith(BINANCE_WS_COMBINED)
        assert "?" in url
        assert "streams=" in url
        
        # Verify all streams are present
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        streams = params["streams"][0].split("/")
        
        # BTCUSDT: 5 timeframes
        btc_streams = [s for s in streams if "btcusdt" in s]
        assert len(btc_streams) == 5
        
        # PAXGUSDT: 3 timeframes
        paxg_streams = [s for s in streams if "paxgusdt" in s]
        assert len(paxg_streams) == 3
        
        # Total: 8 streams
        assert len(streams) == 8
