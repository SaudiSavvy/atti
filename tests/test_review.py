"""Human-validation materials: AI notes and human decisions stay separate."""

import copy
import subprocess

import pytest

from atti import corpus, review
from atti.corpus import ArticlePair
from tests.conftest import ROOT

MANIFEST = {"corpus": "toy", "articles": [{"article": 1, "id": "T-1", "ar_chars": 3, "en_chars": 3,
                                           "ar_sha256": "a" * 64, "en_sha256": "b" * 64},
                                          {"article": 2, "id": "T-2", "ar_chars": 3, "en_chars": 3,
                                           "ar_sha256": "c" * 64, "en_sha256": "d" * 64}]}
H = "f" * 64


def decided(**changes):
    dec = review.decisions_template("toy", MANIFEST, H)
    dec["decisions"]["1"].update(changes)
    return dec


def test_template_is_undecided_and_valid():
    dec = review.decisions_template("toy", MANIFEST, H)
    assert all(d["decision"] is None for d in dec["decisions"].values())
    assert review.validate_decisions(dec, MANIFEST, H) == []


def test_valid_human_decisions():
    dec = decided(decision="APPROVE", reviewer="A. Reviewer", date="2026-12-01")
    dec["decisions"]["2"].update(decision="REQUEST_EXAMINATION", reviewer="A. Reviewer",
                                 date="2026-12-01", comment="check item 1")
    assert review.validate_decisions(dec, MANIFEST, H) == []
    s = review.summarize({"articles": {"1": {"proposed_status": "PASS"}, "2": {"proposed_status": "PASS"}}}, dec)
    assert s["human"]["APPROVE"] == 1 and not s["fully_human_approved"]


@pytest.mark.parametrize("changes,msg", [
    ({"decision": "OK", "reviewer": "X", "date": "2026-12-01"}, "decision must be one of"),
    ({"decision": "APPROVE", "reviewer": "", "date": "2026-12-01"}, "reviewer name required"),
    ({"decision": "APPROVE", "reviewer": "Claude (AI agent)", "date": "2026-12-01"}, "not an AI system"),
    ({"decision": "APPROVE", "reviewer": "X", "date": "01/12/2026"}, "YYYY-MM-DD"),
    ({"decision": "REJECT", "reviewer": "X", "date": "2026-12-01", "comment": ""}, "comment required"),
])
def test_invalid_decisions_rejected(changes, msg):
    errors = review.validate_decisions(decided(**changes), MANIFEST, H)
    assert any(msg in e for e in errors), errors


def test_decisions_bound_to_manifest_version_and_articles():
    dec = review.decisions_template("toy", MANIFEST, H)
    assert any("another version" in e for e in review.validate_decisions(dec, MANIFEST, "0" * 64))
    del dec["decisions"]["2"]
    assert any("articles missing" in e for e in review.validate_decisions(dec, MANIFEST, H))


def test_existing_decisions_never_overwritten(tmp_path):
    path = tmp_path / "d.json"
    assert review.write_json_new(path, {"v": 1})
    assert not review.write_json_new(path, {"v": 2})
    assert path.read_text().strip().endswith("}") and '"v": 1' in path.read_text()


def test_sheet_never_claims_human_approval():
    ai = {"reviewer": "AI", "independence_caveat": "same model.", "status_criteria": {"PASS": "x"},
          "material_discrepancies": [], "no_fail_found": "none",
          "articles": {"1": {"proposed_status": "PASS", "evidence": "e"},
                       "2": {"proposed_status": "NEEDS_REVIEW", "evidence": "e"}}}
    pairs = [ArticlePair(1, "h", "نص <أ>", "text"), ArticlePair(2, "h", "نص", "text")]
    out = review.render_sheet(MANIFEST, pairs, {1: 1, 2: 1}, ai, review.decisions_template("toy", MANIFEST, H), [])
    assert "NOT human-approved" in out and out.count("_not recorded_") == 4
    assert "&lt;أ&gt;" in out  # texts are HTML-escaped


# ---------------------------------------------------------------- committed files

def test_committed_ai_review_covers_corpus():
    m = corpus.read_json(ROOT / "manifest" / "expanded_v1_manifest.json")
    ai = corpus.read_json(ROOT / "review" / "expanded_v1_ai_review.json")
    assert set(ai["articles"]) == {str(e["article"]) for e in m["articles"]}
    assert all(v["proposed_status"] in review.AI_STATUSES and v["evidence"] for v in ai["articles"].values())
    assert "NOT human" in ai["kind"] and "same AI model" in ai["independence_caveat"]
    for d in ai["material_discrepancies"]:
        assert ai["articles"][str(d["article"])]["proposed_status"] != "PASS"


