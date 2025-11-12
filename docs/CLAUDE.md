# CLAUDE CODE GUIDE - SmartMoney Bot

Documentação completa para futuras instâncias do Claude Code trabalhar neste repositório.

---

## VISÃO GERAL DO PROJETO

**Nome:** SmartMoney Brasil - Crypto Trading Alerts Bot
**Objetivo:** Bot Telegram de alertas de trading para criptomoedas (BTCUSDT) com foco em educação financeira.
**Linguagem:** Python 3.13
**Público-alvo:** Comunidade brasileira interessada em trading, cripto, DeFi, privacidade.

### Modelo de Negócio

**Tier FREE (atual - Sprint 2 completo):**
- Alertas RSI em 2 níveis (normal 70/30, extremo 85/15) em 1h, 4h, 1d
- Alertas de breakout em tempo real (1d, 1w)
- Sistema anti-spam com recovery zones
- Monitoramento de BTCUSDT apenas
- Grupo Telegram público
- Newsletter limitada

**Tier PREMIUM (Sprint 3+ - futuro):**
- Todos os alertas do FREE +
- Multi-símbolos (ETHUSDT, SOLUSDT, etc.)
- BTC Dominance alerts
- Suporte/Resistência automático
- Padrões de candles
- Comandos admin customizados
- Grupo Telegram VIP
- Newsletter completa
- Acesso a todos os cursos

---

## FILOSOFIA DE DESENVOLVIMENTO

### PARANOID SECURITY & EFFICIENCY

1. **NUNCA commitar .env com secrets** (BOT_TOKEN, API keys)
2. **VPS é básico/limitado** - otimizar recursos sempre
3. **Async I/O em tudo** - zero blocking operations
4. **Throttling agressivo** - proteger contra spam de alertas
5. **Graceful shutdown** - sempre limpar conexões (WebSocket, DB)
6. **Docker com resource limits** - 256MB RAM, 0.5 CPU
7. **Indexed queries** - database otimizado para consultas rápidas
8. **Logs estruturados** - facilitar debugging remoto

### CÓDIGO LIMPO

- **Type hints** em todas as funções
- **Docstrings** em português brasileiro
- **Testes** antes de deploy (dry-run obrigatório)
- **Formatação brasileira** em tudo (BRT timezone, R$ com vírgula decimal)
- **Emojis apropriados** nas mensagens Telegram

---

## ARQUITETURA

### Estrutura de Pastas

```
smartmoney-bot/
├── configs/               # YAML configs (free.yaml, premium.yaml)
├── docker/               # Dockerfile
├── docs/                 # Documentação
│   ├── CLAUDE.md         # Este arquivo
│   ├── OPERATIONS.md     # Comandos operacionais
│   └── SPRINT1_COMPLETE.md  # Resultados Sprint 1
├── scripts/              # Scripts utilitários
├── src/
│   ├── backtest/         # Sistema de backtesting (futuro)
│   ├── datafeeds/        # Binance WebSocket + REST API
│   ├── indicators/       # RSI (2 níveis), breakouts
│   ├── notif/            # Templates Telegram + throttling
│   ├── rules/            # Alert engine + anti-spam system
│   ├── storage/          # SQLite ORM + cleanup automático
│   ├── utils/            # Logging, healthcheck HTTP, timeframes
│   ├── viz/              # Charts (futuro - mplfinance)
│   ├── config.py         # YAML config loader
│   ├── main.py           # Orquestração principal
│   └── telegram_bot.py   # Telegram Bot API wrapper
├── .env.example          # Template de variáveis de ambiente
├── .gitignore            # Git ignore rules
├── docker-compose.yml    # Orquestração Docker
├── README.md             # Overview objetiva
└── requirements.txt      # Dependências Python
```

### Componentes Principais

#### 1. Config System (`src/config.py`)
- Carrega `configs/free.yaml` (ou premium no futuro)
- Suporta substituição de env vars: `${BOT_TOKEN}`
- Singleton pattern: `get_config()`

