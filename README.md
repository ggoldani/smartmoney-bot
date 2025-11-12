# SmartMoney Bot

Bot Telegram de alertas de trading para criptomoedas (BTCUSDT) com foco no mercado brasileiro. Alertas RSI (sobrecomprado/sobrevendido) em múltiplos timeframes com formatação brasileira (BRT, R$ com vírgula).

**Status:** Sprint 1 completo ✅ | **Versão:** 1.0.0 | **Tier:** FREE

---

## Features (Sprint 1)

- ✅ **RSI Alerts** - Overbought (>70) / Oversold (<30) em 1h, 4h, 1d
- ✅ **Real-time Data** - Binance WebSocket com reconnection resilience
- ✅ **Backfill Histórico** - 200 velas por timeframe ao iniciar
- ✅ **Throttling** - Max 20 alertas/hora + circuit breaker 5/min
- ✅ **Brazilian Format** - Timezone BRT, preços "$67.420,50"
- ✅ **Multi-TF Consolidation** - Mega-alert quando múltiplos timeframes críticos
- ✅ **Admin Channel** - Logs de erro separados
- ✅ **Graceful Shutdown** - SIGTERM/SIGINT handler
- ✅ **Docker Ready** - Resource limits (256MB RAM, 0.5 CPU)

---

## Quick Start

### 1. Local (Desenvolvimento)

```bash
# Clone e setup
git clone <repo-url>
cd smartmoney-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure .env
cp .env.example .env
nano .env  # Edite: BOT_TOKEN, CHANNEL_CHAT_ID, ADMIN_CHANNEL_ID

# Dry-run (sem Telegram)
PYTHONPATH=. python src/main.py --dry-run

# LIVE
PYTHONPATH=. python src/main.py
```

### 2. Docker (Produção)

```bash
docker-compose up -d
docker-compose logs -f smartmoney-free
```

---

## Arquitetura

```
src/
├── datafeeds/      # Binance WebSocket + REST API
├── indicators/     # RSI (Wilder's method), breakouts, MA
├── rules/          # Alert engine + rule definitions
├── notif/          # Telegram templates PT-BR + throttling
├── storage/        # SQLite ORM (SQLAlchemy)
├── utils/          # Logging, healthcheck, timeframes
├── config.py       # YAML config loader
├── main.py         # Orquestração principal
└── telegram_bot.py # Telegram Bot API wrapper

configs/
└── free.yaml       # Config tier FREE (RSI only)

docs/
├── CLAUDE.md       # Guia completo para Claude Code
├── OPERATIONS.md   # Comandos operacionais detalhados
└── SPRINT1_COMPLETE.md  # Testes e validação Sprint 1
```

---

## Config (configs/free.yaml)

```yaml
bot:
  tier: "free"
  version: "1.0.0"

symbols:
  - name: "BTCUSDT"
    timeframes: ["1h", "4h", "1d", "1w"]

indicators:
  rsi:
    period: 14
    overbought: 70
    oversold: 30
    timeframes: ["1h", "4h", "1d"]

alerts:
  timezone: "America/Sao_Paulo"
  throttling:
    max_alerts_per_hour: 20
  circuit_breaker:
    max_alerts_per_minute: 5
```

---

## Environment (.env)

```env
BOT_TOKEN=<botfather_token>
CHANNEL_CHAT_ID=<telegram_channel_id>
ADMIN_CHANNEL_ID=<admin_channel_id>
CONFIG_FILE=./configs/free.yaml
DB_URL=sqlite:///./data.db
LOG_LEVEL=INFO
```

**CRÍTICO:** `.env` com secrets reais NUNCA deve ser commitado.

---

## Comandos Principais

```bash
# Dry-run (teste sem Telegram)
PYTHONPATH=. python src/main.py --dry-run

# LIVE mode
PYTHONPATH=. python src/main.py

# LIVE em background
nohup PYTHONPATH=. python src/main.py > logs/bot.log 2>&1 & echo $! > bot.pid

# Parar (graceful)
kill -SIGTERM $(cat bot.pid)

# Ver logs
tail -f logs/bot.log

# Docker
docker-compose up -d
docker-compose logs -f smartmoney-free
docker-compose down
```

---

## Tech Stack

| Componente | Tecnologia | Versão |
|------------|-----------|--------|
| Linguagem | Python | 3.13 |
| Bot API | python-telegram-bot | 21.6 |
| Data Analysis | pandas | ≥2.2.3 |
| Database | SQLite + SQLAlchemy | 2.0.32 |
| WebSocket | websockets | 12.0 |
| Logging | loguru | 0.7.2 |
| Config | PyYAML | 6.0.1 |
| Timezone | pytz | 2024.1 |

---

## Roadmap

