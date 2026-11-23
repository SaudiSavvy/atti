"""Token-count integrity checks.

Offline tests use a tiny in-memory tokenizer to prove each guard fires.
``network`` tests apply stricter checks to the two pinned tokenizers on the
real corpus. See README "What the tests prove" for the exact claims.
"""

import unicodedata

import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace

from atti import tokenization
from atti.tokenization import TokenCountError, count_tokens, uncovered_chars


def toy() -> Tokenizer:
    vocab = {"[UNK]": 0, "a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
    tok = Tokenizer(WordLevel(vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()
    return tok


# ---------------------------------------------------------------- offline

def test_revisions_are_pinned_commit_shas():
    for s in tokenization.TOKENIZERS:
        assert len(s.revision) == 40 and all(c in "0123456789abcdef" for c in s.revision)


def test_counts_plain_content():
    assert count_tokens(toy(), "a b c d e") == 5


def test_last_offset_check_was_insufficient_left_truncation():
    """The old guard (last offset == len(text)) passes under left truncation."""
    tok, text = toy(), "a b c d e"
    tok.enable_truncation(max_length=2, direction="left")
    enc = tok.encode(text, add_special_tokens=False)
    assert enc.offsets[-1][1] == len(text)          # old assertion: passes
    assert uncovered_chars(text, enc.offsets) == [0, 2, 4]  # new check: 'a','b','c' dropped
    with pytest.raises(TokenCountError, match="truncation"):
        count_tokens(tok, text)


def test_right_truncation_refused():
    tok = toy()
    tok.enable_truncation(max_length=2)
    with pytest.raises(TokenCountError, match="truncation"):
        count_tokens(tok, "a b c d e")


def test_padding_refused():
    tok = toy()
    tok.enable_padding(length=16)
    with pytest.raises(TokenCountError, match="padding"):
        count_tokens(tok, "a b")


def test_unknown_token_refused():
    with pytest.raises(TokenCountError, match="special/unknown"):
        count_tokens(toy(), "a zzz b")


def test_uncovered_chars_ignores_whitespace_only():
    assert uncovered_chars("a  b", [(0, 1), (3, 4)]) == []
    assert uncovered_chars("ab", [(0, 1)]) == [1]


# ---------------------------------------------------------------- pinned tokenizers

@pytest.mark.network
def test_counts_are_deterministic_across_fresh_loads(pairs, tokenizers_loaded):
    from tests.conftest import HF

    fresh = [tokenization.load(s, HF) for s in tokenization.TOKENIZERS]
    for a, b in zip(tokenizers_loaded, fresh):
        assert a.file_sha256 == b.file_sha256
        for p in pairs:
            for text in (p.ar_text, p.en_text):
                assert count_tokens(a.tokenizer, text) == count_tokens(b.tokenizer, text)


@pytest.mark.network
def test_config_truncation_and_padding_disabled(tokenizers_loaded):
    for lt in tokenizers_loaded:
        assert lt.tokenizer.truncation is None
        assert lt.tokenizer.padding is None


@pytest.mark.network
def test_every_character_covered_including_whitespace(pairs, tokenizers_loaded):
    """Stricter than the runtime guard: no character at all is left uncovered."""
    for lt in tokenizers_loaded:
        for p in pairs:
            for text in (p.ar_text, p.en_text):
                enc = lt.tokenizer.encode(text, add_special_tokens=False)
                covered = set()
                for s, e in enc.offsets:
                    covered.update(range(s, e))
                assert covered == set(range(len(text))), (lt.spec.repo_id, p.article)
                assert not enc.overflowing


@pytest.mark.network
def test_decode_reproduces_normalized_input(pairs, tokenizers_loaded):
    """decode(ids) equals the tokenizer's own normalization of the input.

    Qwen applies NFC, so two Arabic articles whose source text is not in NFC
    (combining-mark order) decode to their NFC form; Mistral has no
    normalizer and must round-trip exactly.
    """
    non_identity = set()
    for lt in tokenizers_loaded:
        norm = lt.tokenizer.normalizer
        for p in pairs:
            for lang, text in (("ar", p.ar_text), ("en", p.en_text)):
                expected = norm.normalize_str(text) if norm else text
                ids = lt.tokenizer.encode(text, add_special_tokens=False).ids
                assert lt.tokenizer.decode(ids, skip_special_tokens=False) == expected
                if expected != text:
                    assert expected == unicodedata.normalize("NFC", text)
                    non_identity.add((lt.spec.repo_id, p.article, lang))
    assert non_identity == {("Qwen/Qwen2.5-3B-Instruct", 65, "ar"), ("Qwen/Qwen2.5-3B-Instruct", 92, "ar")}


@pytest.mark.network
def test_special_tokens_excluded(pairs, tokenizers_loaded):
    for lt in tokenizers_loaded:
        specials = tokenization.special_ids(lt.tokenizer)
        assert specials  # both tokenizers define special tokens
        for p in pairs:
            for text in (p.ar_text, p.en_text):
                assert not set(lt.tokenizer.encode(text, add_special_tokens=False).ids) & specials
    by_repo = {lt.spec.repo_id: lt.tokenizer for lt in tokenizers_loaded}
    text = "Article 1"
    mistral = by_repo["mistralai/Mistral-7B-Instruct-v0.3"]
    with_special = mistral.encode(text, add_special_tokens=True)
    assert with_special.tokens[0] == "<s>"  # the BOS that content-only counting excludes
    assert len(with_special.ids) == count_tokens(mistral, text) + 1
    qwen = by_repo["Qwen/Qwen2.5-3B-Instruct"]
    assert len(qwen.encode(text, add_special_tokens=True).ids) == count_tokens(qwen, text)
