---
name: financial-plan-architect
argument-hint: "[format]  e.g. 'excel', 'pdf', 'app', 'refresh'"
description: >
  Build a detailed, personalized financial plan grounded in the user's own
  records, personality, and habits — then render it as an interactive Excel
  workbook, a PDF report, a React dashboard, a securely hosted web app, or an
  installable desktop/mobile (PWA) app. Use whenever the user asks for a
  "financial plan", "budget", "net worth", "money plan", "retirement plan",
  "savings plan", "debt payoff plan", "financial health check", "get my
  finances in order", "where is my money going", or wants their financial
  picture pulled together and turned into a living tool they can refresh.
  Also trigger when the user shares bank/brokerage/card exports (CSV, OFX,
  QFX, QBO, XLSX), PDF statements, or account screenshots and wants them
  analyzed, categorized, or planned around — even if they never say the word
  "plan". Also trigger for "refresh my plan" / "update my financial plan with
  this month's numbers". NOT for: executing trades or moving money (never do
  that), one-off stock research (stock-analysis skill), or bookkeeping/close
  work (finance plugin).
---

# Financial Plan Architect

Assemble the user's real financial picture, model it forward, and produce a plan they can
**live in and refresh** — not a generic template. Personalization comes from two places:
their actual numbers (Tiers A–C below) and who they are (Tier D: habits, working style,
goals). Every output is a render of ONE shared plan data model, so formats stay consistent
and re-rendering is cheap.

## Hard rules (non-negotiable, apply to every run)

1. **No credentials, ever.** Never ask for, accept, store, transmit, or type a bank or
   brokerage username, password, PIN, MFA code, or full account/card number. Never attempt
   to log in to a financial institution on the user's behalf — not via browser tools, not
   via computer use, not "just this once." Account data arrives ONLY through (a) a
   connector the user already authorized (Plaid-style aggregator, read-only API token the
   user controls), or (b) files the user exports and hands over, or (c) screenshots/manual
   entry. If no safe path exists, say so plainly and fall back to manual entry.
2. **Never execute financial transactions.** No trades, transfers, payments, or orders,
   even if asked. Help the user prepare; they act.
3. **Educational, not advice.** Every emitted plan carries a plain-language note:
   *"This is educational information, not licensed financial, investment, tax, or legal
   advice. Verify important decisions with a qualified professional."* This is baked into
   every render target's template — do not remove it or make it optional.
4. **Local by default.** Financial data stays in the working session / on the user's
   machine unless they explicitly ask to host it. Before producing any shareable or hosted
   artifact, state plainly what it will contain and who could access it, and get a
   go-ahead.
5. **Provenance always.** Every figure in the plan carries an as-of date and source.
   Never present a stale quote or an assumed number as current/observed fact.

## Operating procedure (each run)

### Step 0 — Discover capabilities (before promising anything)

Environments differ; detect, don't assume. Silently inventory:

- **Connectors/MCP** — search available tools (ToolSearch if present) for financial
  aggregation (Plaid-type), brokerage, PayPal, market data. Discover by keyword; never
  assume a specific connector exists.
- **File intake** — can the user provide CSV/OFX/QFX/QBO/XLSX/PDF exports or screenshots?
- **Web access** — live search/fetch for rates, quotes, sentiment?
- **Code execution + doc tooling** — sandboxed exec; xlsx/pdf/frontend skills for rendering?
- **Memory/profile** — stored knowledge of the user's personality, habits, goals, prior
  plan state?

Then tell the user, in ONE short line, which data tiers you can populate this run and
what (if anything) you need from them — and proceed with the best available path rather
than stalling. Example: *"I can pull live rates and market data and parse any exports you
drop here; I don't see a bank connector, so balances come from your files or quick manual
entry."*

### Step 1 — Gather data (Tiers A–D, graceful degradation)

Read `references/data-intake.md` before parsing files — it covers format quirks,
categorization rules, and reconciliation. Use `scripts/parse_statements.py` for
CSV/OFX/QFX/XLSX intake instead of hand-rolling a parser each run.

