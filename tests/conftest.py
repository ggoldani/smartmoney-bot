"""Shared test fixtures and configuration."""
import os
import tempfile
from pathlib import Path
from typing import List, Dict
import pytest
import yaml
from datetime import datetime


@pytest.fixture
def sample_candles() -> List[float]:
    """Sample closing prices for RSI calculation (14+ values)."""
    return [
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
        45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.00, 46.00,
        46.00, 46.12, 46.15, 46.14, 46.10, 46.16, 46.16, 46.16
    ]


@pytest.fixture
def extreme_uptrend_candles() -> List[float]:
    """Candles in extreme uptrend (should trigger high RSI)."""
    return [
        40.0, 40.5, 41.0, 41.5, 42.0, 42.5, 43.0, 43.5,
        44.0, 44.5, 45.0, 45.5, 46.0, 46.5, 47.0, 47.5,
        48.0, 48.5, 49.0, 49.5, 50.0, 50.5, 51.0, 51.5
    ]


@pytest.fixture
def extreme_downtrend_candles() -> List[float]:
    """Candles in extreme downtrend (should trigger low RSI)."""
    return [
        50.0, 49.5, 49.0, 48.5, 48.0, 47.5, 47.0, 46.5,
        46.0, 45.5, 45.0, 44.5, 44.0, 43.5, 43.0, 42.5,
        42.0, 41.5, 41.0, 40.5, 40.0, 39.5, 39.0, 38.5
    ]


@pytest.fixture
def flat_candles() -> List[float]:
    """Flat candles (low volatility, neutral RSI)."""
    return [
        45.0, 45.1, 45.05, 45.08, 45.02, 45.10, 45.06, 45.09,
        45.07, 45.11, 45.05, 45.09, 45.08, 45.10, 45.07, 45.09,
        45.08, 45.09, 45.08, 45.09, 45.08, 45.09, 45.08, 45.09
    ]


@pytest.fixture
def test_config_yaml(tmp_path: Path) -> Path:
    """Create a temporary test config YAML file."""
    config = {
        'bot': {
            'tier': 'free',
            'version': '2.1.0',
            'name': 'SmartMoney Brasil Test'
        },
        'telegram': {
            'enabled': True
        },
        'symbols': [
            {
                'name': 'BTCUSDT',
                'timeframes': ['1h', '4h', '1d', '1w']
            }
        ],
        'indicators': {
            'rsi': {
                'period': 14,
                'overbought': 70,
                'oversold': 30,
                'extreme_overbought': 85,
                'extreme_oversold': 15,
                'recovery_zone_lower': 35,
                'recovery_zone_upper': 65,
                'timeframes': ['1h', '4h', '1d']
            },
            'breakout': {
                'timeframes': ['1d', '1w'],
                'margin_percent': 0.1
            }
        },
        'alerts': {
            'timezone': 'America/Sao_Paulo',
            'throttling': {
                'max_alerts_per_hour': 20
            },
            'circuit_breaker': {
                'max_alerts_per_minute': 5
            }
        }
    }

    config_file = tmp_path / 'test_config.yaml'
    with open(config_file, 'w', encoding='utf-8') as f:
        yaml.dump(config, f)

    return config_file


@pytest.fixture
def test_env_vars(monkeypatch, test_config_yaml: Path):
    """Set test environment variables."""
    monkeypatch.setenv('BOT_TOKEN', 'test_token_123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11')
    monkeypatch.setenv('CHANNEL_CHAT_ID', '-1001234567890')
    monkeypatch.setenv('ADMIN_CHANNEL_ID', '-1009876543210')
    monkeypatch.setenv('CONFIG_FILE', str(test_config_yaml))
    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
    monkeypatch.setenv('DB_URL', 'sqlite:///:memory:')


@pytest.fixture
def sample_candle_record() -> Dict:
    """Sample candle record as returned from database."""
    return {
        'symbol': 'BTCUSDT',
        'interval': '1h',
        'open_time': 1700000000,
        'close_time': 1700003600,
        'open': 45000.50,
        'close': 45123.75,
        'high': 45200.00,
        'low': 44950.25,
        'volume': 1500.50,
        'quote_asset_volume': 67500000.00,
        'trades': 5000,
        'taker_buy_base_asset_volume': 750.25,
        'taker_buy_quote_asset_volume': 33750000.00,
        'is_closed': True
    }


@pytest.fixture
def brt_timezone():
    """Return BRT timezone name."""
    return 'America/Sao_Paulo'
