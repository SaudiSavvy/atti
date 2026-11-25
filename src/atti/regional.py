"""Arabic-focused and Arab-developed tokenizers on the 100 current_law_v2 pairs (``raw_content_tokens``).

Experimental and kept apart from every published artifact: Qwen, Mistral and the frontier results are only
read, and this module writes only its own four files (``OUTPUTS``). Same corpus, texts, whitespace
normalization, metric definitions and special-token policy as the other content-only counts.

* Only tokenizer files are downloaded (allow-listed names at pinned revisions, SHA-256 checked before
  use). No model weights, no inference, no repository code is executed.
* Every text must pass the run-time guards: no truncation, every character covered by a token, no special
  or unknown token, and decode(encode(text)) reproduces the text (up to the tokenizer's own declared
  Unicode normalization or GPT-2 prefix space). A tokenizer that fails on any text is EXCLUDED, not counted.
* A tokenizer whose token ids equal those of another tokenizer on all 200 texts is EQUIVALENT: it is
  reported as a member of that tokenizer's group and never as an independent result.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import statistics
import struct
import unicodedata
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from tokenizers import Tokenizer, models

from atti import frontier as F
from atti import tokenization

ADAPTER_VERSION = "1.0"
ASSET_ALLOWLIST = {"tokenizer.json", "tokenizer.model", "tokenizer_config.json"}
HF_CACHE = Path("data") / "hf_regional"
CHECKED_ON = "2026-11-26"  # Hub availability and provenance checks (repository metadata and model cards)
SENSITIVITY_EXCLUDED = ("34", "35", "108")  # pairs retained with documented source-alignment limitations
ENGLISH_FLAG = 1.5  # flag a tokenizer whose English tokens per 1,000 characters exceed 1.5x the median
STATUSES = ("MEASURED", "EQUIVALENT", "EXCLUDED", "UNAVAILABLE", "BLOCKED")
OUTPUTS = {
    "csv": Path("results") / f"{F.CORPUS}_regional.csv",
    "summary": Path("results") / f"{F.CORPUS}_regional_summary.json",
    "report": Path("reports") / f"{F.CORPUS}_regional.md",
    "manifest": Path("manifest") / "regional_tokenizers.json",
}


@dataclass(frozen=True)
class RegionalSpec(F.LocalSpec):
    country: str = ""
    developers: str = ""
    license: str = ""
    tokenizer_type: str = ""


ALLAM = RegionalSpec(
    "allam-7b-instruct-preview", "ALLaM 7B Instruct (preview)", "humain-ai/ALLaM-7B-Instruct-preview",
    "a28dd1e67420cde72d3629c8633a974cf7d9c366", "spm_bpe",
    {"tokenizer.model": "feff3deb3537c4a47b77585053ad2aa00484da7907b188e0111cbed1f4592e67",
     "tokenizer_config.json": "37bcb27b4b135353488e79314ceb16182049265c95790e6586b2afeb62e40093"},
    "The repository ships only a SentencePiece tokenizer.model (no tokenizer.json at any of its 33 commits); "
    "this revision is the 'version 2' tokenizer. It is a BPE model (64,000 pieces, identity normalization, "
    "byte fallback, dummy prefix, digits as user-defined symbols). ATTI reads the model file with a "
    "standard-library protobuf reader and encodes in SentencePiece order (normalize once, split user-defined "
    "symbols, BPE with byte fallback). tokenizer_config.json: add_bos_token=false, add_eos_token=false.",
    country="Saudi Arabia",
    developers="National Center for Artificial Intelligence (NCAI), Saudi Data and AI Authority (SDAIA); "
               "repository now hosted by the humain-ai organization",
    license="apache-2.0 (Hub metadata; the model card refers to a LICENSE file that is not in the repository)",
    tokenizer_type="SentencePiece BPE")
JAIS3 = RegionalSpec(
    "jais-3-375b-a23b", "Jais 3 375B-A23B", "inception42/Jais-3-375B-A23B",
    "f51d0a4dd93ed0d5cbb9ed58749aa519bd091bc9", "tokenizers",
    {"tokenizer.json": "2fa69519ff1ee3ee55ac50927b00058e88b9eb90802fabaf3c6b05804601c53b",
     "tokenizer_config.json": "581375b2ce8d56d59f609f08a7165365ac53b6543f3442ef0117b4951b0d747c"},
    "Released tokenizer.json (byte-level BPE, 250,000 base tokens + 624 added; NFC normalizer; the "
    "TemplateProcessing post-processor adds a begin-of-text token only when special tokens are requested, "
    "which content-only counts never do). tokenizer_class PreTrainedTokenizerFast; the repository's custom "
    "code is model configuration only and is not used.",
    country="United Arab Emirates",
    developers="Team IFM (Institute of Foundation Models, MBZUAI) per the model card citation; repository "
               "hosted by the inception42 organization",
    license="apache-2.0", tokenizer_type="byte-level BPE")
K2_HORIZON = RegionalSpec(
    "k2-horizon-375b-a23b", "K2 Horizon 375B-A23B", "IFM/K2-Horizon-375B-A23B",
    "7a17b47a74b9371e71ed64b4080192e01caa6174", "tokenizers",
    {"tokenizer.json": "2fa69519ff1ee3ee55ac50927b00058e88b9eb90802fabaf3c6b05804601c53b",
     "tokenizer_config.json": "581375b2ce8d56d59f609f08a7165365ac53b6543f3442ef0117b4951b0d747c"},
    "Released tokenizer.json; byte-identical to Jais 3's (same SHA-256 for tokenizer.json and "
    "tokenizer_config.json).",
    country="United Arab Emirates", developers="IFM (Institute of Foundation Models, MBZUAI)",
    license="apache-2.0", tokenizer_type="byte-level BPE")
FANAR2 = RegionalSpec(
    "fanar-2-27b-instruct", "Fanar 2 27B Instruct", "QCRI/Fanar-2-27B-Instruct",
    "074005040e9c3511b1c43b4298bef09908285534", "tokenizers",
    {"tokenizer.json": "4667f2089529e8e7657cfb6d1c19910ae71ff5f28aa7ab2ff2763330affad795",
     "tokenizer_config.json": "40131233b6e76727588476460cb61fda8d6bfa0e85d1d303bcbce405c4a0fc5d"},
    "Continually pretrained from google/gemma-3-27b-pt. Its tokenizer.json has the same SHA-256 as "
    "google/gemma-3-27b-it@005ad3404e59d6023443cb575daa05336842228a, and its tokenizer.model (SHA-256 "
    "1299c11d7cf632ef3b4e11937501358ada021bbdf7c47638d13c0ee982f2e79c) equals that of gemma-3-27b-pt@"
    "9fe3c4ebc93fbadb14913801536d022054ef11cc and gemma-3-27b-it (Hub file metadata; the Gemma repositories "
    "are gated and were not downloaded). The tokenizer is therefore Google's Gemma 3 tokenizer, unchanged. "
    "SentencePiece-style BPE with byte fallback; the post-processor's <bos> is added only on request.",
    country="Qatar",
    developers="Qatar Computing Research Institute (QCRI), Hamad Bin Khalifa University; sponsored by the "
               "Ministry of Communications and Information Technology, State of Qatar. Tokenizer: Google "
               "(Gemma 3), unchanged",
    license="apache-2.0", tokenizer_type="SentencePiece-style BPE (byte fallback)")
ARAGPT2 = RegionalSpec(
    "aragpt2-mega", "AraGPT2 Mega", "aubmindlab/aragpt2-mega",
    "0c129c98931a9d888080c83c410ec67960ea4dff", "tokenizers",
    {"tokenizer.json": "a27c1fb8a2e7cc78c346f6bc21fb114353188930c499f670cbb6ffe75e549d91"},
    "Released tokenizer.json (GPT-2 byte-level BPE, 64,000 tokens, add_prefix_space=true; no "
    "tokenizer_config.json in the repository). The model card asks that input first be passed through the "
    "arabert ArabertPreprocessor; ATTI applies no preprocessing beyond its whitespace normalization, so "
    "counts are for the text as published. The repository's custom code is model code only and is not used.",
    country="Lebanon", developers="AUB MIND Lab, American University of Beirut",
    license="other: custom AraGPT2 software license (aub-mind/arabert)", tokenizer_type="byte-level BPE (GPT-2)")
ACEGPT2 = RegionalSpec(
    "acegpt-v2-32b", "AceGPT v2 32B", "FreedomIntelligence/AceGPT-v2-32B",
    "d07e8ea20b3cb0ccab624615b5e0d5e2da9a1378", "tokenizers",
    {"tokenizer.json": "f7c9b2dba4a296b1aa76c16a34b8225c0c118978400d4bb66bff0902d702f5b8",
     "tokenizer_config.json": "6a4a43e8a7c68a7aa377bca6dcd8df1da42fcb79eca8162eb9f7b817ea75db16"},
    "Developed from Qwen1.5-32B (model card). Its tokenizer.json is the same git blob as "
    "Qwen/Qwen1.5-32B@cefef80dc06a65f89d1d71d0adbc56d335ca2490, and its vocab.json equals Qwen2.5's.",
    country="Saudi Arabia and China (collaboration)",
    developers="KAUST and King Abdulaziz University (Saudi Arabia) with The Chinese University of Hong Kong, "
               "Shenzhen and the Shenzhen Research Institute of Big Data (China); tokenizer from Qwen1.5 "
               "(Alibaba), unchanged",
    license="apache-2.0", tokenizer_type="byte-level BPE")
ARABIANGPT2 = RegionalSpec(
    "arabiangpt-08b-v2", "ArabianGPT 0.8B V2", "riotu-lab/ArabianGPT-08B-V2",
    "97d86d8de4ee494184d25f3e2822ae7a8cf7efe7", "tokenizers",
    {"tokenizer.json": "5a5a774b76cec6111ff2a452bc56dfe2f788e0a7a89fe67028ea81b05153ba58",
     "tokenizer_config.json": "7979d8c7b8d8a9a43daae399968457a61361df9c3d05947dcc3d1227f10b4253"},
    "Released tokenizer.json ('Aranizer 64K': Metaspace BPE, NFKC normalizer, <unk> without byte fallback).",
    country="Saudi Arabia", developers="Robotics and Internet-of-Things Lab (RIOTU), Prince Sultan University",
    license="apache-2.0", tokenizer_type="Metaspace BPE (no byte fallback)")

SPECS = (ALLAM, JAIS3, K2_HORIZON, FANAR2, ARAGPT2, ACEGPT2, ARABIANGPT2)  # order decides group representatives

UNAVAILABLE = {
    "falcon-h1-arabic": {
        "key": "falcon-h1-arabic", "display": "Falcon-H1 Arabic 34B", "country": "United Arab Emirates",
        "developers": "Technology Innovation Institute (TII), Abu Dhabi", "status": "UNAVAILABLE",
        "measurement_method": F.RAW_CONTENT,
        "reason": "No public tokenizer: no Falcon-H1 Arabic repository exists on the Hugging Face Hub (searches "
                  "for Falcon-H1-Arabic, Falcon-Arabic and falcon-h1-ar, by author tiiuae and Hub-wide), and the "
                  "official announcement (huggingface.co/blog/tiiuae/falcon-h1-arabic) and product page "
                  "(falconllm.tii.ae/falcon-h1-arabic.html) link only a chat interface. Neither states that it "
                  "uses the standard Falcon-H1 tokenizer, so that tokenizer is not substituted.",
        "checked_on": CHECKED_ON},
}


# ----------------------------------------------------------------------------- SentencePiece BPE (ALLaM)

_NORMAL, _UNKNOWN, _CONTROL, _USER, _BYTE = 1, 2, 3, 4, 6


def _varint(b: bytes, i: int) -> tuple[int, int]:
    r = s = 0
    while True:
        c = b[i]
        i += 1
        r |= (c & 0x7F) << s
        s += 7
        if c < 0x80:
            return r, i


def _fields(buf: bytes):
    i = 0
    while i < len(buf):
        key, i = _varint(buf, i)
        num, wire = key >> 3, key & 7
        if wire == 0:
            v, i = _varint(buf, i)
        elif wire == 2:
            n, i = _varint(buf, i)
            v, i = bytes(buf[i:i + n]), i + n
        elif wire == 5:
            v, i = struct.unpack("<f", buf[i:i + 4])[0], i + 4
        elif wire == 1:
            v, i = bytes(buf[i:i + 8]), i + 8
        else:
            raise F.AssetIntegrityError(f"unsupported protobuf wire type {wire}")
        yield num, v


def parse_spm(data: bytes) -> dict:
    """The fields of a SentencePiece ModelProto that encoding depends on (field numbers from
    sentencepiece_model.proto: pieces=1 {piece=1, score=2, type=3}; trainer_spec=2 {model_type=3,
    byte_fallback=35, unk_id=40}; normalizer_spec=3 {name=1, precompiled_charsmap=2, add_dummy_prefix=3,
    remove_extra_whitespaces=4, escape_whitespaces=5})."""
    pieces, trainer, norm = [], {}, {}
    for num, v in _fields(data):
        if num == 1:
            f = dict(_fields(v))
            pieces.append((f[1].decode("utf-8"), f.get(2, 0.0), f.get(3, _NORMAL)))
        elif num == 2:
            trainer = dict(_fields(v))
        elif num == 3:
            norm = dict(_fields(v))
    return {"pieces": pieces, "model_type": trainer.get(3, 1), "byte_fallback": bool(trainer.get(35, 0)),
            "unk_id": trainer.get(40, 0), "normalizer": norm.get(1, b"").decode("utf-8"),
            "charsmap": norm.get(2, b""), "add_dummy_prefix": bool(norm.get(3, 1)),
            "remove_extra_whitespaces": bool(norm.get(4, 1)), "escape_whitespaces": bool(norm.get(5, 1))}


class SentencePieceBpeCounter:
    """SentencePiece BPE in SentencePiece's encode order: the whole text is normalized once (dummy prefix,
    space -> U+2581), user-defined symbols are split out by longest match, and each remaining span is
    BPE-encoded with byte fallback. Merge priority is the score of the merged piece, as in SentencePiece.
    Only the configuration below is supported; anything else is refused."""

    def __init__(self, spec: RegionalSpec, model_file: Path):
        m = parse_spm(model_file.read_bytes())
        if (m["model_type"] != 2 or m["normalizer"] != "identity" or m["charsmap"] or m["remove_extra_whitespaces"]
                or not m["escape_whitespaces"] or not m["add_dummy_prefix"] or not m["byte_fallback"]):
            raise F.AssetIntegrityError(f"{spec.repo_id}: unsupported SentencePiece configuration")
        self.spec = spec
        self.pieces = [p for p, _, _ in m["pieces"]]
        vocab = {p: i for i, p in enumerate(self.pieces)}
        score = {p: s for p, s, _ in m["pieces"]}
        merges = sorted((-score[p], vocab[p[:k]], vocab[p[k:]], p[:k], p[k:])
                        for p, _, t in m["pieces"] if t == _NORMAL
                        for k in range(1, len(p)) if p[:k] in vocab and p[k:] in vocab)
        self.model = models.BPE(vocab=vocab, merges=[(a, b) for *_, a, b in merges],
                                unk_token=self.pieces[m["unk_id"]], fuse_unk=True, byte_fallback=True)
        self.user = sorted((p for p, _, t in m["pieces"] if t == _USER), key=len, reverse=True)
        self.vocab = vocab
        self.special = {i for i, (_, _, t) in enumerate(m["pieces"]) if t in (_UNKNOWN, _CONTROL)}
        self.vocab_size = len(self.pieces)

    def encode(self, text: str) -> tuple[list[int], list[tuple[int, int]]]:
        """Token ids and their character spans in `text`."""
        if not text:
            return [], []
        norm = "▁" + text.replace(" ", "▁")  # position j >= 1 is text[j - 1]
        ids, offsets = [], []

        def bpe(a: int, b: int):
            for t in self.model.tokenize(norm[a:b]):
                s, e = t.offsets
                ids.append(t.id)
                offsets.append((max(a + s - 1, 0), max(a + e - 1, 0)))

        i = start = 0
        while i < len(norm):
            hit = next((u for u in self.user if norm.startswith(u, i)), None)
            if hit is None:
                i += 1
                continue
            if start < i:
                bpe(start, i)
            ids.append(self.vocab[hit])
            offsets.append((i - 1, i - 1 + len(hit)))
            i = start = i + len(hit)
        if start < len(norm):
            bpe(start, len(norm))
        return ids, offsets

    def decode(self, ids: list[int]) -> str:
        out = bytearray()
        for i in ids:
            p = self.pieces[i]
            if len(p) == 6 and p.startswith("<0x") and p.endswith(">"):
                out.append(int(p[3:5], 16))
            else:
                out += p.replace("▁", " ").encode("utf-8")
        s = out.decode("utf-8", errors="replace")
        return s[1:] if s.startswith(" ") else s

    def ids(self, text: str) -> list[int]:
        ids, offsets = self.encode(text)
        gaps = tokenization.uncovered_chars(text, offsets)
        if gaps:
            raise tokenization.TokenCountError(f"{len(gaps)} characters not covered by any token "
                                               f"(first at index {gaps[0]})")
        leaked = set(ids) & self.special
        if leaked:
            raise tokenization.TokenCountError(f"special/unknown token ids in content encoding: {sorted(leaked)}")
        if self.decode(ids) != text:
            raise F.FrontierError(f"{self.spec.key}: decode(encode(text)) != text")
        return ids

    def count(self, text: str) -> int:
        return len(self.ids(text))


# ----------------------------------------------------------------------------- tokenizer.json

_NORMALIZERS = {None: None, "NFC": "NFC", "NFKC": "NFKC"}
_METASPACE_REPLACE = {"type": "Replace", "pattern": {"String": " "}, "content": "▁"}


class TokenizerJsonCounter:
    """A released tokenizer.json on the `tokenizers` runtime. decode(encode(text)) must reproduce the text,
    allowing only what the tokenizer itself declares: an NFC/NFKC normalizer (the decode then equals the
    normalized text) and a GPT-2 ByteLevel prefix space."""

    def __init__(self, spec: RegionalSpec, tokenizer_json: Path):
        raw = tokenizer_json.read_text(encoding="utf-8")
        data = json.loads(raw)
        norm = data.get("normalizer")
        if norm == _METASPACE_REPLACE:
            self.form = None
        elif norm is None or set(norm) == {"type"} and norm["type"] in _NORMALIZERS:
            self.form = _NORMALIZERS[norm and norm["type"]]
        else:
            raise F.AssetIntegrityError(f"{spec.repo_id}: unsupported normalizer {json.dumps(norm)[:80]}")
        pre = data.get("pre_tokenizer") or {}
        steps = pre.get("pretokenizers", [pre])
        self.prefix_space = any(p.get("type") == "ByteLevel" and p.get("add_prefix_space") for p in steps)
        self.spec = spec
        self.tok = Tokenizer.from_str(raw)
        self.tok.no_truncation()
        self.tok.no_padding()
        self.vocab_size = self.tok.get_vocab_size(with_added_tokens=True)

    def expected(self, text: str) -> str:
        return unicodedata.normalize(self.form, text) if self.form else text

    def ids(self, text: str) -> list[int]:
        tokenization.count_tokens(self.tok, text)  # truncation/overflow/coverage/special/unknown guards
        ids = self.tok.encode(text, add_special_tokens=False).ids
        out, want = self.tok.decode(ids, skip_special_tokens=False), self.expected(text)
        if out != want and not (self.prefix_space and out == " " + want):
            raise F.FrontierError(f"{self.spec.key}: decode(encode(text)) != text")
        return ids

    def count(self, text: str) -> int:
        return len(self.ids(text))


def load(spec: RegionalSpec, cache_dir: Path, paths: dict | None = None):
    paths = paths or F.fetch_assets(spec, cache_dir, ASSET_ALLOWLIST)
    if spec.kind == "spm_bpe":
        return SentencePieceBpeCounter(spec, paths["tokenizer.model"])
    if spec.kind == "tokenizers":
        return TokenizerJsonCounter(spec, paths["tokenizer.json"])
    raise F.FrontierError(f"unknown adapter kind {spec.kind}")


def unknown_chars(counter, text: str) -> list[str]:
    """Characters a tokenizer.json maps to its unknown token (evidence for an exclusion)."""
    if not isinstance(counter, TokenizerJsonCounter):
        return []
    unk = getattr(counter.tok.model, "unk_token", None)
    uid = counter.tok.token_to_id(unk) if unk else None
    enc = counter.tok.encode(text, add_special_tokens=False)
    return [text[s:e] for i, (s, e) in zip(enc.ids, enc.offsets) if i == uid]


# ----------------------------------------------------------------------------- run

def ids_digest(id_lists) -> str:
    """SHA-256 over the token ids of every text, in corpus order (Arabic then English per article)."""
    return hashlib.sha256(json.dumps(list(id_lists), separators=(",", ":")).encode()).hexdigest()


def reference_digests(root: Path, texts: list[str]) -> dict[str, str]:
    """Token-id digests of the tokenizers already in ATTI's content-only results (loaded read-only)."""
    out = {}
    for t in tokenization.TOKENIZERS:
        lt = tokenization.load(t, root / "data" / "hf")
        out[t.repo_id] = ids_digest(lt.tokenizer.encode(x, add_special_tokens=False).ids for x in texts)
    for s in F.LOCAL:
        c = F.load_local(s, root / F.HF_CACHE)
        out[s.repo_id] = ids_digest(c.ids(x) for x in texts)
    return out


