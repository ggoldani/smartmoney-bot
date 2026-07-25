# Role Contracts — SmartMoney Bot

Define roles, boundaries e handoffs no sistema de workflows.

## Roles

### Orchestrator (este skill)
**Responsabilidade:** Classificar a tarefa, selecionar o workflow, coordenar cross-cutting.
**Pode:** Carregar workflows, pedir classificação, executar review gate final.
**Não pode:** Pular review gate, declarar concluído sem prova executável, carregar workflows não relevantes.

### Workflow Executor (cada workflow skill)
**Responsabilidade:** Executar a tarefa dentro do escopo do módulo, seguindo invariáveis e constraints.
**Pode:** Ler/editar arquivos dentro do escopo, rodar testes, rodar dry-run, criar branches.
**Não pode:** Editar arquivos fora do escopo sem carregar o workflow relevante, pular o review gate do workflow.

### Reviewer (review gate)
**Responsabilidade:** Validar que a mudança é cirúrgica, testes passam, sem regressão.
**Pode:** Bloquear merge, pedir correções, rodar validações adicionais.
**Não pode:** Aprovar sem prova executável (dry-run + testes).

## Handoffs

```
User task
  → Orchestrator classifica
    → Workflow Executor executa (1 ou mais)
      → Reviewer valida (review gate)
        → Orchestrator declara concluído (com prova)
          → User aprova merge
```

## Boundaries por módulo

| Role | Indicators | Engine | Datafeeds | Notif | Storage | Config | Tests | Deploy |
|------|-----------|--------|-----------|-------|---------|--------|-------|--------|
| **Pode criar arquivos em** | `src/indicators/` | `src/rules/` | `src/datafeeds/` | `src/notif/` | `src/storage/` | `configs/`, `src/config.py` | `tests/` | `docker/`, `scripts/` |
| **Pode editar fora do escopo?** | Só integração em `engine.py` + `templates.py` + `free.yaml` | Só `config.py` se precisar de helper | Só `main.py` se startup flow | Só `engine.py` se chamada de throttle | Só `engine.py`/`repo.py` consumers | Nada em `src/` além de `config.py` | Só `src/` se corrigindo bug coberto pelo teste | Só `docker-compose.yml`, `.env.example` |

## Regra de ouro
**Toda declaração de "concluído" deve ser backed by prova executável** — dry-run OK, testes passando, diff cirúrgico. Não existe "concluído" sem evidência.
