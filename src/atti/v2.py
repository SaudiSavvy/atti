"""current_law_v2: consolidated Saudi Labor Law (HRSD), Arabic PDF + English HTML.

Pipeline: cached sources (data/raw_v2) -> per-article records for all 249
Arabic articles -> eligibility with explicit reasons -> automated pair checks
-> deterministic, token-blind selection -> manifest -> measurement -> report.

Article keys are strings: "4", "79bis". Historical corpora (pilot,
expanded_v1) do not use this module.
"""

from __future__ import annotations

import collections
import hashlib
import json
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from atti import hrsd, metrics, tokenization
from atti.arabic import parse_ordinal
from atti.sources import sha256_bytes, sha256_text

CORPUS = "current_law_v2"
SEED = "atti-current-law-v2"
TARGET = 100
MIN_PER_PART = 2
RAW = Path("data") / "raw_v2"

# Human-readable record of the source decisions (see reports/current_law_v2_sources.md).
SOURCE_AUTHORITY = {
    "arabic": {
        "publisher": "Ministry of Human Resources and Social Development (HRSD)",
        "url": hrsd.AR_PDF_URL,
        "document": "نظام العمل, consolidated text; cover lists Royal Decree M/51 (1426/8/23) and amendments "
                    "M/24, M/1, M/46, M/14, M/134, M/5, M/44 (1446/2/8)",
        "pdf_metadata": "68 pages; created 2025-07-14 (Quartz PDFContext); HTTP Last-Modified 2025-11-03 "
                        "(a file date, not a legislative date)",
        "user_attachment": "~/Downloads/labor-law.pdf verified byte-identical (SHA-256) to the ministry-hosted file",
    },
    "english": {
        "publisher": "HRSD, English knowledge-centre pages (16 Parts)",
        "url": hrsd.EN_INDEX_URL,
        "translation_status": "published by the competent ministry; the pages carry no statement that the "
                              "translation is official or which version it reflects; HTTP Last-Modified "
                              "headers are CDN render dates, not legislative dates",
        "version_evidence": "contains M/44 provisions (Art. 2 Assignment/Resignation, Art. 75 30/60-day "
                            "notice, Arts. 11 bis, 79 bis, 131 bis, 229 bis), M/134 (Art. 3) and M/5 "
                            "(Art. 186); repealed-article set matches the Arabic PDF except where the "
                            "English page mislabels article numbers",
    },
    "cross_check": {
        "arabic_html": "HRSD Arabic pages (x-default alternates of each English Part page), used only to "
                       "confirm the PDF extraction",
        "boe_register": "laws.boe.gov.sa Labor Law page re-fetched 2026-11-23: latest amending instrument "
                        "M/44 (1446/2/8), in force from 1446/8/20",
        "official_gazette": "Umm Al-Qura entries p=25377 (Council of Ministers Decision 117, 02/02/1446) "
                            "and p=25379 (amended text), both published 2024-08-23: the M/44 package; "
                            "entry into force 180 days after publication",
        "newer_amendments": "none found in the BOE register or the official gazette; a secondary website's "
                            "claim of a 1447 H decree could not be substantiated",
    },
}


def key_of(number: int, bis: bool) -> str:
    return f"{number}bis" if bis else str(number)


def sort_key(k: str) -> tuple[int, int]:
    return (int(k.rstrip("bis")), 1 if k.endswith("bis") else 0)


# ----------------------------------------------------------------------------- loading

@dataclass
class Record:
    key: str
    part: int
    ar_heading: str
    ar_text: str                 # PDF text after extraction cleanup + whitespace normalization
    ar_pages: list[int]
    ar_html_text: str | None     # independent Arabic rendering (cross-check only)
    en_labels: list[str]         # English headings carrying this number (several => anomaly)
    en_text: str | None
    en_url: str | None
    ar_html_url: str | None
    eligible: bool = False
    reasons: list[str] = field(default_factory=list)


def _repealed(text: str, lang: str) -> bool:
    if lang == "ar":
        return bool(re.fullmatch(r"\(?\s*ملغ[اى]ة\s*\)?\s*\.?", text))
    return bool(re.fullmatch(r"\(?\s*Repealed\s*\)?\s*\.?", text, re.I))


def load(raw: Path = RAW) -> dict:
    prov = json.loads((raw / "provenance.json").read_text())
    parts = hrsd.discover_parts((raw / "en/index.html").read_text(encoding="utf-8"))
    en, ar_html, en_order = collections.defaultdict(list), {}, []
    urls = {}
    for p in parts:
        en_html = (raw / f"en/part-{p.part:02d}.html").read_text(encoding="utf-8")
        ar_page = (raw / f"ar_html/part-{p.part:02d}.html").read_text(encoding="utf-8")
        urls[p.part] = (prov[f"en/part-{p.part:02d}.html"]["final_url"], prov[f"ar_html/part-{p.part:02d}.html"]["final_url"])
        for a in hrsd.parse_html_articles(en_html, "en"):
            en[key_of(a.number, a.bis)].append((p.part, a))
            en_order.append(a)
        for a in hrsd.parse_html_articles(ar_page, "ar"):
            ar_html[key_of(a.number, a.bis)] = a.text
    pdf, footnotes = hrsd.parse_pdf_articles(raw / "ar/labor-law.pdf")
    return {"prov": prov, "parts": parts, "en": en, "en_order": en_order, "ar_html": ar_html,
            "pdf": pdf, "footnotes": footnotes, "urls": urls}


def strip_html_layout(s: str) -> str:
    """HTML-only layout characters ignored in the PDF/HTML cross-check: tatweel and ZWNJ."""
    return s.replace("ـ", "").replace("‌", "")


def build_records(src: dict) -> tuple[dict[str, Record], dict]:
    """Every Arabic article with an eligibility decision and reasons. Nothing is repaired."""
    en, recs = src["en"], {}
    en_report = hrsd.numbering_report(src["en_order"])
    ar_report = hrsd.numbering_report(src["pdf"])
    anomalies = {
        "en_duplicate_labels": sorted({k for k, v in en.items() if len(v) > 1}, key=sort_key),
        "en_missing": [str(n) for n in en_report["missing"]],
        "en_bis_found": [f"{n}bis" for n in en_report["bis"]],
        "ar_pdf_numbering": {k: ar_report[k] for k in ("missing", "duplicates", "out_of_order", "bis")},
    }
    for a in src["pdf"]:
        k = key_of(a.number, a.bis)
        ens = en.get(k, [])
        en_text = ens[0][1].text if len(ens) == 1 else None
        en_url, ar_url = src["urls"][a.part]
        r = Record(k, a.part, a.label, a.text, a.pages, src["ar_html"].get(k),
                   [x.label for _, x in ens], en_text, en_url if ens else None, ar_url)
        if _repealed(a.text, "ar") or a.repealed_marker:
            r.reasons.append("REPEALED: Arabic text is '(ملغاة)'")
        if not ens:
            r.reasons.append("MISSING_SOURCE: no English article carries this number")
        elif len(ens) > 1:
            r.reasons.append(f"NUMBERING: English label used {len(ens)} times on the HRSD pages "
                             "(not repaired)")
        elif _repealed(ens[0][1].text, "en") and not r.reasons:
            r.reasons.append("VERSION_MISMATCH: English repealed but Arabic not")
        if r.ar_html_text is None:
            r.reasons.append("AR_UNCONFIRMED: no Arabic HTML counterpart for cross-check")
        elif strip_html_layout(r.ar_html_text) != r.ar_text:
            r.reasons.append("AR_UNCONFIRMED: PDF extraction differs from the independent Arabic HTML "
                             "rendering (extraction artefact or edition difference; not repaired)")
        if ens and len(ens) == 1 and ens[0][0] != a.part:
            r.reasons.append(f"NUMBERING: English article is in Part {ens[0][0]}, Arabic in Part {a.part}")
        r.eligible = not r.reasons
        recs[k] = r
    return recs, anomalies


