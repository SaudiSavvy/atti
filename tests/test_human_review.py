"""Structured human review records: findings, retrospective review periods, AI-flag adjudication.

Toy articles and placeholder notes only; no finding about a real article is written here."""

import json

import pytest

from atti import cli, corpus, review
from tests.conftest import ROOT

MANIFEST = {"corpus": "toy", "articles": [{"article": 1, "id": "T-1"}, {"article": 2, "id": "T-2"}]}
H = "f" * 64
BASE = {"decision": "APPROVE", "reviewer": "SaudiSavvy", "date": "2026-12-01", "comment": ""}


def errors(entry, flagged=()):
    dec = review.decisions_template("toy", MANIFEST, H)
    dec["decisions"]["1"] = {**BASE, **entry}
    return review.validate_decisions(dec, MANIFEST, H, flagged)


def test_committed_decision_files_remain_valid():
    for name, ai_rel in (("expanded_v1", "review/expanded_v1_ai_review.json"),
                         ("current_law_v2", "manifest/current_law_v2_review.json")):
        m_path = ROOT / "manifest" / f"{name}_manifest.json"
        dec = corpus.read_json(ROOT / "review" / f"{name}_human_decisions.json")
        flagged = review.flagged_articles(corpus.read_json(ROOT / ai_rel))
        assert review.validate_decisions(dec, corpus.read_json(m_path), review.manifest_sha256(m_path),
                                         flagged) == [], name


def test_full_record_with_retrospective_review_period():
    assert errors({"review_period": "2026-11-20/2026-11-23", "equivalence": "MINOR_DIFFERENCES",
                   "terminology": "note T", "discrepancies": [{"severity": "MINOR", "note": "note D"}],
                   "comment": "note C"}) == []
    assert errors({"review_period": "2026-11-21"}) == []  # a single day


@pytest.mark.parametrize("period", ["2026-12-02", "2026-11-30/2026-12-05",  # after the recording date
                                    "2026-11-23/2026-11-20", "Nov 2026", "2026-11-20/21/22", 7])
def test_review_period_must_be_a_valid_interval_before_recording(period):
    assert any("review_period" in e for e in errors({"review_period": period}))


@pytest.mark.parametrize("entry, message", [
    ({"equivalence": "SIMILAR"}, "equivalence must be one of"),
    ({"discrepancies": [{"severity": "MAJOR", "note": "n"}]}, "discrepancies must be"),
    ({"discrepancies": [{"severity": "MINOR", "note": " "}]}, "discrepancies must be"),
    ({"discrepancies": [{"severity": "MATERIAL", "note": "n"}], "equivalence": "MINOR_DIFFERENCES"},
     "requires equivalence MATERIAL_DIFFERENCE"),
    ({"equivalence": "MATERIAL_DIFFERENCE", "comment": "c"}, "requires at least one MATERIAL"),
    ({"equivalence": "EQUIVALENT", "discrepancies": [{"severity": "MINOR", "note": "n"}]}, "use MINOR_DIFFERENCES"),
    ({"equivalence": "MATERIAL_DIFFERENCE", "discrepancies": [{"severity": "MATERIAL", "note": "n"}]},
     "justify the decision in comment"),
    ({"terminology": ["x"]}, "terminology must be text"),
    ({"ai_adjudication": {"verdict": "MAYBE", "note": "n"}}, "ai_adjudication must be"),
    ({"ai_adjudication": {"verdict": "AGREE", "note": ""}}, "ai_adjudication must be"),
    ({"confidence": "high"}, "unknown fields"),
])
def test_inconsistent_or_malformed_findings_rejected(entry, message):
    assert any(message in e for e in errors(entry)), errors(entry)


def test_material_difference_can_still_be_retained_with_justification():
    """Inclusion follows the research scope (texts as published), so APPROVE with a justified material
    difference is allowed; the record states both."""
    assert errors({"equivalence": "MATERIAL_DIFFERENCE", "comment": "note C",
                   "discrepancies": [{"severity": "MATERIAL", "note": "note D"}]}) == []


