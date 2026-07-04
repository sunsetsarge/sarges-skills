import React, { useMemo, useState } from "react";

/**
 * PlanDashboard — self-contained React component that renders a financial
 * plan_model.json (see references/plan-model.md for the schema) as an
 * interactive dashboard. No external chart library: all charts are inline
 * SVG. Scenario sliders recompute displayed projections IN-MEMORY ONLY —
 * nothing here persists or sends data anywhere.
 *
 * Usage:
 *   <PlanDashboard planModel={planModel} />
 *
 * `planModel` must match the shared plan data model schema exactly
 * (field names are load-bearing — renderers must not rename them).
 */

const fmtMoney = (v, currency = "USD") =>
  v === null || v === undefined
    ? "n/a"
    : new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(v);

const fmtPct = (v) => (v === null || v === undefined ? "n/a" : `${v.toFixed(1)}%`);

function Card({ label, value, tone = "neutral" }) {
  const toneClass =
    tone === "bad" ? "pd-card-bad" : tone === "good" ? "pd-card-good" : "pd-card-neutral";
  return (
    <div className={`pd-card ${toneClass}`}>
      <div className="pd-card-label">{label}</div>
      <div className="pd-card-value">{value}</div>
    </div>
  );
}

function ProgressBar({ pct }) {
  const clamped = Math.max(0, Math.min(100, pct ?? 0));
  return (
    <div className="pd-progress-track">
      <div className="pd-progress-fill" style={{ width: `${clamped}%` }} />
    </div>
  );
}

function GoalsList({ goals }) {
  if (!goals || goals.length === 0) return <p className="pd-muted">No goals recorded.</p>;
  return (
    <div className="pd-goals">
      {goals.map((g) => {
        const pct = g.target_amount ? (100 * (g.current_amount || 0)) / g.target_amount : 0;
        return (
          <div key={g.id} className="pd-goal-row">
            <div className="pd-goal-header">
              <span>{g.name}</span>
              <span className="pd-muted">
                {fmtMoney(g.current_amount)} / {fmtMoney(g.target_amount)} ({pct.toFixed(0)}%)
              </span>
            </div>
            <ProgressBar pct={pct} />
            {g.target_date && <div className="pd-muted pd-goal-date">Target: {g.target_date}</div>}
          </div>
        );
      })}
    </div>
  );
}

function LineChartSVG({ series, width = 560, height = 220, colors }) {
  // series: [{label, points: [{x, y}, ...], color}]
  if (!series || series.length === 0) return null;
  const allX = series.flatMap((s) => s.points.map((p) => p.x));
  const allY = series.flatMap((s) => s.points.map((p) => p.y));
  const minX = Math.min(...allX), maxX = Math.max(...allX);
  const minY = 0, maxY = Math.max(...allY, 1);
  const pad = 32;
  const scaleX = (x) => pad + ((x - minX) / (maxX - minX || 1)) * (width - pad * 2);
  const scaleY = (y) => height - pad - ((y - minY) / (maxY - minY || 1)) * (height - pad * 2);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="pd-svg-chart" role="img" aria-label="Projection chart">
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="#D1D5DB" />
      <line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke="#D1D5DB" />
      {series.map((s, i) => {
        const d = s.points
          .map((p, idx) => `${idx === 0 ? "M" : "L"} ${scaleX(p.x)} ${scaleY(p.y)}`)
          .join(" ");
        return <path key={s.label} d={d} fill="none" stroke={s.color || (colors && colors[i]) || "#0F766E"} strokeWidth="2.5" />;
      })}
      {series[0].points.map((p) => (
        <text key={p.x} x={scaleX(p.x)} y={height - pad + 16} fontSize="10" textAnchor="middle" fill="#6B7280">
          {p.x}
        </text>
      ))}
    </svg>
  );
}

