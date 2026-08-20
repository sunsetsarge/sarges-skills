#!/usr/bin/env python3
"""tm_gate.py - fail-closed trademark pre-publish gate for POD / e-commerce apparel.

Blocks a design from going live if its brand/wordmark is a famous or still-active
trademark (especially apparel / Nice Class 25). Public-domain *copyright* on the
artwork does NOT clear the *mark* -- see ../references/trademark-vetting.md.

Verdicts (FAIL-CLOSED: nothing auto-passes):
  RED    famous / aggressive-policer / still-active mark            -> BLOCK
  AMBER  not on the denylist -> a human must run the 30-sec check    -> HOLD
  GREEN  only when a human has verified DEAD + no live Class-25       -> PASS
         (pass --confirmed to record that clearance)

Usage:
  python tm_gate.py "Coca-Cola" "Hamme Hats" "Bobbitt's Rheumacide"
  python tm_gate.py --file brands.txt --out report.json
  python tm_gate.py "Old Local Brand" --probe      # best-effort Justia auto-hint
  python tm_gate.py "Old Local Brand" --confirmed   # record human clearance -> GREEN

Exit code: 0 only if EVERY brand is GREEN; otherwise non-zero, so a publish
pipeline stops until each design is individually cleared. This mirrors the
Saspan orchestrator's AT-LINT-1 fail-closed copy lint.

NOTE: general business tool, NOT legal advice. Clear anything valuable with a
trademark attorney. USPTO has no clean free name-search API (the tmsearch.uspto.gov
'api' path is S3 storage), so the reliable step is the prefilled human worklist.
"""
import sys, json, re, argparse, urllib.parse, urllib.request

# --- Famous / aggressively-policed / still-active marks -> instant RED on apparel.
# Not exhaustive; extend as you learn. Matched as whole word-runs, case-insensitive.
DENYLIST = {
    "coca-cola", "coca cola", "coke", "pepsi", "pepsi-cola", "dr pepper", "sprite",
    "fanta", "7up", "7-up", "mountain dew", "gatorade",
    "kodak", "polaroid", "fujifilm", "nikon", "canon", "leica",
    "dupont", "du pont", "monsanto",
    "ford", "chevrolet", "chevy", "buick", "cadillac", "dodge", "chrysler",
    "harley", "harley-davidson", "john deere", "caterpillar",
    "heinz", "campbell", "campbells", "quaker", "kellogg", "kelloggs", "nabisco",
    "hershey", "hersheys", "nestle", "kraft", "oscar mayer", "jell-o", "jello",
    "maxwell house", "folgers", "lipton", "crisco", "pillsbury", "betty crocker",
    "wrigley", "juicy fruit", "doublemint",
    "michelin", "goodyear", "firestone", "bridgestone",
    "levi", "levis", "wrangler", "gillette", "colgate", "crest", "dove",
    "budweiser", "miller", "coors", "pabst", "guinness", "jack daniels", "jim beam",
    "general electric", "westinghouse", "singer",
    "nike", "adidas", "puma", "reebok", "converse", "vans",
    "disney", "mickey mouse", "minnie mouse", "marvel", "star wars", "pixar",
    "bayer", "aspirin", "tylenol", "advil", "listerine", "vaseline", "band-aid",
    "winchester", "remington", "colt", "smith & wesson", "ruger", "browning",
    "ivory", "tide", "aunt jemima",
}
# Commonly assumed dead but revived / still enforced -> force manual, never auto-green.
ZOMBIE_WATCH = {"nokia", "atari", "polaroid", "pan am", "brownie", "hydrox", "tab", "burma-shave"}

JUSTIA = "https://trademarks.justia.com/search?q={}"
USPTO = "https://tmsearch.uspto.gov/search/search-information"  # official (manual)


def _norm(s):
    return " " + re.sub(r"[^a-z0-9& ]+", " ", s.lower()).strip() + " "


def classify(brand):
    n = _norm(brand)
    reasons, verdict = [], "AMBER"
    for d in DENYLIST:
        if _norm(d).strip() and (" " + _norm(d).strip() + " ") in n:
            verdict = "RED"
            reasons.append(f"denylist: matches famous/active mark '{d}'")
            break
    if verdict != "RED":
        for z in ZOMBIE_WATCH:
            if (" " + _norm(z).strip() + " ") in n:
                reasons.append(f"zombie-watch: '{z}' has been revived/enforced -- verify LIVE status")
    # right-of-publicity light heuristic (honorific prefix strongly implies a named person)
    if re.search(r"\b(dr|mr|mrs|miss|prof|capt|col|gen|madam|madame)\b", n):
        reasons.append("honorific/personal name -> also clear right-of-publicity if a recognizable person")
    if verdict == "AMBER" and not reasons:
        reasons.append("not on denylist -> needs a 30-sec human LIVE + Class-25 check")
    return verdict, reasons


