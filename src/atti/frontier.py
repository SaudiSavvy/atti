"""Frontier tokenizers on the current_law_v2 corpus (same 100 pairs, same texts).

Two measurement methods are kept apart and never mixed in one ranking:

* ``raw_content_tokens``: the released tokenizer, pinned by revision and file hash, applied
  locally to the article body only (no special tokens, no chat template, no truncation).
* ``api_input_tokens``: the count an official provider endpoint returns for one user message
  whose content is the article body. It includes whatever framing the provider adds; it is
  never converted into a content-only count.

Only tokenizer assets are downloaded (allow-listed file names, never model weights).
API keys are read from the environment, sent only in request headers and never logged.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import statistics
import time
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Callable

from tokenizers import Tokenizer

from atti import tokenization

ADAPTER_VERSION = "1.0"
CORPUS = "current_law_v2"
RAW_CONTENT = "raw_content_tokens"
API_INPUT = "api_input_tokens"
STATUSES = ("IMPLEMENTED", "VALIDATED", "MEASURED", "BLOCKED")
ASSET_ALLOWLIST = {"tokenizer.json", "tiktoken.model", "tokenizer_config.json"}
WEIGHT_SUFFIXES = (".safetensors", ".bin", ".pt", ".pth", ".gguf", ".ckpt", ".h5", ".msgpack", ".onnx")


class FrontierError(RuntimeError):
    """A count could not be produced or verified; never replaced by an estimate."""


class AssetIntegrityError(FrontierError):
    pass


class ApiError(FrontierError):
    pass


class CacheIntegrityError(RuntimeError):
    """A cached API observation is invalid, stale, conflicting or unanchored. Deliberately not a
    FrontierError: it aborts the whole run before any output is written instead of being reported
    as a per-adapter BLOCKED status next to freshly published results."""


# ----------------------------------------------------------------------------- specifications

@dataclass(frozen=True)
class LocalSpec:
    key: str
    display: str
    repo_id: str
    revision: str  # full commit SHA
    kind: str  # "tokenizers" (tokenizer.json) or "kimi_tiktoken"
    assets: dict  # file name -> pinned SHA-256
    source_note: str
    method: str = RAW_CONTENT


@dataclass(frozen=True)
class ApiSpec:
    key: str
    display: str
    provider: str
    model: str
    endpoint: str
    env_var: str
    docs: str
    method: str = API_INPUT


DEEPSEEK = LocalSpec(
    "deepseek-v4.1-flash-1017", "DeepSeek V4.1 Flash 1017", "deepseek-ai/DeepSeek-V4.1-Flash-1017",
    "08c8657f02291e11b6f6b63e0e16014f8e748518", "tokenizers",
    {"tokenizer.json": "c90dfa01249db1be4245780a052ede752e1361c612ac6d08e2bdada7d599476b",
     "tokenizer_config.json": "6ac8c8dc065ed118161d02dd532749ae3f52c243deac27872134fae2f50d8547"},
    "Released tokenizer.json of this repository (byte-level BPE, 128,000 base tokens + 1,283 added; empty "
    "normalizer; ByteLevel post-processor adds no tokens). The official encoding/encoding.py renders messages "
    "as a string that this tokenizer encodes; message text is inserted verbatim. tokenizer_config.json: "
    "add_bos_token=false, add_eos_token=false. No older DeepSeek tokenizer is used.")
GLM = LocalSpec(
    "glm-5.3-flash", "GLM-5.3 Flash", "zai-org/GLM-5.3-Flash",
    "46a050bec13002ad29ee795c16e61cf4fa3c4a9c", "tokenizers",
    {"tokenizer.json": "19e773648cb4e65de8660ea6365e10acca112d42a854923df93db4a6f333a82d",
     "tokenizer_config.json": "98b1271574f41abf89427ae2dda030d94dc9478f0edc5a8bd240db213c6fd5fc"},
    "Released tokenizer.json (byte-level BPE, 154,820 base tokens, ignore_merges=true; no normalizer; "
    "ByteLevel post-processor, no template). Chat markers such as [gMASK]<sop> and <|user|> come only from "
    "chat_template.jinja, which is not applied. Note: like the official encode, the runtime maps literal "
    "control strings in the text (e.g. [gMASK], <|user|>) to control ids even without add_special_tokens; "
    "ATTI refuses such content rather than counting it. None of the 200 corpus texts contains one.")
KIMI = LocalSpec(
    "kimi-k3.1-pro", "Kimi K3.1 Pro", "moonshotai/Kimi-K3.1-Pro",
    "d9e99b0792a5e93b78ea9bea62a68167e36ddd9e", "kimi_tiktoken",
    {"tiktoken.model": "b6c497a7469b33ced9c38afb1ad6e47f03f5e5dc05f15930799210ec050c5103",
     "tokenizer_config.json": "9fc322181b8ec44236e148916aea4b6c2467b66ded7bfaff0efe623ad750b852"},
    "tiktoken.model shipped in the K3.1 Pro repository itself (no other checkpoint's vocabulary is used). "
    "Pre-tokenization regex, the 400,000/25,000-character split rule and the 256 reserved special ids are "
    "reproduced from this revision's tokenization_kimi.py (SHA-256 "
    "204ee39fbf13a6d6608b0d3ca1b4b04a14ac5f0a062a7fdee02e61f5d936f9c6). encoding_k3.py encodes message text "
    "with allow_special=False, i.e. disallowed_special=(); counts here use the same call. Token-for-token "
    "identity with the official TikTokenTokenizer was checked on all 200 corpus texts.")

CLAUDE = ApiSpec(
    "claude-opus-5-5", "Claude Opus 5.5", "anthropic", "claude-opus-5-5",
    "https://api.anthropic.com/v1/messages/count_tokens", "ANTHROPIC_API_KEY",
    "https://platform.claude.com/docs/en/build-with-claude/token-counting")
GPT = ApiSpec(
    "gpt-6.2-sol", "GPT-6.2 Sol", "openai", "gpt-6.2-sol",
    "https://api.openai.com/v1/responses/input_tokens", "OPENAI_API_KEY",
    "https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens")

LOCAL = (DEEPSEEK, GLM, KIMI)
API = (CLAUDE, GPT)
ALL = LOCAL + API
ANTHROPIC_VERSION = "2026-10-21"


# ----------------------------------------------------------------------------- local adapters

def fetch_assets(spec: LocalSpec, cache_dir: Path) -> dict[str, Path]:
    """Download allow-listed tokenizer assets at the pinned revision and verify their SHA-256."""
    from huggingface_hub import hf_hub_download

    out = {}
    for name, digest in spec.assets.items():
        if name not in ASSET_ALLOWLIST or name.endswith(WEIGHT_SUFFIXES):
            raise AssetIntegrityError(f"{name} is not an allow-listed tokenizer asset")
        path = Path(hf_hub_download(spec.repo_id, name, revision=spec.revision,
                                    cache_dir=str(cache_dir), token=False))
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != digest:
            raise AssetIntegrityError(f"{spec.repo_id}@{spec.revision[:12]} {name}: SHA-256 {got} != pinned {digest}")
        out[name] = path
    return out


class HFCounter:
    """tokenizer.json via the `tokenizers` runtime (the repositories' declared backend)."""

    def __init__(self, spec: LocalSpec, tokenizer_json: Path):
        data = json.loads(tokenizer_json.read_text(encoding="utf-8"))
        norm = data.get("normalizer")
        if norm not in (None, {"type": "Sequence", "normalizers": []}):
            raise AssetIntegrityError(f"{spec.repo_id}: unexpected normalizer; decode check would not hold")
        post = data.get("post_processor") or {}
        if post.get("type") not in (None, "ByteLevel"):
            raise AssetIntegrityError(f"{spec.repo_id}: post-processor {post.get('type')} may add template tokens")
        self.spec = spec
        self.tok = Tokenizer.from_str(tokenizer_json.read_text(encoding="utf-8"))
        self.tok.no_truncation()
        self.tok.no_padding()

    def ids(self, text: str) -> list[int]:
        tokenization.count_tokens(self.tok, text)  # truncation/overflow/coverage/special-id guards
        ids = self.tok.encode(text, add_special_tokens=False).ids
        if self.tok.decode(ids, skip_special_tokens=False) != text:
            raise FrontierError(f"{self.spec.key}: decode(encode(text)) != text")
        return ids

    def count(self, text: str) -> int:
        return len(self.ids(text))


# Copied verbatim from tokenization_kimi.py at the pinned revision (see KIMI.source_note).
KIMI_PAT_STR = "|".join([
    r"""[\p{Han}]+""",
    r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}&&[^\p{Han}]]*[\p{Ll}\p{Lm}\p{Lo}\p{M}&&[^\p{Han}]]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
    r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}&&[^\p{Han}]]+[\p{Ll}\p{Lm}\p{Lo}\p{M}&&[^\p{Han}]]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
    r"""\p{N}{1,3}""",
    r""" ?[^\s\p{L}\p{N}]+[\r\n]*""",
    r"""\s*[\r\n]+""",
    r"""\s+(?!\S)""",
    r"""\s+""",
])
KIMI_RESERVED = 256
TIKTOKEN_MAX_ENCODE_CHARS = 400_000
MAX_NO_WHITESPACES_CHARS = 25_000


