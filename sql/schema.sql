-- Kalshi Research Database Schema
-- SQLite-compatible

CREATE TABLE IF NOT EXISTS events (
    event_ticker TEXT PRIMARY KEY,
    series_ticker TEXT,
    title TEXT NOT NULL,
    category TEXT,
    mutually_exclusive INTEGER,  -- boolean
    strike_date TEXT,            -- ISO datetime, nullable
    strike_period TEXT,          -- e.g. 'week', 'month'
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS markets (
    ticker TEXT PRIMARY KEY,
    event_ticker TEXT NOT NULL,
    market_type TEXT DEFAULT 'binary',  -- 'binary' or 'scalar'
    yes_sub_title TEXT,
    no_sub_title TEXT,
    rules_primary TEXT,
    status TEXT,        -- initialized|inactive|active|closed|determined|finalized
    result TEXT,        -- 'yes', 'no', 'scalar', or '' (unresolved)
    open_time TEXT,
    close_time TEXT,
    settlement_ts TEXT,
    last_price_dollars TEXT,
    volume_fp TEXT,
    volume_24h_fp TEXT,
    open_interest_fp TEXT,
    notional_value_dollars TEXT,
    settlement_value_dollars TEXT,
    strike_type TEXT,
    floor_strike REAL,
    cap_strike REAL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT,
    FOREIGN KEY (event_ticker) REFERENCES events(event_ticker)
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_ticker TEXT NOT NULL,
    timestamp INTEGER NOT NULL,          -- unix timestamp (end of period)
    period_interval INTEGER NOT NULL,    -- 1, 60, or 1440 minutes
    yes_bid_open TEXT,
    yes_bid_high TEXT,
    yes_bid_low TEXT,
    yes_bid_close TEXT,
    yes_ask_open TEXT,
    yes_ask_high TEXT,
    yes_ask_low TEXT,
    yes_ask_close TEXT,
    price_open TEXT,
    price_high TEXT,
    price_low TEXT,
    price_close TEXT,
    price_mean TEXT,
    volume_fp TEXT,
    open_interest_fp TEXT,
    FOREIGN KEY (market_ticker) REFERENCES markets(ticker)
);

CREATE INDEX IF NOT EXISTS idx_price_history_ticker_ts
    ON price_history(market_ticker, timestamp);

CREATE INDEX IF NOT EXISTS idx_price_history_ticker_interval
    ON price_history(market_ticker, period_interval);

CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    market_ticker TEXT NOT NULL,
    count_fp TEXT,            -- number of contracts
    yes_price_dollars TEXT,
    no_price_dollars TEXT,
    taker_side TEXT,          -- 'yes' or 'no'
    created_time TEXT,
    FOREIGN KEY (market_ticker) REFERENCES markets(ticker)
);

CREATE INDEX IF NOT EXISTS idx_trades_ticker
    ON trades(market_ticker);

CREATE INDEX IF NOT EXISTS idx_trades_time
    ON trades(created_time);

-- Materialized view equivalent: analysis-ready dataset
-- Each row = one market with its resolution and aggregated features
CREATE TABLE IF NOT EXISTS market_features (
    market_ticker TEXT PRIMARY KEY,
    event_ticker TEXT,
    category TEXT,
    result TEXT,                    -- 'yes' or 'no'
    result_binary INTEGER,         -- 1 for yes, 0 for no
    open_time TEXT,
    close_time TEXT,
    settlement_ts TEXT,
    duration_hours REAL,           -- total market lifetime
    total_volume REAL,
    avg_daily_volume REAL,
    max_daily_volume REAL,
    total_trades INTEGER,
    last_price REAL,               -- final price before resolution
    price_1d_before REAL,          -- price 1 day before close
    price_3d_before REAL,          -- price 3 days before close
    price_7d_before REAL,          -- price 7 days before close
    avg_spread REAL,               -- average bid-ask spread
    price_volatility REAL,         -- std dev of daily price changes
    liquidity_bucket TEXT,         -- 'low', 'medium', 'high'
    brier_score REAL,              -- (forecast - outcome)^2 for last price
    FOREIGN KEY (market_ticker) REFERENCES markets(ticker)
);
