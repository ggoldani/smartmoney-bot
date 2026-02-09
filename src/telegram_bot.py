from typing import Optional
from loguru import logger
from src.config import BOT_TOKEN, CHANNEL_CHAT_ID, ADMIN_CHANNEL_ID

try:
    from telegram import Bot
except ImportError:
    Bot = None

import asyncio

# Cached Bot instance (avoids creating a new instance per message)
_bot_instance = None


def _get_bot():
    """Get or create cached Bot instance."""
    global _bot_instance
    if _bot_instance is None and BOT_TOKEN and Bot is not None:
        _bot_instance = Bot(BOT_TOKEN)
    return _bot_instance


async def _send_message_async(text: str, chat_id: str) -> None:
    """Send message to specific chat."""
    bot = _get_bot()
    await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML')

async def _send_photo_async(path: str, caption: Optional[str], chat_id: str) -> None:
    """Send photo to specific chat."""
    bot = _get_bot()
    with open(path, "rb") as f:
        await bot.send_photo(chat_id=chat_id, photo=f, caption=caption)

def _log_task_exception(task: asyncio.Task) -> None:
    """Log exceptions from fire-and-forget tasks."""
    try:
        if task.done() and task.exception():
            logger.error(f"Background send failed: {task.exception()}")
    except asyncio.CancelledError:
        pass

def _run(coro):
    """Run a coroutine from sync context. If an event loop is running, schedules as a task."""
    try:
        loop = asyncio.get_running_loop()
        # Already in async context: fire-and-forget (can't await from sync)
        task = loop.create_task(coro)
        task.add_done_callback(_log_task_exception)
        return task
    except RuntimeError:
        # No running loop: run to completion and return result
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
    Send message to Telegram (sync wrapper — delegates to send_message_async).

    IMPORTANT: When called from an async context (running event loop), this
    schedules a fire-and-forget task and returns True immediately without
    waiting for delivery confirmation. Use send_message_async() directly
    in async code for reliable success/failure tracking.

    Args:
        text: Message text
        to_admin: If True, send to admin channel; otherwise send to main channel

    Returns:
        True if sent successfully (or scheduled in async context), False otherwise
    """
    try:
        result = _run(send_message_async(text, to_admin=to_admin))
        # If _run returned a Task (inside event loop), assume success
        return result if isinstance(result, bool) else True
    except Exception as e:
        logger.exception(f"Failed to send message to {'admin' if to_admin else 'group'}: {e}")
        return False

async def send_photo_async(path: str, caption: Optional[str] = None, to_admin: bool = False) -> bool:
    """
    Send photo to Telegram (async version).

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
        await _send_photo_async(path, caption, target_chat_id)
        return True
    except Exception as e:
        logger.exception(f"Failed to send photo to {'admin' if to_admin else 'group'}: {e}")
        return False


def send_photo(path: str, caption: Optional[str] = None, to_admin: bool = False) -> bool:
    """Send photo to Telegram (sync wrapper — delegates to send_photo_async)."""
    try:
        result = _run(send_photo_async(path, caption, to_admin=to_admin))
        return result if isinstance(result, bool) else True
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
