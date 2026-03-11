from __future__ import annotations
"""
Market design and pricing dynamics analysis.

Covers:
- How does contract structure (multi-market events vs single) affect accuracy?
- Duration effects: do longer-lived markets converge better?
- Mutual exclusivity constraints and information flow between linked markets
- Opening price dynamics: where do markets start vs where they end?
- Actionable insights for platform design
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

PLOTS_DIR = Path(__file__).parent.parent.parent / "data" / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)


def analyze_event_structure(conn) -> pd.DataFrame:
    """
    How does the number of markets per event affect accuracy?
    Mutually exclusive events (only one can be YES) vs independent markets.
    """
    query = """
        SELECT m.ticker, m.result, m.event_ticker,
               CAST(m.volume_fp AS REAL) as volume,
               CAST(m.last_price_dollars AS REAL) as last_price,
               e.mutually_exclusive, e.title as event_title,
               (SELECT COUNT(*) FROM markets m2
                WHERE m2.event_ticker = m.event_ticker
                AND m2.result IN ('yes','no')) as n_markets_in_event
        FROM markets m
        JOIN events e ON m.event_ticker = e.event_ticker
        WHERE m.result IN ('yes', 'no')
          AND m.last_price_dollars IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    df["result_binary"] = (df["result"] == "yes").astype(int)
    df["brier"] = (df["last_price"] - df["result_binary"]) ** 2
    return df


def analyze_duration_effects(conn) -> pd.DataFrame:
    """
    Do longer-lived markets produce better final forecasts?
    """
    query = """
        SELECT m.ticker, m.result,
               CAST(m.volume_fp AS REAL) as volume,
               CAST(m.last_price_dollars AS REAL) as last_price,
               julianday(m.close_time) - julianday(m.open_time) as duration_days,
               (SELECT COUNT(*) FROM price_history ph
                WHERE ph.market_ticker = m.ticker) as n_observations
        FROM markets m
        WHERE m.result IN ('yes', 'no')
          AND m.last_price_dollars IS NOT NULL
          AND m.open_time IS NOT NULL
          AND m.close_time IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    df["result_binary"] = (df["result"] == "yes").astype(int)
    df["brier"] = (df["last_price"] - df["result_binary"]) ** 2
    return df


def analyze_price_paths(conn) -> pd.DataFrame:
    """
    Opening price dynamics: where do markets open vs where they close?
    How much does the first price predict the outcome?
    """
    query = """
        SELECT ph.market_ticker,
               ph.price_close as price,
               ph.timestamp,
               ph.volume_fp,
               m.result,
               m.close_time,
               ROW_NUMBER() OVER (PARTITION BY ph.market_ticker ORDER BY ph.timestamp ASC) as day_num,
               ROW_NUMBER() OVER (PARTITION BY ph.market_ticker ORDER BY ph.timestamp DESC) as days_from_end
        FROM price_history ph
        JOIN markets m ON ph.market_ticker = m.ticker
        WHERE m.result IN ('yes', 'no')
          AND ph.period_interval = 1440
          AND ph.price_close IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["volume_fp"] = pd.to_numeric(df["volume_fp"], errors="coerce")
    df["result_binary"] = (df["result"] == "yes").astype(int)
    return df


