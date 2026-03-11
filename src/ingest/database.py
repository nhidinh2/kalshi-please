"""
SQLite database manager for Kalshi research data.
"""
from __future__ import annotations

import sqlite3
import os
from pathlib import Path


DB_PATH = Path(__file__).parent.parent.parent / "data" / "kalshi.db"
SCHEMA_PATH = Path(__file__).parent.parent.parent / "sql" / "schema.sql"


def get_connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    """Get a database connection, creating the DB if needed."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path = DB_PATH):
    """Initialize the database with the schema."""
    conn = get_connection(db_path)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.close()
    print(f"Database initialized at {db_path}")


def upsert_events(conn: sqlite3.Connection, events: list[dict]):
    """Insert or update events."""
    for e in events:
        conn.execute(
            """INSERT INTO events (event_ticker, series_ticker, title, category,
               mutually_exclusive, strike_date, strike_period, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(event_ticker) DO UPDATE SET
               title=excluded.title, category=excluded.category,
               mutually_exclusive=excluded.mutually_exclusive,
               strike_date=excluded.strike_date, strike_period=excluded.strike_period,
               updated_at=excluded.updated_at""",
            (
                e.get("event_ticker"),
                e.get("series_ticker"),
                e.get("title"),
                e.get("category"),
                1 if e.get("mutually_exclusive") else 0,
                e.get("strike_date"),
                e.get("strike_period"),
                e.get("last_updated_ts"),
            ),
        )
    conn.commit()


def upsert_markets(conn: sqlite3.Connection, markets: list[dict]):
    """Insert or update markets."""
    for m in markets:
        conn.execute(
            """INSERT INTO markets (ticker, event_ticker, market_type,
               yes_sub_title, no_sub_title, rules_primary, status, result,
               open_time, close_time, settlement_ts,
               last_price_dollars, volume_fp, volume_24h_fp,
               open_interest_fp, notional_value_dollars,
               settlement_value_dollars, strike_type, floor_strike,
               cap_strike, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(ticker) DO UPDATE SET
               status=excluded.status, result=excluded.result,
               settlement_ts=excluded.settlement_ts,
               last_price_dollars=excluded.last_price_dollars,
               volume_fp=excluded.volume_fp, volume_24h_fp=excluded.volume_24h_fp,
               open_interest_fp=excluded.open_interest_fp,
               settlement_value_dollars=excluded.settlement_value_dollars,
               updated_at=excluded.updated_at""",
            (
                m.get("ticker"),
                m.get("event_ticker"),
                m.get("market_type"),
                m.get("yes_sub_title"),
                m.get("no_sub_title"),
                m.get("rules_primary"),
                m.get("status"),
                m.get("result"),
                m.get("open_time"),
                m.get("close_time"),
                m.get("settlement_ts"),
                m.get("last_price_dollars"),
                m.get("volume_fp"),
                m.get("volume_24h_fp"),
                m.get("open_interest_fp"),
                m.get("notional_value_dollars"),
                m.get("settlement_value_dollars"),
                m.get("strike_type"),
                m.get("floor_strike"),
                m.get("cap_strike"),
                m.get("updated_time"),
            ),
        )
    conn.commit()


def insert_candlesticks(
    conn: sqlite3.Connection,
    market_ticker: str,
    candlesticks: list[dict],
    period_interval: int,
):
    """Insert candlestick price history, skipping duplicates."""
    for c in candlesticks:
        yes_bid = c.get("yes_bid", {}) or {}
        yes_ask = c.get("yes_ask", {}) or {}
        price = c.get("price", {}) or {}

        conn.execute(
            """INSERT OR IGNORE INTO price_history
               (market_ticker, timestamp, period_interval,
                yes_bid_open, yes_bid_high, yes_bid_low, yes_bid_close,
                yes_ask_open, yes_ask_high, yes_ask_low, yes_ask_close,
                price_open, price_high, price_low, price_close, price_mean,
                volume_fp, open_interest_fp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                market_ticker,
                c.get("end_period_ts"),
                period_interval,
                yes_bid.get("open"),
                yes_bid.get("high"),
                yes_bid.get("low"),
                yes_bid.get("close"),
                yes_ask.get("open"),
                yes_ask.get("high"),
                yes_ask.get("low"),
                yes_ask.get("close"),
                price.get("open"),
                price.get("high"),
                price.get("low"),
                price.get("close"),
                price.get("mean"),
                c.get("volume_fp"),
                c.get("open_interest_fp"),
            ),
        )
    conn.commit()


def insert_trades(conn: sqlite3.Connection, trades: list[dict]):
    """Insert trades, skipping duplicates."""
    for t in trades:
        conn.execute(
            """INSERT OR IGNORE INTO trades
               (trade_id, market_ticker, count_fp, yes_price_dollars,
                no_price_dollars, taker_side, created_time)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                t.get("trade_id"),
                t.get("ticker"),
                t.get("count_fp"),
                t.get("yes_price_dollars"),
                t.get("no_price_dollars"),
                t.get("taker_side"),
                t.get("created_time"),
            ),
        )
    conn.commit()
