# Methodology

Details behind the [README](../README.md): sources, extraction, selection, review, measurement, and what the test suite does and does not establish.

- [Corpora](#corpora)
- [current_law_v2](#current_law_v2)
- [Measurement](#measurement)
- [Historical corpora: pilot and expanded_v1](#historical-corpora-pilot-and-expanded_v1)
- [Human validation](#human-validation)
- [Commands and exit codes](#commands-and-exit-codes)
- [What the tests prove, and what they don't](#what-the-tests-prove-and-what-they-dont)
- [Layout](#layout)

## Corpora

| Corpus | Pairs | Sources | Manifest | Results | Review status |
|---|---:|---|---|---|---|
| `current_law_v2` | 100 | HRSD, current consolidated law | `manifest/current_law_v2_manifest.json` | `results/current_law_v2*.csv`, `reports/current_law_v2*.md` | **provisional**: AI-reviewed (97 PROPOSED_PASS, 3 NEEDS_REVIEW; 6 review exclusions, 5 replacements), no human approval |
| `expanded_v1` | 30 (pilot 10 + 20) | BOE, 2005 base text | `manifest/expanded_v1_manifest.json` | `results/expanded_v1.csv`, `reports/expanded_v1.md` | **provisional**: AI-reviewed, no human approval |
| `pilot` | 10 | BOE, 2005 base text | `manifest/pilot_manifest.json` | `results/pilot.csv`, `reports/pilot.md` | AI-reviewed, not human-approved |

`pilot` and `expanded_v1` are frozen historical corpora; their files are only read by later runs.

**Review provenance.** Every pair in every corpus was reviewed side by side by an AI agent (Claude). No human has approved any pair. The published pilot report says "reviewed manually"; that review was agent-performed. The pilot report is kept byte-identical as a published artifact, so the wording is corrected here and in `manifest/review.json`. The `expanded_v1` manifest records its provenance in `review_provenance`, and its report carries a PROVISIONAL banner.

**Text is not redistributed.** Legal texts are downloaded at run time into git-ignored `data/`. The repository stores only URLs, article identifiers and SHA-256 hashes, and a test checks that no article text appears in repository files.

## current_law_v2

**Scope.** ATTI measures tokenization of Saudi government-published Arabic and English legal texts *as published*. It is not a legal translation equivalence benchmark. Semantic differences in retained pairs (Articles 34, 35 and 108) are documented as source-alignment limitations in `manifest/current_law_v2_review.json` and `reports/current_law_v2.md`.

### Sources

The current consolidated law, with amendments through Royal Decree M/44 (in force from 1446/8/20 AH):

| Role | Source |
|---|---|
| Arabic (measured) | HRSD consolidated PDF, pinned by SHA-256 `cfb8e0e6…` |
| English (measured) | HRSD English pages: 16 Parts, discovered from the official index |
| Arabic cross-check | HRSD Arabic HTML pages (x-default alternates) |
| Legal-version checks | BOE register; Umm Al-Qura gazette |

The English is the ministry's published translation; its official status is not stated on the pages. Full evidence: [`reports/current_law_v2_sources.md`](../reports/current_law_v2_sources.md).

`atti v2-fetch` is deliberately polite: one request at a time, at least 2 s apart, with backoff, verified TLS and a write-once cache. Every request and redirect must stay on `https://www.hrsd.gov.sa` (the BOE downloader likewise on `https://laws.boe.gov.sa`); anything else is refused before it is contacted.

### Extraction

- **English:** HTTPX and selectolax over server-rendered HTML, so no browser automation is needed. `<ol>` numbering is rebuilt as "N.", and section titles end an article.
- **Arabic:** PyMuPDF, with lines classified by font size: headings, body, repealed marker, footnotes (excluded) and titles.
- **Arabic layout cleanup**, kept separate from the whitespace normalization used for counting: presentation-form letters are converted to base letters, justification tatweel is removed, and mirrored brackets are swapped back.

### Eligibility

An article pair qualifies only if:

- the PDF text is character-identical to the HRSD Arabic HTML text, apart from HTML-only tatweel/ZWNJ;
- it is not repealed;
- it has exactly one correctly numbered English article in the same Part.

Nothing is repaired. Of the 249 Arabic articles (245 plus 4 bis), 175 qualify. The draw uses the 172 that qualified when the corpus was curated (2026-11-23). Articles 33, 79 and 79 bis qualified only after two parser fixes on 2026-11-24 and are recorded as `eligible_outside_draw`. Those fixes changed none of the 100 selected texts, so the measured pairs are kept. Exclusions and reasons are in the manifest's `candidates` block.

Requiring two identical Arabic renderings skews the pool toward articles without lists or layout quirks.

### Source anomalies (reported, not repaired)

- The English pages label Articles 101, 197 and 219 as "10", "194" and "210", so those numbers appear twice.
- Article 79 bis is published as "Article 79:(Bis)"; an earlier parser misread it as a second Article 79 (fixed 2026-11-24).
- Clause numbering differs between the languages in some articles (e.g. 15, 64, 108); the content corresponds.
- Two source typos are kept verbatim: a stray "0" in Arabic Article 181 and "seafarer1" in English Article 184.

### Selection

Deterministic and token-blind (token counts, ratios and English length are never consulted):

- each Part gets a minimum of 2 articles, with the remaining quota proportional to its pool size;
- within a Part, picks cycle through short, medium and long thirds by Arabic length;
- ties are broken by `SHA-256("atti-current-law-v2:<key>")`.

### Review

- `manifest/current_law_v2_review.json` holds the AI pair review: statuses PROPOSED_PASS, NEEDS_REVIEW, FAIL, MISSING_SOURCE and VERSION_MISMATCH, with evidence, including a re-evaluation of v1's disputed Articles 45, 65, 108 and 134.
- **Review exclusions.** A pair is excluded when the English adds, drops or changes a legal element (negation, condition, threshold, scope, sanction, legal basis) or reflects another legal version (`EXCLUDED_AFTER_REVIEW` in `src/atti/v2.py`). Each excluded pick is replaced by the next draw from the same Part and length stratum; no other selection moves. Six pairs were excluded (40, 63, 66, 81, 189, and the rejected replacement draw 76). Sources, short excerpts and findings: [`reports/current_law_v2_discrepancies.md`](../reports/current_law_v2_discrepancies.md).
- **Retained with documented limitations.** Article 34 (direction of substitution reversed in the English), Article 35 ("and" vs "or"), and Article 108 (nested list labels make the English cross-reference misleading). The README reports results with and without these three.
- `atti v2-manifest` refuses to rebuild the manifest once any human decision is recorded, because decisions are bound to the manifest hash. While the decision template is empty, it is re-bound to the new manifest.
- Human decisions go in `review/current_law_v2_human_decisions.json` (see [Human validation](#human-validation)).

### Comparison with the historical corpora

The migration record is `manifest/current_law_v2_migration.json`. `reports/current_law_v2.md` separates a *source* effect (the same 15 articles with old BOE and new HRSD texts) from a *sample-composition* effect. Tokenizers are unchanged between corpora.

**Manifest verification.** `v2.verify()` rejects any manifest that is empty or has duplicate keys or ids, malformed hashes or keys, missing or mistyped fields, inadmissible statuses, or a mismatch with `selection.selected`, the candidates or the source texts. Such a manifest is never measured. The v1 `corpus.verify()` rejects empty and duplicate article lists.

## Measurement

**TTR (Token Tax Ratio) = Σ Arabic tokens / Σ English tokens** per model over the same pairs. Medians, minima and maxima are over per-article ratios. Tokens per 1,000 characters use the normalized text lengths.

**Normalization.** Only layout whitespace is changed: every whitespace run (PDF line wraps, `<br>`, NBSP) becomes one space, and the ends are trimmed. No Unicode normalization, punctuation or diacritic changes.

There are two measurement methods, and they are never ranked together.

### `raw_content_tokens`: local tokenizers

| Model | Tokenizer source |
|---|---|
| Qwen2.5-3B-Instruct | `tokenizer.json` @ `aa8e72537993ba99e69dfaafa59ed015b17504d1` |
| Mistral-7B-Instruct-v0.3 | `tokenizer.json` @ `c170c708c41dac9275d15a8fff4eca08d52bab71` |
| DeepSeek V4.1 Flash 1017 | `tokenizer.json`, pinned revision and SHA-256 |
| GLM-5.3 Flash | `tokenizer.json`, pinned revision and SHA-256 |
| Kimi K3.1 Pro | `tiktoken.model` with the pre-tokenizer and split rule of its `tokenization_kimi.py` |

- Only allow-listed tokenizer files are downloaded (anonymously, about 29 MB for the three frontier tokenizers); never model weights. Every tokenizer file's SHA-256 is checked against its pin before it is loaded; revisions and hashes are in `results/current_law_v2_summary.json` and `manifest/frontier_tokenizers.json`.
- Counts use `encode(text, add_special_tokens=False)`: no BOS/EOS and no chat template. Truncation and padding are disabled.
- A count is refused, not estimated, if a text contains literal control-token strings. All 200 texts passed.
- Qwen and Mistral were cross-checked during development against `transformers.AutoTokenizer` (fast) and Mistral's SentencePiece slow tokenizer on the pilot: all 40 counts matched. DeepSeek, GLM and Kimi token IDs were checked against the official implementations on all 200 corpus texts; synthetic reference IDs are in `tests/frontier_reference_ids.json`.

### Arabic-focused and Arab-developed tokenizers (experimental)

`atti regional` measures further tokenizers with the same `raw_content_tokens` method, on the same 100 pairs and texts, with the same whitespace normalization, metrics and special-token policy. Its outputs are separate (`results/current_law_v2_regional*`, `reports/current_law_v2_regional.md`, `manifest/regional_tokenizers.json`); every other result is only read.

- **Assets.** Only `tokenizer.json`, `tokenizer.model` and `tokenizer_config.json` are downloaded, anonymously, at pinned revisions, and each file's SHA-256 is checked before use. No weights are downloaded and no repository code is run.
- **Guards.** Every text must pass the guards above, give identical ids when encoded twice, and decode back to itself. The only allowed differences are the tokenizer's own NFC/NFKC normalization and the GPT-2 prefix space. A tokenizer that fails on any text is **EXCLUDED**, and no count is published for it.
- **Equivalence.** The token ids of all 200 texts are hashed (`ids_sha256`) and compared with every tokenizer already in ATTI and with each other. A tokenizer with identical ids is **EQUIVALENT**: it is listed with its group, never as an independent result.
- **Availability.** A tokenizer that cannot be verified is **UNAVAILABLE**, and nothing is substituted for it.
- **SentencePiece without `tokenizer.json`.** For ALLaM, ATTI reads `tokenizer.model` with a standard-library protobuf reader and encodes in SentencePiece's own order: normalize once, split out user-defined symbols, then BPE with byte fallback. On all 200 corpus texts and the synthetic cases in `tests/regional_reference_ids.json`, its ids match the official `sentencepiece` library, which was run in an isolated environment and is not a dependency.
- **Sensitivity and comparison.** TTR without Articles 34, 35 and 108 is computed from the rows for both the new and the existing tokenizers. The existing values are cross-checked against their published summaries.
- **English efficiency.** A ratio can fall below 1 because English is tokenized poorly rather than Arabic well. Any tokenizer whose English tokens per 1,000 characters exceed 1.5× the median is flagged.

### `api_input_tokens`: provider counting endpoints

| Model | Endpoint | Key |
|---|---|---|
| Claude Opus 5.5 | Anthropic `POST /v1/messages/count_tokens` | `ANTHROPIC_API_KEY` |
| GPT-6.2 Sol | OpenAI `POST /v1/responses/input_tokens` | `OPENAI_API_KEY` |
| Gemini 4 Neon | Google `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-4-neon:countTokens` (`totalTokens`) | `GEMINI_API_KEY` |

- Each request is one user message whose content is the article text, with no system prompt or tools. For Gemini: `{"contents": [{"role": "user", "parts": [{"text": ...}]}]}`.
- The provider's framing is included in the count and never subtracted. It adds a similar absolute amount to both languages, which pulls the ratio toward 1, and it differs between providers.
- Keys are read from the environment and sent only in request headers (Gemini: `x-goog-api-key`), never in URLs, logs, caches or outputs.
- Counts are cached write-once in git-ignored `data/api_cache/`, which holds counts, never keys. Without credentials or cache, an adapter is reported BLOCKED with no value.
- Gemini requests are at least 1 s apart, with up to 6 retries and exponential backoff on 429, 5xx and transport errors; 401, 403 and 404 fail immediately. `atti gemini --pilot-only` counts the frontier pilot's ten articles twice each for repeatability, plus short-input observations (a one-character input costs 35 tokens).
- `atti frontier` runs a 10-pair pilot per adapter and measures all 100 pairs only for adapters that pass. `atti gemini` never calls the Anthropic or OpenAI APIs, and neither command writes historical outputs.
- **Historical cache limitation.** The committed Claude, GPT and Gemini counts were measured before cache schema 2. Provider, text-identity, adapter-version and count-field metadata were never recorded and are not reconstructed. A cache is accepted only if its 200 article counts reproduce an anchor pinned to the SHA-256 of the committed CSV (`HISTORICAL_API_ANCHORS` in `src/atti/frontier.py`, `GEMINI_ANCHOR` in `src/atti/gemini.py`).
- A hosted model's tokenizer can change without a version change, so API counts are a snapshot, not pinned. Gemini was measured on 2026-11-24 (`manifest/gemini_4_neon.json`); no measurement date was recorded for the Claude and GPT counts.

### Run-time guards

`tokenization.count_tokens` applies these to every published raw count. A count is rejected unless:

1. truncation and padding are both disabled, and there are no overflow segments;
2. every non-whitespace character of the input lies inside some token's offset span;
3. no special-token id or unknown-token id appears in the content encoding.

Guard 2 replaces an earlier check that the last token's offset ends at `len(text)`. That check was misleading: left-side truncation keeps the end of the text, so it would still pass, and it said nothing about characters dropped in the middle. `test_last_offset_check_was_insufficient_left_truncation` demonstrates the gap.

## Historical corpora: pilot and expanded_v1

Both use the 2005 base text of the Saudi Labor Law (Royal Decree M/51 of 1426/08/23 AH, 2005-09-27) from the Bureau of Experts (BOE). Both sources record amendments up to Royal Decree M/44 of 1446/02/08 AH (2024-08-12).

| Lang | Publisher | URL |
|---|---|---|
| Arabic (governing) | Bureau of Experts at the Council of Ministers | https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/08381293-6388-48e2-8ad2-a9a700f2aa94/1 |
| English (official translation) | BOE Official Translation Department (PDF) | https://laws.boe.gov.sa/Files/Download/?attId=704cf56e-eb7a-4ddb-8c28-adbb01244dc6 |

### Pair verification

The two BOE sources represent amendment history differently. The English PDF body is the 2005 text with all amendments in an appendix. The Arabic page shows the base text and flags amended articles (`changed-article`), with amendment text in pop-ups. Matching article numbers therefore do **not** imply matching content. A pair is eligible only when:

1. the Arabic page has exactly one non-"bis" article with that number, and does not flag it as amended;
2. the English appendix never references that article number (intentionally over-inclusive: a mere mention counts as affected);
3. both texts are nonempty; and
4. a side-by-side content review is recorded in `manifest/review.json`.

Every `atti pilot` run re-extracts both texts and checks them, and the English PDF, against the manifest hashes. Any change stops the run with `VERIFICATION FAILED`.

Source disagreements found during curation are recorded in the manifest's `audit` block, and all are excluded:

- **Articles 98–100 and 104 (working hours):** the English appendix includes a 2015 amendment (Royal Decree M/46) that the Arabic page does not show.
- **Articles 233–235:** appear twice on the Arabic page, as the repealed originals and as the articles added in 2018.
- **Part 14 (Articles 210–228):** repealed as a whole; the English appendix says so without listing article numbers.

### Extraction

- **Arabic:** HTML article body with tags removed and entities unescaped.
- **English:** `pdfminer.six`, with the running page header/footer and section headings removed. `pypdf` was rejected because it inserted spurious spaces (e.g. "t he", "part -time"). The 10 pilot English texts match poppler's `pdftotext` output exactly after normalization.

### expanded_v1 selection (`src/atti/selection.py`)

Deterministic and ratio-blind:

1. **Pool:** eligible pairs, minus the 10 pilot articles, minus two groups affected by *global* amendments not attached to individual articles:
   - **Part 11 (Marine Employment Contract):** Royal Decree M/44 redefined its key terms by reference to the Commercial Maritime Law.
   - **Articles mentioning the Labor Dispute Commissions:** Royal Decree M/1 replaced that phrase "wherever mentioned". The check matches capitalized "Commission" in the English or "تسوية الخلافات" in the Arabic; lowercase sales "commissions" stays eligible.
2. **Strata:** the pool is sorted by Arabic character count and cut into thirds.
3. **Quotas:** 7 short, 7 medium, 6 long.
4. **Picking:** within each stratum, repeatedly take the candidate whose Part has the fewest articles selected so far (pilot included); ties by `SHA-256("atti-expanded-v1:<article>")`.

Parts come from the Arabic page's Part headings, cross-checked against poppler's reading of the English PDF (pdfminer misorders two Part headings).

**Review.** Each new pair was read side by side, checking numbered clauses and sub-clauses, enumerated lists, exceptions, numbers, percentages, dates and legal references. Automated checks confirm that every digit sequence in the Arabic appears in the English and that the English matches poppler's output exactly. A failing pair would go into `selection.EXCLUDED` with a reason and the selection would be re-run; none failed. Two translation nuances (Articles 29 and 45) are recorded in `manifest/expanded_v1_review.json`.

## Human validation

A corpus stays provisional until a human has recorded a decision for every pair. The material lives in three places (shown for `expanded_v1`; `current_law_v2` is analogous):

| File | Content | Author | Committed? |
|---|---|---|---|
| `review/expanded_v1_ai_review.json` | AI proposed status (PASS / NEEDS_REVIEW / FAIL), evidence, material discrepancies | AI agent; the second pass is by the same model, so it is not independent | yes (no legal text) |
| `review/expanded_v1_human_decisions.json` | APPROVE / REJECT / REQUEST_EXAMINATION, reviewer, date, comment | **human only** | yes, once filled in |
| `data/review/expanded_v1_review_sheet.md` | both full texts side by side, AI notes, recorded decisions | generated | **no** (git-ignored; contains legal texts) |

To record decisions:

1. `uv run atti review-sheet [--corpus current_law_v2]` re-extracts and hash-verifies the pairs, writes the sheet, creates an empty decision template if none exists (never overwriting one), and validates recorded decisions.
2. Read each pair and record a decision, either by editing the decisions file or with `uv run atti decide <article> <APPROVE|REJECT|REQUEST_EXAMINATION> --reviewer "<name or pseudonym>" [--comment ...] [--corpus ...]`. A comment is required for anything other than APPROVE. The reviewer can be a stable pseudonym such as a GitHub handle; a civil name is not required.
3. Re-run `review-sheet`. It exits with code 2 if the file is invalid: an unknown decision, missing name or date, an AI-system reviewer name, or a manifest hash mismatch.

Decisions are bound to the manifest's SHA-256. A REJECT does not remove an article automatically. Excluding one is a separate, reported change that replaces the pair and alters the results, which would then need a new corpus version.

## Commands and exit codes

| Command | What it does | Writes |
|---|---|---|
| `atti v2-fetch` | Politely downloads the HRSD sources for `current_law_v2`; cached files are never replaced. | `data/raw_v2/` (git-ignored) |
| `atti v2` | Reproduces the Qwen/Mistral `current_law_v2` results from the pinned cache. Historical files are only read. | `results/current_law_v2.csv`, `results/current_law_v2_summary.json`, `reports/current_law_v2{,_sources,_discrepancies}.md`, `manifest/current_law_v2_migration.json` |
| `atti frontier [--pilot-only]` | Pilots, then measures, DeepSeek, GLM, Kimi, Claude and GPT. Without keys or the local API cache, Claude and GPT cannot be measured, so the run is refused (see below). To check the committed local-tokenizer rows, run `pytest -q` (`test_local_rows_reproduce_byte_for_byte`). | `results/current_law_v2_frontier*`, `reports/current_law_v2_frontier.md`, `manifest/frontier_tokenizers.json` |
| `atti gemini [--pilot-only]` | Pilots, then measures, Gemini 4 Neon. Without a key or cache it writes nothing and exits with code 4 (BLOCKED). | `results/current_law_v2_gemini*`, `reports/current_law_v2_gemini.md`, `manifest/gemini_4_neon.json` |
| `atti regional` | Measures the Arabic-focused and Arab-developed tokenizers; records EQUIVALENT, EXCLUDED and UNAVAILABLE tokenizers with evidence. Uses the same publish guard. | `results/current_law_v2_regional*`, `reports/current_law_v2_regional.md`, `manifest/regional_tokenizers.json` |

**Published results are protected.** `atti frontier`, `atti gemini` and `atti regional` validate every row before writing (each model covers exactly the 100 corpus articles with positive counts and consistent ratios), then write all outputs or none. They refuse, with exit code 4 and nothing written, any run that would remove or change a published model's rows, alter a recorded passing pilot, or turn a MEASURED adapter into anything else (`frontier.publish`, tested in `tests/test_publish.py`). Re-measuring from scratch is a deliberate step: remove the published files first. `atti pilot`, `atti expanded` and `atti v2` are deterministic and write only after the sources verify against the manifest hashes.
| `atti v2-manifest` | Curation only: rebuilds the manifest from the cache and the AI review file. | `manifest/current_law_v2_manifest.json` |
| `atti pilot` | Reproduces the pilot from `data/raw`, downloading a source only if missing. Checks every article against the manifest hashes, then counts tokens. | `results/pilot.csv`, `results/pilot_summary.json`, `reports/pilot.md` |
| `atti expanded` | Same for the 30-article `expanded_v1` corpus; never touches pilot files. | `results/expanded_v1.csv`, `results/expanded_v1_summary.json`, `reports/expanded_v1.md` |
| `atti verify-live [--corpus expanded_v1]` | Downloads fresh BOE sources into a temporary directory (deleted afterwards) and compares them with the manifest and, if present, the cached baseline. Never updates hashes or approves text. | nothing |
| `atti fetch` | Downloads missing BOE sources. | `data/raw/` (git-ignored) |
| `atti manifest [--corpus expanded_v1]` | Curation only: rebuilds a v1 manifest; refuses ineligible articles or ones without a review note. | `manifest/pilot_manifest.json` or `manifest/expanded_v1_manifest.json` |
| `atti review-sheet`, `atti decide` | Human validation, see above. | `data/review/`, `review/*_human_decisions.json` |

| Code | `pilot` | `verify-live` |
|---|---|---|
| 0 | success | `CLEAN`: all selected articles verified and no source change detected |
| 1 | — | `SOURCE_CHANGED`: selected articles verified, but the law changed elsewhere (PDF bytes, other articles, amendment lists) |
| 2 | `VERIFICATION FAILED` | `ARTICLES_FAILED`: a selected article is changed, missing or ineligible, or a fresh source could not be parsed |
| 3 | `NETWORK ERROR` | `NETWORK ERROR` |

## What the tests prove, and what they don't

`uv run pytest -m "not network" -q` runs the offline tests. `uv run pytest -q` adds the `network` tests, which need the cached sources and tokenizers (downloaded on first run).

**Stronger checks on the two pinned tokenizers** (`network` tests, all pilot and expanded pairs):

- Offsets cover *every* character, including whitespace.
- `decode(ids)` equals the tokenizer's own normalization of the input. Mistral has no normalizer, so decoding reproduces the text exactly. Qwen applies Unicode NFC; Arabic Articles 65 and 92 contain combining marks in non-NFC order, so they decode to their NFC form. That is expected, not data loss, and the test pins exactly these two cases.
- No special tokens appear in content counts. (Mistral would add `<s>` with `add_special_tokens=True`; Qwen adds nothing.)
- Counts are identical across fresh tokenizer loads, and a fresh measurement reproduces `results/pilot.csv` byte for byte.

**Results checks** (offline):

- A missing published artifact fails the tests; it is never skipped.
- CSV rows must match the manifest (ids, hashes, character counts) and the pinned revisions.
- TTR, median, min and max are recomputed from the CSV integers with exact fractions, independently of `atti.metrics`.
- Published totals are pinned (pilot: Qwen 1290/898, Mistral 3114/982), and historical artifacts are pinned by SHA-256 in `tests/historical_sha256.json`.
- Summaries and reports must regenerate byte for byte from the CSV and manifest. API-based outputs regenerate byte for byte from the anchored cache without keys.

**Corpus and selection checks:**

- `expanded_v1`: all 30 entries are unique and reviewed; the 10 pilot entries and rows equal the pilot's; totals are pinned. The selection is deterministic, order-independent and ignores the English side; quotas and exclusion rules are tested. `network` tests rebuild the selection from the sources and reproduce `expanded_v1.csv` byte for byte.
- `current_law_v2`: the 100 measured keys and text hashes are pinned in `tests/current_law_v2_pairs_frozen.json` and checked against an independent digest (`v2.FROZEN_PAIRS_SHA256`), so a manifest edited consistently in several places is still rejected.

**Source checks:**

- Network failures are reported separately from verification failures.
- Without a cached baseline, `verify-live` states that only the selected articles were verified and that the full-source comparison was not performed.
- Changed, missing and ineligible articles are each detected, and changes outside the selected articles are distinguished from changes to them. `verify-live` never modifies the baseline.
- This is tested offline with mocked downloads; one `network` test replays the real cached sources and tampers with one word.

**Not proven:**

- That offsets align with *linguistic* units. They only show that characters are attributed to tokens.
- That production inference for these models uses the same tokenizer files. The Qwen/Mistral cross-check against `transformers` and SentencePiece is not part of the test suite.
- That the Arabic and English texts are legally equivalent beyond the recorded AI review.
- That any pair is human-approved.
- That the official sources are unchanged *today*. Only `atti verify-live` checks that, at the moment it runs, and only for the BOE sources. The Arabic page bytes are not compared because they embed a live view counter; only the parsed article text, headings and amendment flags are.
- That API counts would be the same today, or that they isolate content tokens.

## Layout

```
src/atti/  cli.py           command line
           sources.py       BOE URLs, cached downloader
           live.py          verify-live (fresh download -> temp dir -> compare)
           arabic.py        BOE HTML -> articles
           english.py       BOE PDF -> articles + amendment-appendix references
           hrsd.py          HRSD fetcher, English/Arabic HTML and Arabic PDF extraction
           textnorm.py      the single whitespace normalization
           corpus.py        v1 eligibility rule, manifest build + verification
           selection.py     deterministic expanded_v1 selection
           v2.py            current_law_v2 eligibility, QA, selection, measurement, report, migration
           tokenization.py  pinned tokenizer loading, content-only counting, run-time guards
           frontier.py      DeepSeek/GLM/Kimi tokenizers, Claude/GPT counting APIs, API cache
           gemini.py        Gemini countTokens adapter
           regional.py      Arabic-focused/Arab-developed tokenizers, SentencePiece reader, equivalence
           review.py        review sheet, decision template + validation
           metrics.py / pipeline.py / report.py
manifest/  article manifests, AI review files, adapter manifests
results/   per-article CSVs and summaries
reports/   generated Markdown reports, sources and discrepancy notes
review/    AI review and human decision files
tests/
```
