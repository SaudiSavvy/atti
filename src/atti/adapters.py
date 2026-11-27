"""Tokenizer and API adapters shared by every measurement on a parallel corpus (corpus-agnostic).

Two measurement methods are kept apart and never mixed in one ranking:

* ``raw_content_tokens``: a released tokenizer, pinned by revision and file hash, applied locally to the
  text only (no special tokens, no chat template, no truncation).
* ``api_input_tokens``: the count an official provider endpoint returns for one user message whose
  content is the text. It includes whatever framing the provider adds; it is never converted into a
  content-only count.

Only tokenizer assets are downloaded (allow-listed file names, never model weights). API keys are read
from the environment, sent only in request headers and never logged. API observations live in a
write-once cache whose records are validated against the adapter before any is served.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from tokenizers import Tokenizer

from atti import tokenization

ADAPTER_VERSION = "1.0"


RAW_CONTENT = "raw_content_tokens"


API_INPUT = "api_input_tokens"


ASSET_ALLOWLIST = {"tokenizer.json", "tiktoken.model", "tokenizer_config.json"}


WEIGHT_SUFFIXES = (".safetensors", ".bin", ".pt", ".pth", ".gguf", ".ckpt", ".h5", ".msgpack", ".onnx")


class FrontierError(RuntimeError):
    """A count could not be produced or verified; never replaced by an estimate. (The name dates from the
    frontier adapters, the first users of this module; CLI messages and tests refer to it.)"""


class AssetIntegrityError(FrontierError):
    pass


class ApiError(FrontierError):
    pass


class CacheIntegrityError(RuntimeError):
    """A cached API observation is invalid, stale, conflicting or unanchored. Deliberately not a
    FrontierError: it aborts the whole run before any output is written instead of being reported
    as a per-adapter BLOCKED status next to freshly published results."""


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


ANTHROPIC_VERSION = "2026-10-21"


def fetch_assets(spec: LocalSpec, cache_dir: Path, allowlist=ASSET_ALLOWLIST) -> dict[str, Path]:
    """Download allow-listed tokenizer assets at the pinned revision and verify their SHA-256."""
    from huggingface_hub import hf_hub_download

    out = {}
    for name, digest in spec.assets.items():
        if name not in allowlist or name.endswith(WEIGHT_SUFFIXES):
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
        ids = tokenization.checked_encoding(self.tok, text).ids  # truncation/overflow/coverage/special-id guards
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


def request_shape(spec: ApiSpec) -> dict:
    """The exact JSON body sent, with the article text as a placeholder (no system, tools, instructions)."""
    if spec.provider == "anthropic":
        return {"model": spec.model, "messages": [{"role": "user", "content": "<article body>"}]}
    if spec.provider == "google":
        return {"contents": [{"role": "user", "parts": [{"text": "<article body>"}]}]}
    return {"model": spec.model, "input": [{"role": "user", "content": "<article body>"}]}


def _body(spec: ApiSpec, text: str) -> dict:
    if not text:
        raise ApiError("refusing to count an empty text")
    b = json.loads(json.dumps(request_shape(spec)))
    if spec.provider == "google":
        b["contents"][0]["parts"][0]["text"] = text
    else:
        (b["messages"] if spec.provider == "anthropic" else b["input"])[0]["content"] = text
    return b


def _headers(spec: ApiSpec, key: str) -> dict:
    if spec.provider == "anthropic":
        return {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
    if spec.provider == "google":  # header, not ?key=, so the key never appears in a URL or request log
        return {"x-goog-api-key": key, "Content-Type": "application/json"}
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def parse_count(spec: ApiSpec, status: int, payload) -> int:
    """Validate a provider response strictly; anything unexpected is an error, never a zero."""
    if status != 200:
        detail = ""
        if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
            st = payload["error"].get("status")  # e.g. PERMISSION_DENIED; provider messages are not echoed
            detail = f" ({st})" if isinstance(st, str) and st.isupper() else ""
        raise ApiError(f"{spec.provider}: HTTP {status}{detail}")
    if not isinstance(payload, dict):
        raise ApiError(f"{spec.provider}: malformed response (not a JSON object)")
    if spec.provider == "google":
        return _parse_google(payload)
    if spec.provider == "openai" and payload.get("object") != "response.input_tokens":
        raise ApiError(f"{spec.provider}: unexpected object {payload.get('object')!r}")
    n = payload.get("input_tokens")
    if type(n) is not int or n <= 0:
        raise ApiError(f"{spec.provider}: missing or invalid input_tokens {n!r}")
    return n


def _parse_google(payload: dict) -> int:
    n = payload.get("totalTokens")
    if type(n) is not int or n <= 0:
        raise ApiError(f"google: missing or invalid totalTokens {n!r}")
    cached = payload.get("cachedContentTokenCount", 0)
    if cached not in (0, None):
        raise ApiError(f"google: unexpected cachedContentTokenCount {cached!r} (no cached content is sent)")
    details = payload.get("promptTokensDetails")
    if details is not None:
        if not isinstance(details, list) or not all(isinstance(d, dict) for d in details):
            raise ApiError("google: malformed promptTokensDetails")
        mods = {d.get("modality") for d in details}
        if mods - {"TEXT"}:
            raise ApiError(f"google: non-text modalities reported for a text-only request: {sorted(map(str, mods))}")
    return n


class ApiCounter:
    """One POST per text with rate limiting and bounded exponential backoff on 429/5xx/transport errors."""

    MIN_INTERVAL_S = 0.5
    RETRIES = 4

    def __init__(self, spec: ApiSpec, key: str | None = None, client=None,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic,
                 min_interval_s: float | None = None, retries: int | None = None):
        key = key if key is not None else os.environ.get(spec.env_var)
        if not key:
            raise ApiError(f"{spec.env_var} is not set")
        self.spec, self._key = spec, key
        if client is None:
            import httpx

            client = httpx.Client(timeout=60.0)  # TLS verification stays on (httpx default)
        self._client, self._sleep, self._clock, self._last = client, sleep, clock, None
        if min_interval_s is not None:
            self.MIN_INTERVAL_S = min_interval_s
        if retries is not None:
            self.RETRIES = retries
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


def utc_date() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


CACHE_SCHEMA = 2


COUNT_FIELD = {"anthropic": "input_tokens", "openai": "input_tokens", "google": "totalTokens"}


_LEGACY_FIELDS = {"input_tokens", "measured_on", "model", "endpoint", "request_shape", "anthropic_version"}


_SCHEMA2_FIELDS = _LEGACY_FIELDS | {"schema", "provider", "text_sha256", "adapter_version", "count_field",
                                    "measurement_method"}


_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


_SHA = re.compile(r"[0-9a-f]{64}")


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
        known = anchor
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
