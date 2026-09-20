# Publishing notes to Confluence

## Contents
1. Coordinates and conventions
2. Build the body
3. Create, verify, record
4. Update an existing page
5. Collection hub pages
6. Recovering from a failed or partial write
7. HTML patterns the connector accepts

## 1. Coordinates and conventions

- Site `blainecully.atlassian.net`, space CullyHouse (key `SD`, spaceId `98313`), cloudId `ca6859aa-3e7c-4331-904d-66aecb2409bb`.
- The Atlassian tools load lazily. Run `tool_search("Confluence get page")` before the first call, and search for `createConfluencePage getContentFormatGuide` if the create tool didn't load. `md2conf.py` already follows the connector's HTML format guide.
- Note pages use `contentFormat: "html"`.
- Every update replaces the whole body. Always `getConfluencePage` first so nothing added since the last write is lost.
- Version messages follow Blaine's format `vX.X — description`, adding an `(APP-LL-XXX)` tag when a change implements a logged lesson. Each body also carries a Version History table, newest first; `md2conf.py --history` keeps earlier rows.
- Book notes go under their collection hub (Parenting Library is 121438209). A split book's child page goes under its overview page. For a new collection, confirm the parent with Blaine before creating a hub; the Research Library parent is 30212097.

## 2. Build the body

```powershell
python split_note.py notes\screamfree-parenting.md            # only when the converted HTML would pass ~70 KB
python md2conf.py notes\screamfree-parenting.parent.md notes\parent.html --links notes\links.json `
  --change "Initial ingest from personal EPUB copy with print page citations (ingest-resource)" `
  --history notes\screamfree-parenting.parent.history.json
```

Size guide from real pages: the Positive Discipline note published as one 58 KB page; the ScreamFree note (81 KB of markdown) became a 30 KB overview page and a 62 KB chapter-notes page. Keep each write under roughly 70 KB; nothing larger has been tested.

To pass the body to the tool, print the HTML file and copy it into the `body` parameter exactly. Never retype or condense it.

## 3. Create, verify, record

Call `createConfluencePage` with `cloudId`, `spaceId: "98313"`, `parentId`, `title`, `contentFormat: "html"`, and `body`.

Verify before moving on. The create response includes `body.storage.value`; check that it ends with the Version History table and that the last section before it is present. A body that stops early means the write was cut short, so go to section 6.

Record the result as one line in `<corpus>\notes\confluence-ledger.jsonl`:

```json
{"doc": "screamfree-parenting-10th-anniversary-revised-edition-by-hal--8e7a84a3", "note": "notes/screamfree-parenting.md", "page_id": "121733121", "parent_id": "121438209", "title": "ScreamFree Parenting (Hal Runkel)", "version": 1, "bytes": 29655, "verified": "create response ends with Version History", "at": "2026-09-11T14:56Z"}
```

Then add the page to `links.json` so wikilinks in other notes resolve:

```json
{"screamfree-parenting": {"title": "ScreamFree Parenting (Hal Runkel)", "url": "https://blainecully.atlassian.net/wiki/spaces/cullyhouse/pages/121733121"}}
```

For a split note, convert the child now (its `[[parent]]` link resolves only after this step), create it under the parent, and verify it the same way.

## 4. Update an existing page

1. `getConfluencePage` with `contentFormat: "markdown"` to see the current version and body.
2. Rebuild from the local note: `python md2conf.py note.md out.html --links links.json --version 1.1 --change "what changed" --history note.history.json`.
3. `updateConfluencePage` with `includeBody: false` and a `versionMessage`.
4. Verify by reading the page back with `getConfluencePage` (markdown) and checking that the final section and the new Version History row are there. A CQL phrase search is a lighter spot check, but it can miss phrases containing apostrophes, so the read-back is the reliable test.
5. Append a ledger line with the new version.

## 5. Collection hub pages

A hub such as Parenting Library holds a property table, a summary, a Books table linking each book page, a live Children Display list, a cross-book lookup table with one column per book, usage notes, and version history. When a book joins:

- add its Books row with the page link and citation style;
- add its lookup column and new rows for questions it covers;
- verify every new cell, including cells for older books, against their corpora or published pages, since a lookup cell is a citation;
- bump the version and add a history row, then read the hub back.

## 6. Recovering from a failed or partial write

If a create or update call errors, times out, or the session compacts mid-write:

1. `getConfluencePage` to see what actually saved: version number, and whether the body ends early.
2. Rebuild the full body from the local note, which is the source of truth, and resubmit it as an update.
3. Verify, record, and say what happened in the Version History row, for example "Restored the full page body; the first publish saved only the header and summary".

If the page never got created, check with a CQL title search before creating it again, so a retry doesn't leave a duplicate.

## 7. HTML patterns the connector accepts

| Element | Pattern |
| --- | --- |
| Info panel | `<div data-type="panel-info"><p>...</p></div>` (paragraphs, lists, and headings only; no tables inside) |
| Task list | `<ul data-type="task-list"><li data-type="task-item"><input type="checkbox"> Task text</li></ul>` |
| Children Display macro | the `CHILDREN_MACRO` string in `md2conf.py` |
| Date | `<time datetime="2026-09-11">2026-09-11</time>` |
| Same-page heading link | `<a href="#Heading-text">text</a>` (spaces become hyphens) |
| Horizontal rule | `<hr>` |

Don't put Confluence storage-format markup (`<ac:structured-macro>`, `<ri:page>`) in these bodies; the connector's HTML format uses the `data-type` patterns above and converts them itself.
