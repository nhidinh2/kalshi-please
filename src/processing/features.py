from __future__ import annotations
"""
Feature engineering for Kalshi market analysis.
Transforms raw price/market data into an analysis-ready dataset.
"""

import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.ingest.database import get_connection, DB_PATH


def load_markets_df(conn: sqlite3.Connection) -> pd.DataFrame:
    """Load all resolved binary markets into a DataFrame."""
    query = """
        SELECT m.*, e.title as event_title, e.series_ticker, e.category,
               e.mutually_exclusive
        FROM markets m
        JOIN events e ON m.event_ticker = e.event_ticker
        WHERE m.result IN ('yes', 'no')
          AND m.market_type = 'binary'
    """
    df = pd.read_sql_query(query, conn)
    df["result_binary"] = (df["result"] == "yes").astype(int)
    df["volume"] = pd.to_numeric(df["volume_fp"], errors="coerce").fillna(0)
    df["last_price"] = pd.to_numeric(df["last_price_dollars"], errors="coerce")
    return df


def load_price_history_df(
    conn: sqlite3.Connection, period_interval: int = None
) -> pd.DataFrame:
    """Load price history into a DataFrame.

    If period_interval is None (default), loads daily (1440) data first,
    then fills in markets that have no daily data using hourly (60) data.
    This ensures maximum coverage across all categories.
    """
    if period_interval is not None:
        # Original behavior: load a specific interval
        query = """
            SELECT ph.*, m.result, m.close_time, m.settlement_ts,
                   e.category
            FROM price_history ph
            JOIN markets m ON ph.market_ticker = m.ticker
            JOIN events e ON m.event_ticker = e.event_ticker
            WHERE ph.period_interval = ?
              AND m.result IN ('yes', 'no')
        """
        df = pd.read_sql_query(query, conn, params=(period_interval,))
    else:
        # Load daily data
        query_daily = """
            SELECT ph.*, m.result, m.close_time, m.settlement_ts,
                   e.category
            FROM price_history ph
            JOIN markets m ON ph.market_ticker = m.ticker
            JOIN events e ON m.event_ticker = e.event_ticker
            WHERE ph.period_interval = 1440
              AND m.result IN ('yes', 'no')
        """
        df_daily = pd.read_sql_query(query_daily, conn)
        daily_tickers = set(df_daily["market_ticker"].unique())

        # Load hourly data only for markets missing from daily
        query_hourly = """
            SELECT ph.*, m.result, m.close_time, m.settlement_ts,
                   e.category
            FROM price_history ph
            JOIN markets m ON ph.market_ticker = m.ticker
            JOIN events e ON m.event_ticker = e.event_ticker
            WHERE ph.period_interval = 60
              AND m.result IN ('yes', 'no')
        """
        df_hourly = pd.read_sql_query(query_hourly, conn)
        # Keep only markets not already covered by daily data
        df_hourly = df_hourly[~df_hourly["market_ticker"].isin(daily_tickers)]

        df = pd.concat([df_daily, df_hourly], ignore_index=True)
        print(f"  Price history: {len(df_daily)} daily rows + {len(df_hourly)} hourly rows (backfill)")

    # Parse numeric columns
    for col in [
        "price_open", "price_high", "price_low", "price_close", "price_mean",
        "yes_bid_close", "yes_ask_close", "volume_fp", "open_interest_fp",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["result_binary"] = (df["result"] == "yes").astype(int)
    df["dt"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    return df


def compute_market_features(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Compute per-market features for the analysis dataset.
    Each row = one resolved market with features for calibration analysis.
    """
    markets = load_markets_df(conn)
    prices = load_price_history_df(conn)

    features = []

    for _, market in markets.iterrows():
        ticker = market["ticker"]
        mp = prices[prices["market_ticker"] == ticker].sort_values("timestamp")

        if mp.empty:
            continue

        # Parse times
        close_time = pd.to_datetime(market["close_time"], utc=True, format="ISO8601")
        open_time = pd.to_datetime(market["open_time"], utc=True, format="ISO8601")

        if pd.isna(close_time) or pd.isna(open_time):
            continue

        duration_hours = (close_time - open_time).total_seconds() / 3600

        # Volume features
        total_volume = mp["volume_fp"].sum()
        n_days = max(len(mp), 1)
        avg_daily_volume = total_volume / n_days
        max_daily_volume = mp["volume_fp"].max()

        # Price at different times before resolution
        last_price = mp["price_close"].iloc[-1]

        def price_n_days_before(n_days_before):
            target = close_time - timedelta(days=n_days_before)
            before = mp[mp["dt"] <= target]
            if not before.empty:
                return before["price_close"].iloc[-1]
            return np.nan

        price_1d = price_n_days_before(1)
        price_3d = price_n_days_before(3)
        price_7d = price_n_days_before(7)

        # Spread features
        spreads = mp["yes_ask_close"] - mp["yes_bid_close"]
        avg_spread = spreads.mean() if not spreads.isna().all() else np.nan

        # Volatility: std of price changes
        price_changes = mp["price_close"].diff()
        volatility = price_changes.std() if len(price_changes) > 1 else np.nan

        # Late volatility: std of price changes in last 24 hours before close
        last_24h = mp[mp["dt"] >= (close_time - timedelta(hours=24))]
        if len(last_24h) > 1:
            late_volatility = last_24h["price_close"].diff().std()
        else:
            late_volatility = np.nan

        # Late price reversal: how much price moved in final 3 days
        # Large reversal = surprise / late-breaking information
        if not np.isnan(price_3d) and not np.isnan(last_price):
            late_price_move = abs(last_price - price_3d)
        else:
            late_price_move = np.nan

        # Price range: max - min observed price (measures uncertainty)
        price_range = mp["price_close"].max() - mp["price_close"].min()

        # Volume concentration: what fraction of volume in last 25% of observations
        if len(mp) >= 4:
            cutoff = len(mp) * 3 // 4
            late_vol = mp.iloc[cutoff:]["volume_fp"].sum()
            late_volume_share = late_vol / max(total_volume, 1e-9)
        else:
            late_volume_share = np.nan

        # Liquidity bucket based on total volume
        if total_volume >= 10000:
            liquidity = "high"
        elif total_volume >= 1000:
            liquidity = "medium"
        else:
            liquidity = "low"

        # Brier score for last price
        outcome = market["result_binary"]
        brier = (last_price - outcome) ** 2 if not np.isnan(last_price) else np.nan

        features.append({
            "market_ticker": ticker,
            "event_ticker": market["event_ticker"],
            "category": market.get("category") or infer_category(market["series_ticker"]),
            "event_title": market["event_title"],
            "yes_sub_title": market["yes_sub_title"],
            "result": market["result"],
            "result_binary": outcome,
            "open_time": str(open_time),
            "close_time": str(close_time),
            "settlement_ts": market["settlement_ts"],
            "duration_hours": duration_hours,
            "n_price_observations": len(mp),
            "total_volume": total_volume,
            "avg_daily_volume": avg_daily_volume,
            "max_daily_volume": max_daily_volume,
            "last_price": last_price,
            "price_1d_before": price_1d,
            "price_3d_before": price_3d,
            "price_7d_before": price_7d,
            "avg_spread": avg_spread,
            "price_volatility": volatility,
            "late_volatility": late_volatility,
            "late_price_move": late_price_move,
            "price_range": price_range,
            "late_volume_share": late_volume_share,
            "liquidity_bucket": liquidity,
            "brier_score": brier,
        })

    return pd.DataFrame(features)


def infer_category(series_ticker: str) -> str:
    """Infer a rough category from the series ticker."""
    if not series_ticker:
        return "unknown"
    st = series_ticker.upper()
    if any(k in st for k in ["ECON", "GDP", "CPI", "JOBS", "UNEMP", "FED", "RATE"]):
        return "economics"
    if any(k in st for k in ["ELECT", "PRES", "GOV", "SENATE", "HOUSE", "VOTE"]):
        return "politics"
    if any(k in st for k in ["WEATHER", "TEMP", "HURRICANE", "CLIMATE"]):
        return "weather"
    if any(k in st for k in ["SPORT", "NFL", "NBA", "MLB", "NCAA"]):
        return "sports"
    if any(k in st for k in ["TECH", "AI", "CRYPTO", "BTC", "ETH"]):
        return "tech"
    if any(k in st for k in ["FIN", "SP500", "NASDAQ", "DOW", "STOCK"]):
        return "finance"
    return "other"


def build_calibration_dataset(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Build a dataset for calibration analysis.
    Each row = one (market, timestamp) observation with:
    - implied probability (yes price)
    - days to resolution
    - eventual outcome
    - liquidity features
    """
    prices = load_price_history_df(conn)
    markets = load_markets_df(conn)

    # Merge market-level volume info (prices already has result_binary)
    market_info = markets[["ticker", "volume"]].rename(
        columns={"ticker": "market_ticker", "volume": "total_market_volume"}
    )
    df = prices.merge(market_info, on="market_ticker", how="inner")

    # Compute days to resolution
    df["close_dt"] = pd.to_datetime(df["close_time"], utc=True, format="ISO8601")
    df["days_to_resolution"] = (df["close_dt"] - df["dt"]).dt.total_seconds() / 86400

    # Implied probability = price_close (yes price in dollars = probability)
    df["implied_prob"] = df["price_close"]

    # Liquidity bucket
    df["liquidity_bucket"] = pd.cut(
        df["total_market_volume"],
        bins=[0, 1000, 10000, float("inf")],
        labels=["low", "medium", "high"],
    )

    # Spread
    df["spread"] = df["yes_ask_close"] - df["yes_bid_close"]

    # Keep relevant columns
    keep = [
        "market_ticker", "event_ticker", "category", "dt", "timestamp",
        "implied_prob", "result_binary", "days_to_resolution",
        "volume_fp", "open_interest_fp", "spread",
        "total_market_volume", "liquidity_bucket",
    ]
    return df[[c for c in keep if c in df.columns]].dropna(subset=["implied_prob"])


if __name__ == "__main__":
    conn = get_connection()
    print("Computing market features...")
    features = compute_market_features(conn)
    print(f"Built features for {len(features)} markets")
    print(features.describe())

    # Save to DB
    features.to_sql("market_features", conn, if_exists="replace", index=False)
    print("Saved to market_features table")

    print("\nBuilding calibration dataset...")
    cal = build_calibration_dataset(conn)
    print(f"Calibration dataset: {len(cal)} observations")
    print(cal.describe())

    conn.close()
