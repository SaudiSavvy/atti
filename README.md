# ATTI: Arabic Token Tax Index (pilot)

ATTI compares how many tokens open LLM tokenizers spend on Arabic text versus English text with the same meaning. This pilot uses 10 verified article pairs from the official Arabic **Saudi Labor Law** and its official English translation.

**TTR (Token Tax Ratio) = Σ Arabic tokens / Σ English tokens**, computed per tokenizer. The pilot also reports absolute totals and the median per-article ratio.

This is an engineering pilot, not a full academic benchmark.

## Setup and reproduction

Requires [uv](https://docs.astral.sh/uv/) and internet access on the first run. No API keys, GPU, or paid inference needed.

```bash
uv sync
uv run atti pilot                  # reproduce from the cached baseline corpus
uv run atti verify-live            # compare today's official sources with the manifest
uv run pytest -m "not network" -q  # offline tests (no downloads)
uv run pytest -q                   # all tests (needs the cache, downloaded on first run)
```

| Command | What it does | Writes |
|---|---|---|
| `atti pilot` | Reproduces the benchmark from `data/raw`. It downloads a source only if it is missing (first run) and never replaces a cached file. It checks every article against the manifest hashes, then counts tokens. | `results/pilot.csv`, `results/pilot_summary.json`, `reports/pilot.md` |
| `atti verify-live` | Downloads fresh official sources into a temporary directory, which is deleted afterwards. It compares them with the manifest and, if present, with the cached baseline. It never updates hashes or approves new text. | nothing |
| `atti fetch` | Downloads missing sources into `data/raw`. | `data/raw` (git-ignored) |
| `atti manifest` | Rebuilds the manifest. Only use this as a deliberate curation step. It refuses articles that are ineligible or have no review note in `manifest/review.json`. | `manifest/pilot_manifest.json` |

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

**Source checks:**

- Network failures are reported separately from verification failures.
- Changed, missing and ineligible articles are each detected, and changes outside the selected articles are distinguished from changes to them.
- `verify-live` never modifies the baseline.
- All of this is tested offline with mocked downloads. One `network` test replays the real cached sources and tampers with one word.

**Not proven:**

- That offsets align with *linguistic* units. They only show that characters are attributed to tokens.
- That the tokenizer used in production inference for these models is the same `tokenizer.json`. Counts were cross-checked once against `transformers` and Mistral's SentencePiece model; that check is not part of the test suite.
- That the Arabic and English texts are legally equivalent beyond the recorded manual review.
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
           tokenization.py  pinned tokenizer loading, content-only counting
           metrics.py   TTR, median ratio
           pipeline.py / report.py / cli.py
manifest/  pilot_manifest.json (hashes, ids, audit), review.json (manual review notes)
results/   pilot.csv, pilot_summary.json
reports/   pilot.md
tests/
```