def split_whitespaces_or_nonwhitespaces(s: str, max_len: int):
    """Same algorithm as TikTokenTokenizer._split_whitespaces_or_nonwhitespaces."""
    current_len = 0
    current_is_space = s[0].isspace() if s else False
    start = 0
    for i in range(len(s)):
        now = s[i].isspace()
        if current_is_space ^ now:
            current_len = 1
            current_is_space = now
        else:
            current_len += 1
            if current_len > max_len:
                yield s[start:i]
                start = i
                current_len = 1
    yield s[start:]


class KimiCounter:
    def __init__(self, spec: LocalSpec, tiktoken_model: Path, tokenizer_config: Path):
        import tiktoken
        from tiktoken.load import load_tiktoken_bpe

        ranks = load_tiktoken_bpe(str(tiktoken_model))
        self.n_base = len(ranks)
        added = json.loads(tokenizer_config.read_text(encoding="utf-8")).get("added_tokens_decoder", {})
        names = {int(i): v["content"] for i, v in added.items()}
        special = {names.get(i, f"<|reserved_token_{i}|>"): i
                   for i in range(self.n_base, self.n_base + KIMI_RESERVED)}
        self.spec = spec
        self.enc = tiktoken.Encoding(name=tiktoken_model.name, pat_str=KIMI_PAT_STR,
                                     mergeable_ranks=ranks, special_tokens=special)

    def ids(self, text: str) -> list[int]:
        out: list[int] = []
        for i in range(0, len(text), TIKTOKEN_MAX_ENCODE_CHARS):
            for sub in split_whitespaces_or_nonwhitespaces(text[i:i + TIKTOKEN_MAX_ENCODE_CHARS],
                                                           MAX_NO_WHITESPACES_CHARS):
                out.extend(self.enc.encode(sub, disallowed_special=()))
        leaked = [t for t in out if t >= self.n_base]
        if leaked:
            raise FrontierError(f"{self.spec.key}: special ids in content encoding: {leaked[:5]}")
        if self.enc.decode_bytes(out) != text.encode("utf-8"):
            raise FrontierError(f"{self.spec.key}: decode(encode(text)) != text")
        return out

    def count(self, text: str) -> int:
        return len(self.ids(text))


