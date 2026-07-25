---
name: smartmoney-bot/deploy
description: Workflow para build Docker, deploy VPS, health checks e release no SmartMoney Bot.
parent: smartmoney-bot
---

# Workflow: Deploy

## Goal
Build, deploy, restart, health check, release.

## Scope
- `docker/Dockerfile` — Imagem do bot
- `docker-compose.yml` — Orquestração (service `smartmoney-free`)
- `scripts/deploy.sh` — Deploy script (21KB, completo)
- `scripts/bootstrap.sh` — Setup VPS
- `scripts/benchmark_io.py` — Benchmark I/O
- `docs/OPERATIONS.md` — Runbook de operação
- `docs/SPRINT1_COMPLETE.md` — Histórico sprint 1

## Triggers
- "Deploy", "docker", "build"
- "VPS", "server", "production"
- "Release", "version bump"
- "Restart", "health check"
- "systemd", "compose"

## Inputs
- Tipo de deploy (full, restart, config-only)
- Ambiente (VPS, local)
- Versão (se release)

## Invariants
- **Docker** com `no-new-privileges`, `cap_drop: ALL`, resource limits (0.5 CPU, 256MB)
- **Healthcheck** HTTP no `localhost:8080/health`
- **Logging** json-file com rotation (10MB, 3 files)
- **Volumes:** `data/` (DB), `logs/`, `configs/` (read-only)
- **Restart policy** `unless-stopped`
- **BuildKit** para cache rápido: `DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1`
- **Resource limits** respeitados (VPS básico)
- **Sem secrets na imagem** — via env_file
- **Configs read-only** no container
- **Sem `eval`/`exec`** em scripts ou entrypoint
- Segue constraints hard do orquestrador (`async/await`, `loguru`, Type hints, sem `eval`/`exec`)

## Procedure

### Deploy full (build + up)
1. Confirmar branch `main` limpa
2. `git pull origin main` (na VPS)
3. Build: `DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker compose up -d --build`
4. Aguardar healthcheck: `docker compose ps` (status healthy)
5. Logs: `docker compose logs -f smartmoney-free` — confirmar startup sequence
6. Confirmar: backfill OK, WS conectado, divergence init OK
7. `docker stats` — memória <200MB

### Restart (sem rebuild)
1. `docker compose restart smartmoney-free`
2. Healthcheck
3. Logs startup
4. Confirmar tasks rodando

### Config-only deploy
1. Editar `configs/free.yaml`
2. `docker compose restart smartmoney-free` (configs são volume read-only)
3. Confirmar novo config carregado nos logs

### Release / version bump
1. Atualizar versão em `configs/free.yaml` → `bot.version`
2. Atualizar `README.md` badge se versão major/minor
3. Commit + tag: `git tag v<x.y.z>`
4. Deploy full

### Health check / troubleshoot
1. `docker compose ps` — status
2. `docker compose logs --tail=100 smartmoney-free` — erros recentes
3. `docker exec smartmoney-free-bot curl -f http://localhost:8080/health` — health interno
4. `docker stats` — recursos
5. SQLite check: `docker exec smartmoney-free-bot python -c "import sqlite3; c=sqlite3.connect('data/data.db'); print(c.execute('PRAGMA integrity_check').fetchone())"`

## Outputs
- Container running, healthy
- Logs confirmam startup sequence
- Resource usage dentro dos limits
- DB integrity OK

## Review gate
- [ ] `docker compose ps` — status `Up (healthy)`
- [ ] Logs: startup sequence completed, WS connected, divergence init OK
- [ ] `docker stats` — memória <200MB
- [ ] `docker exec ... PRAGMA integrity_check` → `ok`
- [ ] Se config change: novo valor carregado (confirmar nos logs)
- [ ] Sem secrets expostos na imagem ou logs

## References
- `docker/Dockerfile` — build steps
- `docker-compose.yml` — service config, volumes, limits
- `scripts/deploy.sh` — deploy script completo
- `docs/OPERATIONS.md` — runbook
