"""Pilot, measurement rows, per-model summaries and all-or-nothing publication (corpus-agnostic).

Shared by the frontier, Gemini and regional measurements: the same CSV schema, the same summary
statistics, and one publication guard that never drops, changes or downgrades published results.
"""

from __future__ import annotations

import json
import os
import statistics
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from atti.adapters import (ADAPTER_VERSION, API_INPUT, RAW_CONTENT, ApiCounter, CachedApiCounter, FrontierError,
                           LocalSpec)

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


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


class PublishedResultsError(RuntimeError):
    """Writing would drop, change or downgrade published measurements; nothing was written."""


def _csv_rows(text: str) -> list[dict]:
    import csv
    import io

    return list(csv.DictReader(io.StringIO(text)))


def validate_rows(rows: list[dict], manifest: dict) -> list[str]:
    """Every measured model must cover exactly the corpus articles with positive, consistent counts."""
    keys = sorted(a["key"] for a in manifest["articles"])
    errs = []
    for k in dict.fromkeys(r.get("model_key") for r in rows):
        sel = [r for r in rows if r.get("model_key") == k]
        if sorted(r.get("article") for r in sel) != keys:
            errs.append(f"{k}: rows do not cover exactly the {len(keys)} corpus articles")
        for r in sel:
            if set(r) != set(CSV_FIELDS) or r.get("measurement_method") not in (RAW_CONTENT, API_INPUT):
                errs.append(f"{k} article {r.get('article')}: malformed row")
                continue
            try:
                ar, en = int(r["ar_tokens"]), int(r["en_tokens"])
            except (TypeError, ValueError):
                errs.append(f"{k} article {r['article']}: token counts are not integers")
                continue
            if ar <= 0 or en <= 0 or r["ar_en_ratio"] != f"{ar / en:.4f}":
                errs.append(f"{k} article {r['article']}: invalid counts or ratio")
    return errs


def _adapters(doc: dict) -> dict:
    """Per-adapter records of a pilot or adapter manifest (frontier: many adapters; Gemini: one)."""
    if "adapters" in doc:
        return doc["adapters"]
    rec = doc["adapter"] if "adapter" in doc else doc
    return {doc.get("key", rec.get("key", "adapter")): rec}


def publish(root: Path, paths: dict, outputs: dict, manifest: dict) -> None:
    """Validate, then write all outputs or none. Published results are never dropped, changed or downgraded:
    a model's published rows must reappear unchanged, a recorded passing pilot must be kept verbatim, and an
    adapter published as MEASURED must stay MEASURED. Re-measuring from scratch is a deliberate step:
    remove the published files first."""
    errs = []
    if "csv" in outputs:
        new = _csv_rows(outputs["csv"])
        errs += validate_rows(new, manifest)
        if (root / paths["csv"]).exists():
            old = _csv_rows((root / paths["csv"]).read_text(encoding="utf-8"))
            for k in dict.fromkeys(r["model_key"] for r in old):
                o, n = [r for r in old if r["model_key"] == k], [r for r in new if r["model_key"] == k]
                if not n:
                    errs.append(f"{k}: its {len(o)} published rows would be removed")
                elif n != o:
                    errs.append(f"{k}: its published rows would change")
    for kind in ("pilot", "manifest"):
        if kind in outputs and (root / paths[kind]).exists():
            old = _adapters(json.loads((root / paths[kind]).read_text(encoding="utf-8")))
            new = _adapters(json.loads(outputs[kind]))
            for k, rec in old.items():
                if kind == "pilot" and rec.get("passed") and new.get(k) != rec:
                    errs.append(f"{k}: its recorded passing pilot would be removed or changed")
                if kind == "manifest" and rec.get("status") == "MEASURED" and new.get(k, {}).get("status") != "MEASURED":
                    errs.append(f"{k}: published as MEASURED, would become {new.get(k, {}).get('status', 'absent')}")
    if errs:
        raise PublishedResultsError("; ".join(errs[:8]) + (f"; and {len(errs) - 8} more" if len(errs) > 8 else ""))
    staged = []
    try:
        for k, content in outputs.items():
            dst = root / paths[k]
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".tmp")
            tmp.write_text(content, encoding="utf-8")
            staged.append((tmp, dst))
        for tmp, dst in staged:
            os.replace(tmp, dst)
    finally:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)
