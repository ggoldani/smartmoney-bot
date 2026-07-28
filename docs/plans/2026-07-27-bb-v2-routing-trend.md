# BB v2 — Symbol Routing + Trend Filter Mensal

> **For implementer:** Use TDD throughout. Write failing test first. Watch it fail. Then implement.

**Goal:** (1) Permitir pares com apenas alerta BB (sem RSI/breakout/divergence). (2) Trend filter usar só RSI mensal (drop semanal).

**Architecture:** Campo `alerts` por symbol no YAML define quais alertas cada par recebe. Helper `get_symbol_alerts()` lê o campo (default = todos se omitido). Cada `_collect_*` no engine + divergence_processor checa o routing antes de processar. Daily summary filtra pares que têm RSI no seu `alerts`.

---

## Strategy

### Symbol routing
```yaml
symbols:
  - name: "BTCUSDT"
    timeframes: ["4h", "1d", "1w", "1M"]
    alerts: ["rsi", "breakout", "divergence", "bb"]
  - name: "ETHUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
```
- Default: se campo `alerts` omitido → todos os alertas (backward compatible)
- Daily summary: só symbols com "rsi" em `alerts`

### Trend filter (só mensal)
```python
# _determine_trend — versão final
rsi_1M = analyze_rsi(symbol, "1M", period=rsi_period, _use_config=False)
if val_1M > threshold: return "BULL"
if val_1M < threshold: return "BEAR"
return None
```

---

## Files

| Arquivo | Ação |
|---------|------|
| `src/config.py` | +`get_symbol_alerts()` helper |
| `configs/free.yaml` | +14 symbols BB-only, campo `alerts` nos existentes |
| `src/rules/engine.py` | 4 routing checks + `_determine_trend` simplificado |
| `src/rules/divergence_processor.py` | 1 routing check no `process()` |
| `src/rules/daily_summary.py` | filtrar symbols sem RSI |
| `tests/test_config.py` | testes `get_symbol_alerts` |
| `tests/test_bb_engine.py` | testes routing + trend mensal |
| `tests/test_daily_summary.py` | teste filtro symbol |

---

## Task 1: Config — `get_symbol_alerts()` helper + YAML

**Files:**
- Modify: `src/config.py` (adicionar após `get_timeframes_for_symbol`, ~linha 125)
- Modify: `configs/free.yaml` (reestruturar symbols)
- Test: `tests/test_config.py` (append)

**Step 1: Write failing test**

```python
# tests/test_config.py — append
class TestSymbolAlerts:
    """Tests for get_symbol_alerts() helper."""

    def test_returns_alerts_when_defined(self, monkeypatch):
        """Should return the alerts list when explicitly defined."""
        from src.config import reload_config, get_symbol_alerts
        reload_config()  # configs/free.yaml
        # ETHUSDT has alerts: ["bb"]
        result = get_symbol_alerts("ETHUSDT")
        assert result == ["bb"]

    def test_returns_all_when_omitted(self, monkeypatch):
        """Should return all alerts when field omitted (backward compatible)."""
        from src.config import reload_config, get_symbol_alerts
        reload_config()
        # BTCUSDT has explicit alerts field
        btc_alerts = get_symbol_alerts("BTCUSDT")
        assert "rsi" in btc_alerts
        assert "breakout" in btc_alerts
        assert "divergence" in btc_alerts
        assert "bb" in btc_alerts

    def test_returns_unknown_symbol_empty(self):
        """Should return empty list for unknown symbol."""
        from src.config import get_symbol_alerts
        result = get_symbol_alerts("NONEXISTENT")
        assert result == []
```

**Step 2: Run — confirm fail**
```bash
PYTHONPATH=. python -m pytest tests/test_config.py::TestSymbolAlerts -v
```
Expected: FAIL — `ImportError: cannot import name 'get_symbol_alerts'`

**Step 3: Implement**

`src/config.py` after `get_timeframes_for_symbol()`:
```python
def get_symbol_alerts(symbol: str) -> List[str]:
    """
    Get which alert types a symbol is subscribed to.
    Returns all alert types if 'alerts' field is omitted (backward compatible).

    Args:
        symbol: Trading pair (e.g., "BTCUSDT")

    Returns:
        List of alert types (e.g., ["rsi", "breakout", "divergence", "bb"]) or empty list.
    """
    all_alerts = ["rsi", "breakout", "divergence", "bb"]
    symbols = get_symbols()
    for sym_config in symbols:
        if sym_config.get("name") == symbol:
            alerts = sym_config.get("alerts")
            if alerts is None:
                return all_alerts  # default: all
            return alerts
    return []
```

