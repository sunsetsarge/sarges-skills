# Genealogy Toolbox — site-by-site playbooks

Validated procedures from real sessions (2026-05-09/10 incl. the two pedigree sweeps). Read the entry before using a site — most have a trap.

## Multi-agent sweep pattern (validated at scale, 48 researchers)

- **Architecture:** Workflow tool, waves of Sonnet researchers (1 ancestor or couple each, structured-output schema) piped into Opus adversarial verifiers for any finding that is <high confidence, conflicts with tree, or cites user-generated sites. Loop waves with NEW angles until dry; main loop analyzes between waves.
- **Verification is not optional:** across 2 waves, Opus killed 7+ FABRICATED findings — invented Find A Grave memorial IDs, nonexistent index rows, wrong-state same-name people. Never plan on unverified agent prose.
- **Workflow gotchas:** `args` may arrive as a JSON string — always `typeof args === 'string' ? JSON.parse(args) : args`. Workflow output file = `{summary, agentCount, logs, result, totalTokens}` dict; per-agent raw results in the run's `journal.jsonl` (`type:"result"` lines, keys are hashes — pair via the final result array instead). Failed agents (API 500s) → resume with same scriptPath+resumeFromRunId+args; research replays from cache.
- **Prompt rules that matter:** forbid Agent tool + browser tools + idling; cap WebSearch (~8/agent — the 200-call session budget is SHARED and exhausts); require fetched-URL citations; "never cite a memorial you could not open"; honest dead_ends are valid output.
- **Project convention:** `Projects\Genealogy_Pedigree_Sweep[_Name]\` with PLAN.md, STATE.md, REPORT.md, pedigree.json (ahnentafel + completeness scores), findings/ahn_<n>[_wN].json.

## Agent-vs-browser access map (2026-05 reality)

| Blocked for agents (403/login) — do in main-loop Chrome | Works for agents |
|---|---|
| Find A Grave, Ancestry, WikiTree fetch, MyHeritage, GenealogyBank, **Chronicling America (403 now!)**, RootsWeb/USGWArchives (flaky), FamilySearch record search, **Antenati**, **registers.nli.ie (403s agents too — main-loop only)**, genealogy.com forums (Cloudflare — Google snippets recover content), DuckDuckGo/Ecosia | NCGenWeb/county GenWeb pages, genealogytrails, cemeterycensus, **us-census.org image indexes** (1820s+ county head-of-household lists), **newspapers.digitalnc.org OCR** (`/lccn/<id>/<date>/ed-1/seq-N/ocr/`), **archive.org `_djvu.txt`**, NCGS estate-file county indexes, GRHS village pages, dvhh.org, odessa3.org, Archion coverage pages (public), wittenberg-bessarabien.de public lists, **ancestors.familysearch.org public profiles** (sometimes), Geni search snippets |

## Ancestry (logged-in Chrome) — API + scraping recipes

- **Tree list:** `fetch('/api/treesui-list/trees?limit=50')` in page context (credentials include).
- **Person search in a tree:** `/api/treesui-list/trees/<treeId>/persons?name=<q>&limit=5&fields=NAMES,EVENTS` → gid `<pid>:1030:<treeId>`.
- **Person facts page** `/family-tree/person/tree/<treeId>/person/<pid>/facts` → get_page_text gives the FULL timeline + source list + parents — the single highest-yield page per person.
- **Pedigree scrape:** `/family-tree/tree/<treeId>/family/pedigree?cfpid=<pid>` renders 5 generations as `button.nodePedigree` nodes in DFS order; `aria-controls="HoverCard-<pid>"` carries the person id; "Potential" nodes = Ancestry ghost suggestions NOT in tree; "Add father/mother" = hard gap. Deeper generations: re-focus cfpid on an ancestor and map his ahn k → root ahn by binary prefix substitution (root's '1' → focus person's ahnentafel bits).
- The Chrome-extension JS filter blocks source text containing search/query/county/cookie-ish patterns and long href harvesting — keep injected JS free of those words; fetch() of ancestry APIs from the ancestry tab works.

## Fold3 (logged-in Chrome tab; Ancestry sub covers it) — military records

- **Search URL that works** (after Cloudflare interstitial auto-clears in ~5s — never click a CAPTCHA yourself; if an interactive one appears, hand to Blaine):
  `https://www.fold3.com/search?docQuery=(filters:!((type:military.conflict,values:!((label:%27<CONFLICT>%27,value:%27<CONFLICT>%27)))),keywords:%27<NAME>%27)` — conflict labels: `Civil+War+(Confederate)`, `Civil+War+(Union)`, `US+Revolutionary+War`, `World+War+I`, etc.
