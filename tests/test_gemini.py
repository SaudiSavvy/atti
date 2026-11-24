"""Gemini 4 Neon adapter: request shape, strict validation, retries, credentials, isolation."""

import json
import shutil

import httpx
import pytest

from atti import frontier as F
from atti import gemini as G
from tests.conftest import ROOT

KEY = "AIza-TEST-SECRET-never-logged"
URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-4-neon:countTokens"


class Resp:
    def __init__(self, status, payload=None, raw=False, headers=None):
        self.status_code, self._payload, self._raw, self.headers = status, payload, raw, headers or {}

    def json(self):
        if self._raw:
            raise ValueError("not json")
        return self._payload


class Client:
    def __init__(self, script=None, fn=None):
        self.script, self.fn, self.calls = list(script or []), fn, []

    def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        if self.fn:
            return self.fn(url, headers, json)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def ok(n):
    return Resp(200, {"totalTokens": n, "promptTokensDetails": [{"modality": "TEXT", "tokenCount": n}]})


def live(script, sleeps=None):
    sleeps = [] if sleeps is None else sleeps
    return F.ApiCounter(G.GEMINI, key=KEY, client=Client(script), sleep=sleeps.append, clock=lambda: 0.0,
                        min_interval_s=G.MIN_INTERVAL_S, retries=G.RETRIES)


def test_identifier_endpoint_and_method():
    assert G.GEMINI.model == "gemini-4-neon" and G.GEMINI.provider == "google"
    assert G.GEMINI.endpoint == URL and G.GEMINI.env_var == "GEMINI_API_KEY"
    assert G.GEMINI.method == F.API_INPUT
    assert G.GEMINI not in F.ALL  # the frontier run (and its Anthropic/OpenAI calls) is untouched


def test_request_is_one_user_message_with_one_text_part():
    c = live([ok(38)])
    assert c.count("مرحبا بالعالم") == 38
    call = c._client.calls[0]
    assert call["url"] == URL and "key=" not in call["url"] and KEY not in call["url"]
    assert call["headers"]["x-goog-api-key"] == KEY
    assert call["json"] == {"contents": [{"role": "user", "parts": [{"text": "مرحبا بالعالم"}]}]}
    assert set(call["json"]) == {"contents"}  # no systemInstruction, tools, model or cachedContent


@pytest.mark.parametrize("status,payload,msg", [
    (401, {"error": {"code": 401, "status": "UNAUTHENTICATED", "message": f"bad key {KEY}"}}, "HTTP 401 \\(UNAUTHENTICATED\\)"),
    (403, {"error": {"code": 403, "status": "PERMISSION_DENIED", "message": "no access"}}, "HTTP 403 \\(PERMISSION_DENIED\\)"),
    (404, {"error": {"code": 404, "status": "NOT_FOUND", "message": "models/gemini-4-neon is not found"}}, "HTTP 404 \\(NOT_FOUND\\)"),
    (400, {"error": {"code": 400, "status": "INVALID_ARGUMENT"}}, "HTTP 400"),
])
def test_client_errors_fail_without_retry_or_leak(status, payload, msg):
    c = live([Resp(status, payload)])
    with pytest.raises(F.ApiError, match=msg) as exc:
        c.count("x")
    assert len(c._client.calls) == 1
    assert KEY not in str(exc.value) and "bad key" not in str(exc.value)  # provider messages not echoed
    assert KEY not in json.dumps(c.log) and KEY not in repr(c)


def test_non_json_error_body():
    c = live([Resp(403, raw=True)])
    with pytest.raises(F.ApiError, match="not JSON \\(HTTP 403\\)"):
        c.count("x")