# ----------------------------------------------------------------------------- automated checks

_AR_UNITS = {"واحد": 1, "واحدة": 1, "اثنان": 2, "اثنين": 2, "اثنتين": 2, "اثنتان": 2, "اثني": 2, "اثنتي": 2, "إثنتي": 2, "إثني": 2, "إثنتين": 2, "إثنين": 2, "إثنان": 2,
             "ثلاث": 3, "ثلاثة": 3, "أربع": 4, "أربعة": 4, "خمس": 5, "خمسة": 5, "ست": 6, "ستة": 6,
             "سبع": 7, "سبعة": 7, "ثمان": 8, "ثماني": 8, "ثمانية": 8, "تسع": 9, "تسعة": 9,
             "عشر": 10, "عشرة": 10, "أحد": 1, "إحدى": 1}
_AR_ORD = {"الأول": 1, "الأولى": 1, "الحادي": 1, "الحادية": 1, "الثاني": 2, "الثانية": 2, "الثالث": 3,
           "الثالثة": 3, "الرابع": 4, "الرابعة": 4, "الخامس": 5, "الخامسة": 5, "السادس": 6, "السادسة": 6,
           "السابع": 7, "السابعة": 7, "الثامن": 8, "الثامنة": 8, "التاسع": 9, "التاسعة": 9,
           "العاشر": 10, "العاشرة": 10}
_AR_TENS = {"عشرين": 20, "عشرون": 20, "ثلاثين": 30, "ثلاثون": 30, "أربعين": 40, "أربعون": 40,
            "خمسين": 50, "خمسون": 50, "ستين": 60, "ستون": 60, "سبعين": 70, "سبعون": 70,
            "ثمانين": 80, "ثمانون": 80, "تسعين": 90, "تسعون": 90}
_AR_BIG = {"مائة": 100, "مئة": 100, "مائتين": 200, "مائتان": 200, "مئتين": 200, "ثلاثمائة": 300,
           "أربعمائة": 400, "خمسمائة": 500, "ستمائة": 600, "سبعمائة": 700, "ثمانمائة": 800,
           "تسعمائة": 900, "ألف": 1000, "ألفين": 2000, "ألفا": 1000, "آلاف": 1000}
_AR_FRAC = {"نصف": 0.5, "ثلث": 1 / 3, "ربع": 0.25, "ثلثي": 2 / 3, "خمس": 0.2}
_EN_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
             "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
             "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
             "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
             "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000, "half": 0.5,
             "quarter": 0.25, "third": 1 / 3}
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _strip_prefix(w: str) -> str:
    for pre in ("و", "ب", "ل", "ف"):
        if w.startswith(pre) and len(w) > 3 and w[1:] in {**_AR_UNITS, **_AR_TENS, **_AR_BIG}:
            return w[1:]
    return w


def ar_numbers(text: str) -> set[float]:
    """Numeric values in Arabic text: digits plus cardinal number words (approximate)."""
    t = text.translate(_AR_DIGITS)
    vals = {float(x.replace(",", "")) for x in re.findall(r"\d+(?:[.,]\d+)?", t)}
    words = re.findall(r"[ء-ي]+", re.sub(r"[ً-ْ]", "", t))
    i = 0
    while i < len(words):
        w = _strip_prefix(words[i])
        if w in _AR_FRAC and w != "خمس":
            vals.add(round(_AR_FRAC[w], 4))
        total, matched = 0, False
        if w in _AR_ORD and i + 1 < len(words) and words[i + 1] in ("عشر", "عشرة") and _AR_ORD[w] < 10:
            vals.add(float(_AR_ORD[w] + 10))
            i += 2
            continue
        while i < len(words):
            w = _strip_prefix(words[i])
            if w in _AR_UNITS:
                v = _AR_UNITS[w]
                if i + 1 < len(words) and words[i + 1] in ("عشر", "عشرة") and v < 10:
                    v += 10
                    i += 1
                total += v
            elif w in _AR_TENS:
                total += _AR_TENS[w]
            elif w in _AR_BIG:
                total = (total or 1) * _AR_BIG[w] if _AR_BIG[w] >= 1000 else total + _AR_BIG[w]
            else:
                break
            matched = True
            i += 1
        if matched:
            vals.add(float(total))
        else:
            i += 1
    return vals


def en_numbers(text: str) -> set[float]:
    vals = {float(x.replace(",", "")) for x in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text)}
    for segment in re.split(r"[^a-z\- ]+", text.lower()):  # punctuation ends a number phrase
        _en_words_to_values(re.findall(r"[a-z]+", segment.replace("-", " ")), vals)
    return vals


def _en_words_to_values(words: list[str], vals: set) -> None:
    i = 0
    while i < len(words):
        total, matched = 0, False
        while i < len(words) and (words[i] in _EN_WORDS or (matched and words[i] == "and"
                                  and i + 1 < len(words) and words[i + 1] in _EN_WORDS)):
            if words[i] == "and":
                i += 1
                continue
            v = _EN_WORDS[words[i]]
            if v < 1:
                vals.add(round(v, 4))
            elif v >= 100:
                total = (total or 1) * v
            else:
                total += v
            matched = True
            i += 1
        if matched and total:
            vals.add(float(total))
        if not matched:
            i += 1


def ar_refs(text: str) -> set[int]:
    refs = set()
    for m in re.finditer(r"(?:ال|لل)ماد(?:ة|تين)\s*\(?\s*([^)،.:؛]{3,60}?)\s*\)?\s*(?:من هذا النظام|من النظام|،|\.|$)", text):
        whole = parse_ordinal("المادة " + m.group(1).strip())
        if whole:
            refs.add(whole[0])
            continue
        # "المادتين X و Y": split only where each side is itself a complete ordinal
        bits = re.split(r"\s+و(?=ال)", m.group(1))
        for cut in range(1, len(bits)):
            left = parse_ordinal("المادة " + " و".join(bits[:cut]))
            right = parse_ordinal("المادة " + " و".join(bits[cut:]))
            if left and right:
                refs |= {left[0], right[0]}
                break
    refs |= {int(x) for x in re.findall(r"(?:ال|لل)ماد(?:ة|تين)\s*\(\s*(\d+)\s*\)", text.translate(_AR_DIGITS))}
    return refs


def en_refs(text: str) -> set[int]:
    refs = set()
    for m in re.finditer(r"Articles?\s*\(?\s*((?:\d+\s*\)?\s*(?:,|and|&)?\s*\(?\s*)+)", text):
        refs |= {int(x) for x in re.findall(r"\d+", m.group(1))}
    return refs


