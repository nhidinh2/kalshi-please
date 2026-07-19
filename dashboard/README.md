# Kalshi Calibration — Dashboard

Frontend for the Kalshi prediction-market calibration study. Built with React + Vite + Recharts.

```bash
npm install
npm run dev      # start the dev server
npm run build    # type-check and produce a production build in dist/
```

Data is read at runtime from `public/data/*.json`, which the Python pipeline
generates with `python run_analysis.py --export` (run from the repo root).
