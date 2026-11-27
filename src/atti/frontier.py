"""Frontier tokenizers on the current_law_v2 corpus (same 100 pairs, same texts).

DeepSeek, GLM and Kimi are counted locally (``raw_content_tokens``); Claude and GPT through their
providers' counting endpoints (``api_input_tokens``). The two methods are never mixed in one ranking.
Adapters live in ``atti.adapters``; pilot, rows and safe publication in ``atti.measure``.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from atti import tokenization
from atti.adapters import (ADAPTER_VERSION, API_INPUT, RAW_CONTENT, ApiCache, ApiCounter, ApiError, ApiSpec,
                           CacheIntegrityError, CachedApiCounter, FrontierError, LocalSpec, fetch_assets,
                           load_local, request_shape)
from atti.measure import (CSV_FIELDS, PilotResult, PublishedResultsError, dumps, measure_rows, model_summary,
                          pilot_keys, publish, run_pilot)

CORPUS = "current_law_v2"
STATUSES = ("IMPLEMENTED", "VALIDATED", "MEASURED", "BLOCKED")


# ----------------------------------------------------------------------------- specifications


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


def cached_counter(spec: ApiSpec, cache: ApiCache, live: ApiCounter | None, anchor: dict | None = None):
    """A CachedApiCounter bound to this adapter's historical anchor unless another anchor is given."""
    return CachedApiCounter(spec, cache, live, anchor if anchor is not None else HISTORICAL_API_ANCHORS.get(spec.key))


def _texts(records, keys=None) -> dict[str, tuple[str, str]]:
    return {r.key: (r.ar_text, r.en_text) for r in records if keys is None or r.key in keys}


def _asset_info(spec: LocalSpec, root: Path) -> dict:
    paths = fetch_assets(spec, root / HF_CACHE)
    return {name: {"sha256": spec.assets[name], "bytes": paths[name].stat().st_size} for name in spec.assets}


def run(root: Path, pilot_only: bool = False) -> dict:
    """Pilot every adapter on 10 pairs; measure all 100 pairs only for adapters that pass."""
    from atti import v2

    manifest, records = v2.load_verified(root)
    pkeys = pilot_keys(manifest)
    status, pilot, rows = {}, {}, []
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
                counter = cached_counter(spec, cache, live)  # validates every record or raises
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
    try:
        publish(root, OUTPUTS, outputs, manifest)
    except PublishedResultsError as exc:
        blocked = [f"{st['display']}: {st['blocked_reason']}" for st in status.values() if st["status"] == "BLOCKED"]
        raise PublishedResultsError(str(exc) + (f" (blocked: {'; '.join(blocked)})" if blocked else "")) from None
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


# ----------------------------------------------------------------------------- safe publication


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