@pytest.mark.parametrize("payload,msg", [
    ({}, "invalid totalTokens"),
    ({"totalTokens": 0}, "invalid totalTokens"),
    ({"totalTokens": -3}, "invalid totalTokens"),
    ({"totalTokens": "12"}, "invalid totalTokens"),
    ({"totalTokens": 12.0}, "invalid totalTokens"),
    ({"totalTokens": True}, "invalid totalTokens"),
    ({"totalTokens": 12, "cachedContentTokenCount": 4}, "cachedContentTokenCount"),
    ({"totalTokens": 12, "promptTokensDetails": [{"modality": "IMAGE", "tokenCount": 12}]}, "non-text"),
    ({"totalTokens": 12, "promptTokensDetails": "TEXT"}, "malformed promptTokensDetails"),
    ([12], "not a JSON object"),
])
def test_malformed_success_responses_rejected(payload, msg):
    c = live([Resp(200, payload)])
    with pytest.raises(F.ApiError, match=msg):
        c.count("x")


def test_minimal_valid_response_without_details():
    assert live([Resp(200, {"totalTokens": 5})]).count("x") == 5


@pytest.mark.parametrize("first", [Resp(429), Resp(429, headers={"retry-after": "7"}), Resp(500), Resp(502),
                                   Resp(503), Resp(504), httpx.ReadTimeout("slow")])
def test_rate_limit_server_and_transport_errors_retried(first):
    sleeps = []
    c = live([first, ok(9)], sleeps)
    assert c.count("x") == 9 and len(c._client.calls) == 2
    assert sleeps and sleeps[-1] in (1, 7.0)


def test_bounded_retries_then_explicit_failure():
    sleeps = []
    c = live([Resp(503)] * (G.RETRIES + 1), sleeps)
    with pytest.raises(F.ApiError, match="giving up after 7 attempts \\(HTTP 503\\)"):
        c.count("x")
    # exponential backoff 1, 2, ... 64 s (1 s also equals the rate-limit interval, so compare the rest)
    assert [s for s in sleeps if s > G.MIN_INTERVAL_S] == [2 ** i for i in range(1, G.RETRIES + 1)]


def test_rate_limiting_between_requests():
    t = iter([0.0, 0.2, 0.2])  # first request at t=0; second asked for at t=0.2
    sleeps = []
    c = F.ApiCounter(G.GEMINI, key=KEY, client=Client([ok(3), ok(4)]), sleep=sleeps.append,
                     clock=lambda: next(t), min_interval_s=1.0, retries=0)
    c.count("a"), c.count("b")
    assert sleeps == [pytest.approx(0.8)]


def test_blocked_without_key_and_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(G.GeminiBlocked, match="GEMINI_API_KEY is not set"):
        G.counter(tmp_path)


def test_cache_is_credential_free_and_write_once(tmp_path):
    c = G.counter(tmp_path, client=Client([ok(21)]), key=KEY)
    assert c.count("نص") == 21 and c.count("نص") == 21 and len(c.live._client.calls) == 1
    text = (tmp_path / G.CACHE).read_text()
    assert KEY not in text and "x-goog-api-key" not in text
    rec = next(iter(json.loads(text).values()))
    assert rec["request_shape"] == F.request_shape(G.GEMINI) and rec["model"] == "gemini-4-neon"
    assert rec["endpoint"] == URL and rec["measured_on"]


def test_pilot_articles_are_the_frontier_ten():
    from atti import v2

    m = json.loads((ROOT / v2.MANIFEST_PATH).read_text())
    keys = G.pilot_articles(ROOT, m)
    assert keys == json.loads((ROOT / G.FRONTIER_PILOT).read_text())["pilot_articles"] and len(keys) == 10


def test_pilot_detects_unstable_provider():
    n = iter(range(10, 100))
    c = live([], [])
    c._client.fn = lambda url, h, j: ok(next(n))
    assert not F.run_pilot("gemini-4-neon", c, {"1": ("a", "b")}).passed


# ---------------------------------------------------------------- mocked end-to-end (needs cached sources)

