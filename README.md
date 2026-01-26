# SmartMoney Bot

Bot Telegram de alertas crypto com suporte a **múltiplos símbolos** (BTCUSDT, PAXGUSDT, etc).

**Alertas:** RSI | Breakouts | Divergência RSI | Resumo Diário (Fear & Greed)

**Status:** v2.5.0 | Tier: FREE

---

## Quick Start

### Local (Dev)
```bash
git clone <repo-url> && cd smartmoney-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Editar: BOT_TOKEN, CHANNEL_CHAT_ID, etc
PYTHONPATH=. python src/main.py --dry-run  # Teste
PYTHONPATH=. python src/main.py             # Produção
```

### Docker (Prod)
```bash
# Build com cache (rápido)
DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1 docker compose up -d --build

# Comandos úteis
docker compose logs -f smartmoney-free      # Logs
docker compose restart smartmoney-free      # Restart
docker compose down                         # Stop
```

---

## Features

| Feature | Descrição |
|---------|-----------|
| **RSI Alerts** | Período 14, >70 / <30 / extremos ≥77 / ≤23 em 1h, 4h, 1d, 1w, 1M |
| **Breakouts** | Rompimento máx/mín +0.15% em 1h, 4h, 1d, 1w, 1M |
| **Divergência RSI** | Pivots bullish/bearish com thresholds configuráveis |
| **Daily Summary** | Fear & Greed + RSI + variação (21:05 BRT) |
| **Multi-symbol** | Múltiplos tokens via YAML (BTCUSDT, PAXGUSDT, etc) |
| **Real-time** | Binance WebSocket com auto-reconnect |
| **Anti-spam** | Throttling 20/hora, recovery zones, circuit breaker |
| **Consolidação** | 2+ alertas em 6s → mega-alert (🚨) |

---

## Configuração

### .env (Secrets)
```bash
BOT_TOKEN=123456:ABC...           # @BotFather
CHANNEL_CHAT_ID=-1001234567890    # Grupo principal
ADMIN_CHANNEL_ID=-1009876543210   # Grupo admin (erros)
COINMARKETCAP_API_KEY=abc-123...  # Fear & Greed API
DB_URL=sqlite:///./data.db
CONFIG_FILE=./configs/free.yaml
```

### configs/free.yaml (Parâmetros)
```yaml
symbols:
  - name: "BTCUSDT"
    timeframes: ["1h", "4h", "1d", "1w", "1M"]
  - name: "PAXGUSDT"
    timeframes: ["1h", "4h", "1d", "1w", "1M"]

indicators:
  rsi:
    enabled: true
    period: 14
    overbought: 70
    oversold: 30
    extreme_overbought: 77
    extreme_oversold: 23
    recovery_zone: { lower: 40, upper: 60 }
    timeframes: ["1h", "4h", "1d", "1w", "1M"]

  breakout:
    enabled: true
    timeframes: ["1d", "1w", "1M"]
    margin_percent: 0.15

  divergence:
    enabled: true
    timeframes: ["1h", "4h", "1d", "1w", "1M"]
    lookback: 40              # Janela de candles (por timeframe)
    bullish_rsi_max: 40       # RSI < 40 para bullish
    bearish_rsi_min: 60       # RSI > 60 para bearish

alerts:
  timezone: "America/Sao_Paulo"
  daily_summary:
    enabled: true
    send_time_brt: "21:05"
```

### Adicionar Novos Símbolos
```yaml
symbols:
  - name: "ETHUSDT"
    timeframes: ["1h", "4h", "1d"]
```
Reiniciar o bot após adicionar.

---

## Regras de Negócio

### RSI
- **Trigger:** Real-time (`alert_on_touch: true`)
- **Normal:** >70 (🔴), <30 (🟢)
- **Extremo:** ≥77 (🔴🔴), ≤23 (🟢🟢)
- **Recovery:** Reset apenas quando RSI entra em 40-60

