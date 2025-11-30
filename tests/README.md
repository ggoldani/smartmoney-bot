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
├── conftest.py              # Shared fixtures (candles, config, env vars, mock ORM)
├── test_indicators.py       # RSI & breakout detection tests
├── test_formatter.py        # Brazilian formatting tests
├── test_config.py           # Configuration loading & validation tests
├── test_throttle.py         # Rate limiting & circuit breaker tests
├── test_daily_summary.py    # Fear & Greed Index & daily summary tests
├── test_divergence.py       # RSI divergence detection tests (40 tests)
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

### `test_daily_summary.py` (33 tests) ✅
- **Fear & Greed API (`TestFearGreedAPI`, 9 tests):**
  - API return type validation (tuple: value + label)
  - HTTP error handling (5xx server errors)
  - Timeout handling (graceful fallback)
  - Sentiment mapping (emoji + Portuguese labels): Ganância Extrema, Ganância, Neutro, Medo, Medo Extremo
  - None value handling

- **Daily Summary Template (`TestDailySummaryTemplate`, 9 tests):**
  - Message structure validation (headers, sections, "RESUMO DIÁRIO", "Fear & Greed Index", "RSI (Múltiplos Timeframes)")
  - Multiple timeframes display (1D, 1W, 1M with values)
  - **RSI trend detection (ALTA for >50, BAIXA for <50) with emojis (📈📉)**
  - **Mixed trends across timeframes** (1D ALTA, 1W BAIXA, 1M ALTA)
  - Price variation calculation (open/close, not previous day)
  - Positive/negative variation (+/-%)
  - Zero variation handling (same open/close price)
  - Timestamp formatting (BRT timezone)
  - Disclaimer inclusion

- **Configuration (`TestDailySummaryConfig`, 4 tests):**
  - Default values (enabled, send_time_brt: "21:01", send_window_minutes: 1)
  - Safe fallbacks when config missing
  - Time format validation (HH:MM)
  - Window minutes validation (positive)

- **Scheduling & Timing (`TestDailySummaryTiming`, 4 tests):**
  - HH:MM format parsing
  - Invalid time value handling
  - BRT timezone conversion (UTC-3/-2 offset)
  - Next send time calculation

- **Edge Cases (`TestDailySummaryEdgeCases`, 7 tests):**
  - **Zero open price handling** (variation = 0)
  - Unicode symbol handling (BTC/USDT)
  - All sentiment emoji rendering (🤑😊😐😨😱❓)
  - **RSI boundary at 50 (=50 is BAIXA, >50.1 is ALTA)**
  - **Large price values** ($100.000,00 formatting)
  - **Very small price variations** (fractions of percent)

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
| `mock_candle` | Factory for Mock Candle ORM objects (spec=Candle, with `is_closed` property) |

## Pre-Commit

Run before committing changes:

```bash
# Run all tests (203 tests)
PYTHONPATH=. pytest tests/ -v

# Or run specific test file
PYTHONPATH=. pytest tests/test_divergence.py -v  # 40 divergence tests

# With coverage report
PYTHONPATH=. pytest tests/ -v --cov=src --cov-report=term-missing

# Quick check (pass/fail only)
PYTHONPATH=. pytest tests/ -q && echo "✓ All tests passed"
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
- **Daily Summary:** 90%+ (API, templates, scheduling, edge cases)
- **Divergence:** 100%+ (pivot detection, RSI comparison, database mocking, edge cases)

**Overall target:** 65-70% codebase coverage (focus on critical logic, skip async orchestration)

**Total tests:** **203** (35 indicators + 40 formatter + 25 config + 30 throttle + 33 daily summary + **40 divergence**) ✅

## What's NOT Tested

Intentionally skipped (complex async/integration):
- WebSocket connection (`binance_ws.py`)
- Telegram API calls (`telegram_bot.py`)
- Alert engine async task scheduling (`rules/engine.py` - `_send_daily_summary()` and `_process_divergences()` task loop integration with asyncio)
- Database ORM queries (`storage/repo.py` - `get_previous_closed_candle()` actual DB queries)
- Real CoinMarketCap API calls (mocked in unit tests via aiohttp mocks)

These require integration tests or manual testing with mocked external services.

**Note:** Divergence *core logic (pivot detection, RSI comparison, divergence validation) and database fetching patterns* are **fully unit tested (40 tests, 100% coverage)**. Only the async `_process_divergences()` loop integration and state persistence across restarts require integration testing.

**Note:** Daily Summary *template formatting (RSI 1D/1W/1M ALTA/BAIXA, Fear & Greed emoji, price variation), configuration validation (send_time_brt: "21:01", window_minutes: 1), timing logic (21:01 BRT scheduling), and Fear & Greed sentiment mapping* are **fully unit tested (33 tests)**. Only the async task loop and actual database queries in `AlertEngine._send_daily_summary()` require integration testing.

### `test_divergence.py` (40 tests) ✅ NEW
- **Bullish Pivot Detection (`TestBullishPivot`, 5 tests):**
  - Valid bullish pivot (middle candle is lowest of 3)
  - Invalid pivots (not enough candles, middle not lowest)
  - Edge cases (equal lows, single candle)

- **Bearish Pivot Detection (`TestBearishPivot`, 5 tests):**
  - Valid bearish pivot (middle candle is highest of 3)
  - Invalid pivots (not enough candles, middle not highest)
  - Edge cases (equal highs, single candle)

- **Divergence Detection (`TestDetectDivergence`, 13 tests):**
  - BULLISH: price↓ but RSI↑ (both <50) = bullish divergence
  - BEARISH: price↑ but RSI↓ (both >50) = bearish divergence
  - Invalid divergences (wrong RSI range, same direction)
  - Edge cases (RSI=50 boundary, zero prices, extreme values)

- **RSI Calculation (`TestCalculateRSIForCandles`, 5 tests):**
  - Incremental RSI (None for first 14 candles, then calculated)
  - Uptrend/downtrend scenarios
  - Flat market behavior

- **Database Fetching (`TestFetchCandlesForDivergence`, 4 tests):**
  - Mock SessionLocal context manager (ORM mocking)
  - Query filters (symbol, interval, ordered by open_time DESC, LIMIT)
  - Empty result handling
  - Database error handling

- **Integration Tests (`TestDivergenceIntegration`, 2 tests):**
  - Multiple consecutive pivots (independent per timeframe)
  - Timeframe independence (4h, 1d, 1w diverge separately)

- **Edge Cases (`TestDivergenceEdgeCases`, 6 tests):**
  - RSI=50 boundary (dividing point between ALTA/BAIXA)
  - Zero opening price (variation calc)
  - Extreme RSI values (0, 100, negative)
  - Large price swings
  - Precision rounding

**Mock Patterns:**
- `@patch('src.storage.db.SessionLocal')` for database (NOT divergence.py)
- Context manager mocking: `__enter__` returns mock session
- `.query(Candle).filter(...).order_by(...).limit(...)` chain mocking

**Coverage:** 100% of `divergence.py` module, all edge cases covered, database mocking prevents integration dependencies

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
