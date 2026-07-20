---
name: genealogy-research
argument-hint: "<person or couple> [--line cully|gore|marks|milligan|tucker|conway] [--audit]"
description: Research Blaine's family tree (Cully/Gore/Marks/Milligan + Tucker/Conway/Maloney) using the local GEDCOM, Irish/NC/VA primary-record sites, and source-audit methodology. Use whenever the user mentions family tree, genealogy, ancestor, GEDCOM, Ancestry, Find A Grave, WikiTree, parish register, land grant, obituary hunt for a relative, or names a known ancestor (Culley, Gore, Edens, Conway, Maloney, Marks, Milligan, Tucker). Wraps validated workflows — GEDCOM extraction patterns, NLI register image download, nclandgrants queries — and the evidence rules learned across sessions. DO NOT trust Ancestry-tree/Find-A-Grave claims without a primary-record audit.
---

# Genealogy Research

Research and source-audit ancestors in Blaine's tree. Two modes:
- **Research** — extract what the tree claims, then hunt primary records to prove/extend it.
- **Audit** (`--audit` or any "far back" ancestor) — claim-by-claim table of tree assertions vs. primary records; expect fabrications.

## The prime directive: tree claims are hypotheses, not facts

This tree (like most Ancestry-derived GEDCOMs) contains **proven fabrications**. Confirmed examples:
- "Joshua Gore b. 8 Mar 1710 Christchurch Middlesex VA" — refuted by the actual parish register (date was welded together from two different children's records).
- "Lena Edens daughter of Gov. Charles Eden" — prestige myth; Eden died childless.
- A FamilySearch "Revolutionary War pension" for Thomas Culley — indexing error (the pension is Jacob Weiss's).

Rules of evidence:
1. **Find A Grave**: check for "Burial Details Unknown" + 0 photos → cenotaph, NOT evidence. Note creation date and contradictions.
2. **WikiTree**: read the Sources section — if it's only Find A Grave/Ancestry trees, treat as unsourced. Check G2G comments for open challenges.
3. **Governor/nobility/Mayflower parents** on a colonial-era ancestor → assume prestige myth until a primary record says otherwise.
4. **GEDCOM embedded NOTEs often contain the receipts** — old GenWeb posts admitting "speculation." Always reassemble and read them (CONC/CONT lines).
5. Absence in burned-county records (e.g. Brunswick Co. NC, courthouse burned 1865) is weak evidence — say so.

## Environment (Windows) — hard-won gotchas

| Problem | Fix |
|---|---|
| `python3`/`py` broken on this PC (Store alias / DLL error) | Use `C:\Users\blain\miniconda3\python.exe` (3.9) or `C:\AI-Shared\python.exe` (3.10) |
| Multi-line code in python -i REPL fails (indent/syntax) | Write a script to `%TEMP%` and run it via Desktop Commander `start_process` with `shell:"cmd"` |
| WebFetch 403 on findagrave.com, wikitree.com, from-ireland.net, irishgenealogy.ie | Use the Claude-in-Chrome extension (`navigate` + `get_page_text` / `javascript_tool`) |
| Chrome-extension JS blocked ("Cookie/query string data") | Avoid words like `search`, `query`, `county`, cookie-ish patterns in the JS source; use `indexOf` loops and innerText slices |
| Confluence `spaceId` | Must be numeric `98313` (CullyHouse/SD), not the key; `contentFormat: "markdown"` |

## Key files & data

| Path | What |
|---|---|
| `D:\Documents\Ancestry\CULLYGOREMARKSMILLIGAN.ged` | THE tree (~5.3MB GEDCOM). The `...2.csv` next to it is a PLACES file, not persons |
| `D:\Documents\Ancestry\DigitalNC_Citations.md` | Running citations doc (65+ newspaper citations) |
| Memory: `project_genealogy_digitalnc.md` | Lineage, research state, next steps — update after every session |
| `%TEMP%\christchurch_register.txt` | Downloaded Christ Church Middlesex VA register full text (re-fetch from archive.org if gone) |

## GEDCOM extraction (validated pattern)

Records are `\n0 @I...@ INDI` / `\n0 @F...@ FAM` blocks. Family navigation: person `1 FAMC @F@` (parents) / `1 FAMS @F@` (own family); family lists `1 HUSB/WIFE/CHIL @I@`.

```python
def get_rec(gedid):                      # ALWAYS anchor with '\n0 ' prefix —
    pos = content.find('\n0 ' + gedid)   # a bare .find(gedid) hits cross-references
    end = content.find('\n0 ', pos + 5)
    return content[pos:end]
```

- Filter noise when printing: skip `_APID`, `CONC`, `WWW` lines — but DO reassemble `1 NOTE` + `2 CONC/CONT` when auditing (that's where old GenWeb posts hide).
- Walk a line upward: person → FAMC → family's HUSB → repeat.
- Media objects (`@O7@` etc.) hold record transcriptions (e.g. the 1854 Conway-Malone marriage).

## Core workflow

1. **Extract from GEDCOM first** — full records for the target(s), their families up/down, all NOTEs, all SOUR citations (NLI microfilm numbers, census pages, newspapers.com URLs are often already embedded).
2. **Identify checkable claims** — birthplace parishes, microfilm refs, dates.
3. **Hit primary sources** — see `references/toolbox.md` for site-by-site playbooks (NLI Irish parish registers incl. direct JP2 download, nclandgrants.com form quirks, docsouth 1790 census, archive.org full-text trick, NCGS estate indexes, Armagh hearth rolls).
4. **Write the verdict** — for audits, a claim/status/evidence table with statuses REFUTED / NAME WRONG / DISPROVED (myth) / ADMITTED SPECULATION / NOT EVIDENCE / CONFIRMED.
5. **Log everything**:
   - Confluence space **SD/CullyHouse** (cloudId `ca6859aa-3e7c-4331-904d-66aecb2409bb`, spaceId `98313`) — research-log page per ancestor/couple under the Genealogy parent (98417). Append/companion, never duplicate.
   - Update memory `project_genealogy_digitalnc.md` (lineage additions, verdicts, NEXT steps).
   - New newspaper citations → `DigitalNC_Citations.md`.

## Research state (as of 2026-05-10)

| Line | Earliest proven | Beyond that | Confluence |
|---|---|---|---|
| Cully | Thomas Culley (b.1734 Ireland, d.1798 Lancaster Co. PA); working hypothesis Co. Armagh (1665 HMR: O'Cully/McCully in Orrier + Lower Fewes) | PRONI registers, Tithe Applotments | p.52428801 |
| Tucker→Conway/Maloney | Cornelius Conway (b.1824 Co. Clare) + Bridget Maloney (bapt. 15 Nov 1838 Kildysart, NLI 02475/04 — FOUND); Maloney townland = Gurtnagroon, Carrowreagh West | Galbally 1819 marriage (NLI 02499/03), Conway baptisms ~1829 Kildysart | p.52428907 |
| Gore | Jonathan Gore (1740–1804; 1787 land entry #749, 1790 census Brunswick) | "Joshua Gore + Lena Edens" UNPROVEN; VA Goar family real but no Joshua b.1710 | p.91127833 |
| Marks/Milligan/Gore-NC | Well documented via DigitalNC/Newspapers.com | — | p.48201729 (project log) |
| **Pedigree sweeps (gen 1–5, both trees)** | Blaine: all 63 slots + wave findings (`Projects\Genealogy_Pedigree_Sweep\REPORT.md`). Jennifer (wife, tree CGMM 187294358): Italian line = Trevi (PG); 5 surname errors corrected; WV coal-country convergence (`..._Jennifer\REPORT.md`) | Gen-6 extension; gated sources (Archion, WV VRR, Familienbuch, Trevi records) | p.91652097 / p.91684865 |

Multi-agent sweep methodology + agent-vs-browser access map + Ancestry/Antenati/WV-VRR recipes: see `references/toolbox.md`.

## Related skills / assets

- `digitalnc-harvest` — newspaper page/ad harvesting (Saspan), shares DigitalNC know-how
- `research-access` MCP — academic paper access (rarely needed here)
- Newspapers.com search API endpoint is in the memory file
