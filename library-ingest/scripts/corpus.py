#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
corpus.py: turn a folder of PDF and EPUB files into a page-cited text corpus that
Claude can read, search, and quote from.

    python corpus.py extract SOURCE_DIR OUT_DIR [options]   extract everything (incremental)
    python corpus.py status  OUT_DIR                        buckets, totals, what needs attention
    python corpus.py search  OUT_DIR "phrase" [--doc TEXT]  find a phrase; report page or section
    python corpus.py overlap OUT_DIR NOTE.md --doc TEXT     long verbatim runs a note shares with a book

Design
  Incremental  Files are identified by SHA-256, so re-runs skip unchanged books, moved or
               renamed files keep their extraction, and duplicate copies are merged.
  Isolated     Each file is extracted in its own subprocess with a timeout, so one malformed
               PDF can hang or crash without taking down a multi-thousand-file run.
  Citable      EPUBs keep print page numbers from the publisher's page-list (EPUB3 nav or
               EPUB2 NCX) or inline pagebreak markers. PDFs keep printed page labels when the
               file defines them, otherwise physical page numbers. Books with neither are
               cited by chapter and section. Markers look like ⟦p.23⟧ in full.md and the
               chunks; paragraphs.jsonl carries the same information as data.

Requirements
  Python 3.9+. PDFs: PyMuPDF (pip install pymupdf); pypdf is a slower fallback with no OCR
  and no outline headings. EPUBs: standard library only. OCR of scanned PDFs: Tesseract
  language data installed (tesseract on PATH or TESSDATA_PREFIX set) plus PyMuPDF.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import time
import traceback
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

TOOL_VERSION = "1.0.0"
TOOL_REV = 1  # bump when extraction output changes; older documents get re-extracted
ML, MR = "\u27e6", "\u27e7"  # page marker brackets
BOOK_EXTS = {".pdf", ".epub"}
OTHER_EBOOK_EXTS = {".mobi", ".azw", ".azw3", ".kfx", ".prc", ".djvu", ".cbz", ".cbr", ".fb2", ".lit"}
SKIP_DIRS = {"$recycle.bin", "system volume information", ".git", "__pycache__", "node_modules", "@eadir", ".trash"}
USABLE = {"ok", "partial"}
FAILED = {"error", "timeout"}
TOKENS_PER_WORD = 1.35

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ----------------------------------------------------------------------------- text helpers

_INVISIBLE = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"), None)
_SPACES = str.maketrans({c: " " for c in "\u00a0\u2002\u2003\u2007\u2009\u200a\u202f"})
_LIGATURES = str.maketrans({"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
                            "\ufb05": "st", "\ufb06": "st"})
