# src/datafeeds/binance_ws.py
import asyncio
import json
from datetime import datetime, timezone

import websockets

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
    """Conecta no combined stream e imprime OHLCV para vários timeframes."""
    if intervals is None:
        intervals = ["4h", "1d", "1w", "1M"]

    url = _multi_stream_url(symbol, intervals)
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
                print("✅ Conectado (multi TF).")
                backoff = 1

                async for raw in ws:
                    msg = json.loads(raw)

                    # Combined stream vem como {"stream": "...", "data": {...}}
                    data = msg.get("data") or {}
                    k = data.get("k")
                    if not k:
                        continue

                    # Descobre o timeframe a partir do próprio kline (campo "i")
                    itv = k.get("i")  # ex.: "4h", "1d", "1w", "1M"
                    event_ts = datetime.fromtimestamp(data["E"] / 1000, tz=timezone.utc)

                    o, h, l, c = k["o"], k["h"], k["l"], k["c"]
                    v = k["v"]
                    closed = k["x"]

                    print(
                        f"[{event_ts:%Y-%m-%d %H:%M:%S} UTC] {symbol} {itv:<2} "
                        f"O:{o} H:{h} L:{l} C:{c} V:{v} closed={closed}"
                    )
        except Exception as e:
            print(f"⚠️  WS erro (multi): {e} — reconectando em {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
