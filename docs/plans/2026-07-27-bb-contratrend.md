# BB Contratrend Alert — Implementation Plan

> **For implementer:** Use TDD throughout. Write failing test first. Watch it fail. Then implement.

**Goal:** Alertar quando o preço diário furar a Bollinger Band contra a tendência semanal/mensal.

**Architecture:** Novo indicador `bollinger.py` (cálculo puro + breach detection). Engine determina trend via `analyze_rsi()` existente em `1w`/`1M`, e só coleta alerta se direção do breach for contrária à tendência. Anti-spam por estado ativo (reseta quando preço volta pra dentro das bandas), não por candle.

**Tech Stack:** Python 3.13, pandas (rolling SMA+std), SQLAlchemy ORM, pytest, loguru.

---

## Strategy Spec

### Trend filter (RSI semanal + mensal, período 14, escala 0-100)
| RSI(1w) | RSI(1M) | Tendência | Busca |
---------|---------|-----------|--------
| `< 50` | `< 50` | BAIXA | SHORT (preço furar BB superior) |
| `> 50` | `> 50` | ALTA | LONG (preço furar BB inferior) |
| qualquer outro caso | — | NEUTRA | não alertar |

Threshold é estrito: `== 50` → neutro.

### Entry signal (BB diário)
- BB(21, 2.0σ) sobre **candles diários fechados** (`is_closed=1`). Preço atual (tick) comparado contra banda estática.
- Buffer 0.5%: `upper_efetiva = BB_upper × 1.005`, `lower_efetiva = BB_lower × 0.995`
- ddof=0 (população) para bater com TradingView.

### Anti-spam (state machine)
- Estado: `last_condition[(symbol, "1d", "BB")]` = `"SHORT"` | `"LONG"` | `None`
- Preço fura banda efetiva (na direção correta da tendência) → alerta, marca estado
- Preço volta pra dentro das bandas (entre BB_lower e BB_upper **sem buffer**) → reseta estado (`None`)
- Estado **persiste entre candles diários** (não resetado por `_clear_candle_alerts`)
- Só realerta após reset + novo breach

### Alert keys
- `{symbol}_1d_{open_time}_BB_SHORT`
- `{symbol}_1d_{open_time}_BB_LONG`
- Condition key (throttle): `BB_SHORT_1d` / `BB_LONG_1d`

---

## Edge cases covered (confirmed by user)

| ID | Caso | Decisão |
|----|------|---------|
| A | RSI exatamente 50 | Neutro, não alerta (comparação estrita) |
| B | BB self-healing | Calculado só sobre candles fechados; preço atual comparado contra banda estática |
| C | Startup em breach | `_initialize_conditions()` popula estado → sem alerta retroativo |
| D | Novo candle diário | **Não** reseta estado BB (persiste, como RSI). Reset só por preço voltar dentro |
| E | Pandas std | `ddof=0` (população) para bater com TradingView |

---

## Files

| Arquivo | Ação | Linhas aprox. |
|---------|------|---------------|
| `src/indicators/bollinger.py` | **CREATE** | ~110 |
| `src/config.py` | **MODIFY** | +25 (`get_bollinger_config`) |
| `configs/free.yaml` | **MODIFY** | +12 (seção `indicators.bollinger`) |
| `src/notif/templates.py` | **MODIFY** | +50 (2 templates + block mega-alert) |
| `src/rules/engine.py` | **MODIFY** | ~+120 (collect + init + get_template + mega-alert type) |
| `tests/test_bollinger.py` | **CREATE** | ~250 |
| `tests/test_bb_engine.py` | **CREATE** | ~200 |
| `AGENTS.md` | **MODIFY** | +1 linha (alerta novo) |
| `skills/smartmoney-bot/workflows/indicators/SKILL.md` | **MODIFY** | +BB na scope/references |

---

## Task Dependency Graph

```
Task 1 (config) ─┐
Task 2 (bollinger.py) ──→ Task 3 (templates) ──→ Task 4 (engine) ──→ Task 5 (integration test)
                                              ──→ Task 6 (mega-alert block)
Task 7 (docs update) [independent, last]
```