def run_market_design_analysis(conn):
    """Run all market design analyses and generate plots + findings."""

    findings = []

    # ─── Analysis: Event structure ───
    print("\n--- Event Structure & Contract Design ---")
    ev = analyze_event_structure(conn)

    # Single vs multi-market events
    single = ev[ev["n_markets_in_event"] == 1]
    multi = ev[ev["n_markets_in_event"] > 1]

    if len(single) > 5 and len(multi) > 5:
        bs_single = single["brier"].mean()
        bs_multi = multi["brier"].mean()
        print(f"  Single-market events: Brier={bs_single:.4f} (n={len(single)})")
        print(f"  Multi-market events:  Brier={bs_multi:.4f} (n={len(multi)})")
        findings.append({
            "finding": "event_structure",
            "single_market_brier": round(bs_single, 4),
            "multi_market_brier": round(bs_multi, 4),
            "single_n": len(single),
            "multi_n": len(multi),
        })

    # Mutually exclusive vs independent
    exclusive = ev[ev["mutually_exclusive"] == 1]
    independent = ev[ev["mutually_exclusive"] == 0]

    if len(exclusive) > 5 and len(independent) > 5:
        bs_ex = exclusive["brier"].mean()
        bs_ind = independent["brier"].mean()
        print(f"  Mutually exclusive:   Brier={bs_ex:.4f} (n={len(exclusive)})")
        print(f"  Independent:          Brier={bs_ind:.4f} (n={len(independent)})")
        findings.append({
            "finding": "mutual_exclusivity",
            "exclusive_brier": round(bs_ex, 4),
            "independent_brier": round(bs_ind, 4),
            "exclusive_n": len(exclusive),
            "independent_n": len(independent),
        })

    # Accuracy by event size
    ev["size_bucket"] = pd.cut(
        ev["n_markets_in_event"],
        bins=[0, 1, 3, 10, 100],
        labels=["1 market", "2-3 markets", "4-10 markets", "10+ markets"],
    )
    size_stats = ev.groupby("size_bucket", observed=True).agg(
        brier=("brier", "mean"),
        volume=("volume", "mean"),
        count=("ticker", "count"),
    ).reset_index()

    print("\n  Accuracy by event size:")
    for _, row in size_stats.iterrows():
        print(f"    {row['size_bucket']:15s} Brier={row['brier']:.4f}  avg_vol={row['volume']:,.0f}  n={row['count']}")

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    sns.barplot(data=size_stats, x="size_bucket", y="brier", ax=ax1, color="#2563eb")
    ax1.set_title("Forecast Accuracy by Event Size", fontsize=14)
    ax1.set_xlabel("Markets per Event")
    ax1.set_ylabel("Brier Score (lower = better)")
    ax1.grid(True, alpha=0.3)

    sns.barplot(data=size_stats, x="size_bucket", y="volume", ax=ax2, color="#10b981")
    ax2.set_title("Average Volume by Event Size", fontsize=14)
    ax2.set_xlabel("Markets per Event")
    ax2.set_ylabel("Average Volume")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "event_structure.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved event_structure.png")

    # ─── Analysis: Duration effects ───
    print("\n--- Duration Effects ---")
    dur = analyze_duration_effects(conn)
    dur["duration_bucket"] = pd.cut(
        dur["duration_days"],
        bins=[0, 7, 30, 90, 365, 10000],
        labels=["<1 week", "1-4 weeks", "1-3 months", "3-12 months", "1+ year"],
    )

    dur_stats = dur.groupby("duration_bucket", observed=True).agg(
        brier=("brier", "mean"),
        volume=("volume", "mean"),
        count=("ticker", "count"),
    ).reset_index()

    print("  Accuracy by market duration:")
    for _, row in dur_stats.iterrows():
        print(f"    {row['duration_bucket']:15s} Brier={row['brier']:.4f}  avg_vol={row['volume']:,.0f}  n={row['count']}")

    findings.append({
        "finding": "duration_effects",
        "buckets": dur_stats.to_dict(orient="records"),
    })

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = ["#ef4444", "#f59e0b", "#10b981", "#2563eb", "#8b5cf6"]
    bars = ax.bar(range(len(dur_stats)), dur_stats["brier"], color=colors[:len(dur_stats)])
    ax.set_xticks(range(len(dur_stats)))
    ax.set_xticklabels(dur_stats["duration_bucket"], rotation=15)
    ax.set_ylabel("Brier Score (lower = better)")
    ax.set_title("Forecast Accuracy by Market Duration", fontsize=14)
    ax.grid(True, alpha=0.3, axis="y")
    for bar, row in zip(bars, dur_stats.itertuples()):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002,
                f"n={row.count}", ha="center", fontsize=9, color="#666")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "duration_effects.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved duration_effects.png")

    # ─── Analysis: Opening price as predictor ───
    print("\n--- Opening Price Dynamics ---")
    paths = analyze_price_paths(conn)

    # First observed price vs outcome
    first_prices = paths[paths["day_num"] == 1][["market_ticker", "price", "result_binary"]].copy()
    first_prices.rename(columns={"price": "opening_price"}, inplace=True)

    # Last observed price vs outcome
    last_prices = paths[paths["days_from_end"] == 1][["market_ticker", "price"]].copy()
    last_prices.rename(columns={"price": "closing_price"}, inplace=True)

    merged = first_prices.merge(last_prices, on="market_ticker")
    merged = merged.dropna()

    if len(merged) > 10:
        brier_open = np.mean((merged["opening_price"] - merged["result_binary"]) ** 2)
        brier_close = np.mean((merged["closing_price"] - merged["result_binary"]) ** 2)
        price_change = (merged["closing_price"] - merged["opening_price"]).abs().mean()

        print(f"  Opening price Brier:  {brier_open:.4f}")
        print(f"  Closing price Brier:  {brier_close:.4f}")
        print(f"  Improvement:          {((brier_open - brier_close) / brier_open * 100):.1f}%")
        print(f"  Avg absolute price change: {price_change:.3f}")

        findings.append({
            "finding": "opening_price_dynamics",
            "opening_brier": round(brier_open, 4),
            "closing_brier": round(brier_close, 4),
            "improvement_pct": round((brier_open - brier_close) / brier_open * 100, 1),
            "avg_price_change": round(price_change, 4),
            "n": len(merged),
        })

        # Opening vs closing price scatter
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        yes_markets = merged[merged["result_binary"] == 1]
        no_markets = merged[merged["result_binary"] == 0]

        ax1.scatter(yes_markets["opening_price"], yes_markets["closing_price"],
                   alpha=0.5, s=20, c="#10b981", label="Resolved YES")
        ax1.scatter(no_markets["opening_price"], no_markets["closing_price"],
                   alpha=0.5, s=20, c="#ef4444", label="Resolved NO")
        ax1.plot([0, 1], [0, 1], "k--", alpha=0.3, label="No change")
        ax1.set_xlabel("Opening Price")
        ax1.set_ylabel("Closing Price")
        ax1.set_title("Price Discovery: Open vs Close", fontsize=14)
        ax1.legend(fontsize=9)
        ax1.grid(True, alpha=0.3)

        # How much information is in the opening price?
        bins = np.linspace(0, 1, 6)
        merged["open_bin"] = pd.cut(merged["opening_price"], bins=bins)
        open_cal = merged.groupby("open_bin", observed=True).agg(
            mean_open=("opening_price", "mean"),
            actual_yes=("result_binary", "mean"),
            n=("market_ticker", "count"),
        ).reset_index()

        ax2.plot([0, 1], [0, 1], "k--", alpha=0.3, label="Perfect")
        ax2.scatter(open_cal["mean_open"], open_cal["actual_yes"],
                   s=open_cal["n"] * 3, c="#2563eb", alpha=0.7, edgecolors="white")
        ax2.plot(open_cal["mean_open"], open_cal["actual_yes"], "-", alpha=0.5, color="#2563eb")
        ax2.set_xlabel("Opening Price (implied probability)")
        ax2.set_ylabel("Realized Frequency")
        ax2.set_title("Opening Price Calibration", fontsize=14)
        ax2.set_xlim(-0.05, 1.05)
        ax2.set_ylim(-0.05, 1.05)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(PLOTS_DIR / "opening_price_dynamics.png", dpi=150, bbox_inches="tight")
        plt.close()
        print("  Saved opening_price_dynamics.png")

    # ─── Volume concentration analysis ───
    print("\n--- Volume Concentration (Market Design) ---")
    vol_data = paths.groupby("market_ticker").agg(
        total_vol=("volume_fp", "sum"),
        n_days=("timestamp", "count"),
    ).reset_index()
    vol_data = vol_data[vol_data["total_vol"] > 0].sort_values("total_vol", ascending=False)

    if len(vol_data) > 10:
        top_10_pct = vol_data.head(int(len(vol_data) * 0.1))["total_vol"].sum()
        total_vol = vol_data["total_vol"].sum()
        concentration = top_10_pct / total_vol * 100

        print(f"  Top 10% of markets account for {concentration:.0f}% of total volume")
        print(f"  Median market volume: {vol_data['total_vol'].median():,.0f}")
        print(f"  Mean market volume: {vol_data['total_vol'].mean():,.0f}")

        findings.append({
            "finding": "volume_concentration",
            "top_10pct_share": round(concentration, 1),
            "median_volume": round(vol_data["total_vol"].median()),
            "mean_volume": round(vol_data["total_vol"].mean()),
            "n_markets": len(vol_data),
        })

    # Save findings
    import json
    findings_path = Path("data/market_design_findings.json")
    with open(findings_path, "w") as f:
        json.dump(findings, f, indent=2, default=str)
    print(f"\nSaved findings to {findings_path}")

    return findings


if __name__ == "__main__":
    from src.ingest.database import get_connection
    conn = get_connection()
    run_market_design_analysis(conn)
    conn.close()
