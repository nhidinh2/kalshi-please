# Kalshi Prediction Market Calibration

**Do Kalshi prices mean the same thing across categories and time horizons?**

A 70-cent contract implies a 70% probability — but does that hold equally for politics at 30 days out versus crypto at 7 days out? This project measures calibration across domains and time, identifies what drives the differences, tests whether domain effects survive microstructure controls, and builds an out-of-sample recalibration layer.

**[Live Dashboard](https://dist-zeta-jade-85.vercel.app)** — interactive charts, calibration curves, and the full research report.

For a more detailed walkthrough of the analysis with code and plots, see [`analysis.ipynb`](analysis.ipynb).

## Findings

### A 70% price does not mean the same thing everywhere

Politics at 70% resolves correctly far more often than financials at 70%. Calibration varies by 4x across categories:

| Domain | Brier | Trust Level | Notes |
|---|---|---|---|
| Politics | 0.056 | High | Tight spreads, high volume, long duration |
| Entertainment | 0.050 | High (near resolution) | Improves from 0.190 to 0.050 over market life |
| Economics | 0.068 | Moderate | Reasonable microstructure |
| Crypto | 0.085 | Moderate (addressable) | After controls, coefficient flips *negative* — raw gap is entirely microstructure |
| Sports | 0.127 | Low | Noisy despite 4.6x more volume than Politics |
| Companies | 0.168 | Low | Associated with wide spreads, late surprise moves |
| Mentions | 0.244 | Unreliable | Few observations, wide spreads |
| Financials | 0.245 | Unreliable | Worst at every horizon |

### What is associated with poor calibration

At the category level (Spearman rank correlations):

- **Late price moves** (r=+0.72, p=0.005) — the strongest correlate. Categories with large last-minute price shifts tend to calibrate worse.
- **Late volume concentration** (r=+0.54, p=0.047) — back-loaded trading is associated with poorer price discovery.
- **Short duration** (r=-0.66, p=0.011) and **few price updates** (r=-0.61, p=0.022) — consistent with information aggregation requiring time.
- **Wide bid-ask spreads** (r=+0.27, p<0.001 at market level) — suggesting less competition and noisier signals.

### Domain effects survive controls

Five OLS models progressively add microstructure controls (volume, spread, duration, price range, base rate imbalance). The key test: does domain still matter after controlling for everything?

| Model | R² | Adj R² |
|---|---|---|
| Domain only | 13.8% | 13.7% |
| Domain + horizon | 14.3% | 14.2% |
| Domain + horizon + controls | 23.0% | 22.9% |
| Controls only (no domain) | 18.2% | 18.2% |
| Domain × horizon + controls | 24.7% | 24.4% |

**R² lift from domain: +4.7%.** Controls account for roughly half the gap (Financials drops from +0.38 to +0.20), but 11 of 12 categories remain significant (p<0.05). Domain itself retains independent predictive power. 23 of 36 domain × horizon interactions are significant — categories differ not just in level but in how they respond to time.

**Robustness:** Domain effects survive across five alternative control specifications (minimal, microstructure-only, full, no-spread, no-volume). R² lift ranges from +0.047 to +0.122. The Crypto sign-flip is stable across all specifications.

### Surprising cases

**Crypto flips sign.** Raw coefficient: +0.11 (worse than Politics). After controls: -0.08 (better). The reversal is consistent with Crypto's short duration (median 25 hrs vs 1,975 for Politics). The duration coefficient alone (-0.000015/hr × 1,950 hrs ≈ -0.03) accounts for a large share of the shift. The raw underperformance appears fully attributable to microstructure — longer-duration Crypto markets would likely calibrate as well as or better than Politics.

**Science & Technology flips the other way.** Raw: -0.07 (looks better than Politics). After controls: +0.04 (worse). Sci/Tech has a narrow price range (median 0.06 vs 0.25). The price range coefficient (+0.245/unit) provides a mechanical advantage that compresses squared errors regardless of forecast quality. The raw excellence appears partly an artifact of constrained outcome space.

**Financials: half survives.** Coefficient drops 47% from +0.38 to +0.20. Widest spreads (0.124), shortest duration (71 hrs), lowest volume (7.4K). Microstructure accounts for roughly half the gap, but the residual remains highly significant — consistent with financial outcomes being intrinsically harder to forecast.

**Sports: volume ≠ accuracy.** 4.6x Politics' volume yet worse calibration. The volume coefficient is *positive* (+0.010), suggesting high volume here reflects uncertainty-driven trading rather than informative price discovery.

### Out-of-sample recalibration

5-fold cross-validation (split by market, no data leakage) with Platt scaling per (category, horizon) group:

- **Overall: +1.5% Brier improvement** — modest but confirms the signal is real
- **Financials: +86.4%** — the worst-calibrated category benefits most
- **Crypto: +27.3%**, **Social: +22.7%**
- Small categories degrade (World -98.5%, Climate -47.1%) — insufficient data for stable fits
- **Bootstrap CIs:** 7 of 12 domain effects have 95% confidence intervals excluding zero

The recalibration layer helps most where it's needed most and fails where sample sizes are too small — the pattern expected from a real signal rather than overfitting.

A domain-adjusted probability model (logistic regression with raw price + domain + horizon) achieves **+8.4% Brier improvement** out-of-sample over raw Platt scaling — confirming these effects are exploitable.

## How It Works

### Pipeline

```
python run_analysis.py --all    # ingest → features → analyze → export
```

**1. Ingest** (`src/ingest/`) — Pulls resolved binary markets from the Kalshi public API across 15 categories. Fetches daily candlestick data with hourly backfill for short-lived markets.

**2. Features** (`src/processing/features.py`) — Computes per-market features: duration, volume, prices at 1/3/7 days before resolution, bid-ask spread, volatility, late price moves, price range, late volume share, Brier score. Builds a calibration dataset where each row is one (market, timestamp) observation.

**3. Analysis** (`src/analysis/calibration.py`) — Seven analyses:
- **A.** Accuracy over time (4 horizons)
- **B.** Domain × time interaction matrix
- **C.** Liquidity/volume effect
- **D.** Explanatory correlations + auto-generated category narratives
- **E.** Five OLS models with progressive controls + robustness checks across alternative control sets
- **F.** Out-of-sample recalibration (5-fold CV, Platt scaling, bootstrap CIs)
- **G.** Domain-adjusted probability model + sample-size diagnostics

**4. Dashboard** (`dashboard/`) — React + TypeScript + Recharts with four pages:
- **Overview** — Stat cards, Brier by category, Brier by horizon, domain × time heatmap
- **Calibration Explorer** — Interactive calibration curves with category/time/liquidity toggles and per-slice stats
- **Domain Effects** — Regression verdict, model comparison, before/after coefficients, bootstrap CIs, collapsible diagnostics (controls, narratives, correlations, scatter plots)
- **Practical Use** — Recalibration results, per-category improvement, searchable market table with price path detail

### Architecture

```
├── analysis.ipynb              # Full research notebook (8 sections)
├── run_analysis.py             # Pipeline entry point
├── src/
│   ├── ingest/
│   │   ├── kalshi_client.py    # Rate-limited API client
│   │   ├── database.py         # SQLite with upsert logic
│   │   └── pipeline.py         # Category-diverse collection
│   ├── processing/
│   │   └── features.py         # Feature engineering
│   └── analysis/
│       └── calibration.py      # All analyses + plotting
├── dashboard/                  # React + Vite + Recharts
│   └── src/pages/
│       ├── AccuracyDashboard   # Overview
│       ├── CalibrationExplorer # Calibration curves
│       ├── DomainEffects       # Regression + CIs
│       └── PracticalUse        # Recalibration + market explorer
└── data/                       # Generated: DB, CSVs, plots, JSON
```

## Data

- **Source:** Kalshi public API (no authentication required)
- **Scope:** 496 resolved binary markets, 15 categories, 15,834 price observations
- **Price data:** Daily candlesticks with hourly backfill for short-lived markets

## Setup

```bash
pip install -r requirements.txt

python run_analysis.py --all          # Full pipeline (~5 min)

# Or step by step:
python run_analysis.py --ingest       # Pull from Kalshi API
python run_analysis.py --features     # Compute features
python run_analysis.py --analyze      # Run analyses + plots
python run_analysis.py --export       # Export JSON for dashboard

cd dashboard && npm install && npm run dev
```

## Limitations

- Sample skews toward recently settled markets; some categories have few markets
- Historical candlestick availability varies — not all markets have retrievable price history
- Hourly backfill for short-lived markets creates uneven observation density
- Observation-level R² is 23% — substantial for cross-sectional market data, but individual outcomes remain noisy
- Standard errors assume independence across observations within the same market; clustered SEs would strengthen inference
- Sample-size diagnostics show instability for some category effects at <50% of data

## Technology

- **Pipeline:** Python, SQLite, pandas, requests
- **Analysis:** numpy, scipy, statsmodels, scikit-learn, matplotlib, seaborn
- **Dashboard:** React, TypeScript, Vite, Recharts
- **Data:** Kalshi public API (`/events`, `/markets`, `/series/.../candlesticks`)