---

## Task 1: Config — `get_bollinger_config()` + YAML

**Files:**
- Modify: `src/config.py` (adicionar helper após `get_breakout_config()`, linha ~219)
- Modify: `configs/free.yaml` (adicionar após seção `breakout:`, linha ~58)
- Test: `tests/test_bollinger.py` (criar)

**Step 1: Write the failing test**

```python
# tests/test_bollinger.py
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
```

**Step 2: Run test — confirm it fails**
```bash
cd /home/goldani/smartmoney-bot
PYTHONPATH=. python -m pytest tests/test_bollinger.py::TestBollingerConfig -v
```
Expected: FAIL — `ImportError: cannot import name 'get_bollinger_config'`

**Step 3: Write minimal implementation**

Add to `configs/free.yaml` after the `breakout:` block (after line 58):
```yaml
  bollinger:
    enabled: true
    timeframe: "1d"
    period: 21
    std_mult: 2.0
    # Buffer applied to bands to filter marginal breaches (0.5% = price must exceed band by 0.5%)
    buffer_pct: 0.5
    # Trend filter: RSI on weekly + monthly determines direction
    trend:
      rsi_period: 14
      threshold: 50   # < threshold = downtrend (seek SHORT), > threshold = uptrend (seek LONG)
```

Add to `src/config.py` after `get_breakout_config()` (line ~219):
```python
def get_bollinger_config() -> Dict[str, Any]:
    """Get Bollinger Bands config with validation and safe defaults."""
    bb_config = dict(get_config().get("indicators.bollinger", {}) or {})

    if not isinstance(bb_config, dict):
        bb_config = {}

    bb_config.setdefault("enabled", False)
    bb_config.setdefault("timeframe", "1d")
    bb_config.setdefault("period", 21)
    bb_config.setdefault("std_mult", 2.0)
    bb_config.setdefault("buffer_pct", 0.5)

    trend = bb_config.get("trend", {})
    if not isinstance(trend, dict):
        trend = {}
    trend.setdefault("rsi_period", 14)
    trend.setdefault("threshold", 50)
    bb_config["trend"] = trend

    # Validate
    _validate_numeric(bb_config, "period", 21, min_val=1, max_val=200, cast_fn=int)
    _validate_numeric(bb_config, "std_mult", 2.0, min_val=0.5, max_val=4.0)
    _validate_numeric(bb_config, "buffer_pct", 0.5, min_val=0.0, max_val=5.0)

    return bb_config
```

**Step 4: Run test — confirm it passes**
```bash
PYTHONPATH=. python -m pytest tests/test_bollinger.py::TestBollingerConfig -v
```
Expected: PASS

**Step 5: Commit**
```bash
git add src/config.py configs/free.yaml tests/test_bollinger.py
git commit -m "feat(bb): add bollinger config helper and YAML section"
```

---

## Task 2: Indicator — `src/indicators/bollinger.py`

**Files:**
- Create: `src/indicators/bollinger.py`
- Test: `tests/test_bollinger.py` (append)

**Functions to implement:**

