# ATTI current_law_v2: Arabic-focused and Arab-developed tokenizers (100 pairs)

> **PROVISIONAL corpus, experimental results.** No pair is human-approved. Same 100 pairs, texts, whitespace normalization, metrics and special-token policy as the existing content-only results, which are read unchanged.

Tokenizer measurements of input text only (`raw_content_tokens`): no special tokens, no chat template, no truncation. Not model quality, speed, output length or pricing. Provider API counts (`api_input_tokens`) are a different method and are not included here.

## Ranked results (`raw_content_tokens`)

Token tax = (TTR − 1) × 100. Ratio columns are Arabic ÷ English; Median, Min and Max are over per-article ratios. Each row is one distinct tokenizer; equivalent tokenizers are listed after `=`.

| # | Tokenizer | Country | Set | Σ AR | Σ EN | **TTR** | Token tax | Median | Min | Max | TTR without 34, 35, 108 |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | AraGPT2 Mega ⚠ | Lebanon | new | 5,942 | 13,796 | **0.4307** | -56.9% | 0.4238 | 0.2647 | 0.6761 | 0.4299 |
| 2 | ALLaM 7B Instruct (preview) | Saudi Arabia | new | 6,097 | 7,645 | **0.7975** | -20.2% | 0.8011 | 0.5517 | 1.2222 | 0.7952 |
| 3 | Jais 3 375B-A23B = K2 Horizon 375B-A23B | United Arab Emirates | new | 6,015 | 7,202 | **0.8352** | -16.5% | 0.8295 | 0.6232 | 1.3333 | 0.8321 |
| 4 | Fanar 2 27B Instruct | Qatar | new | 8,780 | 7,279 | **1.2062** | +20.6% | 1.2301 | 0.7778 | 1.9020 | 1.2029 |
| 5 | DeepSeek V4.1 Flash 1017 | — | existing | 9,693 | 7,248 | **1.3373** | +33.7% | 1.3505 | 0.7778 | 2.1538 | 1.3339 |
| 6 | Qwen2.5-3B-Instruct = AceGPT v2 32B | — | existing | 9,811 | 7,293 | **1.3453** | +34.5% | 1.3559 | 0.8889 | 1.8846 | 1.3404 |
| 7 | GLM-5.3 Flash | — | existing | 10,609 | 7,277 | **1.4579** | +45.8% | 1.4605 | 1.0000 | 2.2885 | 1.4543 |
| 8 | Kimi K3.1 Pro | — | existing | 12,564 | 7,251 | **1.7327** | +73.3% | 1.7590 | 1.2963 | 2.6154 | 1.7297 |
| 9 | Mistral-7B-Instruct-v0.3 | — | existing | 23,970 | 7,921 | **3.0261** | +202.6% | 3.0227 | 2.3125 | 4.6964 | 3.0218 |

⚠ AraGPT2 Mega: English costs 1.90x the median tokens per character, so its TTR below 1 reflects inefficient English, not efficient Arabic.

Per-language efficiency separates the two sides of the ratio:

| Tokenizer | Set | AR tok/1k chars | EN tok/1k chars | EN vs median | TTR vs Qwen2.5 | TTR vs Mistral |
|---|---|---:|---:|---:|---:|---:|
| AraGPT2 Mega | new | 219.5 | 353.2 | 1.90x | -68.0% | -85.8% |
| Jais 3 375B-A23B | new | 222.2 | 184.4 | 0.99x | -37.9% | -72.4% |
| ALLaM 7B Instruct (preview) | new | 225.2 | 195.7 | 1.05x | -40.7% | -73.6% |
| Fanar 2 27B Instruct | new | 324.3 | 186.4 | 1.00x | -10.3% | -60.1% |
| DeepSeek V4.1 Flash 1017 | existing | 358.0 | 185.6 | | | |
| Qwen2.5-3B-Instruct | existing | 362.4 | 186.7 | | | |
| GLM-5.3 Flash | existing | 391.9 | 186.3 | | | |
| Kimi K3.1 Pro | existing | 464.1 | 185.7 | | | |
| Mistral-7B-Instruct-v0.3 | existing | 885.4 | 202.8 | | | |

## Tokenizers

