---
name: smartmoney-bot
description: Orchestrator for SmartMoney Bot repo — routes tasks to scoped workflow skills (indicators, engine, datafeeds, notif, storage, config, tests, deploy).
version: 1.0.0
---

# SmartMoney Bot — Orchestrator

## Objetivo
Roteamento determinístico de tarefas no repo SmartMoney Bot. Carrega apenas o workflow relevante, executa com contrato verificável, e faz review gate antes de entregar.

## Contexto do projeto
- **Repo:** `/home/goldani/smartmoney-bot`
- **Stack:** Python 3.13+ async, Binance WS multi-symbol, SQLite+SQLAlchemy, APScheduler, loguru, python-telegram-bot 21.x
- **Entry point:** `src/main.py` → startup → backfill → WS → alert engine (5s loop) → Telegram
- **Config:** `configs/free.yaml` | **Env:** `.env` | **Tests:** pytest (334 tests, 95%+ coverage)
- **Data Flow:** WS multi-symbol → Candles (SQLite) → Indicators (5s) → Rules → Throttle → Telegram
- **Symbols:** 16 symbols (2 full: BTCUSDT, PAXGUSDT — all alerts; 14 BB-only: ETH/SOL/BNB/XRP/DOGE/AVAX/LINK/LTC/SUI/AAVE/ONDO/ZEC/XLM/AERO — alerts: ["bb"] only, timeframes ["1d","1M"])

## Módulos do repo
| Módulo | Path | LOC | Responsabilidade |
|--------|------|-----|------------------|
| indicators | `src/indicators/` | 751 | RSI (Wilder's p14), Breakouts (±0.15%), Divergence (3-pivot), BB Trend (21/2σ trend-follow) |
| rules | `src/rules/` | 1.470 | Alert engine (5s loop), rule_defs, daily_summary, divergence_processor, BB trend-follow integration, symbol routing (`get_symbol_alerts`) |
| datafeeds | `src/datafeeds/` | 595 | Binance WS/REST, Fear & Greed, Market Caps |
| notif | `src/notif/` | 855 | Templates PT-BR, formatter, throttle (20/hr, 5/min) |
| storage | `src/storage/` | 290 | SQLAlchemy ORM, models, repo, cleanup, init_db |
| utils | `src/utils/` | 240 | Logging, healthcheck, timeframes |
| root | `src/*.py` | ~700 | main.py, config.py, telegram_bot.py |

## Decisão de routing (determinística)

### Q1 — Tarefa altera `src/indicators/` (RSI, Breakout, Divergence, Bollinger/BB trend-follow)?
→ **Sim:** carregar `workflows/indicators/SKILL.md`

### Q2 — Tarefa altera `src/rules/` (engine, rule_defs, daily_summary, divergence_processor)?
→ **Sim:** carregar `workflows/engine/SKILL.md`

### Q3 — Tarefa altera `src/datafeeds/` ou `src/telegram_bot.py` (Binance WS/REST, Fear&Greed, Market Caps, Telegram API)?
→ **Sim:** carregar `workflows/datafeeds/SKILL.md`

### Q4 — Tarefa altera `src/notif/` (templates PT-BR, formatter, throttle)?
→ **Sim:** carregar `workflows/notif/SKILL.md`

### Q5 — Tarefa altera `src/storage/` (SQLAlchemy, models, repo, cleanup, init_db)?
→ **Sim:** carregar `workflows/storage/SKILL.md`

### Q6 — Tarefa altera `configs/free.yaml`, `src/config.py`, ou `.env`?
→ **Sim:** carregar `workflows/config/SKILL.md`

### Q7 — Tarefa é criar/manter testes em `tests/` ou coverage?
→ **Sim:** carregar `workflows/tests/SKILL.md`

### Q8 — Tarefa é build, deploy, docker, VPS, release?
→ **Sim:** carregar `workflows/deploy/SKILL.md`

### Q9 — Nenhum dos acima?
→ **Pedir classificação explícita antes de agir.**

## Cross-cutting (2+ módulos)
Se a tarefa toca múltiplos módulos:
1. Carregar todos os workflows relevantes
2. Executar cada workflow em sequência
3. **Review gate final unificado** antes de entregar (diff check, dry-run, testes)

## Constraints hard (aplicáveis a todos os workflows)
- **async/await** obrigatório em todas operações I/O
- **loguru** para logging (nunca `print`)
- **SQLAlchemy ORM** (nunca raw SQL)
- **Type hints** em todas funções
- **90%+ coverage** nos testes (manter ou aumentar)
- **PT-BR** em alertas/templates; **EN** em código/comments/docstrings
- **`get_*_config()`** sempre — nunca hardcodear valores de config
- **Queries indexed** (symbol, interval, open_time) + LIMIT
- **APIs** com exp backoff e error handling
- **Sem `eval`/`exec`**

## Review gate (obrigatório antes de declarar concluído)
Todo workflow deve provar o resultado:
1. `PYTHONPATH=. python src/main.py --dry-run` — sem erros, WS conecta, divergence init OK
2. `PYTHONPATH=. pytest tests/ -v` — todos passam, coverage mantida
3. `PRAGMA integrity_check` OK no SQLite (se tocou storage)
4. Sem raw SQL, sem eval/exec
5. `docker stats` <200MB (se deploy relevante)
6. Diff revisado — mudança cirúrgica, sem refactor adjacente

## Regras do orquestrador
- Ler **só** o workflow selecionado
- Não carregar documentação de outras camadas sem necessidade
- Se cross-cutting: fazer review final unificado
- **Gate mínimo:** sempre provar resultado com build/test/log/diff
- **Source of truth:** `README.md`, `src/CLAUDE.md`, `configs/free.yaml`

## Referências internas
- `reference/routing-matrix.md` — matriz detalhada de task type → workflow
- `reference/role-contracts.md` — contratos de role e boundaries

## Source files do repo
- **`README.md`** — setup completo, troubleshooting, deploy, regras de negócio
- **`src/CLAUDE.md`** — arquitetura detalhada e padrões de código
- **`configs/free.yaml`** — todas configurações (RSI, breakouts, divergence, bollinger, alerts, symbol routing (alerts field), DB, logging)
- **`agents/code-reviewer.md`** — agent de code review pré-existente