def clause_markers(text: str, lang: str) -> int:
    if lang == "ar":
        return len(re.findall(r"(?:^|\s)(?:\d{1,2}|[أبجدهوزحطي])\s*[-.)/](?=\s|\S)", text.translate(_AR_DIGITS)))
    return len(re.findall(r"(?:^|\s)\(?(?:\d{1,2}|[a-h])[.)]\s", text))


def auto_checks(r: Record) -> dict:
    a, e = r.ar_text, r.en_text or ""
    an, enn = ar_numbers(a), en_numbers(e)
    ar_r, en_r = ar_refs(a), en_refs(e)
    confirmed_refs = {float(x) for x in ar_r & en_r}  # Arabic writes these as ordinals
    enn = {x for x in enn if x not in confirmed_refs}
    return {
        "numbers_ar_not_en": sorted(x for x in an if x not in enn),
        "numbers_en_not_ar": sorted(x for x in enn if x not in an),
        "refs_ar": sorted(ar_r), "refs_en": sorted(en_r),
        "refs_mismatch": sorted(ar_r ^ en_r),
        "clauses_ar": clause_markers(a, "ar"), "clauses_en": clause_markers(e, "en"),
        "negation_ar": len(re.findall(r"(?:^|\s)(?:لا|ليس|غير|دون|عدم|ألا|إلا)(?=\s)", a)),
        "negation_en": len(re.findall(r"\b(?:not|no|without|unless|except|nor|neither)\b", e, re.I)),
        "may_en": len(re.findall(r"\bmay\b", e, re.I)), "shall_must_en": len(re.findall(r"\b(?:shall|must)\b", e, re.I)),
        "jaz_ar": len(re.findall(r"(?:يجوز|جاز|للوزير|لصاحب العمل|للعامل)", a)),
        "yajib_ar": len(re.findall(r"(?:يجب|يلتزم|على صاحب العمل|على العامل|يتعين)", a)),
    }


def auto_flags(c: dict) -> list[str]:
    flags = []
    if c["numbers_ar_not_en"] or c["numbers_en_not_ar"]:
        flags.append(f"numbers differ (AR-only {c['numbers_ar_not_en']}, EN-only {c['numbers_en_not_ar']})")
    if c["refs_mismatch"]:
        flags.append(f"article references differ (AR {c['refs_ar']}, EN {c['refs_en']})")
    if c["clauses_ar"] != c["clauses_en"]:
        flags.append(f"clause markers differ (AR {c['clauses_ar']}, EN {c['clauses_en']})")
    return flags


# ----------------------------------------------------------------------------- selection

def allocate(pool_by_part: dict[int, list[str]], target: int = TARGET) -> dict[int, int]:
    """Proportional allocation (largest remainder) with a floor of MIN_PER_PART where available."""
    total = sum(len(v) for v in pool_by_part.values())
    if total <= target:
        return {p: len(v) for p, v in pool_by_part.items()}
    quota = {p: min(len(v), MIN_PER_PART) for p, v in pool_by_part.items()}
    rest = target - sum(quota.values())
    room = {p: len(v) - quota[p] for p, v in pool_by_part.items()}
    weight = sum(room.values())
    shares = {p: rest * room[p] / weight for p in room}
    for p in room:
        quota[p] += int(shares[p])
    leftover = target - sum(quota.values())
    for p in sorted(room, key=lambda p: (-(shares[p] - int(shares[p])), p))[:leftover]:
        quota[p] += 1
    return quota


def tiebreak(k: str) -> str:
    return hashlib.sha256(f"{SEED}:{k}".encode()).hexdigest()


def select(recs: dict[str, Record], excluded_after_review: dict[str, str], target: int = TARGET,
           outside_draw: dict[str, str] | None = None) -> dict:
    """Token-blind: uses only Part, Arabic character length and a seeded hash.

    The base draw runs over the whole eligible pool, so review exclusions never reshuffle it: each
    excluded pick is replaced by the next draw from the same Part, preferring its own length stratum
    (then the following strata in cycle order). Excluded articles are never drawn as replacements.
    """
    outside_draw = outside_draw or {}
    pool = {k: r for k, r in recs.items() if r.eligible and k not in outside_draw}
    by_part = collections.defaultdict(list)
    for k, r in pool.items():
        by_part[r.part].append(k)
    quota = allocate(by_part, target)
    chosen, strata, replacements = [], {}, {}
    for part in sorted(by_part):
        ks = sorted(by_part[part], key=lambda k: (len(pool[k].ar_text), sort_key(k)))
        n = len(ks)
        for i, k in enumerate(ks):
            strata[k] = "short" if i < n / 3 else "medium" if i < 2 * n / 3 else "long"
        remaining = {s: sorted([k for k in ks if strata[k] == s], key=tiebreak) for s in ("short", "medium", "long")}
        order = ["short", "medium", "long"]
        picked, j = [], 0
        while len(picked) < quota[part]:
            s = order[j % 3]
            if remaining[s]:
                picked.append(remaining[s].pop(0))
            j += 1
        for k in picked:
            if k not in excluded_after_review:
                chosen.append(k)
                continue
            i = order.index(strata[k])
            for s in order[i:] + order[:i]:
                cand = [c for c in remaining[s] if c not in excluded_after_review]
                if cand:
                    remaining[s].remove(cand[0])
                    replacements[k] = cand[0]
                    chosen.append(cand[0])
                    break
            else:
                replacements[k] = None  # Part exhausted: shortfall, never filled from another Part
    return {
        "seed": SEED, "target": target, "pool_size": len(pool),
        "eligible_total": sum(1 for r in recs.values() if r.eligible),
        "eligible_outside_draw": {k: outside_draw[k] for k in sorted(outside_draw, key=sort_key)},
        "pool_size_after_review": len([k for k in pool if k not in excluded_after_review]),
        "replacements": {k: replacements[k] for k in sorted(replacements, key=sort_key)},
        "quota_by_part": {str(p): q for p, q in sorted(quota.items())},
        "pool_by_part": {str(p): len(v) for p, v in sorted(by_part.items())},
        "selected": sorted(chosen, key=sort_key),
        "stratum": {k: strata[k] for k in sorted(chosen, key=sort_key)},
        "excluded_after_review": dict(sorted(excluded_after_review.items(), key=lambda kv: sort_key(kv[0]))),
    }


# ----------------------------------------------------------------------------- manifest

# Pairs excluded after AI review (Task 07, 2026-11-23); details and source references in the review
# file (`excluded_after_review`, `discrepancy_matrix`). Neither official text is corrected.
EXCLUDED_AFTER_REVIEW: dict[str, str] = {
    "40": "VERSION_MISMATCH: English predates the M/44 amendment (liability qualifier missing)",
    "63": "FAIL: legal basis changed (prohibited by Sharia -> legally prohibited)",
    "66": "FAIL: sanction not identified (fine -> Penalty)",
    "76": "FAIL: condition widened (agree on more -> agree otherwise); rejected replacement draw",
    "81": "FAIL: threshold dropped (grave danger -> a danger)",
    "189": "FAIL: negation conflict (English adds 'do not'); unresolved by authoritative evidence",
}
# Articles that became eligible only after the 2026-11-24 parser fixes (Article 33: an inter-word
# space set in a smaller font was dropped; Articles 79 and 79 bis: the English heading
# "Article 79:(Bis)" was not recognised). No selected pair's text changed, so the draw stays on the
# pool as curated on 2026-11-23 and the 100 measured pairs are kept. Not AI-reviewed (not selected).
OUTSIDE_DRAW: dict[str, str] = {
    "33": "eligible after PDF whitespace-span fix (2026-11-24); outside the frozen draw",
    "79": "eligible after English 'Article 79:(Bis)' heading fix (2026-11-24); outside the frozen draw",
    "79bis": "eligible after English 'Article 79:(Bis)' heading fix (2026-11-24); outside the frozen draw",
}