| Model | Country | Developers | Repository @ revision | Tokenizer | Vocabulary | License | Status |
|---|---|---|---|---|---:|---|---|
| ALLaM 7B Instruct (preview) | Saudi Arabia | National Center for Artificial Intelligence (NCAI), Saudi Data and AI Authority (SDAIA); repository now hosted by the humain-ai organization | `humain-ai/ALLaM-7B-Instruct-preview@a28dd1e67420` | SentencePiece BPE | 64,000 | apache-2.0 (Hub metadata; the model card refers to a LICENSE file that is not in the repository) | **MEASURED** |
| Jais 3 375B-A23B | United Arab Emirates | Team IFM (Institute of Foundation Models, MBZUAI) per the model card citation; repository hosted by the inception42 organization | `inception42/Jais-3-375B-A23B@f51d0a4dd93e` | byte-level BPE | 250,624 | apache-2.0 | **MEASURED** |
| K2 Horizon 375B-A23B | United Arab Emirates | IFM (Institute of Foundation Models, MBZUAI) | `IFM/K2-Horizon-375B-A23B@7a17b47a74b9` | byte-level BPE | 250,624 | apache-2.0 | **EQUIVALENT** |
| Fanar 2 27B Instruct | Qatar | Qatar Computing Research Institute (QCRI), Hamad Bin Khalifa University; sponsored by the Ministry of Communications and Information Technology, State of Qatar. Tokenizer: Google (Gemma 3), unchanged | `QCRI/Fanar-2-27B-Instruct@074005040e9c` | SentencePiece-style BPE (byte fallback) | 262,145 | apache-2.0 | **MEASURED** |
| AraGPT2 Mega | Lebanon | AUB MIND Lab, American University of Beirut | `aubmindlab/aragpt2-mega@0c129c98931a` | byte-level BPE (GPT-2) | 64,000 | other: custom AraGPT2 software license (aub-mind/arabert) | **MEASURED** |
| AceGPT v2 32B | Saudi Arabia and China (collaboration) | KAUST and King Abdulaziz University (Saudi Arabia) with The Chinese University of Hong Kong, Shenzhen and the Shenzhen Research Institute of Big Data (China); tokenizer from Qwen1.5 (Alibaba), unchanged | `FreedomIntelligence/AceGPT-v2-32B@d07e8ea20b3c` | byte-level BPE | 151,646 | apache-2.0 | **EQUIVALENT** |
| ArabianGPT 0.8B V2 | Saudi Arabia | Robotics and Internet-of-Things Lab (RIOTU), Prince Sultan University | `riotu-lab/ArabianGPT-08B-V2@97d86d8de4ee` | Metaspace BPE (no byte fallback) | 64,002 | apache-2.0 | **EXCLUDED** |
| Falcon-H1 Arabic 34B | United Arab Emirates | Technology Innovation Institute (TII), Abu Dhabi | none |  |  |  | **UNAVAILABLE** |

Full revisions, asset SHA-256s and source notes: `manifest/regional_tokenizers.json`.

## Equivalence groups

- **Jais 3 375B-A23B** = K2 Horizon 375B-A23B: token ids identical on all 200 texts. Released tokenizer.json; byte-identical to Jais 3's (same SHA-256 for tokenizer.json and tokenizer_config.json).
- **Qwen2.5-3B-Instruct** = AceGPT v2 32B: token ids identical on all 200 texts. Developed from Qwen1.5-32B (model card). Its tokenizer.json is the same git blob as Qwen/Qwen1.5-32B@cefef80dc06a65f89d1d71d0adbc56d335ca2490, and its vocab.json equals Qwen2.5's.
- **Fanar 2 27B Instruct** uses Google's Gemma 3 tokenizer unchanged (file hashes; see the manifest). Gemma 3 is not otherwise in ATTI, so the row is a distinct tokenizer, but it is not an Arab-developed tokenizer.

## Excluded and unavailable

- **ArabianGPT 0.8B V2** (EXCLUDED): cannot represent every corpus text faithfully: ar texts with special or unknown token ids: 48. Characters mapped to the unknown token (occurrences): U+064B ARABIC FATHATAN: 85; U+0651 ARABIC SHADDA: 10; U+064F ARABIC DAMMA: 6; U+064E ARABIC FATHA: 1; U+0650 ARABIC KASRA: 1.
- **Falcon-H1 Arabic 34B** (UNAVAILABLE): No public tokenizer: no Falcon-H1 Arabic repository exists on the Hugging Face Hub (searches for Falcon-H1-Arabic, Falcon-Arabic and falcon-h1-ar, by author tiiuae and Hub-wide), and the official announcement (huggingface.co/blog/tiiuae/falcon-h1-arabic) and product page (falconllm.tii.ae/falcon-h1-arabic.html) link only a chat interface. Neither states that it uses the standard Falcon-H1 tokenizer, so that tokenizer is not substituted.

## Method and limitations

- TTR = Σ Arabic tokens / Σ English tokens over the same 100 pairs; the sensitivity column drops Articles 34, 35 and 108, retained with documented source-alignment limitations.
- Every text passed every guard for each measured tokenizer (no truncation, full character coverage, no special or unknown ids, decode round-trip, identical ids on repeat). Round-trip: ALLaM 7B Instruct (preview): exact; Jais 3 375B-A23B: exact up to the tokenizer's own NFC normalization (4 texts change); Fanar 2 27B Instruct: exact; AraGPT2 Mega: exact up to the GPT-2 prefix space the tokenizer adds.
- NFC normalizers (Jais 3 / K2 Horizon here; also Qwen2.5 and AceGPT v2) reorder combining marks in 4 Arabic texts whose published diacritic order is not canonical; the change is canonically equivalent and is the tokenizer's own behaviour.
- AraGPT2's documented usage applies the arabert preprocessor first; ATTI does not, so its counts describe the published text, not the model's training-time input format.
- ALLaM: token ids identical to the official sentencepiece 0.2.1 SentencePieceProcessor.encode on all 200 corpus texts and 15 synthetic edge cases (leading digits, Arabic-Indic digits, repeated, leading and trailing spaces, byte-fallback characters); run in an isolated environment, not a dependency. Fanar 2: tokenizer.json ids identical to the official sentencepiece 0.2.1 encoding with the repository's own tokenizer.model on the same 215 texts.
- Vocabulary size includes added tokens where the tokenizer defines them.
- Equivalence is functional identity on this corpus (all 200 texts) plus, where noted, identical files; it is not a proof of identity on all possible inputs.
- One law, one translation; no statistical significance is claimed for differences between tokenizers.
- Availability and provenance checked on 2026-11-26.
