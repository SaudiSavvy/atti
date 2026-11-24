# ATTI: Arabic Token Tax Index (pilot)

ATTI compares how many tokens open LLM tokenizers spend on Arabic text versus English text with the same meaning. This pilot uses 10 verified article pairs from the official Arabic **Saudi Labor Law** and its official English translation.

**TTR (Token Tax Ratio) = Σ Arabic tokens / Σ English tokens**, computed per tokenizer. The pilot also reports absolute totals and the median per-article ratio.

This is an engineering pilot, not a full academic benchmark.

## Setup and reproduction

Requires [uv](https://docs.astral.sh/uv/) and internet access on the first run. No API keys, GPU, or paid inference needed.

```bash
uv sync
uv run atti pilot                  # reproduce from the cached baseline corpus
uv run atti expanded               # reproduce the 30-article expanded_v1 corpus
uv run atti verify-live            # compare today's official sources with the manifest
uv run atti verify-live --corpus expanded_v1
uv run pytest -m "not network" -q  # offline tests (no downloads)
uv run pytest -q                   # all tests (needs the cache, downloaded on first run)
```

| Command | What it does | Writes |
|---|---|---|
| `atti pilot` | Reproduces the benchmark from `data/raw`. It downloads a source only if it is missing (first run) and never replaces a cached file. It checks every article against the manifest hashes, then counts tokens. | `results/pilot.csv`, `results/pilot_summary.json`, `reports/pilot.md` |
| `atti expanded` | Does the same as `pilot` for the 30-article `expanded_v1` corpus. It writes only `expanded_v1` artifacts; the pilot files are never touched. | `results/expanded_v1.csv`, `results/expanded_v1_summary.json`, `reports/expanded_v1.md` |
| `atti verify-live [--corpus expanded_v1]` | Downloads fresh official sources into a temporary directory, which is deleted afterwards. It compares them with the manifest and, if present, with the cached baseline. It never updates hashes or approves new text. | nothing |
| `atti fetch` | Downloads missing sources into `data/raw`. | `data/raw` (git-ignored) |
| `atti manifest [--corpus expanded_v1]` | Rebuilds a manifest. Only use this as a deliberate curation step. It refuses articles that are ineligible or have no review note in `manifest/review.json`. | `manifest/pilot_manifest.json` |

**Exit codes:**

| Code | `pilot` | `verify-live` |
|---|---|---|
| 0 | success | `CLEAN`: all selected articles verified and no source change detected |
| 1 | — | `SOURCE_CHANGED`: selected articles verified, but the law changed elsewhere (PDF bytes, other articles, amendment lists) |
| 2 | `VERIFICATION FAILED` | `ARTICLES_FAILED`: a selected article is changed, missing or ineligible, or a fresh source could not be parsed |
| 3 | `NETWORK ERROR` (download failed) | `NETWORK ERROR` (download failed) |

## Sources (not redistributed)

The legal texts are **downloaded at runtime** into `data/` (git-ignored) and are never committed. The repository stores only URLs, article identifiers, and SHA-256 hashes. A test checks that no article text appears in repository files.

| Lang | Publisher | URL |
|---|---|---|
| Arabic (governing) | Bureau of Experts at the Council of Ministers | https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/08381293-6388-48e2-8ad2-a9a700f2aa94/1 |
| English (official translation) | BOE Official Translation Department (PDF) | https://laws.boe.gov.sa/Files/Download/?attId=704cf56e-eb7a-4ddb-8c28-adbb01244dc6 |

The law is Royal Decree M/51 of 1426/08/23 AH (2005‑09‑27). Both sources record amendments up to Royal Decree M/44 of 1446/02/08 AH (2024‑08‑12).

## Corpora

| Corpus | Articles | Manifest | Results | Review status |
|---|---:|---|---|---|
| `pilot` | 10 | `manifest/pilot_manifest.json` | `results/pilot.csv`, `reports/pilot.md` | agent-reviewed, **not human-approved** |
| `current_law_v2` | 100 (new sources) | `manifest/current_law_v2_manifest.json` | `results/current_law_v2.csv`, `reports/current_law_v2.md` | **PROVISIONAL**: AI-reviewed (97 PROPOSED_PASS, 3 NEEDS_REVIEW source-alignment limitations; 6 review exclusions, 5 replacements), human approval pending |
| `expanded_v1` | 30 (the pilot 10 + 20) | `manifest/expanded_v1_manifest.json` | `results/expanded_v1.csv`, `reports/expanded_v1.md` | **PROVISIONAL**: agent-reviewed, human approval pending |

**Review provenance.** Every pair in both corpora was reviewed side by side by an AI agent (Claude). No human has approved any pair. The published pilot report says "reviewed manually"; that review was agent-performed. The pilot report is kept byte-identical as a published artifact, so the wording is corrected here and in `manifest/review.json`. The `expanded_v1` manifest records the review provenance explicitly (`review_provenance`), and its report carries a PROVISIONAL banner.

### Expanded corpus selection (`src/atti/selection.py`)

The selection is deterministic and ratio-blind: token counts are never consulted.

1. **Pool:** pairs passing the eligibility rule below, minus the 10 pilot articles, minus two groups affected by *global* amendments that are not attached to individual articles:
   - **Part 11 (Marine Employment Contract):** Royal Decree M/44 redefined its key terms by reference to the Commercial Maritime Law.
   - **Articles mentioning the Labor Dispute Commissions:** Royal Decree M/1 replaced that phrase "wherever mentioned". The check matches capitalized "Commission" in the English or "تسوية الخلافات" in the Arabic; lowercase sales "commissions" stays eligible.
2. **Strata:** the pool is sorted by Arabic character count and cut into thirds (short / medium / long).
3. **Quotas:** 7 short, 7 medium, 6 long.
4. **Picking:** within each stratum, repeatedly take the candidate whose Part of the Law has the fewest articles selected so far (pilot included). Ties are broken by `SHA-256("atti-expanded-v1:<article>")`.

Parts are taken from the Arabic page's Part headings. They were cross-checked against poppler's reading of the English PDF; pdfminer misorders two Part headings.

**Review process.** Each new pair was read side by side, checking numbered clauses and sub-clauses, enumerated lists, exceptions, numbers, percentages, dates and legal references. There were also automated checks: every digit sequence in the Arabic appears in the English, and the English text matches poppler's output exactly. A pair that fails review goes into `selection.EXCLUDED` with a reason, and the selection is re-run. No pair failed. The two translation nuances found (Articles 29 and 45) are recorded in `manifest/expanded_v1_review.json`.

## current_law_v2: the current consolidated law

**Research scope.** ATTI measures tokenization of Saudi government-published Arabic and English legal texts as published. It is not a legal translation equivalence benchmark. Semantic differences in retained pairs (Articles 34, 35 and 108) are documented as source-alignment limitations in `manifest/current_law_v2_review.json` and in the report.

**Manifest verification.** `v2.verify()` rejects any manifest that is empty or has duplicate keys or ids, malformed hashes or keys, missing or mistyped fields, inadmissible statuses, or a mismatch with `selection.selected`, the candidates or the source texts. Such a manifest is never measured. The v1 `corpus.verify()` rejects empty and duplicate article lists.

`pilot` and `expanded_v1` are frozen historical corpora. They use the 2005 base text, from the BOE Arabic page and the BOE English PDF. `current_law_v2` uses the **current consolidated law** (amendments through Royal Decree M/44, in force from 1446/8/20 AH):

| Role | Source |
|---|---|
| Arabic (measured) | HRSD consolidated PDF, pinned by SHA-256 `cfb8e0e6…` |
| English (measured) | HRSD English pages: 16 Parts, discovered from the official index |
| Arabic cross-check | HRSD Arabic HTML pages (x-default alternates) |
| Legal-version checks | BOE register; Umm Al-Qura gazette |

The full evidence is in `reports/current_law_v2_sources.md`.

```bash
uv run atti v2-fetch        # polite fetch: one request at a time, >=2 s apart, backoff, TLS verified, write-once cache
uv run atti v2              # reproduce all v2 outputs from the pinned cache (historical files are only read)
uv run atti v2-manifest     # (curation only) rebuild the manifest from the cache and the AI review file
uv run atti review-sheet --corpus current_law_v2   # local bilingual review page (git-ignored)
```

**Extraction:**

- **English:** HTTPX and selectolax over server-rendered HTML, so no browser automation is needed. `<ol>` numbering is rebuilt as "N.", and section titles end an article.
- **Arabic:** PyMuPDF, with lines classified by font size: headings, body, repealed marker, footnotes (excluded) and titles.
- **Arabic layout cleanup:** this is kept separate from the whitespace normalization used for token counting. It covers:
  - presentation-form letters, converted to base letters;
  - justification tatweel, removed;
  - mirrored brackets, swapped back.

**Eligibility.** An article pair qualifies only if all of these hold:

- the PDF text is character-identical to the HRSD Arabic HTML text, apart from HTML-only tatweel/ZWNJ;
- it is not repealed;
- it has exactly one correctly numbered English article in the same Part.

Nothing is repaired. Of the 249 Arabic articles (245 plus 4 bis), 175 qualify. The draw uses the 172 that qualified when the corpus was curated (2026-11-23). Articles 33, 79 and 79 bis qualified only after two parser fixes on 2026-11-24, and are recorded as `eligible_outside_draw`. Those fixes changed none of the 100 selected texts, so the measured pairs are kept. The exclusions and their reasons are in the manifest's `candidates` block.

**Reported anomalies (not repaired).** The English pages label Articles 101, 197 and 219 as "10", "194" and "210" respectively, so those numbers are duplicated. Article 79 bis is published as "Article 79:(Bis)"; an earlier parser misread it as a second Article 79, which was fixed on 2026-11-24. Some articles have clause numbering that differs between the languages, and two source typos are kept verbatim.

**Selection** is deterministic and token-blind:

- each Part gets a minimum of 2 articles, with the remaining quota proportional to its pool size;
- within a Part, picks cycle through short, medium and long thirds by Arabic length;
- ties are broken by `SHA-256("atti-current-law-v2:<key>")`.

**Review:**

- `manifest/current_law_v2_review.json` holds the AI pair review: statuses PROPOSED_PASS, NEEDS_REVIEW, FAIL, MISSING_SOURCE and VERSION_MISMATCH, with evidence and the re-evaluation of v1's disputed Articles 45, 65, 108 and 134.
- Review exclusions: pairs whose English adds, drops or changes a legal element (negation, condition, threshold, scope, sanction, legal basis) or reflects another legal version are excluded (`EXCLUDED_AFTER_REVIEW` in `src/atti/v2.py`). Each excluded pick is replaced by the next draw from the same Part and length stratum; no other selection moves. Sources, short excerpts and findings: `reports/current_law_v2_discrepancies.md`. `atti review-sheet --corpus current_law_v2` also writes a full-text version under git-ignored `data/review/`.
- `atti v2-manifest` refuses to rebuild the manifest once any human decision is recorded, because decisions are bound to the manifest hash. While the template is empty, it is re-bound to the new manifest.
- Human decisions go in `review/current_law_v2_human_decisions.json` (`uv run atti decide <key> <DECISION> --reviewer "Name" --corpus current_law_v2`).

**Comparing with v1:** the migration record is `manifest/current_law_v2_migration.json`. The v2 report separates a *source* effect (the same 15 articles with old and new texts) from a *sample-composition* effect. Tokenizers are unchanged.

## Human validation (expanded_v1)

`expanded_v1` stays **provisional** until a human has recorded a decision for every pair. The validation material lives in three separate places:

| File | Content | Author | Committed? |
|---|---|---|---|
| `review/expanded_v1_ai_review.json` | AI proposed status (PASS / NEEDS_REVIEW / FAIL), evidence, material discrepancies | AI agent; the second pass is by the same model as the first, so it is not independent | yes (no legal text) |
| `review/expanded_v1_human_decisions.json` | APPROVE / REJECT / REQUEST_EXAMINATION, reviewer, date, comment | **human only** | yes, once filled in |
| `data/review/expanded_v1_review_sheet.md` | both full texts side by side, AI notes, recorded decisions | generated | **no** (git-ignored; contains legal texts) |

**To record decisions:**

1. Run `uv run atti review-sheet`. It re-extracts and hash-verifies all 30 pairs, writes the sheet, creates an empty decision template if none exists (never overwriting one), and validates recorded decisions.
2. Read each pair in the sheet and fill in `review/expanded_v1_human_decisions.json`. Each entry needs a `decision` (`APPROVE`, `REJECT` or `REQUEST_EXAMINATION`), your name as `reviewer`, the `date` (YYYY-MM-DD), and a `comment`; the comment is required for anything other than APPROVE.
3. Re-run `uv run atti review-sheet`. It exits with code 2 if the file is invalid: an unknown decision, missing name or date, an AI-system reviewer name, or a manifest hash mismatch.

Decisions are bound to the manifest's SHA-256. A REJECT does not remove an article automatically. Excluding one is a separate, reported change: add it to `selection.EXCLUDED` with the reason and re-run the selection. That replaces the pair and changes the `expanded_v1` results, which would then need a new corpus version.

## How the article pairs are verified

The two sources represent the amendment history differently:

- **English PDF:** the body is the 2005 text, and all amendments are listed in an appendix.
- **Arabic page:** shows the base text and flags amended articles (`changed-article`), with amendment text in pop-ups.

Because of this, matching article numbers do **not** imply matching content. A pair is eligible only when:

1. the Arabic page has exactly one non-"bis" article with that number, and does not flag it as amended;
2. the English appendix never references that article number. This check is intentionally over-inclusive: an article merely mentioned in an amendment counts as affected;
3. both texts are nonempty; and
4. a manual side-by-side content review is recorded in `manifest/review.json`.

Every `atti pilot` run re-extracts both texts and checks them against the SHA-256 hashes in the manifest, as well as the English PDF hash. If anything changed, the run stops with `VERIFICATION FAILED`.

Source disagreements found during curation are recorded in the manifest's `audit` block. All of them are excluded:

- **Articles 98–100 and 104 (working hours):** the English appendix includes a 2015 amendment (Royal Decree M/46) that the Arabic page does not show.
- **Articles 233–235:** appear twice on the Arabic page, as the repealed originals and as the articles added in 2018.
- **Part 14 (Articles 210–228):** repealed as a whole. The English appendix states this without listing article numbers.

## Text extraction

- **Normalization:** only layout whitespace is changed. Every whitespace run (PDF line wraps, `<br>`, NBSP) becomes one space, and the ends are trimmed. There is no Unicode normalization and no punctuation or diacritic change.
- **Arabic:** HTML article body with tags removed and entities unescaped.
- **English:** `pdfminer.six`, with the running page header/footer and section headings removed. `pypdf` was rejected because it inserted spurious spaces (e.g. "t he", "part -time"). The 10 English texts match poppler's `pdftotext` output exactly after normalization.

## Tokenizers

| Model | Pinned revision |
|---|---|
| `Qwen/Qwen2.5-3B-Instruct` | `aa8e72537993ba99e69dfaafa59ed015b17504d1` |
| `mistralai/Mistral-7B-Instruct-v0.3` | `c170c708c41dac9275d15a8fff4eca08d52bab71` |

- Only `tokenizer.json` is downloaded, anonymously (`token=False`). No model weights are fetched.
- Counts use `encode(text, add_special_tokens=False)`: no BOS/EOS and no chat template.
- Truncation and padding are disabled, and every count is checked at run time (see below).
- During development, counts were cross-checked against `transformers.AutoTokenizer` (fast) and Mistral's SentencePiece slow tokenizer. All 40 counts matched.

## What the tests prove, and what they don't

**Run-time guards** (`tokenization.count_tokens`, applied to every published count). A count is rejected unless:

1. truncation and padding are both disabled, and there are no overflow segments;
2. every non-whitespace character of the input lies inside some token's offset span;
3. no special-token id or unknown-token id appears in the content encoding.

Guard 2 replaces the earlier check that the last token's offset ends at `len(text)`. That check was misleading: left-side truncation keeps the end of the text, so it would still pass. It also said nothing about characters dropped in the middle. `test_last_offset_check_was_insufficient_left_truncation` demonstrates the gap.

**Stronger checks on the two pinned tokenizers and the 10 articles** (`network` tests):

- Offsets cover *every* character, including whitespace.
- `decode(ids)` equals the tokenizer's own normalization of the input:
  - **Mistral:** no normalizer, so decoding reproduces the text exactly.
  - **Qwen:** applies Unicode NFC. Articles 65 and 92 (Arabic) contain combining marks in non-NFC order, so they decode to their NFC form. This is expected and is not data loss; the test pins exactly these two cases.
- No special tokens appear in content counts. Mistral would add `<s>` (BOS) with `add_special_tokens=True`; Qwen adds nothing.
- Counts are identical across fresh tokenizer loads, and a fresh measurement reproduces `results/pilot.csv` byte for byte.

**Results checks** (offline):

- A missing published artifact fails the tests; it is never skipped.
- CSV rows must match the manifest (ids, hashes, character counts) and the pinned revisions.
- TTR, median, min and max are recomputed from the CSV integers with exact fractions, independently of `atti.metrics`.
- The published totals are pinned: Qwen 1290/898, Mistral 3114/982.
- `pilot_summary.json` and `pilot.md` must regenerate byte for byte from the CSV and manifest.

**Expanded corpus checks:**

- All 30 entries are unique and have review notes; the 10 pilot entries are identical to the pilot manifest.
- The pilot rows inside `expanded_v1.csv` equal `pilot.csv`; the expanded totals are pinned.
- The selection is deterministic, order-independent and ignores the English side, and the quotas and exclusion rules are tested.
- `network` tests rebuild the selection from the sources and reproduce `expanded_v1.csv` byte for byte. They also apply full character coverage, no-special-token and decode checks to all 30 pairs.

**Source checks:**

- Network failures are reported separately from verification failures.
- Without a cached baseline, `verify-live` states that only the selected articles were verified ([1]) and that the full-source comparison ([2]) was not performed.
- Changed, missing and ineligible articles are each detected, and changes outside the selected articles are distinguished from changes to them.
- `verify-live` never modifies the baseline.
- All of this is tested offline with mocked downloads. One `network` test replays the real cached sources and tampers with one word.

**Not proven:**

- That offsets align with *linguistic* units. They only show that characters are attributed to tokens.
- That the tokenizer used in production inference for these models is the same `tokenizer.json`. Counts were cross-checked once against `transformers` and Mistral's SentencePiece model; that check is not part of the test suite.
- That the Arabic and English texts are legally equivalent beyond the recorded manual review.
- That any pair is human-approved. All review is agent-assisted; `expanded_v1` is provisional.
- That the official sources are unchanged *today*. Only `atti verify-live` checks that, and only at the moment it runs.
- The Arabic page bytes are not compared, because they embed a live view counter. Only the parsed article text, headings and amendment flags are compared.

## Layout

```
src/atti/  sources.py   official URLs, cached downloader, NetworkError
           live.py      verify-live (fresh download -> temp dir -> compare)
           arabic.py    BOE HTML -> articles (Arabic ordinal parser)
           english.py   BOE PDF -> articles + amendment-appendix references
           textnorm.py  the single whitespace normalization
           corpus.py    eligibility rule, manifest build + verification
           selection.py deterministic expanded_v1 selection
           review.py    human-validation sheet, decision template + validation
           hrsd.py      HRSD fetcher (HTTPX), English/Arabic HTML and Arabic PDF extraction
           v2.py        current_law_v2 eligibility, QA checks, selection, measurement, report, migration
           tokenization.py  pinned tokenizer loading, content-only counting
           metrics.py   TTR, median ratio
           pipeline.py / report.py / cli.py
manifest/  pilot_manifest.json, review.json; expanded_v1_manifest.json, expanded_v1_review.json
results/   pilot.csv, pilot_summary.json; expanded_v1.csv, expanded_v1_summary.json
reports/   pilot.md; expanded_v1.md
tests/
```
