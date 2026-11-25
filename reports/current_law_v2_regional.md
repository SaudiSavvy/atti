# ATTI current_law_v2: Arabic-focused and Arab-developed tokenizers (100 pairs)

> **PROVISIONAL corpus, experimental results.** No pair is human-approved. Same 100 pairs, texts, whitespace normalization, metrics and special-token policy as the existing content-only results, which are read unchanged.

Tokenizer measurements of input text only (`raw_content_tokens`): no special tokens, no chat template, no truncation. Not model quality, speed, output length or pricing. Provider API counts (`api_input_tokens`) are a different method and are not included here.

## Bilingual ranking (`raw_content_tokens`)

TTR = Σ Arabic tokens / Σ English tokens; token tax = (TTR − 1) × 100. Median and range are over the 100 per-article ratios. Each row is one distinct tokenizer, named by origin; the models that ship it are listed beside it.

| # | Tokenizer | Shipped by | Set | Σ AR | Σ EN | **TTR** | Token tax | Median | Min–max | TTR without 34, 35, 108 |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | ALLaM tokenizer (NCAI/SDAIA) | ALLaM 7B Instruct (preview) | new | 6,097 | 7,645 | **0.7975** | -20.2% | 0.8011 | 0.5517–1.2222 | 0.7952 |
| 2 | K2 Horizon tokenizer (IFM, MBZUAI) | Jais 3 375B-A23B, K2 Horizon 375B-A23B | new | 6,015 | 7,202 | **0.8352** | -16.5% | 0.8295 | 0.6232–1.3333 | 0.8321 |
| 3 | Gemma 3 tokenizer (Google) | Fanar 2 27B Instruct | new | 8,780 | 7,279 | **1.2062** | +20.6% | 1.2301 | 0.7778–1.9020 | 1.2029 |
| 4 | DeepSeek V4.1 Flash 1017 | DeepSeek V4.1 Flash 1017 | existing | 9,693 | 7,248 | **1.3373** | +33.7% | 1.3505 | 0.7778–2.1538 | 1.3339 |
| 5 | Qwen2.5-3B-Instruct | Qwen2.5-3B-Instruct, AceGPT v2 32B (same ids on this corpus only) | existing | 9,811 | 7,293 | **1.3453** | +34.5% | 1.3559 | 0.8889–1.8846 | 1.3404 |
| 6 | GLM-5.3 Flash | GLM-5.3 Flash | existing | 10,609 | 7,277 | **1.4579** | +45.8% | 1.4605 | 1.0000–2.2885 | 1.4543 |
| 7 | Kimi K3.1 Pro | Kimi K3.1 Pro | existing | 12,564 | 7,251 | **1.7327** | +73.3% | 1.7590 | 1.2963–2.6154 | 1.7297 |
| 8 | Mistral-7B-Instruct-v0.3 | Mistral-7B-Instruct-v0.3 | existing | 23,970 | 7,921 | **3.0261** | +202.6% | 3.0227 | 2.3125–4.6964 | 3.0218 |

## Arabic-focused result: AraGPT2 Mega (reported separately)

| Tokenizer | Σ AR | Σ EN | **TTR** | Token tax | Median | Min–max | TTR without 34, 35, 108 |
|---|---:|---:|---:|---:|---:|---:|---:|
| AraGPT2 tokenizer (American University of Beirut) | 5,942 | 13,796 | **0.4307** | -56.9% | 0.4238 | 0.2647–0.6761 | 0.4299 |

Its Arabic count is the lowest measured, but its English costs 353.2 tokens per 1,000 characters, 1.90× the median of all reported tokenizers (English tokens per 1,000 characters above 1.5x the median of all reported tokenizers). Its ratio is therefore driven by the English denominator and is not ranked with bilingual tokenizers. Released tokenizer.json (GPT-2 byte-level BPE, 64,000 tokens, add_prefix_space=true; no tokenizer_config.json in the repository). The AraGPT2 paper (arXiv 2012.15520, section 3.2) trains it on a preprocessed corpus from which all diacritics and elongations were removed and in which punctuation and non-alphabetic characters were padded with spaces; the model card asks that input first be passed through the arabert ArabertPreprocessor. ATTI applies no preprocessing beyond its whitespace normalization, so counts are for the text as published. The repository's custom code is model code only and is not used.

## Per-language efficiency