def run(root: Path) -> dict:
    from atti import v2

    manifest = json.loads((root / v2.MANIFEST_PATH).read_text(encoding="utf-8"))
    records = v2.verify(manifest, root / v2.RAW)
    keys = [a["key"] for a in manifest["articles"]]
    if len(keys) != 100 or len(set(keys)) != 100 or [r.key for r in records] != keys:
        raise F.FrontierError("the corpus must be exactly the 100 current_law_v2 pairs")
    texts = [t for r in records for t in (r.ar_text, r.en_text)]
    refs = reference_digests(root, texts)
    status, rows, measured = {}, [], {}
    for spec in SPECS:
        st = {"key": spec.key, "display": spec.display, "repo_id": spec.repo_id, "revision": spec.revision,
              "country": spec.country, "developers": spec.developers, "license": spec.license,
              "tokenizer_type": spec.tokenizer_type, "adapter": spec.kind, "measurement_method": spec.method,
              "source_note": spec.source_note, "status": "BLOCKED"}
        try:
            paths = F.fetch_assets(spec, root / HF_CACHE, ASSET_ALLOWLIST)
            st["assets"] = {n: {"sha256": d, "bytes": paths[n].stat().st_size} for n, d in spec.assets.items()}
            counter = load(spec, root / HF_CACHE, paths)
        except (F.FrontierError, tokenization.TokenizerIntegrityError) as exc:
            st["blocked_reason"] = str(exc)
            status[spec.key] = st
            continue
        st["vocab_size"] = counter.vocab_size
        st["checks"] = check(counter, records)
        if st["checks"]["failed_texts"]:
            st["status"] = "EXCLUDED"
            st["reason"] = ("cannot represent every corpus text faithfully: "
                            + "; ".join(f"{k}: {v}" for k, v in st["checks"]["failures"].items()))
            status[spec.key] = st
            continue
        digest = st["checks"]["ids_sha256"]
        same = next((r for r, d in refs.items() if d == digest), None) or \
            next((k for k, d in measured.items() if d == digest), None)
        if same is not None:
            st.update(status="EQUIVALENT", equivalent_to=same,
                      evidence="token ids identical on all 200 corpus texts (same ids_sha256)")
        else:
            meta = f"{spec.repo_id}@{spec.revision[:12]}; " + ", ".join(
                f"{n} sha256 {d[:12]}" for n, d in spec.assets.items())
            new = F.measure_rows(spec, counter, records, manifest, meta)
            for r in new:
                r["adapter_version"] = ADAPTER_VERSION
            rows += new
            measured[spec.key] = digest
            st["status"] = "MEASURED"
        status[spec.key] = st
    status.update(UNAVAILABLE)
    outputs = build_outputs(root, manifest, rows, status, refs)
    F.publish(root, OUTPUTS, outputs, manifest)  # validates; never drops, changes or downgrades published results
    return status


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
                    raise F.FrontierError("non-deterministic encoding")
            except (tokenization.TokenCountError, F.FrontierError) as exc:
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
        rows += [r for r in csv.DictReader(f) if r["measurement_method"] == F.RAW_CONTENT]
    return {m: [r for r in rows if r["model"] == m] for m in dict.fromkeys(r["model"] for r in rows)}


