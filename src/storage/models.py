from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, BigInteger, UniqueConstraint, Index

class Base(DeclarativeBase):
    pass

class Candle(Base):
    __tablename__ = "candles"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)          # ex: BTCUSDT, TOTAL, ALT
    interval: Mapped[str] = mapped_column(String(5), nullable=False)         # ex: 4h, 1d, 1w, 1M
    open_time: Mapped[int] = mapped_column(BigInteger, nullable=False)       # ms UTC
    close_time: Mapped[int] = mapped_column(BigInteger, nullable=False)      # ms UTC
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_closed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0/1

    __table_args__ = (
        UniqueConstraint("symbol", "interval", "open_time", name="uq_candle_symbol_tf_open"),
        Index("ix_candle_symbol_tf_open", "symbol", "interval", "open_time"),
    )

class MarketCaps(Base):
    __tablename__ = "market_caps"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[int] = mapped_column(BigInteger, nullable=False)        # ms UTC (snapshot)
    total_mcap_usd: Mapped[float] = mapped_column(Float, nullable=False)
    btc_dominance_pct: Mapped[float] = mapped_column(Float, nullable=False)
    eth_dominance_pct: Mapped[float] = mapped_column(Float, nullable=False)
    alt_dominance_pct: Mapped[float] = mapped_column(Float, nullable=False)
    alt_mcap_usd: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("timestamp", name="uq_caps_ts"),
        Index("ix_caps_ts", "timestamp"),
    )

