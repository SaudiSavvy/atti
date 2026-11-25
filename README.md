# ATTI: Arabic Token Tax Index

How many more tokens does it take to say the same thing in Arabic than in English?

ATTI measures this on real parallel text: 100 articles of the current Saudi Labor Law, using the government-published Arabic and the ministry's published English translation. For each model, the **Token Tax Ratio** is

```
TTR = Σ Arabic tokens / Σ English tokens   (over the same 100 article pairs)
```

so 1.0 means parity and 2.0 means Arabic costs twice as many tokens. The corpus is **provisional**: every pair was reviewed by an AI agent, and none has been approved by a human yet.

## Results

Eight models on the same 100 pairs (`current_law_v2`). The last column drops Articles 34, 35 and 108, whose published Arabic and English differ in meaning or numbering (see [Limitations](#limitations)).

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

Per-article rows: [`results/current_law_v2.csv`](results/current_law_v2.csv) (Qwen, Mistral), [`results/current_law_v2_frontier.csv`](results/current_law_v2_frontier.csv) (DeepSeek, GLM, Kimi, Claude, GPT) and [`results/current_law_v2_gemini.csv`](results/current_law_v2_gemini.csv). Every aggregate above can be recomputed from those three files. Generated reports: [`current_law_v2`](reports/current_law_v2.md), [`frontier`](reports/current_law_v2_frontier.md), [`gemini`](reports/current_law_v2_gemini.md).

## How it works

- **Sources.** The Arabic is the HRSD consolidated PDF of the law (amendments through Royal Decree M/44), pinned by SHA-256. The English comes from the HRSD's English pages. The texts belong to their publishers. They are downloaded at run time and never committed; the repo stores only URLs, article IDs and hashes.
- **Pairs.** An article is eligible only if the PDF text matches the HRSD Arabic web page character for character, it is not repealed, and exactly one matching English article exists. Nothing in the official texts is repaired.
- **Selection.** 100 articles are drawn deterministically across the law's Parts and short/medium/long lengths. Token counts are never consulted.
- **Review.** An AI agent read every pair side by side. Six drawn pairs whose English changes a legal element (a condition, threshold, sanction, and so on) were excluded, and the draw moved on to the next article in the same Part.
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
git status                          # nothing committed should have changed
```

In a fresh clone the last test run reports 6 skipped tests. Those replay the API count cache, which stays on the machine that measured them.

The API counts can't be reproduced without keys. `atti frontier` and `atti gemini` re-measure from scratch, calling the providers when `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY` is set. In a fresh clone without keys, `atti frontier` rewrites the frontier result files with Claude and GPT marked BLOCKED (`git checkout -- results reports manifest` restores them), and `atti gemini` exits with code 4 without writing anything. Hosted tokenizers can change without notice, so fresh API counts may differ from the committed ones.

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

- **Provisional, AI-reviewed.** All pair review was done by an AI agent (Claude). No human has approved any pair, in any corpus. The published pilot report says the pairs were "reviewed manually"; that review was also agent-performed. The report is kept byte-identical as a historical artifact, and the correction is recorded in [`docs/methodology.md`](docs/methodology.md#corpora) and `manifest/review.json`. Human decisions can be recorded with `atti decide`.
- **Texts as published, not verified translations.** ATTI measures the official texts as they are. It does not claim they are legally equivalent. In three retained pairs they are not quite: Article 34's English reverses which permit cannot substitute for which, Article 35 uses "or" where the Arabic has "and", and Article 108's nested list labels make its cross-reference misleading. The sensitivity column above shows they barely affect the results. Details: [`reports/current_law_v2_discrepancies.md`](reports/current_law_v2_discrepancies.md).
- **Source quirks are kept, not fixed.** The English pages mislabel Articles 101, 197 and 219, list numbering differs between languages in a few articles, and two typos are kept verbatim. Requiring two identical Arabic renderings also biases the pool toward articles without complex lists or layout.
- **API counts have weaker provenance.** The committed Claude, GPT and Gemini counts predate the current cache format. They are replayed from a cache whose counts must reproduce the committed CSVs, but provider, adapter-version and text-identity metadata were never recorded for them and are not reconstructed.
- **API counts are a snapshot.** Hosted tokenizers can change without a version change. The Gemini counts are dated 2026-11-24; no date was recorded for the Claude and GPT counts.
- **Narrow scope.** One law, one document type, and one translation. The English is the ministry's published translation, whose official status is not stated. No statistical significance is claimed for differences between models.