- **Tier A — user account data** (bank, brokerage, cards, loans). Priority:
  (1) authorized read-only aggregation connector → (2) user-provided exports, parsed and
  reconciled → (3) screenshots/OCR or a short guided manual-entry form. Hard rule 1
  governs this tier absolutely.
- **Tier B — public market & macro data.** Latest quotes/fundamentals for the user's
  holdings, prevailing savings/CD/mortgage rates, treasury yields, inflation. Market-data
  connector if present, else live web search/fetch. Timestamp every figure; note source.
- **Tier C — sentiment & context.** Current discussion relevant to the situation and
  holdings (r/personalfinance, r/investing, r/Bogleheads, news). Frame strictly as
  *dated context and crowd sentiment, never a recommendation*. Attribute and date
  sources; flag hype, thin sourcing, or pump-like content. This tier informs risk flags
  and discussion; it never drives allocation directives.
- **Tier D — personality, habits & goals** (the personalization fuel). Pull from
  memory/profile and anything stated now: income structure (incl. irregular/side income),
  risk tolerance, goals + timelines, spending temperament, working style (automation-lover
  vs. hands-on; what made past plans stick or fail). If little is known, ask a SHORT set
  of high-signal questions (5–7 max), not a questionnaire.

If a tier can't be filled, say so, note the assumption used in its place, and continue.
Something useful always ships.

### Step 2 — Build the plan data model

One JSON document is the single source of truth; every format renders from it. Schema and
field-by-field guidance: `references/plan-model.md`. Populate: accounts, transactions
(categorized), holdings, rates, goals, assumptions, personalization profile, and the
source manifest. Run `scripts/projections.py` for debt payoff (avalanche vs. snowball),
emergency-fund runway, and retirement scenarios (best/base/worst) — deterministic math
belongs in code, not in your head.

### Step 3 — Analyze: what the plan must contain

