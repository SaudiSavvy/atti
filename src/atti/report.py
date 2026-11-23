"""Render corpus reports (deterministic: no timestamps of the run itself).

Defaults reproduce reports/pilot.md byte-for-byte; other corpora pass their
own title, lead, extra sections and limitations.
"""

from __future__ import annotations


def _short(model: str) -> str:
    return model.split("/")[-1]


PILOT_LIMITATIONS = (
    "- 10 articles from a single law: a pilot, not a representative sample.",
    "- The English text is a translation (non-governing). Translation style (e.g. verbosity) "
    "affects the denominator.",
    "- Whitespace is normalized on both sides (layout only); counts on raw HTML/PDF layout "
    "would differ slightly.",
    "- Only articles without recorded amendments were eligible, which biases toward unchanged provisions.",
)


def render(manifest: dict, rows: list[dict], summary: dict, *,
           title: str = "ATTI pilot: Arabic vs English token counts, Saudi Labor Law",
           lead: str = "Engineering pilot.",
           preamble: tuple[str, ...] = (),
           sections: tuple[str, ...] = (),
           csv_name: str = "results/pilot.csv",
           review_sentence: str = "Each pair was also reviewed manually; per-article text SHA-256 hashes "
                                  "are in `manifest/pilot_manifest.json` and are re-checked on every run.",
           corpus_label: str = "pilot",
           limitations: tuple[str, ...] = PILOT_LIMITATIONS) -> str:
    models = list(summary["models"])
    src = manifest["sources"]
    audit = manifest["audit"]
    L = []
    L.append(f"# {title}\n")
    L.extend(preamble)
    L.append(f"{lead} **TTR = Σ Arabic tokens / Σ English tokens** over "
             f"{len(manifest['articles'])} verified article pairs. Content-only counts: no special "
             "tokens, no chat template, truncation disabled.\n")

    L.append("## Results by model\n")
    L.append("| Model | Revision | Σ AR tokens | Σ EN tokens | **TTR** | Median article ratio | Min | Max |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for t in summary["tokenizers"]:
        s = summary["models"][t["model"]]
        L.append(f"| {t['model']} | `{t['revision'][:12]}` | {s['ar_tokens_total']} | "
                 f"{s['en_tokens_total']} | **{s['ttr']:.4f}** | {s['median_article_ratio']:.4f} | "
                 f"{s['min_article_ratio']:.4f} | {s['max_article_ratio']:.4f} |")
    L.append("")

    L.append("## Per-article measurements\n")
    head = "| ID | Art. | AR chars | EN chars | " + " | ".join(
        f"{_short(m)} AR | {_short(m)} EN | {_short(m)} ratio" for m in models) + " |"
    L.append(head)
    L.append("|" + "---|" * 4 + "---:|" * (3 * len(models)))
    for e in manifest["articles"]:
        cells = [e["id"], str(e["article"]), str(e["ar_chars"]), str(e["en_chars"])]
        for m in models:
            r = next(r for r in rows if r["model"] == m and int(r["article"]) == e["article"])
            cells += [str(r["ar_tokens"]), str(r["en_tokens"]), str(r["ar_en_ratio"])]
        L.append("| " + " | ".join(cells) + " |")
    L.append("")

    L.extend(sections)
    L.append("## Sources and verification\n")
    L.append(f"- Law: {manifest['law']['name_en']} ({manifest['law']['name_ar']}), "
             f"{manifest['law']['instrument']}.")
    L.append(f"- Arabic (governing text): {src['ar']['publisher']}, <{src['ar']['url']}>, "
             f"retrieved {src['ar']['retrieved_at_utc']}.")
    L.append(f"- English (official translation): {src['en']['publisher']}, <{src['en']['url']}>, "
             f"PDF sha256 `{src['en']['pdf_sha256']}`, retrieved {src['en']['retrieved_at_utc']}.")
    L.append(f"- Latest amendment recorded in both sources: {manifest['law']['latest_amendment_in_both_sources']}.")
    L.append("- The English PDF body is the 2005 text with amendments listed in an appendix; the Arabic "
             "page shows the base text with amendments flagged per article. Only articles that neither "
             "source records as amended were used, so both sides are the same (unamended) wording. "
             + review_sentence)
    L.append(f"- Source disagreements found (excluded from the {corpus_label}): English appendix references "
             f"articles not flagged on the Arabic page: {audit['disagreements_en_only']}; Arabic page "
             f"flags articles not referenced in the English appendix: {audit['disagreements_ar_only']}.")
    L.append("")

    L.append("## Tokenizers\n")
    for t in summary["tokenizers"]:
        L.append(f"- `{t['model']}` @ `{t['revision']}`; `tokenizer.json` sha256 `{t['tokenizer_json_sha256']}`")
    L.append("")
    L.append("## Recalculation\n")
    L.append(f"All aggregates are recomputable from `{csv_name}`: TTR = sum(`ar_tokens`) / "
             "sum(`en_tokens`) per `model`; the median is over `ar_tokens/en_tokens` per row. "
             "`tests/test_results.py` performs this recalculation.\n")
    L.append("## Limitations\n")
    L.extend(limitations)
    return "\n".join(L) + "\n"


EXPANDED_LIMITATIONS = (
    "- PROVISIONAL: every pair was reviewed by an AI agent; no human has approved the corpus.",
    "- 30 articles from a single law; Parts 11 (marine), 14 (repealed) and 15 (no eligible "
    "articles) are not represented.",
    "- Only articles without recorded amendments were eligible, and articles touched by the "
    "M/1 and M/44 global phrase replacements were excluded; this biases toward unchanged provisions.",
    "- The English text is a non-governing translation; translation verbosity affects the denominator.",
    "- Whitespace is normalized on both sides (layout only).",
    "- Changes versus the pilot are descriptive; no statistical significance is claimed.",
)

_METRICS = (("Σ AR tokens", "ar_tokens_total", "{}"), ("Σ EN tokens", "en_tokens_total", "{}"),
            ("TTR", "ttr", "{:.4f}"), ("Median article ratio", "median_article_ratio", "{:.4f}"),
            ("Min article ratio", "min_article_ratio", "{:.4f}"),
            ("Max article ratio", "max_article_ratio", "{:.4f}"))


def _comparison(summary: dict, pilot_summary: dict) -> list[str]:
    L = ["## Comparison with the 10-article pilot\n",
         "Descriptive only: the 30-article corpus contains the 10 pilot articles, so the two "
         "samples overlap and no statistical significance is claimed.\n"]
    for model, full in summary["models"].items():
        pilot = pilot_summary["models"][model]
        added = summary["subsets"]["added_20"][model]
        L.append(f"**{model}**\n")
        L.append("| Metric | Pilot (10) | Expanded (30) | Added 20 only | Change 10 → 30 |")
        L.append("|---|---:|---:|---:|---:|")
        for label, key, fmt in _METRICS:
            delta = full[key] - pilot[key]
            d = f"{delta:+d}" if isinstance(delta, int) else f"{delta:+.4f}"
            L.append(f"| {label} | {fmt.format(pilot[key])} | {fmt.format(full[key])} | "
                     f"{fmt.format(added[key])} | {d} |")
        L.append("")
    same = all(summary["subsets"]["pilot_10"][m] == pilot_summary["models"][m] for m in summary["models"])
    L.append(f"Pilot articles re-measured inside this corpus reproduce the published pilot aggregates "
             f"exactly: **{'yes' if same else 'NO'}**.\n")
    return L


def _selection(manifest: dict) -> list[str]:
    sel = manifest["selection"]
    L = ["## Selection procedure\n"]
    L += [f"- {line}" for line in sel["procedure"]]
    b = sel["stratum_bounds_ar_chars"]
    L.append(f"- Seed `{sel['seed']}`; pool {sel['pool_size']} articles; Arabic-character strata: "
             f"short {b['short'][0]}–{b['short'][1]}, medium {b['medium'][0]}–{b['medium'][1]}, "
             f"long {b['long'][0]}–{b['long'][1]}; quotas "
             + " / ".join(f"{q} {k}" for k, q in sel["quotas"].items()) + ".")
    for stratum in ("short", "medium", "long"):
        arts = [f"{n} (Part {v['part']})" for n, v in sel["added"].items() if v["stratum"] == stratum]
        L.append(f"- Added, {stratum}: {', '.join(arts)}")
    reasons: dict[str, list[str]] = {}
    for n, r in sel["excluded_from_pool"].items():
        reasons.setdefault(r, []).append(str(n))
    for r, ns in reasons.items():
        L.append(f"- Excluded from pool ({r}): {', '.join(ns)}")
    L.append(f"- Excluded after semantic review: {sel['excluded_after_review'] or 'none'}")
    L.append("")
    return L


def render_expanded(manifest: dict, rows: list[dict], summary: dict, pilot_summary: dict,
                    csv_name: str) -> str:
    prov = manifest["review_provenance"]
    banner = (f"> **Status: {prov['status'].upper()}.** {prov['human_approval']}. "
              "Agent-assisted review only; see `manifest/expanded_v1_review.json`.\n")
    return render(
        manifest, rows, summary,
        title=f"ATTI {manifest['corpus']}: Arabic vs English token counts, Saudi Labor Law "
              f"({len(manifest['articles'])} articles)",
        lead="Expanded corpus.",
        preamble=(banner,),
        sections=tuple(_comparison(summary, pilot_summary) + _selection(manifest)),
        csv_name=csv_name,
        review_sentence="Each pair was reviewed side by side by an AI agent (not human-approved); "
                        "per-article text SHA-256 hashes are in `manifest/expanded_v1_manifest.json` "
                        "and are re-checked on every run.",
        corpus_label="corpus",
        limitations=EXPANDED_LIMITATIONS,
    )
