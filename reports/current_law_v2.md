# ATTI current_law_v2: Arabic vs English token counts, current Saudi Labor Law (100 articles)

> **Status: PROVISIONAL.** PENDING: no pair is human-approved; see review/current_law_v2_human_decisions.json. Pair review is AI-assisted (Claude (AI agent, claude-opus-5-5), 2026-11-23; read every selected pair in full; Task 07 re-examination of the 9 flagged pairs and the replacement draws on 2026-11-23): {'PROPOSED_PASS': 100}.

Token counts from the pinned tokenizers; content only (no special tokens, no chat template, no truncation). **TTR = Σ Arabic tokens / Σ English tokens.** These are tokenizer measurements, not inference cost, latency or quality.

## Sources

- Arabic: HRSD consolidated PDF <https://www.hrsd.gov.sa/sites/default/files/2025-11/labor-law.pdf>, SHA-256 `cfb8e0e6bb0176ebe045e38aed072fc4f7ce5c2f72ee796f4de0beb216c4b5d6`; consolidated through Royal Decree No. M/44 dated 1446/02/08 AH, in force from 1446/08/20 AH.
- English: HRSD English Part pages (16), discovered from <https://www.hrsd.gov.sa/en/knowledge-centre/%D9%86%D8%B8%D8%A7%D9%85-%D8%A7%D9%84%D8%B9%D9%85%D9%84>. Published by the ministry; translation status not stated on the pages.
- Cross-checks: HRSD Arabic HTML (extraction confirmation), BOE register and Umm Al-Qura gazette (no amendment newer than M/44 found). Details: `reports/current_law_v2_sources.md`.

## Results by tokenizer

| Tokenizer | Revision | Σ AR tokens | Σ EN tokens | **TTR** | Median article ratio | Min | Max |
|---|---|---:|---:|---:|---:|---:|---:|
| Qwen/Qwen2.5-3B-Instruct | `aa8e72537993` | 9811 | 7293 | **1.3453** | 1.3559 | 0.8889 | 1.8846 |
| mistralai/Mistral-7B-Instruct-v0.3 | `c170c708c41d` | 23970 | 7921 | **3.0261** | 3.0227 | 2.3125 | 4.6964 |

## By Part

| Part | Articles | Qwen2.5-3B-Instruct AR / EN / TTR | Mistral-7B-Instruct-v0.3 AR / EN / TTR |
|---:|---:|---|---|
| 1 | 9 | 864 / 628 / 1.3758 | 2072 / 681 / 3.0426 |
| 2 | 5 | 454 / 319 / 1.4232 | 1138 / 337 / 3.3769 |
| 3 | 4 | 249 / 178 / 1.3989 | 597 / 192 / 3.1094 |
| 4 | 4 | 530 / 364 / 1.4560 | 1207 / 395 / 3.0557 |
| 5 | 17 | 1900 / 1538 / 1.2354 | 4693 / 1677 / 2.7984 |
| 6 | 13 | 1429 / 1092 / 1.3086 | 3642 / 1168 / 3.1182 |
| 7 | 2 | 154 / 99 / 1.5556 | 376 / 107 / 3.5140 |
| 8 | 14 | 1378 / 1000 / 1.3780 | 3375 / 1105 / 3.0543 |
| 9 | 4 | 368 / 272 / 1.3529 | 923 / 300 / 3.0767 |
| 10 | 4 | 434 / 311 / 1.3955 | 1050 / 341 / 3.0792 |
| 11 | 9 | 1070 / 804 / 1.3308 | 2476 / 878 / 2.8200 |
| 12 | 5 | 348 / 244 / 1.4262 | 904 / 253 / 3.5731 |
| 13 | 4 | 228 / 133 / 1.7143 | 575 / 146 / 3.9384 |
| 15 | 4 | 324 / 240 / 1.3500 | 733 / 266 / 2.7556 |
| 16 | 2 | 81 / 71 / 1.1408 | 209 / 75 / 2.7867 |

## Comparison with historical corpora (descriptive)

| Tokenizer | pilot (10, BOE) | expanded_v1 (30, BOE) | current_law_v2 (100, HRSD) |
|---|---:|---:|---:|
| Qwen/Qwen2.5-3B-Instruct | 1.4365 | 1.4096 | 1.3453 |
| mistralai/Mistral-7B-Instruct-v0.3 | 3.1711 | 3.2026 | 3.0261 |

What can and cannot explain the differences:

- **Tokenizer behaviour:** held constant (same pinned revisions and counting rules in all corpora).
- **Source change** (same articles, old BOE texts vs new HRSD texts), on the 15 articles present in both expanded_v1 and v2:
  - Qwen/Qwen2.5-3B-Instruct: TTR 1.4083 (BOE) → 1.4022 (HRSD); Arabic 1121 → 1126 tokens, English 796 → 803 tokens.
  - mistralai/Mistral-7B-Instruct-v0.3: TTR 3.2982 (BOE) → 3.2436 (HRSD); Arabic 2787 → 2809 tokens, English 845 → 866 tokens.
