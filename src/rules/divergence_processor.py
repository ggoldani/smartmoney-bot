"""
Divergence detection processor - TradingView-style pivot detection.
Manages divergence state and processes divergence alerts.

Pivot detection uses a configurable window (default 5+1+5 = 11 candles).
Price comparison uses low (bullish) / high (bearish) instead of close.
Compares only with the most recent previous pivot within a range window.
"""
from typing import Dict, Optional
from loguru import logger

from src.config import get_symbols, get_divergence_config
from src.indicators.divergence import (
    fetch_candles_for_divergence,
    calculate_rsi_for_candles,
    find_rsi_pivot_low,
    find_rsi_pivot_high,
    detect_divergence,
)
from src.notif.templates import template_divergence
from src.telegram_bot import send_message_async


class DivergenceProcessor:
    """Encapsulates divergence state tracking and detection logic (TradingView-style)."""

    def __init__(self):
        # Divergence state tracking per (symbol, interval)
        # key: "BTCUSDT_4h", value: {"bullish": [...], "bearish": [...]}
        # Each pivot: {"low", "high", "rsi", "open_time", "candle_index"}
        self.divergence_state: Dict[str, Dict[str, list]] = {}

        # Anti-spam: track last divergence alert per symbol/interval/type
        self.last_divergence_alert: Dict[str, dict] = {}

        # Track last processed pivot open_time per (symbol, interval) to avoid reprocessing
        self.last_processed_pivot: Dict[str, int] = {}

    def get_state(self, symbol: str, interval: str) -> Dict[str, list]:
        """Get or create divergence state for a (symbol, interval) pair."""
        key = f"{symbol}_{interval}"
        if key not in self.divergence_state:
            self.divergence_state[key] = {"bullish": [], "bearish": []}
        return self.divergence_state[key]

    def _get_pivot_config(self) -> dict:
        """Read pivot configuration with defaults matching TradingView."""
        divergence_config = get_divergence_config()
        return {
            "pivot_left": divergence_config.get("pivot_left", 5),
            "pivot_right": divergence_config.get("pivot_right", 5),
            "pivot_range_min": divergence_config.get("pivot_range_min", 5),
            "pivot_range_max": divergence_config.get("pivot_range_max", 60),
        }

    def initialize_state(self) -> None:
        """
        Scan historical candles to populate divergence state at startup.
        Uses TradingView-style pivot detection (configurable left/right window).
        Excludes currently open candle.

        NOTE: This is a blocking (sync) method. Call via asyncio.to_thread().
        """
        symbols = get_symbols()
        divergence_config = get_divergence_config()
        configured_timeframes = divergence_config.get("timeframes", ["4h", "1d", "1w"])
        lookback = divergence_config.get("lookback", 80)
        debug_enabled = divergence_config.get("debug_divergence", False)

        pivot_cfg = self._get_pivot_config()
        pivot_left = pivot_cfg["pivot_left"]
        pivot_right = pivot_cfg["pivot_right"]
        min_candles = pivot_left + 1 + pivot_right

        for symbol_config in symbols:
            symbol = symbol_config.get("name", "BTCUSDT")

            for interval in configured_timeframes:
                try:
                    candles = fetch_candles_for_divergence(symbol, interval, lookback)

                    if len(candles) < min_candles:
                        logger.debug(
                            f"Insufficient candles for divergence init {symbol} {interval} "
                            f"(need {min_candles}, got {len(candles)})"
                        )
                        continue

                    # Exclude open candle
                    if candles and not candles[-1]["is_closed"]:
                        candles = candles[:-1]

                    if len(candles) < min_candles:
                        continue

                    closes = [c["close"] for c in candles]
                    rsi_values = calculate_rsi_for_candles(closes)

                    state = self.get_state(symbol, interval)

                    # Scan for pivots using TradingView-style window
                    for i in range(pivot_left, len(candles) - pivot_right):
                        if find_rsi_pivot_low(rsi_values, i, pivot_left, pivot_right):
                            state["bullish"].append({
                                "low": candles[i]["low"],
                                "high": candles[i]["high"],
                                "rsi": rsi_values[i],
                                "open_time": candles[i]["open_time"],
                                "candle_index": i,
                            })
                            if debug_enabled:
                                logger.debug(
                                    f"[INIT] Bullish pivot {symbol} {interval}: "
                                    f"low={candles[i]['low']}, rsi={rsi_values[i]:.1f}, idx={i}"
                                )

                        if find_rsi_pivot_high(rsi_values, i, pivot_left, pivot_right):
                            state["bearish"].append({
                                "low": candles[i]["low"],
                                "high": candles[i]["high"],
                                "rsi": rsi_values[i],
                                "open_time": candles[i]["open_time"],
                                "candle_index": i,
                            })
                            if debug_enabled:
                                logger.debug(
                                    f"[INIT] Bearish pivot {symbol} {interval}: "
                                    f"high={candles[i]['high']}, rsi={rsi_values[i]:.1f}, idx={i}"
                                )

                    if debug_enabled:
                        logger.debug(
                            f"[INIT] {symbol} {interval}: "
                            f"bullish_pivots={len(state['bullish'])}, "
                            f"bearish_pivots={len(state['bearish'])}"
                        )

                except Exception as e:
                    logger.error(f"Failed to initialize divergence state {symbol} {interval}: {e}")

        logger.info("Divergence state initialized for all timeframes")

    async def process(self, symbol: str, interval: str, open_time: int) -> None:
        """
        Check for divergences on configured timeframes.
        Called for each candle in the alert engine loop.

        The pivot candidate is at candles[-(pivot_right + 1)], confirmed by having
        pivot_right closed candles to its right. This matches TradingView's delayed
        confirmation behavior.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Timeframe (e.g., "4h", "1d", "1w")
            open_time: Current candle's open_time
        """
        divergence_config = get_divergence_config()
        if not divergence_config.get("enabled", True):
            return

        configured_timeframes = divergence_config.get("timeframes", ["4h", "1d", "1w"])
        if interval not in configured_timeframes:
            return

        try:
            lookback = divergence_config.get("lookback", 80)
            debug_enabled = divergence_config.get("debug_divergence", False)
            bullish_rsi_max = divergence_config.get("bullish_rsi_max", 40)
            bearish_rsi_min = divergence_config.get("bearish_rsi_min", 60)

            pivot_cfg = self._get_pivot_config()
            pivot_left = pivot_cfg["pivot_left"]
            pivot_right = pivot_cfg["pivot_right"]
            pivot_range_min = pivot_cfg["pivot_range_min"]
            pivot_range_max = pivot_cfg["pivot_range_max"]
            min_candles = pivot_left + 1 + pivot_right

            candles = fetch_candles_for_divergence(symbol, interval, lookback)

            if len(candles) < min_candles:
                return

            # Exclude open candle
            if candles and not candles[-1]["is_closed"]:
                candles = candles[:-1]

            if len(candles) < min_candles:
                return

            closes = [c["close"] for c in candles]
            rsi_values = calculate_rsi_for_candles(closes)

            # The pivot candidate: confirmed by having pivot_right candles to the right
            center_idx = len(candles) - pivot_right - 1
            if center_idx < pivot_left:
                return

            center_candle = candles[center_idx]
            center_open_time = center_candle["open_time"]

            # Skip if this pivot position was already processed
            process_key = f"{symbol}_{interval}"
            if self.last_processed_pivot.get(process_key) == center_open_time:
                return
            self.last_processed_pivot[process_key] = center_open_time

            state = self.get_state(symbol, interval)

            # Check bullish pivot (RSI low)
            if find_rsi_pivot_low(rsi_values, center_idx, pivot_left, pivot_right):
                await self._check_divergence(
                    div_type="BULLISH",
                    state_key="bullish",
                    state=state,
                    candle=center_candle,
                    rsi=rsi_values[center_idx],
                    candle_index=center_idx,
                    symbol=symbol,
                    interval=interval,
                    pivot_range_min=pivot_range_min,
                    pivot_range_max=pivot_range_max,
                    bullish_rsi_max=bullish_rsi_max,
                    bearish_rsi_min=bearish_rsi_min,
                    debug_enabled=debug_enabled,
                )

            # Check bearish pivot (RSI high)
            if find_rsi_pivot_high(rsi_values, center_idx, pivot_left, pivot_right):
                await self._check_divergence(
                    div_type="BEARISH",
                    state_key="bearish",
                    state=state,
                    candle=center_candle,
                    rsi=rsi_values[center_idx],
                    candle_index=center_idx,
                    symbol=symbol,
                    interval=interval,
                    pivot_range_min=pivot_range_min,
                    pivot_range_max=pivot_range_max,
                    bullish_rsi_max=bullish_rsi_max,
                    bearish_rsi_min=bearish_rsi_min,
                    debug_enabled=debug_enabled,
                )

        except Exception as e:
            logger.error(f"Failed to process divergences {symbol} {interval}: {e}")

    async def _check_divergence(
        self,
        div_type: str,
        state_key: str,
        state: Dict[str, list],
        candle: dict,
        rsi: Optional[float],
        candle_index: int,
        symbol: str,
        interval: str,
        pivot_range_min: int,
        pivot_range_max: int,
        bullish_rsi_max: float = 40,
        bearish_rsi_min: float = 60,
        debug_enabled: bool = False,
    ) -> None:
        """
        Check one divergence type (BULLISH or BEARISH).

        Compares the current pivot ONLY with the most recent previous pivot,
        checking that the distance is within [pivot_range_min, pivot_range_max].
        Uses low (bullish) or high (bearish) for price comparison.
        """
        if rsi is None:
            return

        # Price to compare: low for bullish, high for bearish (TradingView-style)
        current_price = candle["low"] if div_type == "BULLISH" else candle["high"]

        # Compare only with the most recent previous pivot (TradingView's ta.valuewhen)
        prev_pivots = state[state_key]
        divergence_detected = False

        if prev_pivots:
            prev = prev_pivots[-1]
            bars_between = candle_index - prev["candle_index"]

            if pivot_range_min <= bars_between <= pivot_range_max:
                prev_price = prev["low"] if div_type == "BULLISH" else prev["high"]
                result = detect_divergence(
                    current_price=current_price,
                    current_rsi=rsi,
                    prev_price=prev_price,
                    prev_rsi=prev["rsi"],
                    div_type=div_type,
                    bullish_rsi_max=bullish_rsi_max,
                    bearish_rsi_min=bearish_rsi_min,
                )
                if result:
                    divergence_detected = True
                    if debug_enabled:
                        logger.debug(
                            f"[DIVERGENCE] {div_type} {symbol} {interval}: "
                            f"current(price={current_price}, rsi={rsi:.1f}, idx={candle_index}) vs "
                            f"prev(price={prev_price}, rsi={prev['rsi']:.1f}, idx={prev['candle_index']}), "
                            f"bars_between={bars_between}"
                        )
            elif debug_enabled:
                logger.debug(
                    f"[RANGE] {div_type} pivot {symbol} {interval}: "
                    f"bars_between={bars_between} outside [{pivot_range_min}, {pivot_range_max}]"
                )

        # Send alert if divergence detected (with anti-spam)
        if divergence_detected:
            cache_key = f"{symbol}_{interval}_{div_type}"
            last = self.last_divergence_alert.get(cache_key)

            same_signal = (
                last
                and round(last["price"], 2) == round(current_price, 2)
                and round(last["rsi"], 1) == round(rsi, 1)
            )

            if same_signal:
                if debug_enabled:
                    logger.debug(
                        f"Skip duplicate divergence: {cache_key} "
                        f"(price={current_price}, rsi={rsi:.1f})"
                    )
            else:
                await self._send_alert(div_type, interval, symbol, current_price, rsi)
                logger.info(f"{div_type} divergence detected {symbol} {interval}")
                self.last_divergence_alert[cache_key] = {"price": current_price, "rsi": rsi}

        # Add new pivot to state
        state[state_key].append({
            "low": candle["low"],
            "high": candle["high"],
            "rsi": rsi,
            "open_time": candle["open_time"],
            "candle_index": candle_index,
        })

        if debug_enabled:
            logger.debug(
                f"[PIVOT] {div_type} pivot added {symbol} {interval}: "
                f"low={candle['low']}, high={candle['high']}, rsi={rsi:.1f}, "
                f"idx={candle_index}, total_pivots={len(state[state_key])}"
            )

    async def _send_alert(
        self, div_type: str, interval: str, symbol: str, price: float, rsi: float
    ) -> None:
        """Send divergence alert to Telegram."""
        data = {
            "symbol": symbol,
            "interval": interval,
            "div_type": div_type,
            "price": price,
            "rsi": rsi,
        }
        message = template_divergence(data)
        await send_message_async(message)
        logger.info(f"Divergence alert sent: {div_type} {interval}")
