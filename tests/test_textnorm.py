from atti.textnorm import normalize_ws


def test_collapses_layout_whitespace_only():
    assert normalize_ws("  a\n b\t\tc d  ") == "a b c d"


def test_preserves_punctuation_and_arabic_marks():
    s = "ألَّا يزيد، «نص» (10%) – “quoted” ."
    assert normalize_ws(s) == s