#### 2. Data Feeds (`src/datafeeds/`)
- **`binance_rest.py`**: Backfill histórico (200 velas por TF)
- **`binance_ws.py`**: Real-time klines via WebSocket
  - Exponential backoff com jitter
  - Watchdog 90s para detectar conexão stalled
  - Multi-stream combinado (`btcusdt@kline_1h/btcusdt@kline_4h/...`)
  - Database throttle: 10s para velas abertas, imediato para fechadas (94% redução I/O)

#### 3. Storage (`src/storage/`)
- **SQLite** com SQLAlchemy
- Tabela `candles`: symbol, interval, OHLCV, timestamps
- Unique constraint: `(symbol, interval, open_time)`
- Indexes: otimização para queries RSI
- **`cleanup.py`**: Limpeza automática
  - Daily cronjob às 03:00 UTC
  - Deleta velas > 90 dias
  - Mantém mínimo 200 velas/TF

#### 4. Indicators (`src/indicators/`)
- **RSI** (`rsi.py`): Wilder's smoothing method (período 14)
  - `calculate_rsi(closes, period=14)` → float
  - `analyze_rsi()` → 2 níveis: NORMAL (70/30) + EXTREME (85/15)
  - Condições: OVERSOLD, OVERBOUGHT, EXTREME_OVERSOLD, EXTREME_OVERBOUGHT
- **Breakouts** (`breakouts.py`): Detecção em tempo real
  - `check_breakout()` → BULL/BEAR quando preço rompe high/low anterior
  - Margem 0.1% para evitar falsos positivos

#### 5. Rules Engine (`src/rules/engine.py`)
- Loop assíncrono verificando velas (abertas e fechadas) a cada 5s
- **Sistema Anti-Spam com Recovery Zones:**
  - RSI: só re-alerta se voltar à zona neutra (35-65)
  - Breakouts: só re-alerta se preço voltar ao range
  - Previne spam de alertas repetitivos
- Processa RSI em tempo real (alerta quando toca threshold)
- Processa breakouts em tempo real (preço > high ou < low anterior)
- Consulta throttler antes de enviar
- Suporta consolidação multi-timeframe

#### 6. Notifications (`src/notif/`)
- **`templates.py`**: Mensagens em PT-BR com emojis
  - RSI normal: `template_rsi_overbought()`, `template_rsi_oversold()`
  - RSI extremo: `template_rsi_extreme_overbought()`, `template_rsi_extreme_oversold()`
  - Breakouts: `template_breakout_bull()`, `template_breakout_bear()`
  - Sistema: `template_startup()`, `template_circuit_breaker()`
  - Disclaimer: "DYOR" em todos os alertas
- **`formatter.py`**: Formatação brasileira
  - `format_price_br(67420.50)` → "$67.420,50"
  - `format_datetime_br()` → "11/11/2025 16:30 BRT"
- **`throttle.py`**: Rate limiting
  - Max 20 alertas/hora
  - Circuit breaker: 5 alertas/minuto

#### 7. Main Orchestration (`src/main.py`)
- **Startup sequence:**
  1. Init DB
  2. Load config
  3. Backfill histórico
  4. Enviar startup message
- **Runtime (4 async tasks):**
  - WebSocket listener
  - Alert engine
  - Database cleanup scheduler
  - Healthcheck HTTP server
  - Shutdown handler (SIGTERM/SIGINT)
- **Graceful shutdown:**
  - Fecha WebSocket
  - Para healthcheck server
  - Commit final ao DB
  - Envia shutdown message (opcional)

#### 8. Healthcheck (`src/utils/healthcheck.py`)
- **HTTP Server** (aiohttp) na porta 8080
- **Endpoints:**
  - `GET /health` → Simple 200 OK
  - `GET /status` → Métricas (uptime, alerts_sent, ws_connected, last_alert)
  - `GET /` → Index HTML com links
- **Uso:** Monitoring externo (UptimeRobot, Prometheus, etc.)

---

## SPRINT 1 - COMPLETADO ✅

### Features Implementadas

