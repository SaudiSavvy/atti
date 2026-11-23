"""HRSD (Ministry of Human Resources and Social Development) Labor Law sources.

Architecture (verified against the live site, 2026-11-23):
  * English: server-rendered HTML (Next.js front end over Drupal). An index
    page links 16 Part pages; each Part page lists articles as
    ``<h4>Article N:</h4>`` followed by ``<p>``/``<ol>`` siblings. No
    JavaScript rendering is needed; no public JSON endpoint is exposed
    (``?_format=json`` redirects, ``/jsonapi`` is 404).
  * Arabic: consolidated PDF (68 pages, amendments through M/44). Each English
    Part page also declares an Arabic ``x-default`` alternate page, used here
    only as an independent cross-check of the PDF extraction.

Fetching: one request at a time, >= 2 s apart, exponential backoff on
429/5xx/transport errors, TLS verified against the OS trust store, and a
write-once cache with provenance (never overwritten).
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import re
import ssl
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin

from atti.arabic import parse_ordinal
from atti.sources import NetworkError, sha256_bytes
from atti.textnorm import normalize_ws

BASE = "https://www.hrsd.gov.sa"
EN_INDEX_URL = BASE + "/en/knowledge-centre/%D9%86%D8%B8%D8%A7%D9%85-%D8%A7%D9%84%D8%B9%D9%85%D9%84"
AR_PDF_URL = BASE + "/sites/default/files/2025-11/labor-law.pdf"
USER_AGENT = "atti-benchmark/0.2 (research; tokenizer measurement)"
MIN_INTERVAL_S = 2.0
RETRIES = 4


# ----------------------------------------------------------------------------- fetching

class Fetcher:
    """Polite, cached HTTP GET. ``client`` is injectable for tests."""

    def __init__(self, cache_dir: Path, client=None, sleep=time.sleep, clock=time.monotonic):
        self.cache_dir = cache_dir
        self._client = client
        self._sleep, self._clock = sleep, clock
        self._last = None

    def _http(self):
        if self._client is None:
            import httpx
            import truststore

            self._client = httpx.Client(
                headers={"User-Agent": USER_AGENT},
                timeout=httpx.Timeout(60.0, connect=20.0),
                follow_redirects=True,
                verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            )
        return self._client

    def _get(self, url: str):
        import httpx

        for attempt in range(RETRIES + 1):
            if self._last is not None:
                wait = MIN_INTERVAL_S - (self._clock() - self._last)
                if wait > 0:
                    self._sleep(wait)
            self._last = self._clock()
            try:
                resp = self._http().get(url)
            except httpx.TransportError as exc:
                err = f"{url}: {type(exc).__name__}: {exc}"
            else:
                if resp.status_code == 200:
                    return resp
                if resp.status_code not in (429, 500, 502, 503, 504):
                    raise NetworkError(f"{url}: HTTP {resp.status_code}")
                err = f"{url}: HTTP {resp.status_code}"
            if attempt < RETRIES:
                self._sleep(2 ** attempt)
        raise NetworkError(f"{err} (after {RETRIES} retries)")

    def fetch(self, key: str, url: str) -> Path:
        """Return the cached file for ``key``; download only if absent."""
        path = self.cache_dir / key
        if path.exists():
            return path
        resp = self._get(url)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".part")
        tmp.write_bytes(resp.content)
        tmp.replace(path)
        prov_path = self.cache_dir / "provenance.json"
        prov = json.loads(prov_path.read_text()) if prov_path.exists() else {}
        prov[key] = {
            "url": url,
            "final_url": str(resp.url),
            "status": resp.status_code,
            "content_type": resp.headers.get("content-type"),
            "last_modified_header": resp.headers.get("last-modified"),
            "etag": resp.headers.get("etag"),
            "sha256": sha256_bytes(resp.content),
            "bytes": len(resp.content),
            "retrieved_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }
        prov_path.write_text(json.dumps(dict(sorted(prov.items())), indent=2, ensure_ascii=False) + "\n")
        return path


# ----------------------------------------------------------------------------- HTML

@dataclass(frozen=True)
class PartLink:
    part: int
    title: str
    url: str


_PART_WORDS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
               "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen"]


def _part_number(label: str) -> int | None:
    w = label.lower().replace("part", "").strip()
    for i, word in enumerate(_PART_WORDS, 1):
        if w in (word, word + "th", word.rstrip("e") + "th"):
            return i
    return None


def discover_parts(index_html: str) -> list[PartLink]:
    """Part links from the index cards: ``<h2>Part One</h2>`` ... ``<a href>``."""
    from selectolax.parser import HTMLParser

    out = []
    for card in HTMLParser(index_html).css("div.card"):
        h2 = card.css_first("h2")
        a = card.css_first("a[href]")
        if not h2 or not a:
            continue
        label = " ".join(h2.text().split())
        n = _part_number(label)
        if n is None:
            continue
        out.append(PartLink(n, " ".join(a.text().split()), urljoin(BASE, a.attributes["href"])))
    nums = [p.part for p in out]
    if sorted(nums) != list(range(1, 17)) or len(nums) != 16:
        raise ValueError(f"expected Parts 1..16 exactly once on the index page, found {nums}")
    return sorted(out, key=lambda p: p.part)


def arabic_alternate(part_html: str) -> str:
    m = re.search(r'hrefLang="x-default" href="([^"]+)"', part_html)
    if not m:
        raise ValueError("Part page has no Arabic x-default alternate link")
    return m.group(1)


@dataclass
class HtmlArticle:
    label: str          # heading text as published, e.g. "Article 79 bis:"
    number: int | None  # None if the heading could not be parsed
    bis: bool
    text: str           # extraction-cleaned (whitespace-normalized) article body
    position: int       # order on the page


# The bis marker may precede the colon ("Article 11 Bis:", "Article 131 (Bis):") or follow it
# ("Article 79:(Bis)", as published for Article 79 bis in Part 5).
_EN_HEADING = re.compile(r"^Article\s*\(?\s*(\d+)\s*\)?\s*(?:\(?\s*(bis|repeated)\s*\)?)?\s*:?\s*"
                         r"(?:\(\s*(bis|repeated)\s*\)\s*:?)?\s*(.*)$", re.I | re.S)
_AR_HEADING = re.compile(r"^(?:\(\s*)?(المادة\b[^:]*?|\(?\s*[^\s:]+[^:]*?مكرر\s*\)?)\s*:\s*(.*)$", re.S)
# Sub-section titles that some Part pages publish as plain paragraphs, not headings.
_SECTION_TITLE = re.compile(
    r"^(?:(?:First|Second|Third|Fourth|Fifth|Sixth)\s*[:\-–]|(?:Section|Chapter|Part)\s+\w+\s*$|"
    r"(?:أولاً|أولًا|ثانياً|ثانيًا|ثالثاً|ثالثًا|رابعاً|رابعًا)\s*[-–:]|(?:الفصل|الباب)\s)", re.I)
_BLOCK = {"p", "ol", "ul", "h1", "h2", "h3", "h4", "h5", "h6", "table", "blockquote"}
_HEAD = {"h1", "h2", "h3", "h4", "h5", "h6"}
_ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]


def _inline_text(node) -> str:
    parts = []
    for child in node.iter(include_text=True):
        if child.tag == "-text":
            parts.append(child.text_content or "")
        elif child.tag in ("br",):
            parts.append(" ")
        elif child.tag in ("ol", "ul"):
            continue
        else:
            parts.append(" " + _inline_text(child) + " " if child.tag in ("p", "div", "li") else _inline_text(child))
    return "".join(parts)


def _list_label(kind: str, i: int) -> str:
    if kind == "a":
        return chr(ord("a") + i - 1)
    if kind == "A":
        return chr(ord("A") + i - 1)
    if kind in ("i", "I"):
        r = _ROMAN[i - 1]
        return r if kind == "i" else r.upper()
    return str(i)


def _render_list(node) -> str:
    """Browsers render <ol> numbers; reconstruct them as 'N.' so clause numbering is kept."""
    ordered = node.tag == "ol"
    start = int(node.attributes.get("start") or 1) if ordered else 1
    kind = node.attributes.get("type") or "1"
    items, i = [], start
    for li in node.iter():
        if li.tag != "li":
            continue
        body = _inline_text(li)
        nested = " ".join(_render_list(c) for c in li.iter() if c.tag in ("ol", "ul"))
        label = f"{_list_label(kind, i)}. " if ordered else ""
        items.append(f"{label}{body} {nested}")
        i += 1
    return " ".join(items)


def _content_root(main):
    """Deepest element containing every article heading (the article body field)."""
    heads = [n for n in main.css("h1,h2,h3,h4,h5,h6,p") if _is_article_heading(n.text())]
    if not heads:
        raise ValueError("no article headings found on page")
    chain = []
    node = heads[0]
    while node is not None:
        chain.append(node)
        node = node.parent
    for anc in chain[1:]:
        if all(_has_ancestor(h, anc) for h in heads):
            return anc
    return main


def _has_ancestor(node, anc) -> bool:
    n = node.parent
    while n is not None:
        if n.mem_id == anc.mem_id:
            return True
        n = n.parent
    return False


def _is_article_heading(text: str) -> bool:
    t = " ".join((text or "").split())
    return bool(re.match(r"^Article\s*\(?\s*\d+", t) or re.match(r"^\(?\s*المادة\s", t)
                or re.match(r"^\(\s*[^\s()]+[^()]*مكرر\s*\)", t))


def parse_html_articles(page_html: str, lang: str) -> list[HtmlArticle]:
    """Articles on one Part page, in page order. Structural headings end an article."""
    from selectolax.parser import HTMLParser

    tree = HTMLParser(page_html)
    root = _content_root(tree.css_first("main") or tree.body)
    blocks = []
    for node in root.traverse(include_text=False):
        if node.tag not in _BLOCK:
            continue
        anc, nested = node.parent, False
        while anc is not None and anc.mem_id != root.mem_id:
            if anc.tag in _BLOCK or anc.tag == "li":
                nested = True
                break
            anc = anc.parent
        if not nested:
            blocks.append(node)
    arts: list[HtmlArticle] = []
    current = None
    for node in blocks:
        text = normalize_ws(_render_list(node) if node.tag in ("ol", "ul") else _inline_text(node))
        if not text:
            continue
        if _is_article_heading(text) and (node.tag in _HEAD or re.match(r"^(Article\s*\(?\s*\d+[^:]{0,20}:|\(?\s*المادة[^:]{0,60}:)", text)):
            label, number, bis, rest = _split_heading(text, lang)
            current = HtmlArticle(label, number, bis, rest, len(arts))
            arts.append(current)
        elif node.tag in _HEAD or (_SECTION_TITLE.match(text) and len(text) < 80):
            current = None  # section / chapter heading: not article content
        elif current is not None:
            current.text = normalize_ws(f"{current.text} {text}")
    return arts


def _split_heading(text: str, lang: str):
    if lang == "en":
        m = _EN_HEADING.match(text)
        if not m:
            return text, None, False, ""
        label = text[: len(text) - len(m.group(4))].strip()
        return label, int(m.group(1)), bool(m.group(2) or m.group(3)), m.group(4).strip()
    head, _, rest = text.partition(":")
    parsed = parse_ordinal(_ar_variants(head))
    return head.strip() + ":", (parsed[0] if parsed else None), (parsed[1] if parsed else False), rest.strip()


def _ar_variants(s: str) -> str:
    """Spelling variants seen in headings (hamza, alif maqsura) -> the forms parse_ordinal knows."""
    s = s.replace("(", " ").replace(")", " ")
    for a, b in (("الاولى", "الأولى"), ("الاربع", "الأربع"), ("المئة", "المائة"), ("المئتين", "المائتين")):
        s = s.replace(a, b)
    s = re.sub(r"\s+", " ", s)
    if "مكرر" in s and not s.strip().startswith("المادة"):
        s = "المادة " + s
    return s


# ----------------------------------------------------------------------------- Arabic PDF

ARABIC_PRESENTATION = re.compile("[ﭐ-﷿ﹰ-﻿]")
TATWEEL = "ـ"


def cleanup_arabic_pdf_text(s: str) -> str:
    """Extraction cleanup for PDF text (layout artefacts only, applied before token counting):
    1. presentation-form code points -> base letters (NFKC on those code points only);
    2. kashida/tatweel used for line justification removed;
    3. mirrored parentheses/brackets in visual-order glyph runs swapped back.
    """
    s = ARABIC_PRESENTATION.sub(lambda m: unicodedata.normalize("NFKC", m.group(0)), s)
    s = s.replace(TATWEEL, "")
    return s.translate(str.maketrans({"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{"}))


@dataclass
class PdfArticle:
    label: str
    number: int | None
    bis: bool
    text: str
    pages: list[int] = field(default_factory=list)
    part: int = 0
    footnote_refs: list[str] = field(default_factory=list)
    repealed_marker: bool = False


HEADING_SIZE, BODY_SIZE, REPEALED_SIZE = 13.9, 12.0, 10.6
FOOTNOTE_MAX_SIZE = 9.0
STRUCTURE_MIN_SIZE = 16.0
PART_TITLE_MIN_SIZE = 30.0  # Part divider pages ("الباب الأول" at 36 pt); the TOC uses 16 pt


@dataclass(frozen=True)
class PdfLine:
    page: int
    y: float
    size: float          # largest span size on the line
    text: str            # spans > 8.5 pt (drops superscript footnote markers), raw
    marker: str          # 8.4 pt footnote marker digits on the line, if any


def line_text(spans: list[dict]) -> tuple[float, str, str]:
    """(size, text, footnote marker) of one PDF line from its spans (pure; unit-tested).

    Body lines drop superscript footnote markers (< 8.5 pt) but keep whitespace-only spans
    whatever their size: the PDF sets some inter-word spaces in a smaller font (Article 33),
    and dropping them joined two words (fixed 2026-11-24).
    """
    visible = [s for s in spans if s["text"].strip()]
    size = max(round(s["size"], 1) for s in visible)
    if size < FOOTNOTE_MAX_SIZE:
        text = "".join(s["text"] for s in spans)
    else:
        text = "".join(s["text"] for s in spans if round(s["size"], 1) > 8.5 or not s["text"].strip())
    marker = "".join(s["text"] for s in visible if round(s["size"], 1) == 8.4).strip()
    return size, text, marker


def read_pdf_lines(path: Path) -> list[PdfLine]:
    """PyMuPDF line reader (blocks top-to-bottom; lines in PyMuPDF's logical order)."""
    import fitz

    out = []
    with fitz.open(path) as doc:
        for pno, page in enumerate(doc, 1):
            for line in _reading_order(page):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                size, text, marker = line_text(line["spans"])
                out.append(PdfLine(pno, line["bbox"][1], size, text, marker))
    return out


def articles_from_lines(lines: list[PdfLine]) -> tuple[list[PdfArticle], dict[int, str]]:
    """Segment classified lines into articles (pure function; see parse_pdf_articles).

    Sizes established from the document's font histogram: 13.9 article
    headings, 12.0 body, 10.6 "(repealed)" marker, < 9 footnotes, >= 16 titles
    and page numbers, >= 30 Part divider titles. Lines before the first Part
    divider (cover, table of contents) are ignored.
    """
    arts: list[PdfArticle] = []
    footnotes: dict[int, str] = {}
    current: PdfArticle | None = None
    part, started = 0, False
    fn_by_page = collections.defaultdict(list)
    for ln in lines:
        if ln.size < FOOTNOTE_MAX_SIZE:
            fn_by_page[ln.page].append((ln.y, ln.text))
            continue
        clean = cleanup_arabic_pdf_text(ln.text)
        if ln.size >= STRUCTURE_MIN_SIZE:
            if ln.size >= PART_TITLE_MIN_SIZE and re.match(r"^\s*الباب\s", clean):
                started = True
                part += 1
                current = None
            elif not re.fullmatch(r"\s*\d+\s*", clean):
                current = None  # chapter / section title
            continue
        if not started:
            continue
        if ln.size == HEADING_SIZE and re.match(r"^\s*\(?\s*المادة|^\s*\(\s*\S+.*مكرر", clean):
            head, _, rest = clean.partition(":")
            parsed = parse_ordinal(_ar_variants(head))
            current = PdfArticle(head.strip() + ":", parsed[0] if parsed else None,
                                 parsed[1] if parsed else False, rest, [ln.page], part,
                                 [ln.marker] if ln.marker else [])
            arts.append(current)
            continue
        if re.fullmatch(r"\s*\d+\s*", clean) and ln.y > 740:
            continue  # page number
        if current is None:
            continue  # sub-section titles between articles
        if ln.page not in current.pages:
            current.pages.append(ln.page)
        if ln.size == REPEALED_SIZE and "ملغ" in clean:
            current.repealed_marker = True
        current.text += " " + clean
    for page_lines in fn_by_page.values():
        for num, txt in _footnotes(page_lines):
            footnotes[num] = txt
    for a in arts:
        a.text = normalize_ws(a.text)
    return arts, footnotes


def parse_pdf_articles(path: Path) -> tuple[list[PdfArticle], dict[int, str]]:
    """Return (articles in document order, footnotes {number: text})."""
    return articles_from_lines(read_pdf_lines(path))


def _reading_order(page) -> list[dict]:
    """Lines in reading order: blocks sorted top-to-bottom, lines within a block
    kept in PyMuPDF's order (which is the logical RTL order). PyMuPDF can emit a
    page's header block after its body (page 5), which would otherwise end the
    article that continues onto the next page.
    """
    blocks = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0]
    blocks.sort(key=lambda b: b["bbox"][1])
    return [l for b in blocks for l in b["lines"]]


