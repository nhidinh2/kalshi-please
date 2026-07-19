# Kalshi Prediction Market Calibration

**Do Kalshi prices mean the same thing across categories and time horizons?**

A 70-cent contract implies a 70% probability — but does that hold equally for politics at 30 days out versus crypto at 7 days out? This project measures calibration across domains and time, tests whether domain differences survive microstructure controls, and asks whether an out-of-sample recalibration layer can exploit them.

**[Live Dashboard](https://dist-zeta-jade-85.vercel.app)** — interactive charts, calibration curves, and the full research report.

For a detailed walkthrough with code and plots, see [`analysis.ipynb`](analysis.ipynb).

> **A note on the numbers.** An earlier version of this study reported much stronger findings (a 4× calibration spread, an out-of-sample recalibration gain, a Crypto "sign flip"). Several of those rested on measurement artifacts — scoring the final traded price after outcomes were public, using whole-lifetime market aggregates as controls (which leak the outcome), a broken bootstrap, and non-clustered standard errors. This version fixes them. The corrected findings are weaker and, in one case, reverse. That is the honest result, and the methodology section explains each correction.

## Findings

### The final traded price is not a forecast

The single most important correction. Scoring a market by its *last* traded price flatters any category whose outcome becomes public before the market technically closes — a called election trades at 0.99 for days. Measured that way, Elections score a Brier of 0.0004 and Social 0.0004, which looks like near-perfect forecasting but is really just reading the answer off the back of the book.

Scored one day before close — while the outcome is still genuinely uncertain — the ranking changes and the whole board gets worse:

| Domain | Brier @ last tick | Brier @ 1 day before | Markets (1d) |
|---|---|---|---|
| Climate and Weather | 0.090 | **0.107** | 22 |
| Politics | 0.056 | **0.160** | 57 |
| Science and Technology | 0.003 | 0.168 | 6 |
| World | 0.005 | 0.169 | 11 |
| Companies | 0.168 | 0.243 | 40 |
| Entertainment | 0.050 | 0.308 | 43 |
| Elections | 0.0004 | 0.361 | 16 |
| Sports | 0.127 | 0.340 | 70 |
| Financials | 0.245 | 0.395 | 21 |
| Economics | 0.068 | **0.535** | 29 |
| Social | 0.0004 | **0.599** | 10 |

Politics and Climate genuinely forecast well a day out (~0.11–0.16). Economics and Social — which looked mid-pack or excellent at the last tick — are barely better than a coin flip once you score them before the result is known. Small categories (Crypto n=4, Sci/Tech n=6 at this horizon) are too thin to rank and are shown for completeness only.

### Domain still carries independent signal, but less than it first appeared

Five OLS models on the observation-level data (~15,800 price observations in 483 markets) progressively add microstructure controls. Two things changed versus the original write-up: the controls are now **point-in-time** (computed from each market's past as of the observation, not its whole life), and standard errors are **clustered by market** (observations from one market share a price path and are far from independent).

| Model | R² |
|---|---|
| Domain only | 13.8% |
| Domain + horizon | 14.3% |
| Domain + horizon + point-in-time controls | 14.7% |
| Controls only (no domain) | 9.9% |
| Domain × horizon + controls | 16.9% |

**R² lift from domain: +4.9%.** Domain adds explanatory power beyond microstructure. But the observation-level R² is **14.7%, not the 23% reported earlier** — the gap was lookahead: the old "price range" control was computed over the market's entire life, so it partly encoded how far the price eventually travelled toward the outcome it was supposed to predict.

Under clustered standard errors, **5 of 12 categories remain significantly different from Politics** (Companies, Financials, Mentions, Social, Sports) — not the 11 claimed before. Clustering roughly triples the honest standard errors, so most category effects that looked significant under IID errors no longer clear the bar. Of the domain × horizon interactions, 11 of 36 are significant.

### Financials really is worse; the "Crypto flips sign" story does not survive

**Financials** is the most robustly poorly-calibrated category. Coefficient +0.38 raw, +0.32 after point-in-time controls (p=0.001), widest spreads, shortest duration. Microstructure explains little of the gap — financial outcomes appear intrinsically hard to forecast.

**Crypto no longer flips.** The original claim was that Crypto looks worse than Politics raw (+0.11) but *better* after controls (−0.08), attributed to its short duration. That reversal was an artifact of the lookahead controls. With point-in-time controls, Crypto's coefficient goes from +0.09 raw to +0.06 controlled — it never crosses zero, and it is not significantly different from Politics (p=0.25). Restricting to markets with genuine daily candles (dropping the hourly-backfilled ones, which are disproportionately Crypto and Sports) gives +0.04, also not significant. The honest statement is: **Crypto is indistinguishable from Politics**, not better than it.

**Sports** stays significantly worse (+0.15, p=0.01) and survives the daily-only check (+0.12, p=0.02) — so its poor calibration is not a clock artifact. It has 4.6× Politics' volume yet worse calibration; volume here does not buy accuracy.

### Bootstrap confidence intervals (now valid)

The original bootstrap collapsed duplicate draws via `.isin()`, turning each "replicate" into a ~63% subsample and widening every interval. Resampling markets with correct multiplicity, **5 of 12 domain effects have 95% CIs excluding zero**: Companies, Financials, Mentions, Sports (worse than Politics) and Science & Technology (better). The rest, including Crypto and Climate, are indistinguishable from Politics.

### Out-of-sample recalibration does not reliably help

A Platt-scaling recalibration layer per (category, horizon), evaluated with 5-fold cross-validation split by market. The headline changed sign under scrutiny.

- **Overall: −0.6% Brier, ± 0.7% (SE) across 10 fold splits** — indistinguishable from zero. The earlier "+1.5% improvement" came from a single lucky fold split; re-running with different splits, the number swings between −5.6% and +2.2% and averages slightly negative. **The layer does not improve calibration overall.**
- Where it *does* help is exactly where miscalibration is large: **Crypto +65%, Financials +60%, Companies +20%**. Where it hurts is small or already-good categories: **Science & Technology −256%, World −82%, Climate −67%**. It is a redistribution, not a free lunch, and on this sample the losses roughly cancel the gains.

A domain-adjusted probability model (logistic regression, price + domain + horizon) does earn a real **+5.2% out-of-sample Brier improvement** over raw price — domain and horizon carry exploitable signal. But *adding* microstructure features to that model makes it **worse** (+1.5%, below domain alone), because the microstructure edge in the original write-up came from the same lookahead that inflated the regression R².

**Bottom line:** category and horizon do mean something beyond raw price, and a model conditioning on them beats raw price out-of-sample. But the effect is modest, concentrated in a few badly-calibrated categories, and does not support a general-purpose recalibration layer.

## How It Works

### Pipeline

```
python run_analysis.py --all    # ingest → features → analyze → export
```

**1. Ingest** (`src/ingest/`) — Pulls resolved binary markets from the Kalshi public API. Fetches daily candlestick data, with hourly backfill for short-lived markets that lack daily candles.

**2. Features** (`src/processing/features.py`) — Computes per-market features: duration, volume, prices at 1/3/7 days before resolution, spread, volatility, price range, Brier scores at the last tick *and* at fixed horizons. Builds an observation-level calibration dataset with **point-in-time** microstructure (expanding aggregates using only each observation's past) and drops post-close candles. Clock-dependent features (volatility, volume share) are normalized to a per-day basis so hourly-backfilled markets are comparable.

**3. Analysis** (`src/analysis/calibration.py`) — Seven analyses:
- **A.** Accuracy over time (4 horizons)
- **B.** Domain × time interaction matrix
- **C.** Liquidity/volume effect
- **D.** Explanatory correlations + category narratives
- **E.** Five OLS models with progressive point-in-time controls, clustered SEs
- **F.** Out-of-sample recalibration (5-fold CV, Platt scaling, seed-stability check, corrected bootstrap CIs)
- **G.** Domain-adjusted probability model + robustness (alternative control sets, daily-only subsample, sample-size diagnostics)

**4. Dashboard** (`dashboard/`) — React + TypeScript + Recharts. Overview, Calibration Explorer, Domain Effects, Practical Use.

### Architecture

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

## Data

- **Source:** Kalshi public API (no authentication required)
- **Scope:** ~430 resolved binary markets, 13 reported categories, ~15,800 pre-close price observations
- **Price data:** Daily candlesticks, with hourly backfill for short-lived markets (36 markets, flagged and normalized)
- **Selection:** markets are drawn top-by-volume within each category (see Limitations) — the sample is not a random draw of Kalshi markets

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

## What changed from the first version, and why

Each fix and the direction it moved the result:

- **Scored the last traded price** → also score 1/3/7 days before close. The last tick reads outcomes that are already public; fixed-horizon Brier is the real test. *Effect: the category ranking changes and every category looks worse.*
- **Whole-lifetime controls (price range, volume, spread)** → point-in-time expanding versions. Lifetime aggregates describe each market's future relative to the observation being predicted; lifetime price range in particular leaks the outcome. *Effect: observation-level R² drops from 23% to 14.7%.*
- **IID standard errors** → clustered by market. ~15,800 observations come from only ~480 markets and are highly correlated within market. *Effect: significant categories drop from 11 to 5.*
- **Broken bootstrap** (`.isin()` collapsed duplicate draws) → resample markets with correct multiplicity. *Effect: intervals tighten; 5 of 12 effects exclude zero.*
- **Single-split recalibration number** → mean ± SE across 10 fold splits. *Effect: +1.5% gain revealed as split noise; true effect ≈ 0.*
- **Hourly/daily clock mismatch** → per-day normalization + a daily-only robustness check. *Effect: the Crypto sign-flip disappears.*
- **`statsmodels` missing from requirements** → added. *Effect: the pipeline runs from a clean install.*

## Limitations

- **Selection bias:** markets are chosen top-by-volume within each category, so the sample is range-restricted on volume — the very variable Analysis C studies and that appears as a control throughout. Findings describe high-volume markets, not Kalshi as a whole.
- **Small categories are unstable:** several categories have fewer than 20 markets, and the fixed-horizon Brier scores for them rest on a handful of markets. Treat per-category numbers below ~20 markets as suggestive only.
- **Fixed-horizon Brier is right-censored:** the 7-day-before score only exists for markets that lived at least 7 days, which is itself a biased subset.
- **Sample skews toward recently settled markets** and historical candlestick availability varies.
- **Point-in-time controls remove lookahead but not endogeneity:** contemporaneous spread and accumulated volume are still jointly determined with price quality.
- Individual outcomes remain noisy; 14.7% observation-level R² is substantial for cross-sectional market data but leaves most variance unexplained.

## Technology

- **Pipeline:** Python, SQLite, pandas, requests
- **Analysis:** numpy, scipy, statsmodels, scikit-learn, matplotlib, seaborn
- **Dashboard:** React, TypeScript, Vite, Recharts
- **Data:** Kalshi public API (`/events`, `/markets`, `/series/.../candlesticks`)