def fake_google(url, headers, body):
    assert url == URL and headers["x-goog-api-key"] == KEY
    text = body["contents"][0]["parts"][0]["text"]
    return ok(4 + len(text.encode("utf-8")) // 5)  # deterministic stand-in, never written to the repo


@pytest.fixture
def sandbox(tmp_path):
    from atti import v2

    for rel in (v2.MANIFEST_PATH, G.FRONTIER_PILOT, G.FRONTIER_SUMMARY):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    (tmp_path / "data").mkdir()
    (tmp_path / v2.RAW).symlink_to(ROOT / v2.RAW, target_is_directory=True)
    return tmp_path


@pytest.mark.network
def test_mocked_end_to_end_writes_only_gemini_outputs(sandbox):
    before = {p: p.read_bytes() for p in sandbox.rglob("*") if p.is_file() and "raw_v2" not in p.parts}
    client = Client(fn=fake_google)
    pilot = G.run(sandbox, pilot_only=True, client=client, key=KEY, sleep=lambda s: None)
    assert pilot["status"] == "VALIDATED" and not (sandbox / G.OUTPUTS["csv"]).exists()
    st = G.run(sandbox, client=client, key=KEY, sleep=lambda s: None)
    assert st["status"] == "MEASURED" and all(c["url"] == URL for c in client.calls)  # no other provider
    for p, b in before.items():
        assert p.read_bytes() == b  # manifest and frontier outputs untouched
    import csv

    rows = list(csv.DictReader((sandbox / G.OUTPUTS["csv"]).open(encoding="utf-8")))
    assert len(rows) == 100 and {r["measurement_method"] for r in rows} == {F.API_INPUT}
    assert {r["tokenizer_revision_or_api_model"] for r in rows} == {"gemini-4-neon"}
    man = json.loads((sandbox / G.OUTPUTS["manifest"]).read_text())
    assert man["framing_observations"]["inputs"][0]["text"] == "a" and man["count_field"] == "totalTokens"
    assert KEY not in "".join(p.read_text(errors="ignore") for p in sandbox.rglob("*.json") if "raw_v2" not in p.parts)
    report = (sandbox / G.OUTPUTS["report"]).read_text()
    assert "Methodological warning" in report and "raw_content_tokens" in report
    raw_rank = json.loads((sandbox / G.FRONTIER_SUMMARY).read_text())["models"]
    assert "gemini-4-neon" not in raw_rank
    # offline regeneration from the cache is byte-identical, with no requests, when bound to an anchor
    # pinned from these (mocked) results; the production anchor rejects this cache
    snapshot = {k: (sandbox / p).read_bytes() for k, p in G.OUTPUTS.items()}
    n = len(client.calls)
    with pytest.raises(F.CacheIntegrityError, match="pinned anchor"):
        G.run(sandbox, key="")
    assert {k: (sandbox / p).read_bytes() for k, p in G.OUTPUTS.items()} == snapshot  # nothing published
    pairs = {(r[f"{l}_sha256"], int(r[f"{l}_tokens"])) for r in rows for l in ("ar", "en")}
    own = {"articles_sha256": F.counts_digest(pairs), "texts": len(pairs), "source": "mocked run"}
    G.run(sandbox, key="", anchor=own)
    assert len(client.calls) == n
    produced = {k: (sandbox / p).read_bytes() for k, p in G.OUTPUTS.items()}
    assert {k: v for k, v in produced.items() if k not in ("manifest", "report")} == \
        {k: v for k, v in snapshot.items() if k not in ("manifest", "report")}
    man2 = json.loads(produced["manifest"])
    assert man2["cache_evidence"]["anchor"]["source"] == "mocked run"  # replay states its anchor
    assert {k: v for k, v in man2.items() if k != "cache_evidence"} == \
        {k: v for k, v in json.loads(snapshot["manifest"]).items() if k != "cache_evidence"}


# ---------------------------------------------------------------- P1 regressions on the Gemini runner

def test_gemini_anchor_reproduces_committed_results():
    import csv

    rows = list(csv.DictReader((ROOT / G.OUTPUTS["csv"]).open(encoding="utf-8")))
    pairs = {(r[f"{l}_sha256"], int(r[f"{l}_tokens"])) for r in rows for l in ("ar", "en")}
    assert F.counts_digest(pairs) == G.GEMINI_ANCHOR["articles_sha256"] and len(pairs) == 200


def _real_sandbox(tmp_path):
    from atti import v2

    for rel in [v2.MANIFEST_PATH, G.FRONTIER_PILOT, G.FRONTIER_SUMMARY, *G.OUTPUTS.values()]:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / rel, tmp_path / rel)
    (tmp_path / "data").mkdir()
    (tmp_path / v2.RAW).symlink_to(ROOT / v2.RAW, target_is_directory=True)
    (tmp_path / G.CACHE).parent.mkdir(parents=True)
    shutil.copy(ROOT / G.CACHE, tmp_path / G.CACHE)
    return tmp_path


