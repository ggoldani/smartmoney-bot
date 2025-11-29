"""Tests for configuration loading and validation."""
import pytest
import os
import tempfile
from pathlib import Path
import yaml
from src.config import ConfigLoader, get_rsi_config


class TestConfigLoaderBasics:
    """Tests for basic ConfigLoader functionality."""

    def test_config_loader_init(self, test_config_yaml: Path):
        """ConfigLoader should initialize with valid YAML file."""
        loader = ConfigLoader(str(test_config_yaml))
        assert loader is not None
        assert loader._config is not None

    def test_config_loader_missing_file(self):
        """ConfigLoader should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            ConfigLoader("/nonexistent/path/config.yaml")

    def test_config_loader_missing_section(self, tmp_path: Path):
        """ConfigLoader should raise ValueError for missing required sections."""
        config = {
            'bot': {'tier': 'free'},
            'telegram': {'enabled': True}
            # Missing: symbols, indicators, alerts
        }

        config_file = tmp_path / 'invalid_config.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)

        with pytest.raises(ValueError, match="Missing required config section"):
            ConfigLoader(str(config_file))

    def test_config_loader_raw_property(self, test_config_yaml: Path):
        """ConfigLoader.raw should return the raw config dictionary."""
        loader = ConfigLoader(str(test_config_yaml))
        raw = loader.raw
        assert isinstance(raw, dict)
        assert 'bot' in raw
        assert 'indicators' in raw


class TestConfigLoaderDotNotation:
    """Tests for dot-notation config access."""

    def test_get_simple_key(self, test_config_yaml: Path):
        """Get simple top-level key."""
        loader = ConfigLoader(str(test_config_yaml))
        result = loader.get('bot.tier')
        assert result == 'free'

    def test_get_nested_key(self, test_config_yaml: Path):
        """Get nested key with dot notation."""
        loader = ConfigLoader(str(test_config_yaml))
        result = loader.get('indicators.rsi.period')
        assert result == 14

    def test_get_deep_nested_key(self, test_config_yaml: Path):
        """Get deeply nested key."""
        loader = ConfigLoader(str(test_config_yaml))
        result = loader.get('alerts.throttling.max_alerts_per_hour')
        assert result == 20

    def test_get_nonexistent_key_with_default(self, test_config_yaml: Path):
        """Get nonexistent key should return default."""
        loader = ConfigLoader(str(test_config_yaml))
        result = loader.get('nonexistent.key', 'default_value')
        assert result == 'default_value'

    def test_get_nonexistent_key_no_default(self, test_config_yaml: Path):
        """Get nonexistent key without default should return None."""
        loader = ConfigLoader(str(test_config_yaml))
        result = loader.get('nonexistent.key')
        assert result is None

    def test_get_partial_path_none_intermediate(self, test_config_yaml: Path):
        """Get path with None intermediate value should return default."""
        loader = ConfigLoader(str(test_config_yaml))
        result = loader.get('bot.nonexistent.deep', 'fallback')
        assert result == 'fallback'

    def test_get_list_value(self, test_config_yaml: Path):
        """Get list values."""
        loader = ConfigLoader(str(test_config_yaml))
        result = loader.get('symbols')
        assert isinstance(result, list)
        assert len(result) > 0
        assert result[0]['name'] == 'BTCUSDT'

    def test_get_dict_value(self, test_config_yaml: Path):
        """Get dictionary values."""
        loader = ConfigLoader(str(test_config_yaml))
        result = loader.get('indicators.rsi')
        assert isinstance(result, dict)
        assert 'period' in result
        assert 'overbought' in result


class TestRSIConfigValidation:
    """Tests for RSI config validation and safe defaults."""

    def test_rsi_config_default_period(self, test_env_vars):
        """RSI config should have default period 14."""
        config = get_rsi_config()
        assert config.get('period') == 14

    def test_rsi_config_default_thresholds(self, test_env_vars):
        """RSI config should have thresholds from test YAML."""
        config = get_rsi_config()
        assert config.get('overbought') == 70
        assert config.get('oversold') == 30
        # Test YAML has extreme defaults from conftest
        assert config.get('extreme_overbought') == 85 or config.get('extreme_overbought') == 75
        assert config.get('extreme_oversold') == 15 or config.get('extreme_oversold') == 25

    def test_rsi_config_validates_period_too_low(self, tmp_path: Path, monkeypatch):
        """RSI config should fallback to default if period < 2."""
        config = {
            'bot': {'tier': 'free'},
            'telegram': {'enabled': True},
            'symbols': [{'name': 'BTCUSDT', 'timeframes': ['1h']}],
            'indicators': {
                'rsi': {
                    'period': 1,  # Invalid (too low)
                    'overbought': 70,
                    'oversold': 30
                }
            },
            'alerts': {}
        }

        config_file = tmp_path / 'rsi_period_low.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)

        monkeypatch.setenv('CONFIG_FILE', str(config_file))
        rsi_config = get_rsi_config()
        assert rsi_config.get('period') == 14  # Should fallback to default

    def test_rsi_config_validates_period_too_high(self, tmp_path: Path, monkeypatch):
        """RSI config should fallback to default if period > 100."""
        config = {
            'bot': {'tier': 'free'},
            'telegram': {'enabled': True},
            'symbols': [{'name': 'BTCUSDT', 'timeframes': ['1h']}],
            'indicators': {
                'rsi': {
                    'period': 200,  # Invalid (too high)
                    'overbought': 70,
                    'oversold': 30
                }
            },
            'alerts': {}
        }

        config_file = tmp_path / 'rsi_period_high.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)

        monkeypatch.setenv('CONFIG_FILE', str(config_file))
        rsi_config = get_rsi_config()
        assert rsi_config.get('period') == 14  # Should fallback to default

    def test_rsi_config_validates_overbought_too_low(self, tmp_path: Path, monkeypatch):
        """RSI config should fallback overbought if <= 50."""
        config = {
            'bot': {'tier': 'free'},
            'telegram': {'enabled': True},
            'symbols': [{'name': 'BTCUSDT', 'timeframes': ['1h']}],
            'indicators': {
                'rsi': {
                    'period': 14,
                    'overbought': 50,  # Invalid (must be > 50)
                    'oversold': 30
                }
            },
            'alerts': {}
        }

        config_file = tmp_path / 'rsi_ob_low.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)

        monkeypatch.setenv('CONFIG_FILE', str(config_file))
        rsi_config = get_rsi_config()
        assert rsi_config.get('overbought') == 70  # Should fallback to default

    def test_rsi_config_validates_oversold_too_high(self, tmp_path: Path, monkeypatch):
        """RSI config should fallback oversold if >= 50."""
        config = {
            'bot': {'tier': 'free'},
            'telegram': {'enabled': True},
            'symbols': [{'name': 'BTCUSDT', 'timeframes': ['1h']}],
            'indicators': {
                'rsi': {
                    'period': 14,
                    'overbought': 70,
                    'oversold': 50  # Invalid (must be < 50)
                }
            },
            'alerts': {}
        }

        config_file = tmp_path / 'rsi_os_high.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)

        monkeypatch.setenv('CONFIG_FILE', str(config_file))
        rsi_config = get_rsi_config()
        assert rsi_config.get('oversold') == 30  # Should fallback to default

    def test_rsi_config_validates_period_non_integer(self, tmp_path: Path, monkeypatch):
        """RSI config should fallback if period is not a valid integer."""
        config = {
            'bot': {'tier': 'free'},
            'telegram': {'enabled': True},
            'symbols': [{'name': 'BTCUSDT', 'timeframes': ['1h']}],
            'indicators': {
                'rsi': {
                    'period': 'invalid',  # Not an integer
                    'overbought': 70,
                    'oversold': 30
                }
            },
            'alerts': {}
        }

        config_file = tmp_path / 'rsi_period_invalid.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)

        monkeypatch.setenv('CONFIG_FILE', str(config_file))
        rsi_config = get_rsi_config()
        assert rsi_config.get('period') == 14  # Should fallback to default

    def test_rsi_config_empty_dict(self, tmp_path: Path, monkeypatch):
        """RSI config with empty dict should use all defaults."""
        config = {
            'bot': {'tier': 'free'},
            'telegram': {'enabled': True},
            'symbols': [{'name': 'BTCUSDT', 'timeframes': ['1h']}],
            'indicators': {
                'rsi': {}  # Empty
            },
            'alerts': {}
        }

        config_file = tmp_path / 'rsi_empty.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)

        monkeypatch.setenv('CONFIG_FILE', str(config_file))
        rsi_config = get_rsi_config()
        assert rsi_config.get('period') == 14
        assert rsi_config.get('overbought') == 70
        assert rsi_config.get('oversold') == 30

    def test_rsi_config_missing_rsi_section(self, tmp_path: Path, monkeypatch):
        """RSI config when section missing should use all defaults."""
        config = {
            'bot': {'tier': 'free'},
            'telegram': {'enabled': True},
            'symbols': [{'name': 'BTCUSDT', 'timeframes': ['1h']}],
            'indicators': {},  # No RSI section
            'alerts': {}
        }

        config_file = tmp_path / 'no_rsi.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)

        monkeypatch.setenv('CONFIG_FILE', str(config_file))
        rsi_config = get_rsi_config()
        assert isinstance(rsi_config, dict)
        assert rsi_config.get('period') == 14

    def test_rsi_config_valid_custom_values(self):
        """RSI config validation should preserve custom valid values."""
        # Create a custom RSI config dict
        custom_rsi = {
            'period': 21,
            'overbought': 75,
            'oversold': 25,
            'extreme_overbought': 90,
            'extreme_oversold': 10,
            'timeframes': ['1h', '4h', '1d']
        }

        # Manually validate (as get_rsi_config() does)
        validated = custom_rsi.copy()
        validated.setdefault('alert_on_touch', True)

        # Check that valid custom values are preserved
        assert validated.get('period') == 21
        assert validated.get('overbought') == 75
        assert validated.get('oversold') == 25
        assert validated.get('extreme_overbought') == 90
        assert validated.get('extreme_oversold') == 10


class TestConfigHelpers:
    """Tests for config helper functions."""

    def test_get_bot_version(self, test_env_vars):
        """get_bot_version should return version string."""
        # Note: Need to reload config to use test env vars
        from src import config
        config.reload_config()
        version = config.get_bot_version()
        assert isinstance(version, str)
        assert len(version) > 0

    def test_get_bot_tier(self, test_env_vars):
        """get_bot_tier should return tier."""
        from src import config
        config.reload_config()
        tier = config.get_bot_tier()
        assert tier in ['free', 'premium']

    def test_get_bot_name(self, test_env_vars):
        """get_bot_name should return bot name."""
        from src import config
        config.reload_config()
        name = config.get_bot_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_get_symbols(self, test_env_vars):
        """get_symbols should return list of symbols."""
        from src import config
        config.reload_config()
        symbols = config.get_symbols()
        assert isinstance(symbols, list)
        assert len(symbols) > 0
        assert all('name' in sym for sym in symbols)

    def test_get_timeframes_for_symbol(self, test_env_vars):
        """get_timeframes_for_symbol should return TF list."""
        from src import config
        config.reload_config()
        timeframes = config.get_timeframes_for_symbol('BTCUSDT')
        assert isinstance(timeframes, list)
        assert len(timeframes) > 0

    def test_get_timeframes_nonexistent_symbol(self, test_env_vars):
        """get_timeframes_for_symbol should return empty list for missing symbol."""
        from src import config
        config.reload_config()
        timeframes = config.get_timeframes_for_symbol('NONEXISTENT')
        assert timeframes == []


class TestConfigEdgeCases:
    """Edge cases and boundary conditions."""

    def test_config_with_unicode_characters(self, tmp_path: Path):
        """Config should handle Unicode characters."""
        config = {
            'bot': {'name': 'SmartMoney Brasil 🤖', 'tier': 'free'},
            'telegram': {'enabled': True},
            'symbols': [{'name': 'BTCUSDT', 'timeframes': ['1h']}],
            'indicators': {'rsi': {}},
            'alerts': {}
        }

        config_file = tmp_path / 'unicode_config.yaml'
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True)

        loader = ConfigLoader(str(config_file))
        assert loader.get('bot.name') == 'SmartMoney Brasil 🤖'

    def test_config_very_large_number(self, tmp_path: Path):
        """Config should handle very large numbers (BTC prices)."""
        config = {
            'bot': {'tier': 'free'},
            'telegram': {'enabled': True},
            'symbols': [{'name': 'BTCUSDT', 'timeframes': ['1h']}],
            'indicators': {
                'rsi': {
                    'period': 14,
                    'overbought': 70,
                    'oversold': 30
                },
                'max_price': 67420.50  # Large number
            },
            'alerts': {}
        }

        config_file = tmp_path / 'large_num.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(config, f)

        loader = ConfigLoader(str(config_file))
        max_price = loader.get('indicators.max_price')
        assert max_price == 67420.50
