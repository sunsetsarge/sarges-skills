#!/usr/bin/env python3
"""
split_note.py: split a long knowledge note into an overview page and a child page before
converting both with md2conf.py.

    python split_note.py NOTE.md [--section "Key points"] [--child-title "Title: Chapter Notes"]

Writes NOTE.parent.md and NOTE.child.md beside NOTE.md. The parent keeps every section except the
chosen one, which becomes a short pointer plus a {{children}} line (rendered as a live list of child
pages). The child keeps the frontmatter, opens with a one-paragraph summary that links back to the
parent through a [[slug]] wikilink, and carries the chosen section.

Why split: a Confluence body over roughly 70 KB is a very large single tool call, and a call that is
cut off mid-write can leave a stub page behind. Two smaller writes are reliable, and the overview page
is cheaper to reload when answering a question later.
"""
import argparse
import re
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description="Split a long note into overview and child notes.")
    ap.add_argument("note")
    ap.add_argument("--section", default="Key points", help='heading of the section to move (default "Key points")')
    ap.add_argument("--child-title", help='title for the child page (default "<note title>: Chapter Notes")')
    a = ap.parse_args()
    path = Path(a.note)
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    fm, body = (m.group(0), text[m.end():]) if m else ("", text)
    title_m = re.search(r"^# (.+)$", body, re.M)
    title = title_m.group(1).strip() if title_m else path.stem
    start = re.search(rf"^## {re.escape(a.section)}\s*$", body, re.M)
    if not start:
        sys.exit(f'No "## {a.section}" heading in {path}')
    nxt = re.compile(r"^## ", re.M).search(body, start.end())
    end = nxt.start() if nxt else len(body)
    section = body[start.start():end]
    trailing_rule = bool(re.search(r"\n-{3,}\s*\Z", section))
    core = re.sub(r"\n-{3,}\s*\Z", "\n", section).rstrip() + "\n"
    child_title = a.child_title or f"{title}: Chapter Notes"

    pointer = (f"## {a.section}\n\n"
               "This section lives on the child page listed below, split out to keep each page a manageable "
               "size. The local note keeps everything in one file.\n\n"
               "{{children}}\n\n"
               + ("---\n\n" if trailing_rule else ""))
    parent = fm + body[:start.start()] + pointer + body[end:]
    child_fm = re.sub(r"^title:.*$", f"title: {child_title}", fm, count=1, flags=re.M) if fm else ""
    child = (child_fm + f"\n# {child_title}\n\n## Summary\n\n"
             f"The {a.section.lower()} for [[{path.stem}]], moved to this child page to keep the overview page a "
             "manageable size. Citations follow the overview page's scheme.\n\n---\n\n" + core)

    parent_path, child_path = path.with_suffix(".parent.md"), path.with_suffix(".child.md")
    parent_path.write_text(parent, encoding="utf-8")
    child_path.write_text(child, encoding="utf-8")
    print(f"{parent_path}: {len(parent.encode('utf-8')):,} bytes\n{child_path}: {len(child.encode('utf-8')):,} bytes")


if __name__ == "__main__":
    main()
