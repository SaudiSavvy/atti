"""Task 12 regressions: manifest verification rejects bad manifests; parser fixes; limitations kept."""

import copy
import json

import pytest

from atti import corpus, hrsd, v2
from tests.conftest import ROOT

MANIFEST = json.loads((ROOT / v2.MANIFEST_PATH).read_text(encoding="utf-8"))
NOWHERE = ROOT / "data" / "does-not-exist"  # structural checks must fail before any source is read


def mutated(fn):
    m = copy.deepcopy(MANIFEST)
    fn(m)
    return m


def _dup_key(m):
    m["articles"][1] = copy.deepcopy(m["articles"][0])
    m["selection"]["selected"][1] = m["selection"]["selected"][0]


def _dup_id_only(m):
    m["articles"][1]["id"] = m["articles"][0]["id"]


def _set(path, value):
    def f(m):
        *head, last = path
        obj = m
        for p in head:
            obj = obj[p]
        obj[last] = value
    return f


BAD = {
    "not an object": (lambda m: None, ["x"]),
    "empty article list": (_set(["articles"], []), None),
    "missing article list": (lambda m: m.pop("articles"), None),
    "duplicate key": (_dup_key, None),
    "duplicate id": (_dup_id_only, None),
    "malformed ar hash": (_set(["articles", 0, "ar_sha256"], "abc"), None),
    "uppercase en hash": (lambda m: m["articles"][0].update(en_sha256=m["articles"][0]["en_sha256"].upper()), None),
    "missing field": (lambda m: m["articles"][0].pop("en_sha256"), None),
    "wrong type": (_set(["articles", 0, "ar_chars"], "120"), None),
    "bool as int": (_set(["articles", 0, "part"], True), None),
    "id/key mismatch": (_set(["articles", 0, "id"], "KSA-LL-v2-999999"), None),
    "malformed key": (lambda m: (m["articles"][0].update(key="x1"), m["selection"]["selected"].__setitem__(0, "x1")), None),
    "non-positive chars": (_set(["articles", 0, "en_chars"], 0), None),
    "inadmissible status": (_set(["articles", 0, "review_status"], "FAIL"), None),
    "selection mismatch": (lambda m: m["selection"]["selected"].reverse(), None),
    "article dropped": (lambda m: m["articles"].pop(), None),
    "excluded article listed": (lambda m: m["selection"]["excluded_after_review"].update({m["articles"][0]["key"]: "x"}), None),
    "ineligible candidate": (lambda m: m["candidates"][m["articles"][0]["key"]].update(eligible=False), None),
    "part disagrees": (lambda m: m["articles"][0].update(part=m["articles"][0]["part"] + 1), None),
    "wrong corpus": (_set(["corpus"], "expanded_v1"), None),
    "pdf hash malformed": (_set(["sources", "ar_pdf", "sha256"], "nope"), None),
}


def test_committed_manifest_is_valid():
    assert v2.validate_manifest(MANIFEST) == []


@pytest.mark.parametrize("name", BAD)
def test_verify_rejects_malformed_manifests(name):
    fn, replacement = BAD[name]
    m = replacement[0] if replacement else mutated(fn)
    assert v2.validate_manifest(m), name
    with pytest.raises(v2.VerificationError, match="malformed manifest"):
        v2.verify(m, NOWHERE)


def test_empty_and_duplicate_manifests_no_longer_pass():
    """The audited defect: verify() returned [] for an empty list and accepted duplicates."""
    with pytest.raises(v2.VerificationError, match="empty"):
        v2.verify({**MANIFEST, "articles": [], "selection": {**MANIFEST["selection"], "selected": []}}, NOWHERE)
    with pytest.raises(v2.VerificationError, match="duplicate"):
        v2.verify(mutated(_dup_key), NOWHERE)


@pytest.mark.parametrize("manifest,msg", [
    ({"articles": []}, "empty"),
    ({}, "empty"),
    ({"articles": [{"article": 1}, {"article": 1}]}, "duplicate"),
    ({"articles": [{"article": "1"}]}, "integer"),
])
def test_v1_verify_rejects_empty_and_duplicate_manifests(manifest, msg):
    with pytest.raises(corpus.VerificationError, match=msg):
        corpus.verify(manifest, NOWHERE)


@pytest.mark.network
def test_verify_rejects_metadata_inconsistent_with_sources():
    m = mutated(lambda m: m["articles"][0].update(ar_chars=m["articles"][0]["ar_chars"] + 1))
    with pytest.raises(v2.VerificationError, match="character counts or part"):
        v2.verify(m)


