"""Build and verify the article-pair manifest.

Eligibility rule for an article pair (both conditions must hold):
  * Arabic page: exactly one non-"bis" article with that number, not marked
    ``changed-article`` (no amendment recorded by the BOE Arabic page);
  * English PDF: the article number is never referenced in the amendments
    appendix.
Under this rule both texts are the 2005 promulgated wording, which both
sources state is still the wording in force (no amendment through Royal
Decree M/44 of 1446/2/8 AH). Content equivalence is additionally checked by
manual review (``manifest/review.json``).
"""

from __future__ import annotations

import collections
import json
from dataclasses import dataclass
from pathlib import Path

from atti import arabic, english
from atti.sources import ARABIC, ENGLISH, sha256_bytes, sha256_text

MANIFEST_VERSION = 1


@dataclass(frozen=True)
class ArticlePair:
    article: int
    ar_heading: str
    ar_text: str
    en_text: str


class VerificationError(RuntimeError):
    pass


def load_sources(raw_dir: Path):
    ar_articles = arabic.parse_articles((raw_dir / ARABIC.filename).read_text(encoding="utf-8"))
    en_doc = english.parse_pdf(raw_dir / ENGLISH.filename)
    return ar_articles, en_doc


def eligible_pairs(ar_articles, en_doc) -> dict[int, ArticlePair]:
    counts = collections.Counter(a.number for a in ar_articles if not a.bis)
    pairs = {}
    for a in ar_articles:
        if a.bis or a.amended or counts[a.number] != 1:
            continue
        if a.number in en_doc.appendix_article_refs:
            continue
        en_text = en_doc.articles.get(a.number, "")
        if a.text and en_text:
            pairs[a.number] = ArticlePair(a.number, a.heading, a.text, en_text)
    return pairs


def build_manifest(raw_dir: Path, articles: list[int], review: dict, fetch_log: dict) -> dict:
    ar_articles, en_doc = load_sources(raw_dir)
    pairs = eligible_pairs(ar_articles, en_doc)
    missing = [n for n in articles if n not in pairs]
    if missing:
        raise VerificationError(f"articles not eligible (amended/ambiguous/empty): {missing}")
    unreviewed = [n for n in articles if str(n) not in review["articles"]]
    if unreviewed:
        raise VerificationError(f"articles lack a manual review note: {unreviewed}")
    ar_amended = sorted({a.number for a in ar_articles if a.amended})
    en_refs = sorted(en_doc.appendix_article_refs)
    entries = []
    for n in sorted(articles):
        p = pairs[n]
        entries.append({
            "id": f"KSA-LL-{n:03d}",
            "article": n,
            "ar_heading": p.ar_heading,
            "en_heading": f"Article {n}",
            "ar_sha256": sha256_text(p.ar_text),
            "en_sha256": sha256_text(p.en_text),
            "ar_chars": len(p.ar_text),
            "en_chars": len(p.en_text),
            "verification": {
                "ar_page_marks_amended": False,
                "en_appendix_references_article": False,
                "content_review": review["articles"][str(n)],
            },
        })
    return {
        "manifest_version": MANIFEST_VERSION,
        "law": {
            "name_en": "Labor Law",
            "name_ar": "نظام العمل",
            "instrument": "Royal Decree No. M/51 dated 1426/08/23 AH (2005-09-27)",
            "latest_amendment_in_both_sources": "Royal Decree No. M/44 dated 1446/02/08 AH (2024-08-12)",
        },
        "sources": {
            "ar": {
                "url": ARABIC.url,
                "publisher": "Bureau of Experts at the Council of Ministers (laws.boe.gov.sa)",
                "format": "HTML; article body text only (amendment pop-ups excluded)",
                "retrieved_at_utc": fetch_log["ar"]["retrieved_at_utc"],
                "page_sha256_at_curation": fetch_log["ar"]["sha256"],
                "page_sha256_note": "informational only: the page embeds a live view counter; per-article text hashes are authoritative",
            },
            "en": {
                "url": ENGLISH.url,
                "publisher": "Bureau of Experts, Official Translation Department",
                "format": "PDF (69 pages, created 2025-05-08); body = 2005 text, amendments in appendix",
                "retrieved_at_utc": fetch_log["en"]["retrieved_at_utc"],
                "pdf_sha256": sha256_bytes((raw_dir / ENGLISH.filename).read_bytes()),
            },
        },
        "extraction": {
            "normalization": "every whitespace run (incl. line wraps, <br>, NBSP) -> one ASCII space; strip ends; no other changes",
            "ar": "HTML tags removed, entities unescaped",
            "en": "pdfminer.six text, running page header/footer and section headings removed",
        },
        "selection_rule": [
            "Arabic page: exactly one non-bis article with this number, not marked changed-article",
            "English PDF: article number never referenced in the amendments appendix",
            "Both texts nonempty; manual content review recorded in manifest/review.json",
            "Picked to span short to long articles across different Parts of the Law",
        ],
        "audit": {
            "ar_articles_marked_amended": ar_amended,
            "en_appendix_article_refs": en_refs,
            "disagreements_en_only": sorted(set(en_refs) - set(ar_amended)),
            "disagreements_ar_only": sorted(set(ar_amended) - set(en_refs)),
        },
        "articles": entries,
    }


def verify(manifest: dict, raw_dir: Path) -> list[ArticlePair]:
    """Re-extract every manifest article and check it is unchanged and eligible."""
    pdf_hash = sha256_bytes((raw_dir / ENGLISH.filename).read_bytes())
    if pdf_hash != manifest["sources"]["en"]["pdf_sha256"]:
        raise VerificationError(
            f"English PDF changed: {pdf_hash} != {manifest['sources']['en']['pdf_sha256']}"
        )
    ar_articles, en_doc = load_sources(raw_dir)
    pairs = eligible_pairs(ar_articles, en_doc)
    out = []
    for e in manifest["articles"]:
        n = e["article"]
        if n not in pairs:
            raise VerificationError(f"Article {n} is no longer eligible (amendment recorded?)")
        p = pairs[n]
        if p.ar_heading != e["ar_heading"]:
            raise VerificationError(f"Article {n}: Arabic heading changed")
        for lang, text in (("ar", p.ar_text), ("en", p.en_text)):
            if sha256_text(text) != e[f"{lang}_sha256"]:
                raise VerificationError(f"Article {n}: {lang} text hash mismatch")
        out.append(p)
    return out


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