- **Sample composition** (same HRSD texts and tokenizers, overlap subset vs all 100 articles):
  - Qwen/Qwen2.5-3B-Instruct: overlap 1.4022 → full corpus 1.3453.
  - mistralai/Mistral-7B-Instruct-v0.3: overlap 3.2436 → full corpus 3.0261.
- Summary of the 10/30 → 100 change, per tokenizer: source effect = overlap HRSD − overlap BOE; composition effect = full v2 − overlap HRSD:
  - Qwen/Qwen2.5-3B-Instruct: source -0.0060, composition -0.0570 (expanded_v1 → v2 total -0.0644; the 15-article overlap is a different subset from expanded_v1's 30, so these do not sum exactly).
  - mistralai/Mistral-7B-Instruct-v0.3: source -0.0546, composition -0.2175 (expanded_v1 → v2 total -0.1765; the 15-article overlap is a different subset from expanded_v1's 30, so these do not sum exactly).
- v2 includes 85 articles that were in no earlier corpus. No statistical significance is claimed.

## Review exclusions and replacements

Rule: Strict corpus: a pair is excluded when the English adds, drops or changes a legal element of the Arabic (negation, condition, threshold, scope, the identity of a sanction, the legal basis) or reflects a different legal version. A pair is retained when only list labels/markup differ with content corresponding one-to-one and in order, or when a term differs but its referent is unambiguous and unchanged. Neither official text is corrected.

| Excluded | Status | Category | Replaced by |
|---:|---|---|---|
| 40 | VERSION_MISMATCH | VERSION_MISMATCH | 35 |
| 63 | FAIL | TRANSLATION_DIFFERENCE | 56 |
| 66 | FAIL | TRANSLATION_DIFFERENCE | 71 |
| 76 | FAIL | TRANSLATION_DIFFERENCE | n/a (rejected replacement draw, never selected) |
| 81 | FAIL | TRANSLATION_DIFFERENCE | 58 |
| 189 | FAIL | TRANSLATION_DIFFERENCE | 187 |

Per-article sources, excerpts and findings: `reports/current_law_v2_discrepancies.md`.

## Selection

- Pool: Arabic articles whose PDF text is confirmed character-for-character by the HRSD Arabic HTML (ignoring HTML-only tatweel/ZWNJ), not repealed, with exactly one correctly numbered English counterpart in the same Part
- Quota per Part: floor of 2 (where available), remainder allocated proportionally to pool size (largest remainder, ties by Part number); target 100
- Within a Part: articles sorted by Arabic character count and cut into thirds; picks cycle short -> medium -> long, each taking the lowest SHA-256(seed:key) remaining in that stratum
- Review exclusions never reshuffle the draw: each excluded pick is replaced by the next draw (same seed order) from the same Part, preferring its own stratum, then the following strata in cycle order
- Token counts, ratios and English length are never consulted
- Seed `atti-current-law-v2`; pool 172 eligible (166 after review exclusions) of 249 Arabic articles; quota by Part {'1': 9, '2': 5, '3': 4, '4': 4, '5': 17, '6': 13, '7': 2, '8': 14, '9': 4, '10': 4, '11': 9, '12': 5, '13': 4, '15': 4, '16': 2}.
- Excluded candidates and reasons: `manifest/current_law_v2_manifest.json` → `candidates`.

## Source anomalies (reported, not repaired)

- English labels used twice: ['10', '79', '194', '210']; English numbers missing: ['101', '197', '219'] (Part 14 shows Article 210 twice and no Article 219; Part 6 labels Article 101 as 'Article 10'; Part 13 labels Article 197 as 'Article 194'; 79 bis is labelled 'Article 79').
- Clause numbering differs between languages in selected Articles 15, 64, 108 (source list markup; content corresponds).
- Arabic Article 181 contains a stray '0'; English Article 184 reads 'seafarer1' (both kept verbatim).

## Recalculation

All aggregates are recomputable from `results/current_law_v2.csv` (TTR = Σ ar_tokens / Σ en_tokens per model; medians over per-row ratios); `tests/test_v2.py` does this with exact fractions.

## Limitations

- PROVISIONAL: AI-assisted review only; 0 pairs NEEDS_REVIEW; no human approval.
- 6 pairs were excluded after AI review under the strict rule above; applying it is an AI judgement that a human reviewer may overturn. Priority items for human review: 15, 64, 108, 167, 187.
- The English is the ministry's published translation; its official status is not stated.
- 77 of 249 Arabic articles were not eligible (35 AR_UNCONFIRMED, 4 MISSING_SOURCE, 4 NUMBERING, 38 REPEALED; an article can have several reasons). Requiring two identical Arabic renderings skews the pool toward articles without lists or layout quirks.
- One law; Part 14 absent (repealed).