def load_local(spec: LocalSpec, cache_dir: Path):
    paths = fetch_assets(spec, cache_dir)
    if spec.kind == "tokenizers":
        return HFCounter(spec, paths["tokenizer.json"])
    if spec.kind == "kimi_tiktoken":
        return KimiCounter(spec, paths["tiktoken.model"], paths["tokenizer_config.json"])
    raise FrontierError(f"unknown adapter kind {spec.kind}")


def weights_present(cache_dir: Path) -> list[str]:
    return sorted(str(p.relative_to(cache_dir)) for p in Path(cache_dir).rglob("*")
                  if p.is_file() and p.name.endswith(WEIGHT_SUFFIXES))


# ----------------------------------------------------------------------------- API adapters

def request_shape(spec: ApiSpec) -> dict:
    """The exact JSON body sent, with the article text as a placeholder (no system, tools, instructions)."""
    if spec.provider == "anthropic":
        return {"model": spec.model, "messages": [{"role": "user", "content": "<article body>"}]}
    return {"model": spec.model, "input": [{"role": "user", "content": "<article body>"}]}


def _body(spec: ApiSpec, text: str) -> dict:
    if not text:
        raise ApiError("refusing to count an empty text")
    b = json.loads(json.dumps(request_shape(spec)))
    (b["messages"] if spec.provider == "anthropic" else b["input"])[0]["content"] = text
    return b


