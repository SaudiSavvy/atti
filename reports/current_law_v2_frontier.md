# ATTI current_law_v2: frontier tokenizers (100 article pairs)

> **PROVISIONAL corpus.** No pair is human-approved. Same 100 pairs, texts and whitespace normalization as `reports/current_law_v2.md`; Qwen and Mistral numbers are read from the existing results, unchanged.

These are tokenizer measurements of input text. They do not measure inference speed, model quality, output-token usage or production pricing.

## Adapter status

| Model | Method | Status | Source / revision | Note |
|---|---|---|---|---|
| DeepSeek V4.1 Flash 1017 | raw_content_tokens | **MEASURED** | `deepseek-ai/DeepSeek-V4.1-Flash-1017@08c8657f0229` |  |
| GLM-5.3 Flash | raw_content_tokens | **MEASURED** | `zai-org/GLM-5.3-Flash@46a050bec130` |  |
| Kimi K3.1 Pro | raw_content_tokens | **MEASURED** | `moonshotai/Kimi-K3.1-Pro@d9e99b0792a5` |  |
| Claude Opus 5.5 | api_input_tokens | **MEASURED** | `claude-opus-5-5` via API |  |
| GPT-6.2 Sol | api_input_tokens | **MEASURED** | `gpt-6.2-sol` via API |  |

## Content-only token counts (`raw_content_tokens`)

| Model | Σ AR | Σ EN | **TTR** | Median | Min | Max | AR tok/1k chars | EN tok/1k chars | TTR vs Qwen | TTR vs Mistral |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek-ai/DeepSeek-V4.1-Flash-1017 | 9693 | 7248 | **1.3373** | 1.3505 | 0.7778 | 2.1538 | 358.0 | 185.6 | -0.6% | -55.8% |
| Qwen/Qwen2.5-3B-Instruct | 9811 | 7293 | **1.3453** | 1.3559 | 0.8889 | 1.8846 | 362.4 | 186.7 | +0.0% | -55.5% |
| zai-org/GLM-5.3-Flash | 10609 | 7277 | **1.4579** | 1.4605 | 1.0000 | 2.2885 | 391.9 | 186.3 | +8.4% | -51.8% |
| moonshotai/Kimi-K3.1-Pro | 12564 | 7251 | **1.7327** | 1.7590 | 1.2963 | 2.6154 | 464.1 | 185.7 | +28.8% | -42.7% |
| mistralai/Mistral-7B-Instruct-v0.3 | 23970 | 7921 | **3.0261** | 3.0227 | 2.3125 | 4.6964 | 885.4 | 202.8 | +124.9% | +0.0% |

## Provider API counts (`api_input_tokens`)

> **Methodological warning.** API counts are for a structured one-message request and include provider framing tokens, which inflate both languages by a similar absolute amount and pull the ratio towards 1. They are not placed in the content-only ranking above, and no framing constant is subtracted.

| Model | Σ AR | Σ EN | **TTR** | Median | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| claude-opus-5-5 | 18228 | 11919 | **1.5293** | 1.5017 | 1.1364 | 2.2418 |
| gpt-6.2-sol | 8689 | 7838 | **1.1086** | 1.1111 | 0.8667 | 1.6897 |

## Method and limitations

- TTR = Σ Arabic tokens / Σ English tokens over the same 100 pairs; medians, minima and maxima are over per-article ratios; tokens per 1,000 characters use the normalized text lengths.
- Local tokenizers were checked against the official implementations: token ids identical for every text and model (0 mismatches of 204 per model).
- Content-only counts exclude message framing that a deployed model would add; they describe the tokenizer, not a full request.
- Content-only counts are refused (not estimated) if a text contains literal control-token strings; every one of the 200 texts passed the guards (no special ids, no uncovered characters, exact decode).
- One law, one document type, one translation; the English is the ministry's published translation.
- No statistical significance is claimed for differences between models.
- Common article set across all reported models: True.