def curated_selection(recs: dict[str, Record]) -> dict:
    return select(recs, EXCLUDED_AFTER_REVIEW, outside_draw=OUTSIDE_DRAW)


REVIEW_PATH = Path("manifest") / f"{CORPUS}_review.json"
MANIFEST_PATH = Path("manifest") / f"{CORPUS}_manifest.json"
DECISIONS_PATH = Path("review") / f"{CORPUS}_human_decisions.json"
PROCEDURE = [
    "Pool: Arabic articles whose PDF text is confirmed character-for-character by the HRSD Arabic HTML "
    "(ignoring HTML-only tatweel/ZWNJ), not repealed, with exactly one correctly numbered English "
    "counterpart in the same Part",
    "Quota per Part: floor of 2 (where available), remainder allocated proportionally to pool size "
    "(largest remainder, ties by Part number); target 100",
    "Within a Part: articles sorted by Arabic character count and cut into thirds; picks cycle "
    "short -> medium -> long, each taking the lowest SHA-256(seed:key) remaining in that stratum",
    "Review exclusions never reshuffle the draw: each excluded pick is replaced by the next draw (same "
    "seed order) from the same Part, preferring its own stratum, then the following strata in cycle order",
    "Token counts, ratios and English length are never consulted",
    "Frozen pool: articles that became eligible only after later parser fixes are recorded but kept out of "
    "the draw, so fixes that leave every selected text unchanged do not reshuffle the measured pairs",
]


def build_manifest(root: Path, recs: dict[str, Record], anomalies: dict, src: dict) -> dict:
    review = json.loads((root / REVIEW_PATH).read_text(encoding="utf-8"))
    sel = curated_selection(recs)
    missing = [k for k in sel["selected"] if k not in review["articles"]]
    if missing:
        raise ValueError(f"selected pairs without an AI review entry: {missing}")
    prov = src["prov"]
    counts = collections.Counter(review["articles"][k]["proposed_status"] for k in sel["selected"])
    entries = []
    for k in sel["selected"]:
        r = recs[k]
        entries.append({
            "id": entry_id(k),
            "key": k, "part": r.part,
            "ar_heading": r.ar_heading, "en_label": r.en_labels[0],
            "ar_sha256": sha256_text(r.ar_text), "en_sha256": sha256_text(r.en_text),
            "ar_chars": len(r.ar_text), "en_chars": len(r.en_text),
            "ar_pdf_pages": r.ar_pages, "en_url": r.en_url, "ar_html_url": r.ar_html_url,
            "stratum": sel["stratum"][k],
            "review_status": review["articles"][k]["proposed_status"],
        })
    return {
        "corpus": CORPUS, "corpus_version": 2, "status": "provisional",
        "human_approval": "PENDING: no pair is human-approved; see review/current_law_v2_human_decisions.json",
        "law": {
            "name_en": "Labor Law", "name_ar": "نظام العمل",
            "instrument": "Royal Decree No. M/51 dated 1426/08/23 AH",
            "version": "consolidated through Royal Decree No. M/44 dated 1446/02/08 AH, in force from 1446/08/20 AH",
        },
        "source_authority": SOURCE_AUTHORITY,
        "sources": {
            "ar_pdf": {k: prov["ar/labor-law.pdf"][k] for k in ("url", "sha256", "bytes", "last_modified_header", "retrieved_at_utc")},
            "en_index": {k: prov["en/index.html"][k] for k in ("final_url", "retrieved_at_utc")},
            "parts": [{
                "part": p.part, "title_en": p.title,
                "en_url": prov[f"en/part-{p.part:02d}.html"]["final_url"],
                "en_page_sha256_at_curation": prov[f"en/part-{p.part:02d}.html"]["sha256"],
                "ar_html_url": prov[f"ar_html/part-{p.part:02d}.html"]["final_url"],
                "ar_html_page_sha256_at_curation": prov[f"ar_html/part-{p.part:02d}.html"]["sha256"],
            } for p in src["parts"]],
            "page_hash_note": "HTML page hashes are informational (pages may change cosmetically); "
                              "per-article text hashes are authoritative. The PDF hash is pinned.",
        },
        "extraction": {
            "arabic_pdf": "PyMuPDF; lines classified by font size (13.9 headings, 12.0 body, 10.6 repealed "
                          "marker, <9 footnotes/markers excluded, >=16 titles); blocks read top-to-bottom",
            "arabic_cleanup": "presentation forms -> base letters (NFKC on those code points only); "
                              "justification tatweel removed; mirrored ( ) [ ] { } swapped back",
            "english_html": "selectolax; article = <h4>Article N:</h4> + following blocks until the next "
                            "article or section title; <ol> numbers reconstructed as 'N.'",
            "counting_normalization": "every whitespace run -> one space, ends stripped (unchanged from v1); "
                                      "applied after extraction cleanup",
            "arabic_confirmation": "PDF text must equal the HRSD Arabic HTML text (ignoring HTML-only "
                                   "tatweel/ZWNJ); otherwise the article is excluded, not repaired",
        },
        "anomalies": anomalies,
        "candidates": {k: {"part": r.part, "eligible": r.eligible, "reasons": r.reasons}
                       for k, r in sorted(recs.items(), key=lambda kv: sort_key(kv[0]))},
        "selection": {"procedure": PROCEDURE, **sel},
        "review": {"file": str(REVIEW_PATH), "proposed_status_counts": dict(sorted(counts.items()))},
        "tokenizers": [{"model": t.repo_id, "revision": t.revision} for t in tokenization.TOKENIZERS],
        "articles": entries,
    }


class VerificationError(RuntimeError):
    pass


_HEX64 = re.compile(r"[0-9a-f]{64}")
_ENTRY_TYPES = {"id": str, "key": str, "part": int, "ar_sha256": str, "en_sha256": str,
                "ar_chars": int, "en_chars": int, "review_status": str}


def entry_id(key: str) -> str:
    return f"KSA-LL-v2-{key.zfill(6) if not key.endswith('bis') else key[:-3].zfill(3) + 'bis'}"


# Independent anchor for the frozen corpus: SHA-256 over the ordered "key ar_sha256 en_sha256" lines of
# the 100 pairs measured since the corpus freeze (also pinned in tests/current_law_v2_pairs_frozen.json). It does
# not depend on the manifest, so a manifest edited consistently in several places is still rejected.
FROZEN_PAIRS = 100
FROZEN_PAIRS_SHA256 = "29a5bf02582f834817f9a094fa8ff73ea82b4a39b086e40e95752dfdf9ad4e13"


def pairs_digest(triples) -> str:
    return hashlib.sha256("".join(f"{k} {a} {e}\n" for k, a, e in triples).encode("utf-8")).hexdigest()


def _get(obj, path: str, kind: type, errs: list[str]):
    """Typed lookup along a dotted path; records a clear error instead of raising."""
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            errs.append(f"{path}: parent of {part!r} is not an object")
            return None
        cur = cur.get(part)
    if not isinstance(cur, kind) or isinstance(cur, bool) and kind is not bool:
        errs.append(f"{path}: missing or not {kind.__name__ if isinstance(kind, type) else kind}")
        return None
    return cur