```python
# src/indicators/bollinger.py
"""
Bollinger Bands indicator and contratrend breach detection.
BB(period, std_mult) calculated on CLOSED candles only (avoids self-healing).
"""
from typing import List, Dict, Optional
import pandas as pd
from loguru import logger


def calculate_bb(closes: List[float], period: int = 21, std_mult: float = 2.0) -> Optional[Dict[str, float]]:
    """
    Calculate Bollinger Bands using population std (ddof=0, TradingView-compatible).

    Args:
        closes: List of closing prices (oldest first), CLOSED candles only
        period: SMA period (default 21)
        std_mult: Standard deviation multiplier (default 2.0)

    Returns:
        Dict with 'upper', 'middle', 'lower' (last values) or None if insufficient data.
        Example: {"upper": 105.0, "middle": 100.0, "lower": 95.0}
    """
    if len(closes) < period:
        logger.debug(f"Insufficient data for BB: need {period}, got {len(closes)}")
        return None

    df = pd.DataFrame({"close": closes})
    df["sma"] = df["close"].rolling(window=period).mean()
    df["std"] = df["close"].rolling(window=period).std(ddof=0)  # population std

    last_row = df.iloc[-1]
    if pd.isna(last_row["sma"]) or pd.isna(last_row["std"]):
        return None

    middle = float(last_row["sma"])
    std = float(last_row["std"])
    upper = middle + std_mult * std
    lower = middle - std_mult * std

    return {"upper": upper, "middle": middle, "lower": lower}


def fetch_closed_candles_for_bb(symbol: str, interval: str, period: int = 21) -> List[float]:
    """
    Fetch recent CLOSED candles from database for BB calculation.
    Filters is_closed=1 to avoid self-healing (band shifting by current forming candle).

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")
        interval: Timeframe (e.g., "1d")
        period: Number of closed candles needed

    Returns:
        List of closing prices (oldest first), empty if insufficient data.
    """
    from src.storage.db import SessionLocal
    from src.storage.models import Candle
    from sqlalchemy import and_

    try:
        with SessionLocal() as session:
            candles = session.query(Candle).filter(
                and_(
                    Candle.symbol == symbol,
                    Candle.interval == interval,
                    Candle.is_closed == 1
                )
            ).order_by(Candle.open_time.desc()).limit(period).all()

            if not candles:
                return []

            candles = list(reversed(candles))
            return [c.close for c in candles]
    except Exception as e:
        logger.error(f"Failed to fetch closed candles for BB {symbol} {interval}: {e}")
        return []


def check_bb_breach(
    symbol: str,
    interval: str,
    current_price: float,
    period: int = 21,
    std_mult: float = 2.0,
    buffer_pct: float = 0.5,
) -> Optional[Dict]:
    """
    Check if current price breaches Bollinger Bands (with buffer).

    Args:
        symbol: Trading pair
        interval: Timeframe for BB calculation
        current_price: Live/tick price to check against bands
        period: BB period
        std_mult: BB std multiplier
        buffer_pct: Buffer percentage (0.5 = 0.5%). Applied as:
                    upper_effective = upper * (1 + buffer/100)
                    lower_effective = lower * (1 - buffer/100)

    Returns:
        Dict with breach data or None:
        {
            "type": "UPPER" | "LOWER",
            "symbol": "BTCUSDT",
            "interval": "1d",
            "price": 67500.0,
            "bb_upper": 105.0,   # raw band value (if UPPER)
            "bb_lower": 95.0,    # raw band value (if LOWER)
            "bb_middle": 100.0,
            "effective_band": 105.525  # the threshold actually crossed
        }
    """
    closes = fetch_closed_candles_for_bb(symbol, interval, period)
    if len(closes) < period:
        logger.warning(f"Insufficient closed candles for BB {symbol} {interval}: {len(closes)}/{period}")
        return None

    bands = calculate_bb(closes, period, std_mult)
    if not bands:
        return None

    buffer_mult = 1 + (buffer_pct / 100)
    upper_effective = bands["upper"] * buffer_mult
    lower_effective = bands["lower"] * (2 - buffer_mult)  # = lower * (1 - buffer/100)

    # Breach upper band
    if current_price > upper_effective:
        return {
            "type": "UPPER",
            "symbol": symbol,
            "interval": interval,
            "price": current_price,
            "bb_upper": bands["upper"],
            "bb_middle": bands["middle"],
            "effective_band": upper_effective,
        }

    # Breach lower band
    if current_price < lower_effective:
        return {
            "type": "LOWER",
            "symbol": symbol,
            "interval": interval,
            "price": current_price,
            "bb_lower": bands["lower"],
            "bb_middle": bands["middle"],
            "effective_band": lower_effective,
        }

    # Price inside bands (between raw lower and raw upper, no buffer)
    return None


def is_price_inside_bands(
    symbol: str,
    interval: str,
    current_price: float,
    period: int = 21,
    std_mult: float = 2.0,
) -> bool:
    """
    Check if price is INSIDE the raw Bollinger Bands (between lower and upper, no buffer).
    Used for anti-spam state reset: when price returns inside, BB alert state resets.

    Args:
        symbol: Trading pair
        interval: Timeframe
        current_price: Live/tick price
        period: BB period
        std_mult: BB std multiplier

    Returns:
        True if lower < price < upper (strict, raw bands without buffer).
    """
    closes = fetch_closed_candles_for_bb(symbol, interval, period)
    if len(closes) < period:
        return False  # can't determine, don't reset

    bands = calculate_bb(closes, period, std_mult)
    if not bands:
        return False

    return bands["lower"] < current_price < bands["upper"]
```

