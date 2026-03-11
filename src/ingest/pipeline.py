"""
Data ingestion pipeline for Kalshi research.
Pulls settled markets across all categories for calibration analysis.
"""
from __future__ import annotations

import time
from datetime import datetime
from tqdm import tqdm

from .kalshi_client import KalshiClient
from .database import (
    get_connection,
    init_db,
    upsert_events,
    upsert_markets,
    insert_candlesticks,
)


def normalize_candlesticks(candles):
    """Normalize candlestick data to dollar string fields."""
    normalized = []
    for c in candles:
        yes_bid = c.get("yes_bid") or {}
        yes_ask = c.get("yes_ask") or {}
        price = c.get("price") or {}

        def to_dollars(obj, field):
            dollar_key = field + "_dollars"
            if dollar_key in obj and obj[dollar_key] is not None:
                return obj[dollar_key]
            if field in obj and obj[field] is not None:
                try:
                    return str(float(obj[field]) / 100.0)
                except (TypeError, ValueError):
                    return str(obj[field])
            return None

        normalized.append({
            "end_period_ts": c.get("end_period_ts"),
            "yes_bid": {k: to_dollars(yes_bid, k) for k in ("open", "high", "low", "close")},
            "yes_ask": {k: to_dollars(yes_ask, k) for k in ("open", "high", "low", "close")},
            "price": {
                **{k: to_dollars(price, k) for k in ("open", "high", "low", "close")},
                "mean": to_dollars(price, "mean"),
            },
            "volume_fp": c.get("volume_fp") or str(c.get("volume", 0)),
            "open_interest_fp": c.get("open_interest_fp") or str(c.get("open_interest", 0)),
        })
    return normalized


def fetch_candlesticks_for_market(client, ticker, series_ticker, open_time, close_time):
    """Try to get daily candlesticks for a market. Returns list or empty."""
    if not open_time or not close_time:
        return []
    try:
        start_ts = int(datetime.fromisoformat(open_time.replace("Z", "+00:00")).timestamp())
        end_ts = int(datetime.fromisoformat(close_time.replace("Z", "+00:00")).timestamp())
    except (ValueError, AttributeError):
        return []

    # Try series endpoint first, then historical
    for attempt in [
        lambda: client.get_candlesticks(series_ticker, ticker, start_ts, end_ts, 1440) if series_ticker else None,
        lambda: client.get_historical_candlesticks(ticker, start_ts, end_ts, 1440),
    ]:
        try:
            data = attempt()
            if data:
                candles = data.get("candlesticks", [])
                if candles:
                    return normalize_candlesticks(candles)
        except Exception:
            pass
    return []


def ingest_diverse_settled(
    max_markets_per_category: int = 200,
    max_pages: int = 100,
    target_categories: list = None,
):
    """
    Pull settled markets across ALL categories for diverse analysis.
    Ensures we get enough data from each category to make cross-domain comparisons.
    """
    client = KalshiClient()
    init_db()
    conn = get_connection()

    # Collect all settled events
    print("Phase 1: Fetching settled events across all categories...")
    all_events = []
    all_markets_by_cat = {}
    event_to_series = {}
    cursor = None

    for page in range(max_pages):
        data = client.get_events(status="settled", with_nested_markets=True, cursor=cursor)
        events = data.get("events", [])
        if not events:
            break

        for event in events:
            cat = event.get("category") or "unknown"
            event_to_series[event["event_ticker"]] = event.get("series_ticker", "")

            for m in event.get("markets", []):
                if m.get("market_type") == "binary" and m.get("result") in ("yes", "no"):
                    if cat not in all_markets_by_cat:
                        all_markets_by_cat[cat] = []
                    all_markets_by_cat[cat].append((event, m))

        all_events.extend(events)
        cursor = data.get("cursor")
        if not cursor:
            break

        if (page + 1) % 10 == 0:
            cat_summary = {k: len(v) for k, v in all_markets_by_cat.items()}
            print(f"  Page {page+1}: {len(all_events)} events, categories: {cat_summary}")

        # Check if we have enough diversity
        if target_categories:
            have_enough = all(
                len(all_markets_by_cat.get(c, [])) >= max_markets_per_category
                for c in target_categories
            )
            if have_enough:
                print(f"  Reached target for all categories at page {page+1}")
                break

    # Summary
    print(f"\nCollected {len(all_events)} events across {len(all_markets_by_cat)} categories:")
    for cat, markets in sorted(all_markets_by_cat.items(), key=lambda x: -len(x[1])):
        print(f"  {cat:30s} {len(markets):5d} markets")

    # Select markets: top by volume per category, up to max_per_cat
    selected = []
    for cat, pairs in all_markets_by_cat.items():
        pairs.sort(key=lambda p: float(p[1].get("volume_fp", "0") or "0"), reverse=True)
        chosen = pairs[:max_markets_per_category]
        selected.extend(chosen)
        print(f"  Selected {len(chosen)} from {cat}")

    print(f"\nTotal selected: {len(selected)} markets")

    # Store events and markets
    seen_events = set()
    for event, market in selected:
        if event["event_ticker"] not in seen_events:
            upsert_events(conn, [event])
            seen_events.add(event["event_ticker"])
    upsert_markets(conn, [m for _, m in selected])

    # Phase 2: Candlesticks
    print("\nPhase 2: Fetching daily candlesticks...")
    success = errors = 0
    for event, market in tqdm(selected, desc="Candlesticks"):
        ticker = market["ticker"]
        series = event_to_series.get(market.get("event_ticker", ""), "")
        open_time = market.get("open_time")
        close_time = market.get("close_time") or market.get("settlement_ts")

        candles = fetch_candlesticks_for_market(client, ticker, series, open_time, close_time)
        if candles:
            insert_candlesticks(conn, ticker, candles, 1440)
            success += 1
        else:
            errors += 1

    print(f"\nDone: {success} with candlesticks, {errors} without")
    for table in ["events", "markets", "price_history"]:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {cur.fetchone()[0]} rows")
    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Kalshi data ingestion")
    parser.add_argument("--max-per-cat", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=100)
    args = parser.parse_args()

    ingest_diverse_settled(
        max_markets_per_category=args.max_per_cat,
        max_pages=args.max_pages,
        target_categories=[
            "Politics", "Economics", "Sports", "Entertainment",
            "Climate and Weather", "Financials", "Elections",
            "Science and Technology", "Crypto", "World",
        ],
    )
