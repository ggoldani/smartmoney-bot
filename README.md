# SmartMoney Bot

Telegram alert bot para trading de criptomoedas (BTCUSDT). Alertas RSI (Wilder's, período 14) + breakouts + resumo diário Fear & Greed em múltiplos timeframes com formatação brasileira (BRT, números em padrão brasileiro).

**Status:** v2.2.0 - Sprint 3 completo ✅ (Daily Summary implementado) | Tier: FREE

---

## ⚡ Quick Start

### Local (Desenvolvimento)
```bash
git clone <repo-url> && cd smartmoney-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env  # BOT_TOKEN, CHANNEL_CHAT_ID, ADMIN_CHANNEL_ID
PYTHONPATH=. python src/main.py --dry-run  # Teste sem Telegram
PYTHONPATH=. python src/main.py             # LIVE
```

### Produção (Any VPS/Linux)
```bash
# Option 1: Automated deployment script (recomendado)
sudo bash scripts/deploy.sh  # Detecta SO, instala dependências + security + bot
# Option 2: Manual Docker
docker-compose up -d
```

---

## ✨ Features

| Sprint | Feature | Detalhes |
|--------|---------|----------|
| **1** ✅ | RSI Alerts | Período 14, >70 (🔴) e <30 (🟢) em 1h, 4h, 1d - real-time |
| **1** ✅ | Breakout Alerts | Rompimento alto+0.1% (🚀) / baixo-0.1% (📉) em 1d, 1w - real-time |
| **1** ✅ | Real-time Data | Binance WebSocket com auto-reconnect (exponential backoff, watchdog 90s) |
| **1** ✅ | Backfill | 200 candles/timeframe ao iniciar via REST API |
| **1** ✅ | Throttling | Max 20 alertas/hora, circuit breaker 5/min → consolidação |
| **1** ✅ | Multi-TF | Mega-alert (🚨) quando 2+ TFs críticos simultaneamente |
| **1** ✅ | Admin Channel | Logs de erro separados + stack traces |
| **1** ✅ | Docker Ready | Resource limits (256MB RAM, 0.5 CPU), non-root user |
| **2** ✅ | RSI Extremo | Níveis adicionais >75 (🔴🔴) / <25 (🟢🟢) |
| **2** ✅ | Anti-Spam | Recovery zones previnem alerts repetitivos na mesma condição |
| **2** ✅ | DB Cleanup | APScheduler cronjob (daily 3AM UTC, 90-day retention, min 200 candles/TF) |
| **2** ✅ | Healthcheck | HTTP endpoints `/health` e `/status` porta 8080 |
| **2** ✅ | Deploy Auto | Script completo (`scripts/deploy.sh`) com UFW + Fail2Ban + systemd sandbox |
| **2** ✅ | Consolidação | 2+ alertas em janela 6s → 1 mega-alerta consolidado (🚨 sirenes) |
| **3** ✅ | **Daily Summary** | **Fear & Greed Index (21:00 BRT) + RSI 1D + variação diária** |
| **3** ✅ | **Fear & Greed API** | **CoinMarketCap API com exponential backoff (2s-4s-8s)** |
| **4** 🔜 | Multi-symbol | ETHUSDT, BNBUSDT, etc (configs/premium.yaml) |
| **4** 🔜 | BTC Dominance | Alertas quando BTC.D cruza níveis chave |
| **4** 🔜 | Custom Alerts | Admin pode enviar mensagens customizadas via Telegram |

---

## 📋 Setup & Configuração

### Environment Variables (`.env`)

| Var | Exemplo | Obrigatório | Descrição |
|-----|---------|-------------|-----------|
| `BOT_TOKEN` | `123456:ABC...` | ✅ | Token do bot (@BotFather) |
| `CHANNEL_CHAT_ID` | `-1001234567890` | ✅ | ID do grupo (deve começar com `-100` para supergrupos) |
| `ADMIN_CHANNEL_ID` | `-1009876543210` | ✅ | ID do grupo admin (erros/warnings) |
| `CONFIG_FILE` | `./configs/free.yaml` | ✅ | Path da config (free ou premium) |
| `DB_URL` | `sqlite:///./data.db` | ✅ | Database URL |
| `LOG_LEVEL` | `INFO` ou `DEBUG` | ❌ | Default: INFO (DEBUG muito verbose) |

**CRÍTICO:**
- Não commitar `.env` com secrets reais. Use `.env.example` como template.
- **DB_URL é obrigatório** - Sem ele, o bot não consegue criar/abrir o banco de dados
- Em Docker, o .env precisa estar no diretório raiz (`~/smartmoney-bot/.env`)

### Bot Config (YAML) - `configs/free.yaml`

```yaml
bot:
  tier: "free"
  version: "2.1.0"

symbols:
  - name: "BTCUSDT"
    timeframes: ["1h", "4h", "1d", "1w"]

indicators:
  rsi:
    period: 14
    overbought: 70          # Ajustar aqui
    oversold: 30            # Ajustar aqui
    timeframes: ["1h", "4h", "1d"]

  breakout:
    timeframes: ["1d", "1w"]
    margin_percent: 0.1     # 0.1% threshold

alerts:
  timezone: "America/Sao_Paulo"
  throttling:
    max_alerts_per_hour: 20
  circuit_breaker:
    max_alerts_per_minute: 5

  # Daily Summary: Resumo Fear & Greed Index @ 21:00 BRT (00:00 UTC)
  daily_summary:
    enabled: true                    # Set false para desabilitar
    send_time_brt: "21:00"          # HH:MM (BRT timezone)
    send_window_minutes: 5          # Tolerância em minutos
```

---

## 🚀 Deployment

### Automated (Recomendado)
```bash
sudo bash scripts/deploy.sh
# Automático: detecta SO (Ubuntu, Debian, CentOS, AlmaLinux, etc)
# 1. Atualiza sistema + instala dependências
# 2. Configura security (UFW/firewalld + Fail2Ban + sandboxing)
# 3. Prompts: método (Docker ou systemd)
# 4. Deploy bot + healthcheck + log rotation
```

### Docker
```bash
docker compose up -d                              # Start
docker compose logs -f smartmoney-free            # Logs
docker compose restart smartmoney-free            # Restart
docker compose down                               # Stop
docker stats smartmoney-free-bot                  # Monitor
```

### Native systemd
```bash
systemctl start smartmoney-bot                    # Start
journalctl -u smartmoney-bot -f                   # Logs
systemctl restart smartmoney-bot                  # Restart
systemctl stop smartmoney-bot                     # Stop
```

### Healthcheck
```bash
curl http://localhost:8080/health    # Status simples
curl http://localhost:8080/status    # JSON com métricas
```

---

## 🎮 CLI Modes

| Modo | Comando | Use Case |
|------|---------|----------|
| **LIVE** | `PYTHONPATH=. python src/main.py` | Produção - envia alertas reais |
| **Dry-run** | `PYTHONPATH=. python src/main.py --dry-run` | Teste sem Telegram (logs only) |
| **Init DB** | `PYTHONPATH=. python src/main.py --init-db` | Criar tabelas (automático na 1ª execução) |
| **Ping** | `PYTHONPATH=. python src/main.py --ping` | Teste conectividade Telegram |
| **Backfill** | `PYTHONPATH=. python src/main.py --backfill` | Buscar dados históricos apenas |

### Background Mode
```bash
nohup PYTHONPATH=. python src/main.py > logs/bot.log 2>&1 & echo $! > bot.pid
kill -SIGTERM $(cat bot.pid)  # Graceful shutdown
```

---

## 📊 Monitoramento

### Logs
```bash
tail -f logs/bot.log                        # Real-time
grep "Alert sent" logs/bot.log              # Alertas enviados
grep "Daily summary" logs/bot.log           # Resumo diário
grep "Fear & Greed" logs/bot.log            # Fear & Greed API
grep "ERROR" logs/bot.log                   # Erros
grep "Throttled" logs/bot.log               # Throttling ativo
grep "RSI analysis" logs/bot.log            # Cálculos RSI
```

### Database
```bash
sqlite3 data.db "SELECT COUNT(*) FROM candles;"  # Total
sqlite3 data.db "SELECT symbol, interval, COUNT(*) FROM candles GROUP BY symbol, interval;"  # Por TF
sqlite3 data.db "PRAGMA integrity_check;"  # Validar integridade
```

### Running Process
```bash
ps aux | grep "python src/main.py"
docker stats smartmoney-free-bot  # Docker: CPU, RAM, network
```

---

## 🔧 Arquitetura

```
src/
├── main.py              # Orquestração: startup → backfill → loop → shutdown
├── config.py            # YAML loader + env substitution
├── telegram_bot.py      # Wrapper Telegram API com retry logic
├── datafeeds/
│   ├── binance_ws.py    # WebSocket client (auto-reconnect)
│   ├── binance_rest.py  # Backfill histórico (200 candles/TF)
│   └── fear_greed.py    # Fear & Greed Index (CoinMarketCap API)
├── indicators/
│   ├── rsi.py           # RSI (Wilder's smoothing)
│   ├── breakouts.py     # Breakout detection
│   └── [ma.py, sr_levels.py]  # Stubs para futuro
├── rules/
│   ├── engine.py        # Alert loop (check every 5s)
│   └── rule_defs.py     # Rule definitions + recovery zones
├── notif/
│   ├── formatter.py     # Brazilian formatting (BRT, números)
│   ├── templates.py     # Portuguese message templates
│   └── throttle.py      # Rate limiting + circuit breaker
├── storage/
│   ├── db.py            # SQLAlchemy engine + session
│   ├── models.py        # ORM models (Candle, MarketCaps)
│   ├── repo.py          # Repository pattern (indexed queries)
│   ├── init_db.py       # Database initialization
│   └── cleanup.py       # APScheduler cleanup task
└── utils/
    ├── logging.py       # loguru setup (async, rotation)
    ├── healthcheck.py   # HTTP /health, /status
    └── timeframes.py    # TF utilities

configs/
└── free.yaml            # Configuration (also: premium.yaml future)
```

**Data Flow:** Binance WS → Candles → SQLite → Alert Engine (5s loop) → Indicators → Rules → Throttle → Telegram

---

## 📈 Regras de Negócio

### RSI
- **Cálculo:** Wilder's smoothing, período 14
- **Trigger:** Real-time (não aguarda fechamento)
- **Normal:** >70 (🔴 overbought), <30 (🟢 oversold)
- **Extremo:** >75 (🔴🔴), <25 (🟢🟢)
- **TFs:** 1h, 4h, 1d

### Breakouts
- **Detecção:** Real-time (não aguarda fechamento)
- **Bull:** Price > previous_high + 0.1% (🚀)
- **Bear:** Price < previous_low - 0.1% (📉)
- **TFs:** 1d, 1w
- **Anti-spam:** Não reseta durante candle aberto (previne múltiplos alertas por oscilação)
  - Preço oscila dentro/fora do range → sem novo alerta
  - **Reset:** Apenas quando novo candle começa (permite novo sinal)
  - Exemplo: Rompimento 1d com preço subindo/descendo min/max = 1 alerta (não 10x)

### Consolidação de Alertas
- **Janela:** 6 segundos (cobre 2 ciclos de check de 5s)
- **Regra:** 2+ alertas simultâneos → 1 mega-alerta consolidado com sirenes (🚨🚨🚨)
- **Exemplo:** RSI <30 (1h) + Rompimento 1d = 1 mensagem consolidada
- **Benefício:** Reduz spam, agrupa informações, mais impactante

### Throttling & Anti-spam
- **Global limit:** 20 alertas/hora (configurável)
- **Recovery zones:** RSI neutral (35-65, configurável) reseta permissão de novo alerta
- **Per-candle:** Evita alerta duplicado na mesma candle
- **Reforço:** Candles diferentes (1h apart) podem alertar novamente se condição persiste
- **Cleanup automático:** Limpa entries de alertas com TTL 1h (a cada 60s)

### Resumo Diário (Daily Summary)
- **Horário:** 21:00 BRT (00:00 UTC próximo dia)
- **Conteúdo:**
  - 😱 Fear & Greed Index (0-100, CoinMarketCap API)
  - 📊 RSI 1D com tendência (📈📉➡️)
  - 💰 Variação diária em %
- **Retry:** Exponential backoff se API falhar (2s → 4s → 8s)
- **Janela:** ±5 minutos para envio (tolerância)
- **Config:** Ativar/desativar em `free.yaml` → `alerts.daily_summary.enabled`

### Formatação
- **Timezone:** America/Sao_Paulo (BRT, UTC-3)
- **Números:** `$1.234,56` (ponto=milhar, vírgula=decimal)
- **Datas:** `11/11/2025 16:30 BRT`
- **Idioma:** Português brasileiro

---

## 🛠️ Tech Stack

| Componente | Versão | Propósito |
|------------|--------|----------|
| Python | 3.13 | Linguagem |
| python-telegram-bot | 21.6 | Telegram API |
| pandas | ≥2.2.3 | Data analysis |
| SQLAlchemy | 2.0.32 | ORM |
| websockets | 12.0 | Binance WebSocket |
| loguru | 0.7.2 | Structured logging |
| APScheduler | 3.10.4 | Scheduled tasks |
| PyYAML | 6.0.1 | Config files |
| pytz | 2024.1 | Timezone handling |
| aiohttp | 3.10.0 | HTTP async client |

---

## 🐛 Troubleshooting

| Sintoma | Causa | Solução |
|---------|-------|---------|
| Sem alertas | RSI não em zona crítica | `grep "RSI analysis" logs/bot.log` para verificar valores |
| Alertas param | Throttling ativo (20/hora) | `grep "Throttled" logs/bot.log`, aumentar limit em YAML |
| WebSocket desconecta | Network ou Binance issue | `ping stream.binance.com`, verificar `grep "WebSocket" logs/bot.log` |
| DB vazio | Backfill falhou | `rm data.db`, reiniciar (auto-backfill), verificar `grep "Backfill" logs/bot.log` |
| Alto uso RAM | Muitas candles em memória | Check: `docker stats`, deve estar <256MB |
| Telegram sem mensagens | Bot não está no grupo ou ID errado | Verificar membership, obter IDs: `curl "https://api.telegram.org/bot$BOT_TOKEN/getUpdates"` |
| Startup lento | Backfill fetching 800 candles | Normal: 60-120s é esperado |
| ImportError | Dependencies faltando ou sem PYTHONPATH | `pip install -r requirements.txt`, usar `PYTHONPATH=. python ...` |
| Bot crashes | Exceção no código | Verificar admin Telegram channel (❌ errors), `grep "ERROR" logs/bot.log` |
| Healthcheck fail | Port 8080 não responde | `curl http://localhost:8080/health`, restart bot |
| Daily Summary não aparece | Task desabilitado ou horário passou | Verificar: `grep "Daily summary" logs/bot.log`, check `free.yaml` → `alerts.daily_summary.enabled` |
| Fear & Greed API falha | Network ou CoinMarketCap down | Normal: usa fallback "Indisponível", `grep "Fear & Greed" logs/bot.log` para logs de retry |
| ModuleNotFoundError: No module named 'src' | PYTHONPATH não definido (Docker) | Adicionar `PYTHONPATH=/app` no docker-compose.yml environment |
| unable to open database file | Filesystem read-only ou sem permissões | Remover `read_only: true` do docker-compose.yml, garantir `/data` volume com permissões 755 |
| Bot não manda msg no Telegram | BOT_TOKEN inválido ou ausente em .env | Verificar: `cat .env \| grep BOT_TOKEN`, token deve vir exato do @BotFather, sem espaços |

---

## ✅ Pré-Deploy Checklist

```bash
# 1. Test dry-run
PYTHONPATH=. python src/main.py --dry-run
# Expect: Backfill OK, WebSocket connected, RSI calculated

# 2. Database
sqlite3 data.db "SELECT COUNT(*) FROM candles;"
# Expect: 800 (200 candles × 4 timeframes)

# 3. Telegram connectivity
curl https://api.telegram.org/bot$BOT_TOKEN/getMe
# Expect: JSON com info do bot

# 4. Binance API
curl https://api.binance.com/api/v3/ping
# Expect: {} (empty JSON)

# 5. Memory usage
docker stats smartmoney-free-bot --no-stream
# Expect: <200MB steady-state

# 6. Live test (1+ hour)
PYTHONPATH=. python src/main.py
# Expect: Startup message received, no crashes, stable

# 7. Graceful shutdown
kill -SIGTERM <pid>
# Expect: Shutdown message sent, clean exit
```

---

## 🔐 Security

- ✅ `.env` em `.gitignore` - NUNCA commitar secrets
- ✅ Use `.env.example` como template
- ✅ Rotacionar tokens periodicamente
- ✅ Docker: non-root user, resource limits, read-only FS
- ✅ systemd: AppArmor sandbox, PrivateTmp
- ✅ SQLAlchemy ORM only - NO raw SQL
- ✅ Async logging - logs nunca bloqueiam main loop

---

## 📄 License

Privado - SmartMoney Brasil © 2025

---

## 🔗 Support

- Issues: GitHub Issues
- Logs: `logs/bot.log`
- Database: `data.db` (SQLite)
- Configuration: `configs/free.yaml`
