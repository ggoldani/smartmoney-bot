---
name: smartmoney-bot/engine
description: Workflow para o alert engine, regras, daily summary e divergence processor no SmartMoney Bot.
parent: smartmoney-bot
---

# Workflow: Engine

## Goal
Modificar o alert engine principal, regras de alerta, daily summary ou divergence processor.

## Scope
- `src/rules/engine.py` — AlertEngine (5s loop), init, process divergence, daily summary task
- `src/rules/rule_defs.py` — Definições de regras (recovery zones 40-60)
- `src/rules/daily_summary.py` — Resumo diário (Fear & Greed + RSI 1D/1W/1M)
- `src/rules/divergence_processor.py` — Processamento de divergência
- **Symbol routing:** `get_symbol_alerts(symbol)` checks em `_collect_rsi`/`_collect_breakout`/`_collect_bb` + `_process_divergences` + `check_multi_tf_consolidation`
- **`_determine_trend()`** — usa RSI(1M) apenas (weekly dropado em v2), retorna `tuple[Optional[str], Optional[float]]` (trend, rsi_value)
- **`_collect_bb_alert()`** state machine — reset quando preço retorna dentro das bands (`is_price_inside_bands`)
- Integração: `src/config.py` (helpers), `src/storage/repo.py` (queries), `src/indicators/bollinger.py` (BB breach detection)

## Triggers
- "Mudar regra de alerta"
- "Engine loop", "5s loop"
- "Daily summary", "resumo diário"
- "Throttle", "circuit breaker"
- "Nova condição de alerta"
- "Alert key", "dedup", "last_condition"
- "Otimizar loop do engine"

## Inputs
- Especificação da regra/mudança
- Timeframes afetados
- Comportamento esperado (quando disparar, quando suprimir)

## Invariants
- **async/await** em todo I/O (DB, Telegram, APIs)
- **Loop principal** roda a cada 5s (`check_interval`)
- **Alert key** formato: `"{symbol}_{interval}_{open_time}_{condition}"`
- **Dedup** via `alerted_candles` + `last_condition` + `alerted_candles_with_timestamp`
- **Throttle** via `src/notif/throttle.py` (20/hr, 5/min)
- **Consolidação** janela 6s (`consolidation_interval`)
- **Recovery zone** 40-60 reseta state (previne spam em reversões)
- **skip_retroactive_alerts** — não alertar condições enquanto bot esteve offline
- **Symbol routing:** cada `_collect_*` checa `get_symbol_alerts(symbol)` antes de processar (subset de alerts por symbol)
- **BB trend filter:** `_determine_trend` usa RSI(1M) apenas, retorna `(trend, rsi_value)` tuple
- **Sem hardcode** — config via `get_*_config()`
- **Type hints** em todas funções
- **loguru** para logging (nunca `print`)
- **Sem `eval`/`exec`**
- Segue constraints hard do orquestrador (`async/await`, `loguru`, Type hints, sem `eval`/`exec`)

## Procedure

### Nova regra/condição de alerta
1. Definir condição em `src/rules/rule_defs.py` ou inline em `engine.py`
2. Adicionar check no `_process_candle()` ou método apropriado do `AlertEngine`
3. Definir alert key único seguindo o formato
4. Integrar com throttle (`get_throttler()`)
5. Criar template em `src/notif/templates.py` se necessário
6. Adicionar config em `configs/free.yaml` + helper em `src/config.py`
7. Testes cobrindo: trigger, dedup, recovery, throttle

### Modificar engine loop
1. Ler `AlertEngine.__init__()` e `run()` para entender state
2. Identificar onde a mudança se encaixa (init, loop, cleanup)
3. Mudança cirúrgica — não quebrar tasks existentes (WS, alert, cleanup, health, daily)
3. Atualizar `last_processed`, `alerted_candles`, `last_condition` conforme necessário
4. Testar dry-run + suíte completa

### Daily summary
1. Método async no `AlertEngine`
2. Config: `alerts.daily_summary.enabled`, `send_time_brt`, `send_window_minutes`
3. Task criada condicionalmente em `main.py` se habilitada
4. Template multi-symbol consolidado em `templates.py`
5. Fear & Greed via `src/datafeeds/fear_greed.py` (exp backoff)

## Outputs
- Engine modificado
- Testes passando
- Config atualizada se necessário
- `src/CLAUDE.md` atualizado se arquitetura mudou

## Review gate
- [ ] `PYTHONPATH=. python src/main.py --dry-run` — sem erros, divergence init OK
- [ ] `PYTHONPATH=. pytest tests/ -v` — suíte completa sem regressão
- [ ] Coverage mantida (90%+)
- [ ] Alert keys seguem formato canônico
- [ ] Dedup/throttle integrados
- [ ] Sem I/O síncrono em funções async
- [ ] Diff cirúrgico

## References
- `src/rules/engine.py` — AlertEngine completo (937 linhas)
- `src/rules/rule_defs.py` — recovery zones
- `src/indicators/bollinger.py` — BB breach detection + `is_price_inside_bands` (anti-spam reset)
- `src/main.py` — task creation pattern (linhas 128-145)
- `configs/free.yaml` — `alerts.*` section
