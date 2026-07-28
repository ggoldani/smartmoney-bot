---
name: smartmoney-bot/config
description: Workflow para configuração YAML, env vars e helpers de config no SmartMoney Bot.
parent: smartmoney-bot
---

# Workflow: Config

## Goal
Modificar configuração do bot: thresholds, symbols, feature flags, env vars.

## Scope
- `configs/free.yaml` — Config principal (bot, symbols, indicators, alerts, database, logging)
- `src/config.py` — YAML loader, validation, helpers `get_*_config()`
- `src/config.py::get_bollinger_config()` — BB params (period, std_mult, buffer_pct, trend)
- `src/config.py::get_symbol_alerts()` — per-symbol alert routing (lê campo `alerts` de cada symbol)
- `.env` / `.env.example` — Environment variables (BOT_TOKEN, CHANNEL_CHAT_ID, etc)

## Triggers
- "Config", "YAML", "configuration"
- "Threshold", "parâmetro"
- "Novo symbol", "adicionar BTCUSDT"
- "Feature flag", "enable/disable"
- "Env var", ".env"
- "Timeframe"

## Inputs
- Chave de config a mudar (path YAML)
- Valor novo
- Justificativa (impacto no comportamento)

## Invariants
- **Sem hardcode** — todo valor de runtime vem do config ou env
- **Helpers `get_*_config()`** sempre validam e aplicam defaults
- **YAML** é source of truth para comportamento; **env** para secrets
- **`.env` nunca commitado** (gitignore)
- **Type hints** e validation em todos helpers
- **Defaults** explícitos em helpers (se key missing, não crasha)
- **Documentar** novas env vars em `.env.example`
- **async/await** não aplicável (config é carregada sync no startup)
- **loguru** para logging de validation errors (nunca `print`)
- **Type hints** em todas funções helper
- **Sem `eval`/`exec`**
- Segue constraints hard do orquestrador (`async/await`, `loguru`, Type hints, sem `eval`/`exec`)

## Procedure

### Mudar threshold/parâmetro
1. Editar `configs/free.yaml` na chave apropriada
2. Verificar se `get_*_config()` em `src/config.py` lê a chave
3. Se novo: adicionar helper + default + validation
4. Dry-run para confirmar carregamento
5. Atualizar `.env.example` se for env var

### Adicionar symbol
1. Adicionar entry em `configs/free.yaml` → `symbols:`
2. Format: `- name: "BTCUSDT"` + `timeframes: [...]`
3. Backfill é automático no startup
4. Dry-run confirma symbols loaded

### Adicionar symbol BB-only
1. Adicionar entry em `configs/free.yaml` → `symbols:` com:
   - `name: "<SYMBOL>USDT"`
   - `timeframes: ["1d", "1M"]` (apenas timeframes necessários para BB trend-follow)
   - `alerts: ["bb"]` (subset — só alerta BB, não RSI/breakout/divergence)
2. O engine lê via `get_symbol_alerts(symbol)` e pula `_collect_rsi`/`_collect_breakout`/`_process_divergences` para esse symbol
3. Backfill automático no startup (200 candles por timeframe)
4. Dry-run confirma symbol loaded + routing correto
5. Sem mudança em `src/` — routing é puramente config-driven

### Adicionar feature flag
1. Adicionar boolean em `configs/free.yaml` sob módulo relevante
2. Adicionar leitura em `get_*_config()` com default seguro
3. Usar flag no engine/datafeed/indicator apropriado
4. Testar ambos estados (on/off)

### Nova env var
1. Adicionar em `.env.example` com descrição
2. Carregar em `src/config.py` via `os.getenv()` com validação
3. Documentar no README se for user-facing

## Outputs
- `configs/free.yaml` atualizado
- `src/config.py` atualizado (se novo helper)
- `.env.example` atualizado (se nova env var)
- Testes passando

## Review gate
- [ ] `PYTHONPATH=. python src/main.py --dry-run` — config carrega sem erros
- [ ] `PYTHONPATH=. pytest tests/test_config.py -v` — testes config passam
- [ ] `PYTHONPATH=. pytest tests/ -v` — suíte completa
- [ ] Helper `get_*_config()` validado (se chave nova)
- [ ] `.env.example` atualizado (se env var nova)
- [ ] Sem hardcode em `src/`
- [ ] Diff cirúrgico

## References
- `configs/free.yaml` — estrutura completa
- `src/config.py` — padrão de helper com validation
- `.env.example` — env vars documentadas
- `tests/test_config.py` — padrão de teste + `TestSymbolAlerts` (symbol routing tests)
