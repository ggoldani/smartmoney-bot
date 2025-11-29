# Tests - SmartMoney Bot

Test suite for critical logic components: indicators, formatting, configuration, and throttling.

## Setup

### 1. Install Test Dependencies

```bash
pip install -r requirements-dev.txt
```

This installs:
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities

### 2. Run Tests

From the `smartmoney-bot/` directory:

```bash
# Run all tests
PYTHONPATH=. pytest tests/ -v

# Run specific test file
PYTHONPATH=. pytest tests/test_indicators.py -v

# Run specific test class
PYTHONPATH=. pytest tests/test_indicators.py::TestRSICalculation -v

# Run specific test
PYTHONPATH=. pytest tests/test_indicators.py::TestRSICalculation::test_rsi_extreme_uptrend -v
```

## Coverage

```bash
# Generate coverage report (HTML)
PYTHONPATH=. pytest tests/ --cov=src --cov-report=html

# View report
open htmlcov/index.html
```

## Test Structure

```
tests/
├── __init__.py              # Package marker
├── conftest.py              # Shared fixtures (candles, config, env vars)
├── test_indicators.py       # RSI & breakout detection tests
├── test_formatter.py        # Brazilian formatting tests
├── test_config.py           # Configuration loading & validation tests
├── test_throttle.py         # Rate limiting & circuit breaker tests
└── README.md                # This file
```

## What's Tested

### `test_indicators.py` (~35 tests)
- **RSI Calculation:**
  - Insufficient data handling
  - Uptrend/downtrend detection
  - Flat market behavior
  - Edge cases (all gains, all losses, zero prices)

- **Breakout Detection:**
  - Bull breakout (0.1% margin)
  - Bear breakout (0.1% margin)
  - Boundary conditions
  - Large price moves

### `test_formatter.py` (~40 tests)
- **Price Formatting:** `$1.234,56` (dot=thousands, comma=decimal)
- **Percentage Formatting:** `0,15%`
- **RSI Formatting:** `75,30`
- **DateTime Formatting:** `11/11/2025 11:30 BRT` (with UTC→BRT conversion)
- **Symbol Display:** `BTCUSDT` → `BTC/USDT`
- **Timeframe Display:** `1h` → `1 hora` (Portuguese)

### `test_config.py` (~25 tests)
- **YAML Loading:** File handling, required sections
- **Dot Notation Access:** `config.get('indicators.rsi.period')`
- **RSI Config Validation:**
  - Safe defaults for invalid values
  - Range validation (period: 2-100, thresholds: 0-100)
  - Type checking
  - Missing sections fallback
- **Helper Functions:** `get_bot_version()`, `get_symbols()`, etc.

### `test_throttle.py` (~30 tests)
- **AlertHistory:**
  - Timestamp recording
  - Counting alerts in time windows (1min, 60min, custom)
  - Capacity management (maxlen=100)

- **AlertThrottler:**
  - Hourly limit enforcement (20/hour default)
  - Per-minute limit (5/min, circuit breaker)
  - Condition-specific tracking
  - Consolidation trigger detection
  - Statistics generation

- **Real-world Scenarios:**
  - Normal trading day (20/hour limit)
  - Spam prevention (rapid-fire alerts)
  - Multiple timeframe combinations
  - Recovery after throttle
  - Edge cases (zero/negative limits, Unicode keys)

## Example Test Run

```bash
$ PYTHONPATH=. pytest tests/test_indicators.py::TestRSICalculation::test_rsi_extreme_uptrend -v

tests/test_indicators.py::TestRSICalculation::test_rsi_extreme_uptrend PASSED [100%]

======================== 1 passed in 0.12s ========================
```

## Fixtures (conftest.py)

Shared fixtures available to all tests:

| Fixture | Description |
|---------|-------------|
| `sample_candles` | 24 normal closing prices |
| `extreme_uptrend_candles` | 24 prices in uptrend (for high RSI) |
| `extreme_downtrend_candles` | 24 prices in downtrend (for low RSI) |
| `flat_candles` | 24 prices with low volatility (neutral RSI) |
| `test_config_yaml` | Temp YAML config file |
| `test_env_vars` | Set test environment variables |
| `sample_candle_record` | Sample DB candle record |
| `brt_timezone` | BRT timezone string |

## Pre-Commit

Run before committing changes:

```bash
PYTHONPATH=. pytest tests/ -v && echo "✓ All tests passed"
```

Or use in CI/CD pipeline.

## Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: No module named 'src'` | Run with `PYTHONPATH=.` |
| `Fixture 'test_env_vars' not found` | Ensure `conftest.py` is in `tests/` directory |
| `ImportError: cannot import name 'pytest'` | Run `pip install -r requirements-dev.txt` |
| `FAILED - assert result == expected` | Check RSI calculation precision (rounded to 2 decimals) |
| Timezone tests fail | Tests assume system running in UTC or BRT-compatible timezone |

## Target Coverage

- **Indicators:** 90%+ (RSI, breakouts fully tested)
- **Formatter:** 95%+ (all functions covered)
- **Config:** 85%+ (validation logic tested)
- **Throttle:** 95%+ (all scenarios covered)

**Overall target:** 65-70% codebase coverage (focus on critical logic, skip async orchestration)

## What's NOT Tested

Intentionally skipped (complex async/integration):
- WebSocket connection (`binance_ws.py`)
- Telegram API calls (`telegram_bot.py`)
- Alert engine state management (`rules/engine.py`)
- Database ORM queries (`storage/repo.py`)

These require integration tests or manual testing with mocked external services.

## Adding New Tests

1. Create test file in `tests/` directory: `test_new_module.py`
2. Import fixtures from `conftest.py` as function arguments
3. Follow naming: `test_<what_being_tested>_<scenario>`
4. Use descriptive docstrings
5. Run: `PYTHONPATH=. pytest tests/test_new_module.py -v`

Example:

```python
def test_new_feature_success(sample_candles):
    """New feature should work with sample data."""
    result = new_function(sample_candles)
    assert result is not None
    assert len(result) > 0
```

## References

- [pytest docs](https://docs.pytest.org/)
- [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [pytest coverage](https://pytest-cov.readthedocs.io/)
