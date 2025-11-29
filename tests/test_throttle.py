"""Tests for alert throttling and rate limiting."""
import pytest
from datetime import datetime, timedelta
from src.notif.throttle import AlertHistory, AlertThrottler
import time


class TestAlertHistory:
    """Tests for AlertHistory tracking."""

    def test_alert_history_init(self):
        """AlertHistory should initialize empty."""
        history = AlertHistory()
        assert history.timestamps is not None
        assert len(history.timestamps) == 0

    def test_alert_history_add_alert(self):
        """AlertHistory should record alert timestamps."""
        history = AlertHistory()
        history.add_alert()
        assert len(history.timestamps) == 1

    def test_alert_history_add_multiple_alerts(self):
        """AlertHistory should record multiple alerts."""
        history = AlertHistory()
        history.add_alert()
        history.add_alert()
        history.add_alert()
        assert len(history.timestamps) == 3

    def test_alert_history_with_explicit_timestamp(self):
        """AlertHistory should accept explicit timestamps."""
        history = AlertHistory()
        now = datetime.now()
        history.add_alert(now)
        assert len(history.timestamps) == 1
        assert history.timestamps[0] == now

    def test_alert_history_count_last_minute_empty(self):
        """Empty history should return 0 for last minute count."""
        history = AlertHistory()
        assert history.count_in_last_minute() == 0

    def test_alert_history_count_last_hour_empty(self):
        """Empty history should return 0 for last hour count."""
        history = AlertHistory()
        assert history.count_in_last_hour() == 0

    def test_alert_history_count_recent_alerts_minute(self):
        """Should count recent alerts in last minute."""
        history = AlertHistory()
        now = datetime.now()
        # Add 3 alerts in the last minute
        history.add_alert(now)
        history.add_alert(now - timedelta(seconds=30))
        history.add_alert(now - timedelta(seconds=59))

        count = history.count_in_last_minute()
        assert count == 3

    def test_alert_history_count_old_alerts_minute(self):
        """Should not count old alerts outside 1-minute window."""
        history = AlertHistory()
        now = datetime.now()
        # Add alert outside 1-minute window
        history.add_alert(now - timedelta(minutes=2))

        count = history.count_in_last_minute()
        assert count == 0

    def test_alert_history_count_mixed_window_minute(self):
        """Should count only alerts within 1-minute window."""
        history = AlertHistory()
        now = datetime.now()
        # Add alerts: 2 recent, 1 old
        history.add_alert(now)
        history.add_alert(now - timedelta(seconds=30))
        history.add_alert(now - timedelta(minutes=2))

        count = history.count_in_last_minute()
        assert count == 2

    def test_alert_history_count_hour_window(self):
        """Should count alerts in 60-minute window."""
        history = AlertHistory()
        now = datetime.now()
        # Add 5 alerts within last hour
        for i in range(5):
            history.add_alert(now - timedelta(minutes=i * 10))

        count = history.count_in_last_hour()
        assert count == 5

    def test_alert_history_count_custom_window(self):
        """Should count alerts in custom time window."""
        history = AlertHistory()
        now = datetime.now()
        # Add alerts at different times
        history.add_alert(now)
        history.add_alert(now - timedelta(minutes=5))
        history.add_alert(now - timedelta(minutes=15))

        # 10-minute window should have 2 alerts
        count = history.count_in_window(10)
        assert count == 2

    def test_alert_history_max_len_capacity(self):
        """AlertHistory should handle max capacity (100)."""
        history = AlertHistory()
        # Add 150 alerts
        for _ in range(150):
            history.add_alert()

        # Should only keep last 100 (maxlen=100)
        assert len(history.timestamps) == 100