**Step 1: Write the failing tests** (append to `tests/test_bollinger.py`)

```python
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
```

**Step 2: Run tests — confirm they fail**
```bash
PYTHONPATH=. python -m pytest tests/test_bollinger.py -v -k "not Config"
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.indicators.bollinger'`

**Step 3: Write implementation** — create `src/indicators/bollinger.py` with the code above.

**Step 4: Run tests — confirm they pass**
```bash
PYTHONPATH=. python -m pytest tests/test_bollinger.py -v
```
Expected: PASS (all)

**Step 5: Commit**
```bash
git add src/indicators/bollinger.py tests/test_bollinger.py
git commit -m "feat(bb): implement bollinger bands indicator + breach detection"
```

---

## Task 3: Templates — `template_bb_short` + `template_bb_long`

**Files:**
- Modify: `src/notif/templates.py` (add after `template_breakout_bear`, line ~202)
- Test: `tests/test_bollinger.py` (append)

**Step 1: Write the failing tests**

```python
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
            "rsi_1w": 42.5,
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
            "rsi_1w": 58.0,
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
            "rsi_1w": 40.0, "rsi_1M": 40.0,
        }
        assert ALERT_DISCLAIMER in template_bb_short(data)
        data_long = {**data, "bb_lower": 101.0}
        assert ALERT_DISCLAIMER in template_bb_long(data_long)
```

**Step 2: Run — confirm fail**
```bash
PYTHONPATH=. python -m pytest tests/test_bollinger.py::TestBBTemplates -v
```
Expected: FAIL — `ImportError: cannot import name 'template_bb_short'`

**Step 3: Implement** — add to `src/notif/templates.py` after `template_breakout_bear` (line ~202):

```python
def template_bb_short(data: Dict) -> str:
    """
    Template for BB contratrend SHORT alert.
    Triggered when downtrend (RSI 1w/1M < 50) and price breaches BB upper band.

    Args:
        data: {
            "symbol": "BTCUSDT", "interval": "1d", "price": 67500.0,
            "bb_upper": 67000.0, "effective_band": 67335.0,
            "rsi_1w": 42.5, "rsi_1M": 38.0
        }
    """
    symbol = format_symbol_display(data["symbol"])
    timeframe = format_timeframe_display(data["interval"])
    price = format_price_br(data["price"])
    bb_upper = format_price_br(data["bb_upper"])
    effective = format_price_br(data["effective_band"])
    rsi_1w = format_rsi_value(data["rsi_1w"])
    rsi_1M = format_rsi_value(data["rsi_1M"])
    timestamp = format_datetime_br()

    return f"""BB Contratrend SHORT ({timeframe})

{symbol} {price}
Banda superior: {bb_upper} (efetiva: {effective})
Tendência: RSI 1S {rsi_1w} | 1M {rsi_1M} (baixa)

{timestamp}
{ALERT_DISCLAIMER}"""


def template_bb_long(data: Dict) -> str:
    """
    Template for BB contratrend LONG alert.
    Triggered when uptrend (RSI 1w/1M > 50) and price breaches BB lower band.

    Args:
        data: {
            "symbol": "BTCUSDT", "interval": "1d", "price": 94500.0,
            "bb_lower": 95000.0, "effective_band": 94525.0,
            "rsi_1w": 58.0, "rsi_1M": 62.0
        }
    """
    symbol = format_symbol_display(data["symbol"])
    timeframe = format_timeframe_display(data["interval"])
    price = format_price_br(data["price"])
    bb_lower = format_price_br(data["bb_lower"])
    effective = format_price_br(data["effective_band"])
    rsi_1w = format_rsi_value(data["rsi_1w"])
    rsi_1M = format_rsi_value(data["rsi_1M"])
    timestamp = format_datetime_br()

    return f"""BB Contratrend LONG ({timeframe})

{symbol} {price}
Banda inferior: {bb_lower} (efetiva: {effective})
Tendência: RSI 1S {rsi_1w} | 1M {rsi_1M} (alta)

{timestamp}
{ALERT_DISCLAIMER}"""
```