### Sprint 1 ✅ (Completo)
- RSI alerts (1h, 4h, 1d)
- Binance integration
- Telegram notifications PT-BR
- Throttling & circuit breaker
- Docker setup

### Sprint 2 (Próximo)
- Breakout alerts (1d, 1w)
- Database cleanup cronjob (90 dias)
- Advanced throttling (per-condition)
- Monitoring & health endpoint

### Sprint 3 (Premium Tier)
- Multi-symbol support
- BTC Dominance alerts
- Custom admin commands
- Premium config (`configs/premium.yaml`)

---

## Regras de Negócio

### RSI Alerts

- **Método:** Wilder's smoothing (período 14)
- **Trigger:** Somente quando vela **fecha** (`is_closed=True`)
- **Thresholds:**
  - Overbought: RSI > 70
  - Oversold: RSI < 30
- **Timeframes monitorados:** 1h, 4h, 1d

### Throttling

- **Global:** Máximo 20 alertas/hora
- **Circuit breaker:** 5 alertas/minuto → ativa consolidação multi-TF
- **Consolidação:** Se múltiplos timeframes críticos simultaneamente, envia 1 mega-alert

### Formatação

- **Timezone:** America/Sao_Paulo (BRT, UTC-3)
- **Preços:** `$67.420,50` (ponto = milhar, vírgula = decimal)
- **Datas:** `11/11/2025 16:30 BRT`
- **Linguagem:** Português brasileiro

---

## Monitoramento

### Logs

```bash
# Ver últimas 50 linhas
tail -50 logs/bot.log

# Seguir em tempo real
tail -f logs/bot.log

# Filtrar por nível
grep "ERROR" logs/bot.log
grep "WARNING" logs/bot.log

# Ver alertas enviados
grep "Alert sent" logs/bot.log

# Ver throttling ativo
grep "Throttled" logs/bot.log
```

### Database

```bash
# Total de velas
sqlite3 data.db "SELECT COUNT(*) FROM candles;"

# Por timeframe
sqlite3 data.db "SELECT symbol, interval, COUNT(*) FROM candles GROUP BY symbol, interval;"

# Últimas 10 velas
sqlite3 data.db "SELECT * FROM candles ORDER BY close_time DESC LIMIT 10;"
```

### Status do Bot

```bash
# Verificar se está rodando
ps aux | grep "python src/main.py"

# Ver recursos
top -p $(pgrep -f "python src/main.py")

# Docker
docker stats smartmoney-free
```

---

## Troubleshooting

### Bot não envia alertas

1. RSI está em zona crítica? (>70 ou <30)
2. Throttling ativo? `grep "Throttled" logs/bot.log`
3. Vela fechou? Logs mostram `is_closed: True`?

### WebSocket desconecta

1. Firewall bloqueando? `ping stream.binance.com`
2. Logs mostram reconexões? `grep "WebSocket" logs/bot.log`
3. Aumentar watchdog timeout (src/datafeeds/binance_ws.py)

### Database vazio

```bash
# Recriar DB com backfill
rm data.db
PYTHONPATH=. python src/main.py
grep "Backfill" logs/bot.log  # Verificar sucesso
```

### Encoding UTF-8

```bash
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
```

---

## Testing

### Checklist Pré-Deploy

```bash
# 1. Dry-run
PYTHONPATH=. python src/main.py --dry-run
# ✓ Backfill OK (800 candles)
# ✓ WebSocket conectado
# ✓ RSI calculado

# 2. LIVE em canal teste
CHANNEL_CHAT_ID=<seu_chat> PYTHONPATH=. python src/main.py
# ✓ Startup message recebida

# 3. Verificar database
sqlite3 data.db "SELECT COUNT(*) FROM candles;"
# ✓ Deve ter 800 (200 x 4 timeframes)

# 4. Telegram API
curl https://api.telegram.org/bot$BOT_TOKEN/getMe
# ✓ Retorna JSON com bot info

# 5. Binance API
curl https://api.binance.com/api/v3/ping
# ✓ Retorna {}
```

---

## Documentação Completa

- **[docs/CLAUDE.md](docs/CLAUDE.md)** - Guia completo para Claude Code
- **[docs/OPERATIONS.md](docs/OPERATIONS.md)** - Comandos operacionais detalhados
- **[docs/SPRINT1_COMPLETE.md](docs/SPRINT1_COMPLETE.md)** - Testes Sprint 1

---

## Security

- ❌ NUNCA commitar `.env` com secrets
- ❌ NUNCA expor API keys em logs
- ❌ NUNCA hardcodar tokens no código
- ✅ Usar `.env.example` como template
- ✅ Rotacionar tokens periodicamente
- ✅ Resource limits no Docker (256MB RAM)

---

## License

Privado - SmartMoney Brasil © 2025

---

## Support

Issues: [GitHub Issues](../../issues)
Docs: `docs/OPERATIONS.md`
