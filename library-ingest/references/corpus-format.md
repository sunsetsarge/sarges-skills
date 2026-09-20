# Corpus format and operations

## Contents
1. Folder layout
2. manifest.jsonl fields
3. paragraphs.jsonl
4. Page markers, citation styles, chunks
5. How a run decides what to extract
6. Measured performance
7. Windows notes
8. Troubleshooting

## 1. Folder layout

```
<corpus>\
  corpus.json          source folder, tool version, last run time
  manifest.jsonl       one record per unique document; the source of truth
  manifest.csv         the same records for Excel (skipped with a message if the file is open)
  index.md             every document in a table, plus a "Needs attention" list
  hashcache.json       path -> size, modified time, sha256, so re-runs skip hashing unchanged files
  docs\<slug>--<sha8>\
    full.md            frontmatter plus the whole text, with headings and page markers
    chunks\part-001.md reading-size pieces, chapter-aligned where possible (default target 12,000 words)
    paragraphs.jsonl   one record per heading or paragraph, for search and citation checks
    meta.json          the manifest record plus the table of contents (with pages) and figures
  notes\               kept by Claude during ingest, not by corpus.py:
                       PROGRESS.md, <folder>.cites.tsv, confluence-ledger.jsonl, links.json, note drafts
```

Folder names come from the first file name found for that content (60 characters at most) plus the first eight characters of the hash, so they stay stable when files move.

## 2. manifest.jsonl fields

| Field | Meaning |
| --- | --- |
| `id` | first 16 hex characters of the SHA-256; stable across moves and renames |
| `sha256`, `bytes` | content hash and size of the primary file |
| `paths`, `primary` | every path holding this exact content; the first in sort order is primary |
| `folder` | the document's folder under `docs\` |
| `type` | `pdf` or `epub`, from the bytes rather than the extension |
| `status`, `detail` | outcome and a plain-language reason (see SKILL.md for the status table) |
| `title`, `authors`, `publisher`, `year`, `language`, `isbn` | metadata from the EPUB package or PDF info; title falls back to the file name |
| `cite_style` | `print-pages`, `pdf-page-labels`, `pdf-physical-pages`, or `sections` |
| `pages` | PDF page count |
| `page_list_entries` | EPUB page-list size, when the book has one |
| `page_markers` | markers actually placed in the text |
| `words`, `est_tokens` | word count and a rough token estimate (words x 1.35) |
| `chunks`, `images` | chunk files written; images referenced by the EPUB |
| `scanned_pages`, `ocr_pages` | PDF pages that looked like images without text, and pages OCR'd |
| `warnings` | anything worth a look, such as a page-list that didn't fully map or a misnamed file |
| `extractor`, `tool_version`, `tool_rev`, `extracted_at`, `seconds` | provenance and timing |
| `missing_source` | present when no file with this content exists in the source folder anymore |

## 3. paragraphs.jsonl

```json
{"i": 157, "page": "24", "sec": "WHO'S REALLY OUT OF CONTROL HERE?", "text": "So I decided, in my parenting-expert wisdom, ..."}
{"i": 158, "h": 2, "page": "25", "sec": "Parent and child > Next section", "text": "Next section"}
{"i": 412, "page": "127", "pages": [["127", 0], ["128", 342]], "sec": "...", "text": "..."}
```

`page` is where the paragraph starts. `pages` appears only when a page begins mid-paragraph, as label and character offset into `text`. `sec` is the last three heading levels in effect. Headings carry `h` with their level. Books without page data have `page: null`, so cite `sec`.

## 4. Page markers, citation styles, chunks

A marker on its own line means a page begins between paragraphs; a marker inside a paragraph means the page begins mid-sentence at that point. For PDFs every page gets a marker, and a paragraph that runs across a page break is rejoined with the marker inline.

Where the numbers come from:
- EPUB3 books: the `page-list` nav in the navigation document.
- EPUB2 books: the `pageList` in the NCX.
- Either version: inline `epub:type="pagebreak"` or `role="doc-pagebreak"` elements.
- PDFs: the document's page label rules when present, otherwise physical page numbers.

Running headers and footers in PDFs are dropped when the same short line repeats at the top or bottom of at least a quarter of the pages (documents of six pages or more), along with bare page numbers at the page edges. Use `--keep-headers` to disable this.

Each chunk starts with a comment such as `<!-- corpus.py doc=8e7a84a3af91b8f7 part=3/12 words=6571 pages=55-84 -->`, then the title and part number, and a "Continues from" line when the chunk opens mid-section. A chunk starts a new file at a chapter-level heading once it has half the target words, or at the target size otherwise.

## 5. How a run decides what to extract

A document is extracted when it is new, when `--force` is set, when the tool's extraction revision changed, when `--retry-failed` is set and it errored or timed out, or when a usable document's `full.md` has gone missing. `--only STATUS,...` narrows a run to documents currently in those statuses (new files are not picked up in that mode), and `--match TEXT` narrows it to paths containing the text. Path lists and `missing_source` flags are refreshed for every document on every run.

## 6. Measured performance

From testing in September 2026 on a Linux sandbox (a Windows desktop should be similar or faster):

| Document | Result |
| --- | --- |
| ScreamFree Parenting EPUB, 72,730 words, 318 page markers | under 2 seconds |
| GeoTopo.pdf, 117 pages with roman and arabic labels | 1.5 seconds |
| tracemonkey.pdf, 14-page two-column paper | 1.1 seconds |
| 218-page PDF with 4 image-only pages OCR'd | 7.8 seconds |
| 2-page scanned PDF, OCR at 300 dpi | 22 seconds |

Timings include starting the worker process. Hashing dominates the first run on a slow or network drive; later runs reuse `hashcache.json`. OCR is the only slow path, so run it as its own pass with fewer workers and a long timeout.

## 7. Windows notes

- Keep the corpus path short, such as `C:\Claude\Corpus\books`, to stay clear of the 260-character path limit.
- Keep the corpus outside OneDrive; thousands of small files make sync churn.
- Output is UTF-8. If the console shows boxes for page markers, the files themselves are fine.
- After installing Tesseract, `tesseract --version` should work in a new terminal. PyMuPDF finds the language data through that install or the `TESSDATA_PREFIX` variable; `extract` prints whether it found OCR support.
- A file open in Excel or locked by antivirus can briefly block writes. The tool retries folder swaps and skips `manifest.csv` when it is open.

## 8. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| Many `.pdf` files report `corrupt` with "content is a zip archive" | They are image bundles exported from a Claude project knowledge store, not PDFs. Use the original files. |
| `page_markers` far below `page_list_entries`, with a warning | The page-list points at element ids the book's XHTML doesn't carry. Spot-check citations with `search` before trusting pages. |
| Garbled characters in a PDF's text | Broken font encoding in the PDF. Rasterize the page and read it, or re-run that file with `--match <name> --force --ocr force`. |
| Two-column PDF text reads in the wrong order | Re-run with `--match <name> --force --pdf-sort`. |
| A book is `needs_ocr` but Tesseract is installed | Open a new terminal so PATH updates, confirm `tesseract --version`, then run the OCR pass. |
| `timeout` on a huge scanned file | Run it alone: `--match <name> --retry-failed --workers 1 --timeout 14400`. |
| Search finds nothing for a phrase you can see in the book | Try a shorter distinctive fragment; hyphenation repaired at line ends and ligatures can differ slightly from the printed text. `--regex` helps for variants. |
