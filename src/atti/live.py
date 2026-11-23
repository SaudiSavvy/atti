"""``atti verify-live``: compare freshly downloaded official sources to the manifest.

Read-only with respect to the baseline: fresh files go to a temporary
directory that is deleted afterwards; ``data/raw`` and the manifest are never
written, and no hash is updated or new text approved automatically.

Outcome (also the CLI exit code):
  0 CLEAN            selected articles verified, no source-level change detected
  1 SOURCE_CHANGED   selected articles verified, but the sources changed elsewhere
  2 ARTICLES_FAILED  a selected article is changed/missing/ineligible, or a
                     fresh source could not be parsed
  3 NETWORK_ERROR    a source could not be downloaded (raised as NetworkError)
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from atti import corpus, sources

CLEAN, SOURCE_CHANGED, ARTICLES_FAILED, NETWORK_ERROR = 0, 1, 2, 3


@dataclass
class LiveReport:
    articles: list[corpus.ArticleStatus] = field(default_factory=list)
    source_changes: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def outcome(self) -> int:
        if self.errors or any(s.status != "ok" for s in self.articles):
            return ARTICLES_FAILED
        return SOURCE_CHANGED if self.source_changes else CLEAN


def _compare_full_texts(base, fresh) -> list[str]:
    """Article-level diff of the whole law between baseline cache and fresh copy."""
    (b_ar, b_en), (f_ar, f_en) = base, fresh
    key = lambda a: (a.number, a.bis, a.heading)  # noqa: E731
    b_ar_map = {key(a): (a.text, a.amended) for a in b_ar}
    f_ar_map = {key(a): (a.text, a.amended) for a in f_ar}
    out = []
    for label, b, f in (("Arabic", b_ar_map, f_ar_map), ("English", b_en.articles, f_en.articles)):
        added, removed = sorted(set(f) - set(b), key=str), sorted(set(b) - set(f), key=str)
        changed = sorted((k for k in set(b) & set(f) if b[k] != f[k]), key=str)
        fmt = (lambda ks: [k[0] if isinstance(k, tuple) else k for k in ks]) if label == "Arabic" else list
        for what, ks in (("added", added), ("removed", removed), ("changed", changed)):
            if ks:
                out.append(f"{label} articles {what} vs cached baseline: {fmt(ks)}")
    if b_en.appendix_text.split() != f_en.appendix_text.split():
        out.append("English amendments appendix text changed vs cached baseline")
    return out


def verify_live(manifest: dict, baseline_dir: Path,
                downloader: sources.Downloader = sources.download) -> LiveReport:
    """Raises sources.NetworkError if a download fails; otherwise returns a report."""
    report = LiveReport()
    with tempfile.TemporaryDirectory(prefix="atti-live-") as tmp:
        fresh = sources.fetch_fresh(Path(tmp), downloader)  # NetworkError propagates

        pdf_hash = sources.sha256_bytes(fresh["en"].read_bytes())
        if pdf_hash != manifest["sources"]["en"]["pdf_sha256"]:
            report.source_changes.append(
                f"English PDF bytes changed (sha256 {pdf_hash[:16]}… != manifest "
                f"{manifest['sources']['en']['pdf_sha256'][:16]}…)")
        try:
            parsed = corpus.load_sources(Path(tmp))
        except Exception as exc:  # malformed / unexpected content, not a network failure
            report.errors.append(f"fresh sources could not be parsed: {type(exc).__name__}: {exc}")
            return report

        report.articles, _ = corpus.check_articles(manifest, *parsed)
        fresh_audit = corpus.audit(*parsed)
        for k, v in manifest["audit"].items():
            if fresh_audit[k] != v:
                added, removed = sorted(set(fresh_audit[k]) - set(v)), sorted(set(v) - set(fresh_audit[k]))
                report.source_changes.append(f"audit {k}: added {added}, removed {removed}")

        if all((baseline_dir / s.filename).exists() for s in sources.SOURCES):
            report.source_changes += _compare_full_texts(corpus.load_sources(baseline_dir), parsed)
        else:
            report.notes.append(
                "no cached baseline in data/raw: whole-law comparison skipped "
                "(only manifest hashes and audit lists were compared)")
    return report


def format_report(report: LiveReport) -> str:
    names = {CLEAN: "CLEAN", SOURCE_CHANGED: "SOURCE_CHANGED", ARTICLES_FAILED: "ARTICLES_FAILED"}
    lines = [f"verify-live: {names[report.outcome]}"]
    for e in report.errors:
        lines.append(f"  ERROR {e}")
    if report.articles:
        ok = [s.article for s in report.articles if s.status == "ok"]
        lines.append(f"  selected articles verified: {len(ok)}/{len(report.articles)}")
        for s in report.articles:
            if s.status != "ok":
                lines.append(f"  {s.status.upper():<10} Article {s.article}: {s.detail}")
    lines.append("  source-level changes: " + ("none" if not report.source_changes else ""))
    lines += [f"    - {c}" for c in report.source_changes]
    lines += [f"  note: {n}" for n in report.notes]
    lines.append("  baseline corpus and manifest were not modified")
    return "\n".join(lines)
