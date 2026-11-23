"""expanded_v1 corpus: manifest integrity, review provenance, reproduction."""

import re
import unicodedata

import pytest

from atti import corpus, pipeline, selection, tokenization
from tests.conftest import HF, ROOT


@pytest.fixture(scope="module")
def expanded():
    return pipeline.load_published(ROOT, "expanded_v1")


@pytest.fixture(scope="module")
def pilot():
    return pipeline.load_published(ROOT, "pilot")


def test_thirty_unique_pairs_with_review_notes(expanded):
    m = expanded["manifest"]
    arts = [e["article"] for e in m["articles"]]
    assert len(arts) == 30 == len(set(arts))
    review = corpus.read_json(ROOT / "manifest" / "expanded_v1_review.json")
    assert set(review["articles"]) == {str(a) for a in arts}
    assert all(e["verification"]["content_review"] for e in m["articles"])


def test_pilot_entries_retained_unchanged(expanded, pilot):
    by_num = {e["article"]: e for e in expanded["manifest"]["articles"]}
    for e in pilot["manifest"]["articles"]:
        assert by_num[e["article"]] == e
    assert expanded["manifest"]["sources"] == pilot["manifest"]["sources"]
    assert expanded["manifest"]["extraction"] == pilot["manifest"]["extraction"]


def test_review_is_labelled_provisional_not_human_approved(expanded):
    prov = expanded["manifest"]["review_provenance"]
    assert prov["status"] == "provisional"
    assert prov["human_approval"].startswith("PENDING")
    assert "PROVISIONAL" in expanded["report_text"]
    assert "reviewed manually" not in expanded["report_text"]


def test_selection_record_is_consistent(expanded, pilot):
    m = expanded["manifest"]
    sel = m["selection"]
    added = sorted(int(n) for n in sel["added"])
    assert m["subsets"]["added_20"] == added and len(added) == 20
    assert m["subsets"]["pilot_10"] == sorted(e["article"] for e in pilot["manifest"]["articles"])
    strata = [v["stratum"] for v in sel["added"].values()]
    assert (strata.count("short"), strata.count("medium"), strata.count("long")) == (7, 7, 6)
    per_part = [v["part"] for v in sel["added"].values()]
    assert max(per_part.count(x) for x in set(per_part)) <= 3  # spread across sections
    excluded = {int(n) for n in sel["excluded_from_pool"]}
    audit = m["audit"]
    flagged = set(audit["ar_articles_marked_amended"]) | set(audit["en_appendix_article_refs"])
    assert not (excluded | flagged) & set(added)
    assert sel["seed"] == selection.SEED and sel["excluded_after_review"] == {}


# Published expanded_v1 aggregates (Task 04).
EXPANDED_PUBLISHED = {
    "Qwen/Qwen2.5-3B-Instruct": (2925, 2075, "1.4096"),
    "mistralai/Mistral-7B-Instruct-v0.3": (7161, 2236, "3.2026"),
}


def test_expanded_totals_pinned(expanded):
    import json
    s = json.loads(expanded["summary_text"])["models"]
    for model, (ar, en, ttr) in EXPANDED_PUBLISHED.items():
        assert (s[model]["ar_tokens_total"], s[model]["en_tokens_total"], f"{s[model]['ttr']:.4f}") == (ar, en, ttr)


def test_pilot_rows_identical_inside_expanded(expanded, pilot):
    key = lambda r: (r["model"], r["article_id"])  # noqa: E731
    exp = {key(r): r for r in expanded["rows"]}
    for r in pilot["rows"]:
        assert exp[key(r)] == r


# ---------------------------------------------------------------- needs cached sources

@pytest.fixture(scope="module")
def expanded_pairs(expanded, raw_dir):
    return corpus.verify(expanded["manifest"], raw_dir)


@pytest.mark.network
def test_selection_reproduces_from_sources(expanded, pilot, raw_dir):
    review = corpus.read_json(ROOT / "manifest" / "expanded_v1_review.json")
    log = corpus.read_json(raw_dir / "fetch_log.json")
    rebuilt = selection.expanded_manifest(raw_dir, pilot["manifest"], review, log)
    committed = expanded["manifest"]
    assert rebuilt["articles"] == committed["articles"]
    import json
    assert json.loads(json.dumps(rebuilt["selection"])) == committed["selection"]
    # all 30 articles span 13 Parts: every Part except 11 (excluded), 14 (repealed)
    # and 15 (no eligible articles)
    ar_articles, _ = corpus.load_sources(raw_dir)
    part = {a.number: a.part for a in ar_articles if not a.bis}
    assert {part[e["article"]] for e in committed["articles"]} == set(range(1, 17)) - {11, 14, 15}


@pytest.mark.network
def test_fresh_measurement_reproduces_expanded_csv(expanded, expanded_pairs):
    rows, _ = pipeline.measure(expanded_pairs, expanded["manifest"], HF)
    assert pipeline.rows_to_csv(rows) == expanded["csv_text"]


@pytest.mark.network
def test_numbers_in_arabic_appear_in_english(expanded_pairs):
    for p in expanded_pairs:
        assert set(re.findall(r"\d+", p.ar_text)) <= set(re.findall(r"\d+", p.en_text)), p.article


@pytest.mark.network
def test_coverage_and_no_special_tokens_all_thirty(expanded_pairs, tokenizers_loaded):
    for lt in tokenizers_loaded:
        specials = tokenization.special_ids(lt.tokenizer)
        norm = lt.tokenizer.normalizer
        for p in expanded_pairs:
            for text in (p.ar_text, p.en_text):
                enc = lt.tokenizer.encode(text, add_special_tokens=False)
                covered = set()
                for s, e in enc.offsets:
                    covered.update(range(s, e))
                assert covered == set(range(len(text))), (lt.spec.repo_id, p.article)
                assert not set(enc.ids) & specials and not enc.overflowing
                expected = norm.normalize_str(text) if norm else text
                assert lt.tokenizer.decode(enc.ids) == expected
                assert expected in (text, unicodedata.normalize("NFC", text))


@pytest.mark.network
def test_expanded_texts_not_in_repository(expanded_pairs):
    tracked = [p for p in ROOT.rglob("*") if p.is_file()
               and not {"data", ".venv", ".git", ".pytest_cache", "__pycache__"} & set(p.relative_to(ROOT).parts)]
    blob = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in tracked)
    for p in expanded_pairs:
        for text in (p.ar_text, p.en_text):
            for i in range(0, max(1, len(text) - 40), 20):
                assert text[i:i + 40] not in blob, f"Article {p.article} text found in repository"