**Step 4: Run — confirm pass**
```bash
PYTHONPATH=. python -m pytest tests/test_bollinger.py::TestBBTemplates -v
```
Expected: PASS

**Step 5: Commit**
```bash
git add src/notif/templates.py tests/test_bollinger.py
git commit -m "feat(bb): add BB contratrend alert templates (PT-BR)"
```

---

## Task 4: Engine integration — `_collect_bb_alert` + `_initialize_conditions`

**Files:**
- Modify: `src/rules/engine.py`
- Test: `tests/test_bb_engine.py` (create)

### Modification map (engine.py)

**4a. Imports** (top of file, after line 27):
```python
from src.indicators.bollinger import check_bb_breach, is_price_inside_bands
```
And add to template imports (line ~28):
```python
from src.notif.templates import (
    # ... existing ...
    template_bb_short,
    template_bb_long,
)
```
And add to config imports (line ~19):
```python
from src.config import (
    # ... existing ...
    get_bollinger_config,
)
```

**4b. `__init__`** (after line 82 `self.alert_config = ...`):
```python
        self.bb_config = get_bollinger_config()
```

**4c. Template helper** (add after `_get_breakout_template`, line ~270):
```python
    def _get_bb_template(self, bb_type: str):
        """Return template function for BB contratrend type."""
        return template_bb_short if bb_type == "SHORT" else template_bb_long
```

**4d. `_initialize_conditions`** — add BB block after breakout block (after line 144):
```python
        # Initialize Bollinger contratrend condition
        if is_indicator_enabled('bollinger'):
            bb_tf = self.bb_config.get('timeframe', '1d')
            if interval == bb_tf:
                period = self.bb_config.get('period', 21)
                std_mult = self.bb_config.get('std_mult', 2.0)
                buffer_pct = self.bb_config.get('buffer_pct', 0.5)
                result = check_bb_breach(symbol, interval, current_price, period, std_mult, buffer_pct)
                if result:
                    # Determine trend to know which breach direction is "active"
                    trend = self._determine_trend(symbol)
                    if trend == "BEAR" and result["type"] == "UPPER":
                        condition_key_tuple = (symbol, interval, "BB")
                        self.last_condition[condition_key_tuple] = "SHORT"
                        alert_key = f"{symbol}_{interval}_{open_time}_BB_SHORT"
                        self.alerted_candles[alert_key] = True
                        self.alerted_candles_with_timestamp[alert_key] = time.time()
                        logger.debug(f"Initialized BB condition: {symbol} {interval} = SHORT (already breaching)")
                    elif trend == "BULL" and result["type"] == "LOWER":
                        condition_key_tuple = (symbol, interval, "BB")
                        self.last_condition[condition_key_tuple] = "LONG"
                        alert_key = f"{symbol}_{interval}_{open_time}_BB_LONG"
                        self.alerted_candles[alert_key] = True
                        self.alerted_candles_with_timestamp[alert_key] = time.time()
                        logger.debug(f"Initialized BB condition: {symbol} {interval} = LONG (already breaching)")
```

**4e. Trend determination helper** (add after `_get_bb_template`):
```python
    def _determine_trend(self, symbol: str) -> Optional[str]:
        """
        Determine trend from RSI on weekly + monthly.
        Uses existing analyze_rsi() which reads from config timeframes.

        Returns:
            "BULL" if RSI(1w) > 50 AND RSI(1M) > 50
            "BEAR" if RSI(1w) < 50 AND RSI(1M) < 50
            None if neutral or insufficient data
        """
        trend_cfg = self.bb_config.get('trend', {})
        rsi_period = trend_cfg.get('rsi_period', 14)
        threshold = trend_cfg.get('threshold', 50)

        rsi_1w = analyze_rsi(symbol, "1w", period=rsi_period, _use_config=False)
        rsi_1M = analyze_rsi(symbol, "1M", period=rsi_period, _use_config=False)

        if not rsi_1w or not rsi_1M:
            return None

        val_1w = rsi_1w.get("rsi")
        val_1M = rsi_1M.get("rsi")
        if val_1w is None or val_1M is None:
            return None

        if val_1w > threshold and val_1M > threshold:
            return "BULL"
        if val_1w < threshold and val_1M < threshold:
            return "BEAR"
        return None
```

