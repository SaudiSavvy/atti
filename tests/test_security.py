"""Security and integrity guards: tokenizer pins, official-host allowlists, review-page escaping,
pseudonymous reviewers and the pdfminer.six floor (all offline)."""

import importlib.metadata
import io
import json
import urllib.request

import httpx
import pytest

from atti import cli, hrsd, review, sources, tokenization
from atti.corpus import ArticlePair
from tests.conftest import ROOT

# ---------------------------------------------------------------- F1: tokenizer SHA-256 pins


def test_tokenizer_pins_equal_the_published_summaries():
    for f in ("pilot_summary.json", "expanded_v1_summary.json", "current_law_v2_summary.json"):
        published = {t["model"]: (t["revision"], t["tokenizer_json_sha256"])
                     for t in json.loads((ROOT / "results" / f).read_text())["tokenizers"]}
        assert published == {s.repo_id: (s.revision, s.sha256) for s in tokenization.TOKENIZERS}, f


def test_tampered_tokenizer_is_rejected_before_parsing(tmp_path, monkeypatch):
    bad = tmp_path / "tokenizer.json"
    bad.write_text('{"model": "tampered"}')
    monkeypatch.setattr("huggingface_hub.hf_hub_download", lambda **kw: str(bad))

    def never(*a, **k):
        raise AssertionError("a tokenizer that fails its pin must not be parsed")
    monkeypatch.setattr(tokenization.Tokenizer, "from_str", never)
    with pytest.raises(tokenization.TokenizerIntegrityError, match="SHA-256 .* != pinned"):
        tokenization.load(tokenization.TOKENIZERS[0], tmp_path)


@pytest.mark.parametrize("command, target", [("pilot", "atti.pipeline.run"), ("v2", "atti.v2.run")])
def test_cli_reports_tokenizer_mismatch_as_verification_failure(monkeypatch, capsys, command, target):
    def tampered(*a, **k):
        raise tokenization.TokenizerIntegrityError("tokenizer.json: SHA-256 x != pinned y")
    monkeypatch.setattr(target, tampered)
    assert cli.main([command]) == cli.EXIT_VERIFICATION
    assert "VERIFICATION FAILED" in capsys.readouterr().err


# ---------------------------------------------------------------- F2: official HTTPS hosts only

@pytest.mark.parametrize("url", ["https://www.hrsd.gov.sa/a", "https://www.hrsd.gov.sa:443/a?x=1#y",
                                 "https://WWW.HRSD.GOV.SA/a"])
def test_official_host_accepted(url):
    assert sources.require_https_host(url, hrsd.HOST) == url


@pytest.mark.parametrize("url", [
    "http://www.hrsd.gov.sa/a",                 # not HTTPS
    "https://hrsd.gov.sa/a",                    # different host
    "https://www.hrsd.gov.sa.evil.example/a",   # look-alike suffix
    "https://evil.example/www.hrsd.gov.sa",     # host only in the path
    "https://user@www.hrsd.gov.sa/a",           # credentials
    "https://www.hrsd.gov.sa:8443/a",           # non-default port
    "javascript:alert(1)", "//www.hrsd.gov.sa/a", "https://[::1/a",
])
def test_other_urls_refused(url):
    with pytest.raises(sources.UntrustedURLError):
        sources.require_https_host(url, hrsd.HOST)


def test_hrsd_redirect_off_host_is_blocked_before_the_request(tmp_path, monkeypatch):
    """The production client (its own hooks and settings) never contacts a redirect target off the host."""
    seen = []

    def handler(req):
        seen.append(req.url.host)
        if req.url.host == hrsd.HOST:
            return httpx.Response(302, headers={"location": "https://evil.example/x"})
        return httpx.Response(200, content=b"attacker content")

    real = httpx.Client

    class MockedClient(real):
        def __init__(self, **kw):
            super().__init__(transport=httpx.MockTransport(handler), **kw)
    monkeypatch.setattr(httpx, "Client", MockedClient)
    f = hrsd.Fetcher(tmp_path, sleep=lambda s: None, clock=lambda: 0.0)
    with pytest.raises(sources.UntrustedURLError, match="evil.example"):
        f.fetch("en/index.html", "https://www.hrsd.gov.sa/index")
    assert seen == [hrsd.HOST] and not (tmp_path / "en" / "index.html").exists()


def test_hrsd_request_url_checked_before_any_request(tmp_path):
    class NoNetwork:
        def get(self, url):
            raise AssertionError("no request may be made")
    f = hrsd.Fetcher(tmp_path, client=NoNetwork(), sleep=lambda s: None, clock=lambda: 0.0)
    with pytest.raises(sources.UntrustedURLError):
        f.fetch("ar_html/part-01.html", "https://evil.example/part")  # e.g. a tampered x-default link


def test_hrsd_redirect_history_checked_for_injected_clients(tmp_path):
    class Resp:
        status_code, content, headers = 200, b"page", {}
        url = "https://www.hrsd.gov.sa/final"
        history = [type("Hop", (), {"url": "https://evil.example/hop"})()]

    class Client:
        def get(self, url):
            return Resp()
    f = hrsd.Fetcher(tmp_path, client=Client(), sleep=lambda s: None, clock=lambda: 0.0)
    with pytest.raises(sources.UntrustedURLError):
        f.fetch("a", "https://www.hrsd.gov.sa/a")
    assert not (tmp_path / "a").exists()