function BarChartSVG({ data, width = 560, height = 220 }) {
  // data: [{label, value}]
  if (!data || data.length === 0) return null;
  const pad = 32;
  const max = Math.max(...data.map((d) => d.value), 1);
  const barWidth = (width - pad * 2) / data.length - 8;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="pd-svg-chart" role="img" aria-label="Category spending chart">
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="#D1D5DB" />
      {data.map((d, i) => {
        const barHeight = ((height - pad * 2) * d.value) / max;
        const x = pad + i * ((width - pad * 2) / data.length) + 4;
        const y = height - pad - barHeight;
        return (
          <g key={d.label}>
            <rect x={x} y={y} width={barWidth} height={barHeight} fill="#0F766E" rx="2" />
            <text x={x + barWidth / 2} y={height - pad + 14} fontSize="9" textAnchor="middle" fill="#6B7280">
              {d.label.length > 8 ? `${d.label.slice(0, 7)}…` : d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function PlanDashboard({ planModel }) {
  const model = planModel || {};
  const currency = model.currency || "USD";
  const analysis = model.analysis || {};
  const netWorth = analysis.net_worth || {};
  const cashFlow = analysis.cash_flow || {};
  const emergencyFund = analysis.emergency_fund || {};
  const debt = analysis.debt || {};
  const retirement = analysis.retirement || {};
  const goals = (model.profile && model.profile.goals) || [];

  // --- Scenario sliders (in-memory only; no persistence, no network) ---
  const [savingsRateDelta, setSavingsRateDelta] = useState(0); // percentage points added to savings rate
  const [marketShockPct, setMarketShockPct] = useState(0); // negative = shock, applied to retirement scenarios

  const adjustedSavingsRate = (cashFlow.savings_rate_pct || 0) + savingsRateDelta;

  const adjustedProjection = useMemo(() => {
    const series = retirement.projection_series || [];
    const shockFactor = 1 + marketShockPct / 100;
    // Simple illustrative recompute: shock scales all projected values;
    // savings-rate delta nudges the base/best scenarios proportionally.
    const savingsBoost = 1 + savingsRateDelta / 100;
    return series.map((p) => ({
      age: p.age,
      best: (p.best || 0) * shockFactor * savingsBoost,
      base: (p.base || 0) * shockFactor * savingsBoost,
      worst: (p.worst || 0) * shockFactor,
    }));
  }, [retirement.projection_series, marketShockPct, savingsRateDelta]);

  const byCategory = cashFlow.by_category || {};
  const barData = Object.entries(byCategory).map(([label, value]) => ({ label, value }));

  const lineSeries = [
    { label: "Best", color: "#0F766E", points: adjustedProjection.map((p) => ({ x: p.age, y: p.best })) },
    { label: "Base", color: "#2563EB", points: adjustedProjection.map((p) => ({ x: p.age, y: p.base })) },
    { label: "Worst", color: "#B91C1C", points: adjustedProjection.map((p) => ({ x: p.age, y: p.worst })) },
  ];

  const avalanche = debt.avalanche || {};

  return (
    <div className="pd-root">
      <style>{styles}</style>

      <header className="pd-header">
        <h1>Financial Plan Dashboard</h1>
        <div className="pd-muted">
          Generated {model.generated_at || "unknown"} · {currency}
        </div>
      </header>

      <section className="pd-cards">
        <Card label="Net Worth" value={fmtMoney(netWorth.net, currency)} tone={netWorth.net >= 0 ? "good" : "bad"} />
        <Card label="Savings Rate" value={fmtPct(cashFlow.savings_rate_pct)} />
        <Card
          label="Emergency Runway"
          value={emergencyFund.runway_months != null ? `${emergencyFund.runway_months} mo` : "n/a"}
          tone={emergencyFund.gap > 0 ? "bad" : "good"}
        />
        <Card label="Total Debt" value={fmtMoney(debt.total, currency)} tone={debt.total > 0 ? "bad" : "good"} />
      </section>

      <section className="pd-section">
        <h2>Goal Progress</h2>
        <GoalsList goals={goals} />
      </section>

      <section className="pd-grid-2">
        <div className="pd-section">
          <h2>Spending by Category</h2>
          <BarChartSVG data={barData} />
        </div>
        <div className="pd-section">
          <h2>Debt Payoff</h2>
          <table className="pd-table">
            <thead>
              <tr><th>Strategy</th><th>Months to free</th><th>Total interest</th></tr>
            </thead>
            <tbody>
              <tr>
                <td>Avalanche</td>
                <td>{avalanche.months_to_free ?? "n/a"}</td>
                <td>{fmtMoney(avalanche.total_interest, currency)}</td>
              </tr>
              <tr>
                <td>Snowball</td>
                <td>{(debt.snowball || {}).months_to_free ?? "n/a"}</td>
                <td>{fmtMoney((debt.snowball || {}).total_interest, currency)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="pd-section">
        <h2>Retirement Scenario (what-if, in-memory only)</h2>
        <div className="pd-sliders">
          <label className="pd-slider-row">
            <span>Savings rate delta: {savingsRateDelta > 0 ? "+" : ""}{savingsRateDelta} pts (now {fmtPct(adjustedSavingsRate)})</span>
            <input
              type="range"
              min="-10"
              max="10"
              step="1"
              value={savingsRateDelta}
              onChange={(e) => setSavingsRateDelta(Number(e.target.value))}
            />
          </label>
          <label className="pd-slider-row">
            <span>Market shock: {marketShockPct}%</span>
            <input
              type="range"
              min="-50"
              max="20"
              step="5"
              value={marketShockPct}
              onChange={(e) => setMarketShockPct(Number(e.target.value))}
            />
          </label>
        </div>
        <LineChartSVG series={lineSeries} />
        <p className="pd-muted pd-small">
          Sliders recompute the chart above only — they do not change your saved plan_model.json
          or send data anywhere. This is an illustrative what-if, not a new projection run.
        </p>
      </section>

      <footer className="pd-footer">
        <p>{model.disclaimer ||
          "This is educational information, not licensed financial, investment, tax, or legal advice. Verify important decisions with a qualified professional."}</p>
        <p className="pd-small">No persistence, no network calls. Data lives only in this page while it is open.</p>
      </footer>
    </div>
  );
}

const styles = `
.pd-root { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1F2937; max-width: 960px; margin: 0 auto; padding: 16px; }
.pd-header h1 { font-size: 22px; margin: 0 0 4px 0; }
.pd-muted { color: #6B7280; font-size: 13px; }
.pd-small { font-size: 11px; }
.pd-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 20px 0; }
.pd-card { border-radius: 10px; padding: 14px 16px; background: #F0FDFA; border: 1px solid #D1D5DB; }
.pd-card-label { font-size: 12px; font-weight: 600; color: #374151; }
.pd-card-value { font-size: 24px; font-weight: 700; margin-top: 4px; }
.pd-card-good .pd-card-value { color: #0F766E; }
.pd-card-bad .pd-card-value { color: #B91C1C; }
.pd-section { margin: 24px 0; }
.pd-section h2 { font-size: 16px; margin-bottom: 8px; }
.pd-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
@media (max-width: 720px) { .pd-grid-2 { grid-template-columns: 1fr; } }
.pd-goal-row { margin-bottom: 12px; }
.pd-goal-header { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 4px; }
.pd-goal-date { margin-top: 2px; }
.pd-progress-track { background: #E5E7EB; border-radius: 6px; height: 8px; overflow: hidden; }
.pd-progress-fill { background: #0F766E; height: 100%; }
.pd-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pd-table th, .pd-table td { border: 1px solid #D1D5DB; padding: 6px 8px; text-align: left; }
.pd-table th { background: #1F2937; color: #fff; }
.pd-svg-chart { width: 100%; height: auto; }
.pd-sliders { display: flex; flex-direction: column; gap: 12px; margin-bottom: 12px; }
.pd-slider-row { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.pd-slider-row input[type="range"] { width: 100%; }
.pd-footer { border-top: 1px solid #D1D5DB; margin-top: 24px; padding-top: 12px; font-size: 12px; color: #6B7280; }
`;
