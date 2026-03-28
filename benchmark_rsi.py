import time
import random
from typing import List, Optional
import numpy as np
import pandas as pd

def original_rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    n = len(closes)
    rsi_values: List[Optional[float]] = [None] * n

    if n < period + 1:
        return rsi_values

    changes = [closes[i] - closes[i - 1] for i in range(1, n)]

    avg_gain = sum(max(c, 0) for c in changes[:period]) / period
    avg_loss = sum(abs(min(c, 0)) for c in changes[:period]) / period

    if avg_loss == 0:
        rsi_values[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_values[period] = round(100 - (100 / (1 + rs)), 2)

    for i in range(period, len(changes)):
        change = changes[i]
        gain = max(change, 0)
        loss = abs(min(change, 0))

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi_values[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_values[i + 1] = round(100 - (100 / (1 + rs)), 2)

    return rsi_values

def pandas_optimized_rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    n = len(closes)
    rsi_values: List[Optional[float]] = [None] * n

    if n < period + 1:
        return rsi_values

    s = pd.Series(closes)
    delta = s.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    first_avg_gain = gain[1:period+1].mean()
    first_avg_loss = loss[1:period+1].mean()

    gain_series = pd.concat([pd.Series([first_avg_gain]), gain.iloc[period+1:]], ignore_index=True)
    loss_series = pd.concat([pd.Series([first_avg_loss]), loss.iloc[period+1:]], ignore_index=True)

    avg_gains = gain_series.ewm(alpha=1/period, adjust=False).mean().values
    avg_losses = loss_series.ewm(alpha=1/period, adjust=False).mean().values

    rsi_vals = np.zeros_like(avg_gains)

    zero_losses = avg_losses == 0
    non_zero_losses = ~zero_losses

    rsi_vals[zero_losses] = 100.0
    rs = avg_gains[non_zero_losses] / avg_losses[non_zero_losses]
    rsi_vals[non_zero_losses] = np.round(100.0 - (100.0 / (1.0 + rs)), 2)

    rsi_values[period:] = rsi_vals.tolist()
    return rsi_values


def numpy_optimized_rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    """A highly optimized numpy-only implementation without Pandas dependency"""
    n = len(closes)
    rsi_values: List[Optional[float]] = [None] * n

    if n < period + 1:
        return rsi_values

    # Using numpy diff
    closes_arr = np.array(closes, dtype=np.float64)
    changes = np.diff(closes_arr)

    # Calculate initial averages
    initial_changes = changes[:period]
    avg_gain = np.sum(np.maximum(initial_changes, 0)) / period
    avg_loss = np.sum(np.abs(np.minimum(initial_changes, 0))) / period

    if avg_loss == 0:
        rsi_values[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_values[period] = round(100 - (100 / (1 + rs)), 2)

    # Pure python loop over numpy arrays for remaining
    if len(changes) > period:
        # tolist is very fast and iterations over lists are much faster than over ndarrays
        remaining_changes = changes[period:].tolist()

        for i, change in enumerate(remaining_changes):
            if change > 0:
                gain = change
                loss = 0.0
            else:
                gain = 0.0
                loss = -change

            avg_gain = (avg_gain * (period - 1) + gain) / period
            avg_loss = (avg_loss * (period - 1) + loss) / period

            if avg_loss == 0:
                rsi_values[period + i + 1] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_values[period + i + 1] = round(100 - (100 / (1 + rs)), 2)

    return rsi_values


def pure_py_optimized_rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    """Pure Python implementation optimized by avoiding redundant generator expressions"""
    n = len(closes)
    rsi_values: List[Optional[float]] = [None] * n

    if n < period + 1:
        return rsi_values

    # Calculate price changes in one go
    changes = [closes[i] - closes[i - 1] for i in range(1, n)]

    # Initial average gain/loss
    sum_gain = 0.0
    sum_loss = 0.0
    for i in range(period):
        c = changes[i]
        if c > 0:
            sum_gain += c
        else:
            sum_loss -= c

    avg_gain = sum_gain / period
    avg_loss = sum_loss / period

    if avg_loss == 0:
        rsi_values[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi_values[period] = round(100 - (100 / (1 + rs)), 2)

    # Wilder's smoothing
    for i in range(period, len(changes)):
        c = changes[i]
        if c > 0:
            gain = c
            loss = 0.0
        else:
            gain = 0.0
            loss = -c

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi_values[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_values[i + 1] = round(100 - (100 / (1 + rs)), 2)

    return rsi_values

# Generate data sizes to benchmark
sizes = [100, 1000, 10000]

for size in sizes:
    print(f"\n--- Benchmark for size {size} ---")
    data = [random.uniform(10000, 60000) for _ in range(size)]

    # Assert correctness
    orig = original_rsi(data)
    pd_res = pandas_optimized_rsi(data)
    np_res = numpy_optimized_rsi(data)
    py_res = pure_py_optimized_rsi(data)

    assert orig == pd_res, f"Pandas failed size {size}"
    assert orig == np_res, f"Numpy failed size {size}"
    assert orig == py_res, f"Py failed size {size}"

    iters = max(10, 100000 // size)

    t0 = time.time()
    for _ in range(iters):
        original_rsi(data)
    t1 = time.time()
    print(f"Original: {t1 - t0:.4f}s")

    t0 = time.time()
    for _ in range(iters):
        pandas_optimized_rsi(data)
    t2 = time.time()
    print(f"Pandas: {t2 - t0:.4f}s")

    t0 = time.time()
    for _ in range(iters):
        numpy_optimized_rsi(data)
    t3 = time.time()
    print(f"Numpy: {t3 - t0:.4f}s")

    t0 = time.time()
    for _ in range(iters):
        pure_py_optimized_rsi(data)
    t4 = time.time()
    print(f"Pure Py: {t4 - t0:.4f}s")
