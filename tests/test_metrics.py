import pytest

from atti.metrics import article_ratio, median_ratio, summarize, ttr


def test_ttr_is_ratio_of_sums_not_mean_of_ratios():
    assert ttr([10, 30], [10, 10]) == 2.0
    assert median_ratio([10, 30], [10, 10]) == 2.0
    assert ttr([1, 9], [1, 1]) == 5.0


def test_median_odd():
    assert median_ratio([1, 2, 9], [1, 1, 1]) == 2.0


def test_guards():
    with pytest.raises(ValueError):
        article_ratio(5, 0)
    with pytest.raises(ValueError):
        ttr([], [])
    with pytest.raises(ValueError):
        ttr([1], [1, 2])


def test_summarize_per_model():
    rows = [
        {"model": "a", "ar_tokens": "4", "en_tokens": "2"},
        {"model": "a", "ar_tokens": "2", "en_tokens": "2"},
        {"model": "b", "ar_tokens": 3, "en_tokens": 1},
    ]
    s = summarize(rows)
    assert s["a"]["ar_tokens_total"] == 6 and s["a"]["en_tokens_total"] == 4
    assert s["a"]["ttr"] == 1.5 and s["a"]["median_article_ratio"] == 1.5
    assert s["b"]["ttr"] == 3.0
