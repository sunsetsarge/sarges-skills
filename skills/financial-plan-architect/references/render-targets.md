# Render Targets — build guidance per format

One `plan_model.json` (see `plan-model.md`), many renders. This doc is for the model
running the skill: how to invoke each renderer, when to recommend which target, and the
honest security-tier ladder to quote the user before anything leaves their machine.

## Excel (.xlsx) — `scripts/render_excel.py`

```
python scripts/render_excel.py plan_model.json --out financial_plan.xlsx
```

- Requires `openpyxl` on the interpreter you invoke. If missing:
  `C:\AI-Shared\python.exe -m pip install openpyxl`
- Produces 8 sheets: Dashboard, Assumptions, Net Worth, Cash Flow, Debt, Retirement,
  Transactions, Source Manifest. Dashboard carries 2+ native charts (category bar,
  retirement line) plus the disclaimer; Source Manifest repeats the disclaimer.
- Assumptions sheet cells are yellow-highlighted inputs. One live formula is wired
  (emergency-fund target = months × avg expenses); debt/retirement scenario numbers are
  static and labeled "recompute via refresh" — don't imply they auto-update, they don't.
- Renderer does not recompute `analysis.*` — if a number is wrong, fix `plan_model.json`
  (or re-run `scripts/projections.py`) and re-render, don't hand-edit formulas to patch it.
- Default sensible pairing: Excel + PDF summary, per SKILL.md Step 5.

## React component — `assets/react/PlanDashboard.jsx`

- Hand the file to the user's project (or scaffold a minimal one if they have none):
  `import PlanDashboard from "./PlanDashboard.jsx"` then `<PlanDashboard planModel={model} />`.
- Zero external chart dependency — inline SVG. No CSS framework needed (styles are
  injected inline in the component). React 18+ function component, hooks only.
- Scenario sliders (savings-rate delta, market shock %) recompute the displayed
  projection **in the browser tab only** — no persistence, no network call. Say this
  explicitly when handing it over so the user doesn't expect it to save changes.
- If the user has no existing React app, the fastest path is a Vite scaffold
  (`npm create vite@latest -- --template react`) with this file dropped into `src/`.

## Local HTML — `assets/html/dashboard_template.html`

- Single file, works from `file://` with zero network requests. Injection point is the
  literal marker `/*__PLAN_MODEL_JSON__*/{}`   in the `<script>` block — replace it with
  `json.dumps(plan_model)` (Python) or `JSON.stringify(planModel)` (JS) before handing the
  file to the user. Keep the marker comment text exact if you're scripting the replacement
  so future re-injection (refresh) can find it again.
- Minimal injection recipe (Python):
  ```python
  html = open("dashboard_template.html", encoding="utf-8").read()
  html = html.replace("/*__PLAN_MODEL_JSON__*/{}", json.dumps(plan_model))
  open("financial_plan_dashboard.html", "w", encoding="utf-8").write(html)
  ```
- Charts are hand-rolled: CSS bars for spending-by-category, one inline SVG polyline
  chart for the retirement best/base/worst series. No canvas libs, no CDN scripts —
  the strict offline requirement forbids any external request.
- Always keep the security-posture note in the page body ("Local file — private on your
  machine; not 'secure anywhere'") — do not remove it even for a quick one-off.

## Security-tier ladder (say this out loud before producing/hosting anything)

Quote the relevant row verbatim when the user asks to share, host, or "put this
somewhere I can check from my phone." Never round up a tier's security claim.

| Tier | What it is | Say this |
|---|---|---|
| 1. Local file (xlsx / html / pdf) | Lives only on the user's machine | "Local file — as private as the machine it's on. Nothing is sent anywhere." |
| 2. Client-side password gate on a static page | JS checks a password in the browser before showing content | "**Not secure** — the data still ships to every visitor's browser; the password only hides the UI. Never call this secure, even if the user asks you to." |
| 3. Hosted app + real auth | A hosting platform (Vercel/Netlify/Firebase/etc.) with a real auth provider (OAuth, Firebase Auth, Clerk, etc.); data lives behind the auth boundary, ideally server-side | "This is the right answer for 'securely accessed anywhere.' Recommend this whenever remote/multi-device access is the actual ask." |
| 4. Installable PWA | One codebase installs on Windows/Mac/Android/iOS via `manifest.json` + a service worker; data stays on-device or behind the same auth as tier 3 | "Installable like an app, but the data protection is only as good as tier 1 (on-device) or tier 3 (behind auth) underneath it — say which one applies." |

Never present tier 2 as adequate protection for real financial data, no matter how the
user frames the request ("just for me," "nobody will find the link," etc.) — restate the
tradeoff and let them decide with the facts in hand.

## PWA guidance (installable app target)

- Minimum viable PWA = a `manifest.json` (name, icons, `start_url`, `display: standalone`)
  plus a service worker that caches the app shell for offline use. Sketch:
  ```json
  // manifest.json
  { "name": "My Financial Plan", "short_name": "Plan", "start_url": "/",
    "display": "standalone", "background_color": "#ffffff", "theme_color": "#0F766E",
    "icons": [{ "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" }] }
  ```
  ```js
  // service-worker.js — cache the shell only; do NOT cache API responses containing
  // account data, so a stale cache never leaks a snapshot after logout.
  const SHELL = ["/", "/index.html", "/app.js", "/styles.css"];
  self.addEventListener("install", (e) => {
    e.waitUntil(caches.open("shell-v1").then((c) => c.addAll(SHELL)));
  });
  self.addEventListener("fetch", (e) => {
    e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
  });
  ```
- Financial data itself belongs in one of two places, never in the cached shell:
  (a) on-device only (IndexedDB/localStorage, no sync — acceptable for single-device,
  no-remote-access use), or (b) behind the same real auth boundary as tier 3 above if the
  user wants multi-device sync.
- Only reach for Electron or React Native if the user explicitly needs native APIs a PWA
  can't reach (e.g. deep OS integration) — say that a PWA covers the "install on my phone"
  ask for the vast majority of requests and is far less to maintain.

## Hard rules that apply to every render target

- Never hardcode secrets (API keys, tokens, passwords) in any generated file.
- Never commit `plan_model.json` or any rendered artifact containing real financial data
  to a git repo or a shared/public location. Treat every rendered file as sensitive.
- Mask account numbers to last-4 everywhere (`mask` field) — never surface a full account
  number in any render, even if the source file happened to contain one; re-mask if seen.
- Every render carries the disclaimer (hard rule 3 in SKILL.md) and a one-line security
  posture statement appropriate to its tier above — this is not optional trim.
