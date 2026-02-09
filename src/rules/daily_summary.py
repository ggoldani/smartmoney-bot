"""
Daily summary task: sends Fear & Greed Index + RSI at scheduled BRT time.
Extracted from engine.py to reduce file size and improve maintainability.
"""
import asyncio
from datetime import datetime, timedelta

import pytz
from loguru import logger

from src.config import get_daily_summary_config, get_symbols
from src.datafeeds.fear_greed import fetch_fear_greed_index, get_fear_greed_sentiment
from src.indicators.rsi import analyze_rsi
from src.notif.templates import template_daily_summary_multi
from src.storage.repo import get_previous_closed_candle
from src.telegram_bot import send_message_async


async def run_daily_summary_loop(
    rsi_config: dict,
    throttler,
    running_flag_fn
) -> None:
    """
    Daily summary loop: sends Fear & Greed Index + RSI 1D/1W/1M at configured BRT time.
    Runs continuously, calculating next send time each cycle.

    Args:
        rsi_config: RSI configuration dict (period, overbought, oversold)
        throttler: AlertThrottler instance for recording alerts
        running_flag_fn: Callable that returns True while engine is running
    """
    config = get_daily_summary_config()

    if not config.get('enabled', False):
        logger.info("Daily summary disabled in config")
        return

    send_time_brt = config.get('send_time_brt', '21:00')
    send_window_minutes = config.get('send_window_minutes', 5)

    # Parse send time (HH:MM format)
    try:
        hour, minute = map(int, send_time_brt.split(':'))
    except (ValueError, TypeError):
        logger.error(f"Invalid send_time_brt format: {send_time_brt}")
        return

    brt_tz = pytz.timezone('America/Sao_Paulo')

    while running_flag_fn():
        try:
            # Calculate next send time (target BRT today or tomorrow)
            now_utc = datetime.now(pytz.UTC)
            now_brt = now_utc.astimezone(brt_tz)

            target_brt = now_brt.replace(hour=hour, minute=minute, second=0, microsecond=0)

            if target_brt <= now_brt:
                target_brt = (now_brt + timedelta(days=1)).replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )

            # Calculate sleep duration
            now_utc = datetime.now(pytz.UTC)
            now_brt = now_utc.astimezone(brt_tz)
            sleep_duration = (target_brt - now_brt).total_seconds()

            logger.info(
                f"Daily summary scheduled for {target_brt.strftime('%Y-%m-%d %H:%M BRT')} "
                f"(in {sleep_duration:.0f}s)"
            )

            await asyncio.sleep(max(0, sleep_duration))

            if not running_flag_fn():
                break

            config = get_daily_summary_config()
            if not config.get('enabled', False):
                logger.info("Daily summary was disabled, pausing task")
                break

            # Check if within send window
            now_brt = datetime.now(pytz.UTC).astimezone(brt_tz)
            window_start = now_brt.replace(hour=hour, minute=minute, second=0) - timedelta(
                minutes=send_window_minutes
            )
            window_end = now_brt.replace(hour=hour, minute=minute, second=0) + timedelta(
                minutes=send_window_minutes
            )

            if window_start <= now_brt <= window_end:
                await _send_summary(rsi_config, throttler)
            else:
                logger.debug(f"Outside send window ({send_window_minutes}min tolerance)")

        except asyncio.CancelledError:
            logger.info("Daily summary task cancelled")
            break
        except Exception as e:
            logger.exception(f"Error in daily summary task: {e}")
            await asyncio.sleep(60)


async def _send_summary(rsi_config: dict, throttler) -> None:
    """Fetch data and send the daily summary message."""
    fgi_value, fgi_label = await fetch_fear_greed_index()
    fgi_emoji, fgi_sentiment = get_fear_greed_sentiment(fgi_value)

    symbols_cfg = get_symbols()
    if not symbols_cfg:
        logger.warning("No symbols configured for daily summary")
        return

    period = rsi_config.get('period', 14)
    overbought = rsi_config.get('overbought', 70)
    oversold = rsi_config.get('oversold', 30)

    symbols_data = []
    for sym_config in symbols_cfg:
        symbol = sym_config["name"]

        rsi_1d_result = analyze_rsi(symbol, "1d", overbought, oversold, period)
        rsi_1d = rsi_1d_result.get('rsi', 0) if rsi_1d_result else 0

        rsi_1w_result = analyze_rsi(symbol, "1w", overbought, oversold, period)
        rsi_1w = rsi_1w_result.get('rsi', 0) if rsi_1w_result else 0

        rsi_1m_result = analyze_rsi(symbol, "1M", overbought, oversold, period)
        rsi_1m = rsi_1m_result.get('rsi', 0) if rsi_1m_result else 0

        closed_candle = get_previous_closed_candle(symbol, "1d")
        price_open = closed_candle["open"] if closed_candle else 0
        price_close = closed_candle["close"] if closed_candle else 0

        symbols_data.append({
            "symbol": symbol,
            "rsi_1d": rsi_1d,
            "rsi_1w": rsi_1w,
            "rsi_1m": rsi_1m,
            "price_open": price_open,
            "price_close": price_close
        })

    message = template_daily_summary_multi(
        symbols_data=symbols_data,
        fear_greed_value=fgi_value if fgi_value else 0,
        fear_greed_label=fgi_sentiment,
        fear_emoji=fgi_emoji
    )

    success = await send_message_async(message)
    if success:
        logger.info(f"[OK] Daily summary sent ({len(symbols_data)} symbols)")
        throttler.record_alert("DAILY_SUMMARY")
    else:
        logger.error("[ERROR] Failed to send daily summary")
