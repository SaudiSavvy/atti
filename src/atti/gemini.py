"""Gemini 4 Neon on the 100 current_law_v2 pairs via Google's official countTokens endpoint.

Kept apart from the frontier run so that the seven existing model results are only read: this
module never imports an Anthropic or OpenAI counter and never writes the frontier outputs.
Method: ``api_input_tokens`` (Google's ``totalTokens`` for one user message with one text part,
no system instruction, no tools). Nothing is subtracted from the reported counts.
"""

from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

from atti import frontier as F

GEMINI = F.ApiSpec(
    "gemini-4-neon", "Gemini 4 Neon", "google", "gemini-4-neon",
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-4-neon:countTokens", "GEMINI_API_KEY",
    "https://aistudio.google.com/api-reference/tokens/count-tokens")
MIN_INTERVAL_S = 1.0  # conservative: Google does not document a countTokens rate limit
RETRIES = 6  # backoff 1, 2, 4, ... 64 s on 429/5xx/transport errors
CACHE = F.API_CACHE / "gemini-4-neon.json"
PROBES = ["a", "a a", "Hello", "مرحبا", "مرحبا بالعالم"]
OUTPUTS = {
    "pilot": Path("results") / f"{F.CORPUS}_gemini_pilot.json",
    "csv": Path("results") / f"{F.CORPUS}_gemini.csv",
    "summary": Path("results") / f"{F.CORPUS}_gemini_summary.json",
    "report": Path("reports") / f"{F.CORPUS}_gemini.md",
    "manifest": Path("manifest") / "gemini_4_neon.json",
}
# Independent anchor for the completed Gemini measurement (see frontier.HISTORICAL_API_ANCHORS): SHA-256
# over sorted "<text sha256> <totalTokens>" lines of the 200 article texts, from the committed results.
GEMINI_ANCHOR = {"articles_sha256": "d6a2b719d76bd7bb0da8e5580eaa508b59435af0a0ab5a840bccffad9c6c11ec",
                 "texts": 200, "source": "results/current_law_v2_gemini.csv sha256:e668ea7d7bdfaf9c83691df294af80074f308a81c67c3ff30e3cafdd7640d00c"}
FRONTIER_PILOT = F.OUTPUTS["pilot"]
FRONTIER_SUMMARY = F.OUTPUTS["summary"]


class GeminiBlocked(F.FrontierError):
    pass


def counter(root: Path, client=None, key: str | None = None, sleep=None,
            anchor: dict | None = None) -> F.CachedApiCounter:
    """Cache-first counter; live requests only when GEMINI_API_KEY (or `key`) is available."""
    cache = F.ApiCache(root / CACHE)
    key = key if key is not None else os.environ.get(GEMINI.env_var)
    extra = {"sleep": sleep} if sleep is not None else {}
    live = F.ApiCounter(GEMINI, key=key, client=client, min_interval_s=MIN_INTERVAL_S, retries=RETRIES,
                        **extra) if key else None
    if live is None and not cache.data:
        raise GeminiBlocked(f"{GEMINI.env_var} is not set in the environment and no cached counts exist; "
                            "no request was made")
    return F.CachedApiCounter(GEMINI, cache, live, anchor=anchor or GEMINI_ANCHOR)  # validates every record


def pilot_articles(root: Path, manifest: dict) -> list[str]:
    """The ten articles already used for the frontier pilot (recomputed and cross-checked)."""
    keys = F.pilot_keys(manifest)
    published = json.loads((root / FRONTIER_PILOT).read_text(encoding="utf-8"))["pilot_articles"]
    if keys != published:
        raise F.FrontierError(f"pilot articles {keys} differ from the frontier pilot {published}")
    return keys


def probe_framing(c: F.CachedApiCounter) -> dict:
    """Observations only: totalTokens for very short inputs. Never used to adjust article counts."""
    live = c.live
    out = []
    for t in PROBES:
        first = live.count(t)
        second = live.count(t)
        out.append({"text": t, "chars": len(t), "total_tokens": [first, second]})
    return {"inputs": out,
            "note": "Short-input counts are reported as observed. A non-zero count for a one-character input "
                    "is consistent with request framing, but its size is not assumed constant across inputs "
                    "and nothing is subtracted from article counts."}


