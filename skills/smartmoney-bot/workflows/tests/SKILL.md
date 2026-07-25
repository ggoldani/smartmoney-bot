---
name: smartmoney-bot/tests
description: Workflow para criar/manter testes pytest e coverage no SmartMoney Bot.
parent: smartmoney-bot
---

# Workflow: Tests

## Goal
Criar novos testes, aumentar coverage, corrigir testes quebrados, TDD.

## Scope
- `tests/` — Todos arquivos de teste
- `tests/conftest.py` — Fixtures compartilhadas
- Coverage alvo: **95%+** (manter ou aumentar)

## Triggers
- "Teste", "test", "coverage"
- "TDD", "red-green-refactor"
- "Regresão", "regression"
- "Quebrou teste", "fixture"
- "Conftest"

## Inputs
- Módulo/classe a testar
- Comportamento esperado (happy path + edge cases)
- Se TDD: spec antes do implementation

## Invariants
- **pytest** com `pytest-asyncio`
- **Coverage 95%+** — nunca diminuir
- **PYTHONPATH=.** sempre ao rodar
- **Sem I/O real** — mockear DB, Telegram, Binance WS, APIs externas
- **Testes async** marcados com `@pytest.mark.asyncio`
- **Fixtures** em `conftest.py` para reuso
- **Nomeação:** `test_<modulo>_<cenario>` (ex: `test_rsi_overbought_detected`)
- **AAA pattern:** Arrange, Act, Assert
- **Um conceito por teste**
- **Sem `eval`/`exec`**

## Procedure

### TDD (novo feature)
1. **RED:** Escrever teste que falha primeiro
2. **GREEN:** Implementar mínimo que faz passar
3. **REFACTOR:** Melhorar código mantendo verde
4. Repetir

### Aumentar coverage
1. Rodar `PYTHONPATH=. pytest --cov=src tests/`
2. Identificar linhas/módulos sem coverage
3. Para cada gap: escrever teste que exercita o path
4. Rodar coverage novamente
5. Confirmar 95%+

### Corrigir teste quebrado
1. Rodar teste isolado: `PYTHONPATH=. pytest tests/<file>::<test> -v`
2. Ler erro + traceback
3. Identificar: bug no código ou teste desatualizado?
4. Se bug: corrigir código (carga o workflow relevante)
5. Se teste: atualizar para comportamento correto
6. Suíte completa

### Novo fixture
1. Adicionar em `tests/conftest.py`
2. Reutilizável, com cleanup se necessário
3. Documentar scope (function/module/session)

## Outputs
- Testes novos/corrigidos
- Coverage mantida ou aumentada
- Suíte completa passando

## Review gate
- [ ] `PYTHONPATH=. pytest tests/ -v` — todos passam
- [ ] `PYTHONPATH=. pytest --cov=src tests/` — coverage 95%+
- [ ] Sem I/O real (DB/Telegram/WS mockeados)
- [ ] Testes async marcados corretamente
- [ ] AAA pattern seguido
- [ ] Nomeação consistente
- [ ] Diff cirúrgico

## References
- `tests/conftest.py` — fixtures existentes
- `tests/test_indicators.py` — padrão de teste de indicador
- `tests/test_divergence.py` — padrão de teste complexo
- `tests/test_websocket.py` — padrão de mock WS
- `tests/test_throttle.py` — padrão de teste de throttle
