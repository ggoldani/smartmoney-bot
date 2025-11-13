"""
Alert Rules Engine - monitors candles and triggers alerts.
This is the core of the bot's alerting system.
"""
import asyncio
from typing import List, Dict, Set, Optional
from datetime import datetime
from loguru import logger

from src.config import (
    get_symbols,
    is_indicator_enabled,
    get_rsi_config,
    get_breakout_config,
    get_alert_config
)
from src.indicators.rsi import analyze_rsi, analyze_rsi_all_timeframes
from src.indicators.breakouts import check_breakout
from src.notif.templates import (
    template_rsi_overbought,
    template_rsi_oversold,
    template_rsi_extreme_overbought,
    template_rsi_extreme_oversold,
    template_rsi_multi_tf,
    template_breakout_bull,
    template_breakout_bear,
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

        # Track which candles already triggered alerts (to avoid spam during same candle)
        # key: "BTCUSDT_4h_1762891200000_OVERSOLD", value: True
        self.alerted_candles: Dict[str, bool] = {}

        # Track last condition per symbol/interval to prevent spam
        # key: "BTCUSDT_1h_RSI", value: "OVERSOLD" | "OVERBOUGHT" | None
        # key: "BTCUSDT_1d_BREAKOUT", value: "BULL" | "BEAR" | None
        self.last_condition: Dict[str, Optional[str]] = {}

        # Load config
        self.rsi_config = get_rsi_config()
        self.breakout_config = get_breakout_config()
        self.alert_config = get_alert_config()
        self.throttler = get_throttler()

    def _get_candle_key(self, symbol: str, interval: str) -> str:
        """Generate unique key for candle tracking."""
        return f"{symbol}_{interval}"

    async def check_for_new_candles(self):
        """
        Check database for latest candles (open OR closed) since last check.
        Returns list of candles to process.
        """
        symbols = get_symbols()
        candles_to_process = []

        with SessionLocal() as session:
            for sym_config in symbols:
                symbol = sym_config["name"]
                timeframes = sym_config["timeframes"]

                for interval in timeframes:
                    key = self._get_candle_key(symbol, interval)
                    last_open_time = self.last_processed.get(key, None)

                    # Query for LATEST candle (open or closed), not just closed ones
                    candle = session.query(Candle).filter(
                        Candle.symbol == symbol,
                        Candle.interval == interval
                    ).order_by(Candle.open_time.desc()).first()

                    if not candle:
                        continue

                    # Initialize on first run: skip all existing candles, start from next one
                    if last_open_time is None:
                        self.last_processed[key] = candle.open_time
                        logger.debug(f"Alert engine initialized for {symbol} {interval}: starting from next candle after {candle.open_time}")
                        continue

                    # Only process if candle is newer than last processed
                    if candle.open_time > last_open_time:
                        candles_to_process.append({
                            "symbol": candle.symbol,
                            "interval": candle.interval,
                            "open_time": candle.open_time,
                            "close": candle.close,
                            "is_closed": candle.is_closed
                        })

                        self.last_processed[key] = candle.open_time
                        # Clear alert history for this symbol/interval (new candle started)
                        self._clear_candle_alerts(symbol, interval, last_open_time)

        if candles_to_process:
            logger.debug(f"Processing {len(candles_to_process)} candles (open or closed)")

        return candles_to_process

    def _clear_candle_alerts(self, symbol: str, interval: str, old_open_time: int):
        """Clear alert flags for old candle when new candle starts."""
        prefix = f"{symbol}_{interval}_{old_open_time}_"
        keys_to_remove = [k for k in self.alerted_candles.keys() if k.startswith(prefix)]
        for key in keys_to_remove:
            del self.alerted_candles[key]
        if keys_to_remove:
            logger.debug(f"Cleared {len(keys_to_remove)} alert flags for old candle")

    async def process_rsi_alerts(self, symbol: str, interval: str, open_time: int):
        """
        Check RSI for given symbol/interval and send alert if needed.
        Includes anti-spam protection: only alerts again after RSI recovers to neutral zone.

        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            interval: Timeframe (e.g., 1h)
            open_time: Candle open_time to track if we already alerted
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

        if not result:
            return

        # Track condition state for anti-spam
        condition_tracker_key = f"{symbol}_{interval}_RSI"
        current_condition = result["condition"]
        current_rsi = result["rsi"]
        last_condition = self.last_condition.get(condition_tracker_key)

        # RECOVERY ZONES (to reset alert permission):
        # - For OVERSOLD/EXTREME_OVERSOLD: RSI must go above 35 to reset
        # - For OVERBOUGHT/EXTREME_OVERBOUGHT: RSI must go below 65 to reset
        RECOVERY_OVERSOLD_THRESHOLD = 35
        RECOVERY_OVERBOUGHT_THRESHOLD = 65

        # Check if RSI is in recovery/neutral zone → reset state but ALLOW processing
        if RECOVERY_OVERSOLD_THRESHOLD < current_rsi < RECOVERY_OVERBOUGHT_THRESHOLD:
            # RSI is neutral - reset condition tracker
            if last_condition is not None:
                logger.debug(f"RSI recovery detected for {symbol} {interval}: RSI={current_rsi:.2f} (was {last_condition})")
                self.last_condition[condition_tracker_key] = None
            # Don't return here - allow check of next condition below

        # If current condition is NORMAL, nothing to alert
        if current_condition == "NORMAL":
            return

        # ANTI-SPAM LOGIC: Check if we can alert
        # Allow alert if:
        # 1. Never alerted this condition before (last_condition is None)
        # 2. OR condition changed (OVERSOLD→EXTREME_OVERSOLD, OVERBOUGHT→EXTREME_OVERBOUGHT, etc)
        # 3. OR went through recovery zone

        # Same condition persists without recovery = skip (anti-spam)
        if last_condition is not None and last_condition == current_condition:
            # Same condition as before, no recovery happened - SKIP ALERT (anti-spam)
            logger.debug(f"Anti-spam: {symbol} {interval} still {current_condition}, RSI={current_rsi:.2f} (no recovery)")
            return

        # Check if we already alerted for this specific candle + condition
        alert_key = f"{symbol}_{interval}_{open_time}_{current_condition}"
        if alert_key in self.alerted_candles:
            # Already alerted for this candle, skip
            return

        # Prepare alert
        condition_key = f"RSI_{current_condition}_{interval}"

        # Check throttling
        can_send, reason = self.throttler.can_send_alert(condition_key)
        if not can_send:
            logger.info(f"Alert throttled: {condition_key} - {reason}")
            return

        # Generate message based on condition
        if current_condition == "EXTREME_OVERBOUGHT":
            message = template_rsi_extreme_overbought(result)
        elif current_condition == "EXTREME_OVERSOLD":
            message = template_rsi_extreme_oversold(result)
        elif current_condition == "OVERBOUGHT":
            message = template_rsi_overbought(result)
        elif current_condition == "OVERSOLD":
            message = template_rsi_oversold(result)
        else:
            return  # Should not happen, but safety check

        # Send alert
        success = send_message(message)

        if success:
            self.throttler.record_alert(condition_key)
            self.alerted_candles[alert_key] = True  # Mark as alerted
            self.last_condition[condition_tracker_key] = current_condition  # Update last condition
            logger.info(f"Alert sent: {condition_key} - RSI={result['rsi']:.2f} (candle {open_time})")
        else:
            logger.error(f"Failed to send alert: {condition_key}")

    async def process_breakout_alerts(self, symbol: str, interval: str,
                                      current_price: float, open_time: int):
        """
        Check for breakout (current price breaking previous candle's high/low).
        Includes anti-spam protection: only alerts again after price returns to range.

        Args:
            symbol: Trading pair (e.g., BTCUSDT)
            interval: Timeframe (e.g., 1d)
            current_price: Current market price
            open_time: Current candle open_time to track if we already alerted
        """
        if not is_indicator_enabled('breakout'):
            return

        # Check if this timeframe is configured for breakouts
        breakout_timeframes = self.breakout_config.get('timeframes', [])
        if interval not in breakout_timeframes:
            return

        # Check for breakout
        margin_pct = self.breakout_config.get('margin_percent', 0.1)
        result = check_breakout(symbol, interval, current_price, open_time, margin_pct)

        # Track condition state for anti-spam
        condition_tracker_key = f"{symbol}_{interval}_BREAKOUT"
        last_breakout = self.last_condition.get(condition_tracker_key)

        if not result:
            # No breakout - price is back in range
            # Reset condition tracker (recovery detected)
            if last_breakout is not None:
                logger.debug(f"Breakout recovery detected for {symbol} {interval}: price back in range (was {last_breakout})")
                self.last_condition[condition_tracker_key] = None
            return

        current_breakout_type = result['type']

        # ANTI-SPAM LOGIC: Check if we can alert
        # Only alert if:
        # 1. Never alerted this breakout type before (last_breakout is None or different)
        # 2. OR breakout was reset (price went back to range)
        if last_breakout == current_breakout_type:
            # Same breakout as before, no recovery happened - SKIP ALERT (anti-spam)
            logger.debug(f"Anti-spam: {symbol} {interval} still in {current_breakout_type} breakout (no recovery)")
            return

        # Check if we already alerted for this specific candle + breakout type
        alert_key = f"{symbol}_{interval}_{open_time}_BREAKOUT_{current_breakout_type}"
        if alert_key in self.alerted_candles:
            # Already alerted for this breakout, skip
            return

        # Prepare alert
        condition_key = f"BREAKOUT_{current_breakout_type}_{interval}"

        # Check throttling
        can_send, reason = self.throttler.can_send_alert(condition_key)
        if not can_send:
            logger.info(f"Alert throttled: {condition_key} - {reason}")
            return

        # Generate message
        if current_breakout_type == "BULL":
            message = template_breakout_bull(result)
        else:  # BEAR
            message = template_breakout_bear(result)

        # Send alert
        success = send_message(message)

        if success:
            self.throttler.record_alert(condition_key)
            self.alerted_candles[alert_key] = True  # Mark as alerted
            self.last_condition[condition_tracker_key] = current_breakout_type  # Update last breakout
            logger.info(f"Alert sent: {condition_key} - Price={result['price']:.2f} (candle {open_time})")
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
        Process a candle (open or closed) and check all applicable rules.

        Args:
            candle_data: {"symbol": "BTCUSDT", "interval": "4h", "open_time": ...,
                          "close": ..., "is_closed": bool}
        """
        symbol = candle_data["symbol"]
        interval = candle_data["interval"]
        open_time = candle_data["open_time"]
        current_price = candle_data["close"]  # Current price = close of current candle
        is_closed = candle_data.get("is_closed", False)

        status = "CLOSED" if is_closed else "OPEN"
        logger.debug(f"Processing candle: {symbol} {interval} ({status})")

        # Check individual RSI alert for this timeframe (works on open candles too)
        await self.process_rsi_alerts(symbol, interval, open_time)

        # Check for breakout alerts (real-time price breaking previous candle high/low)
        await self.process_breakout_alerts(symbol, interval, current_price, open_time)

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
