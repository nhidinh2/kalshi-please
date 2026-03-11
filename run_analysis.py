#!/usr/bin/env python3
"""
Main entry point for the Kalshi research pipeline.

Research question: Do Kalshi prices mean the same thing across categories
and time horizons, or do some markets need recalibration?

Usage:
    python run_analysis.py --ingest          # Pull data from Kalshi API
    python run_analysis.py --features        # Compute features
    python run_analysis.py --analyze         # Run analysis + plots
    python run_analysis.py --export          # Export JSON for dashboard
    python run_analysis.py --all             # Everything
"""

import argparse
import json
from pathlib import Path

from src.ingest.database import get_connection, init_db


def run_ingest(max_per_cat=150, max_pages=80):
    from src.ingest.pipeline import ingest_diverse_settled
    print("=" * 60)
    print("PHASE 1: Data Collection (diverse categories)")
    print("=" * 60)
    ingest_diverse_settled(
        max_markets_per_category=max_per_cat,
        max_pages=max_pages,
        target_categories=[
            "Politics", "Economics", "Sports", "Entertainment",
            "Climate and Weather", "Financials", "Elections",
            "Science and Technology", "Crypto", "World",
        ],
    )


def run_features():
    import pandas as pd
    from src.processing.features import compute_market_features, build_calibration_dataset

    print("=" * 60)
    print("PHASE 2: Feature Engineering")
    print("=" * 60)
    conn = get_connection()

    features = compute_market_features(conn)
    print(f"  {len(features)} markets with features")
    print(f"  Categories: {features['category'].value_counts().to_dict()}")
    features.to_sql("market_features", conn, if_exists="replace", index=False)
    features.to_csv("data/market_features.csv", index=False)

    cal_ds = build_calibration_dataset(conn)
    print(f"  {len(cal_ds)} calibration observations")
    print(f"  Categories: {cal_ds['category'].value_counts().to_dict()}")
    cal_ds.to_sql("calibration_dataset", conn, if_exists="replace", index=False)
    cal_ds.to_csv("data/calibration_dataset.csv", index=False)

    conn.close()


def run_analysis():
    import pandas as pd
    from src.analysis.calibration import (
        analysis_overall,
        analysis_accuracy_over_time,
        analysis_domain_time,
        analysis_liquidity,
        analysis_explanatory,
        analysis_regression,
        analysis_recalibration,
        analysis_adjusted_model,
        compute_summary_stats,
    )

    print("=" * 60)
    print("PHASE 3: Research Analysis")
    print("=" * 60)
    conn = get_connection()

    features = pd.read_sql_query("SELECT * FROM market_features", conn)
    cal_ds = pd.read_sql_query("SELECT * FROM calibration_dataset", conn)
    print(f"Loaded {len(features)} markets, {len(cal_ds)} observations\n")

    # Run all analyses
    overall = analysis_overall(features)
    time_results = analysis_accuracy_over_time(cal_ds)
    domain_matrix = analysis_domain_time(cal_ds)
    liq_results = analysis_liquidity(cal_ds, features)
    explanatory = analysis_explanatory(features)
    regression = analysis_regression(cal_ds, features)
    recalibration = analysis_recalibration(cal_ds, features)
    adjusted = analysis_adjusted_model(cal_ds, features)
    summary = compute_summary_stats(features, cal_ds)

    # Save outputs for dashboard
    def to_serializable(obj):
        """Convert numpy/pandas types for JSON."""
        import math
        import numpy as np
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating, float)):
            v = float(obj)
            if math.isnan(v) or math.isinf(v):
                return None
            return round(v, 6)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient="records")
        if isinstance(obj, np.bool_):
            return bool(obj)
        return str(obj)

    def sanitize_nans(obj):
        """Recursively replace NaN/Inf with None in nested structures."""
        import math
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: sanitize_nans(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize_nans(v) for v in obj]
        return obj

    # Summary JSON
    with open("data/summary.json", "w") as f:
        json.dump(sanitize_nans(summary), f, indent=2, default=to_serializable)

    # Dashboard data JSON
    dashboard_data = {
        "overall_calibration": overall["calibration"].to_dict(orient="records"),
        "time_horizon_calibration": {
            k: v.to_dict(orient="records") for k, v in time_results.items()
        },
        "liquidity_calibration": {
            k: v.to_dict(orient="records") for k, v in liq_results.items()
        },
        "domain_time_matrix": {},
    }
    for cat, horizons in domain_matrix.items():
        dashboard_data["domain_time_matrix"][cat] = {}
        for horizon, entry in horizons.items():
            if entry is not None:
                dashboard_data["domain_time_matrix"][cat][horizon] = {
                    "brier": entry["brier"],
                    "log_loss": entry["log_loss"],
                    "abs_error": entry["abs_error"],
                    "n": entry["n"],
                    "n_markets": entry["n_markets"],
                    "cal_curve": entry["cal_curve"].to_dict(orient="records"),
                }

    dashboard_data["regression"] = regression
    dashboard_data["recalibration"] = recalibration
    dashboard_data["adjusted_model"] = adjusted

    dashboard_data["explanatory"] = {
        "correlations": explanatory["correlations"],
        "category_profiles": explanatory["category_profiles"],
        "regression_r2": explanatory["regression_r2"],
        "regression_coefficients": explanatory["regression_coefficients"],
        "category_correlations": explanatory["category_correlations"],
        "narratives": explanatory["narratives"],
    }

    with open("data/dashboard_data.json", "w") as f:
        json.dump(sanitize_nans(dashboard_data), f, indent=2, default=to_serializable)

    print("\nSaved summary.json and dashboard_data.json")
    conn.close()


def run_export():
    import math
    import json
    import shutil
    import pandas as pd

    print("=" * 60)
    print("PHASE 4: Export for Dashboard")
    print("=" * 60)

    out_dir = Path("dashboard/public/data")
    out_dir.mkdir(parents=True, exist_ok=True)

    for fname in ["summary.json", "dashboard_data.json"]:
        src = Path("data") / fname
        if src.exists():
            shutil.copy(src, out_dir / fname)
            print(f"  Copied {fname}")

    conn = get_connection()
    features = pd.read_sql_query("SELECT * FROM market_features", conn)
    records = features.to_dict(orient="records")
    for record in records:
        for key, val in record.items():
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                record[key] = None
    with open(out_dir / "market_features.json", "w") as f:
        json.dump(records, f, default=str)
    print(f"  Exported {len(records)} markets to market_features.json")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kalshi research pipeline")
    parser.add_argument("--ingest", action="store_true")
    parser.add_argument("--features", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--max-per-cat", type=int, default=150)
    parser.add_argument("--max-pages", type=int, default=80)
    args = parser.parse_args()

    if args.all:
        args.ingest = args.features = args.analyze = args.export = True

    if not any([args.ingest, args.features, args.analyze, args.export]):
        parser.print_help()
        exit(1)

    if args.ingest:
        run_ingest(args.max_per_cat, args.max_pages)
    if args.features:
        run_features()
    if args.analyze:
        run_analysis()
    if args.export:
        run_export()

    print("\nDone!")
