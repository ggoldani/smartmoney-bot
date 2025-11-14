"""
Alert Rules Engine - monitors candles and triggers alerts.
This is the core of the bot's alerting system.
"""
import asyncio
import time
from typing import List, Dict, Set, Optional, TypedDict
from loguru import logger


class CandleData(TypedDict):
    """Candle data structure passed to process_candle."""
    symbol: str
    interval: str
    open_time: int
    close: float
    is_closed: bool

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
    template_mega_alert
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

        # Consolidation: collect alerts in 6s window, send batched
        self.pending_alerts: List[Dict] = []
        self.consolidation_interval = 6.0  # seconds

        # Track timestamp of alerted candles for TTL cleanup (prevent unbounded growth)
        self.alerted_candles_with_timestamp: Dict[str, float] = {}  # key: alert_key, value: timestamp

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

        if not symbols:
            logger.warning("No symbols configured in alert engine")
            return []

        candles_to_process = []

        with SessionLocal() as session:
            for sym_config in symbols:
                symbol = sym_config["name"]
                timeframes = sym_config["timeframes"]

                if not timeframes:
                    logger.warning(f"No timeframes configured for symbol {symbol}")
                    continue

                for interval in timeframes:
                    key = self._get_candle_key(symbol, interval)
                    last_open_time = self.last_processed.get(key, None)

                    # Query for the LATEST candle (whether open or closed)
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

                    # Process if:
                    # 1. New candle (open_time > last_processed) OR
                    # 2. Current open candle being updated (open_time == last_processed AND is_closed=False)
                    is_new_candle = candle.open_time > last_open_time
                    is_open_candle_update = (candle.open_time == last_open_time and not candle.is_closed)

                    if is_new_candle or is_open_candle_update:
                        candles_to_process.append({
                            "symbol": candle.symbol,
                            "interval": candle.interval,
                            "open_time": candle.open_time,
                            "close": candle.close,
                            "is_closed": candle.is_closed
                        })

                        # Only update last_processed and clear alerts if it's a NEW candle
                        if is_new_candle:
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

    def _get_rsi_template(self, condition: str):
        """Return template function for RSI condition"""
        if condition == "EXTREME_OVERBOUGHT":
            return template_rsi_extreme_overbought
        elif condition == "EXTREME_OVERSOLD":
            return template_rsi_extreme_oversold
        elif condition == "OVERBOUGHT":
            return template_rsi_overbought
        elif condition == "OVERSOLD":
            return template_rsi_oversold
        return None

    def _get_breakout_template(self, breakout_type: str):
        """Return template function for breakout type"""
        return template_breakout_bull if breakout_type == "BULL" else template_breakout_bear

    def _is_repeated_condition(self, tracker_key: str, current_condition: str) -> bool:
        """Check if condition hasn't changed since last alert (anti-spam)."""
        last_condition = self.last_condition.get(tracker_key)
        if last_condition is not None and last_condition == current_condition:
            return True
        return False

    def _check_throttle_and_mark(self, condition_key: str, alert_key: str) -> bool:
        """
        Check if alert is throttled and mark as alerted if so.
        Returns True if can send, False if throttled.
        """
        can_send, reason = self.throttler.can_send_alert(condition_key)
        if not can_send:
            logger.info(f"Alert throttled: {condition_key}")
            # Mark as alerted to prevent retry on next cycle
            self.alerted_candles[alert_key] = True
            self.alerted_candles_with_timestamp[alert_key] = time.time()
            return False
        return True

    def _collect_single_alert(self, alert_type: str, condition: str, symbol: str,
                             interval: str, open_time: int, result: Dict,
                             tracker_key: str, condition_key: str,
                             template_func) -> None:
        """
        Collect single alert to pending queue.
        Alert dict includes type-specific fields from result.
        """
        alert_key = f"{symbol}_{interval}_{open_time}_{condition}"

        # Mark as alerted IMMEDIATELY to prevent reprocessing
        self.alerted_candles[alert_key] = True
        self.alerted_candles_with_timestamp[alert_key] = time.time()

        # Build alert dict with common fields
        alert_dict = {
            'type': alert_type,
            'condition': condition,
            'symbol': symbol,
            'interval': interval,
            'open_time': open_time,
            'alert_key': alert_key,
            'condition_key': condition_key,
            'tracker_key': tracker_key,
            'template_func': template_func,
        }

        # Add type-specific fields from result
        if alert_type == 'RSI':
            alert_dict['rsi'] = result.get('rsi')
            alert_dict['price'] = result.get('price')
        elif alert_type == 'BREAKOUT':
            alert_dict['price'] = result.get('price')
            alert_dict['prev_high'] = result.get('prev_high')
            alert_dict['prev_low'] = result.get('prev_low')
            alert_dict['change_pct'] = result.get('change_pct')

        self.pending_alerts.append(alert_dict)

    def _collect_rsi_alert(self, symbol: str, interval: str, open_time: int):
        """
        Check RSI and collect alert if valid (doesn't send, just validates).
        Returns alert dict if should be sent, None otherwise.
        """
        if not is_indicator_enabled('rsi'):
            return

        rsi_timeframes = self.rsi_config.get('timeframes', [])
        if interval not in rsi_timeframes:
            return

        period = self.rsi_config.get('period', 14)
        overbought = self.rsi_config.get('overbought', 70)
        oversold = self.rsi_config.get('oversold', 30)

        result = analyze_rsi(symbol, interval, overbought, oversold, period)
        if not result:
            return

        # Validate required keys in result
        required_keys = {'rsi', 'condition', 'price'}
        if not all(k in result for k in required_keys):
            logger.warning(f"RSI result missing required keys. Expected {required_keys}, got {set(result.keys())}")
            return

        condition_tracker_key = f"{symbol}_{interval}_RSI"
        current_condition = result["condition"]
        current_rsi = result["rsi"]
        last_condition = self.last_condition.get(condition_tracker_key)

        # Load recovery zone from config (prevents spam on reversals)
        recovery_config = self.rsi_config.get('recovery_zone', {})
        recovery_lower = recovery_config.get('lower', 35)  # Safe default
        recovery_upper = recovery_config.get('upper', 65)  # Safe default

        if recovery_lower < current_rsi < recovery_upper:
            if last_condition is not None:
                logger.debug(f"RSI recovery: {symbol} {interval} RSI={current_rsi:.2f}")
                self.last_condition[condition_tracker_key] = None
            return

        if current_condition == "NORMAL":
            return

        # ANTI-SPAM: Same condition persists = skip
        if self._is_repeated_condition(condition_tracker_key, current_condition):
            logger.debug(f"Anti-spam: {symbol} {interval} still {current_condition}")
            return

        # Already alerted for this candle
        alert_key = f"{symbol}_{interval}_{open_time}_{current_condition}"
        if alert_key in self.alerted_candles:
            return

        # Check throttle (and mark as alerted if throttled)
        condition_key = f"RSI_{current_condition}_{interval}"
        if not self._check_throttle_and_mark(condition_key, alert_key):
            return

        # Collect alert using helper (marks as alerted and adds to pending queue)
        self._collect_single_alert(
            alert_type='RSI',
            condition=current_condition,
            symbol=symbol,
            interval=interval,
            open_time=open_time,
            result=result,
            tracker_key=condition_tracker_key,
            condition_key=condition_key,
            template_func=self._get_rsi_template(current_condition)
        )

    def _collect_breakout_alert(self, symbol: str, interval: str,
                               current_price: float, open_time: int):
        """
        Check for breakout and collect alert if valid (doesn't send).
        """
        if not is_indicator_enabled('breakout'):
            return

        breakout_timeframes = self.breakout_config.get('timeframes', [])
        if interval not in breakout_timeframes:
            return

        margin_pct = self.breakout_config.get('margin_percent', 0.1)
        result = check_breakout(symbol, interval, current_price, open_time, margin_pct)

        if not result:
            # Price back in range = recovery
            condition_tracker_key = f"{symbol}_{interval}_BREAKOUT"
            last_breakout = self.last_condition.get(condition_tracker_key)
            if last_breakout is not None:
                logger.debug(f"Breakout recovery: {symbol} {interval}")
                self.last_condition[condition_tracker_key] = None
            return

        # Validate required keys in result
        required_keys = {'type', 'price', 'change_pct'}
        if not all(k in result for k in required_keys):
            logger.warning(f"Breakout result missing required keys. Expected {required_keys}, got {set(result.keys())}")
            return

        # Validate type-specific keys
        breakout_type = result['type']
        if breakout_type == 'BULL' and 'prev_high' not in result:
            logger.warning(f"BULL breakout missing prev_high. Got {set(result.keys())}")
            return
        if breakout_type == 'BEAR' and 'prev_low' not in result:
            logger.warning(f"BEAR breakout missing prev_low. Got {set(result.keys())}")
            return

        condition_tracker_key = f"{symbol}_{interval}_BREAKOUT"
        last_breakout = self.last_condition.get(condition_tracker_key)

        current_breakout_type = result['type']

        # ANTI-SPAM: Same breakout persists = skip
        if last_breakout == current_breakout_type:
            logger.debug(f"Anti-spam: {symbol} {interval} still {current_breakout_type}")
            return

        # Already alerted for this candle
        alert_key = f"{symbol}_{interval}_{open_time}_BREAKOUT_{current_breakout_type}"
        if alert_key in self.alerted_candles:
            return

        # Check throttle (and mark as alerted if throttled)
        condition_key = f"BREAKOUT_{current_breakout_type}_{interval}"
        if not self._check_throttle_and_mark(condition_key, alert_key):
            return

        # Collect alert using helper (marks as alerted and adds to pending queue)
        self._collect_single_alert(
            alert_type='BREAKOUT',
            condition=current_breakout_type,
            symbol=symbol,
            interval=interval,
            open_time=open_time,
            result=result,
            tracker_key=condition_tracker_key,
            condition_key=condition_key,
            template_func=self._get_breakout_template(current_breakout_type)
        )

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

    async def process_candle(self, candle_data: CandleData):
        """
        Process a candle: collect alerts (don't send yet).
        """
        symbol = candle_data["symbol"]
        interval = candle_data["interval"]
        open_time = candle_data["open_time"]
        current_price = candle_data["close"]

        logger.debug(f"Processing candle: {symbol} {interval}")

        # Collect RSI alerts
        self._collect_rsi_alert(symbol, interval, open_time)

        # Collect breakout alerts
        self._collect_breakout_alert(symbol, interval, current_price, open_time)

    async def _consolidation_timer(self):
        """Timer: send consolidated alerts every 6 seconds and cleanup old alert entries"""
        cleanup_counter = 0
        while self.running:
            await asyncio.sleep(self.consolidation_interval)
            self._send_consolidated_alerts()

            # Cleanup old alert entries every 10 cycles (60 seconds)
            cleanup_counter += 1
            if cleanup_counter >= 10:
                self._cleanup_old_alert_entries()
                self._cleanup_stale_conditions()
                cleanup_counter = 0

    def _cleanup_old_alert_entries(self):
        """Remove alert entries older than 1 hour to prevent unbounded dict growth"""
        current_time = time.time()
        ttl_seconds = 3600  # 1 hour

        keys_to_remove = []
        for alert_key, timestamp in self.alerted_candles_with_timestamp.items():
            if current_time - timestamp > ttl_seconds:
                keys_to_remove.append(alert_key)

        # Remove from both dicts
        removed_count = 0
        for key in keys_to_remove:
            self.alerted_candles.pop(key, None)
            self.alerted_candles_with_timestamp.pop(key, None)
            removed_count += 1

        if removed_count > 0:
            logger.debug(f"Cleaned up {removed_count} old alert entries (TTL 1h)")

    def _cleanup_stale_conditions(self):
        """Remove condition tracking for symbols/timeframes no longer in config"""
        current_symbols = {s['name'] for s in get_symbols()}
        all_timeframes = set()
        for sym in get_symbols():
            all_timeframes.update(sym['timeframes'])

        keys_to_remove = []
        for key in list(self.last_condition.keys()):
            # key format: "SYMBOL_TF_RSI" or "SYMBOL_TF_BREAKOUT"
            parts = key.rsplit('_', 1)  # Split from right to get symbol_tf and type
            if len(parts) == 2:
                symbol_tf, condition_type = parts
                symbol_parts = symbol_tf.rsplit('_', 1)  # Extract symbol and tf
                if len(symbol_parts) == 2:
                    symbol, tf = symbol_parts
                    # If symbol not in config, mark for removal
                    if symbol not in current_symbols or tf not in all_timeframes:
                        keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.last_condition[key]

        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} stale condition entries")

    def _send_consolidated_alerts(self):
        """Send pending alerts: single or mega-alert"""
        if not self.pending_alerts:
            return

        # Check hourly throttle (global)
        hourly_count = self.throttler.global_history.count_in_last_hour()
        if hourly_count >= self.throttler.max_alerts_per_hour:
            logger.warning(f"Hourly limit reached ({hourly_count}), discarding {len(self.pending_alerts)} pending")
            # Clear alerted_candles for discarded alerts (allow retry later if limit resets)
            for alert in self.pending_alerts:
                self.alerted_candles.pop(alert['alert_key'], None)
                self.alerted_candles_with_timestamp.pop(alert['alert_key'], None)
            self.pending_alerts = []
            return

        # Save alerts before sending
        alerts_to_send = self.pending_alerts[:]
        self.pending_alerts = []

        # Send FIRST (state updated AFTER success inside send functions)
        if len(alerts_to_send) == 1:
            self._send_single_alert(alerts_to_send[0])
        else:
            self._send_mega_alert(alerts_to_send)

    def _send_single_alert(self, alert: Dict) -> bool:
        """Send single alert. Returns True if successful."""
        try:
            template = alert['template_func'](alert)
        except Exception as e:
            logger.error(f"Template generation failed for {alert['type']} {alert.get('condition')}: {e}")
            # Template failed: remove from alerted_candles to allow retry
            self.alerted_candles.pop(alert['alert_key'], None)
            self.alerted_candles_with_timestamp.pop(alert['alert_key'], None)
            return False

        success = send_message(template)

        if success:
            # Update state AFTER successful send
            self.throttler.record_alert(alert['condition_key'])
            self.last_condition[alert['tracker_key']] = alert['condition']
            logger.info(f"Alert sent: {alert['type']} {alert['condition']}")
        else:
            # Send failed: remove from alerted_candles to allow retry
            logger.error(f"Failed to send alert: {alert['type']} {alert['condition']}")
            self.alerted_candles.pop(alert['alert_key'], None)
            self.alerted_candles_with_timestamp.pop(alert['alert_key'], None)

        return success

    def _send_mega_alert(self, alerts: List[Dict]) -> bool:
        """Send consolidated mega-alert. Returns True if successful."""
        message = template_mega_alert(alerts)
        success = send_message(message)

        if success:
            # Update state AFTER successful send
            for alert in alerts:
                self.throttler.record_alert(alert['condition_key'])
                self.last_condition[alert['tracker_key']] = alert['condition']
            logger.info(f"Mega-alert sent: {len(alerts)} alerts consolidated")
        else:
            # Send failed: remove all from alerted_candles to allow retry
            logger.error(f"Failed to send mega-alert with {len(alerts)} alerts")
            for alert in alerts:
                self.alerted_candles.pop(alert['alert_key'], None)
                self.alerted_candles_with_timestamp.pop(alert['alert_key'], None)

        return success

    async def run(self):
        """Main loop: check candles + consolidation timer"""
        self.running = True
        logger.info("Alert Engine started")

        # Start consolidation timer
        consolidation_task = asyncio.create_task(self._consolidation_timer())
        checked_multi_tf: Set[str] = set()

        try:
            while self.running:
                try:
                    new_candles = await self.check_for_new_candles()

                    if new_candles:
                        for candle in new_candles:
                            await self.process_candle(candle)
                            checked_multi_tf.add(candle["symbol"])

                        # Multi-TF check (copy set to avoid race condition)
                        symbols_to_check = checked_multi_tf.copy()
                        checked_multi_tf.clear()

                        for symbol in symbols_to_check:
                            await self.check_multi_tf_consolidation(symbol)

                    await asyncio.sleep(self.check_interval)

                except Exception as e:
                    logger.exception(f"Error in alert engine loop: {e}")
                    await asyncio.sleep(self.check_interval)

        finally:
            consolidation_task.cancel()
            try:
                await consolidation_task
            except asyncio.CancelledError:
                pass

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
