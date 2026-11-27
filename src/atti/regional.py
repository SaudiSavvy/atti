"""Arabic-focused and Arab-developed tokenizers on the 100 current_law_v2 pairs (``raw_content_tokens``).

Experimental and kept apart from every published artifact: Qwen, Mistral and the frontier results are only
read, and this module writes only its own four files (``OUTPUTS``). Same corpus, texts, whitespace
normalization, metric definitions and special-token policy as the other content-only counts.

* Only tokenizer files are downloaded (allow-listed names at pinned revisions, SHA-256 checked before
  use). No model weights, no inference, no repository code is executed.
* Every text must pass the run-time guards: no truncation, every character covered by a token, no special
  or unknown token, and decode(encode(text)) reproduces the text (up to the tokenizer's own declared
  Unicode normalization or GPT-2 prefix space). A tokenizer that fails on any text is EXCLUDED, not counted.
* A tokenizer whose token ids equal those of another tokenizer on all 200 texts is EQUIVALENT on this
  corpus: it is reported as a member of that tokenizer's group and never as an independent result.
* Any integrity, retrieval or unexpected failure aborts the run before anything is written, so the last
  verified outputs stay in place; published statuses and evidence can only be reproduced, never changed.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import statistics
import unicodedata
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path

from tokenizers import Tokenizer

from atti import measure
from atti import adapters
from atti import frontier as F
from atti import tokenization

ADAPTER_VERSION = "1.0"
SENTENCEPIECE_VERSION = "0.2.1"  # official runtime, pinned in the `regional` dependency group
ASSET_ALLOWLIST = {"tokenizer.json", "tokenizer.model", "tokenizer_config.json"}
HF_CACHE = Path("data") / "hf_regional"
CHECKED_ON = "2026-11-26"  # Hub availability and provenance checks (repository metadata, model cards, reports)
SENSITIVITY_EXCLUDED = ("34", "35", "108")  # pairs retained with documented source-alignment limitations
ENGLISH_FLAG = 1.5  # English tokens per 1,000 characters above 1.5x the median: reported separately
STATUSES = ("MEASURED", "EQUIVALENT", "EXCLUDED", "UNAVAILABLE")
OUTPUTS = {
    "csv": Path("results") / f"{F.CORPUS}_regional.csv",
    "summary": Path("results") / f"{F.CORPUS}_regional_summary.json",
    "report": Path("reports") / f"{F.CORPUS}_regional.md",
    "manifest": Path("manifest") / "regional_tokenizers.json",
}


class RegionalError(adapters.FrontierError):
    """The run could not verify every tokenizer; nothing was written and published outputs are unchanged."""


@dataclass(frozen=True)
class RegionalSpec(adapters.LocalSpec):
    model_country: str = ""
    model_developers: str = ""
    model_license: str = ""  # the downstream model release's own declaration
    tokenizer_name: str = ""
    tokenizer_developer: str = ""  # short attribution used in tables
    tokenizer_type: str = ""
    tokenizer_origin: str = ""  # who built the tokenizer, and where the files come from
    tokenizer_terms: str = ""  # upstream terms for inherited tokenizers; unresolved evidence stated as such
    crosscheck_assets: dict = field(default_factory=dict)  # official-runtime reference files (not counted)


ALLAM = RegionalSpec(
    "allam-7b-instruct-preview", "ALLaM 7B Instruct (preview)", "humain-ai/ALLaM-7B-Instruct-preview",
    "a28dd1e67420cde72d3629c8633a974cf7d9c366", "sentencepiece",
    {"tokenizer.model": "feff3deb3537c4a47b77585053ad2aa00484da7907b188e0111cbed1f4592e67",
     "tokenizer_config.json": "37bcb27b4b135353488e79314ceb16182049265c95790e6586b2afeb62e40093"},
    "The repository ships only a SentencePiece tokenizer.model (no tokenizer.json at any of its 33 commits); "
    "this revision is the 'version 2' tokenizer: BPE, 64,000 pieces, identity normalization, byte fallback. "
    "Counted with the official sentencepiece runtime. tokenizer_config.json: add_bos_token=false, "
    "add_eos_token=false.",
    model_country="Saudi Arabia",
    model_developers="National Center for Artificial Intelligence (NCAI), Saudi Data and AI Authority "
                     "(SDAIA); repository hosted by the humain-ai organization",
    model_license="apache-2.0 (Hub metadata)",
    tokenizer_name="ALLaM tokenizer", tokenizer_developer="NCAI/SDAIA", tokenizer_type="SentencePiece BPE",
    tokenizer_origin="NCAI/SDAIA, released with the model",
    tokenizer_terms="same release; unresolved: the model card refers to a LICENSE file that is not in the "
                    "pinned repository")
JAIS3 = RegionalSpec(
    "jais-3-375b-a23b", "Jais 3 375B-A23B", "inception42/Jais-3-375B-A23B",
    "f51d0a4dd93ed0d5cbb9ed58749aa519bd091bc9", "tokenizers",
    {"tokenizer.json": "2fa69519ff1ee3ee55ac50927b00058e88b9eb90802fabaf3c6b05804601c53b",
     "tokenizer_config.json": "581375b2ce8d56d59f609f08a7165365ac53b6543f3442ef0117b4951b0d747c"},
    "Released tokenizer.json (byte-level BPE, 250,000 base tokens + 624 added; NFC normalizer; the "
    "TemplateProcessing post-processor adds a begin-of-text token only when special tokens are requested, "
    "which content-only counts never do). The IFM technical report 'Jais 3: Introducing Arabic-centric "
    "Agentic AI' (2026-11-13, section 2) states that each Jais 3 model keeps the K2 Horizon architecture and "
    "tokenizer unchanged. The repository's custom code is model configuration only and is not used.",
    model_country="United Arab Emirates, with Cerebras Systems (United States)",
    model_developers="Jais Team: Institute of Foundation Models (IFM), MBZUAI; Cerebras Systems; Inception42 "
                     "(technical report affiliations)",
    model_license="apache-2.0 (Hub metadata)",
    tokenizer_name="K2 Horizon tokenizer", tokenizer_developer="IFM, MBZUAI", tokenizer_type="byte-level BPE",
    tokenizer_origin="IFM (MBZUAI), from K2 Horizon; files byte-identical to IFM/K2-Horizon-375B-A23B",
    tokenizer_terms="apache-2.0 (K2 Horizon Hub metadata; LICENSE file in the K2 Horizon repository)")
K2_HORIZON = RegionalSpec(
    "k2-horizon-375b-a23b", "K2 Horizon 375B-A23B", "IFM/K2-Horizon-375B-A23B",
    "7a17b47a74b9371e71ed64b4080192e01caa6174", "tokenizers",
    {"tokenizer.json": "2fa69519ff1ee3ee55ac50927b00058e88b9eb90802fabaf3c6b05804601c53b",
     "tokenizer_config.json": "581375b2ce8d56d59f609f08a7165365ac53b6543f3442ef0117b4951b0d747c"},
    "Released tokenizer.json; byte-identical to Jais 3's (same SHA-256 for tokenizer.json and "
    "tokenizer_config.json). K2 Horizon is the tokenizer's origin.",
    model_country="United Arab Emirates",
    model_developers="IFM Team, Institute of Foundation Models (IFM), MBZUAI",
    model_license="apache-2.0 (Hub metadata; LICENSE file in the repository)",
    tokenizer_name="K2 Horizon tokenizer", tokenizer_developer="IFM, MBZUAI", tokenizer_type="byte-level BPE",
    tokenizer_origin="IFM (MBZUAI), released with the model",
    tokenizer_terms="same release")
FANAR2 = RegionalSpec(
    "fanar-2-27b-instruct", "Fanar 2 27B Instruct", "QCRI/Fanar-2-27B-Instruct",
    "074005040e9c3511b1c43b4298bef09908285534", "tokenizers",
    {"tokenizer.json": "4667f2089529e8e7657cfb6d1c19910ae71ff5f28aa7ab2ff2763330affad795",
     "tokenizer_config.json": "40131233b6e76727588476460cb61fda8d6bfa0e85d1d303bcbce405c4a0fc5d"},
    "Continually pretrained from google/gemma-3-27b-pt. Its tokenizer.json has the same SHA-256 as "
    "google/gemma-3-27b-it@005ad3404e59d6023443cb575daa05336842228a, and its tokenizer.model equals that of "
    "gemma-3-27b-pt@9fe3c4ebc93fbadb14913801536d022054ef11cc and gemma-3-27b-it (Hub file metadata; the "
    "Gemma repositories are gated and were not downloaded). Fanar's tokenizer_config.json differs from both "
    "Google configurations (git blob ids); it does not affect content-only encoding. SentencePiece-style BPE "
    "with byte fallback; the post-processor's <bos> is added only on request.",
    model_country="Qatar",
    model_developers="Qatar Computing Research Institute (QCRI), Hamad Bin Khalifa University; sponsored by "
                     "the Ministry of Communications and Information Technology, State of Qatar",
    model_license="apache-2.0 (Hub metadata)",
    tokenizer_name="Gemma 3 tokenizer", tokenizer_developer="Google", tokenizer_type="SentencePiece-style BPE (byte fallback)",
    tokenizer_origin="Google (Gemma 3), unchanged",
    tokenizer_terms="upstream Google repositories carry the Hub license tag 'gemma' (Gemma Terms of Use); how "
                    "those terms apply to the files redistributed with Fanar 2 is not assessed here",
    crosscheck_assets={"tokenizer.model": "1299c11d7cf632ef3b4e11937501358ada021bbdf7c47638d13c0ee982f2e79c"})
ARAGPT2 = RegionalSpec(
    "aragpt2-mega", "AraGPT2 Mega", "aubmindlab/aragpt2-mega",
    "0c129c98931a9d888080c83c410ec67960ea4dff", "tokenizers",
    {"tokenizer.json": "a27c1fb8a2e7cc78c346f6bc21fb114353188930c499f670cbb6ffe75e549d91"},
    "Released tokenizer.json (GPT-2 byte-level BPE, 64,000 tokens, add_prefix_space=true; no "
    "tokenizer_config.json in the repository). The AraGPT2 paper (arXiv 2012.15520, section 3.2) trains it on "
    "a preprocessed corpus from which all diacritics and elongations were removed and in which punctuation and "
    "non-alphabetic characters were padded with spaces; the model card asks that input first be passed "
    "through the arabert ArabertPreprocessor. ATTI applies no preprocessing beyond its whitespace "
    "normalization, so counts are for the text as published. The repository's custom code is model code only "
    "and is not used.",
    model_country="Lebanon",
    model_developers="Wissam Antoun, Fady Baly, Hazem Hajj; AUB MIND Lab, American University of Beirut",
    model_license="custom AraGPT2 software license (LICENSE in the pinned repository; Hub tag 'other')",
    tokenizer_name="AraGPT2 tokenizer", tokenizer_developer="American University of Beirut", tokenizer_type="byte-level BPE (GPT-2)",
    tokenizer_origin="American University of Beirut, trained for AraGPT2 (paper section 3.2)",
    tokenizer_terms="same license")
ACEGPT2 = RegionalSpec(
    "acegpt-v2-32b", "AceGPT v2 32B", "FreedomIntelligence/AceGPT-v2-32B",
    "d07e8ea20b3cb0ccab624615b5e0d5e2da9a1378", "tokenizers",
    {"tokenizer.json": "f7c9b2dba4a296b1aa76c16a34b8225c0c118978400d4bb66bff0902d702f5b8",
     "tokenizer_config.json": "6a4a43e8a7c68a7aa377bca6dcd8df1da42fcb79eca8162eb9f7b817ea75db16"},
    "Developed from Qwen1.5-32B (model card). Its tokenizer.json is the same git blob as "
    "Qwen/Qwen1.5-32B@cefef80dc06a65f89d1d71d0adbc56d335ca2490, and its vocab.json equals Qwen2.5's.",
    model_country="Saudi Arabia and China (collaboration)",
    model_developers="KAUST and King Abdulaziz University (Saudi Arabia) with The Chinese University of Hong "
                     "Kong, Shenzhen and the Shenzhen Research Institute of Big Data (China)",
    model_license="apache-2.0 (Hub metadata)",
    tokenizer_name="Qwen1.5 tokenizer", tokenizer_developer="Alibaba Qwen team", tokenizer_type="byte-level BPE",
    tokenizer_origin="Alibaba Qwen team (Qwen1.5), unchanged",
    tokenizer_terms="upstream Qwen/Qwen1.5-32B carries the Hub license 'tongyi-qianwen-research' (LICENSE in "
                    "that repository); how it applies to the files redistributed with AceGPT is not assessed "
                    "here")
ARABIANGPT2 = RegionalSpec(
    "arabiangpt-08b-v2", "ArabianGPT 0.8B V2", "riotu-lab/ArabianGPT-08B-V2",
    "97d86d8de4ee494184d25f3e2822ae7a8cf7efe7", "tokenizers",
    {"tokenizer.json": "5a5a774b76cec6111ff2a452bc56dfe2f788e0a7a89fe67028ea81b05153ba58",
     "tokenizer_config.json": "7979d8c7b8d8a9a43daae399968457a61361df9c3d05947dcc3d1227f10b4253"},
    "Released tokenizer.json ('Aranizer 64K': Metaspace BPE, NFKC normalizer, <unk> without byte fallback).",
    model_country="Saudi Arabia",
    model_developers="Robotics and Internet-of-Things Lab (RIOTU), Prince Sultan University",
    model_license="apache-2.0 (Hub metadata)",
    tokenizer_name="Aranizer 64K", tokenizer_developer="RIOTU Lab, Prince Sultan University", tokenizer_type="Metaspace BPE (no byte fallback)",
    tokenizer_origin="RIOTU Lab, Prince Sultan University", tokenizer_terms="same release")

SPECS = (ALLAM, JAIS3, K2_HORIZON, FANAR2, ARAGPT2, ACEGPT2, ARABIANGPT2)  # order decides group representatives

UNAVAILABLE = {
    "falcon-h1-arabic": {
        "key": "falcon-h1-arabic", "display": "Falcon-H1 Arabic 34B", "model_country": "United Arab Emirates",
        "model_developers": "Technology Innovation Institute (TII), Abu Dhabi", "status": "UNAVAILABLE",
        "measurement_method": adapters.RAW_CONTENT,
        "reason": "No public tokenizer: no Falcon-H1 Arabic repository exists on the Hugging Face Hub (searches "
                  "for Falcon-H1-Arabic, Falcon-Arabic and falcon-h1-ar, by author tiiuae and Hub-wide), and the "
                  "official announcement (huggingface.co/blog/tiiuae/falcon-h1-arabic) and product page "
                  "(falconllm.tii.ae/falcon-h1-arabic.html) link only a chat interface. Neither states that it "
                  "uses the standard Falcon-H1 tokenizer, so that tokenizer is not substituted.",
        "checked_on": CHECKED_ON},
}


# ----------------------------------------------------------------------------- counters

def sentencepiece_processor(model_file: Path):
    """The official SentencePiece runtime at the pinned version (imported only for regional evaluation)."""
    try:
        import sentencepiece as spm
    except ImportError as exc:
        raise adapters.AssetIntegrityError("the official sentencepiece runtime is not installed; "
                                    "run `uv sync --locked` (dependency group `regional`)") from exc
    if spm.__version__ != SENTENCEPIECE_VERSION:
        raise adapters.AssetIntegrityError(f"sentencepiece {spm.__version__} != pinned {SENTENCEPIECE_VERSION}")
    return spm.SentencePieceProcessor(model_file=str(model_file)), spm.__version__


class SentencePieceCounter:
    """tokenizer.model on the official runtime: SentencePieceProcessor.encode, no BOS/EOS (the Python default)."""

    def __init__(self, spec: RegionalSpec, model_file: Path):
        self.spec = spec
        self.sp, version = sentencepiece_processor(model_file)
        self.runtime = f"sentencepiece {version} SentencePieceProcessor.encode (official library)"
        self.vocab_size = self.sp.get_piece_size()
        self.special = {i for i in range(self.vocab_size) if self.sp.is_control(i) or self.sp.is_unknown(i)}

    def ids(self, text: str) -> list[int]:
        pieces = self.sp.encode(text, out_type="immutable_proto").pieces  # begin/end: character offsets
        ids = [p.id for p in pieces]
        if ids != self.sp.encode(text, out_type=int):
            raise adapters.FrontierError(f"{self.spec.key}: proto and integer encodings disagree")
        gaps = tokenization.uncovered_chars(text, [(p.begin, p.end) for p in pieces])
        if gaps:
            raise tokenization.TokenCountError(f"{len(gaps)} characters not covered by any token "
                                               f"(first at index {gaps[0]})")
        leaked = set(ids) & self.special
        if leaked:
            raise tokenization.TokenCountError(f"special/unknown token ids in content encoding: {sorted(leaked)}")
        if self.sp.decode(ids) != text:
            raise adapters.FrontierError(f"{self.spec.key}: decode(encode(text)) != text")
        return ids

    def count(self, text: str) -> int:
        return len(self.ids(text))


_NORMALIZERS = {None: None, "NFC": "NFC", "NFKC": "NFKC"}
_METASPACE_REPLACE = {"type": "Replace", "pattern": {"String": " "}, "content": "▁"}


class TokenizerJsonCounter:
    """A released tokenizer.json on the `tokenizers` runtime. decode(encode(text)) must reproduce the text,
    allowing only what the tokenizer itself declares: an NFC/NFKC normalizer (the decode then equals the
    normalized text) and a GPT-2 ByteLevel prefix space."""

    def __init__(self, spec: RegionalSpec, tokenizer_json: Path):
        import tokenizers

        raw = tokenizer_json.read_text(encoding="utf-8")
        data = json.loads(raw)
        norm = data.get("normalizer")
        if norm == _METASPACE_REPLACE:
            self.form = None
        elif norm is None or set(norm) == {"type"} and norm["type"] in _NORMALIZERS:
            self.form = _NORMALIZERS[norm and norm["type"]]
        else:
            raise adapters.AssetIntegrityError(f"{spec.repo_id}: unsupported normalizer {json.dumps(norm)[:80]}")
        pre = data.get("pre_tokenizer") or {}
        steps = pre.get("pretokenizers", [pre])
        self.prefix_space = any(p.get("type") == "ByteLevel" and p.get("add_prefix_space") for p in steps)
        self.spec = spec
        self.tok = Tokenizer.from_str(raw)
        self.tok.no_truncation()
        self.tok.no_padding()
        self.vocab_size = self.tok.get_vocab_size(with_added_tokens=True)
        self.runtime = f"tokenizers {tokenizers.__version__} Tokenizer.encode(text, add_special_tokens=False)"

    def expected(self, text: str) -> str:
        return unicodedata.normalize(self.form, text) if self.form else text

    def ids(self, text: str) -> list[int]:
        ids = tokenization.checked_encoding(self.tok, text).ids  # truncation/overflow/coverage/special-id guards
        out, want = self.tok.decode(ids, skip_special_tokens=False), self.expected(text)
        if out != want and not (self.prefix_space and out == " " + want):
            raise adapters.FrontierError(f"{self.spec.key}: decode(encode(text)) != text")
        return ids

    def count(self, text: str) -> int:
        return len(self.ids(text))


def load(spec: RegionalSpec, cache_dir: Path, paths: dict | None = None):
    paths = paths or adapters.fetch_assets(spec, cache_dir, ASSET_ALLOWLIST)
    if spec.kind == "sentencepiece":
        return SentencePieceCounter(spec, paths["tokenizer.model"])
    if spec.kind == "tokenizers":
        return TokenizerJsonCounter(spec, paths["tokenizer.json"])
    raise adapters.FrontierError(f"unknown adapter kind {spec.kind}")


def unknown_chars(counter, text: str) -> list[str]:
    """Characters a tokenizer.json maps to its unknown token (evidence for an exclusion)."""
    if not isinstance(counter, TokenizerJsonCounter):
        return []
    unk = getattr(counter.tok.model, "unk_token", None)
    uid = counter.tok.token_to_id(unk) if unk else None
    enc = counter.tok.encode(text, add_special_tokens=False)
    return [text[s:e] for i, (s, e) in zip(enc.ids, enc.offsets) if i == uid]


def official_crosscheck(spec: RegionalSpec, root: Path, counter, texts: list[str]) -> dict:
    """Encode every text with the official SentencePiece runtime and the repository's own tokenizer.model,
    and compare with the counted tokenizer.json ids (executed on every run; nothing is hard-coded)."""
    paths = adapters.fetch_assets(replace(spec, assets=spec.crosscheck_assets), root / HF_CACHE, ASSET_ALLOWLIST)
    sp, version = sentencepiece_processor(paths["tokenizer.model"])
    same = sum(sp.encode(t, out_type=int) == counter.ids(t) for t in texts)
    if same != len(texts):  # the counted tokenizer must agree with the official reference on every text
        raise adapters.FrontierError(f"official SentencePiece cross-check failed: {same}/{len(texts)} texts give "
                              "identical ids")
    return {"reference": f"sentencepiece {version} SentencePieceProcessor.encode with the repository's "
                         f"tokenizer.model (sha256 {spec.crosscheck_assets['tokenizer.model']})",
            "texts": len(texts), "identical_ids": same}


def divergent_added_tokens(a: Tokenizer, b: Tokenizer) -> list[str]:
    """Added-token strings (of either tokenizer) that the two encode differently without special tokens."""
    contents = {t.content for t in (*a.get_added_tokens_decoder().values(), *b.get_added_tokens_decoder().values())}
    return sorted(c for c in contents
                  if a.encode(c, add_special_tokens=False).ids != b.encode(c, add_special_tokens=False).ids)


# ----------------------------------------------------------------------------- run

def ids_digest(id_lists) -> str:
    """SHA-256 over the token ids of every text, in corpus order (Arabic then English per article)."""
    return hashlib.sha256(json.dumps(list(id_lists), separators=(",", ":")).encode()).hexdigest()


def reference_tokenizers(root: Path, texts: list[str]) -> dict[str, dict]:
    """Tokenizers already in ATTI's content-only results (loaded read-only): ids digest, tokenizer.json
    SHA-256 and, where available, the `tokenizers` object."""
    out = {}
    for t in tokenization.TOKENIZERS:
        tok = tokenization.load(t, root / "data" / "hf").tokenizer
        out[t.repo_id] = {"ids_sha256": ids_digest(tok.encode(x, add_special_tokens=False).ids for x in texts),
                          "tokenizer_json": t.sha256, "tok": tok}
    for s in F.LOCAL:
        c = adapters.load_local(s, root / F.HF_CACHE)
        out[s.repo_id] = {"ids_sha256": ids_digest(c.ids(x) for x in texts),
                          "tokenizer_json": s.assets.get("tokenizer.json"), "tok": getattr(c, "tok", None)}
    return out


def _describe(exc: Exception) -> str:
    from huggingface_hub.errors import LocalEntryNotFoundError

    if isinstance(exc, LocalEntryNotFoundError):
        return ("a pinned tokenizer file is not in the local cache and could not be downloaded "
                f"(offline or unreachable): {exc}")
    return f"{type(exc).__name__}: {exc}"


def run(root: Path) -> dict:
    """Measure, then publish only if every tokenizer was verified; otherwise raise RegionalError and write
    nothing, so the last verified outputs remain."""
    from atti import v2

    manifest, records = v2.load_verified(root)
    texts = [t for r in records for t in (r.ar_text, r.en_text)]
    try:
        refs = reference_tokenizers(root, texts)
    except Exception as exc:  # noqa: BLE001 - any failure aborts before writing
        raise RegionalError(f"reference tokenizers: {_describe(exc)}") from exc
    status, rows, measured, errors = {}, [], {}, []
    for spec in SPECS:
        try:
            st, new, counter = evaluate(spec, root, records, manifest, refs, measured)
        except Exception as exc:  # noqa: BLE001 - integrity, retrieval or unexpected failure: abort
            errors.append(f"{spec.key}: {_describe(exc)}")
            continue
        if st["status"] == "MEASURED":
            measured[spec.key] = {"ids_sha256": st["checks"]["ids_sha256"],
                                  "tokenizer_json": spec.assets.get("tokenizer.json"),
                                  "tok": getattr(counter, "tok", None)}
            rows += new
        status[spec.key] = st
    if errors:
        raise RegionalError("; ".join(errors))
    status.update(UNAVAILABLE)
    protect_evidence(root, status)
    outputs = build_outputs(root, manifest, rows, status, refs)
    measure.publish(root, OUTPUTS, outputs, manifest)  # validates; never drops, changes or downgrades published rows
    return status


def evaluate(spec: RegionalSpec, root: Path, records, manifest: dict, refs: dict, measured: dict):
    st = {"key": spec.key, "display": spec.display, "repo_id": spec.repo_id, "revision": spec.revision,
          "model_country": spec.model_country, "model_developers": spec.model_developers,
          "model_license": spec.model_license, "tokenizer_name": spec.tokenizer_name,
          "tokenizer_developer": spec.tokenizer_developer,
          "tokenizer_type": spec.tokenizer_type, "tokenizer_origin": spec.tokenizer_origin,
          "tokenizer_terms": spec.tokenizer_terms, "adapter": spec.kind, "measurement_method": spec.method,
          "source_note": spec.source_note}
    paths = adapters.fetch_assets(spec, root / HF_CACHE, ASSET_ALLOWLIST)
    st["assets"] = {n: {"sha256": d, "bytes": paths[n].stat().st_size} for n, d in spec.assets.items()}
    counter = load(spec, root / HF_CACHE, paths)
    st["runtime"] = counter.runtime
    st["vocab_size"] = counter.vocab_size
    st["checks"] = check(counter, records)
    if st["checks"]["failed_texts"]:
        st["status"] = "EXCLUDED"
        st["reason"] = ("cannot represent every corpus text faithfully: "
                        + "; ".join(f"{k}: {v}" for k, v in st["checks"]["failures"].items()))
        return st, [], counter
    texts = [t for r in records for t in (r.ar_text, r.en_text)]
    if spec.crosscheck_assets:
        st["official_crosscheck"] = official_crosscheck(spec, root, counter, texts)
    digest = st["checks"]["ids_sha256"]
    same = next((k for k, v in {**refs, **measured}.items() if v["ids_sha256"] == digest), None)
    if same is not None:
        other = {**refs, **measured}[same]
        files_same = other["tokenizer_json"] is not None and other["tokenizer_json"] == spec.assets.get(
            "tokenizer.json")
        st.update(status="EQUIVALENT", equivalent_to=same,
                  equivalence={"scope": "identical tokenizer files" if files_same else
                               "same token ids on the 200 corpus texts only; tokenizer files differ",
                               "evidence": "ids_sha256 equal on all 200 corpus texts"})
        if not files_same and other.get("tok") is not None and isinstance(counter, TokenizerJsonCounter):
            div = divergent_added_tokens(counter.tok, other["tok"])
            st["equivalence"]["divergent_added_tokens"] = {"count": len(div), "examples": div[:5]}
        return st, [], counter
    meta = f"{spec.repo_id}@{spec.revision[:12]}; " + ", ".join(
        f"{n} sha256 {d[:12]}" for n, d in spec.assets.items())
    rows = measure.measure_rows(spec, counter, records, manifest, meta)
    for r in rows:
        r["adapter_version"] = ADAPTER_VERSION
    st["status"] = "MEASURED"
    return st, rows, counter


PROTECTED_CHECKS = ("texts", "failed_texts", "failures", "unknown_token_characters", "ids_sha256", "round_trip")


def protect_evidence(root: Path, status: dict) -> None:
    """A published status, equivalence or exclusion record must be reproduced exactly, or nothing is written.
    Changing one is a deliberate step: remove the published regional files first."""
    path = root / OUTPUTS["manifest"]
    if not path.exists():
        return
    old = json.loads(path.read_text(encoding="utf-8"))["adapters"]
    errs = []
    for k, o in old.items():
        n = status.get(k)
        if n is None:
            errs.append(f"{k}: its published record would be removed")
            continue
        if n["status"] != o["status"]:
            errs.append(f"{k}: published as {o['status']}, would become {n['status']}")
        if n.get("equivalent_to") != o.get("equivalent_to") or n.get("equivalence") != o.get("equivalence"):
            errs.append(f"{k}: its published equivalence would change")
        if any(n.get("checks", {}).get(c) != o.get("checks", {}).get(c) for c in PROTECTED_CHECKS):
            errs.append(f"{k}: its published verification evidence would change")
    if errs:
        raise measure.PublishedResultsError("; ".join(errs))


def failure_kind(msg: str) -> str:
    for needle, kind in (("special/unknown", "special or unknown token ids"), ("not covered", "uncovered characters"),
                         ("decode(encode", "a failed decode round-trip"), ("non-deterministic", "unstable ids"),
                         ("truncation", "truncation"), ("padding", "padding"), ("overflow", "overflow")):
        if needle in msg:
            return kind
    return "other guard failures"


def check(counter, records) -> dict:
    """Run every guard on all 200 texts, twice (determinism); collect failures instead of stopping."""
    failures, unk, normalized, prefixed, ids_all = {}, {}, 0, 0, []
    for r in records:
        for lang, text in (("ar", r.ar_text), ("en", r.en_text)):
            try:
                ids = counter.ids(text)
                if counter.ids(text) != ids:
                    raise adapters.FrontierError("non-deterministic encoding")
            except (tokenization.TokenCountError, adapters.FrontierError) as exc:
                kind = f"{lang} texts with {failure_kind(str(exc))}"
                failures[kind] = failures.get(kind, 0) + 1
                for ch in unknown_chars(counter, text):
                    name = " ".join(f"U+{ord(c):04X} {unicodedata.name(c, '?')}" for c in ch)
                    unk[name] = unk.get(name, 0) + 1
                continue
            ids_all.append(ids)
            if isinstance(counter, TokenizerJsonCounter):
                normalized += counter.expected(text) != text
                prefixed += counter.prefix_space
    out = {"texts": 2 * len(records), "failed_texts": sum(failures.values()), "failures": failures,
           "guards": "no truncation/overflow; every character covered; no special or unknown ids; "
                     "decode round-trip; identical ids on repeat"}
    if unk:
        out["unknown_token_characters"] = dict(sorted(unk.items(), key=lambda kv: -kv[1]))
    if not failures:
        out["ids_sha256"] = ids_digest(ids_all)
        out["round_trip"] = "exact" if not normalized and not prefixed else (
            f"exact up to the tokenizer's own {counter.form} normalization ({normalized} texts change)"
            if normalized else "exact up to the GPT-2 prefix space the tokenizer adds")
    return out


# ----------------------------------------------------------------------------- outputs

def ttr_without(rows: list[dict], excluded=SENSITIVITY_EXCLUDED) -> float:
    sel = [r for r in rows if r["article"] not in excluded]
    return float(Fraction(sum(int(r["ar_tokens"]) for r in sel), sum(int(r["en_tokens"]) for r in sel)))


def reference_rows(root: Path) -> dict[str, list[dict]]:
    """Content-only rows already published (Qwen, Mistral, frontier local tokenizers); read only."""
    rows = F.baseline_rows(root)
    with (root / F.OUTPUTS["csv"]).open(encoding="utf-8", newline="") as f:
        rows += [r for r in csv.DictReader(f) if r["measurement_method"] == adapters.RAW_CONTENT]
    return {m: [r for r in rows if r["model"] == m] for m in dict.fromkeys(r["model"] for r in rows)}


REFERENCE_DISPLAY = {"Qwen/Qwen2.5-3B-Instruct": "Qwen2.5-3B-Instruct",
                     "mistralai/Mistral-7B-Instruct-v0.3": "Mistral-7B-Instruct-v0.3",
                     **{s.repo_id: s.display for s in F.LOCAL}}


def _stats(rows: list[dict]) -> dict:
    s = measure.model_summary(rows)
    s["ttr_without_34_35_108"] = ttr_without(rows)
    s["token_tax_pct"] = (s["ttr"] - 1) * 100
    return s


def build_outputs(root: Path, manifest: dict, rows: list[dict], status: dict, refs: dict) -> dict:
    published = json.loads((root / F.OUTPUTS["summary"]).read_text(encoding="utf-8"))["models"]
    reference = {}
    for m, sel in reference_rows(root).items():
        s = _stats(sel)
        if (s["ar_tokens_total"], s["en_tokens_total"], s["ttr"]) != (
                published[m]["ar_tokens_total"], published[m]["en_tokens_total"], published[m]["ttr"]):
            raise adapters.FrontierError(f"{m}: published rows do not reproduce the published summary")
        reference[m] = {"display": REFERENCE_DISPLAY[m], "source": "existing ATTI results (read only)",
                        "ids_sha256": refs[m]["ids_sha256"], **s}
    ref = {"qwen": "Qwen/Qwen2.5-3B-Instruct", "mistral": "mistralai/Mistral-7B-Instruct-v0.3"}
    models = {}
    for k in dict.fromkeys(r["model_key"] for r in rows):
        sel = [r for r in rows if r["model_key"] == k]
        st = status[k]
        s = _stats(sel)
        s["ttr_pct_diff_vs"] = {n: (s["ttr"] / reference[m]["ttr"] - 1) * 100 for n, m in ref.items()}
        models[sel[0]["model"]] = {"display": st["display"], "model_key": k, "model_country": st["model_country"],
                                   "tokenizer_name": st["tokenizer_name"],
                                   "tokenizer_developer": st["tokenizer_developer"],
                                   "tokenizer_origin": st["tokenizer_origin"], "source": str(OUTPUTS["csv"]), **s}
    en_median = statistics.median(s["en_tokens_per_1000_chars"] for s in (*reference.values(), *models.values()))
    for s in models.values():
        s["en_tokens_per_1000_chars_vs_median"] = s["en_tokens_per_1000_chars"] / en_median
        s["ranking"] = "separate" if s["en_tokens_per_1000_chars_vs_median"] > ENGLISH_FLAG else "primary"
    summary = {"corpus": F.CORPUS, "status": "PROVISIONAL", "measurement_method": adapters.RAW_CONTENT,
               "articles": [a["key"] for a in manifest["articles"]],
               "sensitivity_excluded_articles": list(SENSITIVITY_EXCLUDED),
               "separate_ranking_rule": f"English tokens per 1,000 characters above {ENGLISH_FLAG}x the median "
                                        "of all reported tokenizers",
               "models": models, "reference_models": reference,
               "equivalence_groups": equivalence_groups(status, reference)}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=measure.CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    fm = {"corpus": F.CORPUS, "corpus_manifest": "manifest/current_law_v2_manifest.json",
          "corpus_status": manifest["status"], "adapter_version": ADAPTER_VERSION, "checked_on": CHECKED_ON,
          "measurement_method": adapters.RAW_CONTENT,
          "status_definitions": {
              "MEASURED": "all 100 pairs measured in both languages; every guard held on all 200 texts",
              "EQUIVALENT": "token ids identical to another tokenizer's on all 200 corpus texts; reported only "
                            "as a member of that tokenizer's group, never as an independent result. "
                            "`equivalence.scope` says whether the tokenizer files are also identical",
              "EXCLUDED": "at least one corpus text cannot be represented faithfully; no value published",
              "UNAVAILABLE": "no public tokenizer could be verified; nothing substituted"},
          "failure_policy": "an integrity, retrieval or unexpected failure aborts the run before writing; "
                            "published statuses and evidence must be reproduced exactly",
          "asset_policy": "allow-listed tokenizer files only (" + ", ".join(sorted(ASSET_ALLOWLIST)) + ") at "
                          "pinned revisions, SHA-256 checked before use; no weights; no repository code run",
          "adapters": status}
    return {"csv": buf.getvalue(), "summary": measure.dumps(summary), "manifest": measure.dumps(fm),
            "report": render_report(summary, fm)}


def equivalence_groups(status: dict, reference: dict) -> list[dict]:
    groups = {}
    for st in status.values():
        if st["status"] == "EQUIVALENT":
            rep = st["equivalent_to"]
            g = groups.setdefault(rep, {"representative": rep, "display": reference[rep]["display"] if rep in
                                        reference else status[rep]["display"], "members": [], "scope": []})
            g["members"].append(st["key"])
            g["scope"].append(st["equivalence"]["scope"])
    return list(groups.values())


def _row(s: dict) -> str:
    return (f"{s['ar_tokens_total']:,} | {s['en_tokens_total']:,} | **{s['ttr']:.4f}** | {s['token_tax_pct']:+.1f}% | "
            f"{s['median_article_ratio']:.4f} | {s['min_article_ratio']:.4f}–{s['max_article_ratio']:.4f} | "
            f"{s['ttr_without_34_35_108']:.4f}")


def render_report(summary: dict, fm: dict) -> str:
    ad, new, refm = fm["adapters"], summary["models"], summary["reference_models"]
    groups = {g["representative"]: g for g in summary["equivalence_groups"]}

    def shipped_by(key: str, own: str) -> str:
        g = groups.get(key)
        if not g:
            return own
        extra = [f"{ad[m]['display']}" + (" (same ids on this corpus only)" if "only" in s else "")
                 for m, s in zip(g["members"], g["scope"])]
        return ", ".join([own, *extra])

    primary = [(f"{s['tokenizer_name']} ({s['tokenizer_developer']})",
                shipped_by(s["model_key"], s["display"]), "new", s)
               for s in new.values() if s["ranking"] == "primary"]
    primary += [(s["display"], shipped_by(m, s["display"]), "existing", s) for m, s in refm.items()]
    head = ("| Σ AR | Σ EN | **TTR** | Token tax | Median | Min–max | TTR without 34, 35, 108 |",
            "|---:|---:|---:|---:|---:|---:|---:|")
    L = [f"# ATTI {F.CORPUS}: Arabic-focused and Arab-developed tokenizers ({len(summary['articles'])} pairs)\n",
         "> **PROVISIONAL corpus, experimental results.** No pair is human-approved. Same 100 pairs, texts, "
         "whitespace normalization, metrics and special-token policy as the existing content-only results, "
         "which are read unchanged.\n",
         "Tokenizer measurements of input text only (`raw_content_tokens`): no special tokens, no chat template, "
         "no truncation. Not model quality, speed, output length or pricing. Provider API counts "
         "(`api_input_tokens`) are a different method and are not included here.\n",
         "## Bilingual ranking (`raw_content_tokens`)\n",
         "TTR = Σ Arabic tokens / Σ English tokens; token tax = (TTR − 1) × 100. Median and range are over "
         "the 100 per-article ratios. Each row is one distinct tokenizer, named by origin; the models that ship "
         "it are listed beside it.\n",
         "| # | Tokenizer | Shipped by | Set | " + head[0][2:], "|---:|---|---|---|" + head[1][1:]]
    for i, (name, ships, kind, s) in enumerate(sorted(primary, key=lambda x: x[3]["ttr"]), 1):
        L.append(f"| {i} | {name} | {ships} | {kind} | {_row(s)} |")
    for s in (s for s in new.values() if s["ranking"] == "separate"):
        L += ["", f"## Arabic-focused result: {s['display']} (reported separately)\n",
              f"| Tokenizer | {head[0][2:]}", f"|---|{head[1][1:]}",
              f"| {s['tokenizer_name']} ({s['tokenizer_developer']}) | {_row(s)} |", "",
              f"Its Arabic count is the lowest measured, but its English costs {s['en_tokens_per_1000_chars']:.1f} "
              f"tokens per 1,000 characters, {s['en_tokens_per_1000_chars_vs_median']:.2f}× the median of all "
              f"reported tokenizers ({summary['separate_ranking_rule']}). Its ratio is therefore driven by the "
              "English denominator and is not ranked with bilingual tokenizers. " + ad[s["model_key"]]["source_note"]]
    L += ["", "## Per-language efficiency\n",
          "| Tokenizer | Set | AR tok/1k chars | EN tok/1k chars | EN vs median | TTR vs Qwen2.5 | TTR vs Mistral |",
          "|---|---|---:|---:|---:|---:|---:|"]
    for s in sorted(new.values(), key=lambda s: s["ar_tokens_per_1000_chars"]):
        L.append(f"| {s['tokenizer_name']} | new | {s['ar_tokens_per_1000_chars']:.1f} | "
                 f"{s['en_tokens_per_1000_chars']:.1f} | {s['en_tokens_per_1000_chars_vs_median']:.2f}× | "
                 f"{s['ttr_pct_diff_vs']['qwen']:+.1f}% | {s['ttr_pct_diff_vs']['mistral']:+.1f}% |")
    for s in sorted(refm.values(), key=lambda s: s["ar_tokens_per_1000_chars"]):
        L.append(f"| {s['display']} | existing | {s['ar_tokens_per_1000_chars']:.1f} | "
                 f"{s['en_tokens_per_1000_chars']:.1f} | | | |")
    L += ["", "## Models and tokenizers\n",
          "Model developers and tokenizer origin are recorded separately; a model's country does not imply where "
          "its tokenizer was built. Licenses: the model release's own declaration, then the terms of an inherited "
          "tokenizer's upstream release where they differ.\n",
          "| Model | Model developers (country) | Tokenizer (origin) | Model license | Upstream tokenizer terms | "
          "Repository @ revision | Vocabulary | Status |", "|---|---|---|---|---|---|---:|---|"]
    for st in ad.values():
        repo = f"`{st['repo_id']}@{st['revision'][:12]}`" if "repo_id" in st else "none"
        tok = f"{st['tokenizer_name']} ({st['tokenizer_origin']})" if "tokenizer_name" in st else "none"
        vocab = format(st["vocab_size"], ",") if "vocab_size" in st else ""
        L.append(f"| {st['display']} | {st['model_developers']} ({st['model_country']}) | {tok} | "
                 f"{st.get('model_license', '')} | {st.get('tokenizer_terms', '')} | {repo} | {vocab} | "
                 f"**{st['status']}** |")
    L += ["", "Full revisions, asset SHA-256s, runtimes and source notes: `manifest/regional_tokenizers.json`.", "",
          "## Equivalence\n"]
    for g in summary["equivalence_groups"]:
        for m, scope in zip(g["members"], g["scope"]):
            eq = ad[m]["equivalence"]
            div = eq.get("divergent_added_tokens")
            L.append(f"- **{ad[m]['display']}** = **{g['display']}**: {eq['evidence']}; {scope}."
                     + (f" Not equivalent in general: {div['count']} added-token strings encode differently "
                        f"without special tokens (e.g. {', '.join('`' + d + '`' for d in div['examples'][:3])})."
                        if div else "") + " " + ad[m]["source_note"])
    for st in ad.values():
        if st.get("official_crosscheck"):
            c = st["official_crosscheck"]
            L.append(f"- **{st['display']}** ships the {st['tokenizer_name']} ({st['tokenizer_origin']}); it is a "
                     "distinct tokenizer in ATTI but not an Arab-developed one. Executed cross-check: "
                     f"{c['identical_ids']}/{c['texts']} texts give identical ids with {c['reference']}.")
    L += ["", "## Excluded and unavailable\n"]
    for st in ad.values():
        if st["status"] in ("EXCLUDED", "UNAVAILABLE"):
            extra = ""
            if st.get("checks", {}).get("unknown_token_characters"):
                extra = " Characters mapped to the unknown token (occurrences): " + "; ".join(
                    f"{k}: {v}" for k, v in st["checks"]["unknown_token_characters"].items()) + "."
            L.append(f"- **{st['display']}** ({st['status']}): {st['reason'].rstrip('.')}.{extra}")
    runtimes = "; ".join(f"{ad[s['model_key']]['display']}: {ad[s['model_key']]['runtime']}, round-trip "
                         f"{ad[s['model_key']]['checks']['round_trip']}" for s in new.values())
    L += ["", "## Method and limitations\n",
          "- TTR = Σ Arabic tokens / Σ English tokens over the same 100 pairs; the sensitivity column drops "
          "Articles 34, 35 and 108, retained with documented source-alignment limitations.",
          "- Every text passed every guard for each measured tokenizer (no truncation, full character coverage, "
          f"no special or unknown ids, decode round-trip, identical ids on repeat). Runtimes: {runtimes}.",
          "- NFC normalizers (the K2 Horizon tokenizer here; also Qwen2.5 and AceGPT v2) reorder combining marks "
          "in 4 Arabic texts whose published diacritic order is not canonical; the change is canonically "
          "equivalent and is the tokenizer's own behaviour.",
          "- Vocabulary size includes added tokens where the tokenizer defines them.",
          "- Equivalence means identical token ids on these 200 texts; only identical files imply identity on "
          "all inputs.",
          "- Licensing is recorded as declared; where an inherited tokenizer's upstream terms differ from the "
          "model release's declaration, how they apply is not assessed here.",
          "- A failed or unverifiable rerun writes nothing. When a run succeeds, its four files are validated "
          "first and then replaced one at a time, so an interruption between replacements or two overlapping "
          "runs could leave files from different runs; a complete-generation writer is deferred.",
          "- One law, one translation; no statistical significance is claimed for differences between tokenizers.",
          f"- Availability and provenance checked on {CHECKED_ON}."]
    return "\n".join(L) + "\n"
