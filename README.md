# SmartMoney Bot

Telegram alert bot para trading de criptomoedas (**multi-symbol**: BTCUSDT, PAXGUSDT, etc). Alertas RSI (Wilder's, período 14) + breakouts + **divergência RSI** (pivots bullish/bearish com thresholds configuráveis) + resumo diário Fear & Greed em múltiplos timeframes com formatação brasileira (BRT, números em padrão brasileiro).

**Status:** v2.4.0 - Multi-symbol + Divergence thresholds ✅ | Tier: FREE

---

## ⚡ Quick Start

### Local (Desenvolvimento)
```bash
git clone <repo-url> && cd smartmoney-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env  # BOT_TOKEN, CHANNEL_CHAT_ID, ADMIN_CHANNEL_ID, COINMARKETCAP_API_KEY
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
| **1** ✅ | RSI Alerts | Período 14, >70 (🔴) e <30 (🟢) em 1h, 4h, 1d, 1w, 1M - real-time |
| **1** ✅ | Breakout Alerts | Rompimento alto+0.15% (🚀) / baixo-0.15% (📉) em 1h, 4h, 1d, 1w, 1M - real-time |
| **1** ✅ | Real-time Data | Binance WebSocket com auto-reconnect (exponential backoff, watchdog 90s) |
| **1** ✅ | Backfill | 200 candles/timeframe ao iniciar via REST API |
| **1** ✅ | Throttling | Max 20 alertas/hora, circuit breaker 5/min → consolidação |
| **1** ✅ | Multi-TF | Mega-alert (🚨) quando 2+ TFs críticos simultaneamente |
| **1** ✅ | Admin Channel | Logs de erro separados + stack traces |
| **1** ✅ | Docker Ready | Resource limits (256MB RAM, 0.5 CPU), non-root user |
| **2** ✅ | RSI Extremo | Níveis adicionais ≥77 (🔴🔴) / ≤23 (🟢🟢) - configuráveis |
| **2** ✅ | Anti-Spam | Recovery zones (40-60) previnem alerts repetitivos na mesma condição |
| **2** ✅ | DB Cleanup | APScheduler cronjob (daily 3AM UTC, 90-day retention, min 200 candles/TF) |
| **2** ✅ | Healthcheck | HTTP endpoints `/health` e `/status` porta 8080 |
| **2** ✅ | Deploy Auto | Script completo (`scripts/deploy.sh`) com UFW + Fail2Ban + systemd sandbox |
| **2** ✅ | Consolidação | 2+ alertas em janela 6s → 1 mega-alerta consolidado (🚨 sirenes) |
| **3** ✅ | **Daily Summary** | **Fear & Greed Index (21:05 BRT) + RSI 1D/1W/1M ALTA/BAIXA + variação candle anterior** |
| **3** ✅ | **Fear & Greed API** | **CoinMarketCap API v3 (`value`/`value_classification`) + exponential backoff (2s-4s-8s)** |
| **4** ✅ | **RSI Divergence** | **3-candle pivots (bullish=lowest, bearish=highest) + RSI confirmation (price↔RSI diverge) + 2-pivot alert** |
| **4** ✅ | **Divergence Config** | **Timeframes, lookback (40 candles), thresholds configuráveis (bullish <40, bearish >60)** |
| **5** ✅ | **Multi-symbol** | **BTCUSDT, PAXGUSDT, etc - adicionar símbolos em `configs/free.yaml`** |
| **5** ✅ | **Daily Summary Multi** | **Resumo consolidado para todos os símbolos trackeados** |
| **6** 🔜 | BTC Dominance | Alertas quando BTC.D cruza níveis chave |
| **6** 🔜 | Custom Alerts | Admin pode enviar mensagens customizadas via Telegram |

---

## 📋 Setup & Configuração

### Environment Variables (`.env`)

| Var | Exemplo | Obrigatório | Descrição |
|-----|---------|-------------|-----------|
| `BOT_TOKEN` | `123456:ABC...` | ✅ | Token do bot (@BotFather) |
| `CHANNEL_CHAT_ID` | `-1001234567890` | ✅ | ID do grupo (deve começar com `-100` para supergrupos) |
| `ADMIN_CHANNEL_ID` | `-1009876543210` | ✅ | ID do grupo admin (erros/warnings) |
| `COINMARKETCAP_API_KEY` | `abc-123-def...` | ✅ | API key CoinMarketCap (Fear & Greed Index) |
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
  version: "1.0.0"
  name: "SmartMoney Free Bot"

# Símbolos monitorados (adicione quantos quiser)
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
    extreme_overbought: 77      # RSI extremo sobrecomprado
    extreme_oversold: 23        # RSI extremo sobrevendido
    recovery_zone:
      lower: 40                 # Reset estado oversold
      upper: 60                 # Reset estado overbought
    timeframes: ["1h", "4h", "1d", "1w", "1M"]
    alert_on_touch: true        # Alertar durante candle (não só fechamento)

  breakout:
    enabled: true
    timeframes: ["1h", "4h", "1d", "1w", "1M"]
    margin_percent: 0.15        # 0.15% threshold
    alert_on_touch: true

  divergence:
    enabled: true
    timeframes: ["1h", "4h", "1d", "1w", "1M"]
    lookback: 40                        # Candles para buscar pivots
    debug_divergence: false             # Verbose logging
    bullish_rsi_max: 40                 # Divergência bullish: RSI < 40
    bearish_rsi_min: 60                 # Divergência bearish: RSI > 60

alerts:
  timezone: "America/Sao_Paulo"
  throttling:
    max_alerts_per_hour: 20
  circuit_breaker:
    max_alerts_per_minute: 5

  daily_summary:
    enabled: true
    send_time_brt: "21:05"              # HH:MM (BRT, 5min após candle fechar)
    send_window_minutes: 1
```

---

## ➕ Adicionar Novos Símbolos

Para monitorar novos tokens (ex: ETHUSDT, SOLUSDT):

```yaml
# configs/free.yaml
symbols:
  - name: "BTCUSDT"
    timeframes: ["1h", "4h", "1d", "1w", "1M"]
  - name: "PAXGUSDT"
    timeframes: ["1h", "4h", "1d", "1w", "1M"]
  - name: "ETHUSDT"           # Novo símbolo
    timeframes: ["1h", "4h", "1d", "1w"]  # Timeframes customizados
```

**Após adicionar:**
1. Reiniciar o bot
2. Backfill automático para o novo símbolo (200 candles/TF)
3. WebSocket inclui o novo símbolo automaticamente
4. Daily Summary incluirá dados do novo símbolo

**Nota:** O símbolo deve existir na Binance (USDT pairs).

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
tail -f logs/bot.log                                # Real-time
grep "Alert sent" logs/bot.log                      # Alertas enviados
grep "Daily summary" logs/bot.log                   # Resumo diário (task execution)
grep "Fear & Greed" logs/bot.log                    # Fear & Greed API calls/retries
grep "ERROR" logs/bot.log                           # Erros
grep "Throttled" logs/bot.log                       # Throttling ativo
grep "RSI analysis" logs/bot.log                    # Cálculos RSI
grep "BTCUSDT" logs/bot.log                         # Logs de símbolo específico
grep "PAXGUSDT" logs/bot.log                        # Logs de outro símbolo
grep "divergence" logs/bot.log                      # Detecção de divergências
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
│   └── fear_greed.py    # Fear & Greed Index (CoinMarketCap API v3: value/value_classification)
├── indicators/
│   ├── rsi.py           # RSI (Wilder's smoothing)
│   ├── breakouts.py     # Breakout detection
│   ├── divergence.py    # RSI divergence (3-candle pivots, 2-pivot confirmation)
│   └── [ma.py, sr_levels.py]  # Stubs para futuro
├── rules/
│   ├── engine.py        # Alert loop (check every 5s) + _send_daily_summary() task (21:01 BRT)
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
└── free.yaml            # Configuration (multi-symbol, thresholds, timeframes)
```

**Data Flow:**
- **Real-time Alerts:** Binance WS (multi-symbol streams) → Candles → SQLite → Alert Engine (5s loop) → Indicators (RSI, Breakout, Divergence) → Rules → Throttle → Telegram
- **Divergence:** 3-candle pivot detection → Compare with previous pivot → RSI confirmation (thresholds configuráveis) → Direct alert (🔼/🔽, no consolidation)
- **Daily Summary:** Scheduled task (21:05 BRT) → Fetch Fear & Greed API → For each symbol: Get RSI 1D/1W/1M + previous day candle → Format multi-symbol → Telegram

---

## 📈 Regras de Negócio

### RSI
- **Cálculo:** Wilder's smoothing, período 14
- **Trigger:** Real-time (não aguarda fechamento, `alert_on_touch: true`)
- **Normal:** >70 (🔴 overbought), <30 (🟢 oversold)
- **Extremo:** ≥77 (🔴🔴), ≤23 (🟢🟢) - configuráveis via YAML
- **TFs:** 1h, 4h, 1d, 1w, 1M (todos configuráveis)
- **Escalação & Bloqueio:**
  - ✅ Permite: OVERSOLD → EXTREME_OVERSOLD (escalação de severidade)
  - ✅ Permite: OVERBOUGHT → EXTREME_OVERBOUGHT (escalação de severidade)
  - ❌ Bloqueia: EXTREME → OVERSOLD/OVERBOUGHT (redução de severidade)
  - ❌ Bloqueia: EXTREME → EXTREME (mesmo nível)
  - ✅ Reset: Apenas quando RSI entra na recovery zone (40 < RSI < 60, configurável)
  - **Comportamento:** Uma vez em OVERSOLD/OVERBOUGHT, não há novo alerta até voltar à recovery zone (impede re-alertas)

### Breakouts
- **Detecção:** Real-time (não aguarda fechamento, `alert_on_touch: true`)
- **Bull:** Price > previous_high + 0.15% (🚀)
- **Bear:** Price < previous_low - 0.15% (📉)
- **TFs:** 1h, 4h, 1d, 1w, 1M (configuráveis)
- **Anti-spam:** Não reseta durante candle aberto (previne múltiplos alertas por oscilação)
  - Preço oscila dentro/fora do range → sem novo alerta
  - **Reset:** Apenas quando novo candle começa (permite novo sinal)
  - Exemplo: Rompimento 1d com preço subindo/descendo min/max = 1 alerta (não 10x)

### Divergência RSI
- **Detecção:** 3-candle pivots (candle do meio é extremo)
  - **Bullish:** Middle candle é lowest low (fundo)
  - **Bearish:** Middle candle é highest high (topo)
- **Confirmação:** Comparar com pivô anterior
  - **BULLISH:** price↓ mas RSI↑ (ambos < `bullish_rsi_max`, default 40) = compra potencial (🔼)
  - **BEARISH:** price↑ mas RSI↓ (ambos > `bearish_rsi_min`, default 60) = venda potencial (🔽)
- **TFs:** 1h, 4h, 1d, 1w, 1M (configuráveis, independentes)
- **Thresholds:** Configuráveis via YAML (`bullish_rsi_max: 40`, `bearish_rsi_min: 60`)
- **Lookback:** 40 candles para buscar pivots anteriores
- **Alerta:** Requer 2 pivots (estado persiste entre restarts)
- **Janela:** Sem consolidação (direto para Telegram, impactante)
- **Exemplo:** 1d cai para novo low mas RSI sobe (ambos <40) = divergência bullish

### Consolidação de Alertas
- **Janela:** 6 segundos (cobre 2 ciclos de check de 5s)
- **Regra:** 2+ alertas simultâneos → 1 mega-alerta consolidado com sirenes (🚨🚨🚨)
- **Exemplo:** RSI <30 (1h) + Rompimento 1d = 1 mensagem consolidada
- **Benefício:** Reduz spam, agrupa informações, mais impactante

### Throttling & Anti-spam
- **Global limit:** 20 alertas/hora (configurável)
- **Recovery zones:** RSI neutral (35-65, configurável) reseta permissão de novo alerta
- **Per-candle:** Evita alerta duplicado na mesma candle (marked immediately on collect, not on send)
- **Severity-based:** RSI allows escalation (OVERSOLD→EXTREME) but blocks reduction (EXTREME→OVERSOLD)
- **Reforço:** Candles diferentes podem alertar novamente APENAS após voltar à recovery zone (RSI) ou novo candle (Breakout)
- **Cleanup automático:** Limpa entries de alertas com TTL 1h (a cada 60s)
- **Implementação:** `last_condition` marcado em `_collect_single_alert()` (não espera envio) + `_get_rsi_severity()` para comparação

### Resumo Diário (Daily Summary)
- **Horário:** 21:05 BRT (00:05 UTC próximo dia) - 5min após candle fechar
- **Multi-symbol:** Resumo consolidado para TODOS os símbolos configurados em `free.yaml`
- **Conteúdo por símbolo:**
  - 😱 Fear & Greed Index (0-100, CoinMarketCap API v3 - `value`/`value_classification`)
  - 📊 RSI múltiplos timeframes:
    - 1D: `RSI ≥ 50 → 📈 ALTA`, `RSI < 50 → 📉 BAIXA`
    - 1W: mesmo padrão
    - 1M: mesmo padrão
  - 💰 Variação diária: `(candle_anterior.close - candle_anterior.open) / candle_anterior.open × 100%`
- **Template:** Formato limpo com cada símbolo separado, RSI em linhas individuais
- **Retry:** Exponential backoff se API falhar (2s → 4s → 8s)
- **Janela:** ±1 minuto para envio (tolerância)
- **Config:** Ativar/desativar em `free.yaml` → `alerts.daily_summary.enabled`
- **API Key:** Obrigatório `COINMARKETCAP_API_KEY` em `.env`

### Formatação
- **Timezone:** America/Sao_Paulo (BRT, UTC-3)
- **Números:** `$1.234,56` (ponto=milhar, vírgula=decimal)
- **Datas:** `11/11/2025 16:30 BRT`
- **Idioma:** Português brasileiro

---

## 🛠️ Tech Stack

| Componente | Versão | Propósito |
|------------|--------|----------|
| Python | 3.13+ | Linguagem (testado até 3.14) |
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

## 🔧 Últimas Correções (Jan 2026)

**v2.4.0 - Multi-symbol + Divergence Thresholds:**
- **Multi-symbol:** Suporte a múltiplos símbolos (BTCUSDT, PAXGUSDT, etc) via `free.yaml`
- **WebSocket:** Stream combinado para todos os símbolos configurados
- **Daily Summary Multi:** Resumo consolidado para todos os símbolos em uma mensagem
- **Divergence Thresholds:** RSI thresholds configuráveis (`bullish_rsi_max: 40`, `bearish_rsi_min: 60`)
- **Templates:** Formatação melhorada com espaçamento e clareza

**v2.3.x - RSI Alert Duplicate Prevention:**
- **Problema:** Múltiplos alertas RSI idênticos sendo enviados no mesmo candle
- **Solução #1:** Marcar `last_condition` imediatamente em `_collect_single_alert()` para bloqueio imediato de duplicatas
- **Solução #2:** Implementar lógica de severidade:
  - ✅ Permite escalação: OVERSOLD(1) → EXTREME_OVERSOLD(2)
  - ❌ Bloqueia redução: EXTREME_OVERSOLD(2) → OVERSOLD(1)
  - Reset: Apenas quando RSI volta à recovery zone (40-60)
- **Resultado:** Fluxo correto de alertas sem duplicatas, com escalação permitida

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
| **Daily Summary não aparece** | **Task desabilitado, horário passou, ou API key inválida** | **Verificar: `grep "Daily summary" logs/bot.log` + `free.yaml` → `enabled: true` + `COINMARKETCAP_API_KEY` em `.env`** |
| **Fear & Greed mostra "Indisponível"** | **API key ausente/inválida ou CoinMarketCap down** | **Verificar: `COINMARKETCAP_API_KEY` em `.env`, `grep "Fear & Greed" logs/bot.log` para retry attempts** |
| **RSI não mostra no Daily Summary** | Dados insuficientes ou candle anterior não existe | Esperar 1-2 dias para dados acumularem, verificar `grep "RSI analysis" logs/bot.log` |
| **Divergências não alertam** | Feature desabilitada, sem pivots, ou RSI fora do threshold | Verificar `free.yaml` → `divergence.enabled: true`, RSI deve estar < `bullish_rsi_max` (40) para bullish ou > `bearish_rsi_min` (60) para bearish, habilitar `debug_divergence: true` para logs |
| **Divergência com thresholds diferentes** | Valores 50 eram hardcoded, agora configuráveis | Ajustar `bullish_rsi_max` e `bearish_rsi_min` em `free.yaml` (default: 40 e 60) |
| **Divergência re-alerta** | Comportamento esperado (precisa de 2 pivots) | BULLISH/BEARISH requer comparação entre pivots, cada novo pivô pode gerar novo alerta se confirmado |
| **Novo símbolo não aparece** | Símbolo não adicionado ao YAML | Adicionar em `free.yaml` → `symbols:` com nome e timeframes, reiniciar bot |
| ModuleNotFoundError: No module named 'src' | PYTHONPATH não definido (Docker) | Adicionar `PYTHONPATH=/app` no docker-compose.yml environment |
| unable to open database file | Filesystem read-only ou sem permissões | Remover `read_only: true` do docker-compose.yml, garantir `/data` volume com permissões 755 |
| Bot não manda msg no Telegram | BOT_TOKEN inválido ou ausente em .env | Verificar: `cat .env \| grep BOT_TOKEN`, token deve vir exato do @BotFather, sem espaços |

---

## ✅ Pré-Deploy Checklist

```bash
# 1. Test dry-run
PYTHONPATH=. python src/main.py --dry-run
# Expect: Backfill OK, WebSocket connected, RSI/Breakout/Divergence calculated
# Look for: "Divergence state initialized for all timeframes"

# 2. Run all tests (including divergence)
PYTHONPATH=. pytest tests/ -v
# Expect: All tests passing (268 tests including divergence with configurable thresholds)

# 3. Database
sqlite3 data.db "SELECT COUNT(*) FROM candles;"
# Expect: 2000 (200 candles × 5 timeframes × 2 symbols)

# 4. Telegram connectivity
curl https://api.telegram.org/bot$BOT_TOKEN/getMe
# Expect: JSON com info do bot

# 5. Binance API
curl https://api.binance.com/api/v3/ping
# Expect: {} (empty JSON)

# 6. Memory usage
docker stats smartmoney-free-bot --no-stream
# Expect: <200MB steady-state

# 7. Live test (1+ hour)
PYTHONPATH=. python src/main.py
# Expect: Startup message received, no crashes, stable, divergence_state persisted

# 8. Graceful shutdown
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
