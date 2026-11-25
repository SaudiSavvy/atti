# ATTI: Arabic Token Tax Index

[![CI](https://github.com/SaudiSavvy/atti/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SaudiSavvy/atti/actions/workflows/ci.yml)

How many more tokens does it take to say the same thing in Arabic than in English?

ATTI measures this on real parallel text: 100 articles of the current Saudi Labor Law, using the government-published Arabic and the ministry's published English translation. For each model, the **Token Tax Ratio** is

```
TTR = Σ Arabic tokens / Σ English tokens   (over the same 100 article pairs)
```

so 1.0 means parity and 2.0 means Arabic costs twice as many tokens. The corpus is **provisional**: an AI agent reviewed every pair and the maintainer carried out a substantive bilingual semantic review while building it, but no human review decision has been formally recorded yet.

## Results

Eight models on the same 100 pairs (`current_law_v2`). The last column drops Articles 34, 35 and 108, whose published Arabic and English differ in meaning or numbering (see [Limitations](#limitations)).

> **New in v0.2.0:** two tokenizers developed in the region make this Arabic *cheaper* to tokenize than its English translation. ALLaM's tokenizer (Saudi Arabia) has a token tax of **−20.2%**, and the K2 Horizon tokenizer, also used by Jais 3 (UAE), **−16.5%**. See [Arabic-focused and Arab-developed tokenizers](#arabic-focused-and-arab-developed-tokenizers).

**Tokenizer counts** (`raw_content_tokens`): the tokenizer run locally on the article text only, with no special tokens or chat template.

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

Keep the two tables apart. API counts include the provider's message framing (Gemini reports 35 tokens for the single character `a`). That overhead adds roughly the same amount to both languages, which pulls every API ratio toward 1.0, and it differs between providers. Nothing is subtracted, so API ratios are not comparable with tokenizer ratios, and only loosely with each other.

A few observations, without claiming more than one law can support:

- Among the local tokenizers, DeepSeek and Qwen spend about a third more tokens on Arabic, while Mistral spends about three times as many. Most of the difference is on the Arabic side; English totals vary by less than 10%.
- Dropping the three pairs with known alignment problems moves no TTR by more than 0.005, and leaves both orderings unchanged.
- These are input-token counts. They say nothing about model quality, latency, output length or pricing.

### Arabic-focused and Arab-developed tokenizers

Seven more released tokenizers were checked on the same 100 pairs with the same method (`raw_content_tokens`), using `atti regional`. Every count passed the same guards: no truncation, no special or unknown tokens, and a decode round-trip. The round-trip reproduces the text exactly, except where a tokenizer applies its own normalization. The K2 Horizon tokenizer's NFC normalizer reorders combining marks in 4 Arabic texts into their canonically equivalent form; Qwen2.5's existing result does the same. AraGPT2 adds a leading space. Token tax = (TTR − 1) × 100, so a negative tax means the Arabic text needs fewer tokens than its English translation. Each row below is one distinct tokenizer. Tokenizer and model developers are listed separately because they are not always the same.

| Tokenizer (developer) | Shipped by (model developer) | Σ AR | Σ EN | TTR | Token tax | TTR without 34, 35, 108 |
|---|---|---:|---:|---:|---:|---:|
| ALLaM (NCAI/SDAIA, Saudi Arabia) | ALLaM 7B Instruct preview (NCAI/SDAIA) | 6,097 | 7,645 | **0.798** | **−20.2%** | 0.795 |
| K2 Horizon (IFM, MBZUAI, UAE) | K2 Horizon 375B-A23B (IFM); Jais 3 375B-A23B (Jais Team: IFM/MBZUAI, Cerebras Systems, Inception42) | 6,015 | 7,202 | **0.835** | **−16.5%** | 0.832 |
| Gemma 3 (Google) | Fanar 2 27B Instruct (QCRI, Hamad Bin Khalifa University, Qatar) | 8,780 | 7,279 | **1.206** | +20.6% | 1.203 |
| DeepSeek V4.1 Flash 1017 | — | 9,693 | 7,248 | 1.337 | +33.7% | 1.334 |
| Qwen2.5-3B-Instruct | AceGPT v2 32B (KAUST and King Abdulaziz University, with CUHK-Shenzhen and SRIBD) ships the Qwen1.5 tokenizer, which gives the same ids on this corpus | 9,811 | 7,293 | 1.345 | +34.5% | 1.340 |
| GLM-5.3 Flash | — | 10,609 | 7,277 | 1.458 | +45.8% | 1.454 |
| Kimi K3.1 Pro | — | 12,564 | 7,251 | 1.733 | +73.3% | 1.730 |
| Mistral-7B-Instruct-v0.3 | — | 23,970 | 7,921 | 3.026 | +202.6% | 3.022 |

- **Arabic is where the savings are.** ALLaM's and K2 Horizon's tokenizers use about 38% fewer Arabic tokens than Qwen2.5's, while their English counts (7,645 and 7,202) stay in the range of the other bilingual tokenizers (7,202–7,921).
- **Tokenizer origin differs from model origin.** Fanar 2 uses Google's Gemma 3 tokenizer unchanged, and AceGPT v2 uses Qwen1.5's. Jais 3 keeps K2 Horizon's tokenizer unchanged, so the two models share one row. AceGPT's and Qwen2.5's tokenizers give identical ids on all 200 texts but are not identical in general; 19 added-token strings encode differently.
- **AraGPT2 Mega (American University of Beirut, Lebanon) is reported separately:** 5,942 Arabic and 13,796 English tokens (TTR 0.431). Its Arabic count is genuinely the lowest measured, but its unusually low ratio is amplified by inefficient English tokenization: as an Arabic-only tokenizer, it needs 1.9× the median tokens per English character. It was trained on text with diacritics removed and punctuation padded, and its model card asks for the arabert preprocessor. ATTI applies neither, so its counts describe the text as published.
- **Not measured:** ArabianGPT V2's tokenizer maps Arabic diacritics to its unknown token in 48 texts, so it was excluded. Falcon-H1 Arabic has no public tokenizer, and the standard Falcon-H1 tokenizer was not substituted for it.

These results are experimental and kept separate from the v0.1.0 results above. Full table, provenance, licenses and pinned revisions: [`reports/current_law_v2_regional.md`](reports/current_law_v2_regional.md) and `manifest/regional_tokenizers.json`.

Per-article rows: [`results/current_law_v2.csv`](results/current_law_v2.csv) (Qwen, Mistral), [`results/current_law_v2_frontier.csv`](results/current_law_v2_frontier.csv) (DeepSeek, GLM, Kimi, Claude, GPT) [`results/current_law_v2_gemini.csv`](results/current_law_v2_gemini.csv) and [`results/current_law_v2_regional.csv`](results/current_law_v2_regional.csv). Every aggregate above can be recomputed from those four files. Generated reports: [`current_law_v2`](reports/current_law_v2.md), [`frontier`](reports/current_law_v2_frontier.md), [`gemini`](reports/current_law_v2_gemini.md), [`regional`](reports/current_law_v2_regional.md).

## How it works

- **Sources.** The Arabic is the HRSD consolidated PDF of the law (amendments through Royal Decree M/44), pinned by SHA-256. The English comes from the HRSD's English pages. The texts belong to their publishers. They are downloaded at run time and never committed; the repo stores only URLs, article IDs and hashes.
- **Pairs.** An article is eligible only if the PDF text matches the HRSD Arabic web page character for character, it is not repealed, and exactly one matching English article exists. Nothing in the official texts is repaired.
- **Selection.** 100 articles are drawn deterministically across the law's Parts and short/medium/long lengths. Token counts are never consulted.
- **Review.** An AI agent read every pair side by side, and its notes are recorded per article; the maintainer also carried out a bilingual semantic review of the texts during development. Six drawn pairs whose English changes a legal element (a condition, threshold, sanction, and so on) were excluded, and the draw moved on to the next article in the same Part.
- **Counting.** Only whitespace is normalized. Local tokenizers are pinned by revision and file hash, and run-time guards reject any count with truncation, special tokens or uncovered characters.

The full details are in [`docs/methodology.md`](docs/methodology.md): extraction rules, eligibility, selection, review, validation guards and the earlier corpora. It also covers [What the tests prove, and what they don't](docs/methodology.md#what-the-tests-prove-and-what-they-dont).

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

`atti regional` downloads only pinned tokenizer files (about 110 MB, never model weights) into `data/`. ALLaM is counted with the official `sentencepiece` 0.2.1 runtime, which `uv sync` installs from the `regional` dependency group; it is not a dependency of the `atti` package. The command writes only the `*_regional` files. If any pinned file cannot be verified or downloaded, it exits with code 2 and writes nothing. It also refuses, with exit code 4, any run that would change a published regional result.

In a fresh clone the last test run reports 7 skipped tests. Those need the API count cache, which stays on the machine that measured them.

The API counts can't be reproduced without keys. `atti frontier` and `atti gemini` re-measure, calling the providers when `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY` is set. They validate everything before writing and never drop, change or downgrade a published result, so in a fresh clone without keys they stop with exit code 4 and write nothing. Hosted tokenizers can change without notice, so fresh API counts may differ from the committed ones. In that case the run is refused too; re-measuring from scratch means deliberately removing the published files first.

All commands, outputs and exit codes: [`docs/methodology.md`](docs/methodology.md#commands-and-exit-codes).

## Earlier corpora

The project started with a 10-article pilot and a 30-article `expanded_v1`. Both used the 2005 base text from the Bureau of Experts, and only Qwen and Mistral. They are kept frozen and still reproduce (`atti pilot`, `atti expanded`):

| Corpus | Pairs | Qwen TTR | Mistral TTR |
|---|---:|---:|---:|
| `pilot` | 10 | 1.437 | 3.171 |
| `expanded_v1` | 30 | 1.410 | 3.203 |
| `current_law_v2` | 100 | 1.345 | 3.026 |

[`reports/current_law_v2.md`](reports/current_law_v2.md) separates how much of that drift comes from the newer source texts and how much from the larger sample.

## Limitations

- **Provisional: no recorded human decisions.** An AI agent (Claude) reviewed every pair and its notes are committed. The maintainer also carried out a substantive bilingual semantic review while building the corpora. It will be recorded retrospectively, per article, in the human decision files; until an article's decision is recorded there, it is not counted as approval. No human decision has been recorded in any corpus, and nobody outside the project has validated the pairs. Where generated reports, manifests and release notes say "not human-approved", they mean no recorded decision. The published pilot report says the pairs were "reviewed manually"; its recorded per-article notes (`manifest/review.json`) were written by the AI agent, and the report is kept byte-identical as a historical artifact. Decisions can be recorded with `atti decide`.
- **Texts as published, not verified translations.** ATTI measures the official texts as they are. It does not claim they are legally equivalent. In three retained pairs they are not quite: Article 34's English reverses which permit cannot substitute for which, Article 35 uses "or" where the Arabic has "and", and Article 108's nested list labels make its cross-reference misleading. The sensitivity column above shows they barely affect the results. Details: [`reports/current_law_v2_discrepancies.md`](reports/current_law_v2_discrepancies.md).
- **Source quirks are kept, not fixed.** The English pages mislabel Articles 101, 197 and 219, list numbering differs between languages in a few articles, and two typos are kept verbatim. Requiring two identical Arabic renderings also biases the pool toward articles without complex lists or layout.
- **API counts have weaker provenance.** The committed Claude, GPT and Gemini counts predate the current cache format. They are replayed from a cache whose counts must reproduce the committed CSVs, but provider, adapter-version and text-identity metadata were never recorded for them and are not reconstructed.
- **API counts are a snapshot.** Hosted tokenizers can change without a version change. The Gemini counts are dated 2026-11-24; no date was recorded for the Claude and GPT counts.
- **Narrow scope.** One law, one document type, and one translation. The English is the ministry's published translation, whose official status is not stated. No statistical significance is claimed for differences between models.

## License

The code is released under the [MIT License](LICENSE). It covers this project's own code, documentation, token counts and derived results. It does not cover the Saudi legal texts, which belong to their publishers and are never redistributed here, or third-party tokenizer files and model weights, which keep their own licenses.

## Acknowledgments

Developed with the assistance of Claude Opus 5.5 and DeepSeek V4.1 Flash.
