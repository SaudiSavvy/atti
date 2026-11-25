"""Arabic-focused and Arab-developed tokenizers: pins, provenance, equivalence, guards, reproducibility."""

import csv
import json
import re
import shutil
import statistics
import struct
from fractions import Fraction

import pytest

from atti import frontier as F
from atti import regional as R
from atti import tokenization, v2
from tests.conftest import ROOT


# ---------------------------------------------------------------- pins and provenance

def test_specs_pinned_and_tokenizer_files_only():
    assert [s.key for s in R.SPECS] == ["allam-7b-instruct-preview", "jais-3-375b-a23b", "k2-horizon-375b-a23b",
                                        "fanar-2-27b-instruct", "aragpt2-mega", "acegpt-v2-32b", "arabiangpt-08b-v2"]
    for s in R.SPECS:
        assert re.fullmatch(r"[0-9a-f]{40}", s.revision) and s.method == F.RAW_CONTENT
        assert s.assets and all(re.fullmatch(r"[0-9a-f]{64}", d) for d in s.assets.values())
        assert set(s.assets) <= R.ASSET_ALLOWLIST and not any(n.endswith(F.WEIGHT_SUFFIXES) for n in s.assets)
        assert s.country and s.developers and s.license and s.tokenizer_type
    assert R.ASSET_ALLOWLIST == {"tokenizer.json", "tokenizer.model", "tokenizer_config.json"}


def test_existing_pins_untouched_and_disjoint():
    assert [(t.repo_id, t.revision, t.sha256) for t in tokenization.TOKENIZERS] == [
        ("Qwen/Qwen2.5-3B-Instruct", "aa8e72537993ba99e69dfaafa59ed015b17504d1",
         "c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539"),
        ("mistralai/Mistral-7B-Instruct-v0.3", "c170c708c41dac9275d15a8fff4eca08d52bab71",
         "e553af6fff7d7ad76e830608b218c5c0b0822998d5a1a96099a74cd3c1cb1a49")]
    assert F.ASSET_ALLOWLIST == {"tokenizer.json", "tiktoken.model", "tokenizer_config.json"}
    existing = {t.repo_id for t in tokenization.TOKENIZERS} | {s.repo_id for s in F.LOCAL}
    assert not existing & {s.repo_id for s in R.SPECS}
    assert not {s.key for s in F.ALL} & {s.key for s in R.SPECS}


def test_jais3_and_k2_horizon_ship_the_same_files():
    assert R.JAIS3.assets == R.K2_HORIZON.assets


def test_falcon_h1_arabic_not_substituted():
    assert R.UNAVAILABLE["falcon-h1-arabic"]["status"] == "UNAVAILABLE"
    assert not any(s.repo_id.startswith("tiiuae/") for s in R.SPECS)


def test_outputs_separate_from_published_artifacts():
    published = set(json.loads((ROOT / "tests" / "historical_sha256.json").read_text()))
    published |= {str(p) for p in (*F.OUTPUTS.values(), *v2.OUTPUTS.values())}
    from atti import gemini
    published |= {str(p) for p in gemini.OUTPUTS.values()}
    assert not {str(p) for p in R.OUTPUTS.values()} & published
    assert all("regional" in str(p) for p in R.OUTPUTS.values())


def test_weight_and_unlisted_assets_refused(tmp_path, monkeypatch):
    bad = R.RegionalSpec("x", "x", "a/b", "0" * 40, "tokenizers", {"model.safetensors": "0" * 64}, "")
    with pytest.raises(F.AssetIntegrityError, match="allow-listed"):
        F.fetch_assets(bad, tmp_path, R.ASSET_ALLOWLIST)
    fake = tmp_path / "tokenizer.model"
    fake.write_bytes(b"not the pinned file")
    monkeypatch.setattr("huggingface_hub.hf_hub_download", lambda *a, **k: str(fake))
    with pytest.raises(F.AssetIntegrityError, match="SHA-256"):
        R.load(R.ALLAM, tmp_path)


# ---------------------------------------------------------------- SentencePiece reader (synthetic model)

