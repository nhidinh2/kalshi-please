from __future__ import annotations
"""
Core research analysis: Do Kalshi prices mean the same thing across
categories and time horizons, or do some markets need recalibration?

Four analyses:
  A. Accuracy over time (Brier score, log loss, abs error at different horizons)
  B. Domain x time interaction (is 70c in politics = 70c in weather at 7 days?)
  C. Liquidity / volume effect on calibration
  D. Why do calibration differences exist? (explanatory analysis)
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats as scipy_stats
from pathlib import Path

PLOTS_DIR = Path(__file__).parent.parent.parent / "data" / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

# Time horizons for analysis
TIME_HORIZONS = [
    ("30+ days", 30, float("inf")),
    ("7-30 days", 7, 30),
    ("1-7 days", 1, 7),
    ("< 24 hours", 0, 1),
]

# Colors
CAT_COLORS = {
    "Politics": "#2563eb",
    "Economics": "#10b981",
    "Sports": "#ef4444",
    "Entertainment": "#f59e0b",
    "Climate and Weather": "#06b6d4",
    "Elections": "#8b5cf6",
    "Financials": "#ec4899",
    "Crypto": "#f97316",
    "Companies": "#84cc16",
    "World": "#6366f1",
    "Mentions": "#14b8a6",
    "Science and Technology": "#a855f7",
    "Social": "#78716c",
}

TIME_COLORS = {
    "30+ days": "#ef4444",
    "7-30 days": "#f59e0b",
    "1-7 days": "#10b981",
    "< 24 hours": "#2563eb",
}

LIQ_COLORS = {"low": "#ef4444", "medium": "#f59e0b", "high": "#10b981"}


# ──────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────

def brier_score(predicted, actual):
    return np.mean((np.array(predicted) - np.array(actual)) ** 2)

def log_loss(predicted, actual, eps=1e-7):
    p = np.clip(predicted, eps, 1 - eps)
    return -np.mean(actual * np.log(p) + (1 - actual) * np.log(1 - p))

def abs_error(predicted, actual):
    return np.mean(np.abs(np.array(predicted) - np.array(actual)))

def calibration_curve(predicted, actual, n_bins=10):
    """Bin predictions, compare to realized frequency."""
    predicted = np.array(predicted)
    actual = np.array(actual)
    bins = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.clip(np.digitize(predicted, bins) - 1, 0, n_bins - 1)

    rows = []
    for i in range(n_bins):
        mask = bin_indices == i
        if mask.sum() == 0:
            continue
        rows.append({
            "bin_center": (bins[i] + bins[i + 1]) / 2,
            "mean_predicted": predicted[mask].mean(),
            "realized_frequency": actual[mask].mean(),
            "count": int(mask.sum()),
            "calibration_error": abs(predicted[mask].mean() - actual[mask].mean()),
        })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
# Analysis A: Accuracy over time
# ──────────────────────────────────────────────

def analysis_accuracy_over_time(cal_ds):
    """How does forecast accuracy change as markets approach resolution?"""
    print("\n" + "=" * 60)
    print("ANALYSIS A: Accuracy Over Time")
    print("=" * 60)

    results = {}
    for label, min_d, max_d in TIME_HORIZONS:
        mask = (cal_ds["days_to_resolution"] >= min_d) & (cal_ds["days_to_resolution"] < max_d)
        subset = cal_ds[mask]
        if len(subset) < 20:
            continue

        pred = subset["implied_prob"].values
        actual = subset["result_binary"].values
        bs = brier_score(pred, actual)
        ll = log_loss(pred, actual)
        ae = abs_error(pred, actual)
        cal = calibration_curve(pred, actual)
        cal["time_horizon"] = label
        cal["brier_score"] = bs
        cal["log_loss"] = ll
        cal["abs_error"] = ae
        cal["n_observations"] = len(subset)
        cal["n_markets"] = subset["market_ticker"].nunique()

        results[label] = cal
        print(f"  {label:15s}  Brier={bs:.4f}  LogLoss={ll:.4f}  AbsErr={ae:.4f}  n={len(subset)} ({subset['market_ticker'].nunique()} markets)")

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    ax1.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Perfect")
    for label, cal in results.items():
        ax1.plot(cal["mean_predicted"], cal["realized_frequency"], "o-",
                color=TIME_COLORS.get(label, "#666"), label=f"{label} (BS={cal['brier_score'].iloc[0]:.4f})",
                markersize=5, alpha=0.8)
    ax1.set_xlabel("Predicted Probability")
    ax1.set_ylabel("Realized Frequency")
    ax1.set_title("Calibration by Time to Resolution")
    ax1.legend(fontsize=8)
    ax1.set_xlim(-0.02, 1.02)
    ax1.set_ylim(-0.02, 1.02)
    ax1.grid(True, alpha=0.3)

    # Bar chart of metrics
    labels = list(results.keys())
    briers = [results[l]["brier_score"].iloc[0] for l in labels]
    colors = [TIME_COLORS.get(l, "#666") for l in labels]
    ax2.bar(range(len(labels)), briers, color=colors)
    ax2.set_xticks(range(len(labels)))
    ax2.set_xticklabels(labels, rotation=15, fontsize=9)
    ax2.set_ylabel("Brier Score (lower = better)")
    ax2.set_title("Forecast Error by Horizon")
    ax2.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "accuracy_over_time.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved accuracy_over_time.png")

    return results


# ──────────────────────────────────────────────
# Analysis B: Domain x Time Interaction
# ──────────────────────────────────────────────

def analysis_domain_time(cal_ds, min_obs=30):
    """
    The core question: is a 70-cent contract in politics 7 days out
    'equivalent' to a 70-cent contract in weather 7 days out?
    """
    print("\n" + "=" * 60)
    print("ANALYSIS B: Domain x Time Interaction")
    print("=" * 60)

    categories = cal_ds["category"].value_counts()
    # Only categories with enough data
    valid_cats = categories[categories >= min_obs * 2].index.tolist()
    print(f"  Categories with enough data: {valid_cats}")

    # Build the domain x time matrix
    matrix = {}
    for cat in valid_cats:
        cat_data = cal_ds[cal_ds["category"] == cat]
        matrix[cat] = {}
        for label, min_d, max_d in TIME_HORIZONS:
            mask = (cat_data["days_to_resolution"] >= min_d) & (cat_data["days_to_resolution"] < max_d)
            subset = cat_data[mask]
            if len(subset) < min_obs:
                matrix[cat][label] = None
                continue

            pred = subset["implied_prob"].values
            actual = subset["result_binary"].values
            matrix[cat][label] = {
                "brier": brier_score(pred, actual),
                "log_loss": log_loss(pred, actual),
                "abs_error": abs_error(pred, actual),
                "n": len(subset),
                "n_markets": subset["market_ticker"].nunique(),
                "cal_curve": calibration_curve(pred, actual),
            }

    # Print matrix
    print(f"\n  {'Category':25s}", end="")
    for label, _, _ in TIME_HORIZONS:
        print(f"  {label:>12s}", end="")
    print()
    print("  " + "-" * 75)
    for cat in valid_cats:
        print(f"  {cat:25s}", end="")
        for label, _, _ in TIME_HORIZONS:
            entry = matrix[cat].get(label)
            if entry:
                print(f"  {entry['brier']:>12.4f}", end="")
            else:
                print(f"  {'---':>12s}", end="")
        print()

    # Calibration curves by category (at 7-30 day horizon for comparison)
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    for idx, (label, min_d, max_d) in enumerate(TIME_HORIZONS):
        ax = axes[idx // 2][idx % 2]
        ax.plot([0, 1], [0, 1], "k--", alpha=0.4)

        for cat in valid_cats:
            entry = matrix[cat].get(label)
            if entry is None:
                continue
            cal = entry["cal_curve"]
            color = CAT_COLORS.get(cat, "#666")
            ax.plot(cal["mean_predicted"], cal["realized_frequency"], "o-",
                   color=color, label=f"{cat} (BS={entry['brier']:.3f}, n={entry['n']})",
                   markersize=4, alpha=0.7)

        ax.set_xlabel("Predicted Probability")
        ax.set_ylabel("Realized Frequency")
        ax.set_title(f"Calibration at {label}")
        ax.legend(fontsize=6, loc="upper left")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.grid(True, alpha=0.3)

    plt.suptitle("Do Kalshi Prices Mean the Same Thing Across Categories?", fontsize=14, y=1.01)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "domain_time_interaction.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved domain_time_interaction.png")

    # Heatmap: Brier score by category x time
    heatmap_data = []
    for cat in valid_cats:
        row = {"category": cat}
        for label, _, _ in TIME_HORIZONS:
            entry = matrix[cat].get(label)
            row[label] = entry["brier"] if entry else np.nan
        heatmap_data.append(row)

    hm_df = pd.DataFrame(heatmap_data).set_index("category")
    if len(hm_df) > 1:
        fig, ax = plt.subplots(figsize=(10, max(6, len(hm_df) * 0.6)))
        sns.heatmap(hm_df, annot=True, fmt=".3f", cmap="RdYlGn_r",
                   ax=ax, vmin=0, vmax=0.25, linewidths=0.5)
        ax.set_title("Brier Score: Category x Time Horizon\n(lower = more accurate)", fontsize=13)
        ax.set_xlabel("Time to Resolution")
        ax.set_ylabel("")
        plt.tight_layout()
        plt.savefig(PLOTS_DIR / "domain_time_heatmap.png", dpi=150, bbox_inches="tight")
        plt.close()
        print("  Saved domain_time_heatmap.png")

    return matrix


# ──────────────────────────────────────────────
# Analysis C: Liquidity / Volume Effect
# ──────────────────────────────────────────────

def analysis_liquidity(cal_ds, market_features):
    """Do high-volume markets produce better calibrated prices?"""
    print("\n" + "=" * 60)
    print("ANALYSIS C: Liquidity / Volume Effect")
    print("=" * 60)

    results = {}
    for bucket in ["low", "medium", "high"]:
        subset = cal_ds[cal_ds["liquidity_bucket"] == bucket]
        if len(subset) < 30:
            continue

        pred = subset["implied_prob"].values
        actual = subset["result_binary"].values
        bs = brier_score(pred, actual)
        cal = calibration_curve(pred, actual)
        cal["liquidity"] = bucket
        cal["brier_score"] = bs
        cal["n_observations"] = len(subset)
        results[bucket] = cal
        print(f"  {bucket:10s}  Brier={bs:.4f}  n={len(subset)} ({subset['market_ticker'].nunique()} markets)")

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    ax1.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Perfect")
    for bucket, cal in results.items():
        ax1.plot(cal["mean_predicted"], cal["realized_frequency"], "o-",
                color=LIQ_COLORS.get(bucket, "#666"),
                label=f"{bucket} volume (BS={cal['brier_score'].iloc[0]:.4f})",
                markersize=5, alpha=0.8)
    ax1.set_xlabel("Predicted Probability")
    ax1.set_ylabel("Realized Frequency")
    ax1.set_title("Calibration by Liquidity")
    ax1.legend(fontsize=9)
    ax1.set_xlim(-0.02, 1.02)
    ax1.set_ylim(-0.02, 1.02)
    ax1.grid(True, alpha=0.3)

    # Volume vs brier scatter
    mf = market_features.dropna(subset=["total_volume", "brier_score"])
    mf = mf[mf["total_volume"] > 0]
    if len(mf) > 10:
        for cat in mf["category"].unique():
            cat_data = mf[mf["category"] == cat]
            color = CAT_COLORS.get(cat, "#999")
            ax2.scatter(cat_data["total_volume"], cat_data["brier_score"],
                       alpha=0.4, s=15, color=color, label=cat)
        ax2.set_xscale("log")
        ax2.set_xlabel("Total Volume (log scale)")
        ax2.set_ylabel("Brier Score (lower = better)")
        ax2.set_title("Volume vs Accuracy by Category")
        ax2.legend(fontsize=6, ncol=2, loc="upper right")
        ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "liquidity_effect.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved liquidity_effect.png")

    return results


# ──────────────────────────────────────────────
# Overall calibration (final prices)
# ──────────────────────────────────────────────

def analysis_overall(market_features):
    """Overall calibration using final market prices."""
    print("\n" + "=" * 60)
    print("OVERALL CALIBRATION (Final Prices)")
    print("=" * 60)

    valid = market_features.dropna(subset=["last_price", "brier_score"])
    pred = valid["last_price"].values
    actual = valid["result_binary"].values

    bs = brier_score(pred, actual)
    ll = log_loss(pred, actual)
    ae = abs_error(pred, actual)
    cal = calibration_curve(pred, actual)

    print(f"  Markets: {len(valid)}")
    print(f"  Brier Score: {bs:.4f}")
    print(f"  Log Loss: {ll:.4f}")
    print(f"  Abs Error: {ae:.4f}")

    # By category
    print("\n  By category (final prices):")
    for cat in valid["category"].value_counts().index:
        cat_data = valid[valid["category"] == cat]
        if len(cat_data) >= 5:
            cat_bs = brier_score(cat_data["last_price"].values, cat_data["result_binary"].values)
            print(f"    {cat:25s}  Brier={cat_bs:.4f}  n={len(cat_data)}")

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    ax1.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Perfect")
    ax1.scatter(cal["mean_predicted"], cal["realized_frequency"],
               s=cal["count"] / cal["count"].max() * 300,
               alpha=0.7, c="#2563eb", edgecolors="white", linewidth=1)
    ax1.plot(cal["mean_predicted"], cal["realized_frequency"], "-", alpha=0.5, color="#2563eb")
    ax1.set_xlabel("Predicted Probability")
    ax1.set_ylabel("Realized Frequency")
    ax1.set_title(f"Overall Calibration (Brier={bs:.4f})")
    ax1.legend()
    ax1.set_xlim(-0.02, 1.02)
    ax1.set_ylim(-0.02, 1.02)
    ax1.grid(True, alpha=0.3)

    ax2.bar(cal["bin_center"], cal["count"], width=0.08, alpha=0.7, color="#2563eb", edgecolor="white")
    ax2.set_xlabel("Predicted Probability")
    ax2.set_ylabel("Number of Markets")
    ax2.set_title("Distribution of Final Prices")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "overall_calibration.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved overall_calibration.png")

    return {"calibration": cal, "brier": bs, "log_loss": ll, "abs_error": ae, "n": len(valid)}


# ──────────────────────────────────────────────
# Summary stats
# ──────────────────────────────────────────────

# ──────────────────────────────────────────────
# Analysis D: Why do calibration differences exist?
# ──────────────────────────────────────────────

EXPLANATORY_FEATURES = [
    ("avg_spread", "Bid-Ask Spread"),
    ("total_volume", "Total Volume"),
    ("n_price_observations", "Price Updates"),
    ("duration_hours", "Duration (hrs)"),
    ("price_volatility", "Overall Volatility"),
    ("late_volatility", "Late Volatility"),
    ("late_price_move", "Late Price Move"),
    ("price_range", "Price Range"),
    ("late_volume_share", "Late Volume Share"),
]


def analysis_explanatory(market_features):
    """
    Analysis D: Explain WHY calibration differs across categories.
    Tests which market-level features predict poor calibration.
    """
    print("\n" + "=" * 60)
    print("ANALYSIS D: Why Do Calibration Differences Exist?")
    print("=" * 60)

    mf = market_features.dropna(subset=["brier_score", "last_price"]).copy()

    # --- 1. Correlation: each feature vs Brier score ---
    print("\n  Feature correlations with Brier score:")
    correlations = []
    for col, label in EXPLANATORY_FEATURES:
        valid = mf.dropna(subset=[col])
        if len(valid) < 20:
            continue
        r, p = scipy_stats.spearmanr(valid[col], valid["brier_score"])
        correlations.append({
            "feature": col,
            "label": label,
            "spearman_r": round(r, 4),
            "p_value": round(p, 6),
            "n": len(valid),
            "significant": p < 0.05,
        })
        sig = "*" if p < 0.05 else " "
        print(f"    {label:25s}  r={r:+.4f}  p={p:.4f} {sig}  n={len(valid)}")

    corr_df = pd.DataFrame(correlations)

    # --- 2. Category profiles: aggregate features by category ---
    print("\n  Category profiles (median values):")
    profile_cols = [c for c, _ in EXPLANATORY_FEATURES if c in mf.columns]
    profile_cols_plus = profile_cols + ["brier_score"]

    # Yes/no base rate by category
    cat_baserate = mf.groupby("category")["result_binary"].agg(["mean", "count"])
    cat_baserate.columns = ["yes_rate", "n_markets"]
    cat_baserate["base_rate_imbalance"] = abs(cat_baserate["yes_rate"] - 0.5)

    # Aggregate features by category
    cat_profiles = mf.groupby("category")[profile_cols_plus].median()
    # Use MEAN Brier (not median) — median is misleading since many markets are near 0
    cat_mean_brier = mf.groupby("category")["brier_score"].mean()
    cat_profiles["brier_score"] = cat_mean_brier
    cat_profiles = cat_profiles.join(cat_baserate)
    cat_profiles = cat_profiles.sort_values("brier_score")

    print(f"    {'Category':25s} {'Brier':>7s} {'Spread':>8s} {'Volume':>10s} {'Updates':>8s} {'LateVol':>8s} {'YesRate':>8s} {'Imbal':>7s}")
    print("    " + "-" * 90)
    for cat, row in cat_profiles.iterrows():
        print(f"    {cat:25s} {row['brier_score']:7.4f} {row.get('avg_spread', 0):8.4f} "
              f"{row.get('total_volume', 0):10.0f} {row.get('n_price_observations', 0):8.0f} "
              f"{row.get('late_volatility', 0):8.4f} {row.get('yes_rate', 0):8.3f} "
              f"{row.get('base_rate_imbalance', 0):7.3f}")

    # --- 3. Multivariate: which features jointly predict Brier? ---
    # Only use features with enough non-null values
    reg_cols = []
    for c, _ in EXPLANATORY_FEATURES:
        if c in mf.columns and mf[c].notna().sum() > len(mf) * 0.5:
            reg_cols.append(c)
    reg_data = mf[reg_cols + ["brier_score"]].dropna()

    if len(reg_data) > 50:
        # Standardize features for comparable coefficients
        from sklearn.preprocessing import StandardScaler
        from sklearn.linear_model import LinearRegression

        X = reg_data[reg_cols].values
        y = reg_data["brier_score"].values

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        model = LinearRegression()
        model.fit(X_scaled, y)
        r2 = model.score(X_scaled, y)

        print(f"\n  Linear regression (standardized features → Brier):")
        print(f"    R² = {r2:.4f} ({r2*100:.1f}% of variance explained)")
        print(f"    {'Feature':25s} {'Coefficient':>12s} {'Direction':>10s}")
        print("    " + "-" * 50)

        coefs = []
        for col, coef in sorted(zip(reg_cols, model.coef_), key=lambda x: abs(x[1]), reverse=True):
            label = dict(EXPLANATORY_FEATURES).get(col, col)
            direction = "worse" if coef > 0 else "better"
            print(f"    {label:25s} {coef:+12.4f}   → {direction}")
            coefs.append({
                "feature": col,
                "label": label,
                "coefficient": round(float(coef), 6),
                "direction": direction,
            })

        coef_df = pd.DataFrame(coefs)
    else:
        r2 = None
        coef_df = pd.DataFrame()
        print("\n  Not enough data for multivariate regression.")

    # --- 4. Category-level: correlate category medians ---
    print("\n  Category-level correlations (what makes a category poorly calibrated):")
    cat_corr_results = []
    cat_features_to_test = profile_cols + ["base_rate_imbalance", "yes_rate"]
    for feat in cat_features_to_test:
        if feat not in cat_profiles.columns:
            continue
        valid = cat_profiles.dropna(subset=[feat, "brier_score"])
        if len(valid) < 5:
            continue
        r, p = scipy_stats.spearmanr(valid[feat], valid["brier_score"])
        label = dict(EXPLANATORY_FEATURES).get(feat, feat.replace("_", " ").title())
        sig = "*" if p < 0.05 else " "
        print(f"    {label:25s}  r={r:+.4f}  p={p:.4f} {sig}")
        cat_corr_results.append({
            "feature": feat,
            "label": label,
            "spearman_r": round(r, 4),
            "p_value": round(p, 6),
            "significant": p < 0.05,
        })

    cat_corr_df = pd.DataFrame(cat_corr_results)

    # --- 5. Plots ---
    _plot_explanatory(mf, corr_df, cat_profiles, coef_df)

    # --- 6. Build narrative per category ---
    narratives = _build_narratives(cat_profiles, corr_df)

    return {
        "correlations": correlations,
        "category_profiles": cat_profiles.reset_index().to_dict(orient="records"),
        "regression_r2": r2,
        "regression_coefficients": coefs if r2 is not None else [],
        "category_correlations": cat_corr_results,
        "narratives": narratives,
    }


def _plot_explanatory(mf, corr_df, cat_profiles, coef_df):
    """Generate explanatory analysis plots."""

    # Plot 1: Scatter grid - top features vs Brier
    top_features = [
        ("avg_spread", "Bid-Ask Spread"),
        ("late_volatility", "Late Volatility (24h)"),
        ("price_range", "Price Range"),
        ("late_price_move", "Late Price Move"),
        ("n_price_observations", "# Price Updates"),
        ("total_volume", "Total Volume"),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    for idx, (col, label) in enumerate(top_features):
        ax = axes[idx // 3][idx % 3]
        valid = mf.dropna(subset=[col, "brier_score"])
        if valid.empty:
            continue

        for cat in valid["category"].unique():
            cd = valid[valid["category"] == cat]
            color = CAT_COLORS.get(cat, "#999")
            ax.scatter(cd[col], cd["brier_score"], alpha=0.4, s=20, color=color, label=cat)

        # Trend line
        r, p = scipy_stats.spearmanr(valid[col], valid["brier_score"])
        z = np.polyfit(valid[col].values, valid["brier_score"].values, 1)
        x_line = np.linspace(valid[col].min(), valid[col].max(), 100)
        ax.plot(x_line, np.polyval(z, x_line), "k--", alpha=0.5)

        ax.set_xlabel(label)
        ax.set_ylabel("Brier Score")
        ax.set_title(f"{label} vs Accuracy\n(r={r:+.3f}, p={p:.3f})")
        ax.grid(True, alpha=0.3)

        if col == "total_volume":
            ax.set_xscale("log")

    axes[0][0].legend(fontsize=5, ncol=2, loc="upper right")
    plt.suptitle("What Predicts Poor Calibration?", fontsize=14, y=1.01)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "explanatory_scatter.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved explanatory_scatter.png")

    # Plot 2: Category profile heatmap
    profile_display = cat_profiles[
        [c for c in ["avg_spread", "late_volatility", "late_price_move",
                     "price_range", "n_price_observations", "total_volume",
                     "base_rate_imbalance", "brier_score"]
         if c in cat_profiles.columns]
    ].copy()

    if len(profile_display) > 1:
        # Normalize each column 0-1 for heatmap
        profile_norm = (profile_display - profile_display.min()) / (profile_display.max() - profile_display.min() + 1e-9)

        fig, ax = plt.subplots(figsize=(12, max(6, len(profile_norm) * 0.5)))
        sns.heatmap(profile_norm, annot=profile_display.round(4).values, fmt="",
                   cmap="YlOrRd", ax=ax, linewidths=0.5,
                   xticklabels=[dict(EXPLANATORY_FEATURES).get(c, c.replace("_", " ").title())
                                for c in profile_display.columns])
        ax.set_title("Category Profiles: Why Some Categories Calibrate Poorly\n(color = relative rank, values = median)", fontsize=12)
        ax.set_ylabel("")
        plt.tight_layout()
        plt.savefig(PLOTS_DIR / "category_profiles_heatmap.png", dpi=150, bbox_inches="tight")
        plt.close()
        print("  Saved category_profiles_heatmap.png")

    # Plot 3: Regression coefficient bar chart
    if len(coef_df) > 0:
        fig, ax = plt.subplots(figsize=(10, 6))
        colors = ["#ef4444" if c > 0 else "#10b981" for c in coef_df["coefficient"]]
        ax.barh(range(len(coef_df)), coef_df["coefficient"], color=colors)
        ax.set_yticks(range(len(coef_df)))
        ax.set_yticklabels(coef_df["label"])
        ax.set_xlabel("Standardized Coefficient (→ Brier Score)")
        ax.set_title("What Drives Poor Calibration?\n(Red = worse calibration, Green = better)")
        ax.axvline(0, color="black", linewidth=0.5)
        ax.grid(True, alpha=0.3, axis="x")
        plt.tight_layout()
        plt.savefig(PLOTS_DIR / "regression_coefficients.png", dpi=150, bbox_inches="tight")
        plt.close()
        print("  Saved regression_coefficients.png")


def _build_narratives(cat_profiles, corr_df):
    """Build natural-language explanations per category."""
    narratives = {}
    for cat, row in cat_profiles.iterrows():
        reasons = []
        brier = row["brier_score"]

        if row.get("avg_spread", 0) > cat_profiles["avg_spread"].median():
            reasons.append("wider bid-ask spreads (less liquidity)")
        if row.get("late_volatility", 0) > cat_profiles["late_volatility"].median():
            reasons.append("higher late-stage volatility")
        if row.get("late_price_move", 0) > cat_profiles["late_price_move"].median():
            reasons.append("larger surprise price moves near resolution")
        if row.get("base_rate_imbalance", 0) > 0.3:
            reasons.append(f"extreme base rate ({row.get('yes_rate', 0):.0%} yes)")
        if row.get("n_price_observations", 0) < cat_profiles["n_price_observations"].median():
            reasons.append("fewer price observations")
        if row.get("price_range", 0) > cat_profiles["price_range"].median():
            reasons.append("high price uncertainty (wide range)")

        if brier > 0.15:
            quality = "poorly calibrated"
        elif brier > 0.08:
            quality = "moderately calibrated"
        else:
            quality = "well calibrated"

        narrative = f"{cat} markets are {quality} (Brier {brier:.3f})"
        if reasons:
            narrative += f", consistent with {', '.join(reasons[:3])}"
        narrative += "."

        narratives[cat] = {
            "text": narrative,
            "quality": quality,
            "reasons": reasons,
            "brier": round(float(brier), 4),
        }

    return narratives


# ──────────────────────────────────────────────
# Analysis E: Do domain effects survive controls?
# ──────────────────────────────────────────────

def analysis_regression(cal_ds, market_features):
    """
    Analysis E: OLS regressions to test whether domain effects on calibration
    survive after controlling for market microstructure.

    Models:
      1. squared_error ~ domain                         (baseline)
      2. squared_error ~ domain + horizon               (+ time)
      3. squared_error ~ domain + horizon + controls     (+ microstructure)
      4. squared_error ~ controls only                   (no domain)
      5. squared_error ~ domain * horizon + controls     (interaction)

    If domain coefficients shrink to zero in Model 3, then microstructure
    explains the differences. If they survive, domain itself matters.
    """
    import statsmodels.formula.api as smf

    print("\n" + "=" * 60)
    print("ANALYSIS E: Do Domain Effects Survive Controls?")
    print("=" * 60)

    # Build observation-level dataset: each row = (market, timestamp)
    # Outcome = squared error of that observation's price
    df = cal_ds.copy()
    df["squared_error"] = (df["implied_prob"] - df["result_binary"]) ** 2

    # Assign time horizon bucket
    def assign_horizon(days):
        if days >= 30:
            return "30+ days"
        elif days >= 7:
            return "7-30 days"
        elif days >= 1:
            return "1-7 days"
        else:
            return "< 24 hours"

    df["horizon"] = df["days_to_resolution"].apply(assign_horizon)

    # Merge the market-level columns that are NOT used as controls (they are
    # whole-lifetime aggregates, i.e. the market's future as of any observation).
    # They are carried only for the daily-only robustness split and reporting.
    controls_cols = [
        "market_ticker", "total_volume", "avg_spread", "n_price_observations",
        "price_volatility", "late_price_move", "price_range",
        "late_volume_share", "is_hourly_clock",
    ]
    mf_controls = market_features[[c for c in controls_cols if c in market_features.columns]].copy()

    # Base rate by category
    cat_baserate = market_features.groupby("category")["result_binary"].mean().reset_index()
    cat_baserate.columns = ["category", "cat_yes_rate"]
    cat_baserate["cat_base_rate_imbalance"] = abs(cat_baserate["cat_yes_rate"] - 0.5)

    df = df.merge(mf_controls, on="market_ticker", how="left", suffixes=("", "_mkt"))
    df = df.merge(cat_baserate, on="category", how="left")

    # Filter to categories with enough observations
    cat_counts = df["category"].value_counts()
    valid_cats = cat_counts[cat_counts >= 50].index.tolist()
    df = df[df["category"].isin(valid_cats)].copy()

    print(f"\n  Observations: {len(df)}")
    print(f"  Markets: {df['market_ticker'].nunique()}")
    print(f"  Categories: {sorted(valid_cats)}")

    # Log-transform volume (highly skewed). Uses volume accumulated up to the
    # observation, not the market's lifetime total.
    df["log_volume"] = np.log1p(df["pit_cum_volume"])

    # Drop rows with NaN in key columns
    base_cols = ["squared_error", "category", "horizon"]
    df = df.dropna(subset=base_cols)

    # Observations from the same market share a price path, so residuals are
    # strongly correlated within market. Default IID errors would understate
    # every standard error by a large factor; cluster on market instead.
    def fit_clustered(formula, data):
        return smf.ols(formula, data=data).fit(
            cov_type="cluster", cov_kwds={"groups": data["market_ticker"]}
        )

    # Reference category = Politics (best calibrated, natural baseline)
    if "Politics" in valid_cats:
        ref_cat = "Politics"
    else:
        ref_cat = df.groupby("category")["squared_error"].mean().idxmin()

    print(f"  Reference category: {ref_cat}")
    print(f"  Reference horizon: 30+ days\n")

    # ── Model 1: Domain only ──
    print("  " + "─" * 56)
    print("  MODEL 1: squared_error ~ domain")
    print("  " + "─" * 56)
    m1 = fit_clustered(f'squared_error ~ C(category, Treatment("{ref_cat}"))', df)
    print(f"  R² = {m1.rsquared:.4f}  Adj-R² = {m1.rsquared_adj:.4f}  n = {int(m1.nobs)}")
    _print_domain_coefs(m1, ref_cat)

    # ── Model 2: Domain + Horizon ──
    print(f"\n  " + "─" * 56)
    print("  MODEL 2: squared_error ~ domain + horizon")
    print("  " + "─" * 56)
    m2 = fit_clustered(
        f'squared_error ~ C(category, Treatment("{ref_cat}")) + C(horizon, Treatment("30+ days"))',
        df
    )
    print(f"  R² = {m2.rsquared:.4f}  Adj-R² = {m2.rsquared_adj:.4f}  n = {int(m2.nobs)}")
    _print_domain_coefs(m2, ref_cat)
    _print_horizon_coefs(m2)

    # ── Model 3: Domain + Horizon + Controls ──
    # Controls are measured as of the observation. The earlier lifetime versions
    # (total_volume, avg_spread, price_range over the whole market) encoded the
    # future: lifetime price range in particular partly encodes how far the price
    # eventually travelled toward the outcome, which is mechanically tied to the
    # squared error being predicted. duration_hours is fixed at open and so is
    # legitimately known ex ante.
    control_vars = []
    for c in ["log_volume", "pit_avg_spread", "pit_n_obs", "duration_hours",
              "pit_price_range", "cat_base_rate_imbalance"]:
        if c in df.columns and df[c].notna().sum() > len(df) * 0.5:
            control_vars.append(c)

    df_m3 = df.dropna(subset=control_vars)

    print(f"\n  " + "─" * 56)
    print(f"  MODEL 3: squared_error ~ domain + horizon + controls")
    print(f"  Controls: {', '.join(control_vars)}")
    print("  " + "─" * 56)

    controls_formula = " + ".join(control_vars)
    m3 = fit_clustered(
        f'squared_error ~ C(category, Treatment("{ref_cat}")) + C(horizon, Treatment("30+ days")) + {controls_formula}',
        df_m3
    )
    print(f"  R² = {m3.rsquared:.4f}  Adj-R² = {m3.rsquared_adj:.4f}  n = {int(m3.nobs)}")
    _print_domain_coefs(m3, ref_cat)
    _print_horizon_coefs(m3)
    _print_control_coefs(m3, control_vars)

    # ── Model 4: Controls only (no domain) ──
    print(f"\n  " + "─" * 56)
    print(f"  MODEL 4: squared_error ~ horizon + controls (NO domain)")
    print("  " + "─" * 56)
    m4 = fit_clustered(
        f'squared_error ~ C(horizon, Treatment("30+ days")) + {controls_formula}',
        df_m3
    )
    print(f"  R² = {m4.rsquared:.4f}  Adj-R² = {m4.rsquared_adj:.4f}  n = {int(m4.nobs)}")

    # ── Model 5: Domain × Horizon interaction + controls ──
    print(f"\n  " + "─" * 56)
    print(f"  MODEL 5: squared_error ~ domain * horizon + controls")
    print("  " + "─" * 56)
    m5 = fit_clustered(
        f'squared_error ~ C(category, Treatment("{ref_cat}")) * C(horizon, Treatment("30+ days")) + {controls_formula}',
        df_m3
    )
    print(f"  R² = {m5.rsquared:.4f}  Adj-R² = {m5.rsquared_adj:.4f}  n = {int(m5.nobs)}")

    # Count significant interaction terms
    interaction_terms = [p for p in m5.pvalues.index if ":" in p]
    sig_interactions = sum(1 for t in interaction_terms if m5.pvalues[t] < 0.05)
    print(f"  Interaction terms: {len(interaction_terms)} total, {sig_interactions} significant (p<0.05)")

    # ── Summary comparison ──
    print(f"\n  " + "=" * 56)
    print("  MODEL COMPARISON")
    print("  " + "=" * 56)
    print(f"  {'Model':<45s} {'R²':>8s} {'Adj-R²':>8s} {'AIC':>10s}")
    print("  " + "-" * 75)
    for label, model in [
        ("1. Domain only", m1),
        ("2. Domain + horizon", m2),
        ("3. Domain + horizon + controls", m3),
        ("4. Controls only (no domain)", m4),
        ("5. Domain × horizon + controls", m5),
    ]:
        print(f"  {label:<45s} {model.rsquared:8.4f} {model.rsquared_adj:8.4f} {model.aic:10.1f}")

    # ── Key test: does domain add explanatory power over controls? ──
    r2_with_domain = m3.rsquared
    r2_without_domain = m4.rsquared
    r2_lift = r2_with_domain - r2_without_domain

    print(f"\n  KEY TEST: Domain effect after controls")
    print(f"    R² with domain:    {r2_with_domain:.4f}")
    print(f"    R² without domain: {r2_without_domain:.4f}")
    print(f"    R² lift from domain: +{r2_lift:.4f}")

    if r2_lift > 0.01:
        verdict = "Domain effects SURVIVE controls. Category itself matters beyond microstructure."
    else:
        verdict = "Domain effects DISAPPEAR after controls. Microstructure, not domain, explains calibration."
    print(f"    → {verdict}")

    # ── Check which domain coefficients survive ──
    print(f"\n  DOMAIN COEFFICIENTS: Model 2 (no controls) vs Model 3 (with controls)")
    print(f"  {'Category':<25s} {'Coef (M2)':>10s} {'p (M2)':>8s} {'Coef (M3)':>10s} {'p (M3)':>8s} {'Change':>8s}")
    print("  " + "-" * 75)

    surviving_domains = []
    for param in m2.params.index:
        if "category" not in param or "Intercept" in param:
            continue
        cat_name = param.split("[T.")[1].rstrip("]") if "[T." in param else param

        coef_m2 = m2.params[param]
        p_m2 = m2.pvalues[param]

        if param in m3.params.index:
            coef_m3 = m3.params[param]
            p_m3 = m3.pvalues[param]
        else:
            coef_m3 = float("nan")
            p_m3 = float("nan")

        if not np.isnan(coef_m2) and coef_m2 != 0:
            pct_change = ((coef_m3 - coef_m2) / abs(coef_m2)) * 100 if not np.isnan(coef_m3) else float("nan")
        else:
            pct_change = float("nan")

        sig2 = "*" if p_m2 < 0.05 else " "
        sig3 = "*" if not np.isnan(p_m3) and p_m3 < 0.05 else " "
        pct_str = f"{pct_change:+.0f}%" if not np.isnan(pct_change) else "N/A"

        print(f"  {cat_name:<25s} {coef_m2:+10.4f}{sig2} {p_m2:8.4f} {coef_m3:+10.4f}{sig3} {p_m3:8.4f} {pct_str:>8s}")

        if not np.isnan(p_m3) and p_m3 < 0.05:
            surviving_domains.append(cat_name)

    print(f"\n  Domains still significant after controls: {surviving_domains if surviving_domains else 'None'}")

    # ── Plot ──
    _plot_regression(m2, m3, ref_cat, valid_cats)

    # ── Build results for dashboard ──
    model_comparison = []
    for label, model in [
        ("Domain only", m1),
        ("Domain + horizon", m2),
        ("Domain + horizon + controls", m3),
        ("Controls only (no domain)", m4),
        ("Domain x horizon + controls", m5),
    ]:
        model_comparison.append({
            "model": label,
            "r2": round(float(model.rsquared), 6),
            "adj_r2": round(float(model.rsquared_adj), 6),
            "aic": round(float(model.aic), 1),
            "n": int(model.nobs),
        })

    domain_coefs = []
    for param in m3.params.index:
        if "category" not in param or "Intercept" in param:
            continue
        cat_name = param.split("[T.")[1].rstrip("]") if "[T." in param else param
        coef_m2 = float(m2.params[param]) if param in m2.params.index else None
        p_m2 = float(m2.pvalues[param]) if param in m2.pvalues.index else None
        coef_m3 = float(m3.params[param])
        p_m3 = float(m3.pvalues[param])
        domain_coefs.append({
            "category": cat_name,
            "coef_no_controls": coef_m2,
            "p_no_controls": p_m2,
            "coef_with_controls": coef_m3,
            "p_with_controls": p_m3,
            "survives": p_m3 < 0.05,
        })

    control_coefs = []
    for c in control_vars:
        if c in m3.params.index:
            control_coefs.append({
                "feature": c,
                "coefficient": round(float(m3.params[c]), 6),
                "p_value": round(float(m3.pvalues[c]), 6),
                "significant": float(m3.pvalues[c]) < 0.05,
            })

    return {
        "model_comparison": model_comparison,
        "domain_coefficients": domain_coefs,
        "control_coefficients": control_coefs,
        "r2_with_domain": round(float(r2_with_domain), 6),
        "r2_without_domain": round(float(r2_without_domain), 6),
        "r2_lift": round(float(r2_lift), 6),
        "verdict": verdict,
        "surviving_domains": surviving_domains,
        "n_sig_interactions": sig_interactions,
        "n_interactions": len(interaction_terms),
        "reference_category": ref_cat,
    }


def _print_domain_coefs(model, ref_cat):
    """Print domain coefficients from a regression model."""
    coefs = []
    for param in model.params.index:
        if "category" not in param or "Intercept" in param:
            continue
        cat_name = param.split("[T.")[1].rstrip("]") if "[T." in param else param
        coef = model.params[param]
        p = model.pvalues[param]
        sig = "*" if p < 0.05 else " "
        coefs.append((cat_name, coef, p, sig))

    coefs.sort(key=lambda x: x[1])
    for cat_name, coef, p, sig in coefs:
        print(f"    {cat_name:<25s} {coef:+.4f}  p={p:.4f} {sig}")
    print(f"    (reference: {ref_cat} = 0.0000)")


def _print_horizon_coefs(model):
    """Print horizon coefficients."""
    for param in model.params.index:
        if "horizon" not in param or "Intercept" in param:
            continue
        h_name = param.split("[T.")[1].rstrip("]") if "[T." in param else param
        coef = model.params[param]
        p = model.pvalues[param]
        sig = "*" if p < 0.05 else " "
        print(f"    {h_name:<25s} {coef:+.4f}  p={p:.4f} {sig}")


def _print_control_coefs(model, control_vars):
    """Print control variable coefficients."""
    print("  Controls:")
    for c in control_vars:
        if c in model.params.index:
            coef = model.params[c]
            p = model.pvalues[c]
            sig = "*" if p < 0.05 else " "
            print(f"    {c:<25s} {coef:+.6f}  p={p:.4f} {sig}")


def _plot_regression(m2, m3, ref_cat, valid_cats):
    """Plot domain coefficient comparison: before vs after controls."""
    cats = []
    coefs_before = []
    coefs_after = []
    sig_before = []
    sig_after = []

    for param in m2.params.index:
        if "category" not in param or "Intercept" in param:
            continue
        cat_name = param.split("[T.")[1].rstrip("]") if "[T." in param else param
        cats.append(cat_name)
        coefs_before.append(float(m2.params[param]))
        sig_before.append(m2.pvalues[param] < 0.05)

        if param in m3.params.index:
            coefs_after.append(float(m3.params[param]))
            sig_after.append(m3.pvalues[param] < 0.05)
        else:
            coefs_after.append(0)
            sig_after.append(False)

    # Sort by before-controls coefficient
    order = np.argsort(coefs_before)
    cats = [cats[i] for i in order]
    coefs_before = [coefs_before[i] for i in order]
    coefs_after = [coefs_after[i] for i in order]
    sig_before = [sig_before[i] for i in order]
    sig_after = [sig_after[i] for i in order]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, max(6, len(cats) * 0.45)))

    # Left: coefficient comparison
    y = range(len(cats))
    ax1.barh([yi - 0.15 for yi in y], coefs_before, height=0.3, label="Without controls",
             color=["#ef4444" if c > 0 else "#10b981" for c in coefs_before], alpha=0.6)
    ax1.barh([yi + 0.15 for yi in y], coefs_after, height=0.3, label="With controls",
             color=["#ef4444" if c > 0 else "#10b981" for c in coefs_after], alpha=0.9)

    # Mark significant ones
    for i, (sb, sa) in enumerate(zip(sig_before, sig_after)):
        if sa:
            ax1.plot(coefs_after[i], i + 0.15, "k*", markersize=8)

    ax1.set_yticks(list(y))
    ax1.set_yticklabels(cats, fontsize=9)
    ax1.axvline(0, color="black", linewidth=0.5)
    ax1.set_xlabel(f"Coefficient (relative to {ref_cat})")
    ax1.set_title("Domain Effects: Before vs After Controls\n(stars = significant after controls)")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3, axis="x")

    # Right: shrinkage of the largest domain effect once controls are added
    ax2.bar(["Before\ncontrols", "After\ncontrols"], [
        max(abs(c) for c in coefs_before),
        max(abs(c) for c in coefs_after),
    ], color=["#ef4444", "#2563eb"], alpha=0.7)
    ax2.set_ylabel("Max |domain coefficient|")
    ax2.set_title("Largest Domain Effect:\nBefore vs After Controls")
    ax2.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "regression_controls.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved regression_controls.png")


# ──────────────────────────────────────────────
# Analysis F: Recalibration — out-of-sample test
# ──────────────────────────────────────────────

def analysis_recalibration(cal_ds, market_features, n_bootstrap=1000, n_folds=5, seed=42):
    """
    Analysis F: Build a domain-horizon recalibration layer and test it out-of-sample.

    1. 5-fold CV by market — every observation gets an OOS prediction
    2. Platt scaling per (category, horizon) with fallbacks
    3. Reliability plots: raw vs recalibrated
    4. Bootstrap confidence intervals on domain effects
    """
    from sklearn.linear_model import LogisticRegression

    print("\n" + "=" * 60)
    print("ANALYSIS F: Out-of-Sample Recalibration Test")
    print("=" * 60)

    rng = np.random.RandomState(seed)

    # ── Prep data ──
    df = cal_ds.copy()
    df["squared_error"] = (df["implied_prob"] - df["result_binary"]) ** 2

    def assign_horizon(days):
        if days >= 30: return "30+ days"
        elif days >= 7: return "7-30 days"
        elif days >= 1: return "1-7 days"
        else: return "< 24 hours"

    df["horizon"] = df["days_to_resolution"].apply(assign_horizon)

    cat_counts = df["category"].value_counts()
    valid_cats = cat_counts[cat_counts >= 100].index.tolist()
    df = df[df["category"].isin(valid_cats)].copy()
    df = df.reset_index(drop=True)

    print(f"  Observations: {len(df)}")
    print(f"  Markets: {df['market_ticker'].nunique()}")
    print(f"  Categories: {sorted(valid_cats)}")

    # ── 1. 5-fold CV by MARKET (not observation — avoids leakage) ──
    all_markets = df["market_ticker"].unique()
    rng.shuffle(all_markets)
    folds = np.array_split(all_markets, n_folds)

    df["recalibrated_prob"] = np.nan
    min_fit = 30

    def _fit_platt(train_subset):
        """Fit Platt models on training data, return prediction function."""
        platt_ch = {}  # (cat, horizon) models
        platt_c = {}   # category-only fallback
        for cat in valid_cats:
            ct = train_subset[train_subset["category"] == cat]
            if len(ct) >= min_fit and ct["result_binary"].nunique() > 1:
                lr = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
                lr.fit(ct[["implied_prob"]].values, ct["result_binary"].values)
                platt_c[cat] = lr
            platt_ch[cat] = {}
            for h_label, _, _ in TIME_HORIZONS:
                subset = ct[ct["horizon"] == h_label]
                if len(subset) >= min_fit and subset["result_binary"].nunique() > 1:
                    lr = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
                    lr.fit(subset[["implied_prob"]].values, subset["result_binary"].values)
                    platt_ch[cat][h_label] = lr

        platt_g = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
        platt_g.fit(train_subset[["implied_prob"]].values, train_subset["result_binary"].values)

        def predict(row):
            raw = np.array([[row["implied_prob"]]])
            cat, horizon = row["category"], row["horizon"]
            if cat in platt_ch and horizon in platt_ch[cat]:
                return float(platt_ch[cat][horizon].predict_proba(raw)[0, 1])
            if cat in platt_c:
                return float(platt_c[cat].predict_proba(raw)[0, 1])
            return float(platt_g.predict_proba(raw)[0, 1])

        return predict

    print(f"\n  Running {n_folds}-fold cross-validation (split by market)...")
    for fold_i in range(n_folds):
        test_mkts = set(folds[fold_i])
        train_data = df[~df["market_ticker"].isin(test_mkts)]
        test_mask = df["market_ticker"].isin(test_mkts)

        predict_fn = _fit_platt(train_data)
        df.loc[test_mask, "recalibrated_prob"] = df.loc[test_mask].apply(predict_fn, axis=1)
        n_test_fold = test_mask.sum()
        print(f"    Fold {fold_i+1}: train={len(train_data)} obs, test={n_test_fold} obs")

    # Drop any rows without predictions (shouldn't happen)
    df = df.dropna(subset=["recalibrated_prob"])

    df["raw_sq_error"] = (df["implied_prob"] - df["result_binary"]) ** 2
    df["recal_sq_error"] = (df["recalibrated_prob"] - df["result_binary"]) ** 2

    # ── 2. Evaluate: raw vs recalibrated (all OOS) ──
    raw_brier = df["raw_sq_error"].mean()
    recal_brier = df["recal_sq_error"].mean()
    improvement = (raw_brier - recal_brier) / raw_brier * 100

    print(f"\n  OUT-OF-SAMPLE RESULTS ({n_folds}-fold CV, all observations):")
    print(f"    Raw Brier:          {raw_brier:.4f}")
    print(f"    Recalibrated Brier: {recal_brier:.4f}")
    print(f"    Improvement:        {improvement:+.1f}%")

    # ── Seed stability ──
    # A single fold split decides this number, and the split is a lottery: which
    # markets land in which fold moves the result by several points. Re-run the
    # whole CV under different splits so the headline is not one draw.
    def cv_improvement(cv_seed):
        r = np.random.RandomState(cv_seed)
        mkts = df["market_ticker"].unique().copy()
        r.shuffle(mkts)
        sub = df[["market_ticker", "category", "horizon", "implied_prob", "result_binary"]].copy()
        sub["recalibrated_prob"] = np.nan
        for f_i in np.array_split(mkts, n_folds):
            test_mkts = set(f_i)
            train = sub[~sub["market_ticker"].isin(test_mkts)]
            mask = sub["market_ticker"].isin(test_mkts)
            fn = _fit_platt(train)
            sub.loc[mask, "recalibrated_prob"] = sub.loc[mask].apply(fn, axis=1)
        sub = sub.dropna(subset=["recalibrated_prob"])
        raw = ((sub["implied_prob"] - sub["result_binary"]) ** 2).mean()
        rec = ((sub["recalibrated_prob"] - sub["result_binary"]) ** 2).mean()
        return (raw - rec) / raw * 100

    stability_seeds = [seed + k for k in range(10)]
    improvements = [float(cv_improvement(s)) for s in stability_seeds]
    imp_mean, imp_sd = float(np.mean(improvements)), float(np.std(improvements))
    imp_se = imp_sd / np.sqrt(len(improvements))
    print(f"\n    Across {len(stability_seeds)} fold splits: mean {imp_mean:+.1f}%, "
          f"sd {imp_sd:.1f}, range [{min(improvements):+.1f}%, {max(improvements):+.1f}%]")
    if abs(imp_mean) < 2 * imp_se:
        print("    → No reliable overall improvement: the effect is indistinguishable")
        print("      from zero, and the single-split number is mostly split noise.")
    elif imp_mean < 0:
        print("    → Recalibration makes calibration WORSE out-of-sample overall.")

    # Per-category
    print(f"\n    {'Category':<25s} {'Raw BS':>8s} {'Recal BS':>9s} {'Change':>8s} {'n':>6s}")
    print("    " + "-" * 60)
    cat_improvements = []
    for cat in sorted(valid_cats):
        ct = df[df["category"] == cat]
        if len(ct) < 20: continue
        raw_bs = ct["raw_sq_error"].mean()
        recal_bs = ct["recal_sq_error"].mean()
        chg = (raw_bs - recal_bs) / raw_bs * 100 if raw_bs > 0 else 0
        print(f"    {cat:<25s} {raw_bs:8.4f} {recal_bs:9.4f} {chg:+7.1f}% {len(ct):6d}")
        cat_improvements.append({
            "category": cat,
            "raw_brier": round(float(raw_bs), 6),
            "recalibrated_brier": round(float(recal_bs), 6),
            "improvement_pct": round(float(chg), 2),
            "n_test": len(ct),
        })

    # Per horizon
    print(f"\n    {'Horizon':<25s} {'Raw BS':>8s} {'Recal BS':>9s} {'Change':>8s}")
    print("    " + "-" * 55)
    for h_label, _, _ in TIME_HORIZONS:
        ht = df[df["horizon"] == h_label]
        if len(ht) < 20: continue
        raw_bs = ht["raw_sq_error"].mean()
        recal_bs = ht["recal_sq_error"].mean()
        chg = (raw_bs - recal_bs) / raw_bs * 100 if raw_bs > 0 else 0
        print(f"    {h_label:<25s} {raw_bs:8.4f} {recal_bs:9.4f} {chg:+7.1f}%")

    # ── 3. Bootstrap confidence intervals on domain effects ──
    print(f"\n  Bootstrapping {n_bootstrap} samples for confidence intervals...")

    ref_cat = "Politics" if "Politics" in valid_cats else valid_cats[0]
    bootstrap_coefs = {cat: [] for cat in valid_cats if cat != ref_cat}

    # Resample markets with replacement. Selecting with .isin() would silently
    # collapse duplicate draws, turning each replicate into an unweighted ~63%
    # subsample and inflating every interval. Weighting each market by how many
    # times it was drawn reproduces a true bootstrap replicate.
    obs_by_market = {m: g for m, g in df.groupby("market_ticker")["squared_error"]}
    cat_by_market = df.groupby("market_ticker")["category"].first()

    for i in range(n_bootstrap):
        boot_markets = rng.choice(all_markets, len(all_markets), replace=True)
        tickers, counts = np.unique(boot_markets, return_counts=True)

        # Weighted mean of squared_error per category, weights = draw counts.
        sums, weights = {}, {}
        for ticker, count in zip(tickers, counts):
            cat = cat_by_market.get(ticker)
            vals = obs_by_market.get(ticker)
            if cat is None or vals is None:
                continue
            sums[cat] = sums.get(cat, 0.0) + vals.sum() * count
            weights[cat] = weights.get(cat, 0) + len(vals) * count
        cat_means = pd.Series(
            {c: sums[c] / weights[c] for c in sums if weights[c] > 0}
        )
        ref_mean = cat_means.get(ref_cat, np.nan)
        for cat in bootstrap_coefs:
            if cat in cat_means.index:
                bootstrap_coefs[cat].append(cat_means[cat] - ref_mean)
            else:
                bootstrap_coefs[cat].append(np.nan)

    ci_results = []
    print(f"\n  Domain effects with 95% bootstrap CIs (vs {ref_cat}):")
    print(f"    {'Category':<25s} {'Effect':>8s} {'95% CI':>24s} {'Sig':>5s}")
    print("    " + "-" * 66)

    for cat in sorted(bootstrap_coefs.keys()):
        vals = [v for v in bootstrap_coefs[cat] if not np.isnan(v)]
        if len(vals) < 100: continue
        point = np.mean(vals)
        ci_lo = np.percentile(vals, 2.5)
        ci_hi = np.percentile(vals, 97.5)
        sig = "Yes" if (ci_lo > 0 or ci_hi < 0) else "No"
        print(f"    {cat:<25s} {point:+8.4f}   [{ci_lo:+.4f}, {ci_hi:+.4f}] {sig:>5s}")
        ci_results.append({
            "category": cat,
            "effect": round(float(point), 6),
            "ci_lower": round(float(ci_lo), 6),
            "ci_upper": round(float(ci_hi), 6),
            "significant": sig == "Yes",
        })

    # ── 4. Plots ──
    _plot_recalibration(df, valid_cats, ci_results, ref_cat, cat_improvements)

    return {
        "raw_brier": round(float(raw_brier), 6),
        "recalibrated_brier": round(float(recal_brier), 6),
        "improvement_pct": round(float(improvement), 2),
        "improvement_mean_pct": round(imp_mean, 2),
        "improvement_sd_pct": round(imp_sd, 2),
        "improvement_range_pct": [round(min(improvements), 2), round(max(improvements), 2)],
        "improvement_se_pct": round(float(imp_se), 2),
        "improvement_reliable": bool(abs(imp_mean) > 2 * imp_se),
        "n_seeds": len(stability_seeds),
        "n_observations": len(df),
        "n_markets": int(df["market_ticker"].nunique()),
        "n_folds": n_folds,
        "category_improvements": cat_improvements,
        "confidence_intervals": ci_results,
        "reference_category": ref_cat,
    }


def _plot_recalibration(test, valid_cats, ci_results, ref_cat, cat_improvements):
    """Plots for the recalibration analysis."""

    fig, axes = plt.subplots(2, 2, figsize=(16, 14))

    # ── Plot 1: Reliability diagram — raw vs recalibrated ──
    ax = axes[0][0]
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Perfect calibration")

    for label, col, color in [
        ("Raw prices", "implied_prob", "#ef4444"),
        ("Recalibrated", "recalibrated_prob", "#2563eb"),
    ]:
        pred = test[col].values
        actual = test["result_binary"].values
        cal = calibration_curve(pred, actual)
        bs = np.mean((pred - actual) ** 2)
        ax.plot(cal["mean_predicted"], cal["realized_frequency"], "o-",
               color=color, label=f"{label} (BS={bs:.4f})", markersize=6, linewidth=2)

    ax.set_xlabel("Predicted Probability")
    ax.set_ylabel("Realized Frequency")
    ax.set_title("Reliability Diagram: Raw vs Recalibrated\n(out-of-sample test set)")
    ax.legend(fontsize=10)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3)

    # ── Plot 2: Per-category improvement ──
    ax = axes[0][1]
    ci_sorted = sorted(cat_improvements, key=lambda x: x["improvement_pct"])
    cats = [c["category"] for c in ci_sorted]
    imps = [c["improvement_pct"] for c in ci_sorted]
    colors = ["#10b981" if v > 0 else "#ef4444" for v in imps]
    ax.barh(range(len(cats)), imps, color=colors)
    ax.set_yticks(range(len(cats)))
    ax.set_yticklabels(cats, fontsize=9)
    ax.axvline(0, color="black", linewidth=0.5)
    ax.set_xlabel("Brier Score Improvement (%)")
    ax.set_title("Out-of-Sample Improvement by Category\n(green = recalibration helped)")
    ax.grid(True, alpha=0.3, axis="x")

    # ── Plot 3: Confidence intervals on domain effects ──
    ax = axes[1][0]
    ci_sorted2 = sorted(ci_results, key=lambda x: x["effect"])
    cats2 = [c["category"] for c in ci_sorted2]
    effects = [c["effect"] for c in ci_sorted2]
    ci_lo = [c["ci_lower"] for c in ci_sorted2]
    ci_hi = [c["ci_upper"] for c in ci_sorted2]
    colors2 = []
    for c in ci_sorted2:
        if c["significant"]:
            colors2.append("#ef4444" if c["effect"] > 0 else "#10b981")
        else:
            colors2.append("#d1d5db")

    y_pos = range(len(cats2))
    ax.barh(y_pos, effects, color=colors2, alpha=0.7)
    ax.errorbar(effects, y_pos,
               xerr=[[e - lo for e, lo in zip(effects, ci_lo)],
                     [hi - e for e, hi in zip(effects, ci_hi)]],
               fmt="none", ecolor="black", capsize=3, linewidth=1)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(cats2, fontsize=9)
    ax.axvline(0, color="black", linewidth=0.5)
    ax.set_xlabel(f"Domain Effect (relative to {ref_cat})")
    ax.set_title(f"Domain Effects with 95% Bootstrap CIs\n(ref = {ref_cat})")
    ax.grid(True, alpha=0.3, axis="x")

    # ── Plot 4: Reliability by select categories — before/after ──
    ax = axes[1][1]
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Perfect")

    highlight_cats = ["Politics", "Financials", "Sports", "Crypto"]
    highlight_cats = [c for c in highlight_cats if c in valid_cats]

    for cat in highlight_cats:
        ct = test[test["category"] == cat]
        if len(ct) < 20: continue
        color = CAT_COLORS.get(cat, "#666")

        # Raw
        cal_raw = calibration_curve(ct["implied_prob"].values, ct["result_binary"].values)
        ax.plot(cal_raw["mean_predicted"], cal_raw["realized_frequency"],
               "o--", color=color, alpha=0.4, markersize=4)

        # Recalibrated
        cal_recal = calibration_curve(ct["recalibrated_prob"].values, ct["result_binary"].values)
        ax.plot(cal_recal["mean_predicted"], cal_recal["realized_frequency"],
               "s-", color=color, markersize=5, linewidth=2,
               label=f"{cat}")

    ax.set_xlabel("Predicted Probability")
    ax.set_ylabel("Realized Frequency")
    ax.set_title("Calibration by Category: Raw (dashed) vs Recalibrated (solid)\n(out-of-sample)")
    ax.legend(fontsize=9)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "recalibration_results.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved recalibration_results.png")


# ──────────────────────────────────────────────
# Analysis G: Domain-adjusted probability model + robustness
# ──────────────────────────────────────────────

def analysis_adjusted_model(cal_ds, market_features, n_folds=5, n_bootstrap=1000, seed=42):
    """
    Analysis G: Two things:
      1. Domain-adjusted implied probability model (logistic regression using
         raw price + domain + horizon + spread + volume → adjusted probability).
         Tested out-of-sample with 5-fold CV by market.
      2. Robustness checks: alternative control sets and sample-size diagnostics
         for the Analysis E regression.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    import statsmodels.formula.api as smf

    print("\n" + "=" * 60)
    print("ANALYSIS G: Domain-Adjusted Model + Robustness")
    print("=" * 60)

    rng = np.random.RandomState(seed)

    # ── Prep data ──
    df = cal_ds.copy()
    df["squared_error"] = (df["implied_prob"] - df["result_binary"]) ** 2

    def assign_horizon(days):
        if days >= 30: return "30+ days"
        elif days >= 7: return "7-30 days"
        elif days >= 1: return "1-7 days"
        else: return "< 24 hours"

    df["horizon"] = df["days_to_resolution"].apply(assign_horizon)

    # Merge the market-level clock flag only. Microstructure comes from the
    # point-in-time columns on cal_ds; the lifetime aggregates that used to be
    # merged here described each market's future relative to the observation
    # being predicted, which leaked into the cross-validated model below.
    merge_cols = ["market_ticker", "is_hourly_clock"]
    mf_merge = market_features[[c for c in merge_cols if c in market_features.columns]].copy()
    df = df.merge(mf_merge, on="market_ticker", how="left", suffixes=("", "_mkt"))

    cat_counts = df["category"].value_counts()
    valid_cats = cat_counts[cat_counts >= 100].index.tolist()
    df = df[df["category"].isin(valid_cats)].copy()

    df["log_volume"] = np.log1p(df["pit_cum_volume"])

    # Base rate
    cat_br = market_features.groupby("category")["result_binary"].mean()
    df["cat_base_rate_imbalance"] = df["category"].map(lambda c: abs(cat_br.get(c, 0.5) - 0.5))

    print(f"  Observations: {len(df)}")
    print(f"  Markets: {df['market_ticker'].nunique()}")
    print(f"  Categories: {sorted(valid_cats)}")

    # ════════════════════════════════════════════════
    # PART 1: Domain-adjusted probability model
    # ════════════════════════════════════════════════
    print(f"\n  ── Part 1: Domain-Adjusted Probability Model ──")

    # Feature matrix: raw price + domain dummies + horizon dummies + microstructure
    micro_features = ["log_volume", "pit_avg_spread", "duration_hours", "pit_price_range"]
    micro_features = [c for c in micro_features if c in df.columns and df[c].notna().sum() > len(df) * 0.5]

    df_model = df.dropna(subset=micro_features + ["implied_prob"]).copy()
    df_model = df_model.reset_index(drop=True)

    # Encode categoricals
    cat_dummies = pd.get_dummies(df_model["category"], prefix="cat", drop_first=True)
    hor_dummies = pd.get_dummies(df_model["horizon"], prefix="hor", drop_first=True)

    feature_cols = ["implied_prob"] + micro_features
    X_base = df_model[feature_cols].values
    X_cat = cat_dummies.values
    X_hor = hor_dummies.values
    X_full = np.hstack([X_base, X_cat, X_hor])
    y = df_model["result_binary"].values

    # Models to compare:
    # A: raw price only (baseline Platt scaling)
    # B: raw price + domain + horizon (Analysis F approach, single logistic)
    # C: raw price + domain + horizon + microstructure (full model)
    models = {
        "Raw price only": X_base[:, :1],  # just implied_prob
        "Price + domain + horizon": np.hstack([X_base[:, :1], X_cat, X_hor]),
        "Price + domain + horizon + micro": X_full,
    }

    # 5-fold CV by market
    all_markets = df_model["market_ticker"].unique()
    rng.shuffle(all_markets)
    folds = np.array_split(all_markets, n_folds)

    print(f"\n  Running {n_folds}-fold CV for 3 model variants...")
    model_predictions = {name: np.full(len(df_model), np.nan) for name in models}

    for fold_i in range(n_folds):
        test_mkts = set(folds[fold_i])
        train_mask = ~df_model["market_ticker"].isin(test_mkts)
        test_mask = df_model["market_ticker"].isin(test_mkts)

        for name, X in models.items():
            scaler = StandardScaler()
            X_train = scaler.fit_transform(X[train_mask])
            X_test = scaler.transform(X[test_mask])
            y_train = y[train_mask]

            lr = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)
            lr.fit(X_train, y_train)
            preds = lr.predict_proba(X_test)[:, 1]
            model_predictions[name][test_mask] = preds

    print(f"\n  OUT-OF-SAMPLE MODEL COMPARISON:")
    print(f"    {'Model':<40s} {'Brier':>8s} {'LogLoss':>9s} {'vs Raw':>8s}")
    print("    " + "-" * 68)

    model_results = []
    raw_brier_baseline = None
    for name, preds in model_predictions.items():
        valid = ~np.isnan(preds)
        bs = brier_score(preds[valid], y[valid])
        ll = log_loss(preds[valid], y[valid])
        if raw_brier_baseline is None:
            raw_brier_baseline = bs
            chg_str = "baseline"
        else:
            chg = (raw_brier_baseline - bs) / raw_brier_baseline * 100
            chg_str = f"{chg:+.1f}%"
        print(f"    {name:<40s} {bs:8.4f} {ll:9.4f} {chg_str:>8s}")
        model_results.append({
            "model": name,
            "brier": round(float(bs), 6),
            "log_loss": round(float(ll), 6),
            "improvement_vs_raw": round(float((raw_brier_baseline - bs) / raw_brier_baseline * 100), 2) if raw_brier_baseline else 0,
        })

    # Per-category breakdown for the full model
    full_preds = model_predictions["Price + domain + horizon + micro"]
    raw_preds = model_predictions["Raw price only"]

    print(f"\n  PER-CATEGORY: Full model vs raw price only")
    print(f"    {'Category':<25s} {'Raw BS':>8s} {'Full BS':>9s} {'Change':>8s} {'n':>6s}")
    print("    " + "-" * 60)

    adjusted_cat_results = []
    for cat in sorted(valid_cats):
        mask = (df_model["category"] == cat).values & ~np.isnan(full_preds)
        if mask.sum() < 20:
            continue
        raw_bs = brier_score(raw_preds[mask], y[mask])
        full_bs = brier_score(full_preds[mask], y[mask])
        chg = (raw_bs - full_bs) / raw_bs * 100 if raw_bs > 0 else 0
        print(f"    {cat:<25s} {raw_bs:8.4f} {full_bs:9.4f} {chg:+7.1f}% {mask.sum():6d}")
        adjusted_cat_results.append({
            "category": cat,
            "raw_brier": round(float(raw_bs), 6),
            "adjusted_brier": round(float(full_bs), 6),
            "improvement_pct": round(float(chg), 2),
            "n": int(mask.sum()),
        })

    # ════════════════════════════════════════════════
    # PART 2: Robustness — alternative control sets
    # ════════════════════════════════════════════════
    print(f"\n  ── Part 2: Robustness — Alternative Control Sets ──")

    ref_cat = "Politics" if "Politics" in valid_cats else valid_cats[0]

    # Define alternative control sets (all point-in-time)
    alt_control_sets = {
        "Minimal (volume + spread)": ["log_volume", "pit_avg_spread"],
        "Microstructure (volume + spread + duration)": ["log_volume", "pit_avg_spread", "duration_hours"],
        "Full (all 6 controls)": ["log_volume", "pit_avg_spread", "pit_n_obs",
                                   "duration_hours", "pit_price_range", "cat_base_rate_imbalance"],
        "No spread": ["log_volume", "pit_n_obs", "duration_hours",
                       "pit_price_range", "cat_base_rate_imbalance"],
        "No volume": ["pit_avg_spread", "pit_n_obs", "duration_hours",
                       "pit_price_range", "cat_base_rate_imbalance"],
    }

    # Filter to available columns
    for name in list(alt_control_sets.keys()):
        alt_control_sets[name] = [c for c in alt_control_sets[name]
                                   if c in df.columns and df[c].notna().sum() > len(df) * 0.5]

    robustness_results = []
    key_cats = ["Crypto", "Financials", "Sports", "Science and Technology", "Entertainment"]

    # Each spec is (label, controls, sample). The daily-only spec re-runs the full
    # control set on markets that have real daily candles, dropping the ones
    # backfilled with hourly data. Those are almost entirely Sports and Crypto —
    # the two categories whose results get interpreted most — so their effects
    # need to hold up when the clock is uniform.
    specs = [(name, controls, df) for name, controls in alt_control_sets.items() if controls]
    if "is_hourly_clock" in df.columns:
        df_daily = df[df["is_hourly_clock"] != 1]
        if df_daily["market_ticker"].nunique() >= 50:
            specs.append(
                ("Full, daily-clock markets only", alt_control_sets["Full (all 6 controls)"], df_daily)
            )

    print(f"\n  {'Control Set':<45s} {'R²':>6s} {'R² lift':>8s} {'#Surv':>6s}")
    print("  " + "-" * 70)

    for set_name, controls, df_source in specs:
        if not controls:
            continue
        df_r = df_source.dropna(subset=controls)
        cf = " + ".join(controls)

        try:
            m_with = smf.ols(
                f'squared_error ~ C(category, Treatment("{ref_cat}")) + C(horizon, Treatment("30+ days")) + {cf}',
                data=df_r
            ).fit(cov_type="cluster", cov_kwds={"groups": df_r["market_ticker"]})
            m_without = smf.ols(
                f'squared_error ~ C(horizon, Treatment("30+ days")) + {cf}',
                data=df_r
            ).fit(cov_type="cluster", cov_kwds={"groups": df_r["market_ticker"]})
        except Exception as exc:
            print(f"  {set_name:<45s}  SKIPPED: {exc}")
            continue

        r2 = m_with.rsquared
        lift = m_with.rsquared - m_without.rsquared

        # Count surviving domains
        n_surv = 0
        cat_coefs_alt = {}
        for param in m_with.params.index:
            if "category" not in param or "Intercept" in param:
                continue
            cat_name = param.split("[T.")[1].rstrip("]") if "[T." in param else param
            if m_with.pvalues[param] < 0.05:
                n_surv += 1
            if cat_name in key_cats:
                cat_coefs_alt[cat_name] = {
                    "coef": round(float(m_with.params[param]), 4),
                    "p": round(float(m_with.pvalues[param]), 4),
                    "sig": m_with.pvalues[param] < 0.05,
                }

        print(f"  {set_name:<45s} {r2:6.4f} {lift:+8.4f} {n_surv:>6d}")
        robustness_results.append({
            "control_set": set_name,
            "controls": controls,
            "r2": round(float(r2), 6),
            "r2_lift": round(float(lift), 6),
            "n_surviving": n_surv,
            "n_obs": int(m_with.nobs),
            "n_markets": int(df_r["market_ticker"].nunique()),
            "key_category_coefs": cat_coefs_alt,
        })

    # Show key categories across control sets
    print(f"\n  KEY CATEGORY COEFFICIENTS ACROSS CONTROL SETS:")
    print(f"  {'Control Set':<35s}", end="")
    for cat in key_cats:
        print(f" {cat[:8]:>10s}", end="")
    print()
    print("  " + "-" * (35 + 10 * len(key_cats)))

    for r in robustness_results:
        print(f"  {r['control_set']:<35s}", end="")
        for cat in key_cats:
            if cat in r["key_category_coefs"]:
                c = r["key_category_coefs"][cat]
                sig = "*" if c["sig"] else " "
                print(f" {c['coef']:+9.4f}{sig}", end="")
            else:
                print(f" {'N/A':>10s}", end="")
        print()

    # ════════════════════════════════════════════════
    # PART 3: Sample-size diagnostics
    # ════════════════════════════════════════════════
    print(f"\n  ── Part 3: Sample-Size Diagnostics ──")
    print(f"\n  How stable are domain effects as sample size changes?")

    # For each category, compute the coefficient and CI width at different sample fractions
    df_diag = df.dropna(subset=alt_control_sets["Full (all 6 controls)"]).copy()
    cf_full = " + ".join(alt_control_sets["Full (all 6 controls)"])
    fractions = [0.25, 0.50, 0.75, 1.0]

    print(f"\n  {'Category':<25s}", end="")
    for frac in fractions:
        print(f" {'n=' + str(int(frac*100)) + '%':>12s}", end="")
    print(f" {'Stable?':>10s}")
    print("  " + "-" * (25 + 12 * len(fractions) + 10))

    sample_size_results = []
    for cat in key_cats:
        if cat not in valid_cats:
            continue
        coefs_at_frac = []
        for frac in fractions:
            # Sample fraction of markets
            mkt_list = df_diag["market_ticker"].unique()
            n_sample = max(int(len(mkt_list) * frac), 20)
            sampled = rng.choice(mkt_list, min(n_sample, len(mkt_list)), replace=False)
            df_sub = df_diag[df_diag["market_ticker"].isin(sampled)]
            try:
                m = smf.ols(
                    f'squared_error ~ C(category, Treatment("{ref_cat}")) + C(horizon, Treatment("30+ days")) + {cf_full}',
                    data=df_sub
                ).fit(cov_type="cluster", cov_kwds={"groups": df_sub["market_ticker"]})
                param = [p for p in m.params.index if f"[T.{cat}]" in p]
                if param:
                    coef = float(m.params[param[0]])
                    p_val = float(m.pvalues[param[0]])
                    coefs_at_frac.append({"frac": frac, "coef": coef, "p": p_val, "sig": p_val < 0.05})
                else:
                    coefs_at_frac.append({"frac": frac, "coef": None, "p": None, "sig": False})
            except Exception:
                coefs_at_frac.append({"frac": frac, "coef": None, "p": None, "sig": False})

        # Print
        print(f"  {cat:<25s}", end="")
        for cf_entry in coefs_at_frac:
            if cf_entry["coef"] is not None:
                sig = "*" if cf_entry["sig"] else " "
                print(f" {cf_entry['coef']:+10.4f}{sig}", end="")
            else:
                print(f" {'N/A':>12s}", end="")

        # Stability: does sign stay consistent and significance hold at 50%+?
        valid_coefs = [c for c in coefs_at_frac if c["coef"] is not None]
        if len(valid_coefs) >= 3:
            signs = [np.sign(c["coef"]) for c in valid_coefs]
            stable = len(set(signs)) == 1 and all(c["sig"] for c in valid_coefs[-2:])
            print(f" {'Yes' if stable else 'No':>10s}")
        else:
            stable = False
            print(f" {'???':>10s}")

        sample_size_results.append({
            "category": cat,
            "coefficients_by_fraction": coefs_at_frac,
            "stable": stable,
        })

    # ── Plot ──
    _plot_adjusted_model(model_results, adjusted_cat_results, robustness_results, key_cats)

    return {
        "model_comparison": model_results,
        "category_results": adjusted_cat_results,
        "robustness": robustness_results,
        "sample_size": sample_size_results,
        "n_observations": len(df_model),
        "n_markets": int(df_model["market_ticker"].nunique()),
    }