def test_ai_flagged_article_needs_human_adjudication():
    assert any("ai_adjudication is required" in e for e in errors({}, flagged=["1"]))
    assert errors({"ai_adjudication": {"verdict": "DISAGREE", "note": "note A"}}, flagged=["1"]) == []
    assert errors({}, flagged=["2"]) == []  # other articles are unaffected


def test_findings_require_a_recorded_decision():
    dec = review.decisions_template("toy", MANIFEST, H)
    dec["decisions"]["2"]["equivalence"] = "EQUIVALENT"
    assert any("need a recorded decision" in e for e in review.validate_decisions(dec, MANIFEST, H))


def test_decisions_stay_bound_to_the_manifest_hash():
    dec = review.decisions_template("toy", MANIFEST, H)
    dec["decisions"]["1"] = dict(BASE)
    assert any("manifest_sha256 does not match" in e for e in review.validate_decisions(dec, MANIFEST, "e" * 64))


def _repo(tmp_path, monkeypatch, ai_articles):
    (tmp_path / "manifest").mkdir()
    (tmp_path / "review").mkdir()
    m_path = tmp_path / "manifest" / "expanded_v1_manifest.json"
    m_path.write_text(json.dumps(MANIFEST))
    dec_path = tmp_path / "review" / "expanded_v1_human_decisions.json"
    dec_path.write_text(json.dumps(review.decisions_template("toy", MANIFEST, review.manifest_sha256(m_path))))
    (tmp_path / "review" / "expanded_v1_ai_review.json").write_text(json.dumps({"articles": ai_articles}))
    monkeypatch.chdir(tmp_path)
    return dec_path


def test_cli_records_structured_retrospective_decision(tmp_path, monkeypatch):
    dec_path = _repo(tmp_path, monkeypatch, {"1": {"proposed_status": "PASS"}, "2": {"proposed_status": "PASS"}})
    assert cli.main(["decide", "1", "APPROVE", "--reviewer", "SaudiSavvy", "--date", "2026-12-01",
                     "--review-period", "2026-11-20/2026-11-23", "--equivalence", "MINOR_DIFFERENCES",
                     "--terminology", "note T", "--discrepancy", "minor: note D"]) == 0
    entry = json.loads(dec_path.read_text())["decisions"]["1"]
    assert entry == {"decision": "APPROVE", "reviewer": "SaudiSavvy", "date": "2026-12-01", "comment": "",
                     "review_period": "2026-11-20/2026-11-23", "equivalence": "MINOR_DIFFERENCES",
                     "terminology": "note T", "discrepancies": [{"severity": "MINOR", "note": "note D"}]}
    assert json.loads(dec_path.read_text())["decisions"]["2"] == {"decision": None, "reviewer": None,
                                                                  "date": None, "comment": ""}


def test_cli_requires_adjudication_for_ai_flagged_articles(tmp_path, monkeypatch, capsys):
    dec_path = _repo(tmp_path, monkeypatch, {"1": {"proposed_status": "NEEDS_REVIEW"},
                                             "2": {"proposed_status": "PASS"}})
    before = dec_path.read_text()
    assert cli.main(["decide", "1", "APPROVE", "--reviewer", "SaudiSavvy"]) == 2
    assert "ai_adjudication is required" in capsys.readouterr().err and dec_path.read_text() == before
    assert cli.main(["decide", "1", "APPROVE", "--reviewer", "SaudiSavvy", "--ai-adjudication", "note A"]) == 2
    assert cli.main(["decide", "1", "APPROVE", "--reviewer", "SaudiSavvy",
                     "--ai-adjudication", "partly_agree: note A"]) == 0
    assert json.loads(dec_path.read_text())["decisions"]["1"]["ai_adjudication"] == \
        {"verdict": "PARTLY_AGREE", "note": "note A"}


def test_findings_are_kept_verbatim_in_the_markdown_sheet():
    dec = review.decisions_template("toy", MANIFEST, H)
    dec["decisions"]["1"] = {**BASE, "terminology": "<script>x</script>",
                             "discrepancies": [{"severity": "MINOR", "note": "<b>n</b>"}]}
    cell = review._human_cell(dec["decisions"]["1"])
    assert "terminology: <script>x</script>" in cell and "MINOR discrepancy: <b>n</b>" in cell  # local text file