def _pb(num, wire, payload):
    def varint(n):
        out = bytearray()
        while True:
            b, n = n & 0x7F, n >> 7
            out.append(b | (0x80 if n else 0))
            if not n:
                return bytes(out)
    key = varint(num << 3 | wire)
    if wire == 0:
        return key + varint(payload)
    if wire == 5:
        return key + struct.pack("<f", payload)
    return key + varint(len(payload)) + payload


def _spm_model(tmp_path, **norm):
    pieces = [("<unk>", 0.0, 2), ("<s>", 0.0, 3), ("</s>", 0.0, 3), ("1", 0.0, 4)]
    pieces += [(f"<0x{b:02X}>", 0.0, 6) for b in range(256)]
    pieces += [("▁", -1.0, 1), ("a", -2.0, 1), ("b", -3.0, 1), ("▁a", -4.0, 1), ("▁ab", -5.0, 1)]
    body = b"".join(_pb(1, 2, _pb(1, 2, p.encode()) + _pb(2, 5, s) + _pb(3, 0, t)) for p, s, t in pieces)
    body += _pb(2, 2, _pb(3, 0, 2) + _pb(35, 0, 1) + _pb(40, 0, 0))
    ns = {"name": "identity", "remove_extra_whitespaces": 0, **norm}
    body += _pb(3, 2, _pb(1, 2, ns["name"].encode()) + _pb(4, 0, ns["remove_extra_whitespaces"]))
    path = tmp_path / "tokenizer.model"
    path.write_bytes(body)
    return path


def test_spm_reader_normalizes_once_and_splits_user_symbols(tmp_path):
    c = R.SentencePieceBpeCounter(R.ALLAM, _spm_model(tmp_path))
    piece = lambda text: [c.pieces[i] for i in c.encode(text)[0]]  # noqa: E731
    assert piece("ab") == ["▁ab"]
    assert piece("1 ab") == ["▁", "1", "▁ab"]  # dummy prefix before a leading user symbol
    assert piece("a1 ab") == ["▁a", "1", "▁ab"]  # no second dummy prefix after a user symbol
    assert piece("é") == ["▁", "<0xC3>", "<0xA9>"]  # byte fallback, never <unk>
    assert c.encode("") == ([], [])
    for t in ("1 ab", "a  b", " a", "é a1"):
        assert c.decode(c.ids(t)) == t


def test_spm_reader_refuses_unsupported_configuration(tmp_path):
    with pytest.raises(F.AssetIntegrityError, match="unsupported SentencePiece"):
        R.SentencePieceBpeCounter(R.ALLAM, _spm_model(tmp_path, name="nmt_nfkc"))
    with pytest.raises(F.AssetIntegrityError, match="unsupported SentencePiece"):
        R.SentencePieceBpeCounter(R.ALLAM, _spm_model(tmp_path, remove_extra_whitespaces=1))


def test_tokenizer_json_with_unknown_normalizer_refused(tmp_path):
    p = tmp_path / "tokenizer.json"
    p.write_text(json.dumps({"normalizer": {"type": "Lowercase"}}))
    with pytest.raises(F.AssetIntegrityError, match="normalizer"):
        R.TokenizerJsonCounter(R.JAIS3, p)


# ---------------------------------------------------------------- committed outputs

@pytest.fixture(scope="module")
def outputs():
    with (ROOT / R.OUTPUTS["csv"]).open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return (rows, json.loads((ROOT / R.OUTPUTS["summary"]).read_text()),
            json.loads((ROOT / R.OUTPUTS["manifest"]).read_text()))


