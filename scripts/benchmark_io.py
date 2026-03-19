import asyncio
import time
import os
from typing import Optional

# Mocking the bot as it might not be installed or would require network
class MockBot:
    async def send_photo(self, chat_id, photo, caption=None):
        # In a real scenario, this would involve network I/O which is async
        # We simulate some async work here
        await asyncio.sleep(0.05)
        # Simulate reading the file object if it's passed
        if hasattr(photo, 'read'):
            photo.read()

async def heartbeat(stop_event, intervals):
    last_time = time.perf_counter()
    while not stop_event.is_set():
        await asyncio.sleep(0.005)
        now = time.perf_counter()
        intervals.append(now - last_time)
        last_time = now

# The current implementation (simplified for benchmarking)
async def _send_photo_async_current(path: str, caption: Optional[str], chat_id: str, bot) -> None:
    # Current behavior: Open file and pass the object
    with open(path, "rb") as f:
        await bot.send_photo(chat_id=chat_id, photo=f, caption=caption)

async def _send_photo_async_optimized(path: str, caption: Optional[str], chat_id: str, bot) -> None:
    # Optimized behavior: offload reading to thread
    def read_file():
        with open(path, "rb") as f:
            return f.read()

    photo_bytes = await asyncio.to_thread(read_file)
    await bot.send_photo(chat_id=chat_id, photo=photo_bytes, caption=caption)

async def run_benchmark(name, func, path, chat_id, bot):
    stop_event = asyncio.Event()
    intervals = []
    hb_task = asyncio.create_task(heartbeat(stop_event, intervals))

    start = time.perf_counter()
    await func(path, "Test Caption", chat_id, bot)
    end = time.perf_counter()

    stop_event.set()
    await hb_task

    max_lag = max(intervals) if intervals else 0
    avg_lag = sum(intervals) / len(intervals) if intervals else 0

    return end-start, max_lag, avg_lag

async def main():
    dummy_file = "scripts/large_photo.bin"
    # Create a 50MB dummy file to make the impact more noticeable
    with open(dummy_file, "wb") as f:
        f.write(os.urandom(50 * 1024 * 1024))

    bot = MockBot()
    chat_id = "123456"

    print(f"{'Method':<15} | {'Duration':<10} | {'Max Lag':<10} | {'Avg Lag':<10}")
    print("-" * 55)

    for name, func in [("Current", _send_photo_async_current), ("Optimized", _send_photo_async_optimized)]:
        durations = []
        max_lags = []
        for _ in range(3):
            duration, max_lag, avg_lag = await run_benchmark(name, func, dummy_file, chat_id, bot)
            durations.append(duration)
            max_lags.append(max_lag)

        print(f"{name:<15} | {sum(durations)/3:<10.4f}s | {sum(max_lags)/3:<10.4f}s | {avg_lag:<10.4f}s")

    os.remove(dummy_file)

if __name__ == "__main__":
    asyncio.run(main())
