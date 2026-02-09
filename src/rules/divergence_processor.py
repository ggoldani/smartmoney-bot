"""
Divergence detection processor.
Manages divergence state and processes divergence alerts.
Extracted from engine.py to reduce file size and improve maintainability.
"""
from typing import Dict, List
from loguru import logger

from src.config import get_symbols, get_divergence_config
from src.indicators.divergence import (
    fetch_candles_for_divergence,
    calculate_rsi_for_candles,
    is_rsi_bullish_pivot,
    is_rsi_bearish_pivot,
    detect_divergence
)
from src.notif.templates import template_divergence
from src.telegram_bot import send_message_async


class DivergenceProcessor:
    """Encapsulates divergence state tracking and detection logic."""

    def __init__(self):
        # Divergence state tracking per (symbol, interval)
        # key: "BTCUSDT_4h", value: {"bullish": [...], "bearish": [...]}
        self.divergence_state: Dict[str, Dict[str, list]] = {}

        # Anti-spam: track last divergence alert per symbol/interval/type
        self.last_divergence_alert: Dict[str, dict] = {}

    def get_state(self, symbol: str, interval: str) -> Dict[str, list]:
        """Get or create divergence state for a (symbol, interval) pair."""
        key = f"{symbol}_{interval}"
        if key not in self.divergence_state:
            self.divergence_state[key] = {"bullish": [], "bearish": []}
        return self.divergence_state[key]

    def initialize_state(self) -> None:
        """
        Scan historical candles to populate divergence state at startup.
        Detects pivots by RSI extremes (not price).
        Excludes currently open candle.

        NOTE: This is a blocking (sync) method. Call via asyncio.to_thread().
        """
        symbols = get_symbols()
        divergence_config = get_divergence_config()
        configured_timeframes = divergence_config.get('timeframes', ['4h', '1d', '1w'])
        lookback = divergence_config.get('lookback', 20)
        debug_enabled = divergence_config.get('debug_divergence', False)

        for symbol_config in symbols:
            symbol = symbol_config.get('name', 'BTCUSDT')

            for interval in configured_timeframes:
                try:
                    candles = fetch_candles_for_divergence(symbol, interval, lookback)

                    if len(candles) < 3:
                        logger.debug(f"Insufficient candles for divergence init {symbol} {interval}")
                        continue

                    if candles and not candles[-1]["is_closed"]:
                        candles = candles[:-1]

                    if len(candles) < 3:
                        continue

                    closes = [c["close"] for c in candles]
                    rsi_values = calculate_rsi_for_candles(closes)

                    state = self.get_state(symbol, interval)

                    for i in range(1, len(candles) - 1):
                        three_rsi = [rsi_values[i-1], rsi_values[i], rsi_values[i+1]]

                        if is_rsi_bullish_pivot(three_rsi):
                            state["bullish"].append({
                                "price": candles[i]["close"],
                                "rsi": three_rsi[1],
                                "open_time": candles[i]["open_time"]
                            })
                            if debug_enabled:
                                logger.debug(f"Bullish pivot found {symbol} {interval}: price={candles[i]['close']}, rsi={three_rsi[1]:.1f}")

                        if is_rsi_bearish_pivot(three_rsi):
                            state["bearish"].append({
                                "price": candles[i]["close"],
                                "rsi": three_rsi[1],
                                "open_time": candles[i]["open_time"]
                            })
                            if debug_enabled:
                                logger.debug(f"Bearish pivot found {symbol} {interval}: price={candles[i]['close']}, rsi={three_rsi[1]:.1f}")

                except Exception as e:
                    logger.error(f"Failed to initialize divergence state {symbol} {interval}: {e}")

        logger.info("Divergence state initialized for all timeframes")

    async def process(self, symbol: str, interval: str, open_time: int) -> None:
        """
        Check for divergences on configured timeframes.
        Called for each candle in the alert engine loop.

        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            interval: Timeframe (e.g., "4h", "1d", "1w")
            open_time: Current candle's open_time
        """
        divergence_config = get_divergence_config()
        if not divergence_config.get('enabled', True):
            return

        configured_timeframes = divergence_config.get('timeframes', ['4h', '1d', '1w'])
        if interval not in configured_timeframes:
            return

        try:
            lookback = divergence_config.get('lookback', 20)
            candles = fetch_candles_for_divergence(symbol, interval, lookback)

            if len(candles) < 3:
                return

            if candles and not candles[-1]["is_closed"]:
                candles = candles[:-1]

            if len(candles) < 3:
                return

            closes = [c["close"] for c in candles]
            rsi_values = calculate_rsi_for_candles(closes)

            three_candles = candles[-3:]
            three_rsi = rsi_values[-3:]

            debug_enabled = divergence_config.get('debug_divergence', False)
            bullish_rsi_max = divergence_config.get('bullish_rsi_max', 40)
            bearish_rsi_min = divergence_config.get('bearish_rsi_min', 60)

            # Filter pivots to lookback window
            if len(candles) >= lookback:
                min_open_time = candles[-lookback]["open_time"]
            else:
                min_open_time = candles[0]["open_time"] if candles else 0

            state = self.get_state(symbol, interval)
            state["bullish"] = [p for p in state["bullish"] if p["open_time"] >= min_open_time]
            state["bearish"] = [p for p in state["bearish"] if p["open_time"] >= min_open_time]

            if debug_enabled:
                logger.debug(f"Filtered pivots for {symbol} {interval}: min_open_time={min_open_time}, "
                           f"bullish_pivots={len(state['bullish'])}, "
                           f"bearish_pivots={len(state['bearish'])}")

            await self._check_type(
                "BULLISH", is_rsi_bullish_pivot, three_rsi, three_candles,
                interval, symbol, bullish_rsi_max=bullish_rsi_max, debug_enabled=debug_enabled
            )
            await self._check_type(
                "BEARISH", is_rsi_bearish_pivot, three_rsi, three_candles,
                interval, symbol, bearish_rsi_min=bearish_rsi_min, debug_enabled=debug_enabled
            )

        except Exception as e:
            logger.error(f"Failed to process divergences {symbol} {interval}: {e}")

    async def _check_type(
        self, div_type: str, pivot_fn, three_rsi: List, three_candles: List,
        interval: str, symbol: str,
        bullish_rsi_max: float = 40, bearish_rsi_min: float = 60,
        debug_enabled: bool = False
    ) -> None:
        """Check one divergence type (BULLISH or BEARISH)."""
        if not pivot_fn(three_rsi):
            return

        state_key = div_type.lower()
        state = self.get_state(symbol, interval)

        current_rsi = three_rsi[1]
        current_close = three_candles[1]["close"]
        current_open_time = three_candles[1]["open_time"]

        # Check divergence with any previous pivot
        divergence_detected = False
        for prev_pivot in state[state_key]:
            if detect_divergence(
                current_price=current_close,
                current_rsi=current_rsi,
                prev_price=prev_pivot["price"],
                prev_rsi=prev_pivot["rsi"],
                div_type=div_type,
                bullish_rsi_max=bullish_rsi_max,
                bearish_rsi_min=bearish_rsi_min
            ):
                divergence_detected = True
                break

        if divergence_detected:
            cache_key = f"{symbol}_{interval}_{div_type}"
            last = self.last_divergence_alert.get(cache_key)

            same_signal = (
                last and
                round(last["price"], 2) == round(current_close, 2) and
                round(last["rsi"], 1) == round(current_rsi, 1)
            )

            if same_signal:
                if debug_enabled:
                    logger.debug(f"Skip duplicate divergence: {cache_key} (price={current_close}, rsi={current_rsi:.1f})")
            else:
                await self._send_alert(div_type, interval, symbol, current_close, current_rsi)
                logger.info(f"{div_type} divergence detected {symbol} {interval}")
                self.last_divergence_alert[cache_key] = {"price": current_close, "rsi": current_rsi}

        # Add new pivot
        state[state_key].append({
            "price": current_close,
            "rsi": current_rsi,
            "open_time": current_open_time
        })

        if debug_enabled:
            logger.debug(f"{div_type} pivot updated {symbol} {interval}: price={current_close}, rsi={current_rsi:.1f}, "
                       f"open_time={current_open_time}, total_pivots={len(state[state_key])}")

    async def _send_alert(self, div_type: str, interval: str, symbol: str, price: float, rsi: float) -> None:
        """Send divergence alert to Telegram."""
        data = {
            "symbol": symbol,
            "interval": interval,
            "div_type": div_type,
            "price": price,
            "rsi": rsi
        }
        message = template_divergence(data)
        await send_message_async(message)
        logger.info(f"Divergence alert sent: {div_type} {interval}")
