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
    sha256: str  # SHA-256 of tokenizer.json, as recorded in the published summaries


TOKENIZERS = (
    TokenizerSpec("Qwen/Qwen2.5-3B-Instruct", "aa8e72537993ba99e69dfaafa59ed015b17504d1",
                  "c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539"),
    TokenizerSpec("mistralai/Mistral-7B-Instruct-v0.3", "c170c708c41dac9275d15a8fff4eca08d52bab71",
                  "e553af6fff7d7ad76e830608b218c5c0b0822998d5a1a96099a74cd3c1cb1a49"),
)


class TokenizerIntegrityError(RuntimeError):
    """A downloaded or cached tokenizer.json does not match its pinned SHA-256."""


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
    got = hashlib.sha256(data).hexdigest()
    if got != spec.sha256:  # checked before the file is parsed or used for counting
        raise TokenizerIntegrityError(f"{spec.repo_id}@{spec.revision[:12]} tokenizer.json: "
                                      f"SHA-256 {got} != pinned {spec.sha256}")
    tok = Tokenizer.from_str(data.decode("utf-8"))
    tok.no_truncation()
    tok.no_padding()
    return LoadedTokenizer(spec, tok, got)


class TokenCountError(RuntimeError):
    """A content-only count could not be shown to cover the whole input."""


def special_ids(tok: Tokenizer) -> set[int]:
    """Ids of added special tokens plus the model's unknown token, if any."""
    ids = {i for i, t in tok.get_added_tokens_decoder().items() if t.special}
    unk = getattr(tok.model, "unk_token", None)
    if unk is not None and tok.token_to_id(unk) is not None:
        ids.add(tok.token_to_id(unk))
    return ids


def uncovered_chars(text: str, offsets: list[tuple[int, int]]) -> list[int]:
    """Indices of non-whitespace characters not inside any token's offset span.

    Offsets are character spans into the *original* string (tokenizers maps
    them back through normalization). An empty result means every visible
    character is attributed to at least one token, which rules out truncation
    from either end and silently dropped characters in the middle.
    """
    covered = bytearray(len(text))
    for start, end in offsets:
        covered[start:end] = b"\x01" * (end - start)
    return [i for i, c in enumerate(text) if not covered[i] and not c.isspace()]


def checked_encoding(tok: Tokenizer, text: str):
    """Content-only encoding: no BOS/EOS, no chat template, no truncation/padding.

    Raises TokenCountError unless (1) truncation and padding are disabled,
    (2) no overflow segments exist, (3) every non-whitespace input character
    is covered by a token offset span, and (4) no special or unknown token
    appears in the encoding.
    """
    if tok.truncation is not None:
        raise TokenCountError("truncation must be disabled")
    if tok.padding is not None:
        raise TokenCountError("padding must be disabled")
    enc = tok.encode(text, add_special_tokens=False)
    if enc.overflowing:
        raise TokenCountError("encoding produced overflowing segments")
    gaps = uncovered_chars(text, enc.offsets)
    if gaps:
        raise TokenCountError(f"{len(gaps)} characters not covered by any token (first at index {gaps[0]})")
    leaked = set(enc.ids) & special_ids(tok)
    if leaked:
        raise TokenCountError(f"special/unknown token ids in content encoding: {sorted(leaked)}")
    return enc


def count_tokens(tok: Tokenizer, text: str) -> int:
    """Number of tokens in the guarded content-only encoding (see ``checked_encoding``)."""
    return len(checked_encoding(tok, text).ids)
