"""Load pinned tokenizer assets (no model weights) and count content tokens."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from tokenizers import Tokenizer


@dataclass(frozen=True)
class TokenizerSpec:
    repo_id: str
    revision: str  # full commit SHA on the Hugging Face Hub


TOKENIZERS = (
    TokenizerSpec("Qwen/Qwen2.5-3B-Instruct", "aa8e72537993ba99e69dfaafa59ed015b17504d1"),
    TokenizerSpec("mistralai/Mistral-7B-Instruct-v0.3", "c170c708c41dac9275d15a8fff4eca08d52bab71"),
)


@dataclass
class LoadedTokenizer:
    spec: TokenizerSpec
    tokenizer: Tokenizer
    file_sha256: str


def load(spec: TokenizerSpec, cache_dir: Path) -> LoadedTokenizer:
    """Download only ``tokenizer.json`` at the pinned revision (anonymous access)."""
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(
        repo_id=spec.repo_id,
        filename="tokenizer.json",
        revision=spec.revision,
        cache_dir=str(cache_dir),
        token=False,  # no credentials: both repos are publicly downloadable
    )
    data = Path(path).read_bytes()
    tok = Tokenizer.from_str(data.decode("utf-8"))
    tok.no_truncation()
    tok.no_padding()
    return LoadedTokenizer(spec, tok, hashlib.sha256(data).hexdigest())


class TruncationError(RuntimeError):
    pass


def count_tokens(tok: Tokenizer, text: str) -> int:
    """Content-only token count: no BOS/EOS, no chat template, no truncation."""
    if tok.truncation is not None:
        raise TruncationError("truncation must be disabled")
    enc = tok.encode(text, add_special_tokens=False)
    if text and enc.offsets and enc.offsets[-1][1] != len(text):
        raise TruncationError(
            f"encoding covers {enc.offsets[-1][1]} of {len(text)} characters"
        )
    if enc.overflowing:
        raise TruncationError("encoding produced overflowing segments")
    return len(enc.ids)
