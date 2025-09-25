from typing import Optional
from loguru import logger
from src.config import BOT_TOKEN, CHANNEL_CHAT_ID

try:
    from telegram import Bot
except Exception:
    Bot = None

import asyncio

async def _send_message_async(text: str) -> None:
    bot = Bot(BOT_TOKEN)
    await bot.send_message(chat_id=CHANNEL_CHAT_ID, text=text)

async def _send_photo_async(path: str, caption: Optional[str]) -> None:
    bot = Bot(BOT_TOKEN)
    with open(path, "rb") as f:
        await bot.send_photo(chat_id=CHANNEL_CHAT_ID, photo=f, caption=caption)

def _run(coro):
    """Executa a coroutine, mesmo se já houver um event loop rodando."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    else:
        # se já existir loop (no futuro, dentro do app), agenda e espera
        return asyncio.get_event_loop().create_task(coro)

def send_message(text: str) -> bool:
    if not BOT_TOKEN or not CHANNEL_CHAT_ID or Bot is None:
        logger.info(f"[dry-run] MSG -> {text}")
        return True
    try:
        _run(_send_message_async(text))
        return True
    except Exception as e:
        logger.exception(e)
        return False

def send_photo(path: str, caption: Optional[str] = None) -> bool:
    if not BOT_TOKEN or not CHANNEL_CHAT_ID or Bot is None:
        logger.info(f"[dry-run] PHOTO -> {path} | caption={caption}")
        return True
    try:
        _run(_send_photo_async(path, caption))
        return True
    except Exception as e:
        logger.exception(e)
        return False