def validate_manifest(manifest) -> list[str]:
    """Structural checks that need no sources: a manifest failing any of them is never measured."""
    if not isinstance(manifest, dict):
        return ["manifest is not a JSON object"]
    errs = []
    if manifest.get("corpus") != CORPUS:
        errs.append(f"corpus is {manifest.get('corpus')!r}, expected {CORPUS!r}")
    arts = manifest.get("articles")
    if not isinstance(arts, list) or not arts:
        return errs + ["article list is missing or empty"]
    if len(arts) != FROZEN_PAIRS:
        errs.append(f"article list has {len(arts)} entries; the frozen corpus has exactly {FROZEN_PAIRS}")
    pdf_hash = _get(manifest, "sources.ar_pdf.sha256", str, errs)
    if pdf_hash is not None and not _HEX64.fullmatch(pdf_hash):
        errs.append("sources.ar_pdf.sha256 malformed")
    # Child fields are required whenever `selection` is an object, including an empty one ({} is falsy;
    # gating on truthiness let `selection = {}` skip every selection check).
    sel = _get(manifest, "selection", dict, errs)
    selected = _get(manifest, "selection.selected", list, errs) if sel is not None else None
    excluded = _get(manifest, "selection.excluded_after_review", dict, errs) if sel is not None else None
    outside = _get(manifest, "selection.eligible_outside_draw", dict, errs) if sel is not None else None
    # the exclusion records must state exactly what the curation code applied
    if excluded is not None and excluded != EXCLUDED_AFTER_REVIEW:
        errs.append("selection.excluded_after_review differs from EXCLUDED_AFTER_REVIEW")
    if outside is not None and outside != OUTSIDE_DRAW:
        errs.append("selection.eligible_outside_draw differs from OUTSIDE_DRAW")
    cands = _get(manifest, "candidates", dict, errs)
    keys, ids = [], []
    for i, e in enumerate(arts):
        if not isinstance(e, dict):
            errs.append(f"entry {i}: not an object")
            continue
        for f, t in _ENTRY_TYPES.items():
            if type(e.get(f)) is not t:
                errs.append(f"entry {i}: field {f!r} missing or not {t.__name__}")
        if errs and errs[-1].startswith(f"entry {i}:"):
            continue
        k = e["key"]
        keys.append(k)
        ids.append(e["id"])
        if not re.fullmatch(r"[1-9]\d{0,2}(bis)?", k):
            errs.append(f"entry {i}: malformed key {k!r}")
        elif e["id"] != entry_id(k):
            errs.append(f"{k}: id {e['id']!r} does not match key")
        for f in ("ar_sha256", "en_sha256"):
            if not _HEX64.fullmatch(e[f]):
                errs.append(f"{k}: malformed {f}")
        if e["ar_chars"] <= 0 or e["en_chars"] <= 0:
            errs.append(f"{k}: non-positive character count")
        if e["review_status"] not in ("PROPOSED_PASS", "NEEDS_REVIEW"):
            errs.append(f"{k}: review_status {e['review_status']!r} is not admissible in the corpus")
    for name, seq in (("key", keys), ("id", ids)):
        dups = sorted({x for x in seq if seq.count(x) > 1})
        if dups:
            errs.append(f"duplicate article {name}s: {dups}")
    if selected is not None and selected != keys:
        errs.append("article list does not match selection.selected (order and membership)")
    if excluded is not None and set(excluded) & set(keys):
        errs.append(f"articles excluded after review are listed: {sorted(set(excluded) & set(keys))}")
    triples = [(e["key"], e["ar_sha256"], e["en_sha256"]) for e in arts
               if isinstance(e, dict) and all(isinstance(e.get(f), str) for f in ("key", "ar_sha256", "en_sha256"))]
    if pairs_digest(triples) != FROZEN_PAIRS_SHA256:
        errs.append("ordered article identities (key, Arabic hash, English hash) differ from the frozen "
                    "100-pair anchor")
    for e in arts if cands is not None else []:
        if isinstance(e, dict) and isinstance(e.get("key"), str):
            c = cands.get(e["key"])
            if not isinstance(c, dict):
                errs.append(f"{e['key']}: candidate record missing or not an object")
            elif c.get("eligible") is not True:
                errs.append(f"{e['key']}: not an eligible candidate in this manifest")
            elif c.get("part") != e.get("part"):
                errs.append(f"{e['key']}: part {e.get('part')} disagrees with candidates ({c.get('part')})")
    return errs


def verify(manifest: dict, raw: Path = RAW) -> list[Record]:
    """Re-extract from the pinned cache; raise unless the manifest is well formed and every pair is
    unchanged, eligible and consistent with its recorded metadata."""
    errs = validate_manifest(manifest)
    if errs:
        raise VerificationError("malformed manifest: " + "; ".join(errs))
    pdf = raw / "ar/labor-law.pdf"
    if sha256_bytes(pdf.read_bytes()) != manifest["sources"]["ar_pdf"]["sha256"]:
        raise VerificationError("Arabic PDF differs from the pinned SHA-256")
    recs, _ = build_records(load(raw))
    drawn = curated_selection(recs)["selected"]
    if drawn != [e["key"] for e in manifest["articles"]]:
        raise VerificationError("article list differs from the frozen draw recomputed from the sources")
    bad, out = [], []
    for e in manifest["articles"]:
        r = recs.get(e["key"])
        if r is None:
            bad.append(f"{e['key']}: missing")
        elif not r.eligible:
            bad.append(f"{e['key']}: no longer eligible ({'; '.join(r.reasons)})")
        elif sha256_text(r.ar_text) != e["ar_sha256"] or sha256_text(r.en_text) != e["en_sha256"]:
            bad.append(f"{e['key']}: text hash mismatch")
        elif (len(r.ar_text), len(r.en_text), r.part) != (e["ar_chars"], e["en_chars"], e["part"]):
            bad.append(f"{e['key']}: recorded character counts or part disagree with the source")
        else:
            out.append(r)
    if bad:
        raise VerificationError("; ".join(bad))
    return out


# ----------------------------------------------------------------------------- measurement

CSV_FIELDS = ["model", "revision", "article_id", "article", "part", "ar_sha256", "en_sha256",
              "ar_chars", "en_chars", "ar_tokens", "en_tokens", "ar_en_ratio"]


def measure(records: list[Record], manifest: dict, hf_cache: Path) -> tuple[list[dict], list[dict]]:
    by_key = {e["key"]: e for e in manifest["articles"]}
    rows, info = [], []
    for spec in tokenization.TOKENIZERS:
        lt = tokenization.load(spec, hf_cache)
        info.append({"model": spec.repo_id, "revision": spec.revision, "tokenizer_json_sha256": lt.file_sha256})
        for r in records:
            e = by_key[r.key]
            ar = tokenization.count_tokens(lt.tokenizer, r.ar_text)
            en = tokenization.count_tokens(lt.tokenizer, r.en_text)
            rows.append({"model": spec.repo_id, "revision": spec.revision, "article_id": e["id"],
                         "article": r.key, "part": r.part, "ar_sha256": e["ar_sha256"],
                         "en_sha256": e["en_sha256"], "ar_chars": len(r.ar_text), "en_chars": len(r.en_text),
                         "ar_tokens": ar, "en_tokens": en, "ar_en_ratio": f"{ar / en:.4f}"})
    return rows, info