`configs/free.yaml` — replace symbols section:
```yaml
symbols:
  - name: "BTCUSDT"
    timeframes: ["4h", "1d", "1w", "1M"]
    alerts: ["rsi", "breakout", "divergence", "bb"]
  - name: "PAXGUSDT"
    timeframes: ["4h", "1d", "1w", "1M"]
    alerts: ["rsi", "breakout", "divergence", "bb"]
  - name: "ETHUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "SOLUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "BNBUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "XRPUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "DOGEUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "AVAXUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "LINKUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "LTCUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "SUIUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "AAVEUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "ONDOUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "ZECUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "XLMUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
  - name: "AEROUSDT"
    timeframes: ["1d", "1M"]
    alerts: ["bb"]
```

**Step 4: Run — confirm pass**
```bash
PYTHONPATH=. python -m pytest tests/test_config.py::TestSymbolAlerts -v
```

**Step 5: Commit**
```bash
git add src/config.py configs/free.yaml tests/test_config.py
git commit -m "feat(bb): add symbol routing (alerts field per symbol) + 14 BB-only pairs"
```

---

## Task 2: Engine routing checks (4) + trend filter mensal

**Files:**
- Modify: `src/rules/engine.py`
- Test: `tests/test_bb_engine.py` (append)

**Modification points:**

**2a. Import `get_symbol_alerts`** (top imports, add to existing config import block ~line 19):
```python
from src.config import (
    # ... existing ...
    get_bollinger_config,
    get_symbol_alerts,
)
```

**2b. RSI routing check** — in `_collect_rsi_alert()` (after `is_indicator_enabled('rsi')` check, ~line 438):
```python
        if 'rsi' not in get_symbol_alerts(symbol):
            return
```

**2c. Breakout routing check** — in `_collect_breakout_alert()` (after `is_indicator_enabled('breakout')` check, ~line 508):
```python
        if 'breakout' not in get_symbol_alerts(symbol):
            return
```

**2d. BB routing check** — in `_collect_bb_alert()` (after `is_indicator_enabled('bollinger')` check, ~line 596):
```python
        if 'bb' not in get_symbol_alerts(symbol):
            return
```

**2e. Divergence routing check** — in `_process_divergences()` (engine.py ~line 152):
```python
    async def _process_divergences(self, symbol: str, interval: str, open_time: int):
        """Delegate divergence processing to DivergenceProcessor."""
        if 'divergence' not in get_symbol_alerts(symbol):
            return
        await self.divergence_processor.process(symbol, interval, open_time)
```

**2f. Multi-TF consolidation routing** — in `check_multi_tf_consolidation()` (~line 570, after `is_indicator_enabled('rsi')` check):
```python
        if 'rsi' not in get_symbol_alerts(symbol):
            return
```

**2g. Trend filter mensal** — rewrite `_determine_trend()` (replace existing, ~line 306):
```python
    def _determine_trend(self, symbol: str) -> Optional[str]:
        """
        Determine trend from RSI on monthly only.
        Weekly dropped per strategy v2.

        Returns:
            "BULL" if RSI(1M) > threshold
            "BEAR" if RSI(1M) < threshold
            None if neutral or insufficient data
        """
        trend_cfg = self.bb_config.get('trend', {})
        rsi_period = trend_cfg.get('rsi_period', 14)
        threshold = trend_cfg.get('threshold', 50)

        rsi_1M = analyze_rsi(symbol, "1M", period=rsi_period, _use_config=False)

        if not rsi_1M:
            return None

        val_1M = rsi_1M.get("rsi")
        if val_1M is None:
            return None

        if val_1M > threshold:
            return "BULL"
        if val_1M < threshold:
            return "BEAR"
        return None
```

**Step 1: Write failing tests**

```python
# tests/test_bb_engine.py — append
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

    @patch.object(AlertEngine, "_determine_trend", return_value="BEAR")
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
        assert engine._determine_trend("BTCUSDT") == "BULL"
        # Should call analyze_rsi only once (1M), not twice (1w + 1M)
        assert mock_rsi.call_count == 1
        mock_rsi.assert_called_with("BTCUSDT", "1M", period=14, _use_config=False)

    @patch("src.rules.engine.analyze_rsi")
    def test_bear_trend_mensal_only(self, mock_rsi, engine):
        mock_rsi.return_value = {"rsi": 40.0}
        assert engine._determine_trend("BTCUSDT") == "BEAR"

    @patch("src.rules.engine.analyze_rsi")
    def test_neutral_exact_threshold(self, mock_rsi, engine):
        mock_rsi.return_value = {"rsi": 50.0}
        assert engine._determine_trend("BTCUSDT") is None

    @patch("src.rules.engine.analyze_rsi")
    def test_neutral_insufficient_data(self, mock_rsi, engine):
        mock_rsi.return_value = None
        assert engine._determine_trend("BTCUSDT") is None
```

**Step 2: Run — confirm fail**
```bash
PYTHONPATH=. python -m pytest tests/test_bb_engine.py::TestSymbolRouting tests/test_bb_engine.py::TestTrendFilterMensalOnly -v
```

**Step 3: Implement** — apply 2a through 2f.

