#!/usr/bin/env python3
"""
md2conf.py: convert a knowledge note (ingest-resource markdown) into the Confluence HTML body that
the Atlassian connector's createConfluencePage / updateConfluencePage accept with contentFormat "html".

    python md2conf.py NOTE.md OUT.html [--links links.json] [--version 1.0] [--change "what changed"]
                                       [--history NOTE.history.json] [--date YYYY-MM-DD]

What it produces
  * a property table from the frontmatter (Source, Ingested, Type, Key people, Key concepts, Citations, Version)
  * the "## Summary" section inside an info panel (only when it has no table; panels can't hold tables)
  * "- [ ] task" lines as a Confluence task list
  * [[slug]] wikilinks as real links when links.json knows the slug
    ({"slug": {"title": "...", "url": "..."}}), otherwise as italic text so the gap stays visible
  * a line containing only {{children}} as a live Children Display macro
  * a Version History table, newest first; --history keeps earlier rows across updates
  * the byte size, any unresolved wikilinks, and a warning above 70 KB (split first with split_note.py)

Requires: pip install markdown
"""
import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

try:
    import markdown
except ImportError:
    sys.exit("md2conf.py needs the markdown package: python -m pip install markdown")

CHILDREN_MACRO = ('<div data-type="extension" data-extension-key="children" '
                  'data-extension-type="com.atlassian.confluence.macro.core" '
                  'data-parameters=\'{"macroParams":{"all":{"value":"true"}},'
                  '"macroMetadata":{"schemaVersion":{"value":"2"},"title":"Children Display"}}\'></div>')
SPLIT_WARN_BYTES = 70000  # a 62 KB body published cleanly; larger is untested
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    fm, key = {}, None
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if kv:
            key = kv.group(1)
            fm[key] = kv.group(2).strip()
        elif key:
            fm[key] += " " + line.strip()
    for k, v in fm.items():
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = ", ".join(x.strip() for x in v[1:-1].split(",") if x.strip())
        fm[k] = v.strip('"')
    return fm, text[m.end():]


def inline_md(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", s)


def version_key(v):
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", str(v)))


def time_tag(d):
    d = str(d or "")
    return f'<time datetime="{d}">{d}</time>' if ISO_DATE.fullmatch(d) else html.escape(d)


def convert(note_path, links, version, change, history, when):
    fm, body = parse_frontmatter(Path(note_path).read_text(encoding="utf-8"))
    body = re.sub(r"^\s*# .*\n", "", body, count=1)  # the page title carries the note title
    body = re.sub(r"^[ \t]*\{\{children\}\}[ \t]*$", "CHILDRENMACRO", body, flags=re.M)  # [ \t], not \s: keep the blank line

    def wikilink(m):
        slug = m.group(1).strip()
        info = links.get(slug)
        return f"[{info['title']}]({info['url']})" if info else f"*{slug}*"

    body = re.sub(r"\[\[([^\]]+)\]\]", wikilink, body)
    tasks = []

    def task(m):
        tasks.append(m.group(1))
        return f"TASKITEM{len(tasks) - 1}\n"

    body = re.sub(r"^- \[ \] (.+)$", task, body, flags=re.M)
    h = markdown.markdown(body, extensions=["tables", "sane_lists"])

    def task_list(m):
        items = "".join(f'<li data-type="task-item"><input type="checkbox"> {inline_md(tasks[int(i)])}</li>'
                        for i in re.findall(r"TASKITEM(\d+)", m.group(0)))
        return f'<ul data-type="task-list">{items}</ul>'

    h = re.sub(r"<p>(?:TASKITEM\d+\s*)+</p>", task_list, h)
    merged = re.compile(r'(<ul data-type="task-list">(?:(?!</ul>).)*)</ul>\s*<ul data-type="task-list">', re.S)
    while merged.search(h):
        h = merged.sub(r"\1", h)
    h = h.replace("<p>CHILDRENMACRO</p>", CHILDREN_MACRO).replace("<hr />", "<hr>")
    m = re.search(r"(<h2>Summary</h2>)(.*?)(?=<hr>|<h2>)", h, re.S)
    if m and "<table" not in m.group(2):
        h = h[:m.start()] + m.group(1) + f'<div data-type="panel-info">{m.group(2).strip()}</div>' + h[m.end():]

    rows = [dict(r) for r in (history or [])]
    if not any(str(r.get("version")) == str(version) for r in rows):
        when = when or (date.today().isoformat() if rows else (fm.get("date_ingested") or date.today().isoformat()))
        rows.append({"version": str(version), "date": when, "change": change or "Initial ingest (ingest-resource)"})
    rows.sort(key=lambda r: version_key(r.get("version")), reverse=True)
    props = [("Source", fm.get("source", "")), ("Ingested", fm.get("date_ingested", "")), ("Type", fm.get("type", "")),
             ("Key people", fm.get("key_people", "")), ("Key concepts", fm.get("key_concepts", "")),
             ("Citations", fm.get("page_citations", "")), ("Version", rows[0]["version"])]
    prop = ("<table><thead><tr><th>Property</th><th>Value</th></tr></thead><tbody>"
            + "".join(f"<tr><td><strong>{k}</strong></td><td>{time_tag(v) if k == 'Ingested' else inline_md(v)}</td></tr>"
                      for k, v in props if v)
            + "</tbody></table>")
    history_table = ("<h2>Version History</h2><table><thead><tr><th>Version</th><th>Date</th><th>Change</th></tr>"
                     "</thead><tbody>"
                     + "".join(f"<tr><td>{html.escape(str(r['version']))}</td><td>{time_tag(r.get('date'))}</td>"
                               f"<td>{html.escape(str(r.get('change', '')))}</td></tr>" for r in rows)
                     + "</tbody></table>")
    out = re.sub(r">\s*\n\s*<", "><", prop + h + history_table).strip()  # drop layout newlines, keep inline spaces
    return out, rows


def main():
    ap = argparse.ArgumentParser(description="Convert a knowledge note to Confluence HTML.")
    ap.add_argument("note")
    ap.add_argument("out")
    ap.add_argument("--links", help="links.json mapping wikilink slugs to page titles and URLs")
    ap.add_argument("--version", default="1.0", help="version this body represents (default 1.0)")
    ap.add_argument("--change", help="Version History text for this version")
    ap.add_argument("--history", help="JSON file of earlier Version History rows; rewritten with the new row")
    ap.add_argument("--date", help="date for this version's row (default: date_ingested for 1.0, else today)")
    a = ap.parse_args()
    links = json.loads(Path(a.links).read_text(encoding="utf-8")) if a.links and Path(a.links).exists() else {}
    history = json.loads(Path(a.history).read_text(encoding="utf-8")) if a.history and Path(a.history).exists() else []
    out, rows = convert(a.note, links, a.version, a.change, history, a.date)
    Path(a.out).write_text(out, encoding="utf-8")
    if a.history:
        Path(a.history).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    size = len(out.encode("utf-8"))
    print(f"{a.out}: {size:,} bytes, version {rows[0]['version']}")
    unresolved = sorted(set(re.findall(r"<em>([a-z0-9]+(?:-[a-z0-9]+)+)</em>", out)))
    if unresolved:
        print("  wikilinks without a page yet: " + ", ".join(unresolved))
    if size > SPLIT_WARN_BYTES:
        print(f"  over {SPLIT_WARN_BYTES // 1000} KB: split the note with split_note.py before publishing")


if __name__ == "__main__":
    main()