**4f. `_collect_bb_alert`** (add after `_collect_breakout_alert`, line ~516):
```python
    def _collect_bb_alert(self, symbol: str, interval: str, current_price: float, open_time: int):
        """
        Check BB contratrend condition and collect alert if valid.
        Anti-spam: state resets only when price returns inside bands (not on new candle).
        """
        if not is_indicator_enabled('bollinger'):
            return

        bb_tf = self.bb_config.get('timeframe', '1d')
        if interval != bb_tf:
            return

        period = self.bb_config.get('period', 21)
        std_mult = self.bb_config.get('std_mult', 2.0)
        buffer_pct = self.bb_config.get('buffer_pct', 0.5)

        tracker_key = (symbol, interval, "BB")
        last_bb = self.last_condition.get(tracker_key)

        # ANTI-SPAM RESET: if currently in breach state, check if price returned inside bands
        if last_bb is not None:
            if is_price_inside_bands(symbol, interval, current_price, period, std_mult):
                logger.debug(f"BB reset: {symbol} {interval} price returned inside bands")
                self.last_condition[tracker_key] = None
            return  # Either still breaching (skip) or just reset (wait for new breach)

        # Not in breach state — check for new breach
        result = check_bb_breach(symbol, interval, current_price, period, std_mult, buffer_pct)
        if not result:
            return

        # Determine trend
        trend = self._determine_trend(symbol)
        if trend is None:
            return  # Neutral trend, no alert

        # Map breach direction + trend → alert condition
        # BEAR trend + UPPER breach → SHORT (mean reversion short)
        # BULL trend + LOWER breach → LONG (mean reversion long)
        if trend == "BEAR" and result["type"] == "UPPER":
            condition = "SHORT"
        elif trend == "BULL" and result["type"] == "LOWER":
            condition = "LONG"
        else:
            return  # Wrong direction (breach with trend, not against)

        alert_key = f"{symbol}_{interval}_{open_time}_BB_{condition}"
        if alert_key in self.alerted_candles:
            return

        # Throttle
        condition_key = f"BB_{condition}_{interval}"
        if not self._check_throttle_and_mark(condition_key, alert_key, tracker_key, condition):
            return

        # Enrich result with trend context for template
        trend_cfg = self.bb_config.get('trend', {})
        rsi_period = trend_cfg.get('rsi_period', 14)
        rsi_1w_data = analyze_rsi(symbol, "1w", period=rsi_period, _use_config=False)
        rsi_1M_data = analyze_rsi(symbol, "1M", period=rsi_period, _use_config=False)
        result["rsi_1w"] = rsi_1w_data.get("rsi") if rsi_1w_data else None
        result["rsi_1M"] = rsi_1M_data.get("rsi") if rsi_1M_data else None

        self._collect_single_alert(
            alert_type='BB',
            condition=condition,
            symbol=symbol,
            interval=interval,
            open_time=open_time,
            result=result,
            tracker_key=tracker_key,
            condition_key=condition_key,
            template_func=self._get_bb_template(condition)
        )
```

**4g. `_collect_single_alert` BB block** — add `elif` after BREAKOUT block (after engine.py line 370):
```python
        elif alert_type == 'BB':
            alert_dict['price'] = result.get('price')
            alert_dict['bb_upper'] = result.get('bb_upper')
            alert_dict['bb_lower'] = result.get('bb_lower')
            alert_dict['bb_middle'] = result.get('bb_middle')
            alert_dict['effective_band'] = result.get('effective_band')
            alert_dict['rsi_1w'] = result.get('rsi_1w')
            alert_dict['rsi_1M'] = result.get('rsi_1M')
```
**Why:** Without this, BB fields from the result dict are never copied into the alert dict, so templates and mega-alerts can't access `data["price"]`, `data["bb_upper"]`, etc.

