# ATTI expanded_v1: Arabic vs English token counts, Saudi Labor Law (30 articles)

> **Status: PROVISIONAL.** PENDING: no human has reviewed or approved any pair in this corpus (including the 10 pilot pairs). Agent-assisted review only; see `manifest/expanded_v1_review.json`.

Expanded corpus. **TTR = Σ Arabic tokens / Σ English tokens** over 30 verified article pairs. Content-only counts: no special tokens, no chat template, truncation disabled.

## Results by model

| Model | Revision | Σ AR tokens | Σ EN tokens | **TTR** | Median article ratio | Min | Max |
|---|---|---:|---:|---:|---:|---:|---:|
| Qwen/Qwen2.5-3B-Instruct | `aa8e72537993` | 2925 | 2075 | **1.4096** | 1.3972 | 0.8500 | 1.8000 |
| mistralai/Mistral-7B-Instruct-v0.3 | `c170c708c41d` | 7161 | 2236 | **3.2026** | 3.1617 | 2.0909 | 4.5238 |

## Per-article measurements

| ID | Art. | AR chars | EN chars | Qwen2.5-3B-Instruct AR | Qwen2.5-3B-Instruct EN | Qwen2.5-3B-Instruct ratio | Mistral-7B-Instruct-v0.3 AR | Mistral-7B-Instruct-v0.3 EN | Mistral-7B-Instruct-v0.3 ratio |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| KSA-LL-004 | 4 | 96 | 109 | 32 | 19 | 1.6842 | 85 | 21 | 4.0476 |
| KSA-LL-006 | 6 | 263 | 334 | 91 | 59 | 1.5424 | 223 | 63 | 3.5397 |
| KSA-LL-026 | 26 | 455 | 621 | 169 | 122 | 1.3852 | 410 | 130 | 3.1538 |
| KSA-LL-029 | 29 | 251 | 354 | 86 | 68 | 1.2647 | 229 | 70 | 3.2714 |
| KSA-LL-032 | 32 | 53 | 107 | 17 | 20 | 0.8500 | 46 | 22 | 2.0909 |
| KSA-LL-038 | 38 | 156 | 237 | 57 | 43 | 1.3256 | 136 | 44 | 3.0909 |
| KSA-LL-045 | 45 | 92 | 134 | 39 | 23 | 1.6957 | 86 | 25 | 3.4400 |
| KSA-LL-049 | 49 | 243 | 314 | 81 | 55 | 1.4727 | 206 | 58 | 3.5517 |
| KSA-LL-059 | 59 | 227 | 283 | 79 | 59 | 1.3390 | 192 | 67 | 2.8657 |
| KSA-LL-065 | 65 | 993 | 1302 | 350 | 249 | 1.4056 | 874 | 272 | 3.2132 |
| KSA-LL-070 | 70 | 410 | 529 | 153 | 110 | 1.3909 | 374 | 118 | 3.1695 |
| KSA-LL-089 | 89 | 72 | 101 | 26 | 21 | 1.2381 | 67 | 22 | 3.0455 |
| KSA-LL-092 | 92 | 742 | 928 | 289 | 189 | 1.5291 | 659 | 209 | 3.1531 |
| KSA-LL-108 | 108 | 520 | 580 | 189 | 123 | 1.5366 | 435 | 135 | 3.2222 |
| KSA-LL-120 | 120 | 293 | 380 | 98 | 65 | 1.5077 | 246 | 72 | 3.4167 |
| KSA-LL-132 | 132 | 96 | 140 | 33 | 24 | 1.3750 | 82 | 27 | 3.0370 |
| KSA-LL-134 | 134 | 172 | 273 | 58 | 49 | 1.1837 | 156 | 51 | 3.0588 |
| KSA-LL-138 | 138 | 349 | 548 | 139 | 100 | 1.3900 | 318 | 106 | 3.0000 |
| KSA-LL-154 | 154 | 292 | 361 | 104 | 70 | 1.4857 | 262 | 74 | 3.5405 |
| KSA-LL-158 | 158 | 103 | 111 | 36 | 20 | 1.8000 | 95 | 21 | 4.5238 |
| KSA-LL-161 | 161 | 235 | 292 | 80 | 57 | 1.4035 | 205 | 65 | 3.1538 |
| KSA-LL-162 | 162 | 514 | 684 | 196 | 146 | 1.3425 | 463 | 154 | 3.0065 |
| KSA-LL-163 | 163 | 117 | 172 | 41 | 36 | 1.1389 | 103 | 38 | 2.7105 |
| KSA-LL-188 | 188 | 328 | 355 | 104 | 73 | 1.4247 | 286 | 73 | 3.9178 |
| KSA-LL-191 | 191 | 89 | 108 | 27 | 21 | 1.2857 | 77 | 21 | 3.6667 |
| KSA-LL-201 | 201 | 299 | 395 | 107 | 68 | 1.5735 | 263 | 76 | 3.4605 |
| KSA-LL-202 | 202 | 169 | 258 | 62 | 44 | 1.4091 | 148 | 48 | 3.0833 |
| KSA-LL-204 | 204 | 199 | 285 | 69 | 48 | 1.4375 | 176 | 53 | 3.3208 |
| KSA-LL-244 | 244 | 210 | 293 | 82 | 68 | 1.2059 | 184 | 74 | 2.4865 |
| KSA-LL-245 | 245 | 82 | 122 | 31 | 26 | 1.1923 | 75 | 27 | 2.7778 |

## Comparison with the 10-article pilot

Descriptive only: the 30-article corpus contains the 10 pilot articles, so the two samples overlap and no statistical significance is claimed.

**Qwen/Qwen2.5-3B-Instruct**