def summarize(rows: list[dict], info: list[dict]) -> dict:
    by_part = {}
    for model in dict.fromkeys(r["model"] for r in rows):
        parts = collections.defaultdict(lambda: [0, 0, 0])
        for r in rows:
            if r["model"] == model:
                p = parts[int(r["part"])]
                p[0] += 1
                p[1] += int(r["ar_tokens"])
                p[2] += int(r["en_tokens"])
        by_part[model] = {str(p): {"articles": n, "ar_tokens_total": a, "en_tokens_total": e, "ttr": a / e}
                          for p, (n, a, e) in sorted(parts.items())}
    return {"tokenizers": info, "models": metrics.summarize(rows), "by_part": by_part}


# ----------------------------------------------------------------------------- migration

def _loose(s: str) -> str:
    import unicodedata

    s = "".join(c for c in unicodedata.normalize("NFKD", s) if unicodedata.category(c) != "Mn")
    s = re.sub("[أإآ]", "ا", s).replace("ى", "ي").replace("ـ", "")
    return re.sub(r"[\W_]+", "", s.lower())


def migration(manifest: dict, recs: dict[str, Record], v1_manifest: dict, v1_pairs) -> dict:
    import difflib

    selected = {e["key"] for e in manifest["articles"]}
    v1_text = {p.article: p for p in v1_pairs}
    old = []
    for e in v1_manifest["articles"]:
        n = e["article"]
        k, r, p = str(n), recs.get(str(n)), v1_text[n]
        ar_ratio = difflib.SequenceMatcher(None, _loose(p.ar_text), _loose(r.ar_text), autojunk=False).ratio()
        if p.ar_text == r.ar_text:
            ar_state = "identical"
        elif _loose(p.ar_text) == _loose(r.ar_text):
            ar_state = "same wording (typographic differences only: diacritics, hamza, spacing, punctuation)"
        else:
            ar_state = "wording differs"
        en_ratio = (difflib.SequenceMatcher(None, _loose(p.en_text), _loose(r.en_text or ""), autojunk=False).ratio()
                    if r.en_text else None)
        old.append({
            "article": k,
            "v2_status": "selected" if k in selected else ("eligible, not selected by the procedure" if r.eligible else "excluded"),
            "v2_exclusion_reasons": r.reasons,
            "arabic_v1_boe_vs_v2_hrsd": ar_state,
            "arabic_similarity": round(ar_ratio, 4),
            "english_translation": ("BOE official translation (2005 base text) -> HRSD English (consolidated); "
                                    "different translation" if en_ratio is not None and en_ratio < 0.98 else
                                    "near-identical" if en_ratio is not None else "no unambiguous HRSD English"),
            "english_similarity": round(en_ratio, 4) if en_ratio is not None else None,
        })
    v1_keys = {str(e["article"]) for e in v1_manifest["articles"]}
    return {
        "from": "expanded_v1 (30 articles; includes the 10 pilot articles)",
        "to": CORPUS,
        "old_articles": old,
        "summary": {
            "old_selected_in_v2": sorted((o["article"] for o in old if o["v2_status"] == "selected"), key=sort_key),
            "old_eligible_not_selected": sorted((o["article"] for o in old if o["v2_status"].startswith("eligible")), key=sort_key),
            "old_excluded": {o["article"]: o["v2_exclusion_reasons"] for o in old if o["v2_status"] == "excluded"},
            "arabic_identical_or_typographic_only": sorted((o["article"] for o in old if o["arabic_v1_boe_vs_v2_hrsd"] != "wording differs"), key=sort_key),
            "arabic_wording_differs": sorted((o["article"] for o in old if o["arabic_v1_boe_vs_v2_hrsd"] == "wording differs"), key=sort_key),
            "english_translation_changed": sorted((o["article"] for o in old if (o["english_similarity"] or 1) < 0.98), key=sort_key),
            "newly_included": sorted(selected - v1_keys, key=sort_key),
        },
    }


# ----------------------------------------------------------------------------- report

def _overlap(rows: list[dict], v1_rows: list[dict]) -> dict:
    """Same articles, old (BOE) vs new (HRSD) texts, same tokenizers: isolates the source change."""
    v2k = {(r["model"], str(r["article"])): r for r in rows}
    out = {}
    for model in dict.fromkeys(r["model"] for r in rows):
        pairs = [(o, v2k[(model, str(o["article"]))]) for o in v1_rows
                 if o["model"] == model and (model, str(o["article"])) in v2k]
        if not pairs:
            continue
        a1 = sum(int(o["ar_tokens"]) for o, _ in pairs); e1 = sum(int(o["en_tokens"]) for o, _ in pairs)
        a2 = sum(int(n["ar_tokens"]) for _, n in pairs); e2 = sum(int(n["en_tokens"]) for _, n in pairs)
        out[model] = {"articles": sorted((str(o["article"]) for o, _ in pairs), key=sort_key),
                      "v1": {"ar": a1, "en": e1, "ttr": a1 / e1}, "v2": {"ar": a2, "en": e2, "ttr": a2 / e2}}
    return out