def _headers(spec: ApiSpec, key: str) -> dict:
    if spec.provider == "anthropic":
        return {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def parse_count(spec: ApiSpec, status: int, payload) -> int:
    """Validate a provider response strictly; anything unexpected is an error, never a zero."""
    if status != 200:
        raise ApiError(f"{spec.provider}: HTTP {status}")
    if not isinstance(payload, dict):
        raise ApiError(f"{spec.provider}: malformed response (not a JSON object)")
    if spec.provider == "openai" and payload.get("object") != "response.input_tokens":
        raise ApiError(f"{spec.provider}: unexpected object {payload.get('object')!r}")
    n = payload.get("input_tokens")
    if type(n) is not int or n <= 0:
        raise ApiError(f"{spec.provider}: missing or invalid input_tokens {n!r}")
    return n


class ApiCounter:
    """One POST per text with rate limiting and bounded exponential backoff on 429/5xx/transport errors."""

    MIN_INTERVAL_S = 0.5
    RETRIES = 4

    def __init__(self, spec: ApiSpec, key: str | None = None, client=None,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        key = key if key is not None else os.environ.get(spec.env_var)
        if not key:
            raise ApiError(f"{spec.env_var} is not set")
        self.spec, self._key = spec, key
        if client is None:
            import httpx

            client = httpx.Client(timeout=60.0)  # TLS verification stays on (httpx default)
        self._client, self._sleep, self._clock, self._last = client, sleep, clock, None
        self.log: list[dict] = []  # status and attempt only; never headers or bodies

    def __repr__(self):  # never expose the key
        return f"ApiCounter({self.spec.key})"

    def count(self, text: str) -> int:
        import httpx

        body = _body(self.spec, text)
        err = "no attempt"
        for attempt in range(self.RETRIES + 1):
            if self._last is not None:
                wait = self.MIN_INTERVAL_S - (self._clock() - self._last)
                if wait > 0:
                    self._sleep(wait)
            self._last = self._clock()
            try:
                resp = self._client.post(self.spec.endpoint, headers=_headers(self.spec, self._key), json=body)
            except httpx.TransportError as exc:
                err = f"transport error {type(exc).__name__}"
                self.log.append({"attempt": attempt, "error": err})
                self._sleep(2 ** attempt)
                continue
            self.log.append({"attempt": attempt, "status": resp.status_code})
            if resp.status_code == 429 or resp.status_code >= 500:
                err = f"HTTP {resp.status_code}"
                retry_after = resp.headers.get("retry-after")
                self._sleep(float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt)
                continue
            try:
                payload = resp.json()
            except ValueError:
                raise ApiError(f"{self.spec.provider}: response is not JSON (HTTP {resp.status_code})") from None
            return parse_count(self.spec, resp.status_code, payload)
        raise ApiError(f"{self.spec.provider}: giving up after {self.RETRIES + 1} attempts ({err})")


class ApiCache:
    """Write-once cache {text_sha256: record} so API results regenerate offline. Holds no credentials."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.data = json.loads(path.read_text()) if path.exists() else {}
        except ValueError as exc:
            raise CacheIntegrityError(f"{path.name}: not valid JSON ({exc})") from None
        if not isinstance(self.data, dict):
            raise CacheIntegrityError(f"{path.name}: top level is not an object")

    def get(self, sha: str):
        return self.data.get(sha)

    def put(self, sha: str, record: dict) -> None:
        if sha in self.data:
            if self.data[sha].get("input_tokens") != record["input_tokens"]:
                raise CacheIntegrityError(f"stale or conflicting cache: {sha[:12]} holds "
                                          f"{self.data[sha].get('input_tokens')!r}, new observation is "
                                          f"{record['input_tokens']}; not overwritten")
            return
        self.data[sha] = record
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, sort_keys=True) + "\n")
        tmp.replace(self.path)


# ----------------------------------------------------------------------------- pilot / full run

def pilot_keys(manifest: dict, n: int = 10) -> list[str]:
    """Token-blind, deterministic: the articles at the n Arabic-length quantile midpoints."""
    arts = sorted(manifest["articles"], key=lambda a: (a["ar_chars"], a["key"]))
    picks = [arts[int((i + 0.5) * len(arts) / n)]["key"] for i in range(n)]
    order = [a["key"] for a in manifest["articles"]]
    return sorted(picks, key=order.index)


@dataclass
class PilotResult:
    key: str
    passed: bool
    checks: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)  # article -> [ar, en]
    error: str | None = None
    replayed: bool = False  # True: recorded live pilot reused (offline replay), not re-observed


def run_pilot(key: str, counter, texts: dict[str, tuple[str, str]], repeats: int = 2) -> PilotResult:
    """Count each text `repeats` times (live requests for APIs, bypassing the cache) and require equality."""
    res = PilotResult(key, False)
    if isinstance(counter, CachedApiCounter):
        if counter.live is None:
            res.error = "no live requests available; a pilot is never re-run from cached values"
            return res
        try:
            for art, (ar, en) in texts.items():
                obs = []
                for t in (ar, en):
                    seen = [counter.live.count(t) for _ in range(repeats)]  # live, bypassing the cache
                    if len(set(seen)) != 1:
                        raise FrontierError(f"unstable count for article {art}: {seen}")
                    obs.append(counter.observe(t, seen[0]))  # stale/conflicting cache -> CacheIntegrityError
                res.counts[art] = obs
        except FrontierError as exc:
            res.error = str(exc)
            return res
        res.checks = {"arabic_and_english_counts_exist": True, "repeat_counts_identical": True,
                      "repeats": repeats, "guards": "strict response validation"}
        res.passed = True
        return res
    try:
        for art, (ar, en) in texts.items():
            first = [counter.count(ar), counter.count(en)]
            for _ in range(repeats - 1):
                if [counter.count(ar), counter.count(en)] != first:
                    raise FrontierError(f"unstable count for article {art}")
            if min(first) <= 0:
                raise FrontierError(f"non-positive count for article {art}")
            res.counts[art] = first
        res.checks = {"arabic_and_english_counts_exist": True, "repeat_counts_identical": True,
                      "repeats": repeats, "guards": "no truncation/special ids; decode round-trip (local)"
                      if not isinstance(counter, ApiCounter) else "strict response validation"}
        res.passed = True
    except FrontierError as exc:
        res.error = str(exc)
    return res


CSV_FIELDS = ["model", "model_key", "tokenizer_revision_or_api_model", "measurement_method", "article_id",
              "article", "part", "ar_sha256", "en_sha256", "ar_chars", "en_chars", "ar_tokens", "en_tokens",
              "ar_en_ratio", "adapter_version", "measurement_meta"]


def measure_rows(spec, counter, records, manifest, meta: str) -> list[dict]:
    by_key = {e["key"]: e for e in manifest["articles"]}
    rows = []
    for r in records:
        e = by_key[r.key]
        ar, en = counter.count(r.ar_text), counter.count(r.en_text)
        rows.append({
            "model": spec.repo_id if isinstance(spec, LocalSpec) else spec.model, "model_key": spec.key,
            "tokenizer_revision_or_api_model": spec.revision if isinstance(spec, LocalSpec) else spec.model,
            "measurement_method": spec.method, "article_id": e["id"], "article": r.key, "part": r.part,
            "ar_sha256": e["ar_sha256"], "en_sha256": e["en_sha256"], "ar_chars": len(r.ar_text),
            "en_chars": len(r.en_text), "ar_tokens": ar, "en_tokens": en, "ar_en_ratio": f"{ar / en:.4f}",
            "adapter_version": ADAPTER_VERSION, "measurement_meta": meta})
    return rows


def model_summary(rows: list[dict]) -> dict:
    ar = [int(r["ar_tokens"]) for r in rows]
    en = [int(r["en_tokens"]) for r in rows]
    arc = sum(int(r["ar_chars"]) for r in rows)
    enc = sum(int(r["en_chars"]) for r in rows)
    ratios = [Fraction(a, e) for a, e in zip(ar, en)]
    return {
        "articles": len(rows), "measurement_method": rows[0]["measurement_method"],
        "ar_tokens_total": sum(ar), "en_tokens_total": sum(en),
        "ttr": float(Fraction(sum(ar), sum(en))),
        "median_article_ratio": float(statistics.median(ratios)),
        "min_article_ratio": float(min(ratios)), "max_article_ratio": float(max(ratios)),
        "ar_tokens_per_1000_chars": float(Fraction(1000 * sum(ar), arc)),
        "en_tokens_per_1000_chars": float(Fraction(1000 * sum(en), enc)),
    }


def utc_date() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


# ----------------------------------------------------------------------------- orchestration

HF_CACHE = Path("data") / "hf_frontier"
API_CACHE = Path("data") / "api_cache"
OUTPUTS = {
    "pilot": Path("results") / f"{CORPUS}_frontier_pilot.json",
    "csv": Path("results") / f"{CORPUS}_frontier.csv",
    "summary": Path("results") / f"{CORPUS}_frontier_summary.json",
    "report": Path("reports") / f"{CORPUS}_frontier.md",
    "manifest": Path("manifest") / "frontier_tokenizers.json",
}
OFFICIAL_CROSSCHECK = {
    "date": "2026-11-24",
    "texts": "all 200 corpus texts (100 Arabic, 100 English) plus 4 synthetic edge cases",
    "reference": "official implementations in an isolated environment: transformers 5.22.2 AutoTokenizer "
                 "(DeepSeek, GLM: encode(add_special_tokens=False)); Kimi's own TikTokenTokenizer via "
                 "trust_remote_code, encode(allow_special_tokens=False); tiktoken 0.14.0, tokenizers 0.23.3",
    "result": "token ids identical for every text and model (0 mismatches of 204 per model)",
    "default_call_check": "default encode('x') returns one token for all three: no BOS or chat markers added",
    "fixture": "tests/frontier_reference_ids.json (synthetic, non-legal strings)",
}


# ----------------------------------------------------------------------------- cache provenance

CACHE_SCHEMA = 2
COUNT_FIELD = {"anthropic": "input_tokens", "openai": "input_tokens", "google": "totalTokens"}
_LEGACY_FIELDS = {"input_tokens", "measured_on", "model", "endpoint", "request_shape", "anthropic_version"}
_SCHEMA2_FIELDS = _LEGACY_FIELDS | {"schema", "provider", "text_sha256", "adapter_version", "count_field",
                                    "measurement_method"}
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_SHA = re.compile(r"[0-9a-f]{64}")

# Independent anchors for completed API measurements: SHA-256 over the sorted lines
# "<text sha256> <count>\n" for the 200 article texts, computed from the committed results (not from the
# local cache). Records written before cache schema 2 carry no provider, text-identity, adapter-version or
# count-field fields; they are accepted only when the article counts reproduce these anchors, and the
# missing fields are reported as a provenance limitation, never reconstructed.
HISTORICAL_API_ANCHORS = {
    "claude-opus-5-5": {"articles_sha256": "e838b01b436a4380272b8a70c6bcbe364787a0619042042f188fa583ffc6b7a9",
                        "texts": 200, "source": "results/current_law_v2_frontier.csv sha256:d1c06e8c7d2b5c4cb415da65a1cc153475142cb878e92e7b69e3b392efbe3db4"},
    "gpt-6.2-sol": {"articles_sha256": "79cf70ab77910c5374651d074a027295fc25a6d11c6fb62b9c7cecb6e49ff491",
                    "texts": 200, "source": "results/current_law_v2_frontier.csv sha256:d1c06e8c7d2b5c4cb415da65a1cc153475142cb878e92e7b69e3b392efbe3db4"},
}
LEGACY_LIMITATION = ("cache records predate cache schema 2: provider, text-identity, adapter-version and "
                     "count-field fields were not recorded at measurement time and are not reconstructed; "
                     "the records are trusted only because their article counts reproduce the anchor above")


def counts_digest(pairs) -> str:
    return hashlib.sha256("".join(f"{s} {n}\n" for s, n in sorted(pairs)).encode("utf-8")).hexdigest()


def validate_record(spec: ApiSpec, sha: str, rec, legacy_ok: bool) -> list[str]:
    """Every field that identifies what was measured must match this adapter exactly."""
    if not _SHA.fullmatch(sha if isinstance(sha, str) else ""):
        return [f"key {sha!r} is not a text SHA-256"]
    if not isinstance(rec, dict):
        return [f"{sha[:12]}: record is not an object"]
    e = []
    n = rec.get("input_tokens")
    if type(n) is not int or n <= 0:
        e.append(f"input_tokens {n!r} is not a positive integer")
    for f, want in (("model", spec.model), ("endpoint", spec.endpoint), ("request_shape", request_shape(spec))):
        if rec.get(f) != want:
            e.append(f"{f} {rec.get(f)!r} != expected {want!r}")
    if not isinstance(rec.get("measured_on"), str) or not _DATE.fullmatch(rec["measured_on"]):
        e.append(f"measured_on {rec.get('measured_on')!r} is not a date")
    if spec.provider == "anthropic" and rec.get("anthropic_version") != ANTHROPIC_VERSION:
        e.append(f"anthropic_version {rec.get('anthropic_version')!r} != {ANTHROPIC_VERSION}")
    if spec.provider != "anthropic" and "anthropic_version" in rec:
        e.append("anthropic_version present for a non-Anthropic adapter")
    if rec.get("schema") == CACHE_SCHEMA:
        unknown = set(rec) - _SCHEMA2_FIELDS
        for f, want in (("provider", spec.provider), ("text_sha256", sha), ("adapter_version", ADAPTER_VERSION),
                        ("count_field", COUNT_FIELD[spec.provider]), ("measurement_method", API_INPUT)):
            if rec.get(f) != want:
                e.append(f"{f} {rec.get(f)!r} != expected {want!r}")
    else:
        unknown = set(rec) - _LEGACY_FIELDS
        if not legacy_ok:
            e.append("record lacks schema-2 provenance and the adapter has no historical anchor")
    if unknown:
        e.append(f"unknown fields {sorted(unknown)}")
    return [f"{sha[:12]}: {x}" for x in e]


def new_record(spec: ApiSpec, sha: str, n: int) -> dict:
    return {"schema": CACHE_SCHEMA, "input_tokens": n, "measured_on": utc_date(), "model": spec.model,
            "provider": spec.provider, "endpoint": spec.endpoint, "request_shape": request_shape(spec),
            "text_sha256": sha, "adapter_version": ADAPTER_VERSION, "count_field": COUNT_FIELD[spec.provider],
            "measurement_method": API_INPUT,
            **({"anthropic_version": ANTHROPIC_VERSION} if spec.provider == "anthropic" else {})}


class CachedApiCounter:
    """Serve API counts from the write-once cache; fall back to live requests only when a key is set.

    Every record is validated when the counter is built, so no unvalidated record can be served.
    """

    def __init__(self, spec: ApiSpec, cache: ApiCache, live: ApiCounter | None, anchor: dict | None = None):
        self.spec, self.cache, self.live = spec, cache, live
        known = anchor if anchor is not None else HISTORICAL_API_ANCHORS.get(spec.key)
        legacy = any(not (isinstance(r, dict) and r.get("schema") == CACHE_SCHEMA) for r in cache.data.values())
        # The anchor binds any cache holding legacy records and every offline replay (which claims to
        # reproduce the historical measurement). A live re-measurement writing schema-2 records is
        # validated record by record and reports no anchor.
        self.anchor = known if known is not None and (legacy or live is None) else None
        errs = [x for sha, rec in cache.data.items() for x in validate_record(spec, sha, rec, self.anchor is not None)]
        if errs:
            raise CacheIntegrityError(f"{spec.key} cache rejected ({len(errs)} problems): " + "; ".join(errs[:5]))

    def count(self, text: str) -> int:
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        hit = self.cache.get(sha)
        if hit is not None:
            return hit["input_tokens"]
        if self.live is None:
            raise ApiError(f"{self.spec.env_var} is not set and no cached count exists")
        return self.observe(text, self.live.count(text))

    def observe(self, text: str, n: int) -> int:
        """Record a live observation; a cached value that disagrees is a controlled failure."""
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.cache.put(sha, new_record(self.spec, sha, n))
        return n

    def check_anchor(self, texts: list[str]) -> dict:
        """Require the article counts to reproduce the pinned anchor; return the evidence statement."""
        if self.anchor is None:
            legacy = [s for s, r in self.cache.data.items() if r.get("schema") != CACHE_SCHEMA]
            if legacy:
                raise CacheIntegrityError(f"{self.spec.key}: unanchored legacy records {len(legacy)}")
            return {"validation": "every cache record checked against model, provider, endpoint, request shape, "
                                  "text SHA-256, adapter version and count field",
                    "anchor": None, "provenance_limitations": []}
        pairs = set()
        for t in texts:
            sha = hashlib.sha256(t.encode("utf-8")).hexdigest()
            rec = self.cache.get(sha)
            if rec is None:
                raise CacheIntegrityError(f"{self.spec.key}: anchored measurement lacks a cached count for {sha[:12]}")
            pairs.add((sha, rec["input_tokens"]))
        if len(pairs) != self.anchor["texts"] or counts_digest(pairs) != self.anchor["articles_sha256"]:
            raise CacheIntegrityError(f"{self.spec.key}: cached article counts do not reproduce the pinned anchor "
                                      f"({self.anchor['source']})")
        legacy = any(r.get("schema") != CACHE_SCHEMA for r in self.cache.data.values())
        return {"validation": "every cache record checked against model, endpoint, request shape, date"
                              + (" and Anthropic API version" if self.spec.provider == "anthropic" else "")
                              + "; article counts reproduce the pinned anchor",
                "anchor": {"articles_sha256": self.anchor["articles_sha256"], "texts": self.anchor["texts"],
                           "source": self.anchor["source"]},
                "provenance_limitations": [LEGACY_LIMITATION] if legacy else []}

    def meta(self) -> str:
        days = sorted({v["measured_on"] for v in self.cache.data.values()})
        api = f"; anthropic-version {ANTHROPIC_VERSION}" if self.spec.provider == "anthropic" else ""
        return f"POST {self.spec.endpoint}; measured {days[0]}..{days[-1]}{api}" if days else ""


def _texts(records, keys=None) -> dict[str, tuple[str, str]]:
    return {r.key: (r.ar_text, r.en_text) for r in records if keys is None or r.key in keys}


def _asset_info(spec: LocalSpec, root: Path) -> dict:
    paths = fetch_assets(spec, root / HF_CACHE)
    return {name: {"sha256": spec.assets[name], "bytes": paths[name].stat().st_size} for name in spec.assets}


def run(root: Path, pilot_only: bool = False) -> dict:
    """Pilot every adapter on 10 pairs; measure all 100 pairs only for adapters that pass."""
    from atti import v2

    manifest = json.loads((root / v2.MANIFEST_PATH).read_text(encoding="utf-8"))
    records = v2.verify(manifest, root / v2.RAW)
    keys = [a["key"] for a in manifest["articles"]]
    if len(keys) != 100 or len(set(keys)) != 100 or [r.key for r in records] != keys:
        raise FrontierError("the corpus must be exactly the 100 current_law_v2 pairs")
    pkeys = pilot_keys(manifest)
    status, pilot, rows, counters = {}, {}, [], {}
    all_texts = [t for r in records for t in (r.ar_text, r.en_text)]
    prev = recorded_observations(root)

    for spec in ALL:
        st = {"key": spec.key, "display": spec.display, "measurement_method": spec.method, "status": "IMPLEMENTED"}
        try:
            if isinstance(spec, LocalSpec):
                st.update(repo_id=spec.repo_id, revision=spec.revision, adapter=spec.kind,
                          assets=_asset_info(spec, root), source_note=spec.source_note)
                counter = load_local(spec, root / HF_CACHE)
                meta = f"{spec.repo_id}@{spec.revision[:12]}; " + ", ".join(
                    f"{n} sha256 {d[:12]}" for n, d in spec.assets.items())
            else:
                st.update(provider=spec.provider, api_model=spec.model, endpoint=spec.endpoint, docs=spec.docs,
                          credential_env_var=spec.env_var, request_shape=request_shape(spec))
                cache = ApiCache(root / API_CACHE / f"{spec.key}.json")
                live = ApiCounter(spec) if os.environ.get(spec.env_var) else None
                if live is None and not cache.data:
                    raise ApiError(f"{spec.env_var} is not set in the environment; no request was made")
                counter = CachedApiCounter(spec, cache, live)  # validates every record or raises
                if live is not None:
                    st["access_check"] = {"text": "Hello", "input_tokens": counter.observe("Hello", live.count("Hello"))}
                    st["framing_probe"] = {"text": "a", "input_tokens": counter.observe("a", live.count("a")),
                                           "note": "recorded only; never subtracted from article counts"}
                meta = None
        except FrontierError as exc:
            st.update(status="BLOCKED", blocked_reason=str(exc))
            status[spec.key] = st
            continue
        if isinstance(spec, ApiSpec) and counter.live is None:
            # offline replay: the pilot and probes are records of live requests; keep them verbatim
            p = replay_pilot(spec, counter, prev, _texts(records, pkeys), st)
        else:
            p = run_pilot(spec.key, counter, _texts(records, pkeys), repeats=2)
        pilot[spec.key] = prev["pilot"][spec.key] if p.passed and p.replayed else \
            {"passed": p.passed, "checks": p.checks, "counts": p.counts, "error": p.error}
        if not p.passed:
            st.update(status="BLOCKED", blocked_reason=f"pilot failed: {p.error}")
        else:
            st["status"] = "VALIDATED"
            if not pilot_only:
                try:
                    if meta is None:
                        if counter.anchor is not None:
                            st["cache_evidence"] = counter.check_anchor(all_texts)
                        rows_m = measure_rows(spec, counter, records, manifest, "")
                        if counter.anchor is None:
                            st["cache_evidence"] = counter.check_anchor(all_texts)
                        meta = counter.meta()
                        for r in rows_m:
                            r["measurement_meta"] = meta
                    else:
                        rows_m = measure_rows(spec, counter, records, manifest, meta)
                    rows += rows_m
                    st["status"] = "MEASURED"
                except FrontierError as exc:
                    st.update(status="BLOCKED", blocked_reason=f"full run failed: {exc}")
        status[spec.key] = st

    pilot_doc = {"corpus": CORPUS, "pilot_articles": pkeys,
                 "selection": "token-blind: articles at the 10 Arabic-length decile midpoints", "adapters": pilot}
    outputs = {"pilot": dumps(pilot_doc)}
    if not pilot_only:
        outputs.update(build_outputs(root, manifest, rows, status))
    for k, content in outputs.items():
        (root / OUTPUTS[k]).parent.mkdir(parents=True, exist_ok=True)
        (root / OUTPUTS[k]).write_text(content, encoding="utf-8")
    return status


def recorded_observations(root: Path) -> dict:
    """Pilot and adapter records already published (read once, before anything is rewritten)."""
    out = {"pilot": {}, "adapters": {}}
    for k, path in (("pilot", OUTPUTS["pilot"]), ("adapters", OUTPUTS["manifest"])):
        f = root / path
        if f.exists():
            out[k] = json.loads(f.read_text(encoding="utf-8")).get("adapters", {})
    return out


def replay_pilot(spec: ApiSpec, counter: CachedApiCounter, prev: dict, texts: dict, st: dict) -> PilotResult:
    """Reuse the recorded live pilot and probe observations after checking them against the cache."""
    rec, adapter = prev["pilot"].get(spec.key), prev["adapters"].get(spec.key, {})
    res = PilotResult(spec.key, False)
    if not rec or not rec.get("passed"):
        res.error = "no recorded passing live pilot to replay; a pilot is never re-run from cached values"
        return res
    if sorted(rec["counts"]) != sorted(texts):
        raise CacheIntegrityError(f"{spec.key}: recorded pilot covers {sorted(rec['counts'])}, expected {sorted(texts)}")
    for art, (ar, en) in texts.items():
        cached = [counter.count(ar), counter.count(en)]
        if rec["counts"][art] != cached:
            raise CacheIntegrityError(f"{spec.key}: recorded pilot count {rec['counts'][art]} for article {art} "
                                      f"disagrees with the cache {cached}")
    for field in ("access_check", "framing_probe"):
        if field in adapter:
            obs = adapter[field]
            hit = counter.cache.get(hashlib.sha256(obs["text"].encode("utf-8")).hexdigest())
            if hit is not None and hit["input_tokens"] != obs["input_tokens"]:
                raise CacheIntegrityError(f"{spec.key}: recorded {field} disagrees with the cache")
            st[field] = obs
    res.passed, res.counts, res.checks, res.replayed = True, rec["counts"], rec["checks"], True
    return res


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def baseline_rows(root: Path) -> list[dict]:
    """Existing Qwen/Mistral rows (read only) with their measurement method made explicit."""
    import csv

    from atti import v2

    with (root / v2.OUTPUTS["csv"]).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["measurement_method"] = RAW_CONTENT
    return rows


def build_outputs(root: Path, manifest: dict, rows: list[dict], status: dict) -> dict:
    import csv
    import io

    base = baseline_rows(root)
    models = {}
    for m in dict.fromkeys(r["model"] for r in base):
        models[m] = {"source": "results/current_law_v2.csv (existing, unchanged)",
                     **model_summary([r for r in base if r["model"] == m])}
    for k in dict.fromkeys(r["model_key"] for r in rows):
        sel = [r for r in rows if r["model_key"] == k]
        models[sel[0]["model"]] = {"source": str(OUTPUTS["csv"]), "model_key": k, **model_summary(sel)}
    ref = {"qwen": "Qwen/Qwen2.5-3B-Instruct", "mistral": "mistralai/Mistral-7B-Instruct-v0.3"}
    for m, s in models.items():
        s["ttr_pct_diff_vs"] = {n: (s["ttr"] / models[r]["ttr"] - 1) * 100 for n, r in ref.items()}
        if s["measurement_method"] != RAW_CONTENT:
            s["comparability_warning"] = ("api_input_tokens include provider message framing; not directly "
                                          "comparable with raw_content_tokens")
    article_sets = {m: sorted({r["article"] for r in base + rows if r["model"] == m}) for m in models}
    summary = {"corpus": CORPUS, "status": "PROVISIONAL", "articles": [a["key"] for a in manifest["articles"]],
               "common_article_set": all(v == sorted(a["key"] for a in manifest["articles"])
                                         for v in article_sets.values()),
               "models": models}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    fm = {"corpus": CORPUS, "corpus_manifest": "manifest/current_law_v2_manifest.json",
          "corpus_status": manifest["status"], "adapter_version": ADAPTER_VERSION,
          "status_definitions": {
              "IMPLEMENTED": "adapter code and offline tests exist",
              "VALIDATED": "10-pair pilot passed (counts present, stable on repeat, guards held)",
              "MEASURED": "all 100 pairs measured in both languages",
              "BLOCKED": "not measured; reason recorded; no value published"},
          "measurement_methods": {
              RAW_CONTENT: "locally reproduced encoding of the article text only: no special tokens, no chat "
                           "template, no truncation; decode(encode(text)) == text verified per text",
              API_INPUT: "input_tokens returned by the provider's official counting endpoint for one user "
                         "message whose content is the article text; no system prompt, instructions or tools; "
                         "includes provider framing, which is not removed"},
          "official_crosscheck": OFFICIAL_CROSSCHECK,
          "baseline_models": [{"model": t.repo_id, "revision": t.revision, "measurement_method": RAW_CONTENT}
                              for t in tokenization.TOKENIZERS],
          "adapters": status}
    return {"csv": buf.getvalue(), "summary": dumps(summary), "manifest": dumps(fm),
            "report": render_report(summary, fm)}


def render_report(summary: dict, fm: dict) -> str:
    models = summary["models"]
    raw = {m: s for m, s in models.items() if s["measurement_method"] == RAW_CONTENT}
    api = {m: s for m, s in models.items() if s["measurement_method"] == API_INPUT}
    L = [f"# ATTI {CORPUS}: frontier tokenizers ({len(summary['articles'])} article pairs)\n",
         "> **PROVISIONAL corpus.** No pair is human-approved. Same 100 pairs, texts and whitespace "
         "normalization as `reports/current_law_v2.md`; Qwen and Mistral numbers are read from the existing "
         "results, unchanged.\n",
         "These are tokenizer measurements of input text. They do not measure inference speed, model quality, "
         "output-token usage or production pricing.\n",
         "## Adapter status\n", "| Model | Method | Status | Source / revision | Note |", "|---|---|---|---|---|"]
    for st in fm["adapters"].values():
        src = (f"`{st['repo_id']}@{st['revision'][:12]}`" if "repo_id" in st else f"`{st.get('api_model')}` via API")
        note = st.get("blocked_reason", "")
        L.append(f"| {st['display']} | {st['measurement_method']} | **{st['status']}** | {src} | {note} |")
    L += ["", "## Content-only token counts (`raw_content_tokens`)\n",
          "| Model | Σ AR | Σ EN | **TTR** | Median | Min | Max | AR tok/1k chars | EN tok/1k chars | "
          "TTR vs Qwen | TTR vs Mistral |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m, s in sorted(raw.items(), key=lambda kv: kv[1]["ttr"]):
        L.append(f"| {m} | {s['ar_tokens_total']} | {s['en_tokens_total']} | **{s['ttr']:.4f}** | "
                 f"{s['median_article_ratio']:.4f} | {s['min_article_ratio']:.4f} | {s['max_article_ratio']:.4f} | "
                 f"{s['ar_tokens_per_1000_chars']:.1f} | {s['en_tokens_per_1000_chars']:.1f} | "
                 f"{s['ttr_pct_diff_vs']['qwen']:+.1f}% | {s['ttr_pct_diff_vs']['mistral']:+.1f}% |")
    L += ["", "## Provider API counts (`api_input_tokens`)\n",
          "> **Methodological warning.** API counts are for a structured one-message request and include "
          "provider framing tokens, which inflate both languages by a similar absolute amount and pull the "
          "ratio towards 1. They are not placed in the content-only ranking above, and no framing constant is "
          "subtracted.\n"]
    if api:
        L += ["| Model | Σ AR | Σ EN | **TTR** | Median | Min | Max |", "|---|---:|---:|---:|---:|---:|---:|"]
        for m, s in api.items():
            L.append(f"| {m} | {s['ar_tokens_total']} | {s['en_tokens_total']} | **{s['ttr']:.4f}** | "
                     f"{s['median_article_ratio']:.4f} | {s['min_article_ratio']:.4f} | {s['max_article_ratio']:.4f} |")
    else:
        L.append("No provider API counts were measured; see the adapter status table. No values are estimated.")
    L += ["", "## Method and limitations\n",
          "- TTR = Σ Arabic tokens / Σ English tokens over the same 100 pairs; medians, minima and maxima are "
          "over per-article ratios; tokens per 1,000 characters use the normalized text lengths.",
          f"- Local tokenizers were checked against the official implementations: {OFFICIAL_CROSSCHECK['result']}.",
          "- Content-only counts exclude message framing that a deployed model would add; they describe the "
          "tokenizer, not a full request.",
          "- Content-only counts are refused (not estimated) if a text contains literal control-token strings; "
          "every one of the 200 texts passed the guards (no special ids, no uncovered characters, exact decode).",
          "- One law, one document type, one translation; the English is the ministry's published translation.",
          "- No statistical significance is claimed for differences between models.",
          f"- Common article set across all reported models: {summary['common_article_set']}."]
    lim = {st["display"]: st["cache_evidence"] for st in fm["adapters"].values() if st.get("cache_evidence")}
    for name, ev in lim.items():
        if ev.get("anchor"):
            L.append(f"- {name}: API counts are replayed from a local cache whose 200 article counts reproduce an "
                     f"anchor pinned from {ev['anchor']['source']}."
                     + (" Its records predate cache schema 2, so provider, text-identity, adapter-version and "
                        "count-field metadata were never recorded; they are not reconstructed."
                        if ev.get("provenance_limitations") else ""))
    return "\n".join(L) + "\n"
