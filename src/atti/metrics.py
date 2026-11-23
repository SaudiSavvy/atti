"""Token Tax Ratio (TTR) metrics. Pure functions over raw integer counts."""

from __future__ import annotations

import statistics
from collections.abc import Sequence


def article_ratio(ar_tokens: int, en_tokens: int) -> float:
    if en_tokens <= 0:
        raise ValueError("English token count must be positive")
    return ar_tokens / en_tokens


def ttr(ar_counts: Sequence[int], en_counts: Sequence[int]) -> float:
    """TTR = sum(Arabic tokens) / sum(English tokens)."""
    if len(ar_counts) != len(en_counts) or not ar_counts:
        raise ValueError("need equal-length, non-empty count lists")
    return article_ratio(sum(ar_counts), sum(en_counts))


def median_ratio(ar_counts: Sequence[int], en_counts: Sequence[int]) -> float:
    if len(ar_counts) != len(en_counts) or not ar_counts:
        raise ValueError("need equal-length, non-empty count lists")
    return statistics.median(article_ratio(a, e) for a, e in zip(ar_counts, en_counts))


def summarize(rows: Sequence[dict]) -> dict:
    """Per-model aggregates from raw rows (keys: model, ar_tokens, en_tokens)."""
    out: dict[str, dict] = {}
    for model in dict.fromkeys(r["model"] for r in rows):
        sel = [r for r in rows if r["model"] == model]
        ar = [int(r["ar_tokens"]) for r in sel]
        en = [int(r["en_tokens"]) for r in sel]
        out[model] = {
            "articles": len(sel),
            "ar_tokens_total": sum(ar),
            "en_tokens_total": sum(en),
            "ttr": ttr(ar, en),
            "median_article_ratio": median_ratio(ar, en),
            "min_article_ratio": min(a / e for a, e in zip(ar, en)),
            "max_article_ratio": max(a / e for a, e in zip(ar, en)),
        }
    return out
