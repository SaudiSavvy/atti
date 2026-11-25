"""Published results are validated before writing and never dropped, changed or downgraded."""

import json
import shutil

import pytest

from atti import frontier as F
from atti import gemini as G
from atti import v2
from tests.conftest import ROOT

ARTICLES = ["1", "2", "3"]
MANIFEST = {"articles": [{"key": k} for k in ARTICLES]}
PATHS = {"csv": "r.csv", "summary": "s.json", "pilot": "p.json", "manifest": "m.json"}


def row(model_key, article, ar=30, en=20, method=F.API_INPUT):
    return {"model": model_key, "model_key": model_key, "tokenizer_revision_or_api_model": model_key,
            "measurement_method": method, "article_id": f"A{article}", "article": article, "part": "1",
            "ar_sha256": "a" * 64, "en_sha256": "b" * 64, "ar_chars": "10", "en_chars": "10",
            "ar_tokens": str(ar), "en_tokens": str(en), "ar_en_ratio": f"{ar / en:.4f}",
            "adapter_version": "1.0", "measurement_meta": ""}


def csv_text(rows):
    import csv
    import io

    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=F.CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def model(key, **kw):
    return [row(key, a, **kw) for a in ARTICLES]


@pytest.fixture
def published(tmp_path):
    """A published frontier-style result set with a local and an API model, both MEASURED."""
    files = {"csv": csv_text(model("local", method=F.RAW_CONTENT) + model("api")),
             "summary": "{}\n",
             "pilot": F.dumps({"adapters": {"local": {"passed": True, "counts": {"1": [3, 2]}},
                                            "api": {"passed": True, "counts": {"1": [9, 8]}}}}),
             "manifest": F.dumps({"adapters": {"local": {"status": "MEASURED"}, "api": {"status": "MEASURED"}}})}
    for k, text in files.items():
        (tmp_path / PATHS[k]).write_text(text, encoding="utf-8")
    return tmp_path, files


def snapshot(root):
    return {k: (root / p).read_bytes() for k, p in PATHS.items() if (root / p).exists()}


def test_partial_run_cannot_drop_a_published_model(published):
    """The original bug: a run without API credentials replaced complete results with local-only rows."""
    root, files = published
    before = snapshot(root)
    partial = dict(files, csv=csv_text(model("local", method=F.RAW_CONTENT)),
                   pilot=F.dumps({"adapters": {"local": {"passed": True, "counts": {"1": [3, 2]}}}}),
                   manifest=F.dumps({"adapters": {"local": {"status": "MEASURED"},
                                                  "api": {"status": "BLOCKED"}}}))
    with pytest.raises(F.PublishedResultsError) as exc:
        F.publish(root, PATHS, partial, MANIFEST)
    msg = str(exc.value)
    assert "api: its 3 published rows would be removed" in msg
    assert "api: its recorded passing pilot would be removed or changed" in msg
    assert "api: published as MEASURED, would become BLOCKED" in msg
    assert snapshot(root) == before  # nothing written, not even the files that would not change


def test_published_values_cannot_change(published):
    root, files = published
    before = snapshot(root)
    changed = dict(files, csv=csv_text(model("local", method=F.RAW_CONTENT) + model("api", ar=31)))
    with pytest.raises(F.PublishedResultsError, match="api: its published rows would change"):
        F.publish(root, PATHS, changed, MANIFEST)
    assert snapshot(root) == before


@pytest.mark.parametrize("bad", [
    {"article": "4"},                     # not a corpus article
    {"ar_tokens": "0", "ar_en_ratio": "0.0000"},  # non-positive count
    {"en_tokens": "x"},                   # not an integer
    {"ar_en_ratio": "9.9999"},            # ratio inconsistent with counts
    {"measurement_method": "estimated"},  # unknown method
])
def test_invalid_rows_are_rejected_before_writing(tmp_path, bad):
    rows = model("new")
    rows[0].update(bad)
    with pytest.raises(F.PublishedResultsError, match="new"):
        F.publish(tmp_path, PATHS, {"csv": csv_text(rows)}, MANIFEST)
    assert not any(tmp_path.iterdir())


