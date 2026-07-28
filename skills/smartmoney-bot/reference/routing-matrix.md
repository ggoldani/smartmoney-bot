# Routing Matrix — SmartMoney Bot

Matriz determinística de task types → workflows.

## Matiz principal

| Task Type | Sinais (keywords / paths) | Workflow | Arquivos tipicamente afetados |
|-----------|--------------------------|----------|-------------------------------|
| Indicador novo ou mudança de cálculo | "RSI", "breakout", "divergence", "bollinger", "BB", "trend-follow", "novo indicador", "threshold", `src/indicators/` | `indicators` | `src/indicators/*.py`, `src/rules/engine.py`, `src/notif/templates.py`, `configs/free.yaml` |
| Regra de alerta ou engine | "engine", "loop", "regra", "daily summary", "throttle", "condition", `src/rules/` | `engine` | `src/rules/*.py`, `src/config.py` |
| Fonte de dados ou API externa | "websocket", "WS", "binance", "backfill", "fear greed", "market cap", "telegram API", `src/datafeeds/`, `src/telegram_bot.py` | `datafeeds` | `src/datafeeds/*.py`, `src/telegram_bot.py` |
| Formato/conteúdo de notificação | "template", "formato", "mensagem", "PT-BR", "formatter", "throttle config", `src/notif/` | `notif` | `src/notif/*.py` |
| Persistência/DB | "database", "SQLite", "model", "ORM", "query", "repo", "cleanup", "retention", "migration", `src/storage/` | `storage` | `src/storage/*.py` |
| Configuração/env | "config", "YAML", "threshold", "novo symbol", "symbol routing", "alerts field", "bb-only", "feature flag", ".env", `configs/free.yaml`, `src/config.py` | `config` | `configs/free.yaml`, `src/config.py`, `.env.example` |
| Testes/coverage | "teste", "test", "coverage", "TDD", "regressão", `tests/` | `tests` | `tests/*.py`, `tests/conftest.py` |
| Build/deploy/release | "deploy", "docker", "VPS", "build", "release", "systemd", "health", `docker/`, `scripts/` | `deploy` | `docker/Dockerfile`, `docker-compose.yml`, `scripts/deploy.sh`, `docs/OPERATIONS.md` |

## Regras de prioridade (quando múltiplos matches)

1. **Tests** tem prioridade se a tarefa é explicitamente sobre coverage ou TDD, mesmo que toque `src/`.
2. **Config** tem prioridade se a mudança é só em `configs/free.yaml` + `src/config.py`, sem tocar lógica de indicador/engine.
3. **Cross-cutting** se a tarefa toca 2+ módulos `src/` → orquestrador carrega múltiplos workflows + review final unificado.

## Sinais ambíguos

| Sinal | Pode ser | Decidir por |
|-------|----------|------------|
| "Mudar threshold RSI" | config OU indicators | Se só valor em YAML → `config`; se lógica de cálculo → `indicators` |
| "Adicionar alerta novo" | engine OU indicators OU notif | Onde está a lógica? cálculo→`indicators`, regra→`engine`, formato→`notif` |
| "Otimizar query" | storage OU engine | Se é ORM/query → `storage`; se é loop engine → `engine` |

## Task type cross-cutting: symbol routing

| Task Type | Sinais | Workflow(s) | Nota |
|-----------|--------|-------------|------|
| Symbol routing (per-symbol alert subset) | "symbol routing", "alerts field", "bb-only", "adicionar symbol BB-only", `get_symbol_alerts` | `config` (primary) + `engine` (consumer) | Cross-cutting: config define o campo `alerts` por symbol; engine lê via `get_symbol_alerts()` em cada `_collect_*`. Mudar routing só de config → `config`; mudar como engine consome → `engine`. |

## Anti-padrões (NÃO rotear assim)
- ❌ Carregar todos os workflows sempre "por segurança"
- ❌ Pular review gate porque "é só um arquivo pequeno"
- ❌ Declarar concluído sem executar dry-run + testes
