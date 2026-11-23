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
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