def test_missing_article_is_rejected(tmp_path):
    with pytest.raises(F.PublishedResultsError, match="do not cover exactly the 3 corpus articles"):
        F.publish(tmp_path, PATHS, {"csv": csv_text(model("new")[:2])}, MANIFEST)


def test_identical_rewrite_and_new_models_are_allowed(published):
    root, files = published
    F.publish(root, PATHS, files, MANIFEST)  # offline replay: byte-identical rewrite
    assert snapshot(root) == {k: v.encode() for k, v in files.items()}
    more = dict(files, csv=csv_text(model("local", method=F.RAW_CONTENT) + model("api") + model("extra")),
                manifest=F.dumps({"adapters": {"local": {"status": "MEASURED"}, "api": {"status": "MEASURED"},
                                               "extra": {"status": "MEASURED"}}}))
    F.publish(root, PATHS, more, MANIFEST)
    assert (root / PATHS["csv"]).read_text() == more["csv"]
    assert not list(root.glob("*.tmp"))


def test_single_adapter_manifest_cannot_be_downgraded(tmp_path):
    """Gemini's manifest is one adapter record: `--pilot-only` must not turn MEASURED into VALIDATED."""
    (tmp_path / PATHS["manifest"]).write_text(F.dumps({"key": "gemini-4-neon", "status": "MEASURED"}))
    with pytest.raises(F.PublishedResultsError, match="gemini-4-neon: published as MEASURED, would become VALIDATED"):
        F.publish(tmp_path, PATHS, {"manifest": F.dumps({"key": "gemini-4-neon", "status": "VALIDATED"})},
                  MANIFEST)


def test_committed_results_pass_validation():
    manifest = json.loads((ROOT / v2.MANIFEST_PATH).read_text(encoding="utf-8"))
    for rel in (F.OUTPUTS["csv"], G.OUTPUTS["csv"]):
        rows = F._csv_rows((ROOT / rel).read_text(encoding="utf-8"))
        assert F.validate_rows(rows, manifest) == [], rel


# ---------------------------------------------------------------- end to end on a copy of the repository

def _copy(tmp_path, rels, data_dirs):
    for rel in rels:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    (tmp_path / "data").mkdir(exist_ok=True)
    for d in data_dirs:
        (tmp_path / "data" / d).symlink_to(ROOT / "data" / d, target_is_directory=True)
    return tmp_path


@pytest.mark.network
@pytest.mark.parametrize("pilot_only", [False, True])
def test_frontier_without_credentials_or_cache_leaves_published_results(tmp_path, monkeypatch, pilot_only):
    for v in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    root = _copy(tmp_path, [v2.MANIFEST_PATH, v2.OUTPUTS["csv"], *F.OUTPUTS.values()], ("raw_v2", "hf_frontier"))
    assert not (root / F.API_CACHE).exists()
    with pytest.raises(F.PublishedResultsError, match="claude-opus-5-5: .*would be removed"):
        F.run(root, pilot_only=pilot_only)
    for rel in F.OUTPUTS.values():
        assert (root / rel).read_bytes() == (ROOT / rel).read_bytes(), rel


@pytest.mark.network
@pytest.mark.skipif(not (ROOT / G.CACHE).exists(), reason="the Gemini cache is a local, untracked file")
def test_gemini_pilot_only_cannot_downgrade_published_manifest(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    root = _copy(tmp_path, [v2.MANIFEST_PATH, G.FRONTIER_PILOT, G.FRONTIER_SUMMARY, *G.OUTPUTS.values()],
                 ("raw_v2",))
    (root / G.CACHE).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / G.CACHE, root / G.CACHE)
    with pytest.raises(F.PublishedResultsError, match="published as MEASURED, would become VALIDATED"):
        G.run(root, pilot_only=True)
    for rel in G.OUTPUTS.values():
        assert (root / rel).read_bytes() == (ROOT / rel).read_bytes(), rel