_FOLD = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'", "\u00b4": "'", "`": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2033": '"', "\u00ab": '"', "\u00bb": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2015": "-", "\u2212": "-",
})


def clean(s) -> str:
    """Unicode-normalize and strip invisible characters, odd spaces, and ligatures."""
    return unicodedata.normalize("NFC", s or "").translate(_INVISIBLE).translate(_SPACES).translate(_LIGATURES)


def squash(s) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def fold(s) -> str:
    """Case- and typography-insensitive form for matching; every character maps to exactly one."""
    return (s or "").translate(_FOLD).lower()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fmt_secs(s: float) -> str:
    s = int(s)
    if s >= 3600:
        return f"{s // 3600}h{(s % 3600) // 60:02d}m"
    return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"


def slugify(name: str, maxlen: int = 60) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:maxlen].rstrip("-") or "doc"


def title_from_filename(path: str) -> str:
    stem = Path(path).stem
    return squash(stem.replace("_", " ")) or stem


def md_cell(s, limit: int = 140) -> str:
    s = squash(str(s if s is not None else "")).replace("|", "\\|")
    return s if len(s) <= limit else s[: limit - 3] + "..."


def sha256_file(path: str):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def write_atomic(path, text: str) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def iter_jsonl(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


ISBN_RX = re.compile(r"ISBN(?:-1[03])?[:\s]*((?:97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx])")


def find_isbn(text: str) -> str:
    m = ISBN_RX.search(text or "")
    return re.sub(r"[-\s]", "", m.group(1)).upper() if m else ""


def sniff(path: str) -> str:
    """What the bytes say the file is, whatever its extension claims."""
    try:
        if os.path.getsize(path) == 0:
            return "empty"
        with open(path, "rb") as f:
            head = f.read(2048)
    except OSError:
        return "unreadable"
    if b"%PDF-" in head[:1024]:
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        return "zip"
    low = head.lstrip().lower()
    if low.startswith((b"<!doctype html", b"<html")) or b"<html" in low[:300]:
        return "an HTML page"
    if head.startswith(b"AT&TFORM"):
        return "DjVu"
    if head[60:68] in (b"BOOKMOBI", b"TEXtREAd"):
        return "MOBI"
    return "unrecognized data"

# ----------------------------------------------------------------------------- block model
#
# A document is a list of blocks:
#   ("mark", label)                       a new page begins between paragraphs
#   ("h", level, text, page_label)        heading
#   ("p", text, [(label, offset), ...])   paragraph; the first entry is the page it starts on,
#                                         later entries are pages that begin mid-paragraph
#   ("img", file, alt, page_label)        an image big enough to be a figure


def block_words(b) -> int:
    if b[0] == "p":
        return len(b[1].split())
    if b[0] == "h":
        return len(b[2].split())
    return 0


def labels_of(b):
    if b[0] == "mark":
        return [b[1]]
    if b[0] in ("h", "img"):
        return [b[3]] if b[3] else []
    if b[0] == "p":
        return [lab for lab, _ in (b[2] or []) if lab is not None]
    return []


def marker(label) -> str:
    return f"{ML}p.{label}{MR}"


def render_para(text: str, pages) -> str:
    inserts = sorted(((off, lab) for lab, off in (pages or []) if lab is not None and 0 < off <= len(text)),
                     reverse=True)
    for off, lab in inserts:
        left, right = text[:off].rstrip(), text[off:].lstrip()
        text = f"{left} {marker(lab)}" + (f" {right}" if right else "")
    return text


def render_blocks(blocks) -> str:
    out = []
    for b in blocks:
        if b[0] == "mark":
            out.append(marker(b[1]))
        elif b[0] == "h":
            out.append("#" * min(6, b[1] + 1) + " " + b[2])
        elif b[0] == "p":
            out.append(render_para(b[1], b[2]))
        elif b[0] == "img":
            out.append(f"[Image: {b[2] or posixpath.basename(b[1])}]")
    return "\n\n".join(out) + "\n"


def section_path(stack) -> str:
    return " > ".join(t for _, t in stack[-3:])


def push_heading(stack, level: int, text: str):
    return [s for s in stack if s[0] < level] + [(level, text[:90])]


def paragraph_records(blocks):
    """Searchable records, one per heading or paragraph, each with its page and section."""
    stack, cur_page, i = [], None, 0
    for b in blocks:
        if b[0] == "mark":
            cur_page = b[1]
        elif b[0] == "h":
            stack = push_heading(stack, b[1], b[2])
            cur_page = b[3] or cur_page
            yield {"i": i, "h": b[1], "page": cur_page, "sec": section_path(stack), "text": b[2]}
            i += 1
        elif b[0] == "p":
            pages = [[lab, off] for lab, off in (b[2] or []) if lab is not None]
            start = pages[0][0] if pages and pages[0][1] == 0 else cur_page
            rec = {"i": i, "page": start, "sec": section_path(stack), "text": b[1]}
            if len(pages) > 1 or (pages and pages[0][1] > 0):
                rec["pages"] = pages
            yield rec
            if pages:
                cur_page = pages[-1][0]
            i += 1
        elif b[0] == "img" and b[3]:
            cur_page = b[3]


def page_at(rec: dict, pos: int):
    label = rec.get("page")
    for lab, off in rec.get("pages") or []:
        if off <= pos:
            label = lab
    return label


def build_chunks(blocks, target_words: int):
    """Split at chapter-level headings once a chunk is half full, otherwise at the target size."""
    chunks, cur, count = [], [], 0
    for b in blocks:
        major = b[0] == "h" and b[1] <= 2
        if cur and ((major and count >= target_words * 0.5) or count >= target_words):
            chunks.append(cur)
            cur, count = [], 0
        cur.append(b)
        count += block_words(b)
    if cur:
        chunks.append(cur)
    return chunks


def chunk_page_range(chunk, carry):
    first_label = (labels_of(chunk[0]) or [None])[0] if chunk else None
    start = first_label if (chunk and chunk[0][0] == "mark") or carry is None else carry
    last = carry
    for b in chunk:
        labs = labels_of(b)
        if labs:
            last = labs[-1]
            if start is None:
                start = labs[0]
    return start, last


FRONTMATTER_KEYS = ["title", "authors", "publisher", "year", "isbn", "type", "cite_style", "pages", "page_markers",
                    "words", "sha256", "primary", "extracted_at", "extractor"]


def write_document(docdir: Path, rec: dict, blocks, extra: dict, chunk_words: int) -> None:
    """Write full.md, chunks/, paragraphs.jsonl, and meta.json, then swap the folder into place."""
    tmp = Path(f"{docdir}.tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "chunks").mkdir(parents=True)
    chunks = build_chunks(blocks, chunk_words)
    rec["chunks"] = len(chunks)
    fm = "\n".join(f"{k}: {json.dumps(rec.get(k), ensure_ascii=False)}" for k in FRONTMATTER_KEYS
                   if rec.get(k) not in (None, "", []))
    write_atomic(tmp / "full.md", f"---\n{fm}\n---\n\n# {rec['title']}\n\n{render_blocks(blocks)}")
    with open(tmp / "paragraphs.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in paragraph_records(blocks):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    carry, stack = None, []
    for n, chunk in enumerate(chunks, 1):
        first, last = chunk_page_range(chunk, carry)
        span = "" if first is None else (first if first == last else f"{first}-{last}")
        head = (f"<!-- corpus.py doc={rec['id']} part={n}/{len(chunks)} "
                f"words={sum(block_words(b) for b in chunk)} pages={span} -->\n"
                f"# {rec['title']} (part {n} of {len(chunks)})\n\n")
        if stack and not (chunk[0][0] == "h" and chunk[0][1] <= 2):
            head += f"_Continues from: {section_path(stack)}_\n\n"
        write_atomic(tmp / "chunks" / f"part-{n:03d}.md", head + render_blocks(chunk))
        for b in chunk:
            if b[0] == "h":
                stack = push_heading(stack, b[1], b[2])
        carry = last
    meta = dict(rec)
    meta.update(extra)
    write_atomic(tmp / "meta.json", json.dumps(meta, ensure_ascii=False, indent=1))
    for attempt in range(5):  # antivirus or an open Explorer window can briefly lock folders on Windows
        try:
            if docdir.exists():
                shutil.rmtree(docdir)
            os.replace(tmp, docdir)
            return
        except OSError:
            if attempt == 4:
                raise
            time.sleep(1 + attempt)

# ----------------------------------------------------------------------------- PDF

_PAGE_NUM_RX = re.compile(r"^(?:page\s*)?(?:\d{1,4}|[ivxlcdm]{1,7})$", re.I)
_KEEP_HYPHEN = {"self", "well", "non", "anti", "co", "cross", "half", "ill", "long", "multi", "over", "post", "pre",
                "pro", "semi", "sub", "under", "all", "ex", "great", "high", "low", "mid", "full", "part", "first",
                "second", "third", "back", "life", "left", "right", "time", "world", "one", "two", "three", "four",
                "five", "six", "seven", "eight", "nine", "ten", "twenty", "thirty", "forty", "fifty"}


def import_pymupdf():
    for name in ("pymupdf", "fitz"):
        try:
            mod = __import__(name)
        except ImportError:
            continue
        if hasattr(mod, "open") and hasattr(mod, "Document"):
            return mod
    return None


def _boiler_key(t: str) -> str:
    t = re.sub(r"\d+", "#", squash(t).lower())
    return re.sub(r"\b[ivxlcdm]{1,7}\b", "#", t)


def _keep_hyphen(text: str) -> bool:
    m = re.search(r"([A-Za-z]+)-$", text)
    return bool(m) and m.group(1).lower() in _KEEP_HYPHEN


def _reflow(t: str) -> str:
    """Join a PDF text block's lines into one paragraph, repairing end-of-line hyphenation."""
    out = ""
    for line in clean(t).split("\n"):
        line = squash(line)
        if not line:
            continue
        if not out:
            out = line
        elif out.endswith("-") and len(out) > 1 and out[-2].isalpha() and line[:1].islower():
            out = out + line if _keep_hyphen(out) else out[:-1] + line
        else:
            out = f"{out} {line}"
    return out


def assemble_pages(pages, toc_by_page, keep_headers: bool):
    """pages: [{"label": str, "items": [(at_page_edge, text), ...]}] in reading order -> (blocks, text_pages)."""
    n = len(pages)
    boiler = set()
    if not keep_headers and n >= 6:
        counts = Counter()
        for p in pages:
            counts.update({_boiler_key(t) for edge, t in p["items"] if edge and len(t) < 200})
        boiler = {k for k, c in counts.items() if k and c >= max(3, int(0.25 * n))}
    blocks, last_p, text_pages = [], None, 0
    for i, p in enumerate(pages):
        label = p["label"]
        paras = []
        for edge, t in p["items"]:
            if edge and (_PAGE_NUM_RX.match(squash(t)) or _boiler_key(t) in boiler):
                continue
            r = _reflow(t)
            if r:
                paras.append(r)
        heads = toc_by_page.get(i, [])
        text_pages += 1 if paras else 0
        merged = False
        if paras and not heads and last_p is not None:
            prev_text, prev_pages = blocks[last_p][1], blocks[last_p][2]
            if re.search(r"[A-Za-z,;\-]$", prev_text) and paras[0][:1].islower():
                if prev_text.endswith("-") and len(prev_text) > 1 and prev_text[-2].isalpha() and not _keep_hyphen(prev_text):
                    joined, off = prev_text[:-1] + paras[0], len(prev_text) - 1
                elif prev_text.endswith("-"):
                    joined, off = prev_text + paras[0], len(prev_text)
                else:
                    joined, off = f"{prev_text} {paras[0]}", len(prev_text) + 1
                blocks[last_p] = ("p", joined, prev_pages + [(label, off)])
                paras, merged = paras[1:], True
        if not merged:
            blocks.append(("mark", label))
        for lvl, title in heads:
            blocks.append(("h", lvl, title, label))
        if heads:
            last_p = None
        for t in paras:
            blocks.append(("p", t, [(label, 0)]))
            last_p = len(blocks) - 1
        if not paras and not merged:
            last_p = None
    return blocks, text_pages


def pdf_status(rec: dict, n: int, text_pages: int, scanned: int, words: int) -> None:
    if n == 0:
        rec.update(status="empty", detail="PDF has no pages")
    elif scanned and (text_pages == 0 or scanned > 0.5 * n):
        rec.update(status="needs_ocr", detail=f"{scanned} of {n} pages are images without a text layer")
    elif scanned:
        rec.update(status="partial", detail=f"{scanned} of {n} pages are images without a text layer")
    elif words == 0:
        rec.update(status="empty", detail="no text layer and no page images found")
    else:
        rec.update(status="ok", detail="")


def pdf_title(t) -> str:
    t = squash(clean(str(t or "")))
    if not t or re.search(r"\.(docx?|pdf|indd|qxd|rtf|txt|pages)$", t, re.I) or \
            t.lower().startswith(("microsoft word", "untitled", "slide 1")):
        return ""
    return t


def split_authors(a) -> list:
    return [squash(x) for x in re.split(r";|\s&\s|\s+and\s+", clean(str(a or ""))) if squash(x)]


def extract_pdf_pymupdf(fitz, path, job, rec, warnings):
    doc = fitz.open(path)
    try:
        if doc.needs_pass and not doc.authenticate(""):
            rec.update(status="encrypted", detail="password-protected PDF")
            return None
        n = doc.page_count
        rec["pages"] = n
        meta = doc.metadata or {}
        rec["title"] = pdf_title(meta.get("title"))
        rec["authors"] = split_authors(meta.get("author"))
        try:
            has_labels = bool(doc.get_page_labels())
        except Exception:
            has_labels = False
        toc_list, toc_by_page = [], defaultdict(list)
        try:
            for lvl, title, pno in doc.get_toc(simple=True):
                title = squash(clean(title))
                if title and 1 <= pno <= n:
                    toc_list.append([lvl, title, pno - 1])
                    if lvl <= 3:
                        toc_by_page[pno - 1].append((lvl, title))
        except Exception as e:
            warnings.append(f"outline unreadable: {e}")
        use_ocr = job["ocr"] != "off" and job.get("ocr_available")
        pages, scanned, ocr_pages, ocr_errors, head_text = [], 0, 0, 0, []
        for i in range(n):
            try:
                page = doc.load_page(i)
                label = (page.get_label() if has_labels else "") or str(i + 1)
                height = page.rect.height or 1.0

                def items_from(textpage=None, _page=page, _h=height):
                    raw = _page.get_text("blocks", textpage=textpage,
                                         sort=bool(job.get("pdf_sort")) or textpage is not None)
                    return [(b[1] / _h < 0.1 or b[3] / _h > 0.9, b[4]) for b in raw if b[6] == 0 and b[4].strip()]

                items = items_from()
                chars = sum(len(t.strip()) for _, t in items)
                candidate = chars < job["min_page_chars"] and bool(page.get_images(full=False))
                if use_ocr and (job["ocr"] == "force" or candidate):
                    try:
                        tp = page.get_textpage_ocr(language=job["ocr_lang"], dpi=job["ocr_dpi"], full=True)
                        items, candidate = items_from(tp), False
                        ocr_pages += 1
                    except Exception as e:
                        ocr_errors += 1
                        if ocr_errors <= 3:
                            warnings.append(f"OCR failed on page {i + 1}: {e}")
            except Exception as e:
                warnings.append(f"page {i + 1} unreadable: {e.__class__.__name__}: {e}")
                label, items, candidate = str(i + 1), [], False
            scanned += 1 if candidate else 0
            if i < 8:
                head_text.append(" ".join(t for _, t in items))
            pages.append({"label": label, "items": items})
        blocks, text_pages = assemble_pages(pages, toc_by_page, bool(job.get("keep_headers")))
        words = sum(block_words(b) for b in blocks)
        rec.update(isbn=find_isbn(" ".join(head_text)), page_markers=n, ocr_pages=ocr_pages, scanned_pages=scanned,
                   cite_style="pdf-page-labels" if has_labels else "pdf-physical-pages")
        if ocr_errors > 3:
            warnings.append(f"OCR failed on {ocr_errors} pages in total")
        pdf_status(rec, n, text_pages, scanned, words)
        return blocks, {"toc": [[lvl, title, pages[p]["label"]] for lvl, title, p in toc_list]}
    finally:
        doc.close()


def extract_pdf_pypdf(path, job, rec, warnings):
    from pypdf import PdfReader
    reader = PdfReader(path)
    if reader.is_encrypted:
        try:
            unlocked = reader.decrypt("")
        except Exception:
            unlocked = 0
        if not unlocked:
            rec.update(status="encrypted", detail="password-protected PDF")
            return None
    n = len(reader.pages)
    rec["pages"] = n
    try:
        labels = list(reader.page_labels)
    except Exception:
        labels = []
    has_labels = len(labels) == n and any(lab != str(i + 1) for i, lab in enumerate(labels))
    info = reader.metadata
    rec["title"] = pdf_title(getattr(info, "title", None) if info else None)
    rec["authors"] = split_authors(getattr(info, "author", None) if info else None)
    pages, scanned, head_text = [], 0, []
    for i, page in enumerate(reader.pages):
        try:
            text = clean(page.extract_text() or "")
        except Exception as e:
            text = ""
            warnings.append(f"page {i + 1}: {e.__class__.__name__}")
        try:
            has_img = "/XObject" in page["/Resources"]
        except Exception:
            has_img = False
        scanned += 1 if (len(text.strip()) < job["min_page_chars"] and has_img) else 0
        lines = [ln for ln in text.split("\n") if ln.strip()]
        items, run = [], []
        for j, ln in enumerate(lines):
            if (j < 2 or j >= len(lines) - 2) and len(ln.strip()) <= 60:
                if run:
                    items.append((False, "\n".join(run)))
                    run = []
                items.append((True, ln))
            else:
                run.append(ln)
        if run:
            items.append((False, "\n".join(run)))
        if i < 8:
            head_text.append(text)
        pages.append({"label": labels[i] if has_labels else str(i + 1), "items": items})
    blocks, text_pages = assemble_pages(pages, {}, bool(job.get("keep_headers")))
    words = sum(block_words(b) for b in blocks)
    rec.update(isbn=find_isbn(" ".join(head_text)), page_markers=n, scanned_pages=scanned,
               cite_style="pdf-page-labels" if has_labels else "pdf-physical-pages")
    pdf_status(rec, n, text_pages, scanned, words)
    return blocks, {"toc": []}


def extract_pdf(path, job, rec, warnings):
    fitz = import_pymupdf()
    if fitz is not None:
        rec["extractor"] = f"pymupdf {getattr(fitz, 'VersionBind', '')}".strip()
        return extract_pdf_pymupdf(fitz, path, job, rec, warnings)
    try:
        import pypdf
    except ImportError:
        rec.update(status="error", detail="no PDF library available; run: pip install pymupdf")
        return None
    rec["extractor"] = f"pypdf {pypdf.__version__}"
    warnings.append("pypdf fallback in use: no OCR, no outline headings, weaker paragraphs (pip install pymupdf)")
    return extract_pdf_pypdf(path, job, rec, warnings)

# ----------------------------------------------------------------------------- EPUB

FONT_OBFUSCATION = {"http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC"}
HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
BLOCK_TAGS = {"p", "div", "section", "article", "aside", "header", "footer", "main", "blockquote", "li", "dd", "dt",
              "pre", "table", "thead", "tbody", "tfoot", "tr", "figure", "figcaption", "ul", "ol", "dl", "nav", "hr",
              "address", "details", "summary", "caption", "body"}
SKIP_TAGS = {"head", "script", "style", "template", "svg", "math", "noscript"}
VOID_TAGS = {"br", "img", "hr", "input", "meta", "link", "wbr", "col", "area", "base", "source", "embed", "param",
             "track"}
FIGURE_MIN_BYTES = 20000


def lname(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def xml_iter(el, name: str):
    return [c for c in el.iter() if lname(c.tag) == name] if el is not None else []


def xml_children(el, name: str):
    return [c for c in el if lname(c.tag) == name] if el is not None else []


def xml_text(el) -> str:
    return squash(clean("".join(el.itertext()))) if el is not None else ""


def first(seq, default=None):
    return next(iter(seq), default)


def decode_markup(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        m = re.search(rb'encoding=["\']([A-Za-z0-9._-]+)["\']', data[:300])
        try:
            return data.decode(m.group(1).decode("ascii") if m else "cp1252", errors="replace")
        except LookupError:
            return data.decode("cp1252", errors="replace")


class ZipIndex:
    """Case- and URL-encoding-tolerant lookup of EPUB members."""

    def __init__(self, z: zipfile.ZipFile):
        self.z = z
        self.names = {info.filename.lower(): info.filename for info in z.infolist()}
        self.sizes = {info.filename: info.file_size for info in z.infolist()}

    def find(self, path):
        p = posixpath.normpath(path or "").lstrip("/")
        return self.names.get(p.lower()) or self.names.get(unquote(p).lower())

    def read(self, name: str) -> bytes:
        return self.z.read(name)


def resolve_href(base_file: str, href: str):
    path, _, frag = (href or "").partition("#")
    if not path:
        return base_file, unquote(frag)
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_file), unquote(path))), unquote(frag)


class NavParser(HTMLParser):
    """Reads the toc and page-list navs of an EPUB3 navigation document."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lists = {"toc": [], "page-list": []}
        self.kind, self.nav_depth, self.ol_depth = None, 0, 0
        self.href, self.buf = None, []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "nav":
            self.nav_depth += 1
            if self.nav_depth == 1:
                t = f"{a.get('epub:type', '')} {a.get('role', '')}".lower()
                self.kind = "page-list" if ("page-list" in t or "doc-pagelist" in t) else ("toc" if "toc" in t else None)
        elif self.kind and tag == "ol":
            self.ol_depth += 1
        elif self.kind and tag == "a" and a.get("href"):
            self.href, self.buf = a["href"], []

    def handle_endtag(self, tag):
        if tag == "nav":
            self.nav_depth = max(0, self.nav_depth - 1)
            if self.nav_depth == 0:
                self.kind, self.ol_depth = None, 0
        elif self.kind and tag == "ol":
            self.ol_depth = max(0, self.ol_depth - 1)
        elif self.kind and tag == "a" and self.href is not None:
            self.lists[self.kind].append((self.href, squash(clean("".join(self.buf))), max(1, self.ol_depth)))
            self.href = None

    def handle_data(self, data):
        if self.href is not None:
            self.buf.append(data)


class XhtmlToBlocks(HTMLParser):
    """Streams one XHTML content document into blocks, placing markers where the book's pages begin."""

    def __init__(self, page_ids: dict, toc_ids: dict, start_page, image_lookup):
        super().__init__(convert_charrefs=True)
        self.page_ids, self.toc_ids, self.image_lookup = page_ids, toc_ids, image_lookup
        self.blocks, self.images, self.toc_hits = [], [], []
        self.cur_page, self.marks = start_page, 0
        self.text, self.inline_pages, self.block_page = "", [], start_page
        self.skip, self.pre, self.heading, self.cells = 0, 0, None, 0
        self.pb_buf, self.pb_depth, self.pb_label = None, 0, None

    def _append(self, s: str) -> None:
        if not s:
            return
        if not self.text:
            s = s.lstrip()
            if not s:
                return
            self.block_page = self.cur_page
        elif not self.pre:
            if self.text[-1] in " \n":
                s = s.lstrip(" ")
            if s.startswith("\n"):
                self.text = self.text.rstrip(" ")
        self.text += s

    def _has_text(self) -> bool:
        return bool(self.text.strip().strip("-|").strip())

    def _flush(self) -> None:
        raw, pages = self.text, self.inline_pages
        self.text, self.inline_pages = "", []
        body = raw.strip()
        if not body.strip("-| "):
            return
        if self.heading is not None:
            self.blocks.append(("h", self.heading, squash(body), self.block_page))
            self.blocks.extend(("mark", lab) for lab, _ in pages)
            return
        lead = len(raw) - len(raw.lstrip())
        entries = [(self.block_page, 0)] + [(lab, min(len(body), max(0, off - lead))) for lab, off in pages]
        self.blocks.append(("p", body, entries))

    def _mark(self, label) -> None:
        label = squash(clean(str(label)))
        if not label or label == self.cur_page:
            return
        self.cur_page = label
        self.marks += 1
        if self._has_text():
            self.inline_pages.append((label, len(self.text)))
        else:
            if self.text:
                self.block_page = label
            self.blocks.append(("mark", label))

    def _anchor(self, el_id: str) -> None:
        if not el_id:
            return
        if el_id in self.toc_ids:
            title, depth = self.toc_ids[el_id]
            self.toc_hits.append((depth, title, len(self.blocks)))
        if el_id in self.page_ids:
            self._mark(self.page_ids[el_id])

    def _image(self, a: dict) -> None:
        src = a.get("src") or a.get("xlink:href") or ""
        if not src:
            return
        name, size = self.image_lookup(src)
        alt = squash(clean(a.get("alt", "")))
        self.images.append({"file": name, "alt": alt, "page": self.cur_page, "bytes": size})
        if self.heading is None and (size >= FIGURE_MIN_BYTES or (alt and size >= 2000)):
            self._flush()
            self.blocks.append(("img", name, alt, self.cur_page))

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self.skip:
            if tag in SKIP_TAGS:
                self.skip += 1
            return
        if tag in SKIP_TAGS:
            self.skip = 1
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        if self.pb_buf is not None:
            if tag not in VOID_TAGS:
                self.pb_depth += 1
            return
        role = f"{a.get('epub:type', '')} {a.get('role', '')}".lower()
        if "pagebreak" in role and tag not in VOID_TAGS:
            self.pb_buf, self.pb_depth = [], 1
            self.pb_label = a.get("title") or a.get("aria-label") or self.page_ids.get(a.get("id", ""))
            return
        if "pagebreak" in role:  # e.g. <hr epub:type="pagebreak" title="12"/>
            self._mark(a.get("title") or a.get("aria-label") or self.page_ids.get(a.get("id", ""), ""))
            return
        self._anchor(a.get("id") or (a.get("name", "") if tag == "a" else ""))
        if tag in HEADINGS:
            self._flush()
            self.heading = HEADINGS[tag]
        elif tag in ("td", "th"):
            if self.cells and self._has_text():
                self._append(" | ")
            self.cells += 1
        elif tag == "br":
            self._append("\n")
        elif tag == "img":
            self._image(a)
        elif tag in BLOCK_TAGS and self.heading is None:
            self._flush()
            if tag == "tr":
                self.cells = 0
            elif tag == "li":
                self._append("- ")
        if tag == "pre":
            self.pre += 1

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip:
            if tag in SKIP_TAGS:
                self.skip -= 1
            return
        if self.pb_buf is not None:
            if tag in VOID_TAGS:
                return
            self.pb_depth -= 1
            if self.pb_depth <= 0:
                label = self.pb_label or squash("".join(self.pb_buf))
                self.pb_buf = None
                if label:
                    self._mark(label)
            return
        if tag in HEADINGS:
            self._flush()
            self.heading = None
        elif tag in BLOCK_TAGS and self.heading is None:
            self._flush()
            if tag == "tr":
                self.cells = 0
        if tag == "pre":
            self.pre = max(0, self.pre - 1)

    def handle_data(self, data):
        if self.skip:
            return
        if self.pb_buf is not None:
            self.pb_buf.append(data)
            if sum(len(x) for x in self.pb_buf) > 40:  # too long for a page label; give the text back
                captured, label = "".join(self.pb_buf), self.pb_label
                self.pb_buf = None
                if label:
                    self._mark(label)
                self._append(re.sub(r"\s+", " ", clean(captured)))
            return
        data = clean(data)
        self._append(data if self.pre else re.sub(r"\s+", " ", data))


def epub_drm(zi: ZipIndex):
    if zi.find("META-INF/sinf.xml"):
        return "DRM-protected EPUB (Apple FairPlay)"
    enc = zi.find("META-INF/encryption.xml")
    if not enc:
        return None
    try:
        root = ET.fromstring(zi.read(enc))
    except ET.ParseError:
        return None
    locked = []
    for ed in xml_iter(root, "EncryptedData"):
        method = first(xml_iter(ed, "EncryptionMethod"))
        ref = first(xml_iter(ed, "CipherReference"))
        if method is not None and method.get("Algorithm") in FONT_OBFUSCATION:
            continue
        uri = ref.get("URI", "") if ref is not None else ""
        if re.search(r"\.(x?html?|xml|ncx|opf)$", uri, re.I):
            locked.append(uri)
    if not locked:
        return None
    adept = " (Adobe ADEPT)" if zi.find("META-INF/rights.xml") else ""
    return f"DRM-protected EPUB{adept}: {len(locked)} content files are encrypted"


def extract_epub(path, job, rec, warnings):
    with zipfile.ZipFile(path) as z:
        zi = ZipIndex(z)
        drm = epub_drm(zi)
        if drm:
            rec.update(status="drm", detail=drm)
            return None
        container = zi.find("META-INF/container.xml")
        if not container:
            rec.update(status="corrupt", detail="zip archive without META-INF/container.xml, so not an EPUB")
            return None
        rootfiles = [e.get("full-path") for e in xml_iter(ET.fromstring(zi.read(container)), "rootfile")]
        opf_name = first(zi.find(r) for r in rootfiles if r and zi.find(r))
        if not opf_name:
            rec.update(status="corrupt", detail="EPUB package document (OPF) is missing")
            return None
        opf = ET.fromstring(zi.read(opf_name))
        md = first(xml_iter(opf, "metadata"))

        def dc(name):
            return [t for t in (xml_text(e) for e in xml_iter(md, name)) if t]

        rec["title"] = first(dc("title"), "")
        rec["authors"] = dc("creator")
        rec["publisher"] = first(dc("publisher"), "")
        rec["language"] = first(dc("language"), "")
        rec["year"] = first((m.group(0) for m in (re.search(r"\b(?:1[5-9]|20)\d\d\b", d) for d in dc("date")) if m), "")
        for ident in dc("identifier"):
            digits = re.sub(r"[^0-9Xx]", "", ident)
            if re.fullmatch(r"(?:urn:isbn:)?[\d\s-]{9,17}[\dXx]", ident.strip(), re.I) and len(digits) in (10, 13):
                rec["isbn"] = digits.upper()
                break

        manifest = {}
        for item in xml_iter(opf, "item"):
            if item.get("href") and item.get("id"):
                full, _ = resolve_href(opf_name, item.get("href"))
                manifest[item.get("id")] = {"name": zi.find(full) or full,
                                            "type": (item.get("media-type") or "").lower(),
                                            "props": (item.get("properties") or "").lower().split()}
        spine_el = first(xml_iter(opf, "spine"))
        spine = [ir.get("idref") for ir in xml_iter(spine_el, "itemref") if ir.get("idref")]
        if not spine:
            rec.update(status="corrupt", detail="EPUB reading order (spine) is empty")
            return None

        page_list, toc = [], []  # (file, fragment, label) and (file, fragment, title, depth)
        nav = first(m for m in manifest.values() if "nav" in m["props"])
        if nav and zi.find(nav["name"]):
            parser = NavParser()
            try:
                parser.feed(decode_markup(zi.read(zi.find(nav["name"]))))
                parser.close()
            except Exception as e:
                warnings.append(f"navigation document unreadable: {e}")
            for href, label, _ in parser.lists["page-list"]:
                f, frag = resolve_href(nav["name"], href)
                page_list.append((zi.find(f) or f, frag, label))
            for href, title, depth in parser.lists["toc"]:
                f, frag = resolve_href(nav["name"], href)
                toc.append((zi.find(f) or f, frag, title, depth))
        ncx = manifest.get(spine_el.get("toc") if spine_el is not None else None) or \
            first(m for m in manifest.values() if m["type"] == "application/x-dtbncx+xml")
        if ncx and zi.find(ncx["name"]) and (not page_list or not toc):
            try:
                nroot = ET.fromstring(zi.read(zi.find(ncx["name"])))
                if not page_list:
                    for target in xml_iter(nroot, "pageTarget"):
                        content = first(xml_iter(target, "content"))
                        label = xml_text(first(xml_iter(target, "navLabel"))) or target.get("value", "")
                        if content is not None and content.get("src"):
                            f, frag = resolve_href(ncx["name"], content.get("src"))
                            page_list.append((zi.find(f) or f, frag, label))
                if not toc:
                    def walk(point, depth):
                        content = first(xml_children(point, "content"))
                        if content is not None and content.get("src"):
                            f, frag = resolve_href(ncx["name"], content.get("src"))
                            toc.append((zi.find(f) or f, frag, xml_text(first(xml_children(point, "navLabel"))), depth))
                        for child in xml_children(point, "navPoint"):
                            walk(child, depth + 1)

                    for point in xml_children(first(xml_iter(nroot, "navMap")), "navPoint"):
                        walk(point, 1)
            except ET.ParseError as e:
                warnings.append(f"NCX unreadable: {e}")

        page_ids, file_start_page = defaultdict(dict), {}
        for f, frag, label in page_list:
            if label:
                if frag:
                    page_ids[f].setdefault(frag, label)
                else:
                    file_start_page.setdefault(f, label)
        toc_ids, file_start_toc = defaultdict(dict), defaultdict(list)
        for f, frag, title, depth in toc:
            if title:
                if frag:
                    toc_ids[f].setdefault(frag, (title, depth))
                else:
                    file_start_toc[f].append((title, depth))

        def image_lookup(base):
            def look(src):
                f, _ = resolve_href(base, src)
                name = zi.find(f)
                return (name, zi.sizes.get(name, 0)) if name else (f, 0)
            return look

        blocks, images, toc_hits, cur_page, seen = [], [], [], None, set()
        for idref in spine:
            item = manifest.get(idref)
            if not item:
                warnings.append(f"spine entry {idref!r} is not in the manifest")
                continue
            name = zi.find(item["name"])
            if not name or name in seen:
                continue
            seen.add(name)
            if "html" not in item["type"] and not name.lower().endswith((".xhtml", ".html", ".htm")):
                continue
            label = file_start_page.get(name)
            if label and label != cur_page:
                blocks.append(("mark", label))
                cur_page = label
            for title, depth in file_start_toc.get(name, []):
                toc_hits.append((depth, title, len(blocks)))
            parser = XhtmlToBlocks(page_ids.get(name, {}), toc_ids.get(name, {}), cur_page, image_lookup(name))
            try:
                parser.feed(decode_markup(zi.read(name)))
                parser.close()
            except Exception as e:
                warnings.append(f"{name}: {e.__class__.__name__} while parsing; text may be incomplete")
            parser._flush()
            toc_hits.extend((d, t, len(blocks) + i) for d, t, i in parser.toc_hits)
            blocks.extend(parser.blocks)
            images.extend(parser.images)
            cur_page = parser.cur_page

        markers = sum(1 for b in blocks if b[0] == "mark") + sum(len(b[2]) - 1 for b in blocks if b[0] == "p")
        words = sum(block_words(b) for b in blocks)
        rec.update(page_list_entries=len(page_list), page_markers=markers, images=len(images),
                   cite_style="print-pages" if markers else "sections", extractor="epub (python stdlib)")
        distinct = len({label for _, _, label in page_list if label})
        if distinct and markers < 0.8 * distinct:
            warnings.append(f"page-list names {distinct} pages but only {markers} markers were placed; "
                            "some page citations may be off")
        if words == 0 and images:
            rec.update(status="needs_ocr", detail="image-only EPUB with no text layer")
        elif words < 300 and len(images) >= 10:
            rec.update(status="needs_ocr", detail="mostly images; likely a scanned or fixed-layout EPUB")
        elif words == 0:
            rec.update(status="empty", detail="no text found in the reading order")
        else:
            rec.update(status="ok", detail="")

        def page_from(idx):
            for b in blocks[idx: idx + 80]:
                labs = labels_of(b)
                if labs:
                    return labs[0]
            return None

        figures = [im for im in images if im["bytes"] >= FIGURE_MIN_BYTES or im["alt"]]
        return blocks, {"toc": [[d, t, page_from(i)] for d, t, i in toc_hits], "figures": figures}

# ----------------------------------------------------------------------------- worker (one file per process)

def base_record(job: dict) -> dict:
    path = job["paths"][0]
    return {"id": job["sha256"][:16], "sha256": job["sha256"], "folder": job["folder"], "paths": job["paths"],
            "primary": path, "bytes": job.get("bytes"), "type": Path(path).suffix.lower().lstrip("."),
            "status": "error", "detail": "", "title": "", "authors": [], "words": 0, "est_tokens": 0, "chunks": 0,
            "warnings": [], "tool_version": TOOL_VERSION, "tool_rev": TOOL_REV, "extracted_at": now_iso()}


def run_worker(job: dict) -> dict:
    rec = base_record(job)
    warnings = rec["warnings"]
    path = job["paths"][0]
    try:
        kind, ext = sniff(path), Path(path).suffix.lower()
        result = None
        if kind == "empty":
            rec.update(status="empty", detail="zero-byte file")
        elif kind == "pdf":
            if ext != ".pdf":
                warnings.append(f"named {ext} but the content is a PDF")
            rec["type"] = "pdf"
            result = extract_pdf(path, job, rec, warnings)
        elif kind == "zip":
            if ext != ".epub":
                warnings.append(f"named {ext} but the content is a zip archive")
            rec["type"] = "epub"
            result = extract_epub(path, job, rec, warnings)
        else:
            rec.update(status="corrupt", detail=f"not a valid {ext.lstrip('.').upper() or 'file'}: the content is {kind}")
        if result is not None:
            blocks, extra = result
            rec["title"] = rec.get("title") or title_from_filename(path)
            rec["words"] = sum(block_words(b) for b in blocks)
            rec["est_tokens"] = int(rec["words"] * TOKENS_PER_WORD)
            if rec["words"] and rec["status"] in (USABLE | {"needs_ocr"}):
                write_document(Path(job["docdir"]), rec, blocks, extra, job["chunk_words"])
    except zipfile.BadZipFile as e:
        rec.update(status="corrupt", detail=f"damaged zip container: {e}")
    except ET.ParseError as e:
        rec.update(status="corrupt", detail=f"malformed EPUB XML: {e}")
    except Exception as e:
        rec.update(status="error", detail=f"{e.__class__.__name__}: {e}")
        warnings.append(traceback.format_exc(limit=6)[-2000:])
    rec["title"] = rec.get("title") or title_from_filename(path)
    rec["extracted_at"] = now_iso()
    return rec


def run_job(job: dict, timeout: int) -> dict:
    """Extract one document in a child process so a hang or crash costs only that file."""
    payload, job_file = json.dumps(job), None
    if len(payload) > 7000:
        job_file = f"{job['docdir']}.job.json"
        write_atomic(job_file, payload)
        payload = "@" + job_file
    cmd = [sys.executable, os.path.abspath(__file__), "_worker", payload]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    started = time.time()
    rec = base_record(job)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, env=env)
        line = next((ln for ln in reversed(proc.stdout.splitlines()) if ln.startswith("RESULT ")), None)
        if line is None:
            tail = (proc.stderr or proc.stdout or "").strip()[-800:]
            rec.update(status="error", detail=f"worker exited with code {proc.returncode}: {tail}")
        else:
            rec = json.loads(line[len("RESULT "):])
    except subprocess.TimeoutExpired:
        shutil.rmtree(f"{job['docdir']}.tmp", ignore_errors=True)
        rec.update(status="timeout", detail=f"no result after {timeout}s; retry it alone with a longer --timeout")
    except Exception as e:
        rec.update(status="error", detail=f"could not run worker: {e.__class__.__name__}: {e}")
    if job_file:
        try:
            os.remove(job_file)
        except OSError:
            pass
    rec["seconds"] = round(time.time() - started, 1)
    return rec


def ocr_available() -> bool:
    fitz = import_pymupdf()
    if fitz is None:
        return False
    try:
        if hasattr(fitz, "get_tessdata"):
            return bool(fitz.get_tessdata())
        return bool(os.environ.get("TESSDATA_PREFIX"))
    except Exception:
        return False

# ----------------------------------------------------------------------------- corpus bookkeeping

def scan(src: Path, out: Path):
    files, others = [], Counter()
    out_key = os.path.normcase(str(out))
    for root, dirs, names in os.walk(src):
        keep = []
        for d in dirs:
            full = os.path.normcase(os.path.join(root, d))
            if d.lower() in SKIP_DIRS or full == out_key or full.startswith(out_key + os.sep):
                continue
            keep.append(d)
        dirs[:] = sorted(keep)
        for name in names:
            ext = os.path.splitext(name)[1].lower()
            if ext in BOOK_EXTS:
                files.append(os.path.join(root, name))
            elif ext in OTHER_EBOOK_EXTS:
                others[ext] += 1
    return sorted(files, key=str.lower), others


CSV_COLS = ["title", "authors", "status", "type", "cite_style", "words", "est_tokens", "pages", "page_markers",
            "chunks", "year", "isbn", "folder", "primary", "detail"]


def save_manifest(out: Path, manifest: dict) -> None:
    recs = sorted(manifest.values(), key=lambda r: ((r.get("title") or "").lower(), r.get("sha256", "")))
    write_atomic(out / "manifest.jsonl", "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs))
    tmp = out / "manifest.csv.tmp"
    try:
        with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLS)
            for r in recs:
                writer.writerow(["; ".join(r.get(c) or []) if c == "authors" else r.get(c, "") for c in CSV_COLS])
        os.replace(tmp, out / "manifest.csv")
    except PermissionError:
        print("  (manifest.csv is open in another program, so it was not refreshed)")


def write_index(out: Path, manifest: dict, cfg: dict) -> None:
    recs = sorted(manifest.values(), key=lambda r: (r.get("title") or "").lower())
    counts = Counter(r.get("status") for r in recs)
    words = sum(r.get("words") or 0 for r in recs if r.get("status") in USABLE)
    lines = ["# Corpus index", "", f"Source: `{cfg.get('source', '')}`  ",
             f"Updated {now_iso()} by corpus.py {TOOL_VERSION}", "",
             f"{len(recs)} documents, {words:,} words of usable text (about {int(words * TOKENS_PER_WORD):,} tokens). "
             "By status: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()) + ".", ""]
    attention = [r for r in recs if r.get("status") != "ok" or r.get("missing_source")]
    if attention:
        lines += ["## Needs attention", "", "| Status | File | Detail |", "| --- | --- | --- |"]
        for r in attention:
            status = (r.get("status") or "") + (" (source file gone)" if r.get("missing_source") else "")
            lines.append(f"| {status} | {md_cell(r.get('primary'), 160)} | {md_cell(r.get('detail'))} |")
        lines.append("")
    lines += ["## Documents", "", "| Title | Authors | Type | Status | Words | Cite by | Folder |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in recs:
        lines.append(f"| {md_cell(r.get('title'))} | {md_cell('; '.join(r.get('authors') or []), 80)} | "
                     f"{r.get('type', '')} | {r.get('status', '')} | {r.get('words') or 0:,} | "
                     f"{r.get('cite_style', '')} | {md_cell(r.get('folder'), 90)} |")
    write_atomic(out / "index.md", "\n".join(lines) + "\n")


def print_status(out: Path, manifest: dict, cfg: dict) -> None:
    recs = list(manifest.values())
    counts = Counter(r.get("status") for r in recs)
    usable = [r for r in recs if r.get("status") in USABLE]
    words = sum(r.get("words") or 0 for r in usable)
    print(f"\nCorpus {out}")
    print(f"  {len(recs)} documents, {len(usable)} usable, {words:,} words (~{int(words * TOKENS_PER_WORD):,} tokens)")
    print("  status: " + ", ".join(f"{k} {v}" for k, v in counts.most_common()))
    styles = Counter(r.get("cite_style") for r in usable)
    if styles:
        print("  cite by: " + ", ".join(f"{k} {v}" for k, v in styles.most_common()))
    src, script = cfg.get("source", "SOURCE"), os.path.abspath(__file__)
    tips = []
    if counts.get("needs_ocr") or counts.get("partial"):
        tips.append(f'OCR pass (needs Tesseract): python "{script}" extract "{src}" "{out}" '
                    "--ocr auto --only needs_ocr,partial --workers 2 --timeout 7200")
    if counts.get("timeout") or counts.get("error"):
        tips.append(f'retry failures one at a time: python "{script}" extract "{src}" "{out}" '
                    "--retry-failed --workers 1 --timeout 3600")
    if counts.get("drm"):
        tips.append("DRM-protected EPUBs can't be extracted; use a DRM-free copy of those books")
    if counts.get("encrypted"):
        tips.append("password-protected PDFs need the password removed by their owner first")
    if counts.get("corrupt") or counts.get("empty"):
        tips.append("corrupt or empty files: re-download or re-copy them (details in index.md)")
    gone = sum(1 for r in recs if r.get("missing_source"))
    if gone:
        tips.append(f"{gone} documents are no longer in the source folder; their extractions are kept")
    for tip in tips:
        print("  next: " + tip)
    print(f"  details: {out / 'index.md'}")

# ----------------------------------------------------------------------------- commands

def cmd_extract(args) -> None:
    src, out = Path(args.source).expanduser().resolve(), Path(args.out).expanduser().resolve()
    if not src.is_dir():
        sys.exit(f"Source folder not found: {src}")
    (out / "docs").mkdir(parents=True, exist_ok=True)
    cfg = load_json(out / "corpus.json", {"created": now_iso()})
    cfg.update(source=str(src), tool_version=TOOL_VERSION, last_run=now_iso())
    write_atomic(out / "corpus.json", json.dumps(cfg, indent=1))

    files, others = scan(src, out)
    skipped = f"; not processed: {', '.join(f'{k} x{v}' for k, v in others.most_common())}" if others else ""
    print(f"{src}: {len(files)} PDF/EPUB files{skipped}")
    if import_pymupdf() is None:
        print("PyMuPDF is not installed, so PDFs use the slower pypdf fallback without OCR (pip install pymupdf)")
    ocr_ok = args.ocr != "off" and ocr_available()
    if args.ocr != "off":
        print("OCR: " + ("Tesseract language data found; image-only pages will be OCR'd" if ocr_ok
                         else "Tesseract not found; scanned PDFs will be flagged needs_ocr"))

    cache = load_json(out / "hashcache.json", {})
    sizes, to_hash = {}, []
    for f in files:
        try:
            st = os.stat(f)
        except OSError:
            continue
        sizes[f] = st.st_size
        cached = cache.get(os.path.normcase(f))
        if not (cached and cached[0] == st.st_size and cached[1] == st.st_mtime_ns):
            to_hash.append((f, st))
    if to_hash:
        print(f"hashing {len(to_hash)} new or changed files")
        with ThreadPoolExecutor(max_workers=8) as pool:
            for (f, st), digest in zip(to_hash, pool.map(lambda t: sha256_file(t[0]), to_hash)):
                if digest:
                    cache[os.path.normcase(f)] = [st.st_size, st.st_mtime_ns, digest]
        write_atomic(out / "hashcache.json", json.dumps(cache))
    groups = defaultdict(list)
    for f in files:
        cached = cache.get(os.path.normcase(f))
        if cached and f in sizes:
            groups[cached[2]].append(f)

    manifest = {r["sha256"]: r for r in iter_jsonl(out / "manifest.jsonl") if r.get("sha256")}
    only = {s.strip() for s in (args.only or "").split(",") if s.strip()}
    match = (args.match or "").lower()
    jobs = []
    for sha, paths in sorted(groups.items(), key=lambda kv: kv[1][0].lower()):
        paths.sort(key=str.lower)
        rec = manifest.get(sha)
        folder = (rec or {}).get("folder") or f"{slugify(Path(paths[0]).stem)}--{sha[:8]}"
        if rec is not None:
            rec.update(paths=paths, primary=paths[0])
            rec.pop("missing_source", None)
        if match and not any(match in p.lower() for p in paths):
            continue
        if only:
            need = rec is not None and rec.get("status") in only
        else:
            need = (args.force or rec is None or rec.get("tool_rev", 0) < TOOL_REV
                    or (args.retry_failed and rec.get("status") in FAILED)
                    or (rec.get("status") in USABLE and not (out / "docs" / folder / "full.md").exists()))
        if need:
            jobs.append({"sha256": sha, "paths": paths, "folder": folder, "docdir": str(out / "docs" / folder),
                         "bytes": sizes.get(paths[0]), "ocr": args.ocr, "ocr_available": ocr_ok,
                         "ocr_lang": args.ocr_lang, "ocr_dpi": args.ocr_dpi, "min_page_chars": args.min_page_chars,
                         "chunk_words": args.chunk_words, "pdf_sort": args.pdf_sort, "keep_headers": args.keep_headers})
    for sha, rec in manifest.items():
        if sha not in groups:
            rec["missing_source"] = True
    duplicates = sum(len(p) - 1 for p in groups.values())
    print(f"{len(groups)} unique documents ({duplicates} duplicate copies merged); {len(jobs)} to extract")
    if args.limit:
        jobs = jobs[: args.limit]
    if args.dry_run:
        for job in jobs[:500]:
            print("  would extract:", job["paths"][0])
        return
    save_manifest(out, manifest)

    if jobs:
        started, done, width = time.time(), 0, len(str(len(jobs)))
        pool = ThreadPoolExecutor(max_workers=max(1, args.workers))
        futures = [pool.submit(run_job, job, args.timeout) for job in jobs]
        try:
            for future in as_completed(futures):
                rec = future.result()
                manifest[rec["sha256"]] = rec
                done += 1
                eta = (time.time() - started) / done * (len(jobs) - done)
                print(f"[{done:>{width}}/{len(jobs)}] {rec['status']:<9} {rec.get('words') or 0:>9,} words  "
                      f"{(rec.get('title') or '')[:70]}  (eta {fmt_secs(eta)})", flush=True)
                if done % 10 == 0:
                    save_manifest(out, manifest)
        except KeyboardInterrupt:
            print("\nStopped. Progress is saved; run the same command again to continue.")
            pool.shutdown(wait=False, cancel_futures=True)
            save_manifest(out, manifest)
            write_index(out, manifest, cfg)
            sys.exit(130)
        pool.shutdown(wait=True)
        save_manifest(out, manifest)
    write_index(out, manifest, cfg)
    print_status(out, manifest, cfg)


def cmd_status(args) -> None:
    out = Path(args.out).expanduser().resolve()
    manifest = {r["sha256"]: r for r in iter_jsonl(out / "manifest.jsonl") if r.get("sha256")}
    if not manifest:
        sys.exit(f"No manifest in {out}; run extract first.")
    print_status(out, manifest, load_json(out / "corpus.json", {}))


def select_docs(out: Path, query):
    recs = [r for r in iter_jsonl(out / "manifest.jsonl") if r.get("folder") and (r.get("words") or 0) > 0]
    if query:
        q = fold(query)
        recs = [r for r in recs if q in fold(" ".join([r.get("title") or "", r.get("folder") or "", r.get("id") or "",
                                                         " ".join(r.get("authors") or [])]))]
    return [r for r in recs if (out / "docs" / r["folder"] / "paragraphs.jsonl").exists()]


def cmd_search(args) -> None:
    out = Path(args.out).expanduser().resolve()
    docs = select_docs(out, args.doc)
    if not docs:
        sys.exit("No extracted documents match." if args.doc else f"No extracted documents in {out}.")
    rx = re.compile(args.phrase, re.I) if args.regex else None
    needle = fold(squash(clean(args.phrase)))
    hits = 0
    for doc in docs:
        for rec in iter_jsonl(out / "docs" / doc["folder"] / "paragraphs.jsonl"):
            flat = rec.get("text", "").replace("\n", " ")
            if rx is not None:
                spans = [(m.start(), m.end()) for m in rx.finditer(flat)]
            else:
                hay = fold(flat)
                aligned = len(hay) == len(flat)
                spans, pos = [], hay.find(needle) if needle else -1
                while pos != -1:
                    spans.append((pos, pos + len(needle)) if aligned else (0, 0))
                    pos = hay.find(needle, pos + 1)
            for start, end in spans:
                page = page_at(rec, start)
                a, b = max(0, start - args.context), min(len(flat), end + args.context)
                snippet = ("..." if a else "") + flat[a:b] + ("..." if b < len(flat) else "")
                if args.json:
                    print(json.dumps({"doc": doc.get("id"), "title": doc.get("title"), "folder": doc["folder"],
                                      "page": page, "section": rec.get("sec"), "para": rec.get("i"),
                                      "cite_style": doc.get("cite_style"), "snippet": snippet}, ensure_ascii=False))
                else:
                    where = f"p. {page}" if page else (rec.get("sec") or "no page map")
                    sec = f" | {rec['sec']}" if page and rec.get("sec") else ""
                    print(f"{(doc.get('title') or '')[:70]} | {where}{sec} | para {rec.get('i')}\n    {snippet}\n")
                hits += 1
                if hits >= args.max:
                    if not args.json:
                        print(f"(stopped at --max {args.max})")
                    return
    if not args.json:
        print(f"{hits} hit(s) across {len(docs)} document(s)")


def _tokens(s: str):
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)*", fold(s))


def cmd_overlap(args) -> None:
    out = Path(args.out).expanduser().resolve()
    docs = select_docs(out, args.doc)
    if len(docs) != 1:
        listing = "\n  ".join(f"{d.get('title')} [{d.get('folder')}]" for d in docs[:25])
        sys.exit(f"--doc must match exactly one extracted document; it matched {len(docs)}"
                 + (f":\n  {listing}" if docs else ""))
    doc, n = docs[0], max(3, args.n)
    book = []
    for rec in iter_jsonl(out / "docs" / doc["folder"] / "paragraphs.jsonl"):
        book.extend(_tokens(rec.get("text", "")))
    grams = {hash(tuple(book[i:i + n])) for i in range(len(book) - n + 1)}
    with open(args.note, encoding="utf-8") as f:
        note = re.sub(r"\A---\n.*?\n---\n", "", f.read(), count=1, flags=re.S)
    words = _tokens(note)
    spans = []
    for i in range(len(words) - n + 1):
        if hash(tuple(words[i:i + n])) in grams:
            if spans and i <= spans[-1][1]:
                spans[-1][1] = i + n
            else:
                spans.append([i, i + n])
    runs = [s for s in spans if s[1] - s[0] >= args.min_words]
    shared = sum(e - s for s, e in runs)
    pct = 100.0 * shared / len(words) if words else 0.0
    print(f"{doc.get('title')}: {len(runs)} shared run(s) of {args.min_words}+ words; "
          f"{shared} of {len(words)} note words ({pct:.1f}%)")
    for s, e in runs:
        print(f"  [{e - s} words] {' '.join(words[s:e])}")


def cmd_worker(args) -> None:
    fitz = import_pymupdf()
    if fitz is not None:
        try:
            fitz.TOOLS.mupdf_display_errors(False)
            fitz.TOOLS.mupdf_display_warnings(False)
        except Exception:
            pass
    raw = args.job
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8") as f:
            raw = f.read()
    print("RESULT " + json.dumps(run_worker(json.loads(raw)), ensure_ascii=False))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="corpus.py",
                                 description="Turn a folder of PDFs and EPUBs into a page-cited text corpus.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="extract every PDF and EPUB under SOURCE into OUT (incremental)")
    e.add_argument("source")
    e.add_argument("out")
    e.add_argument("--workers", type=int, default=max(1, min(6, (os.cpu_count() or 2) - 1)),
                   help="files processed in parallel (default: CPU count minus one, at most 6)")
    e.add_argument("--timeout", type=int, default=1800, help="seconds allowed per file (default 1800)")
    e.add_argument("--ocr", choices=["off", "auto", "force"], default="auto",
                   help="auto (default): OCR image-only PDF pages when Tesseract is available")
    e.add_argument("--ocr-lang", default="eng", help="Tesseract language code(s), for example eng or eng+spa")
    e.add_argument("--ocr-dpi", type=int, default=300)
    e.add_argument("--chunk-words", type=int, default=12000,
                   help="target words per chunk file (default 12000, roughly 16k tokens)")
    e.add_argument("--min-page-chars", type=int, default=40,
                   help="a page with an image and fewer text characters than this counts as scanned")
    e.add_argument("--pdf-sort", action="store_true", help="sort PDF text blocks top to bottom (for messy layouts)")
    e.add_argument("--keep-headers", action="store_true", help="keep running headers and footers in PDFs")
    e.add_argument("--only", help="re-extract only documents whose status is in this comma list, e.g. needs_ocr,partial")
    e.add_argument("--match", help="only extract files whose path contains this text (case-insensitive)")
    e.add_argument("--retry-failed", action="store_true", help="also retry documents that errored or timed out")
    e.add_argument("--force", action="store_true", help="re-extract everything")
    e.add_argument("--limit", type=int, help="extract at most N documents in this run")
    e.add_argument("--dry-run", action="store_true", help="list what would be extracted and stop")
    e.set_defaults(func=cmd_extract)

    s = sub.add_parser("status", help="summarize an extracted corpus and suggest next steps")
    s.add_argument("out")
    s.set_defaults(func=cmd_status)

    q = sub.add_parser("search", help="find a phrase across the corpus with page or section locations")
    q.add_argument("out")
    q.add_argument("phrase")
    q.add_argument("--doc", help="only documents whose title, author, folder, or id contains this text")
    q.add_argument("--regex", action="store_true", help="treat PHRASE as a regular expression")
    q.add_argument("--context", type=int, default=160, help="characters of context on each side of a hit")
    q.add_argument("--max", type=int, default=50, help="stop after this many hits")
    q.add_argument("--json", action="store_true", help="print one JSON object per hit")
    q.set_defaults(func=cmd_search)

    o = sub.add_parser("overlap", help="list long verbatim runs a note shares with one document")
    o.add_argument("out")
    o.add_argument("note")
    o.add_argument("--doc", required=True)
    o.add_argument("--n", type=int, default=8, help="n-gram size (default 8)")
    o.add_argument("--min-words", type=int, default=8, help="report runs at least this long (default 8)")
    o.set_defaults(func=cmd_overlap)

    w = sub.add_parser("_worker")
    w.add_argument("job")
    w.set_defaults(func=cmd_worker)

    args = ap.parse_args(argv)
    try:
        args.func(args)
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)


if __name__ == "__main__":
    main()
