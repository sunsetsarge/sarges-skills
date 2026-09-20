---
name: library-ingest
description: Extract clean, page-cited text from a folder of PDF and EPUB files, then turn chosen books into verified knowledge notes and Confluence pages. Use this whenever Blaine wants text pulled out of many PDFs or EPUBs (an ebook library, a backup drive, a downloads folder, a batch of uploads), wants to know which files are scanned, broken, DRM-locked, or duplicated, wants a book ingested with print page citations, asks what his books say about a topic and wants page numbers, or wants library summaries logged to Confluence. Also use it for a single long book when page citations matter, for OCR re-runs, and whenever a large note needs publishing to Confluence with read-back verification. Pairs with ingest-resource, which owns the note format.
---

# Library ingest

Turns a directory of books and papers into a corpus Claude can read chunk by chunk, search with page numbers, and quote accurately, then carries chosen books through to Confluence. It exists because the parenting-library sessions kept hitting the same problems: helper scripts lost to sandbox resets, a publish that saved only a stub page, uploads that arrived corrupted, and citations checked by eye.

## What's in the skill

| File | Use |
| --- | --- |
| `scripts/corpus.py` | `extract`, `status`, `search`, `overlap`. Run `python corpus.py <command> -h` for every flag |
| `scripts/split_note.py` | split a long note into an overview page and a child page before publishing |
| `scripts/md2conf.py` | note markdown to Confluence HTML: property table, summary panel, task list, children macro, version history |
| `references/corpus-format.md` | output layout, manifest fields, statuses, performance, Windows notes, troubleshooting. Read when interpreting results or debugging |
| `references/confluence-publishing.md` | the publish-and-verify protocol with tool parameters. Read before any Confluence write |

The note format belongs to the `ingest-resource` skill; read it before drafting a note.

## Where it runs

Run extraction where the files live. For a folder on Blaine's PC that means Claude Code, Cowork, or Desktop Commander, with this skill at `C:\Claude\sarges-skills\library-ingest\`. Don't upload a library into a chat: uploads have size limits, EPUBs have arrived corrupted that way before, and the chat sandbox loses its disk between sessions.

Default corpus location: `C:\Claude\Corpus\<library-name>`, outside OneDrive so thousands of small files don't churn sync. If Blaine hasn't named the source folder, ask for it once.

Long extractions can outlast a tool call. Through Desktop Commander, start the run with `start_process` and poll `read_process_output`. If Desktop Commander stops responding, hand Blaine the exact command to run in a terminal and continue from `status` afterward. Re-running any extract command is safe.

For a few files uploaded to claude.ai, copy `scripts/` into `/home/claude`, extract from `/mnt/user-data/uploads`, and treat the corpus as temporary: zip and present anything worth keeping.

## Step 1: extract

One-time setup on Windows:

```powershell
python -m pip install pymupdf markdown
# Optional, for scanned PDFs: install Tesseract (UB Mannheim build, e.g. winget install UB-Mannheim.TesseractOCR), then open a new terminal
```

Run it:

```powershell
$S = "C:\Claude\sarges-skills\library-ingest\scripts\corpus.py"
python $S extract "D:\Books" "C:\Claude\Corpus\books"
python $S status "C:\Claude\Corpus\books"
```

How a run behaves, so you can explain it:
- Files are identified by content hash. Unchanged files are skipped, so Ctrl+C and re-running picks up where it stopped. Moved or renamed files keep their extraction, and identical copies merge into one document.
- Each file is extracted in its own process with a timeout (default 30 minutes), so one broken PDF costs only itself.
- `--ocr auto` (the default) OCRs image-only PDF pages when Tesseract is installed, at roughly 10 seconds a page. For a big scanned backlog, extract with `--ocr off` first and then run the OCR pass that `status` prints.
- On an unfamiliar drive, start with `--dry-run` or `--limit 20`. To redo one file with different settings, use `--match <part of its path> --force`.

Report results plainly: documents found, how many are usable, total words and estimated tokens, and each non-ok bucket with its next step. `index.md` lists every document with a "Needs attention" section; `manifest.csv` opens in Excel.

| Status | Meaning | Next step |
| --- | --- | --- |
| ok | text extracted | none |
| partial | some pages are images with no text layer | OCR pass: `--ocr auto --only needs_ocr,partial` |
| needs_ocr | mostly or entirely scanned | OCR pass |
| encrypted | password-protected PDF | the owner removes the password |
| drm | DRM-locked EPUB | use a DRM-free copy; don't attempt to remove DRM |
| corrupt | not what the extension claims (HTML saved as .epub, damaged zip, image bundle named .pdf) | re-download or re-copy the original |
| empty | zero bytes or no content | re-copy |
| timeout, error | extraction failed | `--retry-failed --workers 1 --timeout 3600`, then read `detail` in the manifest |

## Step 2: triage

