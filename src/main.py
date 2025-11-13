import argparse
import asyncio
import signal
from datetime import datetime, timezone
from loguru import logger

from src.config import (
    LOG_LEVEL,
    get_config,
    get_symbols,
    get_backfill_config,
    get_bot_name,
    get_bot_version
)
from src.utils.logging import setup_logging
from src.telegram_bot import send_message, send_error_to_admin
from src.datafeeds.market_caps import fetch_global_caps
from src.datafeeds.binance_rest import backfill_all_symbols
from src.datafeeds.binance_ws import listen_multi_klines
from src.storage.init_db import init_db
from src.storage.cleanup import schedule_cleanup_task
from src.rules.engine import get_alert_engine
from src.utils.healthcheck import get_healthcheck


# Global shutdown event
shutdown_event = asyncio.Event()


def signal_handler(sig, frame):
    """Handle SIGTERM and SIGINT for graceful shutdown."""
    logger.info(f"Received signal {sig}, initiating graceful shutdown...")
    shutdown_event.set()


async def startup_sequence():
    """
    Execute bot startup sequence:
    1. Initialize database
    2. Load configuration
    3. Backfill historical data
    4. Send startup message
    """
    logger.info("=" * 60)
    logger.info(f"Starting {get_bot_name()} v{get_bot_version()}")
    logger.info("=" * 60)

    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()

        # Load and validate config
        logger.info("Loading configuration...")
        config = get_config()
        logger.info(f"Config loaded: tier={config.get('bot.tier')}, symbols={len(get_symbols())}")

        # Backfill historical data
        backfill_cfg = get_backfill_config()
        if backfill_cfg.get('enabled', True):
            logger.info("Starting historical data backfill...")
            symbols_cfg = get_symbols()
            results = await backfill_all_symbols(symbols_cfg)

            total_candles = sum(sum(r.values()) for r in results.values())
            logger.info(f"Backfill completed: {total_candles} candles saved")

            # Send backfill report to admin (optional)
            # from src.notif.templates import template_backfill_complete
            # for symbol, symbol_results in results.items():
            #     msg = template_backfill_complete(symbol_results)
            #     send_message(msg, to_admin=True)

        logger.info("Startup sequence completed successfully")
        return True

    except Exception as e:
        logger.exception(f"Startup sequence failed: {e}")
        send_error_to_admin("Startup", str(e), "Bot failed to start")
        return False


async def shutdown_sequence():
    """
    Execute bot shutdown sequence:
    1. Stop alert engine
    2. Close WebSocket connections
    3. Send shutdown message
    """
    logger.info("Starting shutdown sequence...")

    try:
        # Stop alert engine
        alert_engine = get_alert_engine()
        await alert_engine.stop()

        # WebSocket will close automatically when tasks are cancelled

        logger.info("Shutdown sequence completed")

    except Exception as e:
        logger.exception(f"Error during shutdown: {e}")


async def run_bot():
    """
    Main bot runtime - runs all async tasks in parallel.
    """
    # Run startup sequence
    startup_ok = await startup_sequence()
    if not startup_ok:
        logger.error("Startup failed, exiting...")
        return

    # Get first symbol config for WebSocket (free tier = BTCUSDT only)
    symbols_cfg = get_symbols()
    if not symbols_cfg:
        logger.error("No symbols configured, exiting...")
        return

    first_symbol = symbols_cfg[0]
    symbol = first_symbol["name"]
    timeframes = first_symbol["timeframes"]

    logger.info(f"Starting main bot tasks: WebSocket ({symbol}) + Alert Engine + DB Cleanup + Healthcheck")

    # Start alert engine and healthcheck server
    alert_engine = get_alert_engine()
    healthcheck = get_healthcheck()

    # Create tasks
    tasks = [
        asyncio.create_task(listen_multi_klines(symbol, timeframes), name="WebSocket"),
        asyncio.create_task(alert_engine.run(), name="AlertEngine"),
        asyncio.create_task(schedule_cleanup_task(), name="DBCleanup"),
        asyncio.create_task(healthcheck.run(), name="Healthcheck"),
        asyncio.create_task(shutdown_event.wait(), name="ShutdownWatcher")
    ]

    try:
        # Wait for shutdown signal
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        # Shutdown triggered
        logger.info("Shutdown signal received, stopping tasks...")

        # Cancel all remaining tasks
        for task in pending:
            task.cancel()

        # Wait for cancellation to complete
        await asyncio.gather(*pending, return_exceptions=True)

    except Exception as e:
        logger.exception(f"Error in main bot runtime: {e}")
        send_error_to_admin("Runtime", str(e), "Critical error in main loop")

    finally:
        await shutdown_sequence()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Dry-run mode (logs only, no Telegram)")
    parser.add_argument("--ping", action="store_true", help="Send test message to Telegram")
    parser.add_argument("--ws-test", action="store_true", help="Test WebSocket connection (BTCUSDT 1m)")
    parser.add_argument("--ws-multi", action="store_true", help="Test WebSocket multi-TF (BTCUSDT: 4h,1d,1w,1M)")
    parser.add_argument("--caps-test", action="store_true", help="Test market caps API")
    parser.add_argument("--init-db", action="store_true", help="Initialize database tables")
    parser.add_argument("--backfill", action="store_true", help="Run backfill only")
    args = parser.parse_args()

    # Setup logging
    log = setup_logging(LOG_LEVEL)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Legacy test modes (keep for backward compatibility)
    if args.init_db:
        init_db()
        logger.info("Database initialized")
        return

    if args.ws_test:
        from src.datafeeds.binance_ws import listen_kline
        logger.info("Starting WebSocket test (BTCUSDT 1m)...")
        asyncio.run(listen_kline(symbol="BTCUSDT", interval="1m"))
        return

    if args.ws_multi:
        from src.datafeeds.binance_ws import listen_multi_klines
        logger.info("Starting WebSocket multi-TF test...")
        asyncio.run(listen_multi_klines(symbol="BTCUSDT", intervals=["4h", "1d", "1w", "1M"]))
        return

    if args.ping:
        msg = f"SMARTMONEY BRASIL: online ({ts})"
        ok = send_message(msg)
        logger.info(f"Ping sent? {ok}")
        return

    if args.caps_test:
        data = fetch_global_caps()
        logger.info(f"Market caps: {data}")
        return

    if args.backfill:
        logger.info("Running backfill only...")
        symbols_cfg = get_symbols()
        results = asyncio.run(backfill_all_symbols(symbols_cfg))
        logger.info(f"Backfill results: {results}")
        return

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run main bot
    logger.info("Bot starting in %s mode", "dry-run" if args.dry_run else "live")

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down...")
    except Exception as e:
        logger.exception(f"Unhandled exception in main: {e}")
        send_error_to_admin("Fatal", str(e), "Bot crashed")
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    main()
