"""current_law_v2: eligibility, selection, QA checks, artifacts, reproducibility, immutability."""

import csv
import hashlib
import io
import json
import random
import statistics
from fractions import Fraction

import pytest

from atti import hrsd, review, tokenization, v2
from tests.conftest import HF, ROOT

# ---------------------------------------------------------------- historical immutability

def _sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def test_historical_artifacts_unchanged():
    pinned = json.loads((ROOT / "tests" / "historical_sha256.json").read_text())
    assert set(pinned) >= {"results/pilot.csv", "results/expanded_v1.csv", "manifest/expanded_v1_manifest.json"}
    for path, digest in pinned.items():
        assert _sha(path) == digest, f"historical artifact changed: {path}"


# ---------------------------------------------------------------- eligibility (synthetic)

def src_fixture(**over):
    A = hrsd.PdfArticle
    H = hrsd.HtmlArticle
    pdf = [A("المادة الأولى:", 1, False, "نص أ", [5], 1), A("المادة الثانية:", 2, False, "(ملغاة)", [5], 1),
           A("المادة الثالثة:", 3, False, "نص ج", [6], 1), A("المادة الرابعة:", 4, False, "نص د", [6], 1),
           A("المادة الخامسة:", 5, False, "نص ه", [6], 1), A("المادة السادسة:", 6, False, "نص و", [7], 2),
           A("المادة السابعة:", 7, False, "نص ز", [7], 1)]
    en = {"1": [(1, H("Article 1:", 1, False, "text a", 0))],
          "2": [(1, H("Article 2:", 2, False, "(Repealed)", 1))],
          "4": [(1, H("Article 4:", 4, False, "text d", 2)), (1, H("Article 4:", 4, False, "dup", 3))],
          "5": [(1, H("Article 5:", 5, False, "text e", 4))],
          "6": [(2, H("Article 6:", 6, False, "(Repealed)", 5))],
          "7": [(2, H("Article 7:", 7, False, "text g", 6))]}
    ar_html = {"1": "نص أ", "2": "(ملغاة)", "3": "نص ج", "4": "نص د", "5": "نص ه مختلف", "6": "نص و", "7": "نص ز"}
    s = {"pdf": pdf, "en": en, "ar_html": ar_html, "en_order": [a for v in en.values() for _, a in v],
         "urls": {1: ("en1", "ar1"), 2: ("en2", "ar2")}}
    s.update(over)
    return s


def test_eligibility_reasons_are_explicit_and_nothing_is_repaired():
    recs, anomalies = v2.build_records(src_fixture())
    r = {k: x.reasons for k, x in recs.items()}
    assert recs["1"].eligible and r["1"] == []
    assert r["2"][0].startswith("REPEALED")
    assert r["3"][0].startswith("MISSING_SOURCE")
    assert r["4"][0].startswith("NUMBERING") and anomalies["en_duplicate_labels"] == ["4"]
    assert r["5"][0].startswith("AR_UNCONFIRMED")
    assert any(x.startswith("VERSION_MISMATCH") for x in r["6"])  # English repealed, Arabic in force
    assert any("Part 2, Arabic in Part 1" in x for x in r["7"])   # misaligned source structure


# ---------------------------------------------------------------- selection

def records(n=60):
    recs = {}
    for i in range(1, n + 1):
        recs[str(i)] = v2.Record(str(i), 1 + i % 5, "h", "ب" * (i * 7 % 300 + 10), [1], "x", ["Article"],
                                 "e" * (i * 13 % 400 + 5), "u", "u", eligible=True)
    return recs


def test_selection_deterministic_order_independent_and_token_blind():
    recs = records()
    a = v2.select(recs, {}, target=20)
    items = list(recs.items())
    random.Random(3).shuffle(items)
    assert v2.select(dict(items), {}, target=20) == a
    other = {k: v2.Record(**{**r.__dict__, "en_text": "x" * 999}) for k, r in recs.items()}
    assert v2.select(other, {}, target=20)["selected"] == a["selected"]  # English never consulted
    assert len(a["selected"]) == 20 and set(a["quota_by_part"]) == {"1", "2", "3", "4", "5"}
    assert min(a["quota_by_part"].values()) >= v2.MIN_PER_PART


def test_selection_uses_only_eligible_and_honours_review_exclusions():
    recs = records()
    recs["7"].eligible = False
    a = v2.select(recs, {"8": "failed review"}, target=58)
    assert "7" not in a["selected"] and "8" not in a["selected"] and a["excluded_after_review"] == {"8": "failed review"}


