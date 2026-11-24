# ATTI current_law_v2: Gemini 4 Neon (100 article pairs)

> **PROVISIONAL corpus.** No pair is human-approved. Same 100 pairs and texts as the other seven models; their results are read from `results/current_law_v2.csv` and `results/current_law_v2_frontier*`, unchanged.

Tokenizer measurements of input text only. Not inference speed, model quality, output-token usage or pricing.

## Method

- Endpoint: `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-4-neon:countTokens` (model `gemini-4-neon`); count field `totalTokens`.
- Request: one user message with one text part containing the article body; no system instruction, no tools, no cached content: `{"contents": [{"role": "user", "parts": [{"text": "<article body>"}]}]}`.
- Measured on: 2026-11-24. Method `api_input_tokens`: Google's reported count, with no overhead subtracted.

## Gemini 4 Neon

| Σ AR | Σ EN | **TTR** | Median | Min | Max | AR tok/1k chars | EN tok/1k chars |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 12044 | 10662 | **1.1296** | 1.1303 | 0.9457 | 1.5176 | 444.9 | 273.0 |

## Provider API counts, same method (`api_input_tokens`)

> **Methodological warning.** API counts include provider framing for a one-message request, which adds a similar absolute amount to both languages and pulls the ratio towards 1. Framing differs between providers, so even these three are only loosely comparable. They are not ranked with content-only tokenizer counts.

| Model | Σ AR | Σ EN | **TTR** | Median | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| claude-opus-5-5 | 18228 | 11919 | **1.5293** | 1.5017 | 1.1364 | 2.2418 |
| gpt-6.2-sol | 8689 | 7838 | **1.1086** | 1.1111 | 0.8667 | 1.6897 |
| gemini-4-neon | 12044 | 10662 | **1.1296** | 1.1303 | 0.9457 | 1.5176 |

Content-only tokenizer results (`raw_content_tokens`) are in `reports/current_law_v2_frontier.md` and are deliberately not merged into this table.

## Short-input observations

| Input | Characters | totalTokens (two requests) |
|---|---:|---|
| `a` | 1 | 35, 35 |
| `a a` | 3 | 36, 36 |
| `Hello` | 5 | 35, 35 |
| `مرحبا` | 5 | 36, 36 |
| `مرحبا بالعالم` | 13 | 38, 38 |

Short-input counts are reported as observed. A non-zero count for a one-character input is consistent with request framing, but its size is not assumed constant across inputs and nothing is subtracted from article counts.

## Limitations

- Google's documentation does not state whether countTokens includes framing, whether it is exact, or its rate limits.
- A hosted model's tokenizer can change without a version change; counts are dated, not pinned.
- Counts are replayed from a local cache whose 200 article counts reproduce an anchor pinned from results/current_law_v2_gemini.csv sha256:e668ea7d7bdfaf9c83691df294af80074f308a81c67c3ff30e3cafdd7640d00c. Its records predate cache schema 2, so provider, text-identity, adapter-version and count-field metadata were never recorded; they are not reconstructed.
- One law, one translation; the corpus is provisional and documents source-alignment limitations.
