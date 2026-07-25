---
name: smartmoney-bot/notif
description: Workflow para templates PT-BR, formatter e throttle no SmartMoney Bot.
parent: smartmoney-bot
---

# Workflow: Notif

## Goal
Modificar formato, conteúdo ou throttling de notificações/alertas Telegram.

## Scope
- `src/notif/templates.py` — Templates PT-BR (RSI, breakout, divergence, mega-alert, daily summary)
- `src/notif/formatter.py` — Formatação BRT, PT-BR
- `src/notif/throttle.py` — Throttling (20/hr, 5/min), circuit breaker

## Triggers
- "Template", "formato", "mensagem"
- "PT-BR", "texto do alerta"
- "Throttle", "rate limit", "spam"
- "Circuit breaker"
- "Formatter", "timezone", "BRT"

## Inputs
- Especificação do formato/conteúdo
- Regra de throttle (se aplicável)
- Quais alertas afetados

## Invariants
- **PT-BR** em todos templates de alerta
- **BRT** (America/Sao_Paulo) para timestamps
- **Throttle** config: `alerts.throttling.max_alerts_per_hour` (default 20)
- **Circuit breaker**: `alerts.circuit_breaker.max_alerts_per_minute` (default 5)
- **Consolidação** 6s no engine (não duplicar com multi-TF consolidate)
- **Mega-alerts** para condições extremas (🚨🔴 vs 🔴)
- **Type hints** em todas funções
- **Sem hardcode** — thresholds via config
- **async/await** quando chamado de contexto async (throttle calls)
- **loguru** para logging (nunca `print`)
- **Type hints** em todas funções
- **Sem `eval`/`exec`**
- Segue constraints hard do orquestrador (`async/await`, `loguru`, Type hints, sem `eval`/`exec`)

## Procedure

### Novo template de alerta
1. Criar função em `src/notif/templates.py` seguindo padrão existente
2. PT-BR, com emoji apropriado, timestamps BRT
3. Chamar de `src/rules/engine.py` ou indicador apropriado
4. Integrar com throttle (`get_throttler()`)
5. Testes em `tests/test_formatter.py` ou `tests/test_throttle.py`

### Modificar throttle
1. Ler `src/notif/throttle.py` — entender `Throttler` class
2. Respeitar config `alerts.throttling.*` e `alerts.circuit_breaker.*`
3. Mudança cirúrgica
4. Testes: window reset, max per hour, max per minute, circuit breaker trigger

### Modificar formatter
1. Ler `src/notif/formatter.py` — entender helpers BRT
2. Sempre usar `America/Sao_Paulo` timezone
3. Testes em `tests/test_formatter.py`

## Outputs
- Template/formatter/throttle modificado
- Testes passando
- Config atualizada se necessário

## Review gate
- [ ] `PYTHONPATH=. pytest tests/test_formatter.py tests/test_throttle.py -v` — testes notif passam
- [ ] `PYTHONPATH=. pytest tests/ -v` — suíte completa
- [ ] Templates em PT-BR
- [ ] Timestamps em BRT
- [ ] Throttle config respeitada (sem hardcode)
- [ ] Type hints presentes
- [ ] Diff cirúrgico

## References
- `src/notif/templates.py` — todos templates PT-BR existentes
- `src/notif/throttle.py` — padrão Throttler
- `src/notif/formatter.py` — helpers BRT
- `configs/free.yaml` — `alerts.throttling.*`, `alerts.circuit_breaker.*`
- `tests/test_formatter.py`, `tests/test_throttle.py` — padrão de teste