def test_boe_url_checked_before_any_request(monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("no request may be made")
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", no_network)
    with pytest.raises(sources.UntrustedURLError):
        sources.download("https://evil.example/labor-law.pdf")


def test_boe_redirect_off_host_refused():
    req = urllib.request.Request("https://laws.boe.gov.sa/Files/Download/?attId=x")
    handler = sources._OfficialHostRedirects()
    with pytest.raises(sources.UntrustedURLError):
        handler.redirect_request(req, io.BytesIO(), 302, "Found", {}, "https://evil.example/x.pdf")
    same = handler.redirect_request(req, io.BytesIO(), 302, "Found", {}, "https://laws.boe.gov.sa/y")
    assert same.full_url == "https://laws.boe.gov.sa/y"


def test_boe_final_url_checked(monkeypatch):
    class Resp(io.BytesIO):
        def geturl(self):
            return "https://evil.example/x.pdf"
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", lambda self, req, timeout=None: Resp(b"%PDF"))
    with pytest.raises(sources.UntrustedURLError):
        sources.download(sources.ENGLISH.url)


# ---------------------------------------------------------------- F3-F5: review page

MANIFEST = {"corpus": "toy", "articles": [{"article": 1, "id": "T-1", "ar_chars": 3, "en_chars": 3,
                                           "ar_sha256": "a" * 64, "en_sha256": "b" * 64}]}
PAIRS = [ArticlePair(1, "h", "نص", "text one")]


def ai_review(status="PASS"):
    return {"reviewer": "AI", "independence_caveat": "", "status_criteria": {}, "material_discrepancies": [],
            "no_fail_found": "", "articles": {"1": {"proposed_status": status, "evidence": "e"}}}


def page(ai=None, sources_html=None, flagged=()):
    return review.render_html(MANIFEST, PAIRS, {1: 1}, ai or ai_review(),
                              review.decisions_template("toy", MANIFEST, "f" * 64), [], list(flagged),
                              sources_html)


@pytest.mark.parametrize("url", ['https://www.hrsd.gov.sa/"><script>alert(1)</script>',
                                 "javascript:alert(1)", "https://evil.example/part",
                                 'https://www.hrsd.gov.sa/x" onmouseover="alert(1)'])
def test_hostile_source_urls_cannot_inject_markup(url):
    line = review.source_links([12], url, url)
    out = page(sources_html={"1": line})
    assert out.count("<script") == 2  # only the page's own two scripts, nothing injected
    assert 'href="javascript:' not in out and "evil.example" not in line.split("withheld")[0]
    assert "onmouseover=\"" not in out


def test_official_source_url_still_linked():
    url = "https://www.hrsd.gov.sa/en/part?a=1&b=2"
    assert review.source_links([3, 4], url, None) == \
        'Arabic PDF p. 3, 4 · <a href="https://www.hrsd.gov.sa/en/part?a=1&amp;b=2">English page</a> · ' \
        "Arabic HTML page: none"


@pytest.mark.parametrize("status", ['PASS"><script>alert(1)</script>', "APPROVED", None])
def test_unknown_proposed_status_rejected(status):
    with pytest.raises(ValueError, match="unknown AI proposed status"):
        page(ai_review(status))


@pytest.mark.parametrize("key", ["1'); alert(1); ('", "<b>1</b>"])
def test_unexpected_article_keys_rejected(key):
    with pytest.raises(ValueError, match="unexpected article key"):
        review.check_review_inputs(ai_review(), [key])


@pytest.mark.parametrize("status", review.REVIEW_STATUSES)
def test_every_documented_status_renders(status):
    assert f"AI proposed: {status}" in page(ai_review(status))


# ---------------------------------------------------------------- F7: pseudonymous reviewers

def _validate(reviewer):
    dec = review.decisions_template("toy", MANIFEST, "f" * 64)
    dec["decisions"]["1"].update(decision="APPROVE", reviewer=reviewer, date="2026-12-01")
    return review.validate_decisions(dec, MANIFEST, "f" * 64)


@pytest.mark.parametrize("reviewer", ["SaudiSavvy", "octocat", "Reviewer 7", "Claude Smith",
                                      "Research Assistant", "Ai Weiwei", "Kai"])
def test_pseudonyms_and_human_names_accepted(reviewer):
    assert _validate(reviewer) == []


@pytest.mark.parametrize("reviewer", ["Claude (AI agent)", "Claude Opus 5.5", "claude-opus-5-5", "gpt-6.2",
                                      "ChatGPT", "DeepSeek V4.1 Flash", "Gemini 4 Neon", "an LLM",
                                      "AI assistant", "AI", "review-bot", "Claude", "Assistant"])
def test_ai_systems_still_rejected(reviewer):
    assert any("not an AI system" in e for e in _validate(reviewer))


# ---------------------------------------------------------------- F8a: pdfminer.six floor

def test_pdfminer_six_is_not_a_vulnerable_release():
    """CVE-2025-64512 and CVE-2025-70559 are fixed in 20251230 (pdfminer.six uses date versions)."""
    assert int(importlib.metadata.version("pdfminer.six")) >= 20251230
