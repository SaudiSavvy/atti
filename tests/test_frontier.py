"""Frontier tokenizers: identifiers, provenance, local counts, API handling, no fabricated values."""

import csv
import hashlib
import json
import re
import statistics
from fractions import Fraction

import httpx
import pytest

from atti import frontier as F
from atti import v2
from tests.conftest import ROOT

KEY = "sk-test-SECRET-never-logged"


# ---------------------------------------------------------------- identifiers and provenance

def test_exact_model_identifiers():
    assert [s.key for s in F.ALL] == ["deepseek-v4.1-flash-1017", "glm-5.3-flash", "kimi-k3.1-pro",
                                      "claude-opus-5-5", "gpt-6.2-sol"]
    assert [s.repo_id for s in F.LOCAL] == ["deepseek-ai/DeepSeek-V4.1-Flash-1017", "zai-org/GLM-5.3-Flash",
                                            "moonshotai/Kimi-K3.1-Pro"]
    assert (F.CLAUDE.model, F.GPT.model) == ("claude-opus-5-5", "gpt-6.2-sol")
    assert (F.CLAUDE.env_var, F.GPT.env_var) == ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def test_local_specs_pinned_and_asset_only():
    for s in F.LOCAL:
        assert re.fullmatch(r"[0-9a-f]{40}", s.revision) and s.method == F.RAW_CONTENT
        assert s.assets and all(re.fullmatch(r"[0-9a-f]{64}", d) for d in s.assets.values())
        assert set(s.assets) <= F.ASSET_ALLOWLIST
        assert not any(n.endswith(F.WEIGHT_SUFFIXES) for n in s.assets)
    assert all(s.method == F.API_INPUT for s in F.API)


def test_no_unauthorized_fallback_tokenizer():
    # Kimi's vocabulary comes from the K3.1 Pro repository itself, never another checkpoint
    assert F.KIMI.repo_id == "moonshotai/Kimi-K3.1-Pro" and "tiktoken.model" in F.KIMI.assets
    with pytest.raises(F.FrontierError, match="unknown adapter kind"):
        F.load_local(F.LocalSpec("x", "x", "a/b", "0" * 40, "other", {}, ""), ROOT / "data" / "unused")


def test_asset_hash_mismatch_is_fatal(tmp_path, monkeypatch):
    fake = tmp_path / "tokenizer.json"
    fake.write_text("{}")
    monkeypatch.setattr("huggingface_hub.hf_hub_download", lambda *a, **k: str(fake))
    with pytest.raises(F.AssetIntegrityError, match="SHA-256"):
        F.fetch_assets(F.GLM, tmp_path)
    bad = F.LocalSpec("x", "x", "a/b", "0" * 40, "tokenizers", {"model.safetensors": "0" * 64}, "")
    with pytest.raises(F.AssetIntegrityError, match="allow-listed"):
        F.fetch_assets(bad, tmp_path)


def test_kimi_split_rule_matches_official_algorithm():
    parts = list(F.split_whitespaces_or_nonwhitespaces("ab" * 6 + "   " + "c", 5))
    assert "".join(parts) == "ab" * 6 + "   " + "c"
    assert all(len(p) <= 5 or p.isspace() is False for p in parts)
    assert parts[0] == "ababa"


# ---------------------------------------------------------------- API adapters (mocked)

class Resp:
    def __init__(self, status, payload=None, raw=None, headers=None):
        self.status_code, self._payload, self._raw, self.headers = status, payload, raw, headers or {}

    def json(self):
        if self._raw is not None:
            raise ValueError("not json")
        return self._payload