**Step 4: Run — confirm pass**
```bash
PYTHONPATH=. python -m pytest tests/test_bb_engine.py -v
```

**Step 5: Commit**
```bash
git add src/rules/engine.py tests/test_bb_engine.py
git commit -m "feat(bb): symbol routing checks + trend filter mensal only"
```

---

## Task 3: Divergence routing check

**Files:**
- Modify: `src/rules/divergence_processor.py` (add routing check in `process()`, ~line 158)

**Note:** The `_process_divergences()` method in engine.py (2e above) already gates the call. But `divergence_processor.process()` also checks `get_symbols()` internally. To be safe and explicit, add a routing check inside `process()` itself:

**Step 1: Implement** — in `DivergenceProcessor.process()` after the enabled check (~line 160):
```python
        from src.config import get_symbol_alerts
        if 'divergence' not in get_symbol_alerts(symbol):
            return
```

**Step 2: Run existing tests** (ensure no regression)
```bash
PYTHONPATH=. python -m pytest tests/test_divergence.py -v
```

**Step 3: Commit**
```bash
git add src/rules/divergence_processor.py
git commit -m "feat(bb): divergence routing check for BB-only symbols"
```

---

## Task 4: Daily summary filter

**Files:**
- Modify: `src/rules/daily_summary.py` (`_send_summary()`, ~line 121)

**Step 1: Write failing test**

```python
# tests/test_daily_summary.py — append
class TestDailySummarySymbolFilter:
    """Tests for symbol routing in daily summary."""

    @patch("src.rules.daily_summary.get_symbols")
    @patch("src.rules.daily_summary.analyze_rsi")
    @patch("src.rules.daily_summary.get_previous_closed_candle")
    @patch("src.rules.daily_summary.fetch_fear_greed_index", return_value=(50, "Neutral"))
    @patch("src.rules.daily_summary.get_fear_greed_sentiment", return_value=("😐", "Neutral"))
    @patch("src.rules.daily_summary.send_message_async", return_value=True)
    async def test_bb_only_symbols_excluded_from_summary(
        self, mock_send, mock_sentiment, mock_fg, mock_candle, mock_rsi, mock_symbols
    ):
        """BB-only symbols should not appear in daily summary."""
        mock_symbols.return_value = [
            {"name": "BTCUSDT", "alerts": ["rsi", "breakout", "divergence", "bb"]},
            {"name": "ETHUSDT", "alerts": ["bb"]},  # BB-only
        ]
        mock_rsi.return_value = {"rsi": 50.0}
        mock_candle.return_value = {"open": 100.0, "close": 101.0}

        from src.rules.daily_summary import _send_summary
        await _send_summary({"period": 14}, MagicMock())

        # Check message sent — should only contain BTCUSDT, not ETHUSDT
        sent_msg = mock_send.call_args[0][0]
        assert "BTCUSDT" in sent_msg or "BTC/USDT" in sent_msg
        assert "ETHUSDT" not in sent_msg and "ETH/USDT" not in sent_msg
```

**Step 2: Run — confirm fail**

**Step 3: Implement** — in `_send_summary()`, filter symbols (replace loop ~line 121):
```python
    from src.config import get_symbol_alerts

    symbols_data = []
    for sym_config in symbols_cfg:
        symbol = sym_config["name"]

        # Skip symbols without RSI in their alerts (BB-only don't appear in summary)
        if 'rsi' not in get_symbol_alerts(symbol):
            continue

        rsi_1d_result = analyze_rsi(symbol, "1d", overbought, oversold, period)
        # ... rest unchanged
```

**Step 4: Run — confirm pass**
**Step 5: Commit**
```bash
git add src/rules/daily_summary.py tests/test_daily_summary.py
git commit -m "feat(bb): exclude BB-only symbols from daily summary"
```

---

## Task 5: Integration smoke test

**Step 1: Full suite**
```bash
PYTHONPATH=. python -m pytest tests/ -v
```
Expected: All pass (327 + new).

**Step 2: Dry-run**
```bash
PYTHONPATH=. python src/main.py --dry-run
```
Expected: Startup OK, 16 symbols loaded, backfill all, WS connected, no exceptions.

**Step 3: Commit if fixups**
```bash
git add -A && git commit -m "test(bb): v2 integration smoke test passes"
```

---

## Verify Summary

- [ ] `get_symbol_alerts()` returns correct alerts per symbol
- [ ] BB-only symbols skip RSI/breakout/divergence
- [ ] Daily summary excludes BB-only symbols
- [ ] `_determine_trend()` uses only RSI(1M) — no 1w call
- [ ] 16 symbols load in config (2 full + 14 BB-only)
- [ ] `PYTHONPATH=. python src/main.py --dry-run` — startup sem erros
- [ ] `PYTHONPATH=. pytest tests/ -v` — suíte completa sem regressão
- [ ] Diff cirúrgico