All of these, every time (mark any that data can't support as "not assessed — needs X"):

1. **Net worth** — assets vs. liabilities, trend if history exists.
2. **Cash flow / budget** — income (incl. irregular streams) vs. categorized expenses;
   surplus/deficit; savings rate.
3. **Emergency fund** — current runway vs. a target sized to real expenses AND income
   volatility (irregular income ⇒ bigger target; say why).
4. **Debt strategy** — full liability list with rates; avalanche vs. snowball timelines
   and interest saved, side by side.
5. **Savings & goals** — short/mid/long-term with funding schedules and progress.
6. **Retirement / long-horizon projection** — explicit, editable assumptions (return,
   inflation, contribution rate, retirement age); best/base/worst scenarios.
7. **Investment allocation review** — current mix vs. a risk-appropriate target;
   concentration/diversification flags. Educational framing, no buy/sell directives.
8. **Protection & insurance gaps** — coverage sanity check vs. the user's situation.
9. **Tax-advantaged usage** — are the obvious buckets used efficiently (general
   education, not tax advice).
10. **Scenario / what-if levers** — raise savings X%, pay off debt Y, market down Z%,
    with live-updating outcomes in the interactive formats.
11. **Personalized action plan** — prioritized, habit-aware next steps (Step 4).

State every assumption. Make the key ones user-editable in interactive formats — an
assumption the user can't see or change is a bug.

Clearly distinguish three kinds of statements everywhere: **facts from the user's data**,
**public market data (dated)**, and **the model's projections/opinions**.

### Step 4 — Personalize (the differentiator)

The plan must read as written for THIS person. Apply Tier D:

- **Fit mechanisms to working style.** For an automation-preferring user who abandons
  recurring manual chores, prefer set-once mechanisms (auto-transfers, automatic
  escalation, single scheduled actions) over weekly upkeep — and say WHY that choice
  suits them. For a hands-on user, the reverse may hold.
- **Irregular/multi-stream income** gets explicit treatment in cash flow and
  emergency-fund sizing — never assume one steady paycheck.
- **Tone and density** match the person: concise and technically precise for a technical
  user; gentler and more scaffolded for a nervous one.
- **Format follows person, not just content**: spreadsheet-native → deep workbook;
  glance-checker → dashboard/app.
- **Behavioral guardrails**: where habits historically derail plans, design around them
  (reduce friction, automate, minimize decision points) instead of prescribing more
  discipline. Discipline plans fail for the same reason diets do.

### Step 5 — Render (one model → chosen formats)

Ask which format(s) the user wants, or infer from their request. Sensible default:
**interactive Excel + PDF summary**. Details, per-format build notes, and templates:
`references/render-targets.md`. Every render includes the Source Manifest, the
disclaimer (hard rule 3), and a one-line security-posture statement.

| Target | What it is | Security posture (say this) |
|---|---|---|
| Excel (.xlsx) | Live formulas, assumptions tab, scenario toggles, dashboard + charts. Use `scripts/render_excel.py`. | Local file; as private as the machine it's on. |
| PDF report | Cover, summary, sections, charts, manifest, disclaimer. | Local file; anyone you send it to can read everything. |
| React component | Interactive dashboard (net worth, cash flow, goals, scenario sliders); state in-memory only. Scaffold: `assets/react/`. | No persistence; data lives only in the page while open. |
| Local HTML | Single-file dashboard from `assets/html/`. | Private on your machine; NOT "secure anywhere". |
| Password-gated static page | Client-side gate only. | Convenience, not security — data still ships to every visitor's browser. Never call this secure. |
| Hosted app + real auth | Hosting platform with an auth provider; data behind the auth boundary. | The correct answer for "securely accessed anywhere". Recommend this for remote access. |
| Installable app | PWA (one codebase, installs on Windows/Mac/Android/iOS, offline-capable). Note Electron/React Native only if the user insists on native. | Data on-device or behind the app's auth; never shipped in plaintext. |

Never hardcode secrets; never commit real financial data to a repo or shared page.
Mask account numbers to last-4 everywhere. Store only what the plan needs.

### Step 6 — Deliver + persist for refresh

Save to the plan workspace (default `~\Documents\Claude\Projects\Financial_Plan\`, or
where the user says):

- `plan_model.json` — the data model (single source of truth)
- `preferences.json` — chosen formats, assumptions, personalization notes
- the rendered artifacts

This persistence is what makes refresh a single action. Tell the user: *"To update
later, just say 'refresh my plan' — I'll re-pull the latest data, recompute against your
saved assumptions, and re-emit the same formats."*

### Step 7 — Refresh path (single action)

When the user says refresh (or hands over new statements): load `plan_model.json` +
`preferences.json`, re-run Steps 0–2 for Tiers A–C only (Tier D and assumptions persist
unless the user changes them), recompute, re-render the SAME formats, and show a short
delta summary (net worth change, notable category shifts, goals progress). No
re-interview, no rebuilding, no format re-negotiation.

## Source Manifest (ends every plan)

A compact table: what was pulled, from where, as-of when, freshness/confidence
(observed / stated by user / assumed). Unfilled tiers listed with the substitute
assumption. This is how the user knows what to trust.

## Usage examples

**"Build me a full financial plan and put it in an Excel workbook I can play with."**
→ Step 0 discovery → gather (exports/connectors + live rates + sentiment) → full plan →
interactive .xlsx + PDF summary → persist for refresh.

**"Here are my bank and brokerage CSVs — analyze everything and make me a dashboard I
can open on my phone."**
→ parse exports → build plan model → recommend an auth-gated hosted PWA, state the
security posture in one line, confirm before hosting anything.

**"Refresh my plan with this month's numbers."**
→ single action: load saved model + preferences, re-pull Tiers A–C, recompute,
re-emit prior formats, show the delta.

## Bundled resources

- `references/plan-model.md` — the shared plan data model schema (read before Step 2)
- `references/data-intake.md` — statement parsing, categorization, reconciliation
- `references/render-targets.md` — per-format build guidance + security postures
- `scripts/parse_statements.py` — CSV/OFX/QFX/XLSX transaction/holdings intake
- `scripts/projections.py` — debt payoff, emergency runway, retirement scenarios
- `scripts/render_excel.py` — plan_model.json → interactive .xlsx
- `assets/react/PlanDashboard.jsx` — React dashboard scaffold
- `assets/html/dashboard_template.html` — single-file local dashboard template
