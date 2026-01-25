# CLAUDE.md - Code Patterns & Architecture

See `/smartmoney-bot/CLAUDE.md` for setup/deployment.

## Architecture

`main.py` (startup/shutdown) | `config.py` (YAML loader) | `telegram_bot.py` (API wrapper)

**datafeeds/:** `binance_ws.py` (multi-symbol streams, auto-reconnect) | `binance_rest.py` (200 candles/TF backfill) | `fear_greed.py` (CoinMarketCap API v3)

**indicators/:** `rsi.py` (Wilder's p14) | `breakouts.py` (±0.15%) | `divergence.py` (3-pivot, RSI thresholds 40/60)

**rules/:** `engine.py` (5s loop, init/process divergence, daily summary task) | `rule_defs.py` (recovery zones 40-60)

**notif/:** `formatter.py` (BRT, PT-BR) | `templates.py` (PT-BR) | `throttle.py` (20/hr, 5/min)

**storage/:** `db.py` (SQLAlchemy) | `models.py` (ORM) | `repo.py` (indexed queries) | `cleanup.py` (90d retention)

**utils/:** `logging.py` (loguru async) | `healthcheck.py` (HTTP) | `timeframes.py` (utilities)

## Data Flow

**Startup:** YAML → DB init → backfill (200/TF × N symbols) → startup msg → divergence init (scan 40 candles) → tasks (WS, alerts, daily-summary, cleanup, health)

**Real-time:** WS multi-symbol → candle → DB → 5s loop: RSI/breakout/divergence → rules → throttle → Telegram (5 retries)

**Divergence:** 3-pivot detect → compare prior → RSI confirm (bullish <40, bearish >60) → 2-pivot alert → state persists

**Daily Summary:** 21:05 BRT ±1min → Fear & Greed API v3 (exp backoff 2-4-8s) → RSI 1D/1W/1M (ALTA/BAIXA ≥50/<50) → multi-symbol consolidado → Telegram

**Cleanup:** Daily 3AM UTC, >90d candles deleted (min 200/TF)

---

## Key Components (Compact)

`main.py` startup/shutdown | `config.py` (YAML, `get_symbols/rsi/daily_summary/divergence_config()`) | `binance_ws.py` multi-symbol auto-reconnect | `binance_rest.py` 200/TF | `fear_greed.py` CoinMarketCap API v3, exp backoff 2-4-8s | `rsi.py` Wilder's | `breakouts.py` ±0.15% | `divergence.py` 3-pivot + RSI thresholds 40/60 | `engine.py` 5s loop, divergence init/process, daily-summary multi-symbol | `rule_defs.py` recovery zones 40-60 | `throttle.py` 20/hr, 5/min | `formatter.py` BRT, PT-BR | `templates.py` PT-BR multi-symbol | `repo.py` indexed ORM | `cleanup.py` 90d retention | `logging.py` loguru async | `healthcheck.py` HTTP

**Alert Key:** `"{symbol}_{interval}_{open_time}_{condition}"` (breakout: "BULL"/"BEAR", not "BREAKOUT_*")

## Development Patterns

**New symbol:** `configs/free.yaml` → `symbols:` → restart (backfill automatic)

**New indicator:** `src/indicators/new.py` → `rule_defs.py` → `engine.py` → template → test

**New scheduled task:** async method in `engine.py` → YAML config → `config.py` helper → `main.py` init (conditional)

**Config:** Always use `get_*_config()` (validates, defaults). Never hardcode.

**Queries:** Indexed (symbol, interval, open_time) + LIMIT. Never load entire table.

**APIs:** Exp backoff (2s-4s-8s), error handling, logging, fallback. See `fear_greed.py`.

**Divergence:** `divergence.py` core logic → `engine.__init__()` state → `_initialize/process/send_divergence()` → YAML config (`bullish_rsi_max: 40`, `bearish_rsi_min: 60`) → `get_divergence_config()`

**Daily Summary:** async method + YAML + config helper + init (conditional) + template (multi-symbol consolidado)

**Env vars:** `.env.example` → load → validate early → document

**Debug:** `LOG_LEVEL=DEBUG` + `grep "RSI\|Breakout\|Daily summary\|Fear & Greed\|DIVERGENCE\|divergence_state"`

## Pre-Commit

`PYTHONPATH=. python src/main.py --dry-run` (no errors, WS multi-symbol connected, divergence_state init) | `PYTHONPATH=. pytest tests/ -v` (268 tests) | `docker stats <200MB` | `PRAGMA integrity_check` OK | No `eval/exec` | No raw SQL

## Performance & Code Style

**Targets:** Startup <60s | Memory <200MB | CPU idle <5% | Alert latency <5s | DB queries <10ms

**Style:** Python 3.13 | Async I/O only | SQLAlchemy ORM | loguru JSON | Comments explain "why" | Catch specific exceptions