### Breakouts
- **Bull:** Preço > máx anterior + 0.15%
- **Bear:** Preço < mín anterior - 0.15%
- **Reset:** Novo candle

### Divergência RSI
- **Pivot:** 3 candles (meio = extremo)
- **Bullish:** Preço↓ + RSI↑ (ambos < 40) = 🔼
- **Bearish:** Preço↑ + RSI↓ (ambos > 60) = 🔽
- **Lookback:** Janela de 40 candles por timeframe

### Daily Summary (21:05 BRT)
- Fear & Greed Index
- RSI 1D/1W/1M com tendência (📈/📉)
- Variação do candle anterior

---

## CLI

| Comando | Descrição |
|---------|-----------|
| `python src/main.py` | Produção |
| `python src/main.py --dry-run` | Teste (sem Telegram) |
| `python src/main.py --ping` | Testar Telegram |
| `python src/main.py --init-db` | Criar tabelas |

**Nota:** Sempre usar `PYTHONPATH=.` antes dos comandos.

---

## Monitoramento

### Logs
```bash
tail -f logs/bot.log                    # Real-time
grep "ERROR" logs/bot.log               # Erros
grep "divergence" logs/bot.log          # Divergências
grep "Daily summary" logs/bot.log       # Resumo diário
```

### Healthcheck
```bash
curl http://localhost:8080/health
curl http://localhost:8080/status
```

### Database
```bash
sqlite3 data.db "SELECT symbol, interval, COUNT(*) FROM candles GROUP BY symbol, interval;"
```

---

## Arquitetura

```
src/
├── main.py              # Orquestração
├── config.py            # YAML loader
├── telegram_bot.py      # Telegram API
├── datafeeds/
│   ├── binance_ws.py    # WebSocket (multi-symbol)
│   ├── binance_rest.py  # Backfill
│   └── fear_greed.py    # CoinMarketCap API
├── indicators/
│   ├── rsi.py           # RSI (Wilder's)
│   ├── breakouts.py     # Breakouts
│   └── divergence.py    # Divergência RSI
├── rules/engine.py      # Alert engine (5s loop)
├── notif/
│   ├── templates.py     # Templates PT-BR
│   └── throttle.py      # Rate limiting
└── storage/
    ├── models.py        # ORM (Candle)
    └── repo.py          # Queries
```

**Data Flow:**
```
Binance WS → Candles (SQLite) → Indicators → Rules → Throttle → Telegram
```

---

## Troubleshooting

| Sintoma | Solução |
|---------|---------|
| Sem alertas | `grep "RSI" logs/bot.log` - verificar valores |
| Alertas param | Throttling ativo - aumentar limit no YAML |
| WebSocket desconecta | `ping stream.binance.com` |
| Divergência não alerta | Verificar `bullish_rsi_max`/`bearish_rsi_min` e `debug_divergence: true` |
| Daily Summary ausente | Verificar `COINMARKETCAP_API_KEY` |
| Novo símbolo não aparece | Adicionar no YAML e reiniciar |
| ModuleNotFoundError | Usar `PYTHONPATH=.` |

---

## Testes

```bash
PYTHONPATH=. pytest tests/ -v                    # Todos
PYTHONPATH=. pytest --cov=src tests/             # Com coverage
PYTHONPATH=. pytest tests/test_divergence.py -v  # Específico
```

---

## Tech Stack

| Componente | Versão |
|------------|--------|
| Python | 3.13+ |
| python-telegram-bot | 21.6 |
| SQLAlchemy | 2.0.32 |
| websockets | 12.0 |
| loguru | 0.7.2 |
| APScheduler | 3.10.4 |

---

## Changelog

### v2.5.0
- Lookback de divergência por janela de candles (não pivôs)
- Docker multi-stage build com cache BuildKit

### v2.4.0
- Multi-symbol (BTCUSDT, PAXGUSDT, etc)
- Divergence thresholds configuráveis
- Templates melhorados

---

## License

Privado - SmartMoney Brasil © 2026
