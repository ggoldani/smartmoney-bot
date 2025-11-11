# -*- coding: utf-8 -*-
"""
Database cleanup and maintenance tasks.
Handles deletion of old candles while maintaining minimum retention.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict
from loguru import logger
from sqlalchemy import func, delete

from src.storage.db import SessionLocal
from src.storage.models import Candle
from src.config import get_database_cleanup_config, get_symbols


def cleanup_old_candles() -> Dict[str, int]:
    """
    Delete old candles from database while maintaining minimum retention.

    Rules:
    1. Delete candles older than retention_days (default 90)
    2. BUT always keep at least min_candles_per_tf (default 200) per symbol/interval

    Returns:
        Dict with cleanup stats: {"deleted": 42, "kept": 1234}
    """
    config = get_database_cleanup_config()

    if not config.get('enabled', False):
        logger.info("Database cleanup is disabled in config")
        return {"deleted": 0, "kept": 0}

    retention_days = config.get('retention_days', 90)
    min_candles_per_tf = config.get('min_candles_per_tf', 200)

    # Calculate cutoff timestamp (retention_days ago)
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_ms = int(cutoff_time.timestamp() * 1000)

    logger.info(f"Starting database cleanup: retention={retention_days}d, min_candles={min_candles_per_tf}")

    total_deleted = 0
    total_kept = 0

    with SessionLocal() as session:
        symbols = get_symbols()

        for sym_config in symbols:
            symbol = sym_config["name"]
            timeframes = sym_config["timeframes"]

            for interval in timeframes:
                # Count total candles for this symbol/interval
                total_count = session.query(func.count(Candle.id)).filter(
                    Candle.symbol == symbol,
                    Candle.interval == interval
                ).scalar()

                # Count candles older than cutoff
                old_count = session.query(func.count(Candle.id)).filter(
                    Candle.symbol == symbol,
                    Candle.interval == interval,
                    Candle.open_time < cutoff_ms
                ).scalar()

                # Calculate how many we can safely delete
                # We can only delete if: total - old_count >= min_candles_per_tf
                # Which means: old_count <= total - min_candles_per_tf
                max_deletable = max(0, total_count - min_candles_per_tf)
                to_delete = min(old_count, max_deletable)

                if to_delete > 0:
                    # Get IDs of oldest candles to delete
                    oldest_candles = session.query(Candle.id).filter(
                        Candle.symbol == symbol,
                        Candle.interval == interval,
                        Candle.open_time < cutoff_ms
                    ).order_by(Candle.open_time.asc()).limit(to_delete).all()

                    candle_ids = [c.id for c in oldest_candles]

                    # Delete them
                    stmt = delete(Candle).where(Candle.id.in_(candle_ids))
                    result = session.execute(stmt)
                    session.commit()

                    deleted_count = result.rowcount
                    total_deleted += deleted_count

                    logger.info(
                        f"Cleaned up {symbol} {interval}: "
                        f"deleted {deleted_count}/{old_count} old candles "
                        f"(kept {total_count - deleted_count})"
                    )
                else:
                    kept = total_count
                    total_kept += kept
                    logger.debug(
                        f"Skipped {symbol} {interval}: "
                        f"{total_count} candles (below minimum {min_candles_per_tf})"
                    )

    logger.info(f"Database cleanup complete: deleted {total_deleted} candles")

    return {"deleted": total_deleted, "kept": total_kept}


async def schedule_cleanup_task():
    """
    Async task that runs cleanup on a schedule (daily at configured time).
    Uses simple asyncio loop rather than full scheduler library.
    """
    import asyncio

    config = get_database_cleanup_config()

    if not config.get('enabled', False):
        logger.info("Database cleanup scheduler is disabled")
        return

    # Parse cron schedule (e.g., "0 3 * * *" = 03:00 daily)
    # For simplicity, we'll run cleanup daily at 03:00 UTC
    schedule_hour = 3  # 03:00 UTC (00:00 BRT = UTC-3)

    logger.info(f"Database cleanup scheduled daily at {schedule_hour:02d}:00 UTC")

    while True:
        try:
            # Calculate time until next run
            now = datetime.now(timezone.utc)
            next_run = now.replace(hour=schedule_hour, minute=0, second=0, microsecond=0)

            # If we've passed today's scheduled time, schedule for tomorrow
            if now >= next_run:
                next_run += timedelta(days=1)

            sleep_seconds = (next_run - now).total_seconds()

            logger.info(f"Next cleanup scheduled for {next_run} (in {sleep_seconds/3600:.1f}h)")

            # Sleep until next run
            await asyncio.sleep(sleep_seconds)

            # Run cleanup
            logger.info("Running scheduled database cleanup...")
            result = cleanup_old_candles()
            logger.info(f"Cleanup result: {result}")

        except Exception as e:
            logger.exception(f"Error in cleanup scheduler: {e}")
            # Sleep 1 hour before retrying
            await asyncio.sleep(3600)
