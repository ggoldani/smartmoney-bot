import argparse
import asyncio
from datetime import datetime, timezone
from src.config import LOG_LEVEL
from src.utils.logging import setup_logging
from src.telegram_bot import send_message
from src.datafeeds.market_caps import fetch_global_caps

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Não envia para o Telegram; apenas loga.")
    parser.add_argument("--ping", action="store_true", help="Envia uma mensagem simples de status.")
    parser.add_argument("--ws-test", action="store_true", help="Conecta no WS da Binance (BTCUSDT 1m).")
    parser.add_argument("--ws-multi", action="store_true",
                    help="Conecta no WS (BTCUSDT) para 4h, 1d, 1w, 1M.")
    parser.add_argument("--caps-test", action="store_true", help="Consulta TOTAL/ALT MCAP e dominâncias (CoinGecko).")
    args = parser.parse_args()

    logger = setup_logging(LOG_LEVEL)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if args.ws_test:
        from src.datafeeds.binance_ws import listen_kline
        logger.info("Iniciando WS de teste (BTCUSDT 1m)...")
        asyncio.run(listen_kline(symbol="BTCUSDT", interval="1m"))
        return
    
    if args.ws_multi:
        from src.datafeeds.binance_ws import listen_multi_klines
        logger.info("Iniciando WS multi TF (BTCUSDT: 4h,1d,1w,1M)...")
        asyncio.run(listen_multi_klines(symbol="BTCUSDT", intervals=["4h", "1d", "1w", "1M"]))
        return

    if args.ping:
        msg = f"SMARTMONEY BRASIL: online ({ts})"
        ok = send_message(msg)
        logger.info(f"Ping enviado? {ok}")
        return

    if args.caps_test:
        data = fetch_global_caps()
        logger.info(f"Market caps: {data}")
        return

    logger.info("Bot carregado (modo %s).", "dry-run" if args.dry_run else "live")
    if args.dry_run:
        send_message(f"[dry-run] SMARTMONEY BRASIL: online ({ts})")

if __name__ == "__main__":
    main()
