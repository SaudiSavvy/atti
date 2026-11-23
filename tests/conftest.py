from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
HF = ROOT / "data" / "hf"


@pytest.fixture(scope="session")
def manifest():
    from atti.corpus import read_json

    return read_json(ROOT / "manifest" / "pilot_manifest.json")


@pytest.fixture(scope="session")
def raw_dir():
    from atti import sources

    sources.fetch_all(RAW)  # no-op when cached
    return RAW


@pytest.fixture(scope="session")
def pairs(manifest, raw_dir):
    from atti import corpus

    return corpus.verify(manifest, raw_dir)


@pytest.fixture(scope="session")
def tokenizers_loaded():
    from atti import tokenization

    return [tokenization.load(s, HF) for s in tokenization.TOKENIZERS]
