# ATTI: Arabic Token Tax Index (pilot)

ATTI compares how many tokens open LLM tokenizers spend on Arabic text versus English text with the same meaning. This pilot uses 10 verified article pairs from the official Arabic **Saudi Labor Law** and its official English translation.

**TTR (Token Tax Ratio) = Σ Arabic tokens / Σ English tokens**, computed per tokenizer. The pilot also reports absolute totals and the median per-article ratio.

This is an engineering pilot, not a full academic benchmark.

## Setup and reproduction

Requires [uv](https://docs.astral.sh/uv/) and internet access on the first run. No API keys, GPU, or paid inference needed.

```bash
uv sync
uv run atti pilot      # fetch sources -> verify manifest -> count tokens -> write outputs
uv run pytest          # unit + integration tests
```

`atti pilot` writes:

- `results/pilot.csv`: raw per-article, per-model measurements (no legal text)
- `results/pilot_summary.json`: aggregates
- `reports/pilot.md`: human-readable report

Other commands:

- `uv run atti fetch [--refresh]` downloads the official sources into `data/raw/`.
- `uv run atti manifest [--articles 4,32,...]` rebuilds `manifest/pilot_manifest.json`. It refuses any article that is ineligible or has no manual review note in `manifest/review.json`.

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
- Truncation and padding are disabled. Each count also asserts that token offsets cover the full text.
- During development, counts were cross-checked against `transformers.AutoTokenizer` (fast) and Mistral's SentencePiece slow tokenizer. All 40 counts matched.

## Layout

```
src/atti/  sources.py   official URLs + cached downloader
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