def render_report(manifest: dict, rows: list[dict], summary: dict, review: dict,
                  historic: dict, v1_rows: list[dict], mig: dict) -> str:
    sel = manifest["selection"]
    L = [f"# ATTI {CORPUS}: Arabic vs English token counts, current Saudi Labor Law ({len(manifest['articles'])} articles)\n",
         f"> **Status: PROVISIONAL.** {manifest['human_approval']}. Pair review is AI-assisted "
         f"({review['reviewer']}): {manifest['review']['proposed_status_counts']}.\n",
         f"**Research scope.** {review['research_scope']}\n" if review.get("research_scope") else "",
         "Token counts from the pinned tokenizers; content only (no special tokens, no chat template, no "
         "truncation). **TTR = Σ Arabic tokens / Σ English tokens.** These are tokenizer measurements, not "
         "inference cost, latency or quality.\n",
         "## Sources\n",
         f"- Arabic: HRSD consolidated PDF <{manifest['sources']['ar_pdf']['url']}>, SHA-256 "
         f"`{manifest['sources']['ar_pdf']['sha256']}`; {manifest['law']['version']}.",
         f"- English: HRSD English Part pages (16), discovered from <{manifest['sources']['en_index']['final_url']}>. "
         "Published by the ministry; translation status not stated on the pages.",
         "- Cross-checks: HRSD Arabic HTML (extraction confirmation), BOE register and Umm Al-Qura gazette "
         "(no amendment newer than M/44 found). Details: `reports/current_law_v2_sources.md`.\n",
         "## Results by tokenizer\n",
         "| Tokenizer | Revision | Σ AR tokens | Σ EN tokens | **TTR** | Median article ratio | Min | Max |",
         "|---|---|---:|---:|---:|---:|---:|---:|"]
    for t in summary["tokenizers"]:
        s = summary["models"][t["model"]]
        L.append(f"| {t['model']} | `{t['revision'][:12]}` | {s['ar_tokens_total']} | {s['en_tokens_total']} | "
                 f"**{s['ttr']:.4f}** | {s['median_article_ratio']:.4f} | {s['min_article_ratio']:.4f} | "
                 f"{s['max_article_ratio']:.4f} |")
    L += ["", "## By Part\n", "| Part | Articles | " + " | ".join(
        f"{t['model'].split('/')[-1]} AR / EN / TTR" for t in summary["tokenizers"]) + " |",
          "|---:|---:|" + "---|" * len(summary["tokenizers"])]
    first = summary["tokenizers"][0]["model"]
    for p, v in summary["by_part"][first].items():
        cells = [f"{summary['by_part'][t['model']][p]['ar_tokens_total']} / "
                 f"{summary['by_part'][t['model']][p]['en_tokens_total']} / "
                 f"{summary['by_part'][t['model']][p]['ttr']:.4f}" for t in summary["tokenizers"]]
        L.append(f"| {p} | {v['articles']} | " + " | ".join(cells) + " |")
    L += ["", "## Comparison with historical corpora (descriptive)\n",
          "| Tokenizer | pilot (10, BOE) | expanded_v1 (30, BOE) | current_law_v2 (100, HRSD) |",
          "|---|---:|---:|---:|"]
    for t in summary["tokenizers"]:
        m = t["model"]
        L.append(f"| {m} | {historic['pilot'][m]['ttr']:.4f} | {historic['expanded_v1'][m]['ttr']:.4f} | "
                 f"{summary['models'][m]['ttr']:.4f} |")
    ov = _overlap(rows, v1_rows)
    L += ["", "What can and cannot explain the differences:\n",
          "- **Tokenizer behaviour:** held constant (same pinned revisions and counting rules in all corpora).",
          f"- **Source change** (same articles, old BOE texts vs new HRSD texts), on the "
          f"{len(next(iter(ov.values()))['articles'])} articles present in both expanded_v1 and v2:"]
    for m, v in ov.items():
        L.append(f"  - {m}: TTR {v['v1']['ttr']:.4f} (BOE) → {v['v2']['ttr']:.4f} (HRSD); "
                 f"Arabic {v['v1']['ar']} → {v['v2']['ar']} tokens, English {v['v1']['en']} → {v['v2']['en']} tokens.")
    L.append("- **Sample composition** (same HRSD texts and tokenizers, overlap subset vs all 100 articles):")
    for m, v in ov.items():
        full = summary["models"][m]["ttr"]
        L.append(f"  - {m}: overlap {v['v2']['ttr']:.4f} → full corpus {full:.4f}.")
    L.append("- Summary of the 10/30 → 100 change, per tokenizer: source effect = overlap HRSD − overlap BOE; "
             "composition effect = full v2 − overlap HRSD:")
    for m, v in ov.items():
        full = summary["models"][m]["ttr"]
        L.append(f"  - {m}: source {v['v2']['ttr'] - v['v1']['ttr']:+.4f}, composition {full - v['v2']['ttr']:+.4f} "
                 f"(expanded_v1 → v2 total {full - historic['expanded_v1'][m]['ttr']:+.4f}; the 15-article overlap is "
                 "a different subset from expanded_v1's 30, so these do not sum exactly).")
    L.append(f"- v2 includes {len(mig['summary']['newly_included'])} articles that were in no earlier corpus. "
             "No statistical significance is claimed.\n")
    L += _review_exclusions_section(sel, review)
    L += _limitations_section(review)
    L += ["## Selection\n"] + [f"- {x}" for x in sel["procedure"]] + [
        f"- Seed `{sel['seed']}`; pool {sel['pool_size']} eligible ({sel['pool_size_after_review']} after review "
        f"exclusions) of {len(manifest['candidates'])} Arabic articles; "
        f"quota by Part {sel['quota_by_part']}.",
        f"- {sel['eligible_total']} articles are eligible now; "
        + ", ".join(sel["eligible_outside_draw"]) + " became eligible only after the 2026-11-24 parser fixes "
        "and are kept outside the frozen draw (no selected text changed).",
        "- Excluded candidates and reasons: `manifest/current_law_v2_manifest.json` → `candidates`.\n",
        "## Source anomalies (reported, not repaired)\n",
        f"- English labels used twice: {manifest['anomalies']['en_duplicate_labels']}; English numbers missing: "
        f"{manifest['anomalies']['en_missing']} (Part 14 shows Article 210 twice and no Article 219; Part 6 labels "
        "Article 101 as 'Article 10'; Part 13 labels Article 197 as 'Article 194'). Article 79 bis is published as "
        "'Article 79:(Bis)' and is parsed as 79 bis since the 2026-11-24 fix.",
        "- Clause numbering differs between languages in selected Articles "
        + ", ".join(d["article"] for d in review.get("discrepancy_matrix", [])
                    if d["category"] == "FORMATTING_ANOMALY" and d["disposition"] == "RETAINED")
        + " (source list markup; content corresponds).",
        "- Arabic Article 181 contains a stray '0'; English Article 184 reads 'seafarer1' (both kept verbatim).\n",
        "## Recalculation\n",
        "All aggregates are recomputable from `results/current_law_v2.csv` (TTR = Σ ar_tokens / Σ en_tokens per "
        "model; medians over per-row ratios); `tests/test_v2.py` does this with exact fractions.\n",
        "## Limitations\n",
        f"- PROVISIONAL: AI-assisted review only; {manifest['review']['proposed_status_counts'].get('NEEDS_REVIEW', 0)} "
        "pairs NEEDS_REVIEW; no human approval.",
        f"- {len(review['excluded_after_review'])} pairs were excluded after AI review under the strict rule above; "
        "applying it is an AI judgement that a human reviewer may overturn. Priority items for human review: "
        f"{', '.join(review['priority_for_human'])}.",
        "- The English is the ministry's published translation; its official status is not stated.",
        f"- {sum(1 for c in manifest['candidates'].values() if not c['eligible'])} of {len(manifest['candidates'])} "
        "Arabic articles were not eligible (" + ", ".join(
            f"{n} {code}" for code, n in sorted(collections.Counter(
                r.split(':')[0] for c in manifest['candidates'].values() for r in c['reasons']).items()))
        + "; an article can have several reasons). Requiring two identical Arabic renderings skews the pool "
        "toward articles without lists or layout quirks.",
        "- One law; Part 14 absent (repealed).",
    ]
    return "\n".join(L) + "\n"


def _review_exclusions_section(sel: dict, review: dict) -> list[str]:
    L = ["## Review exclusions and replacements\n",
         f"Rule: {review['exclusion_rule']}\n",
         "| Excluded | Status | Category | Replaced by |", "|---:|---|---|---|"]
    for k, v in review["excluded_after_review"].items():
        if k in sel["replacements"]:
            rb = sel["replacements"][k] or "none (Part exhausted)"
        else:
            rb = "n/a (rejected replacement draw, never selected)"
        L.append(f"| {k} | {v['proposed_status']} | {v['category']} | {rb} |")
    L += ["", "Per-article sources, excerpts and findings: `reports/current_law_v2_discrepancies.md`.\n"]
    return L


def _limitations_section(review: dict) -> list[str]:
    lim = review.get("source_alignment_limitations") or []
    if not lim:
        return []
    L = ["## Source-alignment limitations (retained pairs)\n",
         "Semantic differences between the published Arabic and English texts of selected pairs. They are "
         "documented, not repaired; the pairs stay in the corpus under the research scope.\n",
         "| Art. | Category | Arabic excerpt | English excerpt | Finding | Origin |", "|---:|---|---|---|---|---|"]
    for d in lim:
        L.append(f"| {d['article']} | {d['category']} | {d['ar_excerpt']} | {d['en_excerpt']} | {d['finding']} | "
                 f"{d['finding_origin']} |")
    return L + [""]


