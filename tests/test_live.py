"""verify-live classification, with all network responses mocked.

Offline tests use a synthetic three-article "law" (Arabic HTML + English
text); PDF decoding is replaced by plain-text parsing so no real PDF or
legal text is needed. The ``network`` test replays the real cached sources.
"""

import json
import urllib.error
from pathlib import Path

import pytest

from atti import cli, corpus, english, live, sources

ORD = {1: "الأولى", 2: "الثانية", 3: "الثالثة"}


def ar_html(arts: dict[int, tuple[str, bool]]) -> bytes:
    items = "".join(
        f'<div class="article_item no_alternate {"changed-article" if amended else ""}">'
        f'<h3 class="center">المادة {ORD[n]} :</h3>'
        f'<p><div class="HTMLContainer">{text}</div></p></div>'
        for n, (text, amended) in arts.items())
    return f"<html>{items}</html>".encode()


def en_text(arts: dict[int, str], appendix: str) -> bytes:
    body = "".join(f"Article {n}\n{t}\n\n" for n, t in arts.items())
    return f"Labor Law\n{body}Appendix\n{appendix}\n".encode()


AR = {1: ("نص المادة الأولى.", False), 2: ("نص معدل.", True), 3: ("نص المادة الثالثة.", False)}
EN = {1: "Text of article one.", 2: "Amended text.", 3: "Text of article three."}
APPX = "Amending Article 2 to read as follows."


@pytest.fixture
def law(tmp_path, monkeypatch):
    monkeypatch.setattr(english, "parse_pdf", lambda p: english.parse_text(Path(p).read_text()))
    base = tmp_path / "raw"
    base.mkdir()
    (base / sources.ARABIC.filename).write_bytes(ar_html(AR))
    (base / sources.ENGLISH.filename).write_bytes(en_text(EN, APPX))
    log = {k: {"retrieved_at_utc": "t", "sha256": "x"} for k in ("ar", "en")}
    review = {"articles": {"1": "same", "3": "same"}}
    manifest = corpus.build_manifest(base, [1, 3], review, log)
    snapshot = {p.name: p.read_bytes() for p in base.iterdir()}
    return base, manifest, snapshot


def serve(ar: bytes, en: bytes):
    return lambda url: {sources.ARABIC.url: ar, sources.ENGLISH.url: en}[url]


def statuses(report):
    return {s.article: (s.status, s.detail) for s in report.articles}


def test_unchanged_sources_are_clean(law):
    base, manifest, snapshot = law
    r = live.verify_live(manifest, base, serve(ar_html(AR), en_text(EN, APPX)))
    assert r.outcome == live.CLEAN and r.source_changes == [] and r.errors == []
    assert statuses(r) == {1: ("ok", ""), 3: ("ok", "")}
    assert {p.name: p.read_bytes() for p in base.iterdir()} == snapshot  # baseline untouched


def test_modified_selected_article_is_changed(law):
    base, manifest, snapshot = law
    ar = {**AR, 3: ("نص المادة الثالثة المعدل.", False)}
    r = live.verify_live(manifest, base, serve(ar_html(ar), en_text(EN, APPX)))
    assert r.outcome == live.ARTICLES_FAILED
    assert statuses(r)[3] == ("changed", "ar text") and statuses(r)[1][0] == "ok"
    assert any("Arabic articles changed" in c for c in r.source_changes)
    assert {p.name: p.read_bytes() for p in base.iterdir()} == snapshot


def test_missing_selected_article(law):
    base, manifest, _ = law
    ar = {k: v for k, v in AR.items() if k != 3}
    r = live.verify_live(manifest, base, serve(ar_html(ar), en_text(EN, APPX)))
    assert r.outcome == live.ARTICLES_FAILED
    assert statuses(r)[3] == ("missing", "not found in: ar")


def test_new_amendment_makes_article_ineligible(law):
    base, manifest, _ = law
    r = live.verify_live(manifest, base, serve(
        ar_html(AR), en_text(EN, APPX + "\nAmending Article 3 to read as follows.")))
    assert r.outcome == live.ARTICLES_FAILED
    assert statuses(r)[3] == ("ineligible", "English appendix references it")
    assert any("en_appendix_article_refs: added [3]" in c for c in r.source_changes)


def test_change_outside_selection_is_source_level_only(law):
    base, manifest, _ = law
    en = {**EN, 2: "Amended text, revised again."}
    r = live.verify_live(manifest, base, serve(ar_html(AR), en_text(en, APPX)))
    assert r.outcome == live.SOURCE_CHANGED
    assert all(s.status == "ok" for s in r.articles)
    assert any("English PDF bytes changed" in c for c in r.source_changes)
    assert any("English articles changed vs cached baseline: [2]" in c for c in r.source_changes)


def test_unparseable_source_is_verification_failure_not_network(law):
    base, manifest, _ = law
    r = live.verify_live(manifest, base, serve(ar_html(AR), b"<html>Service page</html>"))
    assert r.outcome == live.ARTICLES_FAILED
    assert r.errors and "could not be parsed" in r.errors[0]


def test_network_failure_raises(law):
    base, manifest, snapshot = law

    def down(url):
        raise sources.NetworkError("timed out")
    with pytest.raises(sources.NetworkError):
        live.verify_live(manifest, base, down)
    assert {p.name: p.read_bytes() for p in base.iterdir()} == snapshot


def test_without_baseline_cache_only_notes(law, tmp_path):
    _, manifest, _ = law
    r = live.verify_live(manifest, tmp_path / "absent", serve(ar_html(AR), en_text(EN, APPX)))
    assert r.outcome == live.CLEAN and r.notes


@pytest.mark.parametrize("command", ["verify-live", "pilot"])
def test_cli_network_failure_exit_code(tmp_path, monkeypatch, command, capsys):
    (tmp_path / "manifest").mkdir()
    (tmp_path / "manifest" / "pilot_manifest.json").write_text(json.dumps({"articles": []}))
    monkeypatch.chdir(tmp_path)

    def offline(*a, **k):
        raise urllib.error.URLError("network unreachable")
    monkeypatch.setattr("urllib.request.urlopen", offline)
    assert cli.main([command]) == 3
    assert "NETWORK ERROR" in capsys.readouterr().err
    assert not (tmp_path / "data" / "raw" / sources.ARABIC.filename).exists()


@pytest.mark.network
def test_real_sources_replayed(raw_dir, manifest):
    ar = (raw_dir / sources.ARABIC.filename).read_bytes()
    en = (raw_dir / sources.ENGLISH.filename).read_bytes()
    r = live.verify_live(manifest, raw_dir, serve(ar, en))
    assert r.outcome == live.CLEAN, live.format_report(r)

    # Tamper with one word of Article 4's Arabic body (word chosen at runtime,
    # so no legal text is embedded in this repository).
    article4 = next(e for e in manifest["articles"] if e["article"] == 4)
    heading_at = ar.index(article4["ar_heading"].split(" :")[0].encode())
    word = corpus.verify(manifest, raw_dir)[0].ar_text.split()[-1].encode()
    at = ar.index(word, heading_at)
    tampered = ar[:at] + word.decode()[::-1].encode() + ar[at + len(word):]
    r = live.verify_live(manifest, raw_dir, serve(tampered, en))
    assert r.outcome == live.ARTICLES_FAILED
    assert statuses(r)[4] == ("changed", "ar text")
    assert all(s.status == "ok" for s in r.articles if s.article != 4)
