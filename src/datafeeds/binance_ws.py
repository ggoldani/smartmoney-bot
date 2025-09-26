# src/datafeeds/binance_ws.py
import asyncio
import json
from datetime import datetime, timezone
import random
from websockets.exceptions import (
    ConnectionClosed, ConnectionClosedError, ConnectionClosedOK,
    InvalidStatus, WebSocketException
)

import websockets

def normalize_kline(symbol: str, data: dict) -> dict:
    """
    Converte o kline da Binance (chave 'k') no formato padrão do projeto.
    Espera um dict com a chave 'k' (data['k']).
    """
    k = data["k"]
    return {
        "symbol": symbol.upper(),
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
    """Conecta no WS de klines da Binance e imprime OHLCV."""
    stream = _kline_stream(symbol, interval)
    url = f"{BINANCE_WS_BASE}/{stream}"

    backoff = 1
    while True:
        try:
            print(f"➡️  Conectando em {url} ...")
            async with websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
                max_size=2**20,
            ) as ws:
                print("✅ Conectado.")
                backoff = 1  # reset do backoff

                async for raw in ws:
                    msg = json.loads(raw)
                    k = msg.get("k")
                    if not k:
                        continue

                    event_ts = datetime.fromtimestamp(msg["E"] / 1000, tz=timezone.utc)
                    o, h, l, c = k["o"], k["h"], k["l"], k["c"]
                    v = k["v"]
                    is_closed = k["x"]  # True quando o candle fecha

                    print(
                        f"[{event_ts:%Y-%m-%d %H:%M:%S} UTC] {symbol} 1m "
                        f"O:{o} H:{h} L:{l} C:{c} V:{v} closed={is_closed}"
                    )

        except Exception as e:
            print(f"⚠️  WS erro: {e} — reconectando em {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

import urllib.parse

BINANCE_WS_COMBINED = "wss://stream.binance.com:9443/stream"

def _multi_stream_url(symbol: str, intervals: list[str]) -> str:
    streams = [f"{symbol.lower()}@kline_{itv}" for itv in intervals]
    q = urllib.parse.urlencode({"streams": "/".join(streams)})
    return f"{BINANCE_WS_COMBINED}?{q}"

async def listen_multi_klines(symbol: str = "BTCUSDT", intervals: list[str] = None) -> None:
    """
    Combined stream com reconexão robusta:
    - backoff exponencial com jitter (1s -> 2 -> 4 ... até 30s, com +/-20%)
    - watchdog de inatividade: se não chegar mensagem em 90s, reconecta
    - recv com timeout de 30s (evita ficar pendurado indefinidamente)
    """
    if intervals is None:
        intervals = ["4h", "1d", "1w", "1M"]

    url = _multi_stream_url(symbol, intervals)
    base_backoff = 1      # valor base que vamos exponenciar
    max_backoff = 30      # teto do backoff

    while True:
        try:
            print(f"➡️  Conectando em {url} ...")
            async with websockets.connect(
                url,
                ping_interval=20,  # envia ping automático
                ping_timeout=20,   # sem pong em 20s => erro
                close_timeout=5,
                max_size=2**20,
            ) as ws:
                print("✅ Conectado (multi TF).")
                backoff = base_backoff
                last_msg_ts = datetime.now(timezone.utc)

                while True:
                    # Watchdog: se passar 90s sem mensagens, força reconexão limpa
                    now = datetime.now(timezone.utc)
                    if (now - last_msg_ts).total_seconds() > 90:
                        print("⏱️  Watchdog: 90s sem mensagens — fechando e reconectando…")
                        await ws.close(code=1000)
                        break

                    try:
                        # recv com timeout para não ficar pendurado para sempre
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    except asyncio.TimeoutError:
                        # Sem mensagens em 30s: só continua; ping/pong já mantém a conexão viva
                        continue

                    data = json.loads(raw).get("data") or {}
                    k = data.get("k")
                    if not k:
                        continue

                    last_msg_ts = datetime.now(timezone.utc)
                    itv = k.get("i")  # "4h", "1d", "1w", "1M"
                    event_ts = datetime.fromtimestamp(data["E"] / 1000, tz=timezone.utc)
                    o, h, l, c = k["o"], k["h"], k["l"], k["c"]
                    v = k["v"]
                    closed = k["x"]
                    
                    event = normalize_kline(symbol, data)
                    print(event)

        
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK, InvalidStatus, WebSocketException) as e:
            # desconexões "normais" do WS
            jitter = random.uniform(0.8, 1.2)
            base_backoff = min(max_backoff, max(1, int((base_backoff * 2) * jitter)))
            print(f"⚠️  WS desconectado: {type(e).__name__}: {e} — tentando reconectar em {base_backoff}s")
            await asyncio.sleep(base_backoff)

        except Exception as e:
            # qualquer outro erro inesperado
            jitter = random.uniform(0.8, 1.2)
            base_backoff = min(max_backoff, max(1, int((base_backoff * 2) * jitter)))
            print(f"❗ Erro inesperado: {e} — reconectando em {base_backoff}s")
            await asyncio.sleep(base_backoff)
