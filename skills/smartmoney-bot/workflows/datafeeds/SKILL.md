---
name: smartmoney-bot/datafeeds
description: Workflow para fontes de dados externas (Binance WS/REST, Fear & Greed, Market Caps) e Telegram API no SmartMoney Bot.
parent: smartmoney-bot
---

# Workflow: Datafeeds

## Goal
Modificar ou adicionar fontes de dados externas, WebSocket connections, backfill, ou a integração com Telegram API.

## Scope
- `src/datafeeds/binance_ws.py` — WebSocket multi-symbol streams, auto-reconnect
- `src/datafeeds/binance_rest.py` — REST backfill (200 candles/TF)
- `src/datafeeds/fear_greed.py` — Fear & Greed Index (CoinMarketCap API v3, exp backoff 2-4-8s)
- `src/datafeeds/market_caps.py` — Global market caps
- `src/telegram_bot.py` — Telegram API wrapper (send_message, send_error_to_admin, send_message_async)

## Triggers
- "WebSocket", "WS", "stream"
- "Binance", "backfill", "REST"
- "Fear & Greed", "market cap"
- "Telegram API", "enviar mensagem"
- "Reconnect", "connection drop"
- "Nova exchange/API"

## Inputs
- Especificação da fonte/mudança
- Endpoints, auth, rate limits
- Retry/backoff strategy

## Invariants
- **async/await** obrigatório (websockets, aiohttp, requests-async)
- **Auto-reconnect** no WS — bot deve sobreviver a disconnects
- **Exp backoff** em todas APIs externas (2s → 4s → 8s)
- **Error handling** específico (não bare except)
- **Logging** via loguru com contexto (symbol, timeframe, erro)
- **Sem hardcode** de endpoints/keys — via config/env
- **Multi-symbol** — WS suporta lista de configs
- **Backfill** sempre respeita `candles_per_timeframe` do config
- **Type hints** em todas funções
- **Sem `eval`/`exec`**

## Procedure

### Nova fonte de dados
1. Criar `src/datafeeds/<source>.py`
2. Implementar fetch com exp backoff (ver padrão `fear_greed.py`)
3. Logging structured (loguru)
4. Integrar no engine ou main conforme necessidade
5. Adicionar config em `configs/free.yaml` se tiver thresholds/params
6. Testes em `tests/test_websocket.py` ou novo arquivo

### Modificar WS Binance
1. Ler `binance_ws.py` — entender `listen_multi_klines()` e auto-reconnect
2. Mudança cirúrgica
3. Testar `--ws-multi` mode: `PYTHONPATH=. python src/main.py --ws-multi`
4. Dry-run completo

### Modificar backfill
1. Ler `binance_rest.py` — `backfill_all_symbols()`
2. Respeitar `backfill.candles_per_timeframe` do config
3. Testar `--backfill` mode

### Modificar Telegram API
1. Ler `telegram_bot.py` — `send_message`, `send_message_async`, `send_error_to_admin`
2. Manter 5 retries pattern
3. Dry-run não envia para Telegram

## Outputs
- Datafeed implementado/modificado
- Testes passando
- Logging structured adicionado
- Config/env atualizada se necessário

## Review gate
- [ ] `PYTHONPATH=. python src/main.py --dry-run` — WS conecta, sem erros
- [ ] `PYTHONPATH=. python src/main.py --ws-multi` — multi-TF OK (se tocou WS)
- [ ] `PYTHONPATH=. python src/main.py --backfill` — backfill OK (se tocou REST)
- [ ] `PYTHONPATH=. pytest tests/test_websocket.py -v` — testes WS passam
- [ ] `PYTHONPATH=. pytest tests/ -v` — suíte completa
- [ ] Exp backoff presente em APIs externas
- [ ] Auto-reconnect presente no WS
- [ ] Sem keys/endpoints hardcodeados
- [ ] Diff cirúrgico

## References
- `src/datafeeds/fear_greed.py` — padrão de API com exp backoff
- `src/datafeeds/binance_ws.py` — padrão WS multi-symbol + reconnect
- `src/datafeeds/binance_rest.py` — padrão backfill
- `src/telegram_bot.py` — wrapper com retries
- `.env.example` — env vars esperadas
