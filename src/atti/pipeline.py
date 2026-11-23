"""Pilot run: verify corpus -> count tokens -> write CSV, summary, and report."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from atti import corpus, metrics, report, tokenization

CSV_FIELDS = [
    "model", "revision", "article_id", "article",
    "ar_sha256", "en_sha256", "ar_chars", "en_chars",
    "ar_tokens", "en_tokens", "ar_en_ratio",
]


def measure(pairs, manifest: dict, hf_cache: Path) -> tuple[list[dict], list[dict]]:
    rows, tok_info = [], []
    by_num = {e["article"]: e for e in manifest["articles"]}
    for spec in tokenization.TOKENIZERS:
        lt = tokenization.load(spec, hf_cache)
        tok_info.append({"model": spec.repo_id, "revision": spec.revision,
                         "tokenizer_json_sha256": lt.file_sha256})
        for p in pairs:
            e = by_num[p.article]
            ar = tokenization.count_tokens(lt.tokenizer, p.ar_text)
            en = tokenization.count_tokens(lt.tokenizer, p.en_text)
            rows.append({
                "model": spec.repo_id, "revision": spec.revision,
                "article_id": e["id"], "article": p.article,
                "ar_sha256": e["ar_sha256"], "en_sha256": e["en_sha256"],
                "ar_chars": len(p.ar_text), "en_chars": len(p.en_text),
                "ar_tokens": ar, "en_tokens": en,
                "ar_en_ratio": f"{metrics.article_ratio(ar, en):.4f}",
            })
    return rows, tok_info


def rows_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# Published artifacts that must exist for results to be reviewable.
REQUIRED_ARTIFACTS = (
    "manifest/pilot_manifest.json",
    "results/pilot.csv",
    "results/pilot_summary.json",
    "reports/pilot.md",
)


def load_published(root: Path) -> dict:
    """Load all published artifacts; raise FileNotFoundError naming any that are missing."""
    missing = [a for a in REQUIRED_ARTIFACTS if not (root / a).is_file()]
    if missing:
        raise FileNotFoundError(f"missing published artifacts: {missing}")
    return {
        "manifest": corpus.read_json(root / REQUIRED_ARTIFACTS[0]),
        "csv_text": (root / REQUIRED_ARTIFACTS[1]).read_text(encoding="utf-8"),
        "rows": read_csv(root / REQUIRED_ARTIFACTS[1]),
        "summary_text": (root / REQUIRED_ARTIFACTS[2]).read_text(encoding="utf-8"),
        "report_text": (root / REQUIRED_ARTIFACTS[3]).read_text(encoding="utf-8"),
    }


def summary_to_json(summary: dict) -> str:
    return json.dumps(summary, ensure_ascii=False, indent=2) + "\n"


def run(root: Path) -> dict:
    """Reproduce the benchmark from the cached baseline sources.

    Sources are downloaded only if absent from ``data/raw`` (first run);
    cached files are never replaced. Every article is re-verified against the
    manifest hashes before any token is counted.
    """
    raw_dir, hf_cache = root / "data" / "raw", root / "data" / "hf"
    from atti import sources

    sources.fetch_all(raw_dir)
    manifest = corpus.read_json(root / "manifest" / "pilot_manifest.json")
    pairs = corpus.verify(manifest, raw_dir)
    rows, tok_info = measure(pairs, manifest, hf_cache)
    summary = {"tokenizers": tok_info, "models": metrics.summarize(rows)}

    (root / "results").mkdir(exist_ok=True)
    (root / "results" / "pilot.csv").write_text(rows_to_csv(rows), encoding="utf-8")
    (root / "results" / "pilot_summary.json").write_text(summary_to_json(summary), encoding="utf-8")
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports" / "pilot.md").write_text(report.render(manifest, rows, summary), encoding="utf-8")
    return summary