def test_committed_human_decisions_valid_and_separate():
    m_path = ROOT / "manifest" / "expanded_v1_manifest.json"
    dec = corpus.read_json(ROOT / "review" / "expanded_v1_human_decisions.json")
    assert review.validate_decisions(dec, corpus.read_json(m_path), review.manifest_sha256(m_path)) == []
    assert "evidence" not in str(dec) and "proposed_status" not in str(dec)


@pytest.mark.network
def test_sheet_written_only_to_ignored_path(raw_dir, monkeypatch):
    from atti import cli

    monkeypatch.chdir(ROOT)
    assert cli.main(["review-sheet"]) == 0
    sheet = ROOT / "data" / "review" / "expanded_v1_review_sheet.md"
    assert sheet.exists()
    ignored = subprocess.run(["git", "check-ignore", "-q", str(sheet)], cwd=ROOT)
    assert ignored.returncode == 0


# ---------------------------------------------------------------- recording decisions

def test_record_decision_refuses_overwrite_and_ai():
    dec = review.decisions_template("toy", MANIFEST, H)
    once = review.record_decision(dec, MANIFEST, H, 1, "APPROVE", "A. Reviewer", "2026-12-01", "")
    assert dec["decisions"]["1"]["decision"] is None  # input untouched
    with pytest.raises(ValueError, match="already has a recorded decision"):
        review.record_decision(once, MANIFEST, H, 1, "REJECT", "A. Reviewer", "2026-12-02", "x")
    changed = review.record_decision(once, MANIFEST, H, 1, "REJECT", "A. Reviewer", "2026-12-02", "x", replace=True)
    assert changed["decisions"]["1"]["decision"] == "REJECT"
    with pytest.raises(ValueError, match="not an AI system"):
        review.record_decision(dec, MANIFEST, H, 2, "APPROVE", "Claude", "2026-12-01", "")
    with pytest.raises(ValueError, match="not in this corpus"):
        review.record_decision(dec, MANIFEST, H, 99, "APPROVE", "A. Reviewer", "2026-12-01", "")


def test_cli_decide_writes_only_valid_decisions(tmp_path, monkeypatch):
    import json

    from atti import cli

    (tmp_path / "manifest").mkdir()
    (tmp_path / "review").mkdir()
    m_path = tmp_path / "manifest" / "expanded_v1_manifest.json"
    m_path.write_text(json.dumps(MANIFEST))
    dec_path = tmp_path / "review" / "expanded_v1_human_decisions.json"
    dec_path.write_text(json.dumps(review.decisions_template("toy", MANIFEST, review.manifest_sha256(m_path))))
    monkeypatch.chdir(tmp_path)
    before = dec_path.read_text()
    assert cli.main(["decide", "1", "REJECT", "--reviewer", "A. Reviewer"]) == 2  # comment missing
    assert dec_path.read_text() == before
    assert cli.main(["decide", "1", "APPROVE", "--reviewer", "A. Reviewer", "--date", "2026-12-01"]) == 0
    assert json.loads(dec_path.read_text())["decisions"]["1"]["decision"] == "APPROVE"
    assert cli.main(["decide", "1", "REJECT", "--reviewer", "A. Reviewer", "--comment", "x"]) == 2
    assert json.loads(dec_path.read_text())["decisions"]["1"]["decision"] == "APPROVE"


def test_html_page_is_read_and_draft_only():
    ai = {"reviewer": "AI", "independence_caveat": "same model.", "status_criteria": {},
          "material_discrepancies": [{"article": 2, "issue": "scope"}], "no_fail_found": "",
          "articles": {"1": {"proposed_status": "PASS", "evidence": "e"},
                       "2": {"proposed_status": "NEEDS_REVIEW", "evidence": "e"}}}
    pairs = [ArticlePair(1, "h", "نص <أ>", "text one"), ArticlePair(2, "h", "نص", "text two")]
    out = review.render_html(MANIFEST, pairs, {1: 1, 2: 3}, ai,
                             review.decisions_template("toy", MANIFEST, H), [], flagged=[2])
    assert "nothing on this page is saved" in out and "NOT saved by this page" in out
    assert out.count('type="radio"') == 6 and " checked" not in out.replace(":checked", "")
    assert '<article id="a2" class="flagged"' in out and 'dir="rtl"' in out
    assert "&lt;أ&gt;" in out and "http" not in out and "localStorage" not in out
