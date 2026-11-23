"""Deterministic, ratio-blind selection procedure (offline, synthetic pairs)."""

import random

from atti import selection
from atti.corpus import ArticlePair


def pair(n, ar_len, en="Plain English text."):
    return ArticlePair(n, f"h{n}", "ب" * ar_len, en)


def pool_fixture():
    # 60 articles over 6 Parts, Arabic lengths 10..600
    pairs = {n: pair(n, 10 * n) for n in range(1, 61)}
    parts = {n: 1 + (n - 1) // 10 for n in range(1, 61)}
    return pairs, parts


def test_selection_is_deterministic_and_order_independent():
    pairs, parts = pool_fixture()
    first = selection.select(pairs, parts, fixed=[1, 2])
    items = list(pairs.items())
    random.Random(7).shuffle(items)
    assert selection.select(dict(items), parts, fixed=[2, 1]) == first


def test_quotas_strata_and_fixed_articles():
    pairs, parts = pool_fixture()
    sel = selection.select(pairs, parts, fixed=[1, 2])
    added = sel["added"]
    assert len(added) == 20 and not {1, 2} & set(added)
    by_stratum = [v["stratum"] for v in added.values()]
    assert by_stratum.count("short") == 7 and by_stratum.count("medium") == 7 and by_stratum.count("long") == 6
    strata = selection.strata({n: p for n, p in pairs.items() if n not in (1, 2)})
    assert all(strata[n] == v["stratum"] for n, v in added.items())


def test_selection_ignores_english_text_and_ratios():
    """Only Arabic length and Part matter: rewriting the English side changes nothing."""
    pairs, parts = pool_fixture()
    other = {n: ArticlePair(n, p.ar_heading, p.ar_text, "x" * (n * 37 % 500 + 1)) for n, p in pairs.items()}
    assert selection.select(pairs, parts, [])["added"] == selection.select(other, parts, [])["added"]


def test_part_balance_spreads_sections():
    pairs, parts = pool_fixture()
    sel = selection.select(pairs, parts, fixed=[])
    counts = {}
    for v in sel["added"].values():
        counts[v["part"]] = counts.get(v["part"], 0) + 1
    assert len(counts) == 6  # every Part represented


def test_exclusion_rules():
    assert selection.exclusion_reason(pair(1, 50), part=11).startswith("Part 11")
    assert "Commissions" in selection.exclusion_reason(
        pair(2, 50, "a claim filed with the Commission"), part=5)
    assert "Commissions" in selection.exclusion_reason(
        ArticlePair(3, "h", "أمام هيئة تسوية الخلافات العمالية", "x"), part=5)
    # lower-case "commissions" (sales commissions) is a different meaning and stays eligible
    assert selection.exclusion_reason(pair(4, 50, "wage includes commissions on sales"), part=5) is None


def test_review_exclusion_removes_article(monkeypatch):
    pairs, parts = pool_fixture()
    chosen = list(selection.select(pairs, parts, [])["added"])
    monkeypatch.setitem(selection.EXCLUDED, chosen[0], "failed review: clause mismatch")
    sel = selection.select(pairs, parts, [])
    assert chosen[0] not in sel["added"]
    assert sel["excluded_from_pool"][chosen[0]] == "failed review: clause mismatch"