REFERENCE_DISPLAY = {"Qwen/Qwen2.5-3B-Instruct": "Qwen2.5-3B-Instruct",
                     "mistralai/Mistral-7B-Instruct-v0.3": "Mistral-7B-Instruct-v0.3",
                     **{s.repo_id: s.display for s in F.LOCAL}}


def _stats(rows: list[dict]) -> dict:
    s = F.model_summary(rows)
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
            raise F.FrontierError(f"{m}: published rows do not reproduce the published summary")
        reference[m] = {"display": REFERENCE_DISPLAY[m], "source": "existing ATTI results (read only)",
                        "ids_sha256": refs[m], **s}
    ref = {"qwen": "Qwen/Qwen2.5-3B-Instruct", "mistral": "mistralai/Mistral-7B-Instruct-v0.3"}
    models = {}
    for k in dict.fromkeys(r["model_key"] for r in rows):
        sel = [r for r in rows if r["model_key"] == k]
        st = status[k]
        s = _stats(sel)
        s["ttr_pct_diff_vs"] = {n: (s["ttr"] / reference[m]["ttr"] - 1) * 100 for n, m in ref.items()}
        models[sel[0]["model"]] = {"display": st["display"], "model_key": k, "country": st["country"],
                                   "source": str(OUTPUTS["csv"]), **s}
    en_median = statistics.median(s["en_tokens_per_1000_chars"] for s in (*reference.values(), *models.values()))
    for s in models.values():
        s["en_tokens_per_1000_chars_vs_median"] = s["en_tokens_per_1000_chars"] / en_median
        if s["en_tokens_per_1000_chars_vs_median"] > ENGLISH_FLAG:
            s["flag"] = (f"English costs {s['en_tokens_per_1000_chars_vs_median']:.2f}x the median tokens per "
                         "character, so its TTR below 1 reflects inefficient English, not efficient Arabic")
    groups = equivalence_groups(status, reference)
    summary = {"corpus": F.CORPUS, "status": "PROVISIONAL", "measurement_method": F.RAW_CONTENT,
               "articles": [a["key"] for a in manifest["articles"]],
               "sensitivity_excluded_articles": list(SENSITIVITY_EXCLUDED),
               "models": models, "reference_models": reference, "equivalence_groups": groups}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=F.CSV_FIELDS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    fm = {"corpus": F.CORPUS, "corpus_manifest": "manifest/current_law_v2_manifest.json",
          "corpus_status": manifest["status"], "adapter_version": ADAPTER_VERSION, "checked_on": CHECKED_ON,
          "measurement_method": F.RAW_CONTENT,
          "status_definitions": {
              "MEASURED": "all 100 pairs measured in both languages; every guard held on all 200 texts",
              "EQUIVALENT": "token ids identical to another tokenizer's on all 200 texts; reported only as a "
                            "member of that tokenizer's group, never as an independent result",
              "EXCLUDED": "at least one corpus text cannot be represented faithfully; no value published",
              "UNAVAILABLE": "no public tokenizer could be verified; nothing substituted",
              "BLOCKED": "the pinned assets could not be obtained or loaded; no value published"},
          "asset_policy": "allow-listed tokenizer files only (" + ", ".join(sorted(ASSET_ALLOWLIST)) + ") at "
                          "pinned revisions, SHA-256 checked before use; no weights; no repository code run",
          "official_crosscheck": OFFICIAL_CROSSCHECK, "adapters": status}
    return {"csv": buf.getvalue(), "summary": F.dumps(summary), "manifest": F.dumps(fm),
            "report": render_report(summary, fm)}


