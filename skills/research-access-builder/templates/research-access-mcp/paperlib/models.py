"""Data models for paperlib."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Paper:
    title: str = ""
    authors: list = field(default_factory=list)
    year: Optional[int] = None
    venue: str = ""
    abstract: str = ""
    doi: str = ""
    citation_count: int = 0
    oa_status: str = ""
    pdf_url: str = ""
    urls: dict = field(default_factory=dict)
    source: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def normalize_doi(doi: str) -> str:
        if not doi:
            return ""
        d = doi.strip().lower()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if d.startswith(prefix):
                d = d[len(prefix):]
        return d.strip("/")

    @staticmethod
    def normalize_title(title: str) -> str:
        if not title:
            return ""
        import re
        t = title.lower()
        t = re.sub(r"[^a-z0-9\s]", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t