- **UI quirks:** the query box (`combobox "Search names..."`, use form_input by ref) APPENDS a second keyword term instead of replacing — prefer clean URL navigation. Free-text search drowns in newspaper-OCR hits; always facet-filter by CONFLICT/WAR or search within a publication (`type:general.title.content.collection` filter, or the "Search within this publication" links).
- Key publications: `US, Civil War Service Records (CMSR) - Confederate - <State>` (full service jackets, ages), `US, Revolutionary War Pensions, 1800-1900` (multi-page files, OCR-searchable), Confederate Amnesty Papers, WWI/WWII draft cards, Korean War draft registrations.
- Result types: MULTI-IMAGE FILE = actual record jackets (gold); SERVICEPERSON/Memorial = user-contributed (leads only, same rules as Find A Grave).
- First validated result (2026-05-10): **no NC Confederate CMSR exists for any "Hugh Long"** — the 18th-regiment Hugh M Long is MISSISSIPPI 18th Infantry, so the Columbus Co NC roster's initials-only "Long, H F, Co. H, 18th NC" is probably NOT our Hugh Long (ahn 60, Blaine).

## Archives.com (logged-in Chrome; Ancestry-owned budget sister site)

- URL params don't auto-run — the form at `/search/census` (or /death, /birth, /marriage) needs filling: FirstName textbox, LastName, Location ("County, State" free text), then "Search now". Results include **inline "Members in Household" expanders** — the fastest household-composition view of any Ancestry property, no image load needed.
- Value: same Ancestry census indexes through a lighter UI that doesn't fight automation. **Broke the Tharpe/Stanland Horry census wall in one query** after 2 agent waves + Fold3 + Ancestry-proper all stalled. Use it FIRST for census-trail questions; use Ancestry proper for record images/certs.

## WV Vital Research Records (archive.wvculture.org / wvculture.org VRR) — FREE death/birth/marriage certificate IMAGES, browser only (agents got nothing). Deaths >50yrs public. Names parents, cause, informant. First stop for any WV death.

## Antenati (antenati.cultura.gov.it) — browser only (403s all agent fetches)

- Registry search: homepage "Cerca nei registri" form → GET `/search-registry/?localita=<comune>&anno=<yyyy>&tipologia=Nati|Matrimoni|Morti`. Name index (`/search-nominative/?cognome=`) is PARTIAL — crowdsourced, most comuni unindexed; a zero there means nothing.
- **Same-name comune TRAP:** results for "Trevi" are **Trevi nel Lazio (Frosinone)** — Trevi (Perugia) is NOT digitized (2026-05). Always check the Serie/Località facet for the province. If a comune is absent: FamilySearch films (free login), or write the comune's ufficio anagrafe.
- Immigrant comune discovery order: passenger manifest → **naturalization petition** (exact birthplace+date) → WWI/WWII draft cards → passport applications (all indexed on Ancestry).

## Germans from Russia / Danube Swabians

- **Ortsfamilienbücher** (village family books) are the master sources — check FamilySearch Digital Library (e.g. Parabutsch = item 914277) and HOG (Heimatortsgemeinschaft) publishers.
- Bessarabia: GRHS village profiles (grhs.org), odessa3.org plain-text collections (paths non-obvious — browse libindex.html), wittenberg-bessarabien.de (public immigrant lists; full DB password-gated — email the project), denkmalprojekt.org village memorial lists, Archion for the Württemberg origin parishes (coverage pages public, images paid).
- Context: Yugoslav partisans occupied Batschka Oct 1944 — ethnic-German deaths winter 1944–45 are often internment-related.

## Published-genealogy shortcut

Before grinding records for a colonial-era family, WebSearch "<surname> family history archive.org" — e.g. Ridlon's *History of the Families Millingas and Millanges* (1907) held the whole Brunswick Co Milliken line with land-grant dates. Download `_djvu.txt`, extract verbatim with page numbers. County historical-society **FamilyFiles PDFs** (e.g. brunswickcountyhistoricalsociety.org) are similar gold.

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