def test_statuses_and_no_values_for_unmeasured(outputs):
    rows, summary, fm = outputs
    st = {k: a["status"] for k, a in fm["adapters"].items()}
    assert st == {"allam-7b-instruct-preview": "MEASURED", "jais-3-375b-a23b": "MEASURED",
                  "k2-horizon-375b-a23b": "EQUIVALENT", "fanar-2-27b-instruct": "MEASURED",
                  "aragpt2-mega": "MEASURED", "acegpt-v2-32b": "EQUIVALENT", "arabiangpt-08b-v2": "EXCLUDED",
                  "falcon-h1-arabic": "UNAVAILABLE"}
    assert set(st.values()) <= set(R.STATUSES)
    measured = {k for k, v in st.items() if v == "MEASURED"}
    assert {r["model_key"] for r in rows} == measured == {m["model_key"] for m in summary["models"].values()}
    assert all(r["measurement_method"] == F.RAW_CONTENT for r in rows)
    assert summary["status"] == "PROVISIONAL" and fm["corpus_status"] == "provisional"


def test_equivalence_groups(outputs):
    _, summary, fm = outputs
    groups = {g["representative"]: g["members"] for g in summary["equivalence_groups"]}
    assert groups == {"jais-3-375b-a23b": ["k2-horizon-375b-a23b"], "Qwen/Qwen2.5-3B-Instruct": ["acegpt-v2-32b"]}
    a = fm["adapters"]
    assert a["k2-horizon-375b-a23b"]["checks"]["ids_sha256"] == a["jais-3-375b-a23b"]["checks"]["ids_sha256"]
    assert a["acegpt-v2-32b"]["checks"]["ids_sha256"] == \
        summary["reference_models"]["Qwen/Qwen2.5-3B-Instruct"]["ids_sha256"]
    digests = [a[k]["checks"]["ids_sha256"] for k, v in a.items() if v["status"] == "MEASURED"]
    digests += [m["ids_sha256"] for m in summary["reference_models"].values()]
    assert len(digests) == len(set(digests))  # every reported row is a distinct tokenizer


def test_exclusion_evidence(outputs):
    _, _, fm = outputs
    ex = fm["adapters"]["arabiangpt-08b-v2"]
    assert ex["checks"]["failed_texts"] == 48 and "unknown" in ex["reason"]
    assert "U+064B ARABIC FATHATAN" in ex["checks"]["unknown_token_characters"]
    for k, a in fm["adapters"].items():
        if a["status"] in ("MEASURED", "EQUIVALENT"):
            assert a["checks"]["failed_texts"] == 0 and a["checks"]["texts"] == 200


def test_statistics_and_sensitivity_recompute_exactly(outputs):
    rows, summary, _ = outputs
    keys = [a["key"] for a in json.loads((ROOT / v2.MANIFEST_PATH).read_text())["articles"]]
    for m, s in summary["models"].items():
        sel = [r for r in rows if r["model"] == m]
        assert [r["article"] for r in sel] == keys
        ar, en = [int(r["ar_tokens"]) for r in sel], [int(r["en_tokens"]) for r in sel]
        assert (s["ar_tokens_total"], s["en_tokens_total"]) == (sum(ar), sum(en))
        assert s["ttr"] == float(Fraction(sum(ar), sum(en)))
        assert s["token_tax_pct"] == pytest.approx((s["ttr"] - 1) * 100)
        ratios = [Fraction(a, e) for a, e in zip(ar, en)]
        assert s["median_article_ratio"] == float(statistics.median(ratios))
        assert (s["min_article_ratio"], s["max_article_ratio"]) == (float(min(ratios)), float(max(ratios)))
        keep = [i for i, r in enumerate(sel) if r["article"] not in ("34", "35", "108")]
        assert len(keep) == 97
        assert s["ttr_without_34_35_108"] == float(Fraction(sum(ar[i] for i in keep), sum(en[i] for i in keep)))


def test_reference_models_match_published_results(outputs):
    _, summary, _ = outputs
    published = json.loads((ROOT / F.OUTPUTS["summary"]).read_text())["models"]
    ref = summary["reference_models"]
    assert set(ref) == {m for m, s in published.items() if s["measurement_method"] == F.RAW_CONTENT}
    for m, s in ref.items():
        for f in ("ar_tokens_total", "en_tokens_total", "ttr", "median_article_ratio"):
            assert s[f] == published[m][f]
    # README sensitivity column (rounded to 3 places) is reproduced from the published rows
    readme = {"Qwen/Qwen2.5-3B-Instruct": 1.340, "mistralai/Mistral-7B-Instruct-v0.3": 3.022,
              "deepseek-ai/DeepSeek-V4.1-Flash-1017": 1.334, "zai-org/GLM-5.3-Flash": 1.454,
              "moonshotai/Kimi-K3.1-Pro": 1.730}
    assert {m: round(s["ttr_without_34_35_108"], 3) for m, s in ref.items()} == readme


