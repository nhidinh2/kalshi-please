import { useDashboardData, useSummary } from "../hooks/useData";

const S: Record<string, React.CSSProperties> = {
  section: { marginBottom: "2.5rem" },
  h2: { fontSize: "1.25rem", fontWeight: 700, marginBottom: "1rem", paddingBottom: "0.5rem", borderBottom: "2px solid #e5e7eb" },
  h3: { fontSize: "1.05rem", fontWeight: 600, marginBottom: "0.75rem", color: "#374151" },
  p: { fontSize: "0.92rem", lineHeight: 1.75, color: "#374151", marginBottom: "0.75rem" },
  li: { fontSize: "0.92rem", lineHeight: 1.75, color: "#374151", marginBottom: "0.5rem" },
  metric: { fontWeight: 700, color: "#2563eb" },
  muted: { fontSize: "0.85rem", color: "#6b7280", fontStyle: "italic" as const },
  callout: {
    padding: "1rem 1.25rem",
    background: "rgba(37, 99, 235, 0.04)",
    borderLeft: "4px solid #2563eb",
    borderRadius: "0 6px 6px 0",
    marginBottom: "1rem",
  },
  calloutWarn: {
    padding: "1rem 1.25rem",
    background: "rgba(245, 158, 11, 0.06)",
    borderLeft: "4px solid #f59e0b",
    borderRadius: "0 6px 6px 0",
    marginBottom: "1rem",
  },
};

const fmt = (v: number | null | undefined, d = 3) =>
  v == null ? "—" : v.toFixed(d);

