"""Command-line entry point: ``uv run atti {fetch,manifest,pilot}``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_ARTICLES = "4,32,38,59,65,70,89,92,108,120"


def _root() -> Path:
    return Path.cwd()


def cmd_fetch(args) -> int:
    from atti import sources

    for key, path in sources.fetch_all(_root() / "data" / "raw", refresh=args.refresh).items():
        print(f"{key}: {path}")
    return 0


def cmd_manifest(args) -> int:
    from atti import corpus, sources

    root = _root()
    raw = root / "data" / "raw"
    sources.fetch_all(raw)
    review = corpus.read_json(root / "manifest" / "review.json")
    fetch_log = corpus.read_json(raw / "fetch_log.json")
    articles = [int(x) for x in args.articles.split(",")]
    m = corpus.build_manifest(raw, articles, review, fetch_log)
    corpus.write_json(root / "manifest" / "pilot_manifest.json", m)
    print(f"wrote manifest/pilot_manifest.json with {len(m['articles'])} article pairs")
    return 0


def cmd_pilot(args) -> int:
    from atti import corpus, pipeline

    try:
        summary = pipeline.run(_root())
    except corpus.VerificationError as exc:
        print(f"VERIFICATION FAILED: {exc}", file=sys.stderr)
        return 2
    for model, s in summary["models"].items():
        print(f"{model}: AR={s['ar_tokens_total']} EN={s['en_tokens_total']} "
              f"TTR={s['ttr']:.4f} median={s['median_article_ratio']:.4f}")
    print("wrote results/pilot.csv, results/pilot_summary.json, reports/pilot.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="atti", description="Arabic Token Tax Index")
    sub = p.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fetch", help="download official sources into data/raw (git-ignored)")
    f.add_argument("--refresh", action="store_true")
    f.set_defaults(func=cmd_fetch)
    m = sub.add_parser("manifest", help="(re)build the verified article manifest")
    m.add_argument("--articles", default=DEFAULT_ARTICLES)
    m.set_defaults(func=cmd_manifest)
    sub.add_parser("pilot", help="verify corpus, count tokens, write results and report").set_defaults(func=cmd_pilot)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
