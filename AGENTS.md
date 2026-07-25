# AGENTS.md — SmartMoney Bot

Bot Telegram de alertas crypto (multi-symbol: BTCUSDT, PAXGUSDT, etc).
Alertas: RSI | Breakouts | Divergência RSI | Resumo Diário (Fear & Greed).

**Stack:** Python 3.13+ (async) | SQLite + SQLAlchemy | Binance WS | python-telegram-bot 21.x | APScheduler | loguru | pytest (268 tests, 95%+ coverage)

---

## Skill System (carregar contexto sob demanda)

Este repo usa um sistema de **skills/workflows** para carregar apenas o contexto relevante por tarefa.

**Entry point:** `skills/smartmoney-bot/SKILL.md`

### Routing rápido

| Se a tarefa envolve... | Workflow |
|------------------------|----------|
| Indicadores (RSI, Breakout, Divergence) | `skills/smartmoney-bot/workflows/indicators/SKILL.md` |
| Alert engine, regras, daily summary | `skills/smartmoney-bot/workflows/engine/SKILL.md` |
| Binance WS/REST, Fear & Greed, Telegram API | `skills/smartmoney-bot/workflows/datafeeds/SKILL.md` |
| Templates PT-BR, formatter, throttle | `skills/smartmoney-bot/workflows/notif/SKILL.md` |
| SQLAlchemy, models, queries, cleanup | `skills/smartmoney-bot/workflows/storage/SKILL.md` |
| Config YAML, env vars, thresholds, symbols | `skills/smartmoney-bot/workflows/config/SKILL.md` |
| Testes pytest, coverage | `skills/smartmoney-bot/workflows/tests/SKILL.md` |
| Build Docker, deploy VPS, release | `skills/smartmoney-bot/workflows/deploy/SKILL.md` |

**Cross-cutting (2+ módulos):** carregar todos os workflows relevantes + review final unificado.

### Reference docs
- `skills/smartmoney-bot/reference/routing-matrix.md` — matriz task → workflow
- `skills/smartmoney-bot/reference/role-contracts.md` — contratos de role e boundaries

---

## Constraints hard (sempre aplicar)

- **async/await** em todo I/O (nunca síncrono em funções async)
- **loguru** para logging (nunca `print`)
- **SQLAlchemy ORM** (nunca raw SQL)
- **Type hints** em todas funções
- **90%+ coverage** nos testes (manter ou aumentar)
- **PT-BR** em alertas/templates; **EN** em código/comments/docstrings
- **`get_*_config()`** sempre — nunca hardcodear valores de config
- **Queries indexed** (symbol, interval, open_time) + LIMIT
- **APIs externas** com exp backoff e error handling
- **Sem `eval`/`exec`**

---

## Quick Reference

### Comandos
```bash
# Setup
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Testes
PYTHONPATH=. pytest tests/ -v                    # Todos
PYTHONPATH=. pytest --cov=src tests/             # Coverage
PYTHONPATH=. pytest tests/test_indicators.py -v  # Módulo específico

# Run
PYTHONPATH=. python src/main.py --dry-run        # Test mode (sem Telegram)
PYTHONPATH=. python src/main.py                  # Produção
PYTHONPATH=. python src/main.py --ws-multi        # Test WS multi-TF
PYTHONPATH=. python src/main.py --backfill        # Backfill only

# Deploy
DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker compose up -d --build
docker compose logs -f smartmoney-free
docker compose restart smartmoney-free
```

### Estrutura
```
src/
├── main.py              # Startup → backfill → WS → alerts → shutdown
├── config.py            # YAML loader + validation + get_*_config() helpers
├── telegram_bot.py      # Telegram API wrapper
├── datafeeds/           # Binance WS/REST, Fear & Greed, Market Caps
├── indicators/          # RSI, Breakouts, Divergence
├── rules/               # Alert engine (5s loop) + daily summary + divergence processor
├── notif/               # Templates PT-BR, throttling, formatting
├── storage/             # SQLAlchemy models, indexed queries, cleanup
└── utils/               # Logging, healthcheck, timeframes

configs/free.yaml        # Config principal
tests/                   # pytest (268 tests)
docker/                  # Dockerfile
scripts/                 # deploy.sh, bootstrap.sh, benchmark_io.py
```

### Data Flow
**Startup:** YAML → DB init → backfill (200/TF × N symbols) → divergence init → tasks (WS, alerts, daily-summary, cleanup, health)

**Real-time:** WS multi-symbol → candle → DB → 5s loop: RSI/breakout/divergence → rules → throttle → Telegram

---

## Documentação
- **`README.md`** — Setup completo, troubleshooting, deploy, regras de negócio
- **`src/CLAUDE.md`** — Arquitetura detalhada e padrões de código
- **`docs/legacy/CLAUDE.md`** — Guia legacy (arquivado, substituído por este AGENTS.md + skills)
- **`docs/OPERATIONS.md`** — Runbook de operação
- **`configs/free.yaml`** — Todas configurações