| Tokenizer | Set | AR tok/1k chars | EN tok/1k chars | EN vs median | TTR vs Qwen2.5 | TTR vs Mistral |
|---|---|---:|---:|---:|---:|---:|
| AraGPT2 tokenizer | new | 219.5 | 353.2 | 1.90× | -68.0% | -85.8% |
| K2 Horizon tokenizer | new | 222.2 | 184.4 | 0.99× | -37.9% | -72.4% |
| ALLaM tokenizer | new | 225.2 | 195.7 | 1.05× | -40.7% | -73.6% |
| Gemma 3 tokenizer | new | 324.3 | 186.4 | 1.00× | -10.3% | -60.1% |
| DeepSeek V4.1 Flash 1017 | existing | 358.0 | 185.6 | | | |
| Qwen2.5-3B-Instruct | existing | 362.4 | 186.7 | | | |
| GLM-5.3 Flash | existing | 391.9 | 186.3 | | | |
| Kimi K3.1 Pro | existing | 464.1 | 185.7 | | | |
| Mistral-7B-Instruct-v0.3 | existing | 885.4 | 202.8 | | | |

## Models and tokenizers

Model developers and tokenizer origin are recorded separately; a model's country does not imply where its tokenizer was built. Licenses: the model release's own declaration, then the terms of an inherited tokenizer's upstream release where they differ.

| Model | Model developers (country) | Tokenizer (origin) | Model license | Upstream tokenizer terms | Repository @ revision | Vocabulary | Status |
|---|---|---|---|---|---|---:|---|
| ALLaM 7B Instruct (preview) | National Center for Artificial Intelligence (NCAI), Saudi Data and AI Authority (SDAIA); repository hosted by the humain-ai organization (Saudi Arabia) | ALLaM tokenizer (NCAI/SDAIA, released with the model) | apache-2.0 (Hub metadata) | same release; unresolved: the model card refers to a LICENSE file that is not in the pinned repository | `humain-ai/ALLaM-7B-Instruct-preview@a28dd1e67420` | 64,000 | **MEASURED** |
| Jais 3 375B-A23B | Jais Team: Institute of Foundation Models (IFM), MBZUAI; Cerebras Systems; Inception42 (technical report affiliations) (United Arab Emirates, with Cerebras Systems (United States)) | K2 Horizon tokenizer (IFM (MBZUAI), from K2 Horizon; files byte-identical to IFM/K2-Horizon-375B-A23B) | apache-2.0 (Hub metadata) | apache-2.0 (K2 Horizon Hub metadata; LICENSE file in the K2 Horizon repository) | `inception42/Jais-3-375B-A23B@f51d0a4dd93e` | 250,624 | **MEASURED** |
| K2 Horizon 375B-A23B | IFM Team, Institute of Foundation Models (IFM), MBZUAI (United Arab Emirates) | K2 Horizon tokenizer (IFM (MBZUAI), released with the model) | apache-2.0 (Hub metadata; LICENSE file in the repository) | same release | `IFM/K2-Horizon-375B-A23B@7a17b47a74b9` | 250,624 | **EQUIVALENT** |
| Fanar 2 27B Instruct | Qatar Computing Research Institute (QCRI), Hamad Bin Khalifa University; sponsored by the Ministry of Communications and Information Technology, State of Qatar (Qatar) | Gemma 3 tokenizer (Google (Gemma 3), unchanged) | apache-2.0 (Hub metadata) | upstream Google repositories carry the Hub license tag 'gemma' (Gemma Terms of Use); how those terms apply to the files redistributed with Fanar 2 is not assessed here | `QCRI/Fanar-2-27B-Instruct@074005040e9c` | 262,145 | **MEASURED** |
| AraGPT2 Mega | Wissam Antoun, Fady Baly, Hazem Hajj; AUB MIND Lab, American University of Beirut (Lebanon) | AraGPT2 tokenizer (American University of Beirut, trained for AraGPT2 (paper section 3.2)) | custom AraGPT2 software license (LICENSE in the pinned repository; Hub tag 'other') | same license | `aubmindlab/aragpt2-mega@0c129c98931a` | 64,000 | **MEASURED** |
| AceGPT v2 32B | KAUST and King Abdulaziz University (Saudi Arabia) with The Chinese University of Hong Kong, Shenzhen and the Shenzhen Research Institute of Big Data (China) (Saudi Arabia and China (collaboration)) | Qwen1.5 tokenizer (Alibaba Qwen team (Qwen1.5), unchanged) | apache-2.0 (Hub metadata) | upstream Qwen/Qwen1.5-32B carries the Hub license 'tongyi-qianwen-research' (LICENSE in that repository); how it applies to the files redistributed with AceGPT is not assessed here | `FreedomIntelligence/AceGPT-v2-32B@d07e8ea20b3c` | 151,646 | **EQUIVALENT** |
| ArabianGPT 0.8B V2 | Robotics and Internet-of-Things Lab (RIOTU), Prince Sultan University (Saudi Arabia) | Aranizer 64K (RIOTU Lab, Prince Sultan University) | apache-2.0 (Hub metadata) | same release | `riotu-lab/ArabianGPT-08B-V2@97d86d8de4ee` | 64,002 | **EXCLUDED** |
| Falcon-H1 Arabic 34B | Technology Innovation Institute (TII), Abu Dhabi (United Arab Emirates) | none |  |  | none |  | **UNAVAILABLE** |

