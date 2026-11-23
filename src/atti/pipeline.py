"""Corpus run: verify corpus -> count tokens -> write CSV, summary, and report."""

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


# Published artifacts per corpus: (manifest, csv, summary json, report).
CORPORA = {
    "pilot": ("manifest/pilot_manifest.json", "results/pilot.csv",
              "results/pilot_summary.json", "reports/pilot.md"),
    "expanded_v1": ("manifest/expanded_v1_manifest.json", "results/expanded_v1.csv",
                    "results/expanded_v1_summary.json", "reports/expanded_v1.md"),
}
REQUIRED_ARTIFACTS = CORPORA["pilot"]


def load_published(root: Path, name: str = "pilot") -> dict:
    """Load all published artifacts; raise FileNotFoundError naming any that are missing."""
    paths = CORPORA[name]
    missing = [a for a in paths if not (root / a).is_file()]
    if missing:
        raise FileNotFoundError(f"missing published artifacts: {missing}")
    return {
        "manifest": corpus.read_json(root / paths[0]),
        "csv_text": (root / paths[1]).read_text(encoding="utf-8"),
        "rows": read_csv(root / paths[1]),
        "summary_text": (root / paths[2]).read_text(encoding="utf-8"),
        "report_text": (root / paths[3]).read_text(encoding="utf-8"),
    }


def summary_to_json(summary: dict) -> str:
    return json.dumps(summary, ensure_ascii=False, indent=2) + "\n"


def build_summary(rows: list[dict], tok_info: list[dict], manifest: dict) -> dict:
    """Aggregates over all rows, plus named article subsets if the manifest defines them."""
    summary = {"tokenizers": tok_info, "models": metrics.summarize(rows)}
    if "subsets" in manifest:
        summary["subsets"] = {
            name: metrics.summarize([r for r in rows if int(r["article"]) in set(arts)])
            for name, arts in manifest["subsets"].items()
        }
    return summary


def render_report(name: str, manifest: dict, rows: list[dict], summary: dict, root: Path) -> str:
    if name == "pilot":
        return report.render(manifest, rows, summary)
    pilot_summary = json.loads((root / CORPORA["pilot"][2]).read_text(encoding="utf-8"))
    return report.render_expanded(manifest, rows, summary, pilot_summary, csv_name=CORPORA[name][1])


def run(root: Path, name: str = "pilot") -> dict:
    """Reproduce one corpus from the cached baseline sources.

    Sources are downloaded only if absent from ``data/raw`` (first run);
    cached files are never replaced. Every article is re-verified against the
    manifest hashes before any token is counted. Only this corpus's own
    artifacts are written.
    """
    raw_dir, hf_cache = root / "data" / "raw", root / "data" / "hf"
    from atti import sources

    m_path, csv_path, summary_path, report_path = (root / p for p in CORPORA[name])
    sources.fetch_all(raw_dir)
    manifest = corpus.read_json(m_path)
    pairs = corpus.verify(manifest, raw_dir)
    rows, tok_info = measure(pairs, manifest, hf_cache)
    summary = build_summary(rows, tok_info, manifest)

    csv_path.parent.mkdir(exist_ok=True)
    csv_path.write_text(rows_to_csv(rows), encoding="utf-8")
    summary_path.write_text(summary_to_json(summary), encoding="utf-8")
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(render_report(name, manifest, rows, summary, root), encoding="utf-8")
    return summary