def probe_justia(brand, timeout=15):
    """Best-effort, advisory only. Fetch Justia search and hint at LIVE apparel marks.
    Never raises; returns a short note string (or '')."""
    try:
        url = JUSTIA.format(urllib.parse.quote(brand))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 tm_gate/1.0"})
        html = urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore").lower()
    except Exception as e:
        return f"probe unavailable ({type(e).__name__}) -> do the manual check"
    live = html.count(">live<") + html.count("live</")
    apparel = any(k in html for k in ("class 025", "class 25", "clothing", "t-shirts", "shirts", "apparel"))
    core = re.sub(r"[^a-z0-9]+", "", brand.lower())
    named = core and core in re.sub(r"[^a-z0-9]+", "", html)
    if named and live and apparel:
        return "PROBE: possible LIVE apparel-class mark for this name -> treat as RED until verified"
    if named and live:
        return "PROBE: LIVE mark(s) exist for this name (class unclear) -> verify Class 25 by hand"
    if named:
        return "PROBE: name appears on Justia but no obvious LIVE apparel mark -> confirm by hand"
    return "PROBE: no obvious match on Justia (still confirm by hand)"


def main():
    ap = argparse.ArgumentParser(description="Fail-closed trademark pre-publish gate (POD apparel).")
    ap.add_argument("brands", nargs="*", help="brand/wordmark strings to check")
    ap.add_argument("--file", help="text file, one brand per line")
    ap.add_argument("--probe", action="store_true", help="best-effort Justia auto-hint (advisory)")
    ap.add_argument("--confirmed", action="store_true",
                    help="record that a HUMAN verified DEAD + no live Class-25 -> GREEN (non-RED only)")
    ap.add_argument("--out", help="write JSON report to this path")
    a = ap.parse_args()

    brands = list(a.brands)
    if a.file:
        brands += [ln.strip() for ln in open(a.file, encoding="utf-8") if ln.strip() and not ln.startswith("#")]
    if not brands:
        ap.error("give at least one brand (args or --file)")

    rows = []
    for b in brands:
        verdict, reasons = classify(b)
        note = probe_justia(b) if a.probe else ""
        if a.probe and note.startswith("PROBE: possible LIVE apparel") and verdict != "RED":
            verdict = "RED"
            reasons.append(note)
            note = ""
        if a.confirmed and verdict == "AMBER":
            verdict = "GREEN"
            reasons.append("human-confirmed clearance (--confirmed)")
        rows.append({
            "brand": b, "verdict": verdict, "reasons": reasons,
            "probe": note,
            "justia": JUSTIA.format(urllib.parse.quote(b)),
            "uspto": USPTO,
        })

    icon = {"RED": "[X] RED  ", "AMBER": "[!] AMBER", "GREEN": "[OK] GREEN"}
    print(f"\nTrademark pre-publish gate -- {len(rows)} design(s)\n" + "=" * 60)
    for r in rows:
        print(f"{icon[r['verdict']]}  {r['brand']}")
        for rs in r["reasons"]:
            print(f"        - {rs}")
        if r["probe"]:
            print(f"        - {r['probe']}")
        if r["verdict"] != "GREEN":
            print(f"        check: {r['justia']}")
    reds = sum(v["verdict"] == "RED" for v in rows)
    ambers = sum(v["verdict"] == "AMBER" for v in rows)
    greens = sum(v["verdict"] == "GREEN" for v in rows)
    print("=" * 60)
    print(f"RED(block)={reds}  AMBER(hold)={ambers}  GREEN(pass)={greens}")
    if reds or ambers:
        print("GATE: NOT CLEAR -- resolve every RED/AMBER before publishing (fail-closed).")

    if a.out:
        json.dump({"rows": rows, "summary": {"red": reds, "amber": ambers, "green": greens}},
                  open(a.out, "w", encoding="utf-8"), indent=2)
        print(f"report: {a.out}")

    # exit 0 only if everything is GREEN
    sys.exit(0 if reds == 0 and ambers == 0 else (2 if reds else 1))


if __name__ == "__main__":
    main()
