"""
Export analysis data as JSON files for the React dashboard.
Copies JSON files into dashboard/public/data/ for static serving.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from src.ingest.database import get_connection

DATA_DIR = Path("data")
DASHBOARD_DATA_DIR = Path("dashboard/public/data")


def export():
    DASHBOARD_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Copy summary and dashboard_data JSON
    for fname in ["summary.json", "dashboard_data.json"]:
        src = DATA_DIR / fname
        if src.exists():
            shutil.copy(src, DASHBOARD_DATA_DIR / fname)
            print(f"Copied {fname}")

    # Export market_features as JSON
    conn = get_connection()
    try:
        features = pd.read_sql_query("SELECT * FROM market_features", conn)
    except Exception:
        csv = DATA_DIR / "market_features.csv"
        if csv.exists():
            features = pd.read_csv(csv)
        else:
            print("No market_features data found")
            return

    # Convert to JSON-friendly format, replacing NaN with None (null in JSON)
    import math

    records = features.to_dict(orient="records")
    for record in records:
        for key, val in record.items():
            if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                record[key] = None
    out_path = DASHBOARD_DATA_DIR / "market_features.json"
    with open(out_path, "w") as f:
        json.dump(records, f, default=str)
    print(f"Exported {len(records)} markets to {out_path}")

    conn.close()


if __name__ == "__main__":
    export()