1. ✅ **Config System** - YAML loader com env var substitution
2. ✅ **Binance REST Backfill** - 200 velas por timeframe (1h, 4h, 1d, 1w)
3. ✅ **Binance WebSocket** - Real-time klines com reconnection resilience
4. ✅ **SQLite Database** - Candles storage com indexes otimizados
5. ✅ **RSI Indicator** - Wilder's method, período 14
6. ✅ **Alert Rules Engine** - RSI overbought/oversold em 1h, 4h, 1d
7. ✅ **Telegram Templates** - PT-BR com formatação brasileira
8. ✅ **Alert Throttling** - 20/hora + circuit breaker 5/minuto
9. ✅ **Admin Channel** - Logs de erro para canal admin
10. ✅ **Graceful Shutdown** - Signal handlers (SIGTERM/SIGINT)
11. ✅ **Docker Setup** - Resource limits (256MB RAM, 0.5 CPU)
12. ✅ **Testing Suite** - Dry-run mode completo
13. ✅ **Real-time Alerts** - Alertas quando RSI toca threshold (não apenas no close)
14. ✅ **Database Throttling** - 10s para velas abertas (94% redução I/O)

---

## SPRINT 2 - COMPLETADO ✅

### Features Implementadas

1. ✅ **Breakout Detection** - Tempo real em 1d/1w
   - Alerta quando preço atual rompe high/low da vela anterior
   - Margem 0.1% para evitar falsos positivos
   - Templates urgentes: "⚡ Preço está rompendo AGORA!"

2. ✅ **Database Cleanup Automático**
   - Cronjob diário às 03:00 UTC
   - Deleta velas > 90 dias
   - Mantém mínimo 200 velas/TF

3. ✅ **Healthcheck HTTP Endpoint**
   - Servidor aiohttp na porta 8080
   - `/health`, `/status`, `/` (index)
   - Métricas: uptime, alerts_sent, ws_connected

4. ✅ **Sistema Anti-Spam com Recovery Zones**
   - RSI: só re-alerta após recovery (35 < RSI < 65)
   - Breakouts: só re-alerta se preço volta ao range
   - Previne spam de alertas repetitivos

5. ✅ **Alertas RSI em 2 Níveis**
   - **Nível 1:** RSI > 70 / < 30 (Atenção)
   - **Nível 2:** RSI > 85 / < 15 (EXTREMO)
   - Templates diferenciados por nível

6. ✅ **Disclaimer Simplificado**
   - Removido "(Do Your Own Research)"
   - Mantido apenas "DYOR"

---

## SPRINT 3 - PRÓXIMO

### Features Planejadas

1. **Support/Resistance Levels**
   - Detecção automática de S/R em múltiplos TFs
   - Alertas quando preço se aproxima de níveis-chave
   - Visualização de níveis fortes vs fracos

2. **Padrões de Candles**
   - Doji, Hammer, Engulfing, etc.
   - Detecção em 1d/1w apenas
   - Alertas de reversão potencial

3. **Multi-Symbol Support (Premium Tier)**
   - ETHUSDT, SOLUSDT, BNBUSDT
   - Config separado: `configs/premium.yaml`
   - Database isolado por tier

4. **Advanced Analytics**
   - Volume profile
   - Order flow heatmap
   - Correlation matrix BTC/alts

---

## CONFIGURAÇÃO

### Arquivo: `configs/free.yaml`

```yaml
bot:
  tier: "free"
  version: "1.0.0"
  name: "SmartMoney Free Bot"

symbols:
  - name: "BTCUSDT"
    timeframes: ["1h", "4h", "1d", "1w"]

backfill:
  enabled: true
  candles_per_timeframe: 200

indicators:
  rsi:
    enabled: true
    period: 14
    overbought: 70
    oversold: 30
    extreme_overbought: 85
    extreme_oversold: 15
    timeframes: ["1h", "4h", "1d"]
    alert_on_touch: true  # Real-time alerts

  breakout:
    enabled: true
    timeframes: ["1d", "1w"]
    margin_percent: 0.1
    alert_on_touch: true

alerts:
  language: "pt-BR"
  timezone: "America/Sao_Paulo"
  consolidate_multi_tf: true
  circuit_breaker:
    enabled: true
    max_alerts_per_minute: 5
  throttling:
    enabled: true
    max_alerts_per_hour: 20
  skip_retroactive_alerts: true

database:
  cleanup:
    enabled: true
    schedule: "0 3 * * *"  # Daily 03:00 UTC
    retention_days: 90
    min_candles_per_tf: 200
```

