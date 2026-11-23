"""Render reports/pilot.md (deterministic: no timestamps of the run itself)."""

from __future__ import annotations


def _short(model: str) -> str:
    return model.split("/")[-1]


def render(manifest: dict, rows: list[dict], summary: dict) -> str:
    models = list(summary["models"])
    src = manifest["sources"]
    audit = manifest["audit"]
    L = []
    L.append("# ATTI pilot: Arabic vs English token counts, Saudi Labor Law\n")
    L.append("Engineering pilot. **TTR = Σ Arabic tokens / Σ English tokens** over "
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
             "source records as amended were used, so both sides are the same (unamended) wording. Each "
             "pair was also reviewed manually; per-article text SHA-256 hashes are in "
             "`manifest/pilot_manifest.json` and are re-checked on every run.")
    L.append(f"- Source disagreements found (excluded from the pilot): English appendix references "
             f"articles not flagged on the Arabic page: {audit['disagreements_en_only']}; Arabic page "
             f"flags articles not referenced in the English appendix: {audit['disagreements_ar_only']}.")
    L.append("")

    L.append("## Tokenizers\n")
    for t in summary["tokenizers"]:
        L.append(f"- `{t['model']}` @ `{t['revision']}`; `tokenizer.json` sha256 `{t['tokenizer_json_sha256']}`")
    L.append("")
    L.append("## Recalculation\n")
    L.append("All aggregates are recomputable from `results/pilot.csv`: TTR = sum(`ar_tokens`) / "
             "sum(`en_tokens`) per `model`; the median is over `ar_tokens/en_tokens` per row. "
             "`tests/test_results.py` performs this recalculation.\n")
    L.append("## Limitations\n")
    L.append("- 10 articles from a single law: a pilot, not a representative sample.")
    L.append("- The English text is a translation (non-governing). Translation style (e.g. verbosity) "
             "affects the denominator.")
    L.append("- Whitespace is normalized on both sides (layout only); counts on raw HTML/PDF layout "
             "would differ slightly.")
    L.append("- Only articles without recorded amendments were eligible, which biases toward unchanged provisions.")
    return "\n".join(L) + "\n"