def run(root: Path, pilot_only: bool = False, client=None, key: str | None = None, sleep=None,
        anchor: dict | None = None) -> dict:
    """`anchor` defaults to GEMINI_ANCHOR (the committed measurement); tests pass their own."""
    from atti import v2

    manifest = json.loads((root / v2.MANIFEST_PATH).read_text(encoding="utf-8"))
    records = v2.verify(manifest, root / v2.RAW)
    keys = [a["key"] for a in manifest["articles"]]
    if len(keys) != 100 or len(set(keys)) != 100:
        raise F.FrontierError("the corpus must be exactly the 100 current_law_v2 pairs")
    c = counter(root, client=client, key=key, sleep=sleep, anchor=anchor)
    pkeys = pilot_articles(root, manifest)
    status = {"key": GEMINI.key, "display": GEMINI.display, "provider": GEMINI.provider,
              "api_model": GEMINI.model, "endpoint": GEMINI.endpoint, "docs": GEMINI.docs,
              "http_method": "POST", "auth": "x-goog-api-key header (value from GEMINI_API_KEY; never stored)",
              "credential_env_var": GEMINI.env_var, "request_shape": F.request_shape(GEMINI),
              "measurement_method": F.API_INPUT, "count_field": "totalTokens",
              "rate_limit": {"min_interval_s": MIN_INTERVAL_S, "retries": RETRIES,
                             "backoff": "Retry-After if given, else 2**attempt s; on 429, 5xx, transport errors"},
              "adapter_version": F.ADAPTER_VERSION, "status": "IMPLEMENTED"}
    old = root / OUTPUTS["manifest"]
    if c.live is not None:
        status["framing_observations"] = probe_framing(c)
    elif old.exists():  # offline regeneration: keep the observations recorded with the live run
        prev = json.loads(old.read_text(encoding="utf-8"))
        if "framing_observations" in prev:
            status["framing_observations"] = prev["framing_observations"]
    outputs = {}
    if c.live is not None:
        p = F.run_pilot(GEMINI.key, c, {r.key: (r.ar_text, r.en_text) for r in records if r.key in pkeys},
                        repeats=2)
        pilot = {"corpus": F.CORPUS, "pilot_articles": pkeys,
                 "selection": "the ten frontier pilot articles (Arabic-length decile midpoints, token-blind)",
                 "repeats": 2, "requests": "live; each text counted twice",
                 "adapter": {"passed": p.passed, "checks": p.checks, "counts": p.counts, "error": p.error}}
        outputs["pilot"] = F.dumps(pilot)
    else:  # offline regeneration: the pilot is a record of live requests and is kept, not re-run
        path = root / OUTPUTS["pilot"]
        if not path.exists():
            raise GeminiBlocked("no recorded live pilot; set GEMINI_API_KEY and run the pilot first")
        rec = json.loads(path.read_text(encoding="utf-8"))["adapter"]
        texts = {r.key: (r.ar_text, r.en_text) for r in records if r.key in pkeys}
        if rec["passed"]:
            if sorted(rec["counts"]) != sorted(texts):
                raise F.CacheIntegrityError(f"recorded pilot covers {sorted(rec['counts'])}, expected {sorted(texts)}")
            for art, (ar, en) in texts.items():
                if rec["counts"][art] != [c.count(ar), c.count(en)]:
                    raise F.CacheIntegrityError(f"recorded pilot count {rec['counts'][art]} for article {art} "
                                                f"disagrees with the cache")
        p = F.PilotResult(GEMINI.key, rec["passed"], rec["checks"], rec["counts"], rec["error"], replayed=True)
    if not p.passed:
        status.update(status="BLOCKED", blocked_reason=f"pilot failed: {p.error}")
    else:
        status["status"] = "VALIDATED"
        if not pilot_only:
            status["cache_evidence"] = c.check_anchor([t for r in records for t in (r.ar_text, r.en_text)])
            rows = F.measure_rows(GEMINI, c, records, manifest, "")
            meta = c.meta()
            for r in rows:
                r["measurement_meta"] = meta
            status["status"] = "MEASURED"
            status["measured_on"] = sorted({v["measured_on"] for v in c.cache.data.values()})
            outputs.update(build_outputs(root, rows, status))
    if pilot_only or not p.passed:
        outputs["manifest"] = F.dumps(status)
    F.publish(root, OUTPUTS, outputs, manifest)  # validates; never drops, changes or downgrades published results
    return status


