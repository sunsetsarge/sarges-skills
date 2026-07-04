# financial-plan-architect

Builds a detailed, personalized financial plan from your own records and habits, then
renders it as whatever format you actually use: an interactive Excel workbook, a PDF
report, a React dashboard, a local HTML dashboard, or a securely hosted / installable
(PWA) web app. One shared data model (`plan_model.json`) backs every format, so refreshing
the plan later re-renders everything from new numbers instead of starting over.

See `SKILL.md` for the full operating procedure; this file is the quick-start.

## Install

Follow the repo's junction convention — author skills in `sarges-skills`, symlink them
into the live skills folder:

```powershell
# from C:\Claude\sarges-skills (repo root)
New-Item -ItemType Junction -Path "$HOME\.claude\skills\financial-plan-architect" `
  -Target "C:\Claude\sarges-skills\skills\financial-plan-architect"
```

If the junction already exists (repo already checked out and linked), no action needed —
edits to the repo copy are live immediately.

## Invocation phrases

Say any of these and the skill triggers:

- "Build me a financial plan" / "get my finances in order" / "money plan"
- "net worth", "budget", "savings plan", "retirement plan", "debt payoff plan"
- "financial health check", "where is my money going"
- Hand over a bank/brokerage/card export (CSV, OFX, QFX, QBO, XLSX) or PDF statements /
  account screenshots and ask for analysis — you don't have to say the word "plan"
- "refresh my plan" / "update my financial plan with this month's numbers"

## What it does NOT do

- Never asks for or handles bank/brokerage credentials, PINs, MFA codes, or full account
  numbers — account data comes only from an authorized connector, your own exports, or
  manual entry/screenshots.
- Never executes a trade, transfer, or payment.
- Never gives licensed financial, investment, tax, or legal advice — every plan carries an
  educational-only disclaimer, prominently, on every render.

## Optional connectors it can discover

The skill inventories what's actually available in your environment each run rather than
assuming — it will tell you in one line what it found. Possible connectors, if present:

- **Bank/brokerage aggregation** (Plaid-style, read-only) for Tier A account data
- **Market data** (quotes, fundamentals, rates, treasury yields) for Tier B context
- **Web search/fetch** for live rates and dated sentiment (Tier C, framed as context only,
  never a directive)

If none are connected, it falls back to your file exports or a short guided manual-entry
form — it always ships something useful rather than stalling on missing connectors.

## Output formats and security posture

| Format | What it is | Security posture |
|---|---|---|
| Excel (.xlsx) | Live formulas, editable assumptions tab, dashboard + native charts | Local file — as private as the machine it's on |
| PDF report | Cover, summary, sections, manifest, disclaimer | Local file — anyone you send it to can read everything |
| React component | Interactive dashboard w/ scenario sliders | No persistence — data lives only in the page while open |
| Local HTML | Single-file offline dashboard | Private on your machine; **not** "secure anywhere" |
| Password-gated static page | Client-side gate only | **Not secure** — data still ships to every visitor's browser; never presented as secure |
| Hosted app + real auth | Hosting platform + real auth provider, data behind the auth boundary | The correct answer for "securely accessed anywhere" |
| Installable app (PWA) | One codebase, installs on Windows/Mac/Android/iOS | Data on-device or behind the app's auth — never shipped in plaintext |

Full per-format build notes: `references/render-targets.md`.

## Hard rules (non-negotiable)

1. **No credentials, ever** — never requested, accepted, stored, or typed on your behalf.
2. **Never executes financial transactions** — it helps you prepare; you act.
3. **Educational, not advice** — every plan says so, in plain language, every time.
4. **Local by default** — data stays on your machine unless you explicitly ask to host it,
   and you're told exactly what a hosted artifact contains and who could access it first.
5. **Provenance always** — every figure carries an as-of date and source; nothing stale is
   presented as current fact.
6. Account numbers are always masked to last-4; nothing hardcodes secrets; nothing commits
   real financial data to a repo or shared page.

## Bundled resources

- `SKILL.md` — full operating procedure (read this first if extending the skill)
- `references/plan-model.md` — the shared plan data model schema
- `references/data-intake.md` — statement parsing, categorization, reconciliation
- `references/render-targets.md` — per-format build guidance + security postures
- `scripts/parse_statements.py` — CSV/OFX/QFX/XLSX transaction/holdings intake
- `scripts/projections.py` — debt payoff, emergency runway, retirement scenarios
- `scripts/render_excel.py` — plan_model.json → interactive .xlsx
- `assets/react/PlanDashboard.jsx` — React dashboard scaffold
- `assets/html/dashboard_template.html` — single-file local dashboard template
