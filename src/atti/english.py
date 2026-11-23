"""Parse the Bureau of Experts official English translation PDF.

The PDF body contains the 2005 text as promulgated; all later amendments are
listed in an "Appendix: Amendments" section at the end.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from atti.textnorm import normalize_ws

# Running header ("Labor Law") at the top of each page and page number at the bottom,
# as emitted by pdfminer.six (pages separated by form feeds).
_PAGE_HEADER = re.compile(r"^\s*Labor Law[ \t]*\n")
_PAGE_FOOTER = re.compile(r"\n\s*\d+\s*$")
_ARTICLE_LINE = re.compile(r"(?m)^\s*Article (\d+)\s*$")
# Structural headings that may follow an article's last paragraph.
_STRUCTURAL = re.compile(
    r"(?m)^\s*(?:Part \d+:|Chapter \d+:|"
    r"(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth):)"
)
_LEADING_HEADING = re.compile(
    r"\s*(?:Part \d+:|Chapter \d+:|"
    r"(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth):)[^\n]*\n"
)
_APPENDIX = re.compile(r"(?m)^\s*Appendix\s*$")
_ART_REFS = re.compile(r"Articles?\s+((?:\d+(?:\s*bis)?(?:\s*\([\d.]+\))?(?:,?\s+and\s+|,\s*)?)+)")


@dataclass
class EnglishDocument:
    articles: dict[int, str]
    appendix_text: str
    appendix_article_refs: set[int] = field(default_factory=set)


def pages_to_text(pages: list[str]) -> str:
    return "\n".join(_PAGE_FOOTER.sub("", _PAGE_HEADER.sub("", p, count=1)) for p in pages)


def appendix_refs(appendix: str) -> set[int]:
    """Every article number mentioned anywhere in the amendments appendix.

    Deliberately over-inclusive: an article merely referenced by an amendment
    is treated as possibly affected.
    """
    refs: set[int] = set()
    for m in _ART_REFS.finditer(appendix):
        cleaned = re.sub(r"\([\d.]+\)", "", m.group(1))
        refs |= {int(x) for x in re.findall(r"\d+", cleaned)}
    return refs


def parse_text(full: str) -> EnglishDocument:
    parts_ = _APPENDIX.split(full, maxsplit=1)
    if len(parts_) != 2:
        raise ValueError("English PDF: amendments appendix not found")
    body, appendix = parts_
    chunks = _ARTICLE_LINE.split(body)
    articles: dict[int, str] = {}
    for i in range(1, len(chunks), 2):
        num = int(chunks[i])
        text = chunks[i + 1]
        # pdfminer may emit a section heading just *after* the "Article N" line.
        while (m := _LEADING_HEADING.match(text)) is not None:
            text = text[m.end():]
        text = _STRUCTURAL.split(text, maxsplit=1)[0]
        if num in articles:
            raise ValueError(f"English PDF: duplicate Article {num}")
        articles[num] = normalize_ws(text)
    return EnglishDocument(articles, appendix, appendix_refs(appendix))


def parse_pdf(path: Path) -> EnglishDocument:
    from pdfminer.high_level import extract_text

    return parse_text(pages_to_text(extract_text(str(path)).split("\f")))