def _plot_adjusted_model(model_results, cat_results, robustness_results, key_cats):
    """Plots for Analysis G."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 14))

    # Plot 1: Model comparison (3 models)
    ax = axes[0][0]
    names = [m["model"] for m in model_results]
    briers = [m["brier"] for m in model_results]
    colors = ["#d1d5db", "#93c5fd", "#2563eb"]
    ax.barh(range(len(names)), briers, color=colors)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=10)
    ax.set_xlabel("Brier Score (lower = better)")
    ax.set_title("Out-of-Sample: Adjusted Probability Models")
    for i, bs in enumerate(briers):
        ax.text(bs + 0.001, i, f"{bs:.4f}", va="center", fontsize=9)
    ax.grid(True, alpha=0.3, axis="x")

    # Plot 2: Per-category improvement (full model vs raw)
    ax = axes[0][1]
    cat_df = sorted(cat_results, key=lambda x: x["improvement_pct"])
    cats = [c["category"] for c in cat_df]
    imps = [c["improvement_pct"] for c in cat_df]
    colors = ["#10b981" if i > 0 else "#ef4444" for i in imps]
    ax.barh(range(len(cats)), imps, color=colors)
    ax.set_yticks(range(len(cats)))
    ax.set_yticklabels(cats, fontsize=9)
    ax.set_xlabel("Improvement (%)")
    ax.set_title("Full Model vs Raw Price: Per-Category Improvement")
    ax.axvline(0, color="black", linewidth=0.5)
    ax.grid(True, alpha=0.3, axis="x")

    # Plot 3: Robustness — R² lift across control sets
    ax = axes[1][0]
    set_names = [r["control_set"] for r in robustness_results]
    lifts = [r["r2_lift"] for r in robustness_results]
    ax.barh(range(len(set_names)), lifts, color="#8b5cf6", alpha=0.7)
    ax.set_yticks(range(len(set_names)))
    ax.set_yticklabels(set_names, fontsize=9)
    ax.set_xlabel("R² Lift from Domain")
    ax.set_title("Domain R² Lift Across Alternative Control Sets")
    for i, l in enumerate(lifts):
        ax.text(l + 0.001, i, f"+{l:.4f}", va="center", fontsize=9)
    ax.grid(True, alpha=0.3, axis="x")

    # Plot 4: Key category coefficients across control sets
    ax = axes[1][1]
    n_sets = len(robustness_results)
    n_cats = len(key_cats)
    width = 0.15
    x = np.arange(n_sets)

    cat_colors = {
        "Crypto": "#f97316", "Financials": "#ec4899", "Sports": "#ef4444",
        "Science and Technology": "#a855f7", "Entertainment": "#f59e0b",
    }

    for j, cat in enumerate(key_cats):
        vals = []
        for r in robustness_results:
            if cat in r["key_category_coefs"]:
                vals.append(r["key_category_coefs"][cat]["coef"])
            else:
                vals.append(0)
        ax.bar(x + j * width, vals, width, label=cat[:8],
               color=cat_colors.get(cat, "#666"), alpha=0.8)

    ax.set_xticks(x + width * n_cats / 2)
    ax.set_xticklabels([r["control_set"][:20] for r in robustness_results], fontsize=7, rotation=15)
    ax.set_ylabel("Coefficient (vs Politics)")
    ax.set_title("Domain Coefficients: Stability Across Control Sets")
    ax.axhline(0, color="black", linewidth=0.5)
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "adjusted_model_robustness.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Saved adjusted_model_robustness.png")


def compute_summary_stats(market_features, cal_ds):
    """Compute summary statistics for the dashboard."""
    mf = market_features.dropna(subset=["last_price", "brier_score"])

    def horizon_brier(d, col):
        """Brier at a fixed horizon, over the markets that lived that long."""
        dd = d.dropna(subset=[col])
        if len(dd) < 3:
            return None, 0
        return round(brier_score(dd[col].values, dd["result_binary"].values), 4), len(dd)

    # Per-category stats. brier_last_tick scores the final price before close,
    # which for categories whose outcome becomes public early (a called election
    # trades at 0.99 for days) is not a forecast at all — it is reported as a
    # diagnostic. brier_1d/7d are the honest comparison.
    cat_stats = {}
    for cat in mf["category"].value_counts().index:
        cd = mf[mf["category"] == cat]
        if len(cd) >= 3:
            b1, n1 = horizon_brier(cd, "brier_1d_before")
            b7, n7 = horizon_brier(cd, "brier_7d_before")
            cat_stats[cat] = {
                "n_markets": len(cd),
                "brier": round(brier_score(cd["last_price"].values, cd["result_binary"].values), 4),
                "brier_last_tick": round(brier_score(cd["last_price"].values, cd["result_binary"].values), 4),
                "brier_1d_before": b1,
                "n_markets_1d": n1,
                "brier_7d_before": b7,
                "n_markets_7d": n7,
                "avg_volume": round(cd["total_volume"].mean()),
                "yes_rate": round((cd["result"] == "yes").mean(), 3),
            }

    b1_all, _ = horizon_brier(mf, "brier_1d_before")
    b7_all, _ = horizon_brier(mf, "brier_7d_before")

    return {
        "total_markets": len(mf),
        "total_observations": len(cal_ds),
        # Categories actually reported (those clearing the 3-market floor), not
        # every category present — the two disagreed and the dashboard showed the
        # larger number above a chart with fewer bars.
        "n_categories": len(cat_stats),
        "n_categories_all": int(mf["category"].nunique()),
        "yes_outcomes": int((mf["result"] == "yes").sum()),
        "no_outcomes": int((mf["result"] == "no").sum()),
        "overall_brier_score": round(brier_score(mf["last_price"].values, mf["result_binary"].values), 4),
        "overall_brier_1d_before": b1_all,
        "overall_brier_7d_before": b7_all,
        "overall_log_loss": round(log_loss(mf["last_price"].values, mf["result_binary"].values), 4),
        "mean_volume": round(mf["total_volume"].mean()),
        "median_volume": round(mf["total_volume"].median()),
        "mean_duration_hours": round(mf["duration_hours"].mean(), 1),
        "n_hourly_clock_markets": int(mf["is_hourly_clock"].sum()) if "is_hourly_clock" in mf.columns else 0,
        "categories": mf["category"].value_counts().to_dict(),
        "liquidity_distribution": mf["liquidity_bucket"].value_counts().to_dict(),
        "category_stats": cat_stats,
    }
