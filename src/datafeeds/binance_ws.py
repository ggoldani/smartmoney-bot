# src/datafeeds/binance_ws.py
import asyncio
import json
import time
import urllib.parse
from datetime import datetime, timezone
import random
from typing import Dict
from loguru import logger
from websockets.exceptions import (
    ConnectionClosed, ConnectionClosedError, ConnectionClosedOK,
    InvalidStatus, WebSocketException
)
from src.storage.repo import save_candle_event

import websockets

# Throttle de database writes (evita UPDATE a cada tick)
# key: "BTCUSDT_1h_1762891200000", value: timestamp
_last_save_time: Dict[str, float] = {}
SAVE_THROTTLE_SECONDS = 10  # Salvar velas abertas a cada 10 segundos max

def _should_save_candle(event: dict) -> bool:
    """
    Decide se deve salvar vela no DB baseado em throttle.

    Regras:
    1. Se vela fechou (is_closed=True): SEMPRE salva
    2. Se vela aberta: salva apenas se passou SAVE_THROTTLE_SECONDS desde último save

    Isso reduz writes ao DB de ~100/min para ~6/min por timeframe (velas abertas).
    """
    if event.get("is_closed"):
        # Cleanup throttle entry for this candle (no longer needed after close)
        key = f"{event['symbol']}_{event['interval']}_{event['open_time']}"
        _last_save_time.pop(key, None)
        return True  # Velas fechadas sempre salvam

    # Vela aberta: verificar throttle
    key = f"{event['symbol']}_{event['interval']}_{event['open_time']}"
    now = time.time()
    last_save = _last_save_time.get(key, 0)

    if now - last_save >= SAVE_THROTTLE_SECONDS:
        _last_save_time[key] = now
        return True

    return False

def normalize_kline(data: dict) -> dict:
    """
    Converte o kline da Binance (chave 'k') no formato padrão do projeto.
    Espera um dict com a chave 'k' (data['k']).
    Extrai o símbolo do payload (k["s"]).
    """
    k = data["k"]
    return {
        "symbol": k["s"].upper(),                  # Extrai do payload
        "interval": k["i"],                        # "4h" | "1d" | "1w" | "1M"
        "open_time": int(k["t"]),                  # ms UTC
        "close_time": int(k["T"]),                 # ms UTC
        "open": float(k["o"]),
        "high": float(k["h"]),
        "low": float(k["l"]),
        "close": float(k["c"]),
        "volume": float(k["v"]),
        "is_closed": bool(k["x"]),
    }

BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws"


def _kline_stream(symbol: str, interval: str) -> str:
    return f"{symbol.lower()}@kline_{interval}"

async def listen_kline(symbol: str = "BTCUSDT", interval: str = "1m") -> None:
    """
    Conecta no WS de klines da Binance e emite eventos normalizados.
    Salva no SQLite somente quando o candle fecha (is_closed=True).
    """
    stream = _kline_stream(symbol, interval)
    url = f"{BINANCE_WS_BASE}/{stream}"

    backoff = 1
    while True:
        try:
            logger.info(f"Connecting to {url} ...")
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
                max_size=2**20,
            ) as ws:
                logger.info("WebSocket connected.")
                backoff = 1  # reset do backoff

                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    k = msg.get("k")
                    if not k:
                        continue

                    try:
                        event = normalize_kline(msg)
                    except (KeyError, ValueError, TypeError) as e:
                        logger.warning(f"Malformed kline message: {e}")
                        continue

                    logger.debug(event)

                    if _should_save_candle(event):
                        saved = save_candle_event(event)
                        if saved and event["is_closed"]:
                            logger.info(f"Closed candle saved: {event['symbol']} {event['interval']} open_time={event['open_time']}")

        except Exception as e:
            logger.warning(f"WS error: {e} — reconnecting in {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


BINANCE_WS_COMBINED = "wss://stream.binance.com:9443/stream"

def _multi_stream_url(symbols_config: list[dict]) -> str:
    """
    Build combined stream URL for multiple symbols and timeframes.
    
    Args:
        symbols_config: List of dicts with 'name' and 'timeframes' keys
                       Example: [{"name": "BTCUSDT", "timeframes": ["1h", "4h"]}]
    
    Returns:
        Combined stream URL for Binance WebSocket
    """
    streams = []
    for sym in symbols_config:
        symbol = sym["name"].lower()
        for interval in sym["timeframes"]:
            streams.append(f"{symbol}@kline_{interval}")
    q = urllib.parse.urlencode({"streams": "/".join(streams)})
    return f"{BINANCE_WS_COMBINED}?{q}"

async def listen_multi_klines(symbols_config: list[dict]) -> None:
    """
    Combined stream com reconexão robusta para múltiplos símbolos:
    - backoff exponencial com jitter (1s -> 2 -> 4 ... até 30s, com +/-20%)
    - watchdog de inatividade: se não chegar mensagem em 90s, reconecta
    - recv com timeout de 30s (evita ficar pendurado indefinidamente)
    
    Args:
        symbols_config: List of dicts with 'name' and 'timeframes' keys
                       Example: [{"name": "BTCUSDT", "timeframes": ["1h", "4h"]}]
    """
    url = _multi_stream_url(symbols_config)
    base_backoff = 1      # valor base que vamos exponenciar
    max_backoff = 30      # teto do backoff

    while True:
        try:
            logger.info(f"Connecting to {url} ...")
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
                max_size=2**20,
            ) as ws:
                logger.info("WebSocket connected (multi TF).")
                base_backoff = 1  # Reset backoff on successful connection
                backoff = base_backoff
                last_msg_ts = datetime.now(timezone.utc)

                while True:
                    # Watchdog: se passar 90s sem mensagens, força reconexão limpa
                    now = datetime.now(timezone.utc)
                    if (now - last_msg_ts).total_seconds() > 90:
                        logger.warning("Watchdog: 90s without messages — closing and reconnecting")
                        await ws.close(code=1000)
                        break

                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    except asyncio.TimeoutError:
                        continue

                    try:
                        data = json.loads(raw).get("data") or {}
                    except json.JSONDecodeError:
                        continue

                    k = data.get("k")
                    if not k:
                        continue

                    last_msg_ts = datetime.now(timezone.utc)

                    try:
                        event = normalize_kline(data)
                    except (KeyError, ValueError, TypeError) as e:
                        logger.warning(f"Malformed kline message: {e}")
                        continue

                    logger.debug(event)

                    if _should_save_candle(event):
                        saved = save_candle_event(event)
                        if saved and event["is_closed"]:
                            logger.info(f"Closed candle saved: {event['symbol']} {event['interval']} open_time={event['open_time']}")

        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK, InvalidStatus, WebSocketException) as e:
            jitter = random.uniform(0.8, 1.2)
            base_backoff = min(max_backoff, max(1, int((base_backoff * 2) * jitter)))
            logger.warning(f"WS disconnected: {type(e).__name__}: {e} — reconnecting in {base_backoff}s")
            await asyncio.sleep(base_backoff)

        except Exception as e:
            jitter = random.uniform(0.8, 1.2)
            base_backoff = min(max_backoff, max(1, int((base_backoff * 2) * jitter)))
            logger.error(f"Unexpected error: {e} — reconnecting in {base_backoff}s")
            await asyncio.sleep(base_backoff)
