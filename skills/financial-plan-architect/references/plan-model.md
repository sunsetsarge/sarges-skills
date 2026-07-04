# Plan Data Model (single source of truth)

Every render target (Excel, PDF, React, HTML, PWA) is a pure function of one JSON
document, `plan_model.json`. Scripts consume and produce this exact shape — keep field
names stable; renderers and the refresh path depend on them.

Dates are ISO `YYYY-MM-DD`. Money is a float in `currency` units (default `USD`).
Account numbers are ALWAYS masked to last-4 (`"mask": "1234"`) — never store the full
number anywhere in this file.

```json
{
  "schema_version": 1,
  "generated_at": "2026-07-04",
  "currency": "USD",

  "profile": {
    "name": null,
    "risk_tolerance": "low|moderate|high|null",
    "income_structure": "steady|irregular|mixed",
    "working_style_notes": "free text: automation-lover, abandons recurring chores, ...",
    "tone": "technical-concise|scaffolded-gentle|default",
    "goals": [
      {"id": "g1", "name": "Emergency fund", "target_amount": 15000.0,
       "target_date": "2027-06-30", "current_amount": 4000.0,
       "priority": 1, "horizon": "short|mid|long"}
    ]
  },

  "accounts": [
    {"id": "a1", "name": "Checking", "institution": "Bank X", "mask": "1234",
     "type": "checking|savings|brokerage|retirement|credit_card|loan|mortgage|other",
     "balance": 5230.12, "as_of": "2026-07-01", "apr_or_apy": 0.045,
     "is_liability": false,
     "source": "export|connector|manual|screenshot"}
  ],

  "transactions": [
    {"date": "2026-06-15", "account_id": "a1", "amount": -82.50,
     "description": "HARRIS TEETER 041", "category": "groceries",
     "is_income": false, "is_transfer": false}
  ],

  "holdings": [
    {"account_id": "a3", "symbol": "VTI", "quantity": 41.2, "cost_basis": 8200.0,
     "last_price": 289.31, "price_as_of": "2026-07-03", "asset_class": "us_equity"}
  ],

  "market_context": {
    "as_of": "2026-07-03",
    "rates": {"savings_hy_apy": null, "cd_12mo": null, "mortgage_30y": null,
              "treasury_10y": null, "inflation_cpi_yoy": null},
    "sentiment_notes": [
      {"topic": "VTI", "summary": "…", "source": "r/Bogleheads", "date": "2026-07-01",
       "flag": "none|hype|thin-sourcing|pump-like"}
    ]
  },

  "assumptions": {
    "expected_return_pct": 6.0,
    "inflation_pct": 3.0,
    "retirement_age": 65,
    "current_age": null,
    "monthly_contribution": 500.0,
    "emergency_fund_months": 6,
    "notes": "every entry here is user-editable in interactive formats"
  },

  "analysis": {
    "net_worth": {"assets": 0.0, "liabilities": 0.0, "net": 0.0,
                  "trend": [{"date": "2026-06-01", "net": 0.0}]},
    "cash_flow": {"monthly_income_avg": 0.0, "monthly_expenses_avg": 0.0,
                  "surplus": 0.0, "savings_rate_pct": 0.0,
                  "by_category": {"groceries": 0.0},
                  "income_streams": [{"name": "salary", "monthly_avg": 0.0,
                                      "volatility": "steady|irregular"}]},
    "emergency_fund": {"runway_months": 0.0, "target_months": 6,
                       "target_amount": 0.0, "gap": 0.0},
    "debt": {"total": 0.0,
             "items": [{"account_id": "a5", "balance": 0.0, "apr": 0.24,
                        "min_payment": 0.0}],
             "avalanche": {"months_to_free": 0, "total_interest": 0.0,
                           "order": ["a5"]},
             "snowball":  {"months_to_free": 0, "total_interest": 0.0,
                           "order": ["a5"]}},
    "retirement": {"scenarios": {
        "best":  {"return_pct": 8.0, "value_at_retirement": 0.0},
        "base":  {"return_pct": 6.0, "value_at_retirement": 0.0},
        "worst": {"return_pct": 3.0, "value_at_retirement": 0.0}},
        "projection_series": [{"age": 40, "best": 0.0, "base": 0.0, "worst": 0.0}]},
    "allocation": {"current": {"us_equity": 0.0, "intl_equity": 0.0, "bonds": 0.0,
                               "cash": 0.0, "other": 0.0},
                   "target": {}, "flags": ["concentration: 40% single stock"]},
    "insurance_gaps": ["free-text observations, or 'not assessed — needs X'"],
    "tax_advantaged": ["free-text observations"],
    "action_plan": [
      {"priority": 1, "action": "…", "why_it_fits_you": "…",
       "mechanism": "set-once|recurring|one-time", "status": "open|done"}
    ]
  },

  "source_manifest": [
    {"item": "Checking balance", "source": "user CSV export chase_jun.csv",
     "as_of": "2026-07-01", "confidence": "observed|stated|assumed"}
  ],

  "disclaimer": "This is educational information, not licensed financial, investment, tax, or legal advice. Verify important decisions with a qualified professional."
}
```

## Rules for producers/consumers

- `scripts/parse_statements.py` fills `accounts`, `transactions`, `holdings`.
- `scripts/projections.py` reads the model and fills `analysis.debt`,
  `analysis.emergency_fund`, `analysis.retirement`; it never touches inputs.
- Claude (in-session) fills `profile`, `market_context`, `assumptions` (with the user),
  `analysis.allocation/insurance_gaps/tax_advantaged/action_plan`, `source_manifest`.
- Renderers read the whole model and MUST NOT recompute analysis — if a number looks
  wrong, fix the model, then re-render.
- Unknown/unfillable values are `null` plus a `source_manifest` entry saying what was
  assumed instead. Never invent an observed-looking number.
- `is_transfer` transactions are excluded from income/expense math (they'd double-count).