def build_outputs(root: Path, rows: list[dict], status: dict) -> dict:
    s = F.model_summary(rows)
    frontier = json.loads((root / FRONTIER_SUMMARY).read_text(encoding="utf-8"))["models"]
    ref = {"qwen": "Qwen/Qwen2.5-3B-Instruct", "mistral": "mistralai/Mistral-7B-Instruct-v0.3"}
    s["ttr_pct_diff_vs"] = {n: (s["ttr"] / frontier[m]["ttr"] - 1) * 100 for n, m in ref.items()}
    s["comparability_warning"] = ("api_input_tokens include provider message framing; not directly comparable "
                                  "with raw_content_tokens")
    summary = {"corpus": F.CORPUS, "status": "PROVISIONAL", "articles": [r["article"] for r in rows],
               "models": {GEMINI.model: {"source": str(OUTPUTS["csv"]), "model_key": GEMINI.key, **s}}}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=F.CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return {"csv": buf.getvalue(), "summary": F.dumps(summary), "manifest": F.dumps(status),
            "report": render_report(summary, status, frontier)}


def render_report(summary: dict, status: dict, frontier: dict) -> str:
    g = summary["models"][GEMINI.model]
    L = [f"# ATTI {F.CORPUS}: Gemini 4 Neon ({g['articles']} article pairs)\n",
         "> **PROVISIONAL corpus.** No pair is human-approved. Same 100 pairs and texts as the other seven models; "
         "their results are read from `results/current_law_v2.csv` and `results/current_law_v2_frontier*`, unchanged.\n",
         "Tokenizer measurements of input text only. Not inference speed, model quality, output-token usage or pricing.\n",
         "## Method\n",
         f"- Endpoint: `POST {status['endpoint']}` (model `{status['api_model']}`); count field `totalTokens`.",
         "- Request: one user message with one text part containing the article body; no system instruction, "
         "no tools, no cached content: `" + json.dumps(status["request_shape"], ensure_ascii=False) + "`.",
         f"- Measured on: {', '.join(status['measured_on'])}. Method `api_input_tokens`: Google's reported count, "
         "with no overhead subtracted.\n",
         "## Gemini 4 Neon\n",
         "| Σ AR | Σ EN | **TTR** | Median | Min | Max | AR tok/1k chars | EN tok/1k chars |",
         "|---:|---:|---:|---:|---:|---:|---:|---:|",
         f"| {g['ar_tokens_total']} | {g['en_tokens_total']} | **{g['ttr']:.4f}** | {g['median_article_ratio']:.4f} | "
         f"{g['min_article_ratio']:.4f} | {g['max_article_ratio']:.4f} | {g['ar_tokens_per_1000_chars']:.1f} | "
         f"{g['en_tokens_per_1000_chars']:.1f} |", "",
         "## Provider API counts, same method (`api_input_tokens`)\n",
         "> **Methodological warning.** API counts include provider framing for a one-message request, which adds "
         "a similar absolute amount to both languages and pulls the ratio towards 1. Framing differs between "
         "providers, so even these three are only loosely comparable. They are not ranked with content-only "
         "tokenizer counts.\n",
         "| Model | Σ AR | Σ EN | **TTR** | Median | Min | Max |", "|---|---:|---:|---:|---:|---:|---:|"]
    api = {m: v for m, v in frontier.items() if v["measurement_method"] == F.API_INPUT}
    api[GEMINI.model] = g
    for m, v in api.items():
        L.append(f"| {m} | {v['ar_tokens_total']} | {v['en_tokens_total']} | **{v['ttr']:.4f}** | "
                 f"{v['median_article_ratio']:.4f} | {v['min_article_ratio']:.4f} | {v['max_article_ratio']:.4f} |")
    L += ["", "Content-only tokenizer results (`raw_content_tokens`) are in `reports/current_law_v2_frontier.md` "
          "and are deliberately not merged into this table.\n", "## Short-input observations\n"]
    obs = status.get("framing_observations")
    if obs:
        L += ["| Input | Characters | totalTokens (two requests) |", "|---|---:|---|"]
        for o in obs["inputs"]:
            L.append(f"| `{o['text']}` | {o['chars']} | {', '.join(map(str, o['total_tokens']))} |")
        L += ["", obs["note"]]
    else:
        L.append("Not recorded.")
    L += ["", "## Limitations\n",
          "- Google's documentation does not state whether countTokens includes framing, whether it is exact, "
          "or its rate limits.",
          "- A hosted model's tokenizer can change without a version change; counts are dated, not pinned.",
          *(["- Counts are replayed from a local cache whose 200 article counts reproduce an anchor pinned from "
             f"{status['cache_evidence']['anchor']['source']}. Its records predate cache schema 2, so provider, "
             "text-identity, adapter-version and count-field metadata were never recorded; they are not "
             "reconstructed."] if status.get("cache_evidence", {}).get("provenance_limitations") else []),
          "- One law, one translation; the corpus is provisional and documents source-alignment limitations."]
    return "\n".join(L) + "\n"
