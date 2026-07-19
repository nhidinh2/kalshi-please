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

        # Drop candles at or after close. Post-close candles carry the settled
        # price (0.99/0.01), which would score as a near-perfect forecast.
        mp = mp[mp["dt"] < close_time]
        if mp.empty:
            continue

        # Observation spacing. Markets without daily candles are backfilled with
        # hourly ones, so any per-observation statistic is on a different clock
        # for them. Everything below is normalised to a per-day basis instead.
        interval_hours = float(mp["period_interval"].median()) / 60.0
        if not np.isfinite(interval_hours) or interval_hours <= 0:
            interval_hours = 24.0
        is_hourly_clock = interval_hours < 24.0
        obs_per_day = 24.0 / interval_hours

        # Volume features
        total_volume = mp["volume_fp"].sum()
        duration_days = max(duration_hours / 24.0, 1.0 / 24.0)
        avg_daily_volume = total_volume / duration_days
        max_daily_volume = mp["volume_fp"].max() * obs_per_day

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

        # Volatility: std of price changes, scaled to a per-day basis so hourly
        # and daily markets are comparable (random walk: sigma_day = sigma_step
        # * sqrt(steps per day)).
        day_scale = np.sqrt(obs_per_day)
        price_changes = mp["price_close"].diff()
        volatility = price_changes.std() * day_scale if len(price_changes) > 1 else np.nan

        # Late volatility: std of price changes in last 24 hours before close
        last_24h = mp[mp["dt"] >= (close_time - timedelta(hours=24))]
        if len(last_24h) > 1:
            late_volatility = last_24h["price_close"].diff().std() * day_scale
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

        # Volume concentration: fraction of volume traded in the last 25% of the
        # market's life. Measured over elapsed time, not row count, so it means
        # the same thing on both clocks.
        if len(mp) >= 4 and duration_hours > 0:
            late_start = close_time - timedelta(hours=duration_hours * 0.25)
            late_vol = mp[mp["dt"] >= late_start]["volume_fp"].sum()
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

        # Brier scores. The last-tick score flatters categories whose outcome is
        # public before the market closes (a called election trades at 0.99 for
        # days), so it is kept only as a diagnostic. The fixed-horizon scores are
        # the ones that actually test forecasting.
        outcome = market["result_binary"]
        brier = (last_price - outcome) ** 2 if not np.isnan(last_price) else np.nan

        def brier_at(price):
            return (price - outcome) ** 2 if not np.isnan(price) else np.nan

        brier_1d = brier_at(price_1d)
        brier_3d = brier_at(price_3d)
        brier_7d = brier_at(price_7d)

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
            "obs_per_day": obs_per_day,
            "is_hourly_clock": int(is_hourly_clock),
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
            "brier_1d_before": brier_1d,
            "brier_3d_before": brier_3d,
            "brier_7d_before": brier_7d,
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
    - liquidity features, measured as of the observation (see pit_* columns)
    """
    prices = load_price_history_df(conn)
    markets = load_markets_df(conn)

    # Merge market-level volume info (prices already has result_binary)
    market_info = markets[["ticker", "volume", "open_time"]].rename(
        columns={"ticker": "market_ticker", "volume": "total_market_volume"}
    )
    df = prices.merge(market_info, on="market_ticker", how="inner")

    # Compute days to resolution
    df["close_dt"] = pd.to_datetime(df["close_time"], utc=True, format="ISO8601")
    df["open_dt"] = pd.to_datetime(df["open_time"], utc=True, format="ISO8601")
    df["days_to_resolution"] = (df["close_dt"] - df["dt"]).dt.total_seconds() / 86400

    # Implied probability = price_close (yes price in dollars = probability)
    df["implied_prob"] = df["price_close"]

    # Spread
    df["spread"] = df["yes_ask_close"] - df["yes_bid_close"]

    # Drop observations at or after close before anything is accumulated: the
    # settled price is not a forecast, and including it scores as near-perfect.
    df = df[df["days_to_resolution"] > 0]
    df = df.dropna(subset=["implied_prob"])

    # Liquidity bucket. Left-inclusive so zero-volume markets bucket as "low"
    # rather than dropping to NaN.
    df["liquidity_bucket"] = pd.cut(
        df["total_market_volume"],
        bins=[-float("inf"), 1000, 10000, float("inf")],
        labels=["low", "medium", "high"],
    )

    # Duration is fixed at open, so it is known to a trader standing at any
    # observation and is safe to use as-is.
    df["duration_hours"] = (df["close_dt"] - df["open_dt"]).dt.total_seconds() / 3600

    # ── Point-in-time microstructure, computed from the market's past only ──
    # Whole-market aggregates (total volume, lifetime price range, mean spread)
    # describe the future relative to any observation before close. Using them
    # as controls leaks the outcome: lifetime price range in particular encodes
    # how far the price eventually travelled. These expanding versions use only
    # candles up to and including the current one.
    df = df.sort_values(["market_ticker", "timestamp"])
    g = df.groupby("market_ticker", sort=False)

    df["pit_cum_volume"] = g["volume_fp"].cumsum()
    df["pit_avg_spread"] = g["spread"].expanding().mean().reset_index(level=0, drop=True)
    df["pit_price_range"] = (
        g["implied_prob"].cummax() - g["implied_prob"].cummin()
    )
    df["pit_n_obs"] = g.cumcount() + 1
    df["pit_elapsed_days"] = (df["dt"] - df["open_dt"]).dt.total_seconds() / 86400

    # Keep relevant columns
    keep = [
        "market_ticker", "event_ticker", "category", "dt", "timestamp",
        "implied_prob", "result_binary", "days_to_resolution",
        "volume_fp", "open_interest_fp", "spread",
        "total_market_volume", "liquidity_bucket", "duration_hours",
        "pit_cum_volume", "pit_avg_spread", "pit_price_range",
        "pit_n_obs", "pit_elapsed_days",
    ]
    return df[[c for c in keep if c in df.columns]]


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
