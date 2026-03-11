"""
Kalshi API client for public data endpoints.
No authentication required for the endpoints we use.
"""

import time
import requests
from typing import Optional



BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

# Rate limit: 20 reads/sec for basic tier, stay well under
RATE_LIMIT_DELAY = 0.1  # 100ms between requests


class KalshiClient:
    """Client for Kalshi public API endpoints."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
        })
        self._last_request_time = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_request_time = time.time()

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        self._rate_limit()
        url = f"{BASE_URL}{path}"
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def get_events(
        self,
        status: Optional[str] = None,
        series_ticker: Optional[str] = None,
        with_nested_markets: bool = False,
        limit: int = 200,
        cursor: Optional[str] = None,
    ) -> dict:
        params = {"limit": limit, "with_nested_markets": with_nested_markets}
        if status:
            params["status"] = status
        if series_ticker:
            params["series_ticker"] = series_ticker
        if cursor:
            params["cursor"] = cursor
        return self._get("/events", params)

    def get_all_events(
        self,
        status: Optional[str] = None,
        series_ticker: Optional[str] = None,
        with_nested_markets: bool = False,
    ) -> list[dict]:
        """Paginate through all events matching the filter."""
        all_events = []
        cursor = None
        while True:
            data = self.get_events(
                status=status,
                series_ticker=series_ticker,
                with_nested_markets=with_nested_markets,
                cursor=cursor,
            )
            events = data.get("events", [])
            if not events:
                break
            all_events.extend(events)
            cursor = data.get("cursor")
            if not cursor:
                break
        return all_events

    def get_markets(
        self,
        event_ticker: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 1000,
        cursor: Optional[str] = None,
        tickers: Optional[str] = None,
    ) -> dict:
        params = {"limit": limit}
        if event_ticker:
            params["event_ticker"] = event_ticker
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        if tickers:
            params["tickers"] = tickers
        return self._get("/markets", params)

    def get_all_markets(
        self,
        event_ticker: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        """Paginate through all markets matching the filter."""
        all_markets = []
        cursor = None
        while True:
            data = self.get_markets(
                event_ticker=event_ticker,
                status=status,
                cursor=cursor,
            )
            markets = data.get("markets", [])
            if not markets:
                break
            all_markets.extend(markets)
            cursor = data.get("cursor")
            if not cursor:
                break
        return all_markets

    def get_series(self, category: Optional[str] = None) -> dict:
        params = {}
        if category:
            params["category"] = category
        return self._get("/series", params)

    def get_candlesticks(
        self,
        series_ticker: str,
        ticker: str,
        start_ts: int,
        end_ts: int,
        period_interval: int = 1440,  # daily by default
    ) -> dict:
        """Get candlestick data for an active market."""
        params = {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": period_interval,
        }
        return self._get(
            f"/series/{series_ticker}/markets/{ticker}/candlesticks",
            params,
        )

    def get_historical_candlesticks(
        self,
        ticker: str,
        start_ts: int,
        end_ts: int,
        period_interval: int = 1440,
    ) -> dict:
        """Get candlestick data for archived/settled markets."""
        params = {
            "start_ts": start_ts,
            "end_ts": end_ts,
            "period_interval": period_interval,
        }
        return self._get(
            f"/historical/markets/{ticker}/candlesticks",
            params,
        )

    def get_trades(
        self,
        ticker: Optional[str] = None,
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
        limit: int = 1000,
        cursor: Optional[str] = None,
    ) -> dict:
        params = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts
        if cursor:
            params["cursor"] = cursor
        return self._get("/markets/trades", params)

    def get_historical_trades(
        self,
        ticker: Optional[str] = None,
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
        limit: int = 1000,
        cursor: Optional[str] = None,
    ) -> dict:
        params = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts
        if cursor:
            params["cursor"] = cursor
        return self._get("/historical/trades", params)
