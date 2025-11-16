from typing import Optional
from loguru import logger
from src.config import BOT_TOKEN, CHANNEL_CHAT_ID, ADMIN_CHANNEL_ID

try:
    from telegram import Bot
except Exception:
    Bot = None

import asyncio

async def _send_message_async(text: str, chat_id: str) -> None:
    """Send message to specific chat."""
    bot = Bot(BOT_TOKEN)
    await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')

async def _send_photo_async(path: str, caption: Optional[str], chat_id: str) -> None:
    """Send photo to specific chat."""
    bot = Bot(BOT_TOKEN)
    with open(path, "rb") as f:
        await bot.send_photo(chat_id=chat_id, photo=f, caption=caption)

def _run(coro):
    """Executa a coroutine, mesmo se já houver um event loop rodando."""
    try:
        loop = asyncio.get_running_loop()
        # Already in async context, create task
        return loop.create_task(coro)
    except RuntimeError:
        # No running loop, use asyncio.run()
        return asyncio.run(coro)

async def send_message_async(text: str, to_admin: bool = False) -> bool:
    """
    Send message to Telegram (async version).

    Args:
        text: Message text
        to_admin: If True, send to admin channel; otherwise send to main channel

    Returns:
        True if sent successfully, False otherwise
    """
    target_chat_id = ADMIN_CHANNEL_ID if to_admin else CHANNEL_CHAT_ID

    if not BOT_TOKEN or not target_chat_id or Bot is None:
        prefix = "[admin]" if to_admin else "[group]"
        logger.info(f"[dry-run] {prefix} MSG -> {text}")
        return True

    try:
        await _send_message_async(text, target_chat_id)
        return True
    except Exception as e:
        logger.exception(f"Failed to send message to {'admin' if to_admin else 'group'}: {e}")
        return False

def send_message(text: str, to_admin: bool = False) -> bool:
    """
    Send message to Telegram (sync wrapper for backward compatibility).

    Args:
        text: Message text
        to_admin: If True, send to admin channel; otherwise send to main channel

    Returns:
        True if sent successfully, False otherwise
    """
    target_chat_id = ADMIN_CHANNEL_ID if to_admin else CHANNEL_CHAT_ID

    if not BOT_TOKEN or not target_chat_id or Bot is None:
        prefix = "[admin]" if to_admin else "[group]"
        logger.info(f"[dry-run] {prefix} MSG -> {text}")
        return True

    try:
        _run(_send_message_async(text, target_chat_id))
        return True
    except Exception as e:
        logger.exception(f"Failed to send message to {'admin' if to_admin else 'group'}: {e}")
        return False

def send_photo(path: str, caption: Optional[str] = None, to_admin: bool = False) -> bool:
    """
    Send photo to Telegram.

    Args:
        path: Path to image file
        caption: Optional caption
        to_admin: If True, send to admin channel; otherwise send to main channel

    Returns:
        True if sent successfully, False otherwise
    """
    target_chat_id = ADMIN_CHANNEL_ID if to_admin else CHANNEL_CHAT_ID

    if not BOT_TOKEN or not target_chat_id or Bot is None:
        prefix = "[admin]" if to_admin else "[group]"
        logger.info(f"[dry-run] {prefix} PHOTO -> {path} | caption={caption}")
        return True

    try:
        _run(_send_photo_async(path, caption, target_chat_id))
        return True
    except Exception as e:
        logger.exception(f"Failed to send photo to {'admin' if to_admin else 'group'}: {e}")
        return False

def send_error_to_admin(error_type: str, error_msg: str, context: str = "") -> bool:
    """
    Send error alert to admin channel.

    Args:
        error_type: Type of error (e.g., "WebSocket", "Database")
        error_msg: Error message
        context: Additional context

    Returns:
        True if sent successfully
    """
    from src.notif.templates import template_error_admin

    message = template_error_admin(error_type, error_msg, context)
    return send_message(message, to_admin=True)

def send_warning_to_admin(warning_type: str, warning_msg: str) -> bool:
    """
    Send warning to admin channel.

    Args:
        warning_type: Type of warning
        warning_msg: Warning message

    Returns:
        True if sent successfully
    """
    from src.notif.templates import template_warning_admin

    message = template_warning_admin(warning_type, warning_msg)
    return send_message(message, to_admin=True)
