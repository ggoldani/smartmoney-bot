# SMARTMONEY BOT
Bot de alertas de mercado cripto (BTCUSDT + BTC.D) para Telegram.

## Rodar local (dry-run)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python src/main.py --dry-run

## Docker
docker compose up --build
