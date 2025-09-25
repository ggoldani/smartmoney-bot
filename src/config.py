import os
from dotenv import load_dotenv

# carrega o .env da raiz do projeto
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_CHAT_ID = os.getenv("CHANNEL_CHAT_ID", "")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENABLE_CHARTS = os.getenv("ENABLE_CHARTS", "false").lower() == "true"
USE_COINGECKO_FOR_BTCD = os.getenv("USE_COINGECKO_FOR_BTCD", "true").lower() == "true"