def _footnotes(lines):
    """Group footnote lines (y-sorted) into {number: text}; readable (HRSDGov) notes only."""
    out, cur, buf = [], None, []
    for _, t in sorted(lines):
        t = cleanup_arabic_pdf_text(t).strip()
        m = re.match(r"^(\d+)\s*(-.*)?$", t)
        if m and (m.group(2) or len(t) <= 3):
            if cur is not None:
                out.append((cur, normalize_ws(" ".join(buf))))
            cur, buf = int(m.group(1)), [m.group(2) or ""]
        elif cur is not None:
            buf.append(t)
    if cur is not None:
        out.append((cur, normalize_ws(" ".join(buf))))
    return out


# ----------------------------------------------------------------------------- integrity

def numbering_report(articles) -> dict:
    """Missing, duplicated and out-of-order article identifiers (never repaired)."""
    seq = [(a.number, a.bis) for a in articles if a.number is not None]
    seen, dups, reordered = set(), [], []
    prev = (0, False)
    for key in seq:
        if key in seen:
            dups.append(key[0] if not key[1] else f"{key[0]} bis")
        seen.add(key)
        if key < prev:
            reordered.append(key[0] if not key[1] else f"{key[0]} bis")
        prev = max(prev, key)
    plain = {n for n, b in seq if not b}
    return {
        "count": len(seq),
        "unparsed_headings": [a.label for a in articles if a.number is None],
        "missing": [n for n in range(1, 246) if n not in plain],
        "duplicates": dups,
        "out_of_order": reordered,
        "bis": sorted(n for n, b in seq if b),
    }


# ----------------------------------------------------------------------------- source set

def fetch_source_set(fetcher: Fetcher) -> dict:
    """Fetch (or reuse cached) index, 16 English Parts, 16 Arabic alternates and the PDF."""
    index = fetcher.fetch("en/index.html", EN_INDEX_URL).read_text(encoding="utf-8")
    parts = discover_parts(index)
    out = {"parts": [], "pdf": fetcher.fetch("ar/labor-law.pdf", AR_PDF_URL)}
    for p in parts:
        en_path = fetcher.fetch(f"en/part-{p.part:02d}.html", p.url)
        ar_url = arabic_alternate(en_path.read_text(encoding="utf-8"))
        ar_path = fetcher.fetch(f"ar_html/part-{p.part:02d}.html", ar_url)
        out["parts"].append({"part": p.part, "title": p.title, "en_url": p.url, "en_path": en_path,
                             "ar_html_url": ar_url, "ar_html_path": ar_path})
    return out