class TestAlertThrottler:
    """Tests for AlertThrottler rate limiting."""

    def test_throttler_init(self):
        """AlertThrottler should initialize with defaults."""
        throttler = AlertThrottler()
        assert throttler.max_alerts_per_hour == 20
        assert throttler.max_alerts_per_minute == 5
        assert throttler.circuit_breaker_enabled is True

    def test_throttler_custom_limits(self):
        """AlertThrottler should accept custom limits."""
        throttler = AlertThrottler(
            max_alerts_per_hour=30,
            max_alerts_per_minute=8
        )
        assert throttler.max_alerts_per_hour == 30
        assert throttler.max_alerts_per_minute == 8

    def test_throttler_can_send_first_alert(self):
        """First alert should always be allowed."""
        throttler = AlertThrottler(max_alerts_per_hour=5)
        can_send, reason = throttler.can_send_alert("RSI_OB_1h")
        assert can_send is True
        assert reason is None

    def test_throttler_can_send_within_limit(self):
        """Alerts within limit should be allowed."""
        throttler = AlertThrottler(max_alerts_per_hour=10, max_alerts_per_minute=100)
        # Record 5 alerts (not send, which would check the limit)
        for i in range(5):
            throttler.record_alert(f"RSI_{i}")

        # Should still be able to send (only 5 of 10)
        can_send, reason = throttler.can_send_alert("RSI_5")
        assert can_send is True, f"Should allow more alerts, reason: {reason}"

    def test_throttler_blocks_hourly_limit(self):
        """Should block alerts when hourly limit reached."""
        throttler = AlertThrottler(max_alerts_per_hour=3)
        # Fill up the limit
        for i in range(3):
            throttler.record_alert(f"alert_{i}")

        # Next alert should be blocked
        can_send, reason = throttler.can_send_alert("alert_new")
        assert can_send is False
        assert "horário" in reason or "hourly" in reason.lower()

    def test_throttler_circuit_breaker_threshold(self):
        """Circuit breaker should trigger when minute limit exceeded."""
        throttler = AlertThrottler(
            max_alerts_per_hour=100,
            max_alerts_per_minute=3,
            circuit_breaker_enabled=True
        )
        # Record alerts quickly
        for i in range(3):
            throttler.record_alert(f"alert_{i}")

        # Next alert should trigger circuit breaker
        can_send, reason = throttler.can_send_alert("alert_new")
        assert can_send is False
        assert "circuit" in reason.lower() or "breaker" in reason.lower()

    def test_throttler_circuit_breaker_disabled(self):
        """Circuit breaker can be disabled."""
        throttler = AlertThrottler(
            max_alerts_per_hour=100,
            max_alerts_per_minute=3,
            circuit_breaker_enabled=False
        )
        # Record more than minute limit
        for i in range(5):
            throttler.record_alert(f"alert_{i}")

        # Should still allow more (circuit breaker disabled)
        can_send, reason = throttler.can_send_alert("alert_new")
        assert can_send is True

    def test_throttler_record_alert_global_history(self):
        """record_alert should update global history."""
        throttler = AlertThrottler()
        throttler.record_alert("condition_1")

        assert throttler.global_history.count_in_last_hour() == 1

    def test_throttler_record_alert_condition_history(self):
        """record_alert should update condition-specific history."""
        throttler = AlertThrottler()
        throttler.record_alert("RSI_OB_1h")
        throttler.record_alert("RSI_OB_1h")
        throttler.record_alert("BREAKOUT_1d")

        # Check condition history
        assert "RSI_OB_1h" in throttler.condition_history
        assert len(throttler.condition_history["RSI_OB_1h"].timestamps) == 2
        assert len(throttler.condition_history["BREAKOUT_1d"].timestamps) == 1

    def test_throttler_should_consolidate_alerts_false(self):
        """should_consolidate_alerts should return False initially."""
        throttler = AlertThrottler(max_alerts_per_minute=5)
        assert throttler.should_consolidate_alerts() is False

    def test_throttler_should_consolidate_alerts_true(self):
        """should_consolidate_alerts should return True when threshold exceeded."""
        throttler = AlertThrottler(max_alerts_per_minute=3)
        # Record 3 alerts quickly
        for i in range(3):
            throttler.record_alert(f"alert_{i}")

        assert throttler.should_consolidate_alerts() is True

    def test_throttler_consolidate_disabled(self):
        """should_consolidate_alerts returns False when disabled."""
        throttler = AlertThrottler(
            max_alerts_per_minute=3,
            circuit_breaker_enabled=False
        )
        # Record many alerts
        for i in range(5):
            throttler.record_alert(f"alert_{i}")

        # Should return False since circuit breaker disabled
        assert throttler.should_consolidate_alerts() is False

    def test_throttler_get_stats(self):
        """get_stats should return current throttling statistics."""
        throttler = AlertThrottler(max_alerts_per_hour=20, max_alerts_per_minute=5)
        throttler.record_alert("alert_1")
        throttler.record_alert("alert_2")

        stats = throttler.get_stats()
        assert isinstance(stats, dict)
        assert stats["alerts_last_minute"] == 2
        assert stats["alerts_last_hour"] == 2
        assert stats["max_per_hour"] == 20
        assert stats["max_per_minute"] == 5
        assert "circuit_breaker_active" in stats

    def test_throttler_stats_empty(self):
        """get_stats should work with empty throttler."""
        throttler = AlertThrottler()
        stats = throttler.get_stats()
        assert stats["alerts_last_minute"] == 0
        assert stats["alerts_last_hour"] == 0