OFFICIAL_CROSSCHECK = {
    "date": CHECKED_ON,
    "allam": "token ids identical to the official sentencepiece 0.2.1 SentencePieceProcessor.encode on all 200 "
             "corpus texts and 15 synthetic edge cases (leading digits, Arabic-Indic digits, repeated, leading "
             "and trailing spaces, byte-fallback characters); run in an isolated environment, not a dependency",
    "fanar_2": "tokenizer.json ids identical to the official sentencepiece 0.2.1 encoding with the repository's "
               "own tokenizer.model on the same 215 texts",
    "others": "tokenizer.json is the released artifact and `tokenizers` its declared runtime",
    "fixture": "tests/regional_reference_ids.json (synthetic, non-legal strings)",
}


def equivalence_groups(status: dict, reference: dict) -> list[dict]:
    groups = {}
    for st in status.values():
        if st["status"] == "EQUIVALENT":
            rep = st["equivalent_to"]
            g = groups.setdefault(rep, {"representative": rep, "display": reference[rep]["display"] if rep in
                                        reference else status[rep]["display"], "members": []})
            g["members"].append(st["key"])
    return list(groups.values())


def render_report(summary: dict, fm: dict) -> str:
    ad, new, refm = fm["adapters"], summary["models"], summary["reference_models"]
    member_of = {g["representative"]: g for g in summary["equivalence_groups"]}

    def label(display: str, key: str) -> str:
        g = member_of.get(key)
        return display + (" = " + ", ".join(ad[m]["display"] for m in g["members"]) if g else "")

    table = [(label(s["display"], s["model_key"]), s["country"], "new", s) for s in new.values()]
    table += [(label(s["display"], m), "—", "existing", s) for m, s in refm.items()]
    L = [f"# ATTI {F.CORPUS}: Arabic-focused and Arab-developed tokenizers ({len(summary['articles'])} pairs)\n",
         "> **PROVISIONAL corpus, experimental results.** No pair is human-approved. Same 100 pairs, texts, "
         "whitespace normalization, metrics and special-token policy as the existing content-only results, "
         "which are read unchanged.\n",
         "Tokenizer measurements of input text only (`raw_content_tokens`): no special tokens, no chat template, "
         "no truncation. Not model quality, speed, output length or pricing. Provider API counts "
         "(`api_input_tokens`) are a different method and are not included here.\n",
         "## Ranked results (`raw_content_tokens`)\n",
         "Token tax = (TTR − 1) × 100. Ratio columns are Arabic ÷ English; Median, Min and Max are over "
         "per-article ratios. Each row is one distinct tokenizer; equivalent tokenizers are listed after `=`.\n",
         "| # | Tokenizer | Country | Set | Σ AR | Σ EN | **TTR** | Token tax | Median | Min | Max | "
         "TTR without 34, 35, 108 |", "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for i, (name, country, kind, s) in enumerate(sorted(table, key=lambda x: x[3]["ttr"]), 1):
        name += " ⚠" if s.get("flag") else ""
        L.append(f"| {i} | {name} | {country} | {kind} | {s['ar_tokens_total']:,} | {s['en_tokens_total']:,} | "
                 f"**{s['ttr']:.4f}** | {s['token_tax_pct']:+.1f}% | {s['median_article_ratio']:.4f} | "
                 f"{s['min_article_ratio']:.4f} | {s['max_article_ratio']:.4f} | "
                 f"{s['ttr_without_34_35_108']:.4f} |")
    L += [""] + [f"⚠ {s['display']}: {s['flag']}." for s in new.values() if s.get("flag")]
    L += ["", "Per-language efficiency separates the two sides of the ratio:\n",
          "| Tokenizer | Set | AR tok/1k chars | EN tok/1k chars | EN vs median | TTR vs Qwen2.5 | TTR vs Mistral |",
          "|---|---|---:|---:|---:|---:|---:|"]
    for s in sorted(new.values(), key=lambda s: s["ar_tokens_per_1000_chars"]):
        L.append(f"| {s['display']} | new | {s['ar_tokens_per_1000_chars']:.1f} | {s['en_tokens_per_1000_chars']:.1f} | "
                 f"{s['en_tokens_per_1000_chars_vs_median']:.2f}x | {s['ttr_pct_diff_vs']['qwen']:+.1f}% | "
                 f"{s['ttr_pct_diff_vs']['mistral']:+.1f}% |")
    for s in sorted(refm.values(), key=lambda s: s["ar_tokens_per_1000_chars"]):
        L.append(f"| {s['display']} | existing | {s['ar_tokens_per_1000_chars']:.1f} | "
                 f"{s['en_tokens_per_1000_chars']:.1f} | | | |")
    L += ["", "## Tokenizers\n", "| Model | Country | Developers | Repository @ revision | Tokenizer | Vocabulary | "
          "License | Status |", "|---|---|---|---|---|---:|---|---|"]
    for st in ad.values():
        repo = f"`{st['repo_id']}@{st['revision'][:12]}`" if "repo_id" in st else "none"
        L.append(f"| {st['display']} | {st['country']} | {st['developers']} | {repo} | {st.get('tokenizer_type', '')} | "
                 f"{format(st['vocab_size'], ',') if 'vocab_size' in st else ''} | {st.get('license', '')} | **{st['status']}** |")
    L += ["", "Full revisions, asset SHA-256s and source notes: `manifest/regional_tokenizers.json`.", "",
          "## Equivalence groups\n"]
    for g in summary["equivalence_groups"]:
        L.append(f"- **{g['display']}** = " + ", ".join(ad[m]["display"] for m in g["members"])
                 + ": token ids identical on all 200 texts. " + " ".join(ad[m]["source_note"] for m in g["members"]))
    if ad.get("fanar-2-27b-instruct", {}).get("status") == "MEASURED":
        L.append(f"- **{ad['fanar-2-27b-instruct']['display']}** uses Google's Gemma 3 tokenizer unchanged (file "
                 "hashes; see the manifest). Gemma 3 is not otherwise in ATTI, so the row is a distinct tokenizer, "
                 "but it is not an Arab-developed tokenizer.")
    L += ["", "## Excluded and unavailable\n"]
    for st in ad.values():
        if st["status"] in ("EXCLUDED", "UNAVAILABLE", "BLOCKED"):
            why = (st.get("reason") or st.get("blocked_reason")).rstrip(".")
            extra = ""
            if st.get("checks", {}).get("unknown_token_characters"):
                extra = " Characters mapped to the unknown token (occurrences): " + "; ".join(
                    f"{k}: {v}" for k, v in st["checks"]["unknown_token_characters"].items()) + "."
            L.append(f"- **{st['display']}** ({st['status']}): {why}.{extra}")
    L += ["", "## Method and limitations\n",
          "- TTR = Σ Arabic tokens / Σ English tokens over the same 100 pairs; the sensitivity column drops "
          "Articles 34, 35 and 108, retained with documented source-alignment limitations.",
          "- Every text passed every guard for each measured tokenizer (no truncation, full character coverage, "
          "no special or unknown ids, decode round-trip, identical ids on repeat). Round-trip: "
          + "; ".join(f"{ad[s['model_key']]['display']}: {ad[s['model_key']]['checks']['round_trip']}"
                      for s in new.values()) + ".",
          "- NFC normalizers (Jais 3 / K2 Horizon here; also Qwen2.5 and AceGPT v2) reorder combining marks in "
          "4 Arabic texts whose published diacritic order is not canonical; the change is canonically "
          "equivalent and is the tokenizer's own behaviour.",
          "- AraGPT2's documented usage applies the arabert preprocessor first; ATTI does not, so its counts "
          "describe the published text, not the model's training-time input format.",
          f"- ALLaM: {OFFICIAL_CROSSCHECK['allam']}. Fanar 2: {OFFICIAL_CROSSCHECK['fanar_2']}.",
          "- Vocabulary size includes added tokens where the tokenizer defines them.",
          "- Equivalence is functional identity on this corpus (all 200 texts) plus, where noted, identical "
          "files; it is not a proof of identity on all possible inputs.",
          "- One law, one translation; no statistical significance is claimed for differences between tokenizers.",
          f"- Availability and provenance checked on {CHECKED_ON}."]
    return "\n".join(L) + "\n"