REAL_CACHE = (ROOT / G.CACHE).exists()


@pytest.mark.network
@pytest.mark.skipif(not REAL_CACHE, reason="the Gemini cache is a local, untracked file")
def test_gemini_offline_replay_is_byte_identical(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    root = _real_sandbox(tmp_path)
    assert G.run(root)["status"] == "MEASURED"
    for rel in G.OUTPUTS.values():
        assert (root / rel).read_bytes() == (ROOT / rel).read_bytes(), rel


@pytest.mark.network
@pytest.mark.skipif(not REAL_CACHE, reason="the Gemini cache is a local, untracked file")
@pytest.mark.parametrize("corrupt,msg", [({"model": "WRONG", "input_tokens": 123456}, "model 'WRONG'"),
                                         ({"input_tokens": 123456}, "pinned anchor|disagrees")])
def test_gemini_corrupted_cache_fails_without_publishing(tmp_path, monkeypatch, corrupt, msg):
    """Audit regression: model=WRONG, input_tokens=123456 was published as MEASURED."""
    import csv

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    root = _real_sandbox(tmp_path)
    data = json.loads((root / G.CACHE).read_text())
    row = next(csv.DictReader((ROOT / G.OUTPUTS["csv"]).open(encoding="utf-8")))
    data[row["ar_sha256"]].update(corrupt)
    (root / G.CACHE).write_text(json.dumps(data))
    with pytest.raises(F.CacheIntegrityError, match=msg):
        G.run(root)
    for rel in G.OUTPUTS.values():
        assert (root / rel).read_bytes() == (ROOT / rel).read_bytes()  # nothing published


@pytest.mark.network
def test_gemini_pilot_stale_7_live_9_9_is_a_controlled_failure(sandbox):
    """Audit regression: pilot saw 9, 9 while the cache (and so the publication) held 7."""
    import hashlib

    from atti import v2

    m = json.loads((sandbox / v2.MANIFEST_PATH).read_text())
    recs = {r.key: r for r in v2.verify(m, sandbox / v2.RAW)}
    text = recs[G.pilot_articles(sandbox, m)[0]].ar_text
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (sandbox / G.CACHE).parent.mkdir(parents=True, exist_ok=True)
    (sandbox / G.CACHE).write_text(json.dumps({sha: F.new_record(G.GEMINI, sha, 7)}))
    client = Client(fn=lambda url, h, j: ok(9))
    with pytest.raises(F.CacheIntegrityError, match="holds 7, new observation is 9"):
        G.run(sandbox, client=client, key=KEY, sleep=lambda s: None)
    assert not any((sandbox / p).exists() for p in G.OUTPUTS.values())  # nothing published
    assert json.loads((sandbox / G.CACHE).read_text())[sha]["input_tokens"] == 7  # not overwritten


@pytest.mark.network
def test_gemini_published_values_equal_pilot_observations(sandbox):
    import csv

    G.run(sandbox, client=Client(fn=fake_google), key=KEY, sleep=lambda s: None)
    pilot = json.loads((sandbox / G.OUTPUTS["pilot"]).read_text())["adapter"]["counts"]
    rows = {r["article"]: r for r in csv.DictReader((sandbox / G.OUTPUTS["csv"]).open(encoding="utf-8"))}
    for art, (ar, en) in pilot.items():
        assert [int(rows[art]["ar_tokens"]), int(rows[art]["en_tokens"])] == [ar, en]
    man = json.loads((sandbox / G.OUTPUTS["manifest"]).read_text())
    assert man["cache_evidence"]["anchor"] is None and man["cache_evidence"]["provenance_limitations"] == []
