# ATTI: Arabic Token Tax Index

[![CI](https://github.com/SaudiSavvy/atti/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SaudiSavvy/atti/actions/workflows/ci.yml)

How many more tokens does it take to say the same thing in Arabic than in English?

ATTI measures this on parallel legal text: 100 articles of the current Saudi Labor Law, in the government-published Arabic and the ministry's published English translation. For each model, the **Token Tax Ratio** is

```
TTR = Σ Arabic tokens / Σ English tokens   (over the same 100 article pairs)
```

so 1.0 means parity and 2.0 means Arabic costs twice as many tokens. All three corpora underwent substantive bilingual semantic review and were accepted by the maintainer for comparative tokenization benchmarking. Human review: **COMPLETE**. Corpora (`pilot`, `expanded_v1`, `current_law_v2`): **ACCEPTED**. See [review provenance](docs/methodology.md#review-provenance).

## Results

Eight models on the same 100 pairs (`current_law_v2`). The last column drops Articles 34, 35 and 108, whose published Arabic and English differ in meaning or numbering (see [Limitations](#limitations)).

> **New in v0.2.0:** Two Arab-developed tokenizers reverse the Arabic token tax on this corpus: ALLaM from Saudi Arabia (**−20.2%**) and K2 Horizon from the UAE, also used by Jais 3 (**−16.5%**). See [Arabic-focused and Arab-developed tokenizers](#arabic-focused-and-arab-developed-tokenizers).

**Tokenizer counts** (`raw_content_tokens`): each tokenizer is run locally on the article text only, with no special tokens or chat template.

| Model | Σ AR | Σ EN | TTR | Median per article | TTR without 34, 35, 108 |
|---|---:|---:|---:|---:|---:|
| DeepSeek V4.1 Flash 1017 | 9,693 | 7,248 | **1.337** | 1.350 | 1.334 |
| Qwen2.5-3B-Instruct | 9,811 | 7,293 | **1.345** | 1.356 | 1.340 |
| GLM-5.3 Flash | 10,609 | 7,277 | **1.458** | 1.460 | 1.454 |
| Kimi K3.1 Pro | 12,564 | 7,251 | **1.733** | 1.759 | 1.730 |
| Mistral-7B-Instruct-v0.3 | 23,970 | 7,921 | **3.026** | 3.023 | 3.022 |

**Provider API counts** (`api_input_tokens`): each article sent as a one-message request to the provider's token-counting endpoint.

| Model | Σ AR | Σ EN | TTR | Median per article | TTR without 34, 35, 108 |
|---|---:|---:|---:|---:|---:|
| GPT-6.2 Sol | 8,689 | 7,838 | **1.109** | 1.111 | 1.105 |
| Gemini 4 Neon | 12,044 | 10,662 | **1.130** | 1.130 | 1.127 |
| Claude Opus 5.5 | 18,228 | 11,919 | **1.529** | 1.502 | 1.528 |

Do not compare the two tables. API counts include the provider's message framing (Gemini reports 35 tokens for the single character `a`). This overhead adds roughly the same number of tokens to both languages, pulling every API ratio toward 1.0, and it varies by provider. Nothing is subtracted, so API ratios are only loosely comparable even with each other.

Key findings:

- Among the local tokenizers, DeepSeek and Qwen spend about a third more tokens on Arabic, while Mistral spends about three times as many. Most of the difference is on the Arabic side; English totals vary by less than 10%.
- Dropping the three pairs with known alignment problems moves no TTR by more than 0.005 and leaves both orderings unchanged.
- These are input-token counts. They say nothing about model quality, latency, output length or pricing.

### Arabic-focused and Arab-developed tokenizers

`atti regional` measures seven more released tokenizers with the same `raw_content_tokens` method on the same 100 pairs. Every reported count passed the same guards: no truncation, no special or unknown tokens, and a decode round-trip. The round-trip is exact except for each tokenizer's own normalization: K2 Horizon's NFC normalizer puts the combining marks of 4 Arabic texts in canonical order, as Qwen2.5's does, and AraGPT2 adds a leading space. Token tax is (TTR − 1) × 100; a negative tax means the Arabic needs fewer tokens than the English. Each row is one distinct tokenizer. Tokenizer and model developers are listed separately because they can differ.

| Tokenizer (developer) | Shipped by (model developer) | Σ AR | Σ EN | TTR | Token tax | TTR without 34, 35, 108 |
|---|---|---:|---:|---:|---:|---:|
| ALLaM (NCAI/SDAIA, Saudi Arabia) | ALLaM 7B Instruct preview (NCAI/SDAIA) | 6,097 | 7,645 | **0.798** | **−20.2%** | 0.795 |
| K2 Horizon (IFM, MBZUAI, UAE) | K2 Horizon 375B-A23B (IFM); Jais 3 375B-A23B (Jais Team: IFM/MBZUAI, Cerebras Systems, Inception42) | 6,015 | 7,202 | **0.835** | **−16.5%** | 0.832 |
| Gemma 3 (Google) | Fanar 2 27B Instruct (QCRI, Hamad Bin Khalifa University, Qatar) | 8,780 | 7,279 | **1.206** | +20.6% | 1.203 |
| DeepSeek V4.1 Flash 1017 | — | 9,693 | 7,248 | 1.337 | +33.7% | 1.334 |
| Qwen2.5-3B-Instruct | AceGPT v2 32B (KAUST and King Abdulaziz University, with CUHK-Shenzhen and SRIBD), whose Qwen1.5 tokenizer gives the same ids on this corpus | 9,811 | 7,293 | 1.345 | +34.5% | 1.340 |
| GLM-5.3 Flash | — | 10,609 | 7,277 | 1.458 | +45.8% | 1.454 |
| Kimi K3.1 Pro | — | 12,564 | 7,251 | 1.733 | +73.3% | 1.730 |
| Mistral-7B-Instruct-v0.3 | — | 23,970 | 7,921 | 3.026 | +202.6% | 3.022 |

- **The savings come from more efficient Arabic tokenization.** ALLaM's and K2 Horizon's tokenizers use about 38% fewer Arabic tokens than Qwen2.5's. Their English counts, 7,645 and 7,202, fall within the range of the other bilingual tokenizers (7,202–7,921).
- **Tokenizer origin can differ from model origin.** Fanar 2 uses Google's Gemma 3 tokenizer unchanged, and AceGPT v2 uses Qwen1.5's. Jais 3 keeps K2 Horizon's tokenizer, so the two models share one row. AceGPT's and Qwen2.5's tokenizers give identical ids on all 200 texts but are not identical: 19 added-token strings encode differently.
- **AraGPT2 Mega (American University of Beirut, Lebanon) is reported separately:** 5,942 Arabic and 13,796 English tokens (TTR 0.431). Its Arabic count is the lowest measured, but inefficient English tokenization amplifies its low ratio: as an Arabic-only tokenizer, it needs 1.9× the median tokens per English character. It was trained on text with diacritics removed and punctuation padded, and its model card asks for the arabert preprocessor. ATTI applies no preprocessing beyond whitespace normalization, so these counts describe the text as published.
- **Not measured:** ArabianGPT V2 was excluded because its tokenizer maps Arabic diacritics to the unknown token in 48 texts. Falcon-H1 Arabic has no public tokenizer, and the standard Falcon-H1 tokenizer was not substituted.

These results are experimental and kept separate from the v0.1.0 results above. Full table, provenance, licenses and pinned revisions: [`reports/current_law_v2_regional.md`](reports/current_law_v2_regional.md) and `manifest/regional_tokenizers.json`.

Per-article rows: [`results/current_law_v2.csv`](results/current_law_v2.csv) (Qwen, Mistral), [`results/current_law_v2_frontier.csv`](results/current_law_v2_frontier.csv) (DeepSeek, GLM, Kimi, Claude, GPT), [`results/current_law_v2_gemini.csv`](results/current_law_v2_gemini.csv) and [`results/current_law_v2_regional.csv`](results/current_law_v2_regional.csv). Every aggregate above can be recomputed from those four files. Generated reports: [`current_law_v2`](reports/current_law_v2.md), [`frontier`](reports/current_law_v2_frontier.md), [`gemini`](reports/current_law_v2_gemini.md), [`regional`](reports/current_law_v2_regional.md).

## How it works

- **Sources.** The Arabic is the HRSD consolidated PDF of the law (amendments through Royal Decree M/44), pinned by SHA-256. The English comes from the HRSD's English pages. The texts belong to their publishers. They are downloaded at run time and never committed; the repo stores only URLs, article IDs and hashes.
- **Pairs.** An article is eligible only if the PDF text matches the HRSD Arabic web page character for character, it is not repealed, and exactly one matching English article exists. Nothing in the official texts is repaired.
- **Selection.** 100 articles are drawn deterministically across the law's Parts and three length strata, without consulting token counts.
- **Review.** The maintainer carried out a substantive bilingual semantic review of every pair and accepted all three corpora for comparative tokenization benchmarking. An AI agent also read every pair side by side; its notes are recorded per article. Six drawn pairs whose English changes a legal element (a condition, threshold, sanction, and so on) were excluded, and the draw moved on to the next article in the same Part.
- **Counting.** Only whitespace is normalized. Local tokenizers are pinned by revision and file hash, and run-time guards reject any count with truncation, special tokens or uncovered characters.

[`docs/methodology.md`](docs/methodology.md) documents extraction, eligibility, selection, review, validation guards and the earlier corpora, and states [what the tests prove, and what they don't](docs/methodology.md#what-the-tests-prove-and-what-they-dont).

## Reproduce

Requires [uv](https://docs.astral.sh/uv/). The tokenizer results need no GPU and no API keys.

```bash
uv sync
uv run pytest -m "not network" -q   # offline: check and recompute the committed results
uv run atti v2-fetch                # download the HRSD sources into data/ (polite, cached)
uv run atti v2                      # rebuild the Qwen and Mistral results from the sources
uv run pytest -q                    # everything, incl. re-tokenizing all 100 pairs with DeepSeek, GLM and Kimi
uv run atti regional                # re-measure the Arabic-focused tokenizers (tokenizer files only)
git status                          # nothing committed should have changed
```

`atti regional` downloads about 110 MB of pinned tokenizer files, never model weights, into `data/`. ALLaM is counted with the official `sentencepiece` 0.2.1 runtime, which `uv sync` installs from the `regional` dependency group; the `atti` package does not depend on it. The command writes only the `*_regional` files. It exits with code 2 and writes nothing if a pinned file cannot be downloaded or verified, and with code 4 if a run would change a published regional result.

In a fresh clone, the full test run skips 7 tests that need the API count caches, which stay on the machine that measured the counts.

The API counts cannot be reproduced without keys. When `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY` is set, `atti frontier` and `atti gemini` re-measure by calling the providers. They validate everything before writing and never drop, change or downgrade a published result, so in a fresh clone without keys they stop with exit code 4 and write nothing. Hosted tokenizers can change without notice, so fresh API counts may differ from the committed ones; such runs are also refused. To re-measure from scratch, delete the published files first.

All commands, outputs and exit codes: [`docs/methodology.md`](docs/methodology.md#commands-and-exit-codes).

## Earlier corpora

The project started with a 10-article pilot and a 30-article `expanded_v1`. Both used the 2005 base text from the Bureau of Experts and measured only Qwen and Mistral. They are frozen and still reproduce (`atti pilot`, `atti expanded`):

| Corpus | Pairs | Qwen TTR | Mistral TTR |
|---|---:|---:|---:|
| `pilot` | 10 | 1.437 | 3.171 |
| `expanded_v1` | 30 | 1.410 | 3.203 |
| `current_law_v2` | 100 | 1.345 | 3.026 |

[`reports/current_law_v2.md`](reports/current_law_v2.md) separates how much of that drift comes from the newer source texts and how much from the larger sample.

## Limitations

- **Accepted for benchmarking, not certified as legally equivalent.** All three corpora underwent substantive bilingual semantic review and were accepted by the maintainer for comparative tokenization benchmarking. Acceptance covers use as a tokenization benchmark; it does not certify legal equivalence. The maintainer noted textual observations on `expanded_v1` Articles 32 and 70 that do not affect their inclusion. Independent external validation has not been performed. Reports, manifests and release notes generated before the acceptance keep their PROVISIONAL label and their "not human-approved" or "no human has reviewed" wording as published, hash-bound artifacts; that wording is superseded. The published pilot report says the pairs were "reviewed manually"; its recorded per-article notes (`manifest/review.json`) were written by the AI agent. See [review provenance](docs/methodology.md#review-provenance).
- **Texts as published, not verified translations.** ATTI measures the official texts as published and does not claim they are legally equivalent. Three retained pairs diverge: Article 34's English reverses which permit cannot substitute for which, Article 35 uses "or" where the Arabic has "and", and Article 108's nested list labels make its cross-reference misleading. The sensitivity columns above show that these pairs barely affect the results. Details: [`reports/current_law_v2_discrepancies.md`](reports/current_law_v2_discrepancies.md).
- **Source quirks are kept, not fixed.** The English pages mislabel Articles 101, 197 and 219, list numbering differs between languages in a few articles, and two typos are kept verbatim. Requiring two identical Arabic renderings also biases the pool toward articles without complex lists or layout.
- **API counts have weaker provenance.** The committed Claude, GPT and Gemini counts predate the current cache format. They are replayed from a cache whose counts must reproduce the committed CSVs, but provider, adapter-version and text-identity metadata were never recorded for them and are not reconstructed.
- **API counts are a snapshot.** Hosted tokenizers can change without a version change. The Gemini counts are dated 2026-11-24; no date was recorded for the Claude and GPT counts.
- **Narrow scope.** One law, one document type and one translation. The English is the ministry's published translation, whose official status is not stated. No statistical significance is claimed for differences between models.

## License

The code is released under the [MIT License](LICENSE). It covers this project's own code, documentation, token counts and derived results. It does not cover the Saudi legal texts, which belong to their publishers and are never redistributed here, or third-party tokenizer files and model weights, which keep their own licenses.

## Acknowledgments

Developed with the assistance of Claude Opus 5.5 and DeepSeek V4.1 Flash.
