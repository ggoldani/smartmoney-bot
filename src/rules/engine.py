"""
Alert Rules Engine - monitors candles and triggers alerts.
This is the core of the bot's alerting system.
"""
import asyncio
from typing import List, Dict, Set
from datetime import datetime
from loguru import logger

from src.config import (
    get_symbols,
    is_indicator_enabled,
    get_rsi_config,
    get_alert_config
)
from src.indicators.rsi import analyze_rsi, analyze_rsi_all_timeframes
from src.notif.templates import (
    template_rsi_overbought,
    template_rsi_oversold,
    template_rsi_multi_tf,
    template_circuit_breaker
)
from src.notif.throttle import get_throttler
from src.telegram_bot import send_message
from src.storage.db import SessionLocal
from src.storage.models import Candle


class AlertEngine:
    """
    Monitors for new closed candles and triggers alerts based on rules.
    """

    def __init__(self, check_interval: int = 5):
        """
        Args:
            check_interval: How often to check for new candles (seconds)
        """
        self.check_interval = check_interval
        self.running = False

        # Track last processed candle per symbol/interval to avoid duplicates
        self.last_processed: Dict[str, int] = {}  # key: "BTCUSDT_4h", value: open_time

        # Load config
        self.rsi_config = get_rsi_config()
        self.alert_config = get_alert_config()
        self.throttler = get_throttler()

    def _get_candle_key(self, symbol: str, interval: str) -> str:
        """Generate unique key for candle tracking."""
        return f"{symbol}_{interval}"

    async def check_for_new_candles(self):
        """
        Check database for new closed candles since last check.
        Returns list of new candles to process.
        """
        symbols = get_symbols()
        new_candles = []

        with SessionLocal() as session:
            for sym_config in symbols:
                symbol = sym_config["name"]
                timeframes = sym_config["timeframes"]

                for interval in timeframes:
                    key = self._get_candle_key(symbol, interval)
                    last_open_time = self.last_processed.get(key, 0)

                    # Query for candles newer than last processed
                    candle = session.query(Candle).filter(
                        Candle.symbol == symbol,
                        Candle.interval == interval,
                        Candle.is_closed == 1,
                        Candle.open_time > last_open_time
                    ).order_by(Candle.open_time.desc()).first()

                    if candle:
                        new_candles.append({
                            "symbol": candle.symbol,
                            "interval": candle.interval,
                            "open_time": candle.open_time,
                            "close": candle.close
                        })

                        # Update last processed
                        self.last_processed[key] = candle.open_time

        if new_candles:
            logger.debug(f"Found {len(new_candles)} new closed candles")

        return new_candles

    async def process_rsi_alerts(self, symbol: str, interval: str):
        """
        Check RSI for given symbol/interval and send alert if needed.
        """
        if not is_indicator_enabled('rsi'):
            return

        # Check if this timeframe is configured for RSI
        rsi_timeframes = self.rsi_config.get('timeframes', [])
        if interval not in rsi_timeframes:
            return

        # Analyze RSI
        period = self.rsi_config.get('period', 14)
        overbought = self.rsi_config.get('overbought', 70)
        oversold = self.rsi_config.get('oversold', 30)

        result = analyze_rsi(symbol, interval, overbought, oversold, period)

        if not result or result["condition"] == "NORMAL":
            return

        # Prepare alert
        condition_key = f"RSI_{result['condition']}_{interval}"

        # Check throttling
        can_send, reason = self.throttler.can_send_alert(condition_key)
        if not can_send:
            logger.info(f"Alert throttled: {condition_key} - {reason}")
            return

        # Generate message
        if result["condition"] == "OVERBOUGHT":
            message = template_rsi_overbought(result)
        else:  # OVERSOLD
            message = template_rsi_oversold(result)

        # Send alert
        success = send_message(message)

        if success:
            self.throttler.record_alert(condition_key)
            logger.info(f"Alert sent: {condition_key} - RSI={result['rsi']:.2f}")
        else:
            logger.error(f"Failed to send alert: {condition_key}")

    async def check_multi_tf_consolidation(self, symbol: str):
        """
        Check if multiple timeframes have critical RSI simultaneously.
        If yes, send consolidated alert instead of individual alerts.
        """
        if not is_indicator_enabled('rsi'):
            return

        if not self.alert_config.get('consolidate_multi_tf', False):
            return

        # Analyze all RSI timeframes
        rsi_timeframes = self.rsi_config.get('timeframes', [])
        period = self.rsi_config.get('period', 14)
        overbought = self.rsi_config.get('overbought', 70)
        oversold = self.rsi_config.get('oversold', 30)

        critical_conditions = analyze_rsi_all_timeframes(
            symbol, rsi_timeframes, overbought, oversold, period
        )

        # Only consolidate if 2+ timeframes critical
        if len(critical_conditions) < 2:
            return

        logger.info(f"Multi-TF alert: {len(critical_conditions)} timeframes critical for {symbol}")

        # Check throttling
        condition_key = f"RSI_MULTI_TF_{symbol}"
        can_send, reason = self.throttler.can_send_alert(condition_key)
        if not can_send:
            logger.info(f"Multi-TF alert throttled: {reason}")
            return

        # Send consolidated alert
        message = template_rsi_multi_tf(critical_conditions)
        success = send_message(message)

        if success:
            self.throttler.record_alert(condition_key)
            logger.info(f"Multi-TF alert sent: {symbol}")

    async def process_candle(self, candle_data: Dict):
        """
        Process a new closed candle and check all applicable rules.

        Args:
            candle_data: {"symbol": "BTCUSDT", "interval": "4h", "open_time": ..., "close": ...}
        """
        symbol = candle_data["symbol"]
        interval = candle_data["interval"]

        logger.debug(f"Processing candle: {symbol} {interval}")

        # Check individual RSI alert for this timeframe
        await self.process_rsi_alerts(symbol, interval)

        # After processing individual alerts, check for multi-TF consolidation
        # (only run once per symbol, not per candle)
        # We'll check this separately in the main loop

    async def run(self):
        """
        Main loop: continuously check for new candles and process alerts.
        """
        self.running = True
        logger.info("Alert Engine started")

        # Track which symbols we've checked for multi-TF in this cycle
        checked_multi_tf: Set[str] = set()

        while self.running:
            try:
                # Check for new closed candles
                new_candles = await self.check_for_new_candles()

                if new_candles:
                    # Process each new candle
                    for candle in new_candles:
                        await self.process_candle(candle)

                        # Mark symbol for multi-TF check
                        checked_multi_tf.add(candle["symbol"])

                    # After processing all candles, check multi-TF for affected symbols
                    for symbol in checked_multi_tf:
                        await self.check_multi_tf_consolidation(symbol)

                    checked_multi_tf.clear()

                # Check if circuit breaker should trigger
                if self.throttler.should_consolidate_alerts():
                    stats = self.throttler.get_stats()
                    logger.warning(f"Circuit breaker active: {stats['alerts_last_minute']} alerts in last minute")

                    # Could send a mega-alert here if needed
                    # For now, just throttle naturally

                # Wait before next check
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.exception(f"Error in alert engine loop: {e}")
                # Don't crash, just log and continue
                await asyncio.sleep(self.check_interval)

    async def stop(self):
        """Stop the alert engine gracefully."""
        logger.info("Stopping alert engine...")
        self.running = False


# Global engine instance
_engine_instance = None


def get_alert_engine() -> AlertEngine:
    """Get global alert engine instance (singleton)."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AlertEngine()
    return _engine_instance
