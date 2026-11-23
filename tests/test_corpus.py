"""Integration tests against the cached official sources (downloaded on first run)."""

import copy

import pytest

from atti import corpus

pytestmark = pytest.mark.network


def test_every_article_verifies_against_sources(pairs, manifest):
    assert [p.article for p in pairs] == [a["article"] for a in manifest["articles"]]
    assert all(p.ar_text and p.en_text for p in pairs)


def test_hash_mismatch_is_detected(manifest, raw_dir):
    bad = copy.deepcopy(manifest)
    bad["articles"][0]["en_sha256"] = "0" * 64
    with pytest.raises(corpus.VerificationError):
        corpus.verify(bad, raw_dir)


def test_manifest_rebuild_is_identical(manifest, raw_dir):
    from tests.conftest import ROOT

    review = corpus.read_json(ROOT / "manifest" / "review.json")
    log = corpus.read_json(raw_dir / "fetch_log.json")
    # retrieval metadata is environment-specific; compare the verified content
    rebuilt = corpus.build_manifest(raw_dir, [a["article"] for a in manifest["articles"]], review, log)
    assert rebuilt["articles"] == manifest["articles"]
    assert rebuilt["sources"]["en"]["pdf_sha256"] == manifest["sources"]["en"]["pdf_sha256"]


def test_legal_texts_not_in_repository(pairs):
    from tests.conftest import ROOT

    tracked = [p for p in ROOT.rglob("*") if p.is_file()
               and not any(part in {"data", ".venv", ".git", ".pytest_cache", "__pycache__"}
                           for part in p.relative_to(ROOT).parts)]
    blob = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in tracked)
    for p in pairs:
        for text in (p.ar_text, p.en_text):
            snippet = text[:40]
            assert snippet not in blob, f"Article {p.article} text found in repository files"
