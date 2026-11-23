# ATTI pilot: Arabic vs English token counts, Saudi Labor Law

Engineering pilot. **TTR = Σ Arabic tokens / Σ English tokens** over 10 verified article pairs. Content-only counts: no special tokens, no chat template, truncation disabled.

## Results by model

| Model | Revision | Σ AR tokens | Σ EN tokens | **TTR** | Median article ratio | Min | Max |
|---|---|---:|---:|---:|---:|---:|---:|
| Qwen/Qwen2.5-3B-Instruct | `aa8e72537993` | 1290 | 898 | **1.4365** | 1.3983 | 0.8500 | 1.6842 |
| mistralai/Mistral-7B-Instruct-v0.3 | `c170c708c41d` | 3114 | 982 | **3.1711** | 3.1613 | 2.0909 | 4.0476 |

## Per-article measurements

| ID | Art. | AR chars | EN chars | Qwen2.5-3B-Instruct AR | Qwen2.5-3B-Instruct EN | Qwen2.5-3B-Instruct ratio | Mistral-7B-Instruct-v0.3 AR | Mistral-7B-Instruct-v0.3 EN | Mistral-7B-Instruct-v0.3 ratio |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| KSA-LL-004 | 4 | 96 | 109 | 32 | 19 | 1.6842 | 85 | 21 | 4.0476 |
| KSA-LL-032 | 32 | 53 | 107 | 17 | 20 | 0.8500 | 46 | 22 | 2.0909 |
| KSA-LL-038 | 38 | 156 | 237 | 57 | 43 | 1.3256 | 136 | 44 | 3.0909 |
| KSA-LL-059 | 59 | 227 | 283 | 79 | 59 | 1.3390 | 192 | 67 | 2.8657 |
| KSA-LL-065 | 65 | 993 | 1302 | 350 | 249 | 1.4056 | 874 | 272 | 3.2132 |
| KSA-LL-070 | 70 | 410 | 529 | 153 | 110 | 1.3909 | 374 | 118 | 3.1695 |
| KSA-LL-089 | 89 | 72 | 101 | 26 | 21 | 1.2381 | 67 | 22 | 3.0455 |
| KSA-LL-092 | 92 | 742 | 928 | 289 | 189 | 1.5291 | 659 | 209 | 3.1531 |
| KSA-LL-108 | 108 | 520 | 580 | 189 | 123 | 1.5366 | 435 | 135 | 3.2222 |
| KSA-LL-120 | 120 | 293 | 380 | 98 | 65 | 1.5077 | 246 | 72 | 3.4167 |

## Sources and verification

- Law: Labor Law (نظام العمل), Royal Decree No. M/51 dated 1426/08/23 AH (2005-09-27).
- Arabic (governing text): Bureau of Experts at the Council of Ministers (laws.boe.gov.sa), <https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/08381293-6388-48e2-8ad2-a9a700f2aa94/1>, retrieved 2026-11-23T11:46:04+00:00.
- English (official translation): Bureau of Experts, Official Translation Department, <https://laws.boe.gov.sa/Files/Download/?attId=704cf56e-eb7a-4ddb-8c28-adbb01244dc6>, PDF sha256 `8fd3c9e17f25318b9bdf784827923c53a2666a3d63e49c6d471e8a41987ff3c5`, retrieved 2026-11-23T11:46:06+00:00.
- Latest amendment recorded in both sources: Royal Decree No. M/44 dated 1446/02/08 AH (2024-08-12).
- The English PDF body is the 2005 text with amendments listed in an appendix; the Arabic page shows the base text with amendments flagged per article. Only articles that neither source records as amended were used, so both sides are the same (unamended) wording. Each pair was also reviewed manually; per-article text SHA-256 hashes are in `manifest/pilot_manifest.json` and are re-checked on every run.
- Source disagreements found (excluded from the pilot): English appendix references articles not flagged on the Arabic page: [98, 99, 100, 104, 240, 242]; Arabic page flags articles not referenced in the English appendix: [131, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228].

## Tokenizers

- `Qwen/Qwen2.5-3B-Instruct` @ `aa8e72537993ba99e69dfaafa59ed015b17504d1`; `tokenizer.json` sha256 `c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539`
- `mistralai/Mistral-7B-Instruct-v0.3` @ `c170c708c41dac9275d15a8fff4eca08d52bab71`; `tokenizer.json` sha256 `e553af6fff7d7ad76e830608b218c5c0b0822998d5a1a96099a74cd3c1cb1a49`

## Recalculation

All aggregates are recomputable from `results/pilot.csv`: TTR = sum(`ar_tokens`) / sum(`en_tokens`) per `model`; the median is over `ar_tokens/en_tokens` per row. `tests/test_results.py` performs this recalculation.

## Limitations

- 10 articles from a single law: a pilot, not a representative sample.
- The English text is a translation (non-governing). Translation style (e.g. verbosity) affects the denominator.
- Whitespace is normalized on both sides (layout only); counts on raw HTML/PDF layout would differ slightly.
- Only articles without recorded amendments were eligible, which biases toward unchanged provisions.
