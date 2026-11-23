"""Parse the Bureau of Experts Arabic Labor Law page into articles."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from atti.textnorm import normalize_ws

_UNITS = {
    "الأولى": 1, "الحادية": 1, "الثانية": 2, "الثالثة": 3, "الرابعة": 4,
    "الخامسة": 5, "السادسة": 6, "السابعة": 7, "الثامنة": 8, "التاسعة": 9,
    "العاشرة": 10,
}
_TENS = {
    "العشرون": 20, "العشرين": 20, "الثلاثون": 30, "الثلاثين": 30,
    "الأربعون": 40, "الأربعين": 40, "الخمسون": 50, "الخمسين": 50,
    "الستون": 60, "الستين": 60, "السبعون": 70, "السبعين": 70,
    "الثمانون": 80, "الثمانين": 80, "التسعون": 90, "التسعين": 90,
}
_HUNDREDS = {"المائة": 100, "المئة": 100, "المائتين": 200, "المئتين": 200, "المئتان": 200, "المائتان": 200}


def parse_ordinal(heading: str) -> tuple[int, bool] | None:
    """Convert an Arabic article heading to ``(number, is_bis)``.

    Returns ``None`` for headings that are not a single article ordinal
    (e.g. chapter titles or renumbering annotations).
    """
    if "حالياً" in heading or "سابقاً" in heading:
        return None
    s = re.sub(r"[():]", " ", heading)
    words = s.split()
    if words and words[0] == "المادة":
        words = words[1:]
    if not words:
        return None
    bis = False
    total = 0
    seen = False
    for w in words:
        if w == "مكرر":
            bis = True
            continue
        if w == "بعد":
            continue
        if w.startswith("و") and w[1:] in _TENS:
            w = w[1:]
        if w in _UNITS:
            total += _UNITS[w]
        elif w == "عشرة":
            total += 10
        elif w in _TENS:
            total += _TENS[w]
        elif w in _HUNDREDS:
            total += _HUNDREDS[w]
        else:
            return None
        seen = True
    return (total, bis) if seen else None


@dataclass(frozen=True)
class ArabicArticle:
    number: int
    bis: bool
    heading: str
    amended: bool  # page marks the article with class "changed-article"
    text: str
    part: int = 0  # 1-based Part (الباب) of the Law, by order of headings on the page


_ITEM_SPLIT = re.compile(r'<div class="article_item no_alternate ?')
_HEADING = re.compile(r'<h3 class="center">(.*?)</h3>', re.S)
_PART_HEADING = re.compile(r'<h3 class="center">\s*الباب')
_BODY = re.compile(r'<p><div class="HTMLContainer">(.*?)</div></p>', re.S)


def _html_to_text(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", fragment)
    text = re.sub(r"<[^>]+>", "", text)
    return normalize_ws(html.unescape(text))


def parse_articles(page_html: str) -> list[ArabicArticle]:
    out: list[ArabicArticle] = []
    chunks = _ITEM_SPLIT.split(page_html)
    part = len(_PART_HEADING.findall(chunks[0]))
    for item in chunks[1:]:
        # A block may open with a chapter title before the article heading.
        heading, parsed = "", None
        for h in _HEADING.findall(item):
            heading = normalize_ws(html.unescape(h))
            parsed = parse_ordinal(heading)
            if parsed is not None:
                break
        if parsed is not None:
            body = _BODY.search(item)
            out.append(
                ArabicArticle(
                    number=parsed[0],
                    bis=parsed[1],
                    heading=heading,
                    amended=item.startswith("changed-article"),
                    text=_html_to_text(body.group(1)) if body else "",
                    part=part,
                )
            )
        # Part headings follow the closing tag of the previous article block.
        part += len(_PART_HEADING.findall(item))
    return out
