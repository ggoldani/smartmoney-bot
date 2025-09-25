from loguru import logger
import sys
def setup_logging(level: str = "INFO"):
    logger.remove()
    logger.add(sys.stdout, level=level, backtrace=False, diagnose=False)
    return logger
