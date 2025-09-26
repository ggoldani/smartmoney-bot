from typing import Dict
from sqlalchemy.dialects.sqlite import insert
from .db import SessionLocal
from .models import Candle

def save_candle_event(event: Dict) -> bool:
    """
    Salva um candle (somente fechado) na tabela candles.
    Ignora se já existir (unique: symbol, interval, open_time).
    """
    if not event.get("is_closed"):
        return False

    with SessionLocal() as session:
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
            is_closed=1,
        ).on_conflict_do_nothing(
            index_elements=["symbol", "interval", "open_time"]
        )
        session.execute(stmt)
        session.commit()
        return True