**4h. `process_candle`** — add call (after line 575 `self._collect_breakout_alert(...)`):
```python
        # Collect Bollinger contratrend alerts
        self._collect_bb_alert(symbol, interval, current_price, open_time)
```

**Step 1: Write the failing tests** — create `tests/test_bb_engine.py`:

```python
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


class TestDetermineTrend:
    """Tests for _determine_trend()."""

    @patch("src.rules.engine.analyze_rsi")
    def test_bear_trend(self, mock_rsi, engine):
        mock_rsi.side_effect = [{"rsi": 40.0}, {"rsi": 35.0}]  # 1w, 1M
        assert engine._determine_trend("BTCUSDT") == "BEAR"

    @patch("src.rules.engine.analyze_rsi")
    def test_bull_trend(self, mock_rsi, engine):
        mock_rsi.side_effect = [{"rsi": 60.0}, {"rsi": 65.0}]
        assert engine._determine_trend("BTCUSDT") == "BULL"

    @patch("src.rules.engine.analyze_rsi")
    def test_neutral_mixed(self, mock_rsi, engine):
        mock_rsi.side_effect = [{"rsi": 60.0}, {"rsi": 40.0}]  # mixed
        assert engine._determine_trend("BTCUSDT") is None

    @patch("src.rules.engine.analyze_rsi")
    def test_neutral_exact_threshold(self, mock_rsi, engine):
        mock_rsi.side_effect = [{"rsi": 50.0}, {"rsi": 50.0}]  # exactly 50
        assert engine._determine_trend("BTCUSDT") is None

    @patch("src.rules.engine.analyze_rsi")
    def test_neutral_insufficient_data(self, mock_rsi, engine):
        mock_rsi.side_effect = [None, {"rsi": 40.0}]
        assert engine._determine_trend("BTCUSDT") is None


class TestCollectBBAlert:
    """Tests for _collect_bb_alert() state machine."""

    @patch.object(AlertEngine, "_determine_trend", return_value="BEAR")
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

    @patch.object(AlertEngine, "_determine_trend", return_value="BULL")
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

    @patch.object(AlertEngine, "_determine_trend", return_value="BEAR")
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

    @patch.object(AlertEngine, "_determine_trend", return_value=None)
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
```

**Step 2: Run — confirm fail**
```bash
PYTHONPATH=. python -m pytest tests/test_bb_engine.py -v
```
Expected: FAIL — `AttributeError: 'AlertEngine' object has no attribute '_collect_bb_alert'`

**Step 3: Implement** — apply modifications 4a-4g to `src/rules/engine.py` per the map above.

**Step 4: Run — confirm pass**
```bash
PYTHONPATH=. python -m pytest tests/test_bb_engine.py -v
```
Expected: PASS

**Step 5: Commit**
```bash
git add src/rules/engine.py tests/test_bb_engine.py
git commit -m "feat(bb): integrate BB contratrend alert into AlertEngine"
```

---

## Task 5: Mega-alert block — `template_mega_alert` BB type

**Files:**
- Modify: `src/notif/templates.py` (add `elif alert['type'] == 'BB'` block in `template_mega_alert`, after line ~309)
- Test: `tests/test_bollinger.py` (append)

**Step 1: Write the failing test**

```python
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
            "rsi_1w": 42.0, "rsi_1M": 38.0,
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
            "rsi_1w": 58.0, "rsi_1M": 62.0,
        }]
        result = template_mega_alert(alerts)
        assert "BB Contratrend LONG" in result
```

**Step 2: Run — confirm fail**
```bash
PYTHONPATH=. python -m pytest tests/test_bollinger.py::TestBBMegaAlert -v
```
Expected: FAIL — BB block missing from mega-alert (type falls through)

**Step 3: Implement** — add after DIVERGENCE block in `template_mega_alert` (line ~309):