### Variáveis de Ambiente (.env)

```env
BOT_TOKEN=<botfather_token>
CHANNEL_CHAT_ID=<telegram_channel_id>
ADMIN_CHANNEL_ID=<admin_channel_id>
LOG_LEVEL=INFO
CONFIG_FILE=./configs/free.yaml
ENABLE_CHARTS=false
USE_COINGECKO_FOR_BTCD=true
DB_URL=sqlite:///./data.db
```

**CRÍTICO:** `.env` NUNCA deve ser commitado (secrets reais).

---

## COMANDOS COMUNS

### Desenvolvimento

```bash
# Setup inicial
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Dry-run (sem Telegram)
PYTHONPATH=. python src/main.py --dry-run

# LIVE mode
PYTHONPATH=. python src/main.py

# Com logs
PYTHONPATH=. python src/main.py 2>&1 | tee bot.log
```

### Produção (VPS)

```bash
# Docker (recomendado)
docker-compose up -d
docker-compose logs -f smartmoney-free

# Python direto
nohup PYTHONPATH=. python src/main.py > bot.log 2>&1 & echo $! > bot.pid
kill -SIGTERM $(cat bot.pid)
```

### Database

```bash
# Queries úteis
sqlite3 data.db "SELECT COUNT(*) FROM candles;"
sqlite3 data.db "SELECT symbol, interval, COUNT(*) FROM candles GROUP BY symbol, interval;"

# Backup
cp data.db backup_$(date +%Y%m%d).db
```

### Debugging

```bash
# Verificar RSI atual
python -c "from src.indicators.rsi import get_latest_rsi; print(get_latest_rsi('BTCUSDT', '1h'))"

# Ver logs de throttling
grep "Throttled" bot.log

# Ver alertas enviados
grep "Alert sent" bot.log
```

---

## TROUBLESHOOTING

### Problema: Bot não envia alertas

**Diagnóstico:**
1. Verificar RSI atual: está em zona crítica (>70 ou <30)?
2. Verificar throttling: `grep "Throttled" bot.log`
3. Verificar vela fechada: logs mostram `is_closed: True`?

**Solução:** Aguardar condições de mercado ou ajustar thresholds no config.

---

### Problema: UTF-8 encoding errors

**Diagnóstico:** Emojis ou caracteres PT-BR corrompidos.

**Solução:**
```bash
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8

# Verificar arquivos têm: # -*- coding: utf-8 -*-
```

---

### Problema: WebSocket disconnects frequentes

**Diagnóstico:** `grep "WebSocket" bot.log` mostra reconexões.

**Solução:**
- Verificar firewall VPS
- Aumentar watchdog timeout (90s → 120s)
- Verificar conectividade: `ping stream.binance.com`

---

### Problema: Database vazio após iniciar

**Diagnóstico:** Backfill falhou.

**Solução:**
```bash
rm data.db
PYTHONPATH=. python src/main.py  # Refaz backfill
grep "Backfill" bot.log  # Verificar sucesso
```

---

## REGRAS DE NEGÓCIO

### RSI Alerts