class Client:
    def __init__(self, script):
        self.script, self.calls = list(script), []

    def post(self, url, headers=None, json=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def counter(spec, script):
    sleeps = []
    c = F.ApiCounter(spec, key=KEY, client=Client(script), sleep=sleeps.append, clock=lambda: 0.0)
    return c, sleeps


def test_api_request_shape_is_one_plain_user_message():
    c, _ = counter(F.CLAUDE, [Resp(200, {"input_tokens": 7})])
    assert c.count("نص") == 7
    call = c._client.calls[0]
    assert call["url"] == "https://api.anthropic.com/v1/messages/count_tokens"
    assert call["json"] == {"model": "claude-opus-5-5", "messages": [{"role": "user", "content": "نص"}]}
    assert call["headers"]["anthropic-version"] == F.ANTHROPIC_VERSION
    g, _ = counter(F.GPT, [Resp(200, {"object": "response.input_tokens", "input_tokens": 9})])
    assert g.count("text") == 9
    assert g._client.calls[0]["json"] == {"model": "gpt-6.2-sol", "input": [{"role": "user", "content": "text"}]}
    assert g._client.calls[0]["url"] == "https://api.openai.com/v1/responses/input_tokens"


@pytest.mark.parametrize("spec,resp,msg", [
    (F.CLAUDE, Resp(200, {}), "missing or invalid input_tokens"),
    (F.CLAUDE, Resp(200, {"input_tokens": 0}), "invalid input_tokens"),
    (F.CLAUDE, Resp(200, {"input_tokens": "12"}), "invalid input_tokens"),
    (F.CLAUDE, Resp(200, [1, 2]), "not a JSON object"),
    (F.CLAUDE, Resp(200, raw="<html>"), "not JSON"),
    (F.GPT, Resp(200, {"object": "error", "input_tokens": 5}), "unexpected object"),
    (F.GPT, Resp(401, {"error": {"message": "bad key"}}), "HTTP 401"),
    (F.GPT, Resp(404, {"error": {"message": "model not found"}}), "HTTP 404"),
])
def test_malformed_or_failed_responses_raise(spec, resp, msg):
    c, _ = counter(spec, [resp])
    with pytest.raises(F.ApiError, match=msg):
        c.count("text")
    assert len(c._client.calls) == 1  # client errors are not retried


def test_rate_limits_and_transport_errors_retry_with_backoff():
    c, sleeps = counter(F.CLAUDE, [Resp(429, headers={"retry-after": "3"}), httpx.ConnectError("reset"),
                                   Resp(503), Resp(200, {"input_tokens": 4})])
    assert c.count("x") == 4
    assert 3.0 in sleeps and 2 in sleeps and 4 in sleeps  # retry-after honoured, then 2**attempt


def test_gives_up_after_bounded_retries():
    c, _ = counter(F.GPT, [Resp(500)] * (F.ApiCounter.RETRIES + 1))
    with pytest.raises(F.ApiError, match="giving up"):
        c.count("x")


def test_credentials_never_exposed(monkeypatch):
    c, _ = counter(F.GPT, [Resp(401, {"error": {"message": f"key {KEY} rejected"}})])
    with pytest.raises(F.ApiError) as exc:
        c.count("x")
    assert KEY not in str(exc.value) and KEY not in repr(c) and KEY not in json.dumps(c.log)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(F.ApiError, match="OPENAI_API_KEY is not set"):
        F.ApiCounter(F.GPT)


def test_empty_text_refused_without_request():
    c, _ = counter(F.CLAUDE, [])
    with pytest.raises(F.ApiError, match="empty"):
        c.count("")
    assert c._client.calls == []


def test_api_cache_is_write_once_and_credential_free(tmp_path):
    cache = F.ApiCache(tmp_path / "c.json")
    live, _ = counter(F.CLAUDE, [Resp(200, {"input_tokens": 11})])
    cc = F.CachedApiCounter(F.CLAUDE, cache, live)
    assert cc.count("abc") == 11 and cc.count("abc") == 11  # second served from cache
    assert len(live._client.calls) == 1 and KEY not in (tmp_path / "c.json").read_text()
    sha = hashlib.sha256(b"abc").hexdigest()
    with pytest.raises(F.ApiError, match="not overwritten"):
        cache.put(sha, {"input_tokens": 12})
    offline = F.CachedApiCounter(F.CLAUDE, F.ApiCache(tmp_path / "empty.json"), None)
    with pytest.raises(F.ApiError, match="no cached count"):
        offline.count("abc")


def test_pilot_detects_instability_and_non_positive_counts():
    class Flaky:
        n = 0

        def count(self, text):
            self.n += 1
            return self.n

    assert not F.run_pilot("x", Flaky(), {"1": ("a", "b")}).passed
    assert F.run_pilot("x", type("Z", (), {"count": lambda self, t: 0})(), {"1": ("a", "b")}).error


def test_pilot_selection_token_blind_and_deterministic():
    m = json.loads((ROOT / v2.MANIFEST_PATH).read_text())
    keys = F.pilot_keys(m)
    assert len(keys) == len(set(keys)) == 10 and keys == F.pilot_keys(json.loads(json.dumps(m)))
    assert set(keys) <= {a["key"] for a in m["articles"]}


# ---------------------------------------------------------------- committed outputs

@pytest.fixture(scope="module")
def outputs():
    with (ROOT / F.OUTPUTS["csv"]).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return (rows, json.loads((ROOT / F.OUTPUTS["summary"]).read_text()),
            json.loads((ROOT / F.OUTPUTS["manifest"]).read_text()),
            json.loads((ROOT / F.OUTPUTS["pilot"]).read_text()))


def test_no_fabricated_values(outputs):
    rows, summary, fm, pilot = outputs
    measured = {k for k, st in fm["adapters"].items() if st["status"] == "MEASURED"}
    blocked = {k for k, st in fm["adapters"].items() if st["status"] == "BLOCKED"}
    assert {r["model_key"] for r in rows} == measured
    assert all(st.get("blocked_reason") for k, st in fm["adapters"].items() if k in blocked)
    for k in blocked:
        assert not any(s.get("model_key") == k for s in summary["models"].values())
        assert pilot["adapters"].get(k) is None or not pilot["adapters"][k]["passed"]
    assert all(int(r["ar_tokens"]) > 0 and int(r["en_tokens"]) > 0 for r in rows)
    assert set(fm["adapters"]) == {s.key for s in F.ALL}
    assert all(st["status"] in F.STATUSES for st in fm["adapters"].values())


def test_provenance_recorded_per_row(outputs):
    rows, _, fm, _ = outputs
    spec = {s.key: s for s in F.ALL}
    for r in rows:
        s = spec[r["model_key"]]
        assert r["measurement_method"] == s.method and r["adapter_version"] == F.ADAPTER_VERSION
        if isinstance(s, F.LocalSpec):
            assert r["tokenizer_revision_or_api_model"] == s.revision and r["model"] == s.repo_id
            assert s.revision[:12] in r["measurement_meta"]
        else:
            assert r["tokenizer_revision_or_api_model"] == s.model and "POST" in r["measurement_meta"]
    for k, st in fm["adapters"].items():
        if st["status"] in ("VALIDATED", "MEASURED") and k in {s.key for s in F.LOCAL}:
            assert {n: a["sha256"] for n, a in st["assets"].items()} == spec[k].assets


def test_one_common_set_of_100_articles(outputs):
    rows, summary, _, _ = outputs
    m = json.loads((ROOT / v2.MANIFEST_PATH).read_text())
    keys = [a["key"] for a in m["articles"]]
    by_id = {a["key"]: (a["id"], a["ar_sha256"], a["en_sha256"]) for a in m["articles"]}
    assert len(keys) == 100 and summary["articles"] == keys and summary["common_article_set"] is True
    for k in {r["model_key"] for r in rows}:
        sel = [r for r in rows if r["model_key"] == k]
        assert [r["article"] for r in sel] == keys
        assert all((r["article_id"], r["ar_sha256"], r["en_sha256"]) == by_id[r["article"]] for r in sel)


def test_ttr_and_statistics_recompute_exactly(outputs):
    rows, summary, _, _ = outputs
    for k in {r["model_key"] for r in rows}:
        sel = [r for r in rows if r["model_key"] == k]
        s = summary["models"][sel[0]["model"]]
        ar, en = [int(r["ar_tokens"]) for r in sel], [int(r["en_tokens"]) for r in sel]
        assert (s["ar_tokens_total"], s["en_tokens_total"]) == (sum(ar), sum(en))
        assert s["ttr"] == float(Fraction(sum(ar), sum(en)))
        ratios = [Fraction(a, e) for a, e in zip(ar, en)]
        assert s["median_article_ratio"] == float(statistics.median(ratios))
        assert (s["min_article_ratio"], s["max_article_ratio"]) == (float(min(ratios)), float(max(ratios)))
        assert s["ar_tokens_per_1000_chars"] == float(Fraction(1000 * sum(ar), sum(int(r["ar_chars"]) for r in sel)))
        q = summary["models"]["Qwen/Qwen2.5-3B-Instruct"]["ttr"]
        assert s["ttr_pct_diff_vs"]["qwen"] == pytest.approx((s["ttr"] / q - 1) * 100)
        for r in sel:
            assert r["ar_en_ratio"] == f"{int(r['ar_tokens']) / int(r['en_tokens']):.4f}"


def test_baselines_read_unchanged(outputs):
    _, summary, _, _ = outputs
    base = json.loads((ROOT / v2.OUTPUTS["summary"]).read_text())["models"]
    for m in ("Qwen/Qwen2.5-3B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"):
        for f in ("ar_tokens_total", "en_tokens_total", "ttr", "median_article_ratio"):
            assert summary["models"][m][f] == base[m][f]


def test_report_regenerates_and_separates_methods(outputs):
    _, summary, fm, _ = outputs
    rep = (ROOT / F.OUTPUTS["report"]).read_text(encoding="utf-8")
    assert F.render_report(summary, fm) == rep
    assert "Methodological warning" in rep and "PROVISIONAL" in rep
    raw_table = rep.split("## Content-only")[1].split("## Provider API")[0]
    for s in F.API:
        assert s.model not in raw_table  # never ranked with content-only counts


# ---------------------------------------------------------------- needs the pinned tokenizer assets

REF = json.loads((ROOT / "tests" / "frontier_reference_ids.json").read_text(encoding="utf-8"))


@pytest.mark.network
@pytest.mark.parametrize("spec", F.LOCAL, ids=lambda s: s.key)
def test_local_ids_match_official_reference_and_no_specials(spec):
    from atti import tokenization

    c = F.load_local(spec, ROOT / F.HF_CACHE)
    special_text = REF["samples"][3]  # literal control-token strings
    for text, ref in zip(REF["samples"], REF["ids"][spec.key]):
        if isinstance(c, F.HFCounter) and set(ref) & tokenization.special_ids(c.tok):
            # the official encode maps literal control strings to control ids even without
            # add_special_tokens; ATTI refuses such content instead of counting it
            assert text == special_text
            with pytest.raises(tokenization.TokenCountError, match="special"):
                c.count(text)
            continue
        assert c.ids(text) == ref
        assert c.count(text) == c.count(text) == len(ref)  # deterministic
    if isinstance(c, F.KimiCounter):  # encoding_k3 encodes user text with disallowed_special=()
        assert all(t < c.n_base for t in c.ids(special_text))
    assert F.weights_present(ROOT / F.HF_CACHE) == []


@pytest.mark.network
def test_local_rows_reproduce_byte_for_byte(outputs):
    rows, _, fm, _ = outputs
    m = json.loads((ROOT / v2.MANIFEST_PATH).read_text())
    records = v2.verify(m, ROOT / v2.RAW)
    for spec in F.LOCAL:
        committed = [r for r in rows if r["model_key"] == spec.key]
        meta = committed[0]["measurement_meta"]
        fresh = F.measure_rows(spec, F.load_local(spec, ROOT / F.HF_CACHE), records, m, meta)
        assert [{k: str(v) for k, v in r.items()} for r in fresh] == committed
