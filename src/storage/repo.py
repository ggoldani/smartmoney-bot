from typing import Dict, Optional
from sqlalchemy.dialects.sqlite import insert
from loguru import logger
from .db import SessionLocal
from .models import Candle


def save_candle_event(event: Dict) -> bool:
    """
    Salva/atualiza um candle (aberto ou fechado) na tabela candles.
    Se já existir (unique: symbol, interval, open_time), atualiza os valores.
    Isso permite atualizar velas abertas conforme evoluem.
    """
    try:
        with SessionLocal() as session:
            is_closed_val = 1 if event.get("is_closed") else 0

            stmt = insert(Candle).values(
                symbol=event["symbol"],
                interval=event["interval"],
                open_time=int(event["open_time"]),
                close_time=int(event["close_time"]),
                open=float(event["open"]),
                high=float(event["high"]),
                low=float(event["low"]),
                close=float(event["close"]),
                volume=float(event.get("volume", 0.0)),
                is_closed=is_closed_val,
            ).on_conflict_do_update(
                index_elements=["symbol", "interval", "open_time"],
                set_={
                    "close_time": int(event["close_time"]),
                    "high": float(event["high"]),
                    "low": float(event["low"]),
                    "close": float(event["close"]),
                    "volume": float(event.get("volume", 0.0)),
                    "is_closed": is_closed_val,
                }
            )
            session.execute(stmt)
            session.commit()
            return True
    except (KeyError, ValueError, TypeError) as e:
        logger.error(f"Invalid candle event data: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to save candle event: {e}")
        return False


def get_previous_closed_candle(symbol: str, interval: str) -> Optional[Dict]:
    """
    Get most recent closed candle (day that just closed).

    Returns:
        Dict with candle fields or None if not found.
        Fields: symbol, interval, open_time, close_time, open, high, low, close, volume, is_closed
    """
    try:
        with SessionLocal() as session:
            candle = session.query(Candle).filter_by(
                symbol=symbol, interval=interval, is_closed=1
            ).order_by(Candle.open_time.desc()).first()

            if candle is None:
                return None

            # Return dict to avoid detached ORM object issues outside session
            return {
                "symbol": candle.symbol,
                "interval": candle.interval,
                "open_time": candle.open_time,
                "close_time": candle.close_time,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "is_closed": candle.is_closed,
            }
    except Exception as e:
        logger.error(f"Failed to get previous closed candle {symbol} {interval}: {e}")
        return None

