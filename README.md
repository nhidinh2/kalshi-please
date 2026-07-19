# Kalshi Prediction Market Calibration

**Do Kalshi prices mean the same thing across categories and time horizons?**

A 70-cent contract implies a 70% probability — but does that hold equally for politics 30 days out versus crypto 7 days out? This project measures calibration across domains and time, tests whether domain differences survive microstructure controls, and asks whether an out-of-sample recalibration layer can exploit them.

**[Live Dashboard](https://dist-zeta-jade-85.vercel.app)** — interactive charts, calibration curves, and the full report. Code walkthrough with plots in [`analysis.ipynb`](analysis.ipynb).

## Findings

**Score before the outcome is public.** A market's *last* traded price is not a forecast — a called election trades at 0.99 for days. Scored one day before close, while the result is still uncertain, calibration is far weaker and the category ranking reshuffles. Politics and Climate forecast well a day out (Brier ~0.11–0.16); Economics and Social are barely better than a coin flip (~0.53–0.60).

**Domain carries real signal beyond microstructure.** Across five OLS models on ~15,800 observations in ~480 markets (point-in-time controls, standard errors clustered by market), domain adds **+4.9% R²** over microstructure alone; the full model reaches **14.7%**. Under clustered errors, **5 of 12 categories** differ significantly from Politics (Companies, Financials, Mentions, Social, Sports), and bootstrap 95% CIs exclude zero for those five plus Science & Technology.

**Financials is the worst-calibrated category** — coefficient +0.32 after controls (p=0.001), widest spreads, shortest duration; microstructure explains little of the gap. **Sports** is also significantly worse (+0.15, p=0.01) and stays worse on daily-clock markets only, despite 4.6× Politics' volume — volume here does not buy accuracy. **Crypto is indistinguishable from Politics** (+0.06 controlled, p=0.25).

**Recalibration doesn't reliably help.** A Platt-scaling layer per (category, horizon), 5-fold CV split by market, moves overall Brier by **−0.6% ± 0.7%** — indistinguishable from zero. It helps where miscalibration is large (Crypto, Financials, Companies) and hurts small or already-good categories: a redistribution, not a free lunch. A domain-adjusted logistic model (price + domain + horizon) *does* beat raw price out-of-sample by **+5.2%** — the exploitable signal is in category and horizon, not microstructure.

**Bottom line:** category and horizon mean something beyond raw price, and a model conditioning on them beats raw price. But the effect is modest, concentrated in a few badly-calibrated categories, and does not support a general-purpose recalibration layer.

## How It Works

```
python run_analysis.py --all    # ingest → features → analyze → export
```

1. **Ingest** (`src/ingest/`) — Pulls resolved binary markets from the Kalshi public API, with daily candlesticks and hourly backfill for short-lived markets.
2. **Features** (`src/processing/features.py`) — Per-market features (duration, volume, prices at 1/3/7 days before resolution, spread, volatility, Brier at last tick and fixed horizons) plus an observation-level calibration dataset with **point-in-time** microstructure (expanding aggregates using only each observation's past). Clock-dependent features are normalized per-day so hourly-backfilled markets are comparable.
3. **Analysis** (`src/analysis/calibration.py`) — Seven analyses: (A) accuracy over time, (B) domain × time matrix, (C) liquidity effect, (D) explanatory correlations, (E) five OLS models with point-in-time controls and clustered SEs, (F) out-of-sample recalibration, (G) domain-adjusted probability model + robustness.
4. **Dashboard** (`dashboard/`) — React + TypeScript + Recharts.

```
├── analysis.ipynb              # Research notebook
├── run_analysis.py             # Pipeline entry point
├── src/
│   ├── ingest/                 # API client, SQLite, collection
│   ├── processing/features.py  # Feature engineering (point-in-time)
│   └── analysis/calibration.py # All analyses + plotting
├── dashboard/                  # React + Vite + Recharts
└── data/                       # Generated: DB, CSVs, plots, JSON
```

## Setup

```bash
pip install -r requirements.txt
python run_analysis.py --all          # Full pipeline (~5 min)
cd dashboard && npm install && npm run dev
```

Steps also run individually: `--ingest`, `--features`, `--analyze`, `--export`.

## Data & Scope

- **Source:** Kalshi public API (`/events`, `/markets`, `/series/.../candlesticks`), no auth required
- **Scope:** ~430 resolved binary markets, 13 categories, ~15,800 pre-close price observations
- **Selection:** markets are drawn top-by-volume within each category, so the sample is range-restricted on volume — findings describe high-volume markets, not Kalshi as a whole. Several categories have <20 markets and should be read as suggestive; fixed-horizon Brier is right-censored (the 7-day score only exists for markets that lived ≥7 days).

## Technology

Python, SQLite, pandas, numpy, scipy, statsmodels, scikit-learn, matplotlib/seaborn · React, TypeScript, Vite, Recharts.
