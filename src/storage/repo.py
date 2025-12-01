from typing import Dict, Optional
from sqlalchemy.dialects.sqlite import insert
from .db import SessionLocal
from .models import Candle

def save_candle_event(event: Dict) -> bool:
    """
    Salva/atualiza um candle (aberto ou fechado) na tabela candles.
    Se já existir (unique: symbol, interval, open_time), atualiza os valores.
    Isso permite atualizar velas abertas conforme evoluem.
    """
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


def get_previous_closed_candle(symbol: str, interval: str) -> Optional[Candle]:
    """Get most recent closed candle (day that just closed)."""
    with SessionLocal() as session:
        return session.query(Candle).filter_by(symbol=symbol, interval=interval, is_closed=1).order_by(Candle.open_time.desc()).first()