@pytest.mark.network
def test_verify_rejects_text_hash_mismatch():
    m = mutated(lambda m: m["articles"][0].update(ar_sha256="0" * 64))
    with pytest.raises(v2.VerificationError, match="hash mismatch"):
        v2.verify(m)


# ---------------------------------------------------------------- parser fixes (offline)

@pytest.mark.parametrize("heading,number,bis", [
    ("Article 79:(Bis)", 79, True),      # as published for Article 79 bis (was parsed as 79)
    ("Article 79: (Bis)", 79, True),
    ("Article 79:", 79, False),
    ("Article 11 Bis:", 11, True),
    ("Article 131 (Bis):", 131, True),
    ("Article (75):", 75, False),
])
def test_english_bis_headings(heading, number, bis):
    _, n, b, rest = hrsd._split_heading(heading, "en")
    assert (n, b, rest) == (number, bis, "")


def test_english_bis_after_colon_in_page():
    page = ("<main><div><h4>Article 79:</h4><p>first text</p><h4>Article 79:(Bis)</h4><p>second text</p>"
            "<h4>Article 80:</h4><p>third</p></div></main>")
    arts = hrsd.parse_html_articles(page, "en")
    assert [(a.number, a.bis, a.text) for a in arts] == [(79, False, "first text"), (79, True, "second text"),
                                                          (80, False, "third")]
    assert hrsd.numbering_report(arts)["duplicates"] == []


def test_pdf_small_font_whitespace_span_kept():
    spans = [{"text": "كلمة", "size": 12.0}, {"text": " ", "size": 10.56}, {"text": "أخرى", "size": 12.0},
             {"text": "3", "size": 8.4}]
    size, text, marker = hrsd.line_text(spans)
    assert (size, text, marker) == (12.0, "كلمة أخرى", "3")  # space kept, footnote marker dropped


# ---------------------------------------------------------------- corpus impact (committed manifest)

def test_newly_eligible_articles_recorded_outside_frozen_draw():
    sel = MANIFEST["selection"]
    assert set(sel["eligible_outside_draw"]) == set(v2.OUTSIDE_DRAW) == {"33", "79", "79bis"}
    for k in v2.OUTSIDE_DRAW:
        assert MANIFEST["candidates"][k] == {**MANIFEST["candidates"][k], "eligible": True, "reasons": []}
        assert k not in sel["selected"]
    assert sel["eligible_total"] == sel["pool_size"] + len(v2.OUTSIDE_DRAW) == 175
    assert "79" not in MANIFEST["anomalies"]["en_duplicate_labels"]
    assert "79bis" in MANIFEST["anomalies"]["en_bis_found"]


def test_measured_pairs_unchanged_by_fixes():
    # the 100 keys and text hashes measured before the fixes (the frozen pair set)
    pinned = json.loads((ROOT / "tests" / "current_law_v2_pairs_frozen.json").read_text())
    assert [(a["key"], a["ar_sha256"], a["en_sha256"]) for a in MANIFEST["articles"]] == \
        [tuple(x) for x in pinned]


def test_source_alignment_limitations_preserved():
    review = json.loads((ROOT / v2.REVIEW_PATH).read_text(encoding="utf-8"))
    assert "not a legal translation equivalence benchmark" in review["research_scope"]
    lim = {d["article"]: d for d in review["source_alignment_limitations"]}
    assert set(lim) == {"34", "35", "108"}
    keys = {a["key"]: a for a in MANIFEST["articles"]}
    for k, d in lim.items():
        assert k in keys and keys[k]["review_status"] == "NEEDS_REVIEW"  # retained, not hidden
        assert d["finding"] and d["category"] in review["discrepancy_categories"]
        assert len(d["ar_excerpt"]) < 40
    assert "independent audit" in lim["34"]["finding_origin"]
    report = (ROOT / v2.OUTPUTS["report"]).read_text(encoding="utf-8")
    assert "Source-alignment limitations" in report and "Research scope" in report


@pytest.mark.network
def test_selection_reproduces_with_frozen_pool():
    recs, anomalies = v2.build_records(v2.load(ROOT / v2.RAW))
    assert v2.curated_selection(recs) == {k: MANIFEST["selection"][k] for k in v2.curated_selection(recs)}
    assert anomalies == MANIFEST["anomalies"]
