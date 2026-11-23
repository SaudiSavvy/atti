import pytest

from atti import tokenization

pytestmark = pytest.mark.network


def test_revisions_are_pinned_commit_shas():
    for s in tokenization.TOKENIZERS:
        assert len(s.revision) == 40 and all(c in "0123456789abcdef" for c in s.revision)


def test_counts_are_deterministic_across_fresh_loads(pairs, tokenizers_loaded):
    from tests.conftest import HF

    fresh = [tokenization.load(s, HF) for s in tokenization.TOKENIZERS]
    for a, b in zip(tokenizers_loaded, fresh):
        assert a.file_sha256 == b.file_sha256
        for p in pairs:
            for text in (p.ar_text, p.en_text):
                assert tokenization.count_tokens(a.tokenizer, text) == tokenization.count_tokens(b.tokenizer, text)


def test_no_truncation_full_coverage(pairs, tokenizers_loaded):
    for lt in tokenizers_loaded:
        assert lt.tokenizer.truncation is None
        for p in pairs:
            for text in (p.ar_text, p.en_text):
                enc = lt.tokenizer.encode(text, add_special_tokens=False)
                assert enc.offsets[-1][1] == len(text)
                assert not enc.overflowing


def test_special_tokens_excluded(tokenizers_loaded):
    text = "Article 1"
    for lt in tokenizers_loaded:
        content = tokenization.count_tokens(lt.tokenizer, text)
        with_special = len(lt.tokenizer.encode(text, add_special_tokens=True).ids)
        assert content <= with_special
        ids = lt.tokenizer.encode(text, add_special_tokens=False).ids
        special_ids = {i for i, t in lt.tokenizer.get_added_tokens_decoder().items() if t.special}
        assert not set(ids) & special_ids
    mistral = next(lt for lt in tokenizers_loaded if "Mistral" in lt.spec.repo_id)
    assert len(mistral.tokenizer.encode(text, add_special_tokens=True).ids) == \
        tokenization.count_tokens(mistral.tokenizer, text) + 1  # BOS excluded


def test_truncation_is_refused(tokenizers_loaded):
    tok = tokenizers_loaded[0].tokenizer
    tok.enable_truncation(max_length=4)
    try:
        with pytest.raises(tokenization.TruncationError):
            tokenization.count_tokens(tok, "a b c d e f g h")
    finally:
        tok.no_truncation()