```python
        elif alert['type'] == 'BB':
            symbol = format_symbol_display(alert['symbol'])
            tf = format_timeframe_display(alert['interval'])
            price = format_price_br(alert['price'])
            rsi_1w = format_rsi_value(alert.get('rsi_1w', 0))
            rsi_1M = format_rsi_value(alert.get('rsi_1M', 0))

            direction = 'SHORT' if alert['condition'] == 'SHORT' else 'LONG'
            alert_blocks.append(
                f"BB Contratrend {direction} ({tf}): \n{symbol} {price} | RSI 1S {rsi_1w} 1M {rsi_1M}"
            )
```

**Step 4: Run — confirm pass**
```bash
PYTHONPATH=. python -m pytest tests/test_bollinger.py::TestBBMegaAlert -v
```
Expected: PASS

**Step 5: Commit**
```bash
git add src/notif/templates.py tests/test_bollinger.py
git commit -m "feat(bb): add BB block to mega-alert consolidation template"
```

---

## Task 6: Integration smoke test + full suite

**Files:** None (verification only)

**Step 1: Full test suite (no regression)**
```bash
cd /home/goldani/smartmoney-bot
PYTHONPATH=. python -m pytest tests/ -v
```
Expected: All 268 original + new BB tests pass.

**Step 2: Coverage check**
```bash
PYTHONPATH=. python -m pytest --cov=src/indicators/bollinger --cov=src/notif/templates tests/test_bollinger.py tests/test_bb_engine.py
```
Expected: BB indicator ≥ 90%, BB engine integration ≥ 85%.

**Step 3: Dry-run**
```bash
PYTHONPATH=. python src/main.py --dry-run
```
Expected: Startup OK, config loads BB section, divergence init OK, no exceptions.

**Step 4: Commit (if any fixups needed)**
```bash
git add -A && git commit -m "test(bb): integration smoke test passes, no regression"
```

---

## Task 7: Documentation update

**Files:**
- Modify: `AGENTS.md` (line 4: add BB to alert list)
- Modify: `skills/smartmoney-bot/workflows/indicators/SKILL.md` (scope + references)

**Changes:**

`AGENTS.md` line 4:
```
Alertas: RSI | Breakouts | Divergência RSI | Resumo Diário (Fear & Greed) | BB Contratrend.
```

`skills/smartmoney-bot/workflows/indicators/SKILL.md` scope (add line):
```
- `src/indicators/bollinger.py` — Bollinger Bands (21, 2σ) contratrend breach detection
```
And references:
```
- `src/indicators/bollinger.py` — BB calculation (pandas rolling, ddof=0) + breach with buffer
```

Also update `src/CLAUDE.md` architecture section indicators list:
```
**indicators/:** `rsi.py` (Wilder's p14) | `breakouts.py` (±0.15%) | `divergence.py` (3-pivot, RSI thresholds 40/60) | `bollinger.py` (BB 21/2σ contratrend)
```

**Step 1: Apply edits**
**Step 2: Commit**
```bash
git add AGENTS.md skills/smartmoney-bot/workflows/indicators/SKILL.md src/CLAUDE.md
git commit -m "docs(bb): document BB contratrend alert in AGENTS.md, skills, CLAUDE.md"
```

---

## Verify Summary

- [ ] `PYTHONPATH=. python src/main.py --dry-run` — sem erros, BB config carregado
- [ ] `PYTHONPATH=. pytest tests/ -v` — suíte completa (268 + novos) sem regressão
- [ ] Coverage ≥ 90% no módulo bollinger
- [ ] Sem hardcode — todos parâmetros via `get_bollinger_config()`
- [ ] Type hints presentes em todas funções novas
- [ ] Templates PT-BR
- [ ] Alert keys seguem formato canônico `{symbol}_{interval}_{open_time}_BB_{condition}`
- [ ] Anti-spam state machine: reset por preço dentro das bandas (não por candle)
- [ ] `_initialize_conditions()` cobre BB (sem alerta retroativo)
- [ ] BB não resetado por `_clear_candle_alerts()` (estado persiste)
- [ ] ddof=0 (TradingView-compatible)
- [ ] Diff cirúrgico — sem refactor adjacente