- **Período:** 14 (Wilder's smoothing)
- **Nível 1 (Atenção):**
  - Overbought: > 70
  - Oversold: < 30
- **Nível 2 (EXTREMO):**
  - Extreme Overbought: > 85
  - Extreme Oversold: < 15
- **Timeframes:** 1h, 4h, 1d (apenas)
- **Trigger:** Quando RSI **toca** threshold (tempo real, não apenas no close)
- **Anti-Spam:** Recovery zone 35-65 (só re-alerta após recovery)

### Breakout Alerts

- **Timeframes:** 1d, 1w (apenas)
- **Detecção:** Preço atual rompe high/low da vela **anterior**
- **Margem:** 0.1% para evitar falsos positivos
- **Trigger:** Tempo real (não apenas no close)
- **Anti-Spam:** Só re-alerta se preço voltar ao range

### Throttling

- **Global:** Max 20 alertas/hora
- **Circuit breaker:** 5 alertas/minuto → ativa consolidação
- **Consolidação multi-TF:** Se múltiplos TFs críticos, envia 1 mega-alert

### Formatação Brasileira

- **Moeda:** `$67.420,50` (ponto = milhar, vírgula = decimal)
- **Data:** `11/11/2025 16:30 BRT`
- **Timezone:** America/Sao_Paulo (UTC-3)
- **Linguagem:** Português brasileiro (sem Portugal PT)

---

## DEPENDÊNCIAS CRÍTICAS

```txt
python-telegram-bot==21.6      # Telegram Bot API
pandas>=2.2.3                  # Python 3.13 compatible
loguru==0.7.2                  # Structured logging
APScheduler==3.10.4            # Cronjobs (futuro)
requests==2.32.3               # HTTP client
websockets==12.0               # Binance WebSocket
python-dotenv==1.0.1           # .env loader
SQLAlchemy==2.0.32             # ORM
PyYAML==6.0.1                  # Config parser
pytz==2024.1                   # Timezone handling
aiohttp==3.10.0                # Healthcheck HTTP server
```

**IMPORTANTE:** pandas>=2.2.3 é obrigatório para Python 3.13 (versões antigas não compilam).

---

## PONTOS DE ATENÇÃO

### 1. Multi-bot Setup (Futuro)

Quando implementar bot premium:
- **NÃO duplicar código** - usar mesmo `src/`
- **Configs separados:** `configs/free.yaml` vs `configs/premium.yaml`
- **Docker Compose:** serviços `smartmoney-free` e `smartmoney-premium`
- **Database separado:** `data_free.db` vs `data_premium.db`

### 2. Secrets Management

**NUNCA:**
- Commitar `.env` com secrets reais
- Hardcodar tokens no código
- Expor API keys em logs

**SEMPRE:**
- Usar `.env.example` como template
- Substituir via `${ENV_VAR}` no YAML
- Rotacionar tokens periodicamente

### 3. Resource Limits (VPS Básico)

**Atual:**
- Docker: 256MB RAM, 0.5 CPU
- SQLite (não PostgreSQL) para simplicidade
- Async I/O para evitar threads

**Se escalar:**
- PostgreSQL para múltiplos bots
- Redis para cache de RSI
- Prometheus + Grafana para métricas

---

## TESTES ANTES DE DEPLOY

### Checklist Obrigatória

```bash
# 1. Dry-run local
PYTHONPATH=. python src/main.py --dry-run
# Verificar: backfill OK, WebSocket conectado, RSI calculado

# 2. LIVE local (canal teste)
CHANNEL_CHAT_ID=<seu_chat_pessoal> PYTHONPATH=. python src/main.py
# Verificar: startup message recebida

# 3. Database
sqlite3 data.db "SELECT COUNT(*) FROM candles;"
# Deve ter 800 candles (200 x 4 timeframes)

# 4. Telegram
curl https://api.telegram.org/bot$BOT_TOKEN/getMe
# Deve retornar JSON com bot info

# 5. Binance
curl https://api.binance.com/api/v3/ping
# Deve retornar {}
```

---

## REFERÊNCIAS

- **Docs operacionais:** `docs/OPERATIONS.md`
- **Sprint 1 completo:** `docs/SPRINT1_COMPLETE.md`
- **Binance API:** https://binance-docs.github.io/apidocs/spot/en/
- **python-telegram-bot:** https://docs.python-telegram-bot.org/
- **SQLAlchemy:** https://docs.sqlalchemy.org/

---

## FILOSOFIA DE COMUNICAÇÃO

**Ao trabalhar neste projeto:**

1. **Objetividade** - Respostas densas, sem fluff
2. **Alta densidade** - Informação técnica concentrada
3. **Zero emojis** - Exceto em mensagens Telegram para usuários
4. **Português brasileiro** - Exceto código (variáveis em inglês)
5. **Validação técnica** - Nunca confirmar cegamente, investigar primeiro
6. **Profissionalismo** - Fatos > validação emocional

**Bad:**
> "Você está absolutamente certo! Seu código está perfeito! 🎉"

**Good:**
> "O código funciona, mas há 3 pontos de otimização: [lista objetiva]"

---

**Versão:** 2.0.0
**Última atualização:** 2025-11-11
**Status:** Sprint 2 completo, Sprint 3 planejado
