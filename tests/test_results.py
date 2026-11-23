"""Published results must be recomputable from raw measurements."""

import json
import statistics
from collections import defaultdict

import pytest

from atti import pipeline
from tests.conftest import ROOT

CSV = ROOT / "results" / "pilot.csv"
SUMMARY = ROOT / "results" / "pilot_summary.json"


@pytest.mark.skipif(not CSV.exists(), reason="run `uv run atti pilot` first")
def test_aggregates_recompute_from_csv():
    rows = pipeline.read_csv(CSV)
    summary = json.loads(SUMMARY.read_text())
    by_model = defaultdict(list)
    for r in rows:
        by_model[r["model"]].append((int(r["ar_tokens"]), int(r["en_tokens"])))
        assert abs(float(r["ar_en_ratio"]) - int(r["ar_tokens"]) / int(r["en_tokens"])) < 5e-5
    assert set(by_model) == set(summary["models"])
    for model, pairs in by_model.items():
        s = summary["models"][model]
        assert len(pairs) == 10
        assert s["ar_tokens_total"] == sum(a for a, _ in pairs)
        assert s["en_tokens_total"] == sum(e for _, e in pairs)
        assert s["ttr"] == sum(a for a, _ in pairs) / sum(e for _, e in pairs)
        assert s["median_article_ratio"] == statistics.median(a / e for a, e in pairs)


@pytest.mark.network
@pytest.mark.skipif(not CSV.exists(), reason="run `uv run atti pilot` first")
def test_fresh_measurement_matches_published_csv(pairs, manifest):
    from tests.conftest import HF

    rows, _ = pipeline.measure(pairs, manifest, HF)
    assert pipeline.rows_to_csv(rows) == CSV.read_text(encoding="utf-8")


@pytest.mark.skipif(not CSV.exists(), reason="run `uv run atti pilot` first")
def test_report_contains_published_numbers():
    summary = json.loads(SUMMARY.read_text())
    report = (ROOT / "reports" / "pilot.md").read_text(encoding="utf-8")
    for s in summary["models"].values():
        assert f"{s['ttr']:.4f}" in report
        assert str(s["ar_tokens_total"]) in report