| Metric | Pilot (10) | Expanded (30) | Added 20 only | Change 10 → 30 |
|---|---:|---:|---:|---:|
| Σ AR tokens | 1290 | 2925 | 1635 | +1635 |
| Σ EN tokens | 898 | 2075 | 1177 | +1177 |
| TTR | 1.4365 | 1.4096 | 1.3891 | -0.0269 |
| Median article ratio | 1.3983 | 1.3972 | 1.3968 | -0.0011 |
| Min article ratio | 0.8500 | 0.8500 | 1.1389 | +0.0000 |
| Max article ratio | 1.6842 | 1.8000 | 1.8000 | +0.1158 |

**mistralai/Mistral-7B-Instruct-v0.3**

| Metric | Pilot (10) | Expanded (30) | Added 20 only | Change 10 → 30 |
|---|---:|---:|---:|---:|
| Σ AR tokens | 3114 | 7161 | 4047 | +4047 |
| Σ EN tokens | 982 | 2236 | 1254 | +1254 |
| TTR | 3.1711 | 3.2026 | 3.2273 | +0.0315 |
| Median article ratio | 3.1613 | 3.1617 | 3.2126 | +0.0004 |
| Min article ratio | 2.0909 | 2.0909 | 2.4865 | +0.0000 |
| Max article ratio | 4.0476 | 4.5238 | 4.5238 | +0.4762 |

Pilot articles re-measured inside this corpus reproduce the published pilot aggregates exactly: **yes**.

## Selection procedure

- Pool: pairs passing the existing eligibility rule, minus the 10 pilot articles
- Excluded from pool: Part 11 (marine terms redefined by M/44) and articles mentioning the Labor Dispute Commissions (M/1 global phrase replacement)
- Strata: pool sorted by Arabic character count (ties by article number) and cut into thirds
- Quotas 7 short / 7 medium / 6 long; within a stratum, repeatedly take the candidate whose Part has the fewest selected articles (pilot included), ties broken by SHA-256(seed:article)
- Token counts are never consulted during selection
- Seed `atti-expanded-v1`; pool 106 articles; Arabic-character strata: short 27–172, medium 172–286, long 292–930; quotas 7 short / 7 medium / 6 long.
- Added, short: 158 (Part 9), 132 (Part 8), 202 (Part 13), 45 (Part 4), 191 (Part 12), 163 (Part 10), 245 (Part 16)
- Added, medium: 29 (Part 2), 134 (Part 8), 49 (Part 4), 204 (Part 13), 244 (Part 16), 161 (Part 10), 6 (Part 1)
- Added, long: 154 (Part 9), 188 (Part 12), 26 (Part 2), 162 (Part 10), 138 (Part 8), 201 (Part 13)
- Excluded from pool (mentions Labor Dispute Commissions (M/1 global phrase replacement)): 20, 91, 93, 94, 95
- Excluded from pool (Part 11 (marine): terms redefined by M/44 via the Commercial Maritime Law): 169, 170, 171, 172, 173, 174, 175, 176, 177, 179, 180, 181, 183, 184
- Excluded after semantic review: none

## Sources and verification

- Law: Labor Law (نظام العمل), Royal Decree No. M/51 dated 1426/08/23 AH (2005-09-27).
- Arabic (governing text): Bureau of Experts at the Council of Ministers (laws.boe.gov.sa), <https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/08381293-6388-48e2-8ad2-a9a700f2aa94/1>, retrieved 2026-11-23T11:46:04+00:00.
- English (official translation): Bureau of Experts, Official Translation Department, <https://laws.boe.gov.sa/Files/Download/?attId=704cf56e-eb7a-4ddb-8c28-adbb01244dc6>, PDF sha256 `8fd3c9e17f25318b9bdf784827923c53a2666a3d63e49c6d471e8a41987ff3c5`, retrieved 2026-11-23T11:46:06+00:00.
- Latest amendment recorded in both sources: Royal Decree No. M/44 dated 1446/02/08 AH (2024-08-12).
- The English PDF body is the 2005 text with amendments listed in an appendix; the Arabic page shows the base text with amendments flagged per article. Only articles that neither source records as amended were used, so both sides are the same (unamended) wording. Each pair was reviewed side by side by an AI agent (not human-approved); per-article text SHA-256 hashes are in `manifest/expanded_v1_manifest.json` and are re-checked on every run.
- Source disagreements found (excluded from the corpus): English appendix references articles not flagged on the Arabic page: [98, 99, 100, 104, 240, 242]; Arabic page flags articles not referenced in the English appendix: [131, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228].

## Tokenizers

- `Qwen/Qwen2.5-3B-Instruct` @ `aa8e72537993ba99e69dfaafa59ed015b17504d1`; `tokenizer.json` sha256 `c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539`
- `mistralai/Mistral-7B-Instruct-v0.3` @ `c170c708c41dac9275d15a8fff4eca08d52bab71`; `tokenizer.json` sha256 `e553af6fff7d7ad76e830608b218c5c0b0822998d5a1a96099a74cd3c1cb1a49`

## Recalculation

All aggregates are recomputable from `results/expanded_v1.csv`: TTR = sum(`ar_tokens`) / sum(`en_tokens`) per `model`; the median is over `ar_tokens/en_tokens` per row. `tests/test_results.py` performs this recalculation.

## Limitations

- PROVISIONAL: every pair was reviewed by an AI agent; no human has approved the corpus.
- 30 articles from a single law; Parts 11 (marine), 14 (repealed) and 15 (no eligible articles) are not represented.
- Only articles without recorded amendments were eligible, and articles touched by the M/1 and M/44 global phrase replacements were excluded; this biases toward unchanged provisions.
- The English text is a non-governing translation; translation verbosity affects the denominator.
- Whitespace is normalized on both sides (layout only).
- Changes versus the pilot are descriptive; no statistical significance is claimed.