export function Report() {
  const { data: summary, loading: ls } = useSummary();
  const { data: dash, loading: ld } = useDashboardData();

  if (ls || ld) return <div className="loading">Loading...</div>;
  if (!summary || !dash) return <div className="loading">No data available.</div>;

  const reg = dash.regression;
  const recal = dash.recalibration;
  const cs = summary.category_stats;

  // Forecasting table: each category's Brier at the last tick vs one day before
  // close, sorted by the honest (1-day) number. Only categories with enough
  // markets a day out are ranked.
  const forecastRows = Object.entries(cs)
    .filter(([, s]) => s.brier_1d_before != null && s.n_markets_1d >= 5)
    .map(([domain, s]) => ({
      domain,
      last: s.brier_last_tick,
      d1: s.brier_1d_before as number,
      n1: s.n_markets_1d,
    }))
    .sort((a, b) => a.d1 - b.d1);

  // Domain coefficients, worst (most positive vs Politics) first.
  const coefs = [...reg.domain_coefficients].sort(
    (a, b) => b.coef_with_controls - a.coef_with_controls
  );
  const financials = coefs.find((c) => c.category === "Financials");
  const sports = coefs.find((c) => c.category === "Sports");
  const crypto = coefs.find((c) => c.category === "Crypto");

  const recalMean = recal.improvement_mean_pct;
  const recalSE = recal.improvement_se_pct;
  const catImp = [...recal.category_improvements].sort(
    (a, b) => b.improvement_pct - a.improvement_pct
  );
  const topGain = catImp.slice(0, 3);
  const topLoss = catImp.slice(-3).reverse();
  const nSigCI = recal.confidence_intervals.filter((c) => c.significant).length;

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      {/* ── Title ── */}
      <div style={{ textAlign: "center", marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.75rem", fontWeight: 700, marginBottom: "0.5rem" }}>
          Kalshi Prediction Market Calibration
        </h1>
        <p style={{ ...S.muted, fontSize: "0.95rem" }}>
          {summary.total_markets.toLocaleString()} resolved markets across{" "}
          {summary.n_categories} categories, {summary.total_observations.toLocaleString()} pre-close price observations
        </p>
      </div>

      {/* ── Correction notice ── */}
      <div style={S.section}>
        <div style={S.calloutWarn}>
          <p style={{ ...S.p, marginBottom: 0 }}>
            <strong>A note on the numbers.</strong> An earlier version reported much
            stronger results — a 4× calibration spread, an out-of-sample recalibration
            gain, and a Crypto "sign flip." Several rested on measurement artifacts:
            scoring the final traded price after outcomes were public, whole-lifetime
            controls that leak the outcome, a broken bootstrap, and non-clustered
            standard errors. This version fixes them. The corrected findings are weaker,
            and one reverses.
          </p>
        </div>
      </div>

      {/* ── Research Question ── */}
      <div style={S.section}>
        <div style={S.callout}>
          <p style={{ ...S.p, marginBottom: 0, fontWeight: 500 }}>
            <strong>Research question:</strong> A 70-cent contract on Kalshi implies a 70% probability.
            Does that hold equally for politics at 30 days out versus crypto at 7 days out?
            And if not — what drives the difference, and can we correct it?
          </p>
        </div>
      </div>

      {/* ── 1. Last tick is not a forecast ── */}
      <div style={S.section}>
        <h2 style={S.h2}>1. The final traded price is not a forecast</h2>
        <p style={S.p}>
          Scoring a market by its <em>last</em> traded price flatters any category whose
          outcome becomes public before the market technically closes — a called election
          trades at 0.99 for days. Measured that way, Elections and Social score a Brier
          near <span style={S.metric}>0.0004</span>, which looks like near-perfect
          forecasting but is really reading the answer off the back of the book.
        </p>
        <p style={S.p}>
          Scored <strong>one day before close</strong> — while the outcome is still genuinely
          uncertain — the ranking changes and the whole board gets worse:
        </p>

        <div className="table-container" style={{ marginTop: "1rem" }}>
          <table>
            <thead>
              <tr>
                <th>Domain</th>
                <th style={{ textAlign: "center" }}>Brier @ last tick</th>
                <th style={{ textAlign: "center" }}>Brier @ 1 day before</th>
                <th style={{ textAlign: "center" }}>Markets (1d)</th>
              </tr>
            </thead>
            <tbody>
              {forecastRows.map((row) => (
                <tr key={row.domain}>
                  <td style={{ fontWeight: 600 }}>{row.domain}</td>
                  <td style={{ textAlign: "center", fontFamily: "monospace", color: "#9ca3af" }}>
                    {fmt(row.last)}
                  </td>
                  <td style={{ textAlign: "center", fontFamily: "monospace", fontWeight: 600 }}>
                    {fmt(row.d1)}
                  </td>
                  <td style={{ textAlign: "center", color: "#6b7280" }}>{row.n1}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p style={{ ...S.p, marginTop: "1rem" }}>
          Politics and Climate genuinely forecast well a day out. Economics and Social —
          which looked mid-pack or excellent at the last tick — are barely better than a
          coin flip once scored before the result is known.
        </p>
        <p style={S.muted}>
          Categories with fewer than 5 markets one day out are omitted as too thin to rank.
        </p>
      </div>

      {/* ── 2. Controls ── */}
      <div style={S.section}>
        <h2 style={S.h2}>2. Domain carries signal beyond microstructure — but less than it first appeared</h2>
        <p style={S.p}>
          Five OLS models on the observation-level data progressively add microstructure
          controls. The controls are now <strong>point-in-time</strong> (computed from each
          market's past as of the observation, not its whole life), and standard errors are{" "}
          <strong>clustered by market</strong>.
        </p>

        <div className="table-container" style={{ marginBottom: "1rem" }}>
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th style={{ textAlign: "center" }}>R²</th>
                <th style={{ textAlign: "center" }}>Adj R²</th>
              </tr>
            </thead>
            <tbody>
              {reg.model_comparison.map((m) => (
                <tr key={m.model}>
                  <td>{m.model}</td>
                  <td style={{ textAlign: "center" }}>{(m.r2 * 100).toFixed(1)}%</td>
                  <td style={{ textAlign: "center" }}>{(m.adj_r2 * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={S.callout}>
          <p style={{ ...S.p, marginBottom: 0 }}>
            <strong>R² lift from domain: +{(reg.r2_lift * 100).toFixed(1)}%.</strong> Domain
            adds explanatory power beyond microstructure. But the observation-level R² is{" "}
            <span style={S.metric}>{(reg.r2_with_domain * 100).toFixed(1)}%</span>, not the 23%
            reported earlier — the gap was lookahead. Under clustered errors,{" "}
            <span style={S.metric}>{reg.surviving_domains.length} of {reg.domain_coefficients.length}</span>{" "}
            categories remain significantly different from {reg.reference_category} (p&lt;0.05),
            not the 11 claimed before. {reg.n_sig_interactions} of {reg.n_interactions} domain ×
            horizon interactions are significant.
          </p>
        </div>
      </div>

      {/* ── 3. Cases ── */}
      <div style={S.section}>
        <h2 style={S.h2}>3. Which categories actually differ</h2>

        <h3 style={S.h3}>Financials: robustly worse</h3>
        <p style={S.p}>
          The most reliably poorly-calibrated category. Coefficient{" "}
          {fmt(financials?.coef_no_controls, 2)} raw,{" "}
          <strong>{fmt(financials?.coef_with_controls, 2)}</strong> after point-in-time
          controls (p={fmt(financials?.p_with_controls, 3)}). Microstructure explains little
          of the gap — financial outcomes appear intrinsically hard to forecast.
        </p>

        <h3 style={S.h3}>Sports: worse, and not a clock artifact</h3>
        <p style={S.p}>
          Coefficient <strong>{fmt(sports?.coef_with_controls, 2)}</strong>{" "}
          (p={fmt(sports?.p_with_controls, 3)}), and it survives a robustness check restricted
          to markets with genuine daily candles. Sports has 4.6× Politics' volume yet worse
          calibration — volume here does not buy accuracy.
        </p>

        <h3 style={S.h3}>Crypto: the "sign flip" does not survive</h3>
        <p style={S.p}>
          The earlier claim was that Crypto looks worse than Politics raw but <em>better</em> after
          controls, attributed to short duration. That reversal was an artifact of the lookahead
          controls. With point-in-time controls, Crypto goes from{" "}
          {fmt(crypto?.coef_no_controls, 2)} raw to{" "}
          <strong>{fmt(crypto?.coef_with_controls, 2)}</strong> controlled — it never crosses
          zero and is not significantly different from Politics
          (p={fmt(crypto?.p_with_controls, 2)}). The honest statement: Crypto is
          indistinguishable from Politics, not better than it.
        </p>
      </div>

      {/* ── 4. Recalibration ── */}
      <div style={S.section}>
        <h2 style={S.h2}>4. Out-of-sample recalibration does not reliably help</h2>
        <p style={S.p}>
          A Platt-scaling recalibration layer per (category, horizon), evaluated with 5-fold
          cross-validation split by market. The headline changed sign under scrutiny.
        </p>

        <div style={S.calloutWarn}>
          <p style={{ ...S.p, marginBottom: 0 }}>
            <strong>Overall: {recalMean >= 0 ? "+" : ""}{recalMean.toFixed(1)}% Brier,
            ± {recalSE.toFixed(1)}% (SE) across {recal.n_seeds} fold splits</strong> —
            indistinguishable from zero. The earlier "+1.5% improvement" came from a single
            lucky fold split; re-running with different splits, the number ranges from{" "}
            {recal.improvement_range_pct[0].toFixed(1)}% to {recal.improvement_range_pct[1].toFixed(1)}%.
            The layer does not improve calibration overall.
          </p>
        </div>

        <p style={S.p}>
          Where it <em>does</em> help is where miscalibration is large; where it hurts is small
          or already-good categories. It is a redistribution, not a free lunch:
        </p>
        <ul style={{ paddingLeft: "1.5rem", marginBottom: "1rem" }}>
          <li style={S.li}>
            <strong>Helps:</strong>{" "}
            {topGain.map((c) => `${c.category} +${c.improvement_pct.toFixed(0)}%`).join(", ")}
          </li>
          <li style={S.li}>
            <strong>Hurts:</strong>{" "}
            {topLoss.map((c) => `${c.category} ${c.improvement_pct.toFixed(0)}%`).join(", ")}
          </li>
          <li style={S.li}>
            <strong>Bootstrap CIs (corrected):</strong> {nSigCI} of{" "}
            {recal.confidence_intervals.length} domain effects have 95% intervals excluding zero
          </li>
        </ul>
        <p style={S.p}>
          A domain-adjusted probability model (logistic regression, price + domain + horizon)
          does earn a real <strong>+5.2%</strong> out-of-sample improvement over raw price —
          domain and horizon carry exploitable signal. But adding microstructure features makes
          it <em>worse</em>, because that edge came from the same lookahead that inflated the
          regression R².
        </p>
      </div>

      {/* ── 5. Bottom line ── */}
      <div style={S.section}>
        <h2 style={S.h2}>5. The bottom line</h2>
        <p style={S.p}>
          Category and horizon do mean something beyond raw price: a model conditioning on them
          beats raw price out-of-sample, and Financials and Sports are reliably worse-calibrated
          than Politics even after controls. But the effect is modest, concentrated in a few
          badly-calibrated categories, and does not support a general-purpose recalibration layer.
          Several of the original headline findings — a 4× spread, a universal recalibration
          gain, the Crypto reversal — were artifacts of how accuracy was measured.
        </p>
      </div>

      {/* ── Methodology ── */}
      <div style={S.section}>
        <h2 style={S.h2}>Methodology & corrections</h2>
        <ul style={{ paddingLeft: "1.5rem" }}>
          <li style={S.li}>
            <strong>Scored the last traded price</strong> → also score 1/3/7 days before close.
            The last tick reads outcomes already public. <em>Category ranking changes; everything looks worse.</em>
          </li>
          <li style={S.li}>
            <strong>Whole-lifetime controls</strong> → point-in-time expanding versions.
            Lifetime aggregates leak the outcome. <em>Observation-level R² drops 23% → {(reg.r2_with_domain * 100).toFixed(1)}%.</em>
          </li>
          <li style={S.li}>
            <strong>IID standard errors</strong> → clustered by market.
            <em> Significant categories drop 11 → {reg.surviving_domains.length}.</em>
          </li>
          <li style={S.li}>
            <strong>Broken bootstrap</strong> (duplicate draws collapsed) → correct multiplicity.
          </li>
          <li style={S.li}>
            <strong>Single-split recalibration number</strong> → mean ± SE across {recal.n_seeds} splits.
            <em> +1.5% gain revealed as split noise.</em>
          </li>
          <li style={S.li}>
            <strong>Hourly/daily clock mismatch</strong> → per-day normalization + daily-only check.
            <em> The Crypto sign-flip disappears.</em>
          </li>
        </ul>
        <p style={{ ...S.p, marginTop: "1rem" }}>
          <strong>Data:</strong> {summary.total_markets} resolved binary markets from the Kalshi
          public API, {summary.total_observations.toLocaleString()} pre-close price observations
          (daily candlesticks, hourly backfill for {summary.n_hourly_clock_markets} short-lived
          markets). Markets selected top-by-volume within category, so the sample is not
          representative of Kalshi as a whole.
        </p>
      </div>

      <div style={{ textAlign: "center", padding: "2rem 0", color: "#9ca3af", fontSize: "0.8rem" }}>
        Use the tabs above to explore the interactive charts and data.
      </div>
    </div>
  );
}