Read `index.md` and settle with Blaine which books get a full note and which get a catalog entry (Step 5). Budget honestly: a document's `est_tokens` is roughly what reading it costs, so a 75,000-word book runs about 100,000 tokens. Plan one full book per session, two at most. Keep `<corpus>\notes\PROGRESS.md` current after each step so a compacted or restarted session can resume without guessing.

## Step 3: full ingest of one book

Read `docs/<folder>/chunks/part-001.md` onward, every chunk, in order. A full note needs the whole book; sampling produces confident gaps. Chunks break at chapter headings where possible and carry page markers like `⟦p.23⟧`; the page in effect is the nearest marker above the text. The manifest's `cite_style` says what those numbers mean:

- `print-pages`: the publisher's print pages from the EPUB page map. Cite them as page numbers and name the edition, since other editions paginate differently.
- `pdf-page-labels`: the PDF's printed page labels, including roman-numeral front matter.
- `pdf-physical-pages`: the PDF's page index. Say so in the note, because it may differ from the number printed on the page.
- `sections`: no page data. Cite chapter plus section heading.

While reading, keep a citation ledger at `<corpus>\notes\<folder>.cites.tsv` with claim, page, and chunk. It survives compaction and turns verification into a checklist.

Draft the note in ingest-resource format. For a book people will bring practical questions to, the parenting notes set a useful shape: a vocabulary table, chapter-by-chapter key points, a scripts or moves index, a situation lookup, where the book meets the others in the library, an evidence check, and action items.

Before calling the note done:
1. Verify every page citation with `python $S search <corpus> "distinctive phrase" --doc "<title words>"`, using wording from the book near the claim. Curly and straight quotes match each other. Verify cross-book citations against that book's corpus or its published page, never from memory.
2. Run `python $S overlap <corpus> note.md --doc "<title words>"`. Chapter titles, book titles, and name lists can stay; reword any other shared run so the note paraphrases.
3. Apply Blaine's style rules: no em or en dashes, and none of "not just x, but y", "smoking gun", "heavy lifting", or "you're absolutely right".
4. If the text leans on a table or figure the note uses, look at it. `meta.json` lists figures with their pages; pull the image from the EPUB or rasterize the PDF page.

## Step 4: publish to Confluence

Read `references/confluence-publishing.md` first. In short:

1. Convert with `md2conf.py`. If the HTML is over about 70 KB, run `split_note.py` and publish an overview page with a child page.
2. Create the page (or `getConfluencePage` then `updateConfluencePage` for an existing one), then verify. A create response echoes the stored body, which must end with the Version History table; after an update, read the page back.
3. Record the page ID, version, and how it was verified in `<corpus>\notes\confluence-ledger.jsonl`, add the page to `links.json`, and convert a child page only after its parent exists so the backlink resolves.
4. Update the collection's hub page (Parenting Library is page 121438209), then set `status: published` and the page URLs in the local note.

Don't tell Blaine a page is published until the read-back shows the whole body.

## Step 5: catalog mode for many books

When the goal is a map of the library rather than deep notes, read each book's front matter, table of contents, introduction, and conclusion chunks, and write one short paragraph per book: what it argues, who it's for, and which chapters matter. Label these as catalog summaries drawn from those parts, not full reads. Publish them as a table on one Confluence page per collection, adding about 25 rows per update and verifying after each.

## Answering questions from the library

Search everything first: `python $S search <corpus> "time-out" --json --max 100`. Try several phrasings (singular and plural, synonyms, the author's own vocabulary), then read the surrounding paragraphs in the chunk to confirm each hit says what it seems to. Answer per book with page numbers (or chapter and section), note where books disagree, and keep quotes under 15 words. The corpus is for finding and checking passages, not for reproducing the books.

## Lessons behind the design

- Uploaded EPUBs arrived as HTML error pages and damaged zips. The extractor now names the real content instead of failing vaguely.
- Files exported from a Claude project's knowledge store can be zip bundles of page images carrying a .pdf name. They show up as `corrupt`; extract from the originals.
- Helper scripts that lived only in the chat sandbox vanished on reset. Everything durable belongs in the skill folder or the corpus folder.
- A publish call cut off mid-session left a page holding only its header and summary. Verification after every write is what caught it.
- Typographic apostrophes defeated a plain text search during citation checks. `search` folds them.
- Reader letters printed as sidebars sit a little away from their page markers, so flag those ranges as approximate.
- In testing, the EPUB print page map matched the hand-verified ScreamFree citations on every check, so page-list pages can be trusted once spot-checked.

## Boundaries

Extracted full text stays on Blaine's machine for his own reading and analysis of books he owns. Notes and Confluence pages carry paraphrase, with short quotes only where exact wording matters. Don't paste chunks into Confluence, don't share corpus text outside his systems, and don't try to get around DRM or passwords.