def test_allocation_floor_and_total():
    q = v2.allocate({1: list("abcdefghij"), 2: list("ab"), 3: list("a")}, target=8)
    assert sum(q.values()) == 8 and q[3] == 1 and q[2] == 2


# ---------------------------------------------------------------- QA helpers

def test_number_extraction_including_words():
    assert {180.0, 12.0, 18.0, 72.0, 0.25} <= v2.ar_numbers("مائة وثمانين يوماً، إثنتي عشرة ساعة، الثامنة عشرة، إثنتين وسبعين، ربع الأجر")
    assert {180.0, 12.0, 72.0, 0.25, 100000.0} <= v2.en_numbers("one hundred and eighty days, twelve hours, seventy-two, one quarter, one hundred thousand Riyals")


def test_reference_extraction():
    assert v2.ar_refs("يستثنى من ذلك ما ورد في المادتين الخامسة والسبعين والسادسة بعد المائة من هذا النظام") == {75, 106}
    assert v2.en_refs("Articles 98 and 101 of this Law; Article (75)") == {98, 101, 75}
    c = v2.auto_checks(v2.Record("1", 1, "h", "طبقاً للمادة (السادسة والعشرين بعد المائة)، خلال ثلاثين يوماً", [1], None,
                                  ["Article 1:"], "under Article (126), within sixty days", "u", "u"))
    assert c["refs_mismatch"] == [] and 30.0 in c["numbers_ar_not_en"] and 60.0 in c["numbers_en_not_ar"]


# ---------------------------------------------------------------- committed artifacts (offline)

