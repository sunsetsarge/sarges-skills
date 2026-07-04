# Data Intake Guide

How to get real numbers into `plan_model.json` without ever touching credentials.

## No-credentials hard rule (restated)

Never ask for, accept, type, or store a bank/brokerage username, password, PIN, MFA
code, or full account/card number. Never log into a financial institution on the
user's behalf. Account data only arrives via: (a) an authorized read-only connector,
(b) a file the user exports and hands over, or (c) manual entry / screenshots the
user provides. If none of these are available, say so and fall back to manual entry.
This applies for the whole session, not just at intake.

## Using `scripts/parse_statements.py`

```
python scripts/parse_statements.py chase_checking.csv fidelity.qfx holdings.xlsx --out plan_inputs.json
```

- Accepts any mix of CSV, OFX/QFX/QBO, and XLSX files in one call.
- Detects format by extension first, then by content sniff (ZIP signature for XLSX,
  `<OFX>`/`<STMTTRN>` tags for OFX) if the extension is missing or wrong.
- Emits `{"accounts": [...], "transactions": [...], "holdings": [...], "warnings": [...]}`
  shaped to match `references/plan-model.md`. Merge this into `plan_model.json` under
  the same keys (append to existing arrays rather than overwrite, unless refreshing).
- Prints only counts and warnings to stdout — never full account numbers or a bulk
  transaction dump. Do not pipe raw statement contents into chat; work from the file.

## Format quirks handled

- **CSV**: delimiter sniffed (comma/semicolon/tab/pipe). Header columns matched by
  alias table (`date`/`transaction date`/`posted date`, `description`/`memo`/`payee`,
  `amount` OR split `debit`/`credit` columns). Amounts parse `$1,234.56`, `(45.00)` as
  negative, trailing `-`/`CR`/`DR` markers. Rows that don't parse (bad date or amount)
  are silently skipped, not fabricated.
- **OFX/QFX/QBO**: treated as SGML-ish tag soup, not XML — `<STMTTRN>` blocks are
  split with regex and each `<DTPOSTED>`/`<TRNAMT>`/`<NAME>`/`<MEMO>` tag is read
  independently. This tolerates unclosed tags that would fail a strict XML parser.
  Account balance comes from `<BALAMT>`/`<DTASOF>` if present.
  QBO is dispatched the same as OFX (same underlying tag format).
- **XLSX**: read via raw `zipfile` + `xl/sharedStrings.xml` + first `xl/worksheets/sheetN.xml`
  — no openpyxl dependency. Only the first sheet is read; multi-sheet workbooks (e.g. a
  separate holdings tab) need a separate `--out` run per sheet if the layout differs.
- Every account identifier is masked to last-4 before it's written anywhere. If a
  CSV/XLSX has no account-number column at all (common), `mask` is left `null` —
  do not invent one.

## Reconciling parsed vs. statement balances

1. After parsing, compare each account's `balance`/`as_of` (pulled from a running-balance
   column or OFX `<BALAMT>`) against the ending balance printed on the actual statement
   (ask the user to read it off, or from a screenshot).
2. Small mismatches (a few dollars, pending transactions) are normal — note the
   difference in `source_manifest` as "observed, minor pending-transaction variance."
3. Large or unexplained mismatches: don't silently trust the parse. Ask the user to
   confirm the statement's stated ending balance and use that as `accounts[].balance`
   with `source: "manual"`, keeping the parsed transactions for cash-flow analysis.
4. If a file covers a partial month, say so — `cash_flow` monthly averages will be
   understated/overstated for that month; note it rather than silently averaging.

## When to fall back to manual entry

- No export available at all (institution doesn't support downloads, or the user
  doesn't want to generate one right now).
- A parse produces zero usable transactions/accounts (format not recognized, or
  header row missing) — report the warning from `parse_statements.py` verbatim to the
  user rather than guessing at columns.
- Investment/holdings data that only exists in a PDF statement or screenshot — OCR or
  ask the user to read off symbol/quantity/cost-basis; mark `source: "manual"` or
  `"screenshot"`.
- Sensitive/edge-case files (encrypted PDFs, image-only scans) — don't attempt exotic
  parsing; ask for a plain export instead.

## Categorization override etiquette

- The regex categorizer in `parse_statements.py` (`CATEGORY_RULES`) is a starting
  point, not a verdict. It will mis-categorize ambiguous merchant names (e.g. "SQ
  *ROASTERY", generic "PAYMENT", store names not on the keyword list).
- Do not interrogate the user about every transaction. After parsing, rank categories
  by dollar volume and **only ask about the top 5 ambiguous/uncategorized ones**
  (typically whatever landed in `uncategorized`, plus any category the user flags as
  wrong on sight).
- If the user corrects a category, apply it to that transaction and to future
  transactions sharing the same normalized description — and consider adding a new
  keyword rule to `CATEGORY_RULES` if the pattern is likely to recur (that's what makes
  the table "easy to extend" in practice).
- Never silently recategorize a transaction the user already confirmed on a prior
  refresh — the categorizer only fills gaps, it doesn't overwrite confirmed history.
- `is_transfer` is inferred from keywords (transfer/Zelle/Venmo/CashApp/wire/etc.) and
  used to exclude internal money-movement from income/expense math. If a transfer
  slips through uncaught (e.g. "TO SAVINGS 1234" phrased unusually), fix it in the
  model and re-run `projections.py` — don't hand-adjust the analysis output directly.

## No-credentials hard rule (again, because it matters)

Restated once more so it isn't missed on a skim: this script and this whole intake
step never see, request, or need a login. If a user offers to share a password "to
save time," decline and ask for an export or a screenshot instead.
