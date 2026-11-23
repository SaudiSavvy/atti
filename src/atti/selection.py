"""Deterministic, ratio-blind selection of the expanded corpus (expanded_v1).

Procedure (no token counts are ever consulted):

1. Pool = pairs passing the existing eligibility rule (``corpus.eligible_pairs``),
   minus the 10 pilot articles, minus:
   - Part 11 (Marine Employment Contract): Royal Decree M/44 redefined its key
     terms by reference to the Commercial Maritime Law, a change not attached
     to the individual articles;
   - articles mentioning the Labor Dispute Commissions (the dispute-settlement
     bodies): Royal Decree M/1 replaced that phrase "wherever mentioned"
     without naming the articles;
   - articles excluded after review (``EXCLUDED``, with reasons).
2. Length strata: the pool is sorted by Arabic character count and cut into
   thirds (short / medium / long).
3. Quotas: 7 short, 7 medium, 6 long (20 total).
4. Within each stratum (short, then medium, then long) repeatedly take the
   candidate whose Part of the Law has the fewest articles selected so far
   (pilot articles included), breaking ties by SHA-256(SEED + ":" + article).
"""

from __future__ import annotations

import hashlib
import re

from atti.corpus import ArticlePair

SEED = "atti-expanded-v1"
QUOTAS = (("short", 7), ("medium", 7), ("long", 6))
EXCLUDED_PARTS = {11: "Part 11 (marine): terms redefined by M/44 via the Commercial Maritime Law"}
_COMMISSION_EN = re.compile(r"\bCommissions?\b")  # capitalised: the dispute-settlement body
_COMMISSION_AR = "تسوية الخلافات"

# Articles removed after semantic review: {article: reason}. Empty unless a
# selected pair fails review; the selection is then re-run without it.
EXCLUDED: dict[int, str] = {}


def exclusion_reason(pair: ArticlePair, part: int) -> str | None:
    if part in EXCLUDED_PARTS:
        return EXCLUDED_PARTS[part]
    if _COMMISSION_EN.search(pair.en_text) or _COMMISSION_AR in pair.ar_text:
        return "mentions Labor Dispute Commissions (M/1 global phrase replacement)"
    return EXCLUDED.get(pair.article)


def tiebreak(article: int) -> str:
    return hashlib.sha256(f"{SEED}:{article}".encode()).hexdigest()


def strata(pool: dict[int, ArticlePair]) -> dict[int, str]:
    order = sorted(pool, key=lambda n: (len(pool[n].ar_text), n))
    k = len(order)
    return {n: ("short" if i < k // 3 else "medium" if i < 2 * k // 3 else "long")
            for i, n in enumerate(order)}


def select(pairs: dict[int, ArticlePair], parts: dict[int, int], fixed: list[int]) -> dict:
    """Return the selection with its full audit trail."""
    excluded = {}
    pool = {}
    for n, p in pairs.items():
        if n in fixed:
            continue
        reason = exclusion_reason(p, parts[n])
        if reason:
            excluded[n] = reason
        else:
            pool[n] = p
    stratum = strata(pool)
    counts: dict[int, int] = {}
    for n in fixed:
        counts[parts[n]] = counts.get(parts[n], 0) + 1
    chosen: list[int] = []
    for name, quota in QUOTAS:
        cands = [n for n in pool if stratum[n] == name]
        for _ in range(quota):
            best = min(cands, key=lambda n: (counts.get(parts[n], 0), tiebreak(n)))
            cands.remove(best)
            chosen.append(best)
            counts[parts[best]] = counts.get(parts[best], 0) + 1
    lengths = sorted(len(p.ar_text) for p in pool.values())
    k = len(lengths)
    return {
        "seed": SEED,
        "pool_size": len(pool),
        "stratum_bounds_ar_chars": {
            "short": [lengths[0], lengths[k // 3 - 1]],
            "medium": [lengths[k // 3], lengths[2 * k // 3 - 1]],
            "long": [lengths[2 * k // 3], lengths[-1]],
        },
        "quotas": dict(QUOTAS),
        "added": {n: {"stratum": stratum[n], "part": parts[n]} for n in chosen},
        "excluded_from_pool": dict(sorted(excluded.items())),
    }


PROCEDURE = (
    "Pool: pairs passing the existing eligibility rule, minus the 10 pilot articles",
    "Excluded from pool: Part 11 (marine terms redefined by M/44) and articles mentioning the "
    "Labor Dispute Commissions (M/1 global phrase replacement)",
    "Strata: pool sorted by Arabic character count (ties by article number) and cut into thirds",
    "Quotas 7 short / 7 medium / 6 long; within a stratum, repeatedly take the candidate whose Part "
    "has the fewest selected articles (pilot included), ties broken by SHA-256(seed:article)",
    "Token counts are never consulted during selection",
)


def expanded_manifest(raw_dir, pilot_manifest: dict, review: dict, fetch_log: dict) -> dict:
    from atti import corpus

    ar_articles, en_doc = corpus.load_sources(raw_dir)
    pairs = corpus.eligible_pairs(ar_articles, en_doc)
    parts = {a.number: a.part for a in ar_articles if not a.bis}
    fixed = [e["article"] for e in pilot_manifest["articles"]]
    sel = select(pairs, parts, fixed)
    added = list(sel["added"])
    extra = {
        "corpus": "expanded_v1",
        "corpus_version": 1,
        "derived_from": "manifest/pilot_manifest.json (all 10 entries retained unchanged)",
        "review_provenance": review["review_provenance"],
        "selection_rule": pilot_manifest["selection_rule"][:3] + [
            "Pilot 10 retained; 20 added by the deterministic procedure in `selection`"],
        "selection": {"procedure": list(PROCEDURE), **sel, "excluded_after_review": dict(EXCLUDED)},
        "subsets": {"pilot_10": sorted(fixed), "added_20": sorted(added)},
    }
    return corpus.build_manifest(raw_dir, fixed + added, review, fetch_log, extra)
