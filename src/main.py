import argparse
from datetime import datetime, timezone
from src.config import LOG_LEVEL
from src.utils.logging import setup_logging
from src.telegram_bot import send_message

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Não envia para o Telegram; apenas loga.")
    parser.add_argument("--ping", action="store_true", help="Envia uma mensagem simples de status.")
    args = parser.parse_args()

    logger = setup_logging(LOG_LEVEL)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if args.ping:
        msg = f"SMARTMONEY BRASIL: online ({ts})"
        ok = send_message(msg)
        logger.info(f"Ping enviado? {ok}")
        return

    logger.info("Bot carregado (modo %s).", "dry-run" if args.dry_run else "live")
    if args.dry_run:
        send_message(f"[dry-run] SMARTMONEY BRASIL: online ({ts})")

if __name__ == "__main__":
    main()