@pytest.fixture(scope="module")
def manifest():
    return json.loads((ROOT / v2.MANIFEST_PATH).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def review_file():
    return json.loads((ROOT / v2.REVIEW_PATH).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows():
    with (ROOT / v2.OUTPUTS["csv"]).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_manifest_integrity_and_provenance(manifest, review_file):
    arts = manifest["articles"]
    assert len(arts) == 100 == len({a["key"] for a in arts}) == len({a["id"] for a in arts})
    assert manifest["selection"]["selected"] == [a["key"] for a in arts]
    for a in arts:
        assert manifest["candidates"][a["key"]]["eligible"] and manifest["candidates"][a["key"]]["reasons"] == []
        assert a["review_status"] == review_file["articles"][a["key"]]["proposed_status"]
        assert a["review_status"] in ("PROPOSED_PASS", "NEEDS_REVIEW")
        assert a["en_url"].startswith("https://www.hrsd.gov.sa/en/") and a["ar_pdf_pages"]
        assert len(a["ar_sha256"]) == 64 and len(a["en_sha256"]) == 64
    assert manifest["sources"]["ar_pdf"]["sha256"] == "cfb8e0e6bb0176ebe045e38aed072fc4f7ce5c2f72ee796f4de0beb216c4b5d6"
    assert [t["revision"] for t in manifest["tokenizers"]] == [t.revision for t in tokenization.TOKENIZERS]
    assert len(manifest["candidates"]) == 249


def test_known_anomalies_recorded(manifest):
    an = manifest["anomalies"]
    assert {"10", "79", "194", "210"} <= set(an["en_duplicate_labels"])
    assert {"101", "197", "219"} <= set(an["en_missing"])
    for k in ("101", "197", "219", "79bis"):
        assert not manifest["candidates"][k]["eligible"]


def test_human_approval_pending_and_separate(manifest, review_file):
    assert manifest["status"] == "provisional" and manifest["human_approval"].startswith("PENDING")
    assert review_file["human_approval"].startswith("PENDING") and "NOT human" in review_file["kind"]
    m_path = ROOT / v2.MANIFEST_PATH
    dec = json.loads((ROOT / "review" / "current_law_v2_human_decisions.json").read_text())
    assert review.validate_decisions(dec, manifest, review.manifest_sha256(m_path)) == []
    assert "proposed_status" not in json.dumps(dec)
    report = (ROOT / v2.OUTPUTS["report"]).read_text(encoding="utf-8")
    assert "PROVISIONAL" in report and "human-approved" in report


PUBLISHED_V2 = {"Qwen/Qwen2.5-3B-Instruct": (10117, 7567), "mistralai/Mistral-7B-Instruct-v0.3": (24662, 8233)}


def test_results_recompute_independently(rows, manifest):
    summary = json.loads((ROOT / v2.OUTPUTS["summary"]).read_text())
    keys = [a["key"] for a in manifest["articles"]]
    for model, (ar_total, en_total) in PUBLISHED_V2.items():
        sel = [r for r in rows if r["model"] == model]
        assert [r["article"] for r in sel] == keys
        ar, en = [int(r["ar_tokens"]) for r in sel], [int(r["en_tokens"]) for r in sel]
        s = summary["models"][model]
        assert (sum(ar), sum(en)) == (ar_total, en_total) == (s["ar_tokens_total"], s["en_tokens_total"])
        assert s["ttr"] == float(Fraction(sum(ar), sum(en)))
        assert s["median_article_ratio"] == float(statistics.median(Fraction(a, e) for a, e in zip(ar, en)))
        for r in sel:
            assert r["ar_en_ratio"] == f"{int(r['ar_tokens']) / int(r['en_tokens']):.4f}"
        by_part = {}
        for r in sel:
            by_part.setdefault(r["part"], [0, 0])
            by_part[r["part"]][0] += int(r["ar_tokens"])
            by_part[r["part"]][1] += int(r["en_tokens"])
        assert {p: [v["ar_tokens_total"], v["en_tokens_total"]] for p, v in summary["by_part"][model].items()} == by_part


def test_summary_and_reports_regenerate_offline(rows, manifest, review_file):
    from atti import pipeline

    summary = json.loads((ROOT / v2.OUTPUTS["summary"]).read_text())
    assert v2.dumps(v2.summarize(rows, summary["tokenizers"])) == (ROOT / v2.OUTPUTS["summary"]).read_text()
    historic = {n: json.loads((ROOT / pipeline.CORPORA[n][2]).read_text())["models"] for n in ("pilot", "expanded_v1")}
    v1_rows = pipeline.read_csv(ROOT / "results" / "expanded_v1.csv")
    mig = json.loads((ROOT / v2.OUTPUTS["migration"]).read_text())
    assert v2.render_report(manifest, rows, summary, review_file, historic, v1_rows, mig) == \
        (ROOT / v2.OUTPUTS["report"]).read_text(encoding="utf-8")
    assert v2.render_sources_report(manifest) == (ROOT / v2.OUTPUTS["sources_report"]).read_text(encoding="utf-8")


def test_migration_record_covers_all_old_articles():
    mig = json.loads((ROOT / v2.OUTPUTS["migration"]).read_text())
    assert len(mig["old_articles"]) == 30
    s = mig["summary"]
    assert len(s["old_selected_in_v2"]) + len(s["old_eligible_not_selected"]) + len(s["old_excluded"]) == 30
    assert all(reasons for reasons in s["old_excluded"].values())


# ---------------------------------------------------------------- needs the pinned cache

@pytest.mark.network
def test_clean_reproduction_from_cache(manifest, rows):
    recs = v2.verify(manifest, ROOT / v2.RAW)
    new_rows, _ = v2.measure(recs, manifest, HF)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=v2.CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(new_rows)
    assert buf.getvalue() == (ROOT / v2.OUTPUTS["csv"]).read_text(encoding="utf-8")


@pytest.mark.network
def test_selection_and_candidates_reproduce_from_cache(manifest):
    src = v2.load(ROOT / v2.RAW)
    recs, anomalies = v2.build_records(src)
    sel = v2.select(recs, v2.EXCLUDED_AFTER_REVIEW)
    assert sel["selected"] == manifest["selection"]["selected"]
    assert {k: {"part": r.part, "eligible": r.eligible, "reasons": r.reasons} for k, r in recs.items()} == manifest["candidates"]
    assert anomalies == manifest["anomalies"]


@pytest.mark.network
def test_arabic_renderings_agree_for_every_selected_pair(manifest):
    recs, _ = v2.build_records(v2.load(ROOT / v2.RAW))
    for a in manifest["articles"]:
        r = recs[a["key"]]
        assert v2.strip_html_layout(r.ar_html_text) == r.ar_text


@pytest.mark.network
def test_no_v2_legal_text_in_repository(manifest):
    recs = v2.verify(manifest, ROOT / v2.RAW)
    skip = {"data", ".venv", ".git", ".pytest_cache", "__pycache__"}
    files = [p for p in ROOT.rglob("*") if p.is_file() and not skip & set(p.relative_to(ROOT).parts)]
    blob = "\n".join(" ".join(p.read_text(encoding="utf-8", errors="ignore").split()) for p in files)
    for r in recs:
        for text in (r.ar_text, r.en_text):
            for i in range(0, max(1, len(text) - 40), 20):
                assert text[i:i + 40] not in blob, f"Article {r.key} text found in repository"
