---
name: smartmoney-bot/indicators
description: Workflow para trabalho em indicadores técnicos (RSI, Breakout, Divergence) no SmartMoney Bot.
parent: smartmoney-bot
---

# Workflow: Indicators

## Goal
Implementar ou modificar indicadores técnicos no módulo `src/indicators/`.

## Scope
- `src/indicators/rsi.py` — RSI Wilder's período 14
- `src/indicators/breakouts.py` — Breakouts ±0.15%
- `src/indicators/divergence.py` — Divergência 3-pivot, RSI thresholds 40/60
- Integração: `src/rules/engine.py` (chamadas), `src/notif/templates.py` (templates), `configs/free.yaml` (thresholds)

## Triggers
- "Novo indicador"
- "Mudar cálculo RSI/breakout/divergence"
- "Alterar threshold de cálculo" (não de config)
- "Otimizar performance de indicador"

## Inputs
- Especificação do indicador ou mudança
- Timeframes afetados
- Se novo: thresholds default e template de alerta

## Invariants
- **async/await** se houver I/O (indicadores puros são sync, chamadas DB são async)
- **Type hints** em todas funções
- **Sem hardcode** — thresholds via `get_*_config()`
- **Período RSI** sempre do config (`indicators.rsi.period`)
- **Pivot window** (`pivot_left`, `pivot_right`) sempre do config
- **loguru** para logging (nunca `print`)
- **Sem `eval`/`exec`**
- **Sem raw SQL** — usar SQLAlchemy ORM via `src/storage/repo.py`
- Segue constraints hard do orquestrador (`async/await`, `loguru`, Type hints, sem `eval`/`exec`)

## Procedure

### Novo indicador
1. Criar `src/indicators/<nome>.py` com a lógica de cálculo
2. Type hints completos, docstring explicando fórmula
3. Adicionar chamada em `src/rules/engine.py` no loop apropriado
4. Criar template(s) em `src/notif/templates.py` (PT-BR)
5. Adicionar config em `configs/free.yaml` sob `indicators.<nome>`
6. Adicionar helper `get_<nome>_config()` em `src/config.py`
7. Escrever testes em `tests/test_indicators.py`
8. Atualizar `src/CLAUDE.md` se arquitetura mudou

### Modificar indicador existente
1. Ler o indicador alvo em `src/indicators/`
2. Ler como é chamado em `src/rules/engine.py`
3. Fazer mudança cirúrgica
4. Atualizar testes afetados

## Outputs
- Código do indicador implementado/modificado
- Testes passando
- Templates PT-BR criados (se novo)
- Config YAML atualizada (se novos thresholds)
- `src/CLAUDE.md` atualizado (se arquitetura mudou)

## Review gate
- [ ] `PYTHONPATH=. python src/main.py --dry-run` — sem erros
- [ ] `PYTHONPATH=. pytest tests/test_indicators.py -v` — todos passam
- [ ] `PYTHONPATH=. pytest tests/ -v` — suíte completa sem regressão
- [ ] Coverage mantida (90%+)
- [ ] Sem hardcode de thresholds
- [ ] Type hints presentes
- [ ] Templates PT-BR (se alerta novo)
- [ ] Diff cirúrgico — sem refactor adjacente

## References
- `src/indicators/rsi.py` — padrão de implementação (Wilder's smoothing)
- `src/indicators/divergence.py` — padrão 3-pivot com RSI confirmation
- `configs/free.yaml` — estrutura de config de indicadores
- `src/rules/engine.py` — padrão de integração (chamadas no loop 5s)
