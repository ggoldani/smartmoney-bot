import time
import asyncio
from src.rules.engine import AlertEngine
from src.config import get_symbols

def setup_engine():
    engine = AlertEngine()

    # Populate last_condition with dummy data to measure performance
    # of the new tuple-based cleanup
    for i in range(100000):
        engine.last_condition[(f"SYM{i}", "1h", "RSI")] = "OVERSOLD"
        engine.last_condition[(f"SYM{i}", "1h", "BREAKOUT")] = "BULL"
        engine.last_condition[(f"SYM{i}", "4h", "RSI")] = "OVERBOUGHT"

    return engine

def test_cleanup_stale_conditions_optimized():
    engine = setup_engine()

    start_time = time.perf_counter()
    engine._cleanup_stale_conditions()
    end_time = time.perf_counter()

    elapsed = end_time - start_time
    print(f"Optimized _cleanup_stale_conditions: {elapsed:.6f} seconds")

if __name__ == "__main__":
    test_cleanup_stale_conditions_optimized()