Full revisions, asset SHA-256s, runtimes and source notes: `manifest/regional_tokenizers.json`.

## Equivalence

- **K2 Horizon 375B-A23B** = **Jais 3 375B-A23B**: ids_sha256 equal on all 200 corpus texts; identical tokenizer files. Released tokenizer.json; byte-identical to Jais 3's (same SHA-256 for tokenizer.json and tokenizer_config.json). K2 Horizon is the tokenizer's origin.
- **AceGPT v2 32B** = **Qwen2.5-3B-Instruct**: ids_sha256 equal on all 200 corpus texts; same token ids on the 200 corpus texts only; tokenizer files differ. Not equivalent in general: 19 added-token strings encode differently without special tokens (e.g. `</tool_call>`, `<tool_call>`, `<|box_end|>`). Developed from Qwen1.5-32B (model card). Its tokenizer.json is the same git blob as Qwen/Qwen1.5-32B@cefef80dc06a65f89d1d71d0adbc56d335ca2490, and its vocab.json equals Qwen2.5's.
- **Fanar 2 27B Instruct** ships the Gemma 3 tokenizer (Google (Gemma 3), unchanged); it is a distinct tokenizer in ATTI but not an Arab-developed one. Executed cross-check: 200/200 texts give identical ids with sentencepiece 0.2.1 SentencePieceProcessor.encode with the repository's tokenizer.model (sha256 1299c11d7cf632ef3b4e11937501358ada021bbdf7c47638d13c0ee982f2e79c).

## Excluded and unavailable

- **ArabianGPT 0.8B V2** (EXCLUDED): cannot represent every corpus text faithfully: ar texts with special or unknown token ids: 48. Characters mapped to the unknown token (occurrences): U+064B ARABIC FATHATAN: 85; U+0651 ARABIC SHADDA: 10; U+064F ARABIC DAMMA: 6; U+064E ARABIC FATHA: 1; U+0650 ARABIC KASRA: 1.
- **Falcon-H1 Arabic 34B** (UNAVAILABLE): No public tokenizer: no Falcon-H1 Arabic repository exists on the Hugging Face Hub (searches for Falcon-H1-Arabic, Falcon-Arabic and falcon-h1-ar, by author tiiuae and Hub-wide), and the official announcement (huggingface.co/blog/tiiuae/falcon-h1-arabic) and product page (falconllm.tii.ae/falcon-h1-arabic.html) link only a chat interface. Neither states that it uses the standard Falcon-H1 tokenizer, so that tokenizer is not substituted.

## Method and limitations

- TTR = Σ Arabic tokens / Σ English tokens over the same 100 pairs; the sensitivity column drops Articles 34, 35 and 108, retained with documented source-alignment limitations.
- Every text passed every guard for each measured tokenizer (no truncation, full character coverage, no special or unknown ids, decode round-trip, identical ids on repeat). Runtimes: ALLaM 7B Instruct (preview): sentencepiece 0.2.1 SentencePieceProcessor.encode (official library), round-trip exact; Jais 3 375B-A23B: tokenizers 0.22.1 Tokenizer.encode(text, add_special_tokens=False), round-trip exact up to the tokenizer's own NFC normalization (4 texts change); Fanar 2 27B Instruct: tokenizers 0.22.1 Tokenizer.encode(text, add_special_tokens=False), round-trip exact; AraGPT2 Mega: tokenizers 0.22.1 Tokenizer.encode(text, add_special_tokens=False), round-trip exact up to the GPT-2 prefix space the tokenizer adds.
- NFC normalizers (the K2 Horizon tokenizer here; also Qwen2.5 and AceGPT v2) reorder combining marks in 4 Arabic texts whose published diacritic order is not canonical; the change is canonically equivalent and is the tokenizer's own behaviour.
- Vocabulary size includes added tokens where the tokenizer defines them.
- Equivalence means identical token ids on these 200 texts; only identical files imply identity on all inputs.
- Licensing is recorded as declared; where an inherited tokenizer's upstream terms differ from the model release's declaration, how they apply is not assessed here.
- A failed or unverifiable rerun writes nothing. When a run succeeds, its four files are validated first and then replaced one at a time, so an interruption between replacements or two overlapping runs could leave files from different runs; a complete-generation writer is deferred.
- One law, one translation; no statistical significance is claimed for differences between tokenizers.
- Availability and provenance checked on 2026-11-26.
