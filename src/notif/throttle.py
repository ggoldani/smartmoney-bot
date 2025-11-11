# -*- coding: utf-8 -*-
"""
Alert throttling and circuit breaker to prevent spam.
Tracks alert history and enforces rate limits.
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class AlertHistory:
    """Tracks alert history for throttling."""
    # Deque of timestamps (newest first)
    timestamps: deque = field(default_factory=lambda: deque(maxlen=100))

    def add_alert(self, timestamp: Optional[datetime] = None):
        """Record a new alert."""
        if timestamp is None:
            timestamp = datetime.now()
        self.timestamps.append(timestamp)

    def count_in_window(self, window_minutes: int) -> int:
        """Count alerts in the last N minutes."""
        if not self.timestamps:
            return 0

        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        count = sum(1 for ts in self.timestamps if ts > cutoff)
        return count

    def count_in_last_minute(self) -> int:
        """Count alerts in the last 1 minute."""
        return self.count_in_window(1)

    def count_in_last_hour(self) -> int:
        """Count alerts in the last 60 minutes."""
        return self.count_in_window(60)


class AlertThrottler:
    """
    Manages alert rate limiting and circuit breaker.
    Thread-safe for concurrent access.
    """

    def __init__(
        self,
        max_alerts_per_hour: int = 20,
        max_alerts_per_minute: int = 5,
        circuit_breaker_enabled: bool = True
    ):
        self.max_alerts_per_hour = max_alerts_per_hour
        self.max_alerts_per_minute = max_alerts_per_minute
        self.circuit_breaker_enabled = circuit_breaker_enabled

        # Global alert history
        self.global_history = AlertHistory()

        # Per-condition history (e.g., "RSI_OVERBOUGHT_4h")
        self.condition_history: Dict[str, AlertHistory] = {}

    def can_send_alert(self, condition_key: str) -> tuple[bool, Optional[str]]:
        """
        Check if alert can be sent based on throttling rules.

        Args:
            condition_key: Unique identifier for this alert type
                          (e.g., "RSI_OVERBOUGHT_4h", "BREAKOUT_BULL_1d")

        Returns:
            (can_send: bool, reason: Optional[str])
            - (True, None) if alert can be sent
            - (False, "reason") if throttled
        """
        # Check global hourly limit
        hourly_count = self.global_history.count_in_last_hour()
        if hourly_count >= self.max_alerts_per_hour:
            logger.warning(f"Throttled: {hourly_count} alerts in last hour (max {self.max_alerts_per_hour})")
            return False, f"Limite horário atingido ({hourly_count}/{self.max_alerts_per_hour})"

        # Check global per-minute limit (circuit breaker)
        if self.circuit_breaker_enabled:
            minute_count = self.global_history.count_in_last_minute()
            if minute_count >= self.max_alerts_per_minute:
                logger.warning(f"Circuit breaker: {minute_count} alerts in last minute")
                return False, f"Circuit breaker ativado ({minute_count}/{self.max_alerts_per_minute})"

        # All checks passed
        return True, None

    def record_alert(self, condition_key: str):
        """
        Record that an alert was sent.

        Args:
            condition_key: Unique identifier for this alert type
        """
        now = datetime.now()

        # Record in global history
        self.global_history.add_alert(now)

        # Record in condition-specific history
        if condition_key not in self.condition_history:
            self.condition_history[condition_key] = AlertHistory()

        self.condition_history[condition_key].add_alert(now)

        logger.debug(f"Alert recorded: {condition_key} (hourly: {self.global_history.count_in_last_hour()})")

    def should_consolidate_alerts(self) -> bool:
        """
        Check if we should consolidate multiple alerts into one mega-alert.

        Returns:
            True if circuit breaker threshold exceeded
        """
        if not self.circuit_breaker_enabled:
            return False

        minute_count = self.global_history.count_in_last_minute()
        return minute_count >= self.max_alerts_per_minute

    def get_stats(self) -> Dict:
        """Get current throttling statistics."""
        return {
            "alerts_last_minute": self.global_history.count_in_last_minute(),
            "alerts_last_hour": self.global_history.count_in_last_hour(),
            "max_per_hour": self.max_alerts_per_hour,
            "max_per_minute": self.max_alerts_per_minute,
            "circuit_breaker_active": self.should_consolidate_alerts()
        }


# Global throttler instance (singleton)
_throttler_instance: Optional[AlertThrottler] = None


def get_throttler() -> AlertThrottler:
    """Get global alert throttler instance."""
    global _throttler_instance

    if _throttler_instance is None:
        from src.config import get_alert_config

        alert_config = get_alert_config()
        throttle_config = alert_config.get('throttling', {})
        circuit_config = alert_config.get('circuit_breaker', {})

        _throttler_instance = AlertThrottler(
            max_alerts_per_hour=throttle_config.get('max_alerts_per_hour', 20),
            max_alerts_per_minute=circuit_config.get('max_alerts_per_minute', 5),
            circuit_breaker_enabled=circuit_config.get('enabled', True)
        )

    return _throttler_instance
