from loguru import logger
import sys
import os

def setup_logging(level: str = "INFO"):
    """
    Configure logging:
    - stdout: for Docker logs
    - file: /app/logs/bot.log with rotation (10MB, 7 backups)
    """
    logger.remove()

    # Console output (Docker logs)
    logger.add(sys.stdout, level=level, backtrace=False, diagnose=False)

    # File output with rotation
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "bot.log")
    logger.add(
        log_file,
        level=level,
        rotation="10 MB",    # Rotate at 10MB
        retention=7,          # Keep 7 files
        compression="gz",     # Compress old logs
        backtrace=True,
        diagnose=True,
        enqueue=True          # Async logging (thread-safe)
    )

    logger.info(f"Logging configured: console + file ({log_file})")
    return logger
