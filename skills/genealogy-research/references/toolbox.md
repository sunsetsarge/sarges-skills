# Genealogy Toolbox — site-by-site playbooks

Validated procedures from real sessions (2026-05-09/10). Read the entry before using a site — most have a trap.

## Irish records

### NLI Catholic Parish Registers — registers.nli.ie (FREE, the crown jewel)
- Parish lookup: `https://registers.nli.ie/parishes?locale=en&q=<parish>` redirects straight to the parish page. County browse is BROKEN (ignores the county filter — don't use it).
- Parish page lists microfilms with date ranges + a `registers/vtls...` link per film.
- Viewer is an old BookReader. **Direct image download** (skip the viewer):
  1. On the register page, run JS: `window.br.getPageURI(i, 1, 0)` → returns `https://iserver.nli.ie/fcgi-bin/iipsrv.fcgi?FIF=000640000/<vtlsid>/<vtlsid>_NNN.jp2` (NNN = image index + 1, zero-padded 3).
  2. Append `&WID=1800&CVT=JPEG` and fetch with Python urllib (no auth needed). ~260KB/page at WID=1800, readable handwriting.
  3. Batch-download ranges to `%TEMP%` and Read them as images.
- Register structure quirk (Kildysart at least): film may open with a modern typescript INDEX (surname → register page number), then the register proper. Map register-page → image by sampling: find a dated page, compute offset. Kildysart 02475/04: register p.7 (Jul 1829) ≈ image 84; ~2 register pages per image spread.
- Known films: **02475/04** Kildysart Co. Clare baptisms Jul 1829–Nov 1866 (vtls000634722); **02475/05** 1866–81; **02499/03** Galbally & Aherlow Co. Tipperary marriages 1809–82 + baptisms 1810–28; **02485/08** Kilmihil 1849–69.
- NLI catalogue search for a microfilm number: `https://catalogue.nli.ie/Search/Results?lookfor=<number>&type=AllFields&filter[]=hierarchy_top_id:%22vtls000621546%22`

### irishgenealogy.ie
- Church-records coverage is ONLY Dublin, Kerry, Cork & Ross (RC) + some CoI — **NO County Clare RC records**. Zero results ≠ person absent.
- Form is client-side JS: set values then `document.querySelector('input[type=submit]').click()`. Results render in-page; read `document.body.innerText`.

### failteromhat.com (Armagh Hearth Money Rolls 1665, Flax Growers 1796, etc.)
- **The POST search form has a database indexing bug**: returns "no matches" for Cul- names that ARE in the data. Never trust its negatives.
- Go direct to static barony pages: `failteromhat.com/armaghhearth/<barony>.php` (ardmagh, fewes, lowerfewes, onealand, orrier, torhany) and scan text with JS indexOf loops.
- "Cullowe/Cullow" in these rolls is a GIVEN name (Cú Uladh), not a surname.

### logainm.ie — placename API
- Free REST: `https://www.logainm.ie/api/v1.0/` — resolve townland/parish/barony hierarchy and Irish etymologies. Used to place Cullyhanna (Coilleach Eanach) and Gurtnagroon.

### Griffith's Valuation / Tithe Applotments
- Griffith's free at askaboutireland.ie; Tithe Applotments 1823–37 = FamilySearch collection **1804886**. Both still on the open list for Culley (Armagh) and Maloney/Conway (Clare).

## US colonial / NC records

### nclandgrants.com (NC land grants, free, has images)
- Query form at `/q/`. Fill `input[name="name"]`, county via `select[name="cyid"]` **selectedIndex** (Brunswick=16, New Hanover=75 as of 2026-05), then click `input[name="search"]`.
- Results = name/county/entered/issued/acres/location/file#. `PtBk` = patent book image available.
- Lesson: colonial-era people in Brunswick pre-1764 → land was under New Hanover or Bladen; state grants resume 1778+. No grant ≠ no land (deeds are separate, at county level).

### Colonial & State Records of NC — docsouth.unc.edu/csr
- Full transcriptions incl. **1790 census by county** (Brunswick = document csr26-0006). WebFetch works here.

### NCGS county estate-file indexes — ncgenealogy.org
- e.g. "North Carolina Estate Files, Brunswick County Index" (1783–1925, links to FamilySearch images). Brunswick court records burned 1865 — absence is weak.

### Christ Church Parish, Middlesex Co. VA register (1653–1812, published)
- archive.org id `parishregisterof00chri`. Download full text: `https://archive.org/download/<id>/<id>_djvu.txt` (~1MB), grep locally. OCR is dirty (Goar/Goare/Gore; `17 14` = 1714; `y''`/`y*` = ye) — search surname stems case-insensitively.
- This register REFUTED the tree's "Joshua Gore b. 8 Mar 1710" — full Goar reconstruction is on Confluence p.91127833.

### archive.org generic pattern
- Find the item: `https://archive.org/advancedsearch.php?q=<terms>&fl[]=identifier&fl[]=title&rows=10&output=json` (WebFetch-able).
- Any text-bearing item → `_djvu.txt` download + local grep beats the site's search UI.

## Compiled-source evidence rules (quick reference)

| Source | Trust test |
|---|---|
| Find A Grave | Real stone photo + burial location = usable. "Burial Details Unknown" + 0 photos = cenotaph, cite as nothing |
| WikiTree | Only as good as its Sources section; check G2G/comments for challenges & duplicates |
| Ancestry Member Trees / "Smart Match" SOURs in GEDCOM | Never evidence, only leads |
| GEDCOM NOTE blocks | Reassemble CONC/CONT; often contain candid old GenWeb posts ("speculation is...") |
| FamilySearch index entries | Verify against the film image — indexing errors happen (Thomas Culley "pension" = Jacob Weiss's file W.11769) |

## Newspapers

- **Newspapers.com API**: `https://www.newspapers.com/api/search/query?keyword=TERM&entity-types=obituary%2Cpage&product=1&sort=score-desc&start=*&count=20&include-publication-metadata=true`
- **DigitalNC**: Open ONI `page=` / `yearRange=` params; ~120-request throttle; see `digitalnc-harvest` skill. Best NC papers for the family: State Port Pilot, Brunswick Beacon, Wilmington Morning Star.
- Nebraska (Cully/Tucker/Conway): Beatrice Daily Sun, Fairbury Journal-News, Diller Record, Omaha Daily Bee.

## Logging conventions

1. Confluence CullyHouse: one research-log page per ancestor/couple, parent 98417. Existing: Thomas Culley 52428801 · Irish Resources/APIs 52428844 · Conway/Maloney 52428907 · Gore/Edens audit 91127833 · Project log 48201729 (update its table).
2. Memory `project_genealogy_digitalnc.md`: add lineage facts, verdicts, NEXT steps; bump `description` date.
3. Reads of Confluence go through `C:\Claude\KB-mirror\SD\CullyHouse\` (nightly mirror), writes through the MCP.
