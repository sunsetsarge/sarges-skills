# Trademark Vetting — the fail-closed gate (Phase 2)

> **Not legal advice.** General business information. Clear anything valuable with a trademark
> attorney. Deep legal detail (US + intl, Dastar, dilution, right-of-publicity, platform takedown
> mechanics) lives in the KB note **`public-domain-brands-trademark-pod-safety.md`**.

## The core gate (why this phase exists)

**Copyright and trademark are two separate locks; the public domain only opens copyright.**
A vintage ad's *artwork* can be fully copyright-public-domain while the *brand name/logo* on it is
still a **live, enforceable trademark**. Putting that mark on a product you sell — **apparel is
the exact category brands police (Nice Class 25)** — is "trademark use on goods," which is what
gets a listing pulled or a shop suspended. **PD copyright does NOT clear the mark.**

For ~1890s–1920s material the *copyright* side is essentially solved (US works published ≤1930
are public domain as of 2026). **All the risk is on the trademark side, and in practice it's
platform complaint-and-takedown, not lawsuits** — one complaint can kill a listing; a pattern
suspends the shop.

## The gate spec (what `scripts/tm_gate.py` enforces)

Fail-closed, mirroring the Saspan orchestrator's AT-LINT-1 copy lint: **nothing auto-passes.**

- **RED (block):** brand matches the **famous / aggressive-policer / still-active denylist**
  (Coca-Cola, Kodak, Du Pont, Ford, Heinz, Levi's, Disney/Mickey, Nike, Winchester, Remington, …).
  Famous marks also carry **dilution** liability — no consumer confusion even required, and a
  disclaimer won't save you. Hard no on merch.
- **AMBER (hold):** anything not on the denylist. Requires a **30-second human check** before it
  can pass. This is the default — the tool prints a prefilled **Justia** search link
  (`trademarks.justia.com/search?q=…`) + the **USPTO** search page.
- **GREEN (pass):** only when a human has verified **DEAD + no live Class-25 registration** and
  recorded it (`--confirmed`). Exit code is 0 only if every design is GREEN, so a publish
  pipeline halts until each is cleared.
- **Optional `--probe`:** best-effort Justia hint (advisory). Degrades to "do the manual check"
  if the site blocks automated requests — never a hard dependency. (USPTO has **no** clean free
  name-search API; the `tmsearch.uspto.gov/api-*` path is S3 storage.)

Run it:
```
python scripts/tm_gate.py "Brand A" "Brand B" --out report.json
python scripts/tm_gate.py --file brands.txt          # one brand per line
python scripts/tm_gate.py "Old Local Brand" --confirmed   # after a human check -> GREEN
```

## The per-design human check (what AMBER asks for)

1. **Copyright date** — US published ≤1930? → artwork is PD (2026). Keep the source citation.
2. **USPTO / Justia** — search the wordmark for **LIVE** registrations, especially **Class 25
   (clothing)** and adjacent. TESS was retired in 2023 → use `tmsearch.uspto.gov` or Justia.
3. **Selling into EU/UK?** — also check **EUIPO** and the **UK IPO** (marks are territorial;
   dead in the US can be live in the EU/UK).
4. **Fame / revival check** — still operating? recently relaunched ("heritage" brand)? famous
   (→ dilution)? A USPTO **"DEAD" status is NOT safe** on its own — residual goodwill, common-law
   rights, and zombie/revived marks bite (see *Macy's v. Strategic Marks*).
5. **People in the ad** — any **named/recognizable person**? → clear right-of-publicity separately
   (unnamed 1900s models ≈ negligible).
6. **Prefer the safer construction** — sell as an **art/history reproduction**, keep the full ad
   composition rather than isolating the logo, don't imply endorsement. A disclaimer helps
   *confusion* (not *dilution*).

## The safe lane (default heuristic)

**Obscure + long-defunct + local + unregistered + not-famous = green-ish** (a 1905 local hardware
store, a shuttered regional hatter, a dead patent medicine with no successor). **National, famous,
or still-selling = red**, regardless of how clever the copyright/ornamental-use argument is —
because **platform takedown fires before any legal merits are ever reached.**

The Steamboat Willie lesson: the 1928 Mickey's *copyright* expired in 2024, but Disney holds
Mickey as a **live trademark** and will still sue over merch. "Copyright expired" ≠ "safe to sell."
