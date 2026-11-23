"""Command-line entry point: ``uv run atti {fetch,manifest,pilot}``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_ARTICLES = "4,32,38,59,65,70,89,92,108,120"


def _root() -> Path:
    return Path.cwd()


EXIT_VERIFICATION, EXIT_NETWORK = 2, 3


def _network_error(exc) -> int:
    print(f"NETWORK ERROR: {exc}", file=sys.stderr)
    return EXIT_NETWORK


def cmd_fetch(args) -> int:
    from atti import sources

    try:
        paths = sources.fetch_all(_root() / "data" / "raw")
    except sources.NetworkError as exc:
        return _network_error(exc)
    for key, path in paths.items():
        print(f"{key}: {path}")
    return 0


def cmd_manifest(args) -> int:
    from atti import corpus, sources

    root = _root()
    raw = root / "data" / "raw"
    sources.fetch_all(raw)
    review = corpus.read_json(root / "manifest" / "review.json")
    fetch_log = corpus.read_json(raw / "fetch_log.json")
    if args.corpus == "expanded_v1":
        from atti import selection

        pilot = corpus.read_json(root / "manifest" / "pilot_manifest.json")
        review = corpus.read_json(root / "manifest" / "expanded_v1_review.json")
        m = selection.expanded_manifest(raw, pilot, review, fetch_log)
    else:
        articles = [int(x) for x in args.articles.split(",")]
        m = corpus.build_manifest(raw, articles, review, fetch_log)
    out = root / "manifest" / f"{args.corpus}_manifest.json"
    corpus.write_json(out, m)
    print(f"wrote {out.relative_to(root)} with {len(m['articles'])} article pairs")
    return 0


def cmd_pilot(args, name: str = "pilot") -> int:
    from atti import corpus, pipeline, sources

    try:
        summary = pipeline.run(_root(), name)
    except sources.NetworkError as exc:
        return _network_error(exc)
    except corpus.VerificationError as exc:
        print(f"VERIFICATION FAILED: {exc}", file=sys.stderr)
        return EXIT_VERIFICATION
    for model, s in summary["models"].items():
        print(f"{model}: AR={s['ar_tokens_total']} EN={s['en_tokens_total']} "
              f"TTR={s['ttr']:.4f} median={s['median_article_ratio']:.4f}")
    print("wrote " + ", ".join(pipeline.CORPORA[name][1:]))
    return 0


def cmd_expanded(args) -> int:
    return cmd_pilot(args, "expanded_v1")


def cmd_verify_live(args) -> int:
    from atti import corpus, live, sources

    root = _root()
    manifest = corpus.read_json(root / "manifest" / f"{args.corpus}_manifest.json")
    try:
        report = live.verify_live(manifest, root / "data" / "raw")
    except sources.NetworkError as exc:
        return _network_error(exc)
    print(live.format_report(report))
    return report.outcome


def cmd_review_sheet(args) -> int:
    from types import SimpleNamespace

    from atti import corpus, review

    root = _root()
    name = args.corpus
    m_path = root / "manifest" / f"{name}_manifest.json"
    manifest = corpus.read_json(m_path)
    m_hash = review.manifest_sha256(m_path)
    sources = {}
    try:
        if name == "current_law_v2":
            from atti import v2

            recs = v2.verify(manifest, root / v2.RAW)
            pairs = [SimpleNamespace(article=r.key, ar_text=r.ar_text, en_text=r.en_text) for r in recs]
            parts = {r.key: r.part for r in recs}
            for r in recs:
                pages = ", ".join(str(p) for p in r.ar_pages)
                sources[r.key] = (f'Arabic PDF p. {pages} · <a href="{r.en_url}">English page</a> · '
                                  f'<a href="{r.ar_html_url}">Arabic HTML page</a>')
            ai = corpus.read_json(root / "manifest" / f"{name}_review.json")
        else:
            pairs = corpus.verify(manifest, root / "data" / "raw")
            ar_articles, _ = corpus.load_sources(root / "data" / "raw")
            parts = {a.number: a.part for a in ar_articles if not a.bis}
            ai = corpus.read_json(root / "review" / f"{name}_ai_review.json")
    except (corpus.VerificationError, Exception) as exc:  # noqa: BLE001
        if type(exc).__name__ != "VerificationError":
            raise
        print(f"VERIFICATION FAILED: {exc}", file=sys.stderr)
        return EXIT_VERIFICATION
    dec_path = root / "review" / f"{name}_human_decisions.json"
    if review.write_json_new(dec_path, review.decisions_template(name, manifest, m_hash)):
        print(f"created empty decision template {dec_path.relative_to(root)}")
    dec = corpus.read_json(dec_path)
    errors = review.validate_decisions(dec, manifest, m_hash)
    out = root / "data" / "review" / f"{name}_review_sheet.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(review.render_sheet(manifest, pairs, parts, ai, dec, errors), encoding="utf-8")
    flagged = [k for k, v in ai["articles"].items() if v["proposed_status"] not in ("PASS", "PROPOSED_PASS")]
    flagged.sort(key=review._sort)
    page = out.with_name(f"{name}_review.html")
    page.write_text(review.render_html(manifest, pairs, parts, ai, dec, errors, flagged, sources), encoding="utf-8")
    s = review.summarize(ai, dec)
    print(f"wrote {out.relative_to(root)} and {page.relative_to(root)} (git-ignored; contain full legal texts)")
    print(f"AI proposed: {s['ai_proposed']}")
    print(f"human decisions: {s['human']}; fully human-approved: {s['fully_human_approved']}")
    for e in errors:
        print(f"DECISION FILE ERROR: {e}", file=sys.stderr)
    return EXIT_VERIFICATION if errors else 0


def cmd_decide(args) -> int:
    """Record ONE human decision in the decision file (the only writer of that file)."""
    import datetime as dt
    import json
    import os

    from atti import corpus, review

    root = _root()
    m_path = root / "manifest" / f"{args.corpus}_manifest.json"
    dec_path = root / "review" / f"{args.corpus}_human_decisions.json"
    if not dec_path.exists():
        print(f"ERROR: {dec_path.relative_to(root)} not found; run `atti review-sheet` first", file=sys.stderr)
        return EXIT_VERIFICATION
    try:
        new = review.record_decision(
            corpus.read_json(dec_path), corpus.read_json(m_path), review.manifest_sha256(m_path),
            args.article, args.decision, args.reviewer, args.date or dt.date.today().isoformat(),
            args.comment, replace=args.replace)
    except ValueError as exc:
        print(f"NOT RECORDED: {exc}", file=sys.stderr)
        return EXIT_VERIFICATION
    tmp = dec_path.with_name(dec_path.name + ".part")
    tmp.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, dec_path)
    d = new["decisions"][str(args.article)]
    print(f"recorded Article {args.article}: {d['decision']} by {d['reviewer']} on {d['date']}")
    return 0


def cmd_v2_fetch(args) -> int:
    from atti import sources, v2

    try:
        v2.fetch(_root())
    except sources.NetworkError as exc:
        return _network_error(exc)
    print("HRSD sources cached in data/raw_v2 (provenance.json records URLs, hashes, retrieval times)")
    return 0


def cmd_v2_manifest(args) -> int:
    from atti import v2

    m = v2.curate(_root())
    print(f"wrote {v2.MANIFEST_PATH} with {len(m['articles'])} pairs; review counts "
          f"{m['review']['proposed_status_counts']}")
    return 0


def cmd_v2(args) -> int:
    from atti import sources, v2

    try:
        summary = v2.run(_root())
    except sources.NetworkError as exc:
        return _network_error(exc)
    except v2.VerificationError as exc:
        print(f"VERIFICATION FAILED: {exc}", file=sys.stderr)
        return EXIT_VERIFICATION
    for model, s in summary["models"].items():
        print(f"{model}: AR={s['ar_tokens_total']} EN={s['en_tokens_total']} "
              f"TTR={s['ttr']:.4f} median={s['median_article_ratio']:.4f}")
    print("wrote " + ", ".join(str(p) for p in v2.OUTPUTS.values()))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="atti", description="Arabic Token Tax Index")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="download missing official sources into data/raw "
                   "(git-ignored; cached files are never replaced)").set_defaults(func=cmd_fetch)
    m = sub.add_parser("manifest", help="(re)build the verified article manifest")
    m.add_argument("--articles", default=DEFAULT_ARTICLES, help="pilot only")
    m.add_argument("--corpus", choices=("pilot", "expanded_v1"), default="pilot")
    m.set_defaults(func=cmd_manifest)
    sub.add_parser("pilot", help="reproduce from cached sources: verify hashes, count tokens, "
                   "write results and report").set_defaults(func=cmd_pilot)
    sub.add_parser("expanded", help="reproduce the 30-article expanded_v1 corpus (writes only "
                   "expanded_v1 artifacts)").set_defaults(func=cmd_expanded)
    v = sub.add_parser("verify-live", help="download fresh official sources to a temp dir and "
                       "compare with the manifest (exit 0 clean, 1 source changed, "
                       "2 articles failed, 3 network error)")
    v.add_argument("--corpus", choices=("pilot", "expanded_v1"), default="pilot")
    v.set_defaults(func=cmd_verify_live)
    r = sub.add_parser("review-sheet", help="write the local bilingual review sheet (data/review, "
                       "git-ignored) and validate recorded human decisions")
    r.add_argument("--corpus", choices=("pilot", "expanded_v1", "current_law_v2"), default="expanded_v1")
    r.set_defaults(func=cmd_review_sheet)
    d = sub.add_parser("decide", help="record one HUMAN review decision (refuses to overwrite "
                       "without --replace)")
    d.add_argument("article", help="article key, e.g. 45 or 79bis")
    d.add_argument("decision", choices=("APPROVE", "REJECT", "REQUEST_EXAMINATION"))
    d.add_argument("--reviewer", required=True, help="your name (a human)")
    d.add_argument("--comment", default="")
    d.add_argument("--date", help="YYYY-MM-DD (default: today)")
    d.add_argument("--replace", action="store_true", help="change an already recorded decision")
    d.add_argument("--corpus", choices=("pilot", "expanded_v1", "current_law_v2"), default="expanded_v1")
    d.set_defaults(func=cmd_decide)
    sub.add_parser("v2-fetch", help="fetch HRSD sources for current_law_v2 into data/raw_v2 "
                   "(polite, cached, never overwritten)").set_defaults(func=cmd_v2_fetch)
    sub.add_parser("v2-manifest", help="(curation) rebuild manifest/current_law_v2_manifest.json "
                   "from the cache and the AI review file").set_defaults(func=cmd_v2_manifest)
    sub.add_parser("v2", help="reproduce current_law_v2 results from the pinned cache "
                   "(historical artifacts are only read)").set_defaults(func=cmd_v2)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
