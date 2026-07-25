# CLAUDE.md

Guia para Claude Code neste repositório.

## ⚠️ Comportamento CRÍTICO

**OBRIGATÓRIO:**
- SEMPRE perguntar antes de editar código ou executar comandos
- SUGERIR primeiro, aguardar aprovação
- Se não tiver certeza ou contexto, PERGUNTAR - nunca supor
- Commits: sugerir apenas (sem push), sempre em português

**ANTI-ALUCINAÇÃO:**
- Se informação não está no contexto → perguntar
- Se não tem certeza → perguntar
- NUNCA inventar dados, valores ou comportamentos

---

## Contexto Rápido

**SmartMoney Bot v2.4.0:** Bot Telegram de alertas crypto (multi-symbol: BTCUSDT, PAXGUSDT, etc).

| Stack | Valor |
|-------|-------|
| Python | 3.13+ (async/await) |
| DB | SQLite + SQLAlchemy ORM |
| WebSocket | Binance (multi-symbol streams) |
| Telegram | python-telegram-bot 21.x |
| Scheduler | APScheduler |
| Logging | loguru (async) |
| Tests | pytest (268 tests, 95%+ coverage) |

**Config:** `configs/free.yaml` | **Env:** `.env` | **Logs:** `logs/bot.log`

**Data Flow:** WS multi-symbol → Candles (SQLite) → Indicators (5s) → Rules → Throttle → Telegram

---

## Regras de Código

**✅ DO:**
- Type hints obrigatórios em todas funções
- async/await para todas operações I/O
- loguru para logging (não print)
- SQLAlchemy ORM (não raw SQL)
- Testes 90%+ coverage
- Texto PT-BR para templates/alertas
- Inglês para código/comments/docstrings

**❌ DON'T:**
- Hardcode valores (usar config YAML)
- Commit .env com secrets
- Quebrar testes existentes
- I/O síncrono em funções async
- eval/exec

---

## Comandos Rápidos

```bash
# Dev Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Testes
PYTHONPATH=. pytest tests/ -v              # Todos (268 tests)
PYTHONPATH=. pytest --cov=src tests/       # Com coverage
PYTHONPATH=. pytest tests/test_divergence.py -v  # Módulo específico

# Run
PYTHONPATH=. python src/main.py --dry-run  # Test mode (sem Telegram)
PYTHONPATH=. python src/main.py            # Production

# Quality
black src/ tests/                          # Format
mypy src/                                  # Type check
flake8 src/                                # Lint

# Monitor
tail -f logs/bot.log | grep "ERROR\|Alert\|DIVERGENCE"
```

---

## Estrutura

```
src/
├── main.py           # Startup → backfill → WS → alerts → shutdown
├── config.py         # YAML loader + validation
├── telegram_bot.py   # Telegram API wrapper
├── datafeeds/        # Binance WS/REST, Fear & Greed API
├── indicators/       # RSI, Breakouts, Divergence
├── rules/engine.py   # Alert engine (5s loop) + daily summary
├── notif/            # Templates PT-BR, throttling, formatting
├── storage/          # SQLAlchemy models, indexed queries
└── utils/            # Logging, healthcheck, timeframes
```

---

## Referências

- **README.md** - Setup completo, troubleshooting, deploy, regras de negócio
- **src/CLAUDE.md** - Arquitetura detalhada e padrões de código
- **configs/free.yaml** - Todas configurações (RSI, breakouts, divergence, alerts)

---

## Tarefas Comuns

| Tarefa | Passos |
|--------|--------|
| **Add Symbol** | `configs/free.yaml` → `symbols:` → restart |
| **Modify Thresholds** | `configs/free.yaml` → `indicators:` → restart |
| **Debug Mode** | `LOG_LEVEL=DEBUG PYTHONPATH=. python src/main.py --dry-run` |
| **New Indicator** | `src/indicators/new.py` → rule em `engine.py` → template → test |
