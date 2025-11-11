#!/usr/bin/env bash
set -euo pipefail

# 1) Pastas e arquivos vazios
mkdir -p src/{datafeeds,indicators,rules,notif,storage,backtest,viz,utils} docker
touch src/{__init__.py,config.py,main.py,telegram_bot.py}
touch src/datafeeds/{__init__.py,binance_ws.py,btc_dominance.py}
touch src/indicators/{__init__.py,ma.py,rsi.py,sr_levels.py,breakouts.py}
touch src/rules/{__init__.py,engine.py,rule_defs.py}
touch src/notif/{__init__.py,formatter.py,templates.py,throttle.py}
touch src/storage/{__init__.py,db.py,models.py}
touch src/backtest/{__init__.py,loader.py,runner.py,report.py}
touch src/viz/{__init__.py,chart.py}
touch .gitignore requirements.txt .env.example README.md docker/Dockerfile docker-compose.yml

# 2) .gitignore
cat > .gitignore <<'EOF'
__pycache__/
*.pyc
*.pyo
*.pyd
.venv/
venv/
.env
*.env
*.sqlite
*.db
logs/
*.log
.DS_Store
.idea/
.vscode/
docker-data/
EOF

# 3) requirements.txt (mínimo; demais lib adicionamos depois)
cat > requirements.txt <<'EOF'
python-telegram-bot==21.6
pandas==2.2.2
loguru==0.7.2
APScheduler==3.10.4
requests==2.32.3
EOF

# 4) .env.example
cat > .env.example <<'EOF'
BOT_TOKEN=
CHANNEL_CHAT_ID=
LOG_LEVEL=INFO
ENABLE_CHARTS=false
USE_COINGECKO_FOR_BTCD=true
EOF

# 5) README.md
cat > README.md <<'EOF'
# SMARTMONEY BOT
Bot de alertas de mercado cripto (BTCUSDT + BTC.D) para Telegram.

## Rodar local (dry-run)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python src/main.py --dry-run

## Docker
docker compose up --build
EOF

# 6) docker/Dockerfile
cat > docker/Dockerfile <<'EOF'
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates git tzdata \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src /app/src
COPY .env.example /app/.env.example
ENV PYTHONUNBUFFERED=1
CMD ["python", "src/main.py", "--dry-run"]
EOF

# 7) docker-compose.yml
cat > docker-compose.yml <<'EOF'
services:
  bot:
    build:
      context: .
      dockerfile: docker/Dockerfile
    env_file:
      - .env
    volumes:
      - ./src:/app/src
      - ./docker-data:/app/data
    restart: unless-stopped
EOF

# 8) src/config.py
cat > src/config.py <<'EOF'
import os
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_CHAT_ID = os.getenv("CHANNEL_CHAT_ID", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENABLE_CHARTS = os.getenv("ENABLE_CHARTS", "false").lower() == "true"
USE_COINGECKO_FOR_BTCD = os.getenv("USE_COINGECKO_FOR_BTCD", "true").lower() == "true"
EOF

# 9) src/utils/logging.py
cat > src/utils/logging.py <<'EOF'
from loguru import logger
import sys
def setup_logging(level: str = "INFO"):
    logger.remove()
    logger.add(sys.stdout, level=level, backtrace=False, diagnose=False)
    return logger
EOF

# 10) src/utils/timeframes.py
cat > src/utils/timeframes.py <<'EOF'
VALID_TF = {"4h": "4h", "1d": "1d", "1w": "1w", "1M": "1M"}
def all_base_timeframes():
    return ["4h", "1d", "1w", "1M"]
EOF

# 11) src/telegram_bot.py
cat > src/telegram_bot.py <<'EOF'
from typing import Optional
from loguru import logger
from src.config import BOT_TOKEN, CHANNEL_CHAT_ID
try:
    from telegram import Bot
except Exception:
    Bot = None

def send_message(text: str) -> bool:
    if not BOT_TOKEN or not CHANNEL_CHAT_ID or Bot is None:
        logger.info(f"[dry-run] MSG -> {text}")
        return True
    try:
        bot = Bot(BOT_TOKEN)
        bot.send_message(chat_id=CHANNEL_CHAT_ID, text=text)
        return True
    except Exception as e:
        logger.exception(e)
        return False

def send_photo(path: str, caption: Optional[str] = None) -> bool:
    if not BOT_TOKEN or not CHANNEL_CHAT_ID or Bot is None:
        logger.info(f"[dry-run] PHOTO -> {path} | caption={caption}")
        return True
    try:
        bot = Bot(BOT_TOKEN)
        with open(path, "rb") as f:
            bot.send_photo(chat_id=CHANNEL_CHAT_ID, photo=f, caption=caption)
        return True
    except Exception as e:
        logger.exception(e)
        return False
EOF

# 12) src/main.py
cat > src/main.py <<'EOF'
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
EOF

echo "✅ Bootstrap concluído."
echo "Próximos passos:"
echo "  1) python -m venv .venv && source .venv/bin/activate"
echo "  2) pip install -r requirements.txt"
echo "  3) cp .env.example .env  # preencha quando tiver token"
echo "  4) python src/main.py --dry-run"