def test_report_regenerates_and_keeps_methods_apart(outputs):
    _, summary, fm = outputs
    rep = (ROOT / R.OUTPUTS["report"]).read_text(encoding="utf-8")
    assert R.render_report(summary, fm) == rep
    assert "PROVISIONAL" in rep
    for s in F.API:
        assert s.model not in rep and s.display not in rep
    assert "gemini" not in rep.lower()


def test_english_inefficiency_flagged(outputs):
    _, summary, _ = outputs
    flagged = {s["model_key"] for s in summary["models"].values() if s.get("flag")}
    assert flagged == {"aragpt2-mega"}


# ---------------------------------------------------------------- needs the pinned tokenizer files

REF = json.loads((ROOT / "tests" / "regional_reference_ids.json").read_text(encoding="utf-8"))


@pytest.mark.network
@pytest.mark.parametrize("spec", [R.ALLAM, R.FANAR2], ids=lambda s: s.key)
def test_ids_match_official_sentencepiece(spec):
    c = R.load(spec, ROOT / R.HF_CACHE)
    for text, ref in zip(REF["samples"], REF["ids"][spec.key]):
        got = c.encode(text)[0] if isinstance(c, R.SentencePieceBpeCounter) else \
            c.tok.encode(text, add_special_tokens=False).ids
        assert got == ref, text


@pytest.mark.network
def test_rows_reproduce_byte_for_byte(outputs):
    rows, _, _ = outputs
    m = json.loads((ROOT / v2.MANIFEST_PATH).read_text())
    records = v2.verify(m, ROOT / v2.RAW)
    for spec in R.SPECS:
        committed = [r for r in rows if r["model_key"] == spec.key]
        if not committed:
            continue
        fresh = F.measure_rows(spec, R.load(spec, ROOT / R.HF_CACHE), records, m, committed[0]["measurement_meta"])
        assert [{k: str(v) for k, v in r.items()} for r in fresh] == committed
    assert F.weights_present(ROOT / R.HF_CACHE) == []


def _sandbox(tmp_path):
    for d in ("manifest", "results", "reports"):
        shutil.copytree(ROOT / d, tmp_path / d)
    (tmp_path / "data").mkdir()
    for d in ("raw_v2", "hf", F.HF_CACHE.name, R.HF_CACHE.name):
        (tmp_path / "data" / d).symlink_to(ROOT / "data" / d)
    return tmp_path


@pytest.mark.network
def test_full_run_regenerates_every_regional_artifact_byte_for_byte(tmp_path):
    root = _sandbox(tmp_path)
    R.run(root)
    for rel in R.OUTPUTS.values():
        assert (root / rel).read_bytes() == (ROOT / rel).read_bytes(), rel
    for d in ("manifest", "results", "reports"):  # nothing else touched
        for p in (ROOT / d).iterdir():
            assert (root / d / p.name).read_bytes() == p.read_bytes(), p


@pytest.mark.network
def test_run_refuses_to_change_published_rows(tmp_path):
    root = _sandbox(tmp_path)
    path = root / R.OUTPUTS["csv"]
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    head, first = lines[0], lines[1].split(",")
    col = head.strip().split(",").index("ar_tokens")
    first[col] = str(int(first[col]) + 1)
    path.write_text(head + ",".join(first) + "".join(lines[2:]), encoding="utf-8")
    before = {p: (root / p).read_bytes() for p in R.OUTPUTS.values()}
    with pytest.raises(F.PublishedResultsError, match="would change"):
        R.run(root)
    assert {p: (root / p).read_bytes() for p in R.OUTPUTS.values()} == before
