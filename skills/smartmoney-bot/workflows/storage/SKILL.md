---
name: smartmoney-bot/storage
description: Workflow para SQLAlchemy models, repo, queries, cleanup e init_db no SmartMoney Bot.
parent: smartmoney-bot
---

# Workflow: Storage

## Goal
Modificar schema, models ORM, queries, retention/cleanup ou inicialização do SQLite.

## Scope
- `src/storage/models.py` — SQLAlchemy ORM models (Candle, etc)
- `src/storage/db.py` — SessionLocal, engine config
- `src/storage/repo.py` — Indexed queries (symbol, interval, open_time) + LIMIT
- `src/storage/cleanup.py` — Retention 90d, min 200 candles/TF, daily 3AM UTC
- `src/storage/init_db.py` — Create all tables

## Triggers
- "Database", "SQLite", "DB"
- "Model", "ORM", "schema"
- "Query", "repo", "índice"
- "Cleanup", "retention", "purge"
- "Migration", "nova tabela"
- "PRAGMA", "integrity check"

## Inputs
- Schema change spec (se model novo)
- Query requirements (filtros, ordenação, limite)
- Retention policy (se cleanup)

## Invariants
- **SQLAlchemy ORM** apenas — nunca raw SQL
- **SQLite** via `DB_URL=sqlite:///./data/data.db`
- **Indexed queries** sempre com (symbol, interval, open_time) + LIMIT
- **Nunca carregar tabela inteira** — sempre LIMIT
- **Cleanup** respeita `database.cleanup.retention_days` (90d) e `min_candles_per_tf` (200)
- **Cleanup schedule** via `database.cleanup.schedule` cron (default `0 3 * * *`)
- **Type hints** em todas funções
- **async session** quando chamado de contexto async
- **loguru** para logging em cleanup/init (nunca `print`)
- **Type hints** em todas funções
- **Sem `eval`/`exec`**
- Segue constraints hard do orquestrador (`async/await`, `loguru`, Type hints, sem `eval`/`exec`)

## Procedure

### Novo model/tabela
1. Definir SQLAlchemy model em `src/storage/models.py`
2. Criar indexes em colunas de query frequente (symbol, interval, open_time)
3. Adicionar repo methods em `src/storage/repo.py` (sempre com LIMIT)
4. `init_db()` cria tabelas automaticamente (`create_all`)
5. Se migration de dados: script em `scripts/` (não auto)
6. Testes cobrindo CRUD + edge cases

### Modificar query existente
1. Ler `src/storage/repo.py` — entender queries indexed
2. Sempre usar filter + order_by + limit
3. Mudança cirúrgica
4. Testar com dados reais (dry-run)

### Modificar cleanup
1. Ler `src/storage/cleanup.py` — `schedule_cleanup_task()`
2. Respeitar `retention_days` e `min_candles_per_tf`
3. Schedule via APScheduler cron
4. Testar retenção: não deletar abaixo do min

## Outputs
- Model/repo/cleanup modificado
- Testes passando
- `PRAGMA integrity_check` OK
- Indexes criados se nova coluna de query

## Review gate
- [ ] `PYTHONPATH=. python src/main.py --dry-run` — init_db OK
- [ ] `PYTHONPATH=. pytest tests/ -v` — suíte completa
- [ ] `PRAGMA integrity_check` no SQLite → OK (se tocou storage)
- [ ] Sem raw SQL
- [ ] Queries com LIMIT
- [ ] Indexes apropriados
- [ ] Cleanup respeita min_candles_per_tf
- [ ] Diff cirúrgico

## References
- `src/storage/models.py` — padrão ORM
- `src/storage/repo.py` — padrão queries indexed
- `src/storage/cleanup.py` — retention pattern
- `configs/free.yaml` — `database.cleanup.*`
