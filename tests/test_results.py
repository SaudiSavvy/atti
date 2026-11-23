"""Published results must exist and be recomputable from the raw measurements.

Everything here runs offline except the test marked ``network``. A missing
artifact is a test *failure* (never a skip).
"""

import csv
import io
import json
import statistics
from collections import defaultdict
from fractions import Fraction

import pytest

from atti import pipeline, report, tokenization
from tests.conftest import ROOT

# Published invariants (Task 01 baseline; results/pilot.csv pinned in tests/historical_sha256.json). Changing these requires a
# deliberate methodology change, never a test update to make a run pass.
PUBLISHED = {
    "Qwen/Qwen2.5-3B-Instruct": (1290, 898, "1.4365"),
    "mistralai/Mistral-7B-Instruct-v0.3": (3114, 982, "3.1711"),
}
CSV_HEADER = ["model", "revision", "article_id", "article", "ar_sha256", "en_sha256",
              "ar_chars", "en_chars", "ar_tokens", "en_tokens", "ar_en_ratio"]


@pytest.fixture(scope="module")
def published():
    return pipeline.load_published(ROOT)  # raises -> error, not skip, if anything is missing


def test_missing_artifacts_raise(tmp_path):
    with pytest.raises(FileNotFoundError, match="results/pilot.csv"):
        (tmp_path / "manifest").mkdir()
        (tmp_path / "manifest" / "pilot_manifest.json").write_text("{}")
        pipeline.load_published(tmp_path)


def test_csv_structure_matches_manifest_and_pins(published):
    rows = list(csv.reader(io.StringIO(published["csv_text"])))
    assert rows[0] == CSV_HEADER
    manifest = published["manifest"]
    expected_keys = [(t.repo_id, t.revision, e["id"])
                     for t in tokenization.TOKENIZERS for e in manifest["articles"]]
    assert [(r["model"], r["revision"], r["article_id"]) for r in published["rows"]] == expected_keys
    by_id = {e["id"]: e for e in manifest["articles"]}
    for r in published["rows"]:
        e = by_id[r["article_id"]]
        assert (int(r["article"]), r["ar_sha256"], r["en_sha256"], int(r["ar_chars"]), int(r["en_chars"])) == \
            (e["article"], e["ar_sha256"], e["en_sha256"], e["ar_chars"], e["en_chars"])
        assert int(r["ar_tokens"]) > 0 and int(r["en_tokens"]) > 0


def test_aggregates_recompute_independently(published):
    """Recompute from CSV integers with exact fractions, without atti.metrics."""
    per_model = defaultdict(list)
    for r in published["rows"]:
        a, e = int(r["ar_tokens"]), int(r["en_tokens"])
        per_model[r["model"]].append((a, e))
        assert r["ar_en_ratio"] == f"{a / e:.4f}"
    summary = json.loads(published["summary_text"])["models"]
    assert set(per_model) == set(summary) == set(PUBLISHED)
    for model, pairs in per_model.items():
        ar, en = sum(a for a, _ in pairs), sum(e for _, e in pairs)
        exact_ttr = Fraction(ar, en)
        exact_median = statistics.median(Fraction(a, e) for a, e in pairs)
        s = summary[model]
        assert (s["articles"], s["ar_tokens_total"], s["en_tokens_total"]) == (len(pairs), ar, en)
        assert s["ttr"] == float(exact_ttr)
        assert s["median_article_ratio"] == float(exact_median)
        assert s["min_article_ratio"] == float(min(Fraction(a, e) for a, e in pairs))
        assert s["max_article_ratio"] == float(max(Fraction(a, e) for a, e in pairs))
        assert (ar, en, f"{float(exact_ttr):.4f}") == PUBLISHED[model]


def test_summary_json_is_deterministic_function_of_csv(published):
    from atti import metrics

    stored = json.loads(published["summary_text"])
    rebuilt = {"tokenizers": stored["tokenizers"], "models": metrics.summarize(published["rows"])}
    assert pipeline.summary_to_json(rebuilt) == published["summary_text"]


def test_report_is_deterministic_function_of_artifacts(published):
    summary = json.loads(published["summary_text"])
    assert report.render(published["manifest"], published["rows"], summary) == published["report_text"]


@pytest.mark.network
def test_fresh_measurement_matches_published_csv(pairs, published):
    from tests.conftest import HF

    rows, _ = pipeline.measure(pairs, published["manifest"], HF)
    assert pipeline.rows_to_csv(rows) == published["csv_text"]