def render_discrepancy_matrix(review: dict, texts: dict | None = None) -> str:
    """Committed matrix (short excerpts only). With `texts` ({key: (ar, en)}) it appends the full
    texts: that variant is written only under git-ignored data/review/."""
    L = [f"# ATTI {CORPUS}: discrepancy matrix (AI review, provisional)\n",
         "> AI-assisted analysis, **not** human verification. Excerpts are short quotations for "
         "identification; full texts stay in local, git-ignored files.\n",
         f"Rule: {review['exclusion_rule']}\n",
         "Categories: " + "; ".join(f"**{k}** = {v}" for k, v in review["discrepancy_categories"].items()) + ".\n",
         f"{review['no_extraction_failure_found']}\n",
         "| Art. | Part | Flagged | Category | Arabic excerpt | English excerpt | BOE English (cross-check) | Disposition |",
         "|---:|---:|---|---|---|---|---|---|"]
    for d in review["discrepancy_matrix"]:
        disp = d["disposition"] + (f" → {d['replaced_by']}" if d.get("replaced_by") else "")
        L.append(f"| {d['article']} | {d['part']} | {'yes' if d['originally_flagged'] else 'no'} | {d['category']} | "
                 f"{d['ar_excerpt']} | {d['en_excerpt']} | {d['boe_en_crosscheck']} | {disp} ({d['proposed_status']}) |")
    L.append("")
    L += _limitations_section(review)
    for d in review["discrepancy_matrix"] + review.get("source_alignment_limitations", []):
        if "disposition" not in d:
            d = {**d, "disposition": "RETAINED (source-alignment limitation)"}
        s = d["sources"]
        L += [f"## Article {d['article']}: {d['category']}, {d['disposition']}\n",
              "- Arabic PDF: " + ", ".join(f"<{u}>" for u in s["ar_pdf"]),
              f"- Arabic HTML: <{s['ar_html']}>",
              f"- English HTML: <{s['en_html']}>",
              f"- Finding: {d['finding']}"]
        if d.get("replacement_draws"):
            L.append(f"- Replacement draws: {', '.join(d['replacement_draws'])}")
        if texts and d["article"] in texts:
            ar, en = texts[d["article"]]
            L += ["", f'<div dir="rtl" lang="ar">{ar}</div>', "", en]
        L.append("")
    return "\n".join(L)


def render_sources_report(manifest: dict) -> str:
    a = manifest["source_authority"]
    L = ["# current_law_v2: source verification\n",
         "Recorded 2026-11-23. Web page and file dates are distinguished from legislative dates throughout.\n",
         "## Legal version\n",
         f"- {manifest['law']['instrument']}; {manifest['law']['version']}.",
         f"- Official register: {a['cross_check']['boe_register']}.",
         f"- Official gazette: {a['cross_check']['official_gazette']}.",
         f"- Newer amendments: {a['cross_check']['newer_amendments']}. This is an absence of evidence in the "
         "sources checked, not proof; the corpus therefore stays provisional.\n",
         "## Arabic\n"] + [f"- {k}: {v}" for k, v in a["arabic"].items()] + [
         f"- SHA-256 `{manifest['sources']['ar_pdf']['sha256']}`, {manifest['sources']['ar_pdf']['bytes']} bytes, "
         f"retrieved {manifest['sources']['ar_pdf']['retrieved_at_utc']}.\n",
         "## English\n"] + [f"- {k}: {v}" for k, v in a["english"].items()] + [
         "- Part pages (final URLs and page hashes at curation):"] + [
         f"  - Part {p['part']} ({p['title_en']}): <{p['en_url']}>" for p in manifest["sources"]["parts"]] + [
         "", "## Not confused with\n",
         "- The Implementing Regulations (اللائحة التنفيذية) are a separate instrument and are not used.",
         "- The BOE English PDF (2005 base text + amendments appendix) used by pilot/expanded_v1 is not mixed "
         "into this corpus.\n",
         "## Extraction\n"] + [f"- {k}: {v}" for k, v in manifest["extraction"].items()]
    return "\n".join(L) + "\n"


# ----------------------------------------------------------------------------- entry points

OUTPUTS = {
    "csv": Path("results") / f"{CORPUS}.csv",
    "summary": Path("results") / f"{CORPUS}_summary.json",
    "report": Path("reports") / f"{CORPUS}.md",
    "sources_report": Path("reports") / f"{CORPUS}_sources.md",
    "migration": Path("manifest") / f"{CORPUS}_migration.json",
    "discrepancies": Path("reports") / f"{CORPUS}_discrepancies.md",
}


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def fetch(root: Path) -> dict:
    return hrsd.fetch_source_set(hrsd.Fetcher(root / RAW))


def curate(root: Path) -> dict:
    """Deliberate curation step: rebuild the manifest from the cache and the AI review file."""
    src = load(root / RAW)
    recs, anomalies = build_records(src)
    manifest = build_manifest(root, recs, anomalies, src)
    dec_path = root / DECISIONS_PATH
    if dec_path.exists():
        recorded = [k for k, d in json.loads(dec_path.read_text())["decisions"].items() if d.get("decision")]
        if recorded:
            raise ValueError(f"human decisions are recorded for {recorded}; refusing to change the manifest "
                             "under them (decisions are bound to the manifest hash)")
    (root / MANIFEST_PATH).write_text(dumps(manifest), encoding="utf-8")
    if dec_path.exists():  # empty template only: re-bind it to the new manifest version
        from atti import review as review_mod

        tmpl = review_mod.decisions_template(CORPUS, manifest, review_mod.manifest_sha256(root / MANIFEST_PATH))
        dec_path.write_text(json.dumps(tmpl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def run(root: Path) -> dict:
    """Reproduce all current_law_v2 outputs from the pinned cache; historical files are only read."""
    import csv
    import io

    from atti import corpus, pipeline, sources

    fetch(root)
    sources.fetch_all(root / "data" / "raw")  # v1 BOE cache, read for the migration comparison
    manifest = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    review = json.loads((root / REVIEW_PATH).read_text(encoding="utf-8"))
    records = verify(manifest, root / RAW)
    rows, info = measure(records, manifest, root / "data" / "hf")
    summary = summarize(rows, info)
    historic = {n: json.loads((root / pipeline.CORPORA[n][2]).read_text())["models"] for n in ("pilot", "expanded_v1")}
    v1 = pipeline.load_published(root, "expanded_v1")
    recs, _ = build_records(load(root / RAW))
    mig = migration(manifest, recs, v1["manifest"], corpus.verify(v1["manifest"], root / "data" / "raw"))

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    for key, content in (
        ("csv", buf.getvalue()),
        ("summary", dumps(summary)),
        ("report", render_report(manifest, rows, summary, review, historic, v1["rows"], mig)),
        ("sources_report", render_sources_report(manifest)),
        ("migration", dumps(mig)),
        ("discrepancies", render_discrepancy_matrix(review)),
    ):
        path = root / OUTPUTS[key]
        path.parent.mkdir(exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return summary
