from typing import Optional, List, Tuple
import datetime
from sqlmodel import SQLModel, Field, create_engine, Session, select

DATABASE_URL = "sqlite:///portfolio.db"

utcnow = lambda: datetime.datetime.now(datetime.timezone.utc)

class ETF(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(index=True, nullable=False)
    target_pct: float = Field(default=0.0)
    resolved_ticker: Optional[str] = None
    last_price: Optional[float] = None
    last_updated: Optional[datetime.datetime] = None
    supports_fractions: bool = Field(default=True)
    created_at: datetime.datetime = Field(default_factory=utcnow)


def _ensure_column_exists(engine, table_name: str, column_def: str):
    """Add a column to a table if it doesn't exist."""
    import sqlalchemy as sa
    col_name = column_def.split()[0]
    try:
        with engine.begin() as conn:
            # Check if column exists using PRAGMA
            res = conn.execute(sa.text(f"PRAGMA table_info('{table_name}')")).fetchall()
            cols = [r[1] for r in res]
            if col_name not in cols:
                # Column doesn't exist, add it - use quoted table name for SQLite compatibility
                alter_sql = f'ALTER TABLE "{table_name}" ADD COLUMN {column_def}'
                conn.execute(sa.text(alter_sql))
    except Exception as e:
        import logging
        logging.warning(f"Failed to ensure column {col_name} exists in {table_name}: {e}")

class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    etf_id: int = Field(foreign_key="etf.id")
    date: datetime.datetime = Field(default_factory=utcnow)
    price: float
    shares: float
    amount: float
    commission: float = Field(default=0.0)

_engine = None

def init_db(url: str = DATABASE_URL):
    global _engine
    _engine = create_engine(url, echo=False)
    SQLModel.metadata.create_all(_engine)
    # ensure the resolved_ticker column exists for existing DBs
    try:
        _ensure_column_exists(_engine, 'etf', 'resolved_ticker TEXT')
    except Exception:
        # best effort - ignore if not supported
        pass
    # ensure the supports_fractions column exists for existing DBs
    try:
        _ensure_column_exists(_engine, 'etf', 'supports_fractions BOOLEAN DEFAULT 1')
    except Exception:
        # best effort - ignore if not supported
        pass
    # ensure the commission column exists for existing DBs
    try:
        _ensure_column_exists(_engine, 'transaction', 'commission REAL DEFAULT 0.0')
    except Exception:
        # best effort - ignore if not supported
        pass

def get_session() -> Session:
    if _engine is None:
        init_db()
    return Session(_engine)

# CRUD helpers

def add_etf(ticker: str, target_pct: float, supports_fractions: bool = True) -> ETF:
    with get_session() as s:
        etf = ETF(ticker=ticker.upper(), target_pct=target_pct, supports_fractions=supports_fractions)
        s.add(etf)
        s.commit()
        s.refresh(etf)
        return etf

def get_etf_by_id(etf_id: int) -> Optional[ETF]:
    with get_session() as s:
        return s.get(ETF, etf_id)

def get_etf_by_ticker(ticker: str) -> Optional[ETF]:
    with get_session() as s:
        statement = select(ETF).where(ETF.ticker == ticker.upper())
        return s.exec(statement).first()

def list_etfs() -> List[ETF]:
    with get_session() as s:
        return s.exec(select(ETF)).all()

def delete_etf(etf_id: int) -> None:
    with get_session() as s:
        etf = s.get(ETF, etf_id)
        if etf:
            s.delete(etf)
            s.commit()

def update_etf(etf_id: int, target_pct: Optional[float] = None, supports_fractions: Optional[bool] = None) -> None:
    """Update ETF properties."""
    with get_session() as s:
        etf = s.get(ETF, etf_id)
        if etf:
            if target_pct is not None:
                etf.target_pct = target_pct
            if supports_fractions is not None:
                etf.supports_fractions = supports_fractions
            s.add(etf)
            s.commit()

# Transactions

def add_transaction(etf_id: int, price: float, shares: float, commission: float = 0.0, date: Optional[datetime.datetime] = None):
    amount = price * shares
    if date is None:
        date = utcnow()
    with get_session() as s:
        tx = Transaction(etf_id=etf_id, price=price, shares=shares, amount=amount, commission=commission, date=date)
        s.add(tx)
        s.commit()
        s.refresh(tx)
        return tx

def get_transactions(etf_id: int) -> List[Transaction]:
    with get_session() as s:
        return s.exec(select(Transaction).where(Transaction.etf_id == etf_id)).all()

# Price updates & calculations

def update_etf_price(etf_id: int, price: float) -> None:
    with get_session() as s:
        etf = s.get(ETF, etf_id)
        if etf:
            etf.last_price = price
            etf.last_updated = datetime.datetime.now(datetime.timezone.utc)
            s.add(etf)
            s.commit()

def update_etf_resolved_ticker(etf_id: int, resolved: str) -> None:
    with get_session() as s:
        etf = s.get(ETF, etf_id)
        if etf and resolved:
            etf.resolved_ticker = resolved.upper()
            s.add(etf)
            s.commit()

def get_etf_holdings(etf_id: int) -> Tuple[float, float]:
    """Return (total_shares, total_value) for an ETF based on transactions and last_price."""
    with get_session() as s:
        etf = s.get(ETF, etf_id)
        if not etf:
            return 0.0, 0.0
        txs = s.exec(select(Transaction).where(Transaction.etf_id == etf_id)).all()
        total_shares = sum(t.shares for t in txs)
        total_value = (etf.last_price or 0.0) * total_shares
        return total_shares, total_value

def get_etf_invested(etf_id: int) -> float:
    """Return total invested money (sum of transaction amounts + commissions) for an ETF."""
    with get_session() as s:
        txs = s.exec(select(Transaction).where(Transaction.etf_id == etf_id)).all()
        total_invested = sum(t.amount + t.commission for t in txs)
        return total_invested

def get_portfolio_value() -> float:
    total = 0.0
    with get_session() as s:
        etfs = s.exec(select(ETF)).all()
        for e in etfs:
            txs = s.exec(select(Transaction).where(Transaction.etf_id == e.id)).all()
            shares = sum(t.shares for t in txs)
            total += (e.last_price or 0.0) * shares
    return total