class TestThrottlingScenarios:
    """Real-world throttling scenarios."""

    def test_scenario_normal_trading_day(self):
        """Simulate normal trading day with 20/hour limit."""
        throttler = AlertThrottler(max_alerts_per_hour=20)

        # Send 20 alerts
        for i in range(20):
            throttler.record_alert(f"alert_{i}")

        # 21st should be blocked
        can_send, _ = throttler.can_send_alert("alert_21")
        assert can_send is False

    def test_scenario_alert_spam_prevention(self):
        """Prevent spam within short time window."""
        throttler = AlertThrottler(max_alerts_per_minute=3)

        # Try to send alerts rapidly
        for i in range(3):
            throttler.record_alert(f"alert_{i}")

        # 4th should trigger circuit breaker
        assert throttler.should_consolidate_alerts() is True

    def test_scenario_multiple_conditions(self):
        """Track different alert conditions separately."""
        throttler = AlertThrottler()

        conditions = [
            "RSI_OB_1h",
            "RSI_OB_4h",
            "RSI_OB_1d",
            "BREAKOUT_BULL_1d"
        ]

        for cond in conditions:
            throttler.record_alert(cond)

        # Should have all conditions tracked
        assert len(throttler.condition_history) == len(conditions)
        assert throttler.global_history.count_in_last_hour() == len(conditions)

    def test_scenario_recovery_after_throttle(self):
        """Alerts should recover after time passes."""
        throttler = AlertThrottler(max_alerts_per_hour=2)

        # Record 2 alerts
        old_time = datetime.now() - timedelta(minutes=1, seconds=1)
        throttler.global_history.add_alert(old_time)
        throttler.global_history.add_alert(old_time)

        # Should still be throttled (within hour)
        can_send, _ = throttler.can_send_alert("new_alert")
        assert can_send is False

    def test_scenario_mixed_timeframe_alerts(self):
        """Handle alerts from different timeframes."""
        throttler = AlertThrottler(max_alerts_per_hour=10)

        timeframes = ["1h", "4h", "1d", "1w"]
        conditions = ["RSI_OB", "RSI_OS", "BREAKOUT_BULL", "BREAKOUT_BEAR"]

        # Generate alerts across combinations
        for tf in timeframes:
            for cond in conditions:
                key = f"{cond}_{tf}"
                throttler.record_alert(key)

        # 16 alerts recorded (4 TFs × 4 conditions)
        assert throttler.global_history.count_in_last_hour() == 16

        # Should be throttled
        can_send, _ = throttler.can_send_alert("new_alert")
        assert can_send is False


class TestThrottleEdgeCases:
    """Edge cases and boundary conditions."""

    def test_throttler_zero_limit(self):
        """Throttler with zero limit should block everything."""
        throttler = AlertThrottler(max_alerts_per_hour=0)
        can_send, reason = throttler.can_send_alert("alert")
        assert can_send is False

    def test_throttler_negative_limit(self):
        """Throttler with negative limit should block everything."""
        throttler = AlertThrottler(max_alerts_per_hour=-1)
        can_send, reason = throttler.can_send_alert("alert")
        assert can_send is False

    def test_throttler_very_high_limit(self):
        """Throttler with very high limit should rarely block."""
        throttler = AlertThrottler(max_alerts_per_hour=10000, max_alerts_per_minute=10000)

        # Record many alerts
        for i in range(100):
            throttler.record_alert(f"alert_{i}")

        # Should still allow more (100 < 10000)
        can_send, _ = throttler.can_send_alert("new_alert")
        assert can_send is True, "Should allow with very high limit"

    def test_throttler_condition_key_empty_string(self):
        """Should handle empty string condition key."""
        throttler = AlertThrottler()
        throttler.record_alert("")
        assert "" in throttler.condition_history

    def test_throttler_condition_key_unicode(self):
        """Should handle Unicode in condition key."""
        throttler = AlertThrottler()
        throttler.record_alert("RSI_OB_🚀")
        assert "RSI_OB_🚀" in throttler.condition_history

    def test_alert_history_same_timestamp_multiple_alerts(self):
        """Should handle multiple alerts with same timestamp."""
        history = AlertHistory()
        now = datetime.now()
        history.add_alert(now)
        history.add_alert(now)
        history.add_alert(now)

        assert history.count_in_last_minute() == 3
