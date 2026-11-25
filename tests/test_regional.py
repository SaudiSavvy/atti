"""Arabic-focused and Arab-developed tokenizers: pins, provenance, equivalence, guards, failure handling,
reproducibility."""

import csv
import json
import re
import shutil
import statistics
from dataclasses import replace
from fractions import Fraction

import pytest

from atti import cli
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
        for assets in (s.assets, s.crosscheck_assets):
            assert all(re.fullmatch(r"[0-9a-f]{64}", d) for d in assets.values())
            assert set(assets) <= R.ASSET_ALLOWLIST and not any(n.endswith(F.WEIGHT_SUFFIXES) for n in assets)
        assert s.assets and s.kind in ("sentencepiece", "tokenizers")
        for f in ("model_country", "model_developers", "model_license", "tokenizer_name", "tokenizer_developer",
                  "tokenizer_type", "tokenizer_origin", "tokenizer_terms"):
            assert getattr(s, f), (s.key, f)
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


def test_model_and_tokenizer_provenance_kept_apart():
    assert R.JAIS3.assets == R.K2_HORIZON.assets
    assert R.JAIS3.tokenizer_name == R.K2_HORIZON.tokenizer_name == "K2 Horizon tokenizer"
    assert "unchanged" in R.JAIS3.source_note and "K2 Horizon" in R.JAIS3.tokenizer_origin
    assert (R.FANAR2.tokenizer_name, R.FANAR2.tokenizer_developer) == ("Gemma 3 tokenizer", "Google")
    assert R.FANAR2.model_country == "Qatar" and "gemma" in R.FANAR2.tokenizer_terms
    assert (R.ACEGPT2.tokenizer_name, R.ACEGPT2.tokenizer_developer) == ("Qwen1.5 tokenizer", "Alibaba Qwen team")
    assert "tongyi-qianwen-research" in R.ACEGPT2.tokenizer_terms
    assert R.ACEGPT2.model_license.startswith("apache-2.0")  # downstream declaration, recorded separately
    assert "unresolved" in R.ALLAM.tokenizer_terms  # LICENSE file referenced by the card is absent


def test_falcon_h1_arabic_not_substituted():
    assert R.UNAVAILABLE["falcon-h1-arabic"]["status"] == "UNAVAILABLE"
    assert not any(s.repo_id.startswith("tiiuae/") for s in R.SPECS)


def test_outputs_separate_from_published_artifacts():
    from atti import gemini

    published = set(json.loads((ROOT / "tests" / "historical_sha256.json").read_text()))
    published |= {str(p) for p in (*F.OUTPUTS.values(), *v2.OUTPUTS.values(), *gemini.OUTPUTS.values())}
    assert not {str(p) for p in R.OUTPUTS.values()} & published
    assert all("regional" in str(p) for p in R.OUTPUTS.values())


def test_custom_sentencepiece_reader_removed():
    for name in ("parse_spm", "SentencePieceBpeCounter", "_fields", "_varint"):
        assert not hasattr(R, name)
    assert R.ALLAM.kind == "sentencepiece" and R.SENTENCEPIECE_VERSION == "0.2.1"


def test_weight_and_unlisted_assets_refused(tmp_path, monkeypatch):
    bad = R.RegionalSpec("x", "x", "a/b", "0" * 40, "tokenizers", {"model.safetensors": "0" * 64}, "")
    with pytest.raises(F.AssetIntegrityError, match="allow-listed"):
        F.fetch_assets(bad, tmp_path, R.ASSET_ALLOWLIST)
    fake = tmp_path / "tokenizer.model"
    fake.write_bytes(b"not the pinned file")
    monkeypatch.setattr("huggingface_hub.hf_hub_download", lambda *a, **k: str(fake))
    with pytest.raises(F.AssetIntegrityError, match="SHA-256"):
        R.load(R.ALLAM, tmp_path)


def test_sentencepiece_runtime_version_is_pinned(tmp_path, monkeypatch):
    import sentencepiece

    monkeypatch.setattr(sentencepiece, "__version__", "0.2.0")
    with pytest.raises(F.AssetIntegrityError, match="pinned 0.2.1"):
        R.sentencepiece_processor(tmp_path / "tokenizer.model")


def test_tokenizer_json_with_unknown_normalizer_refused(tmp_path):
    p = tmp_path / "tokenizer.json"
    p.write_text(json.dumps({"normalizer": {"type": "Lowercase"}}))
    with pytest.raises(F.AssetIntegrityError, match="normalizer"):
        R.TokenizerJsonCounter(R.JAIS3, p)


# ---------------------------------------------------------------- failure handling (no corpus needed)

def _published_manifest(root, adapters):
    (root / "manifest").mkdir(parents=True, exist_ok=True)
    (root / R.OUTPUTS["manifest"]).write_text(json.dumps({"adapters": adapters}))


def test_evidence_guard_protects_equivalence_and_exclusion(tmp_path):
    old = {"k2": {"status": "EQUIVALENT", "equivalent_to": "jais", "checks": {"ids_sha256": "a" * 64}},
           "ag": {"status": "EXCLUDED", "checks": {"failed_texts": 48, "failures": {"ar x": 48}}}}
    _published_manifest(tmp_path, old)
    R.protect_evidence(tmp_path, json.loads(json.dumps(old)))  # reproduced exactly: allowed
    for change, msg in [
        ({"k2": {**old["k2"], "status": "BLOCKED"}}, "would become BLOCKED"),
        ({"k2": {**old["k2"], "equivalent_to": "qwen"}}, "equivalence would change"),
        ({"k2": {**old["k2"], "checks": {"ids_sha256": "b" * 64}}}, "evidence would change"),
        ({"ag": {**old["ag"], "checks": {"failed_texts": 0, "failures": {}}}}, "evidence would change"),
        ({"k2": None}, "would be removed")]:
        new = {**json.loads(json.dumps(old)), **change}
        new = {k: v for k, v in new.items() if v is not None}
        with pytest.raises(F.PublishedResultsError, match=msg):
            R.protect_evidence(tmp_path, new)


@pytest.mark.parametrize("exc,code,msg", [
    (R.RegionalError("k2: AssetIntegrityError"), 2, "no output was written"),
    (F.PublishedResultsError("k2: evidence would change"), 4, "nothing was written")])
def test_cli_failed_verification_exits_nonzero(monkeypatch, capsys, exc, code, msg):
    def fail(root):
        raise exc
    monkeypatch.setattr(R, "run", fail)
    assert cli.main(["regional"]) == code
    assert msg in capsys.readouterr().err


def test_offline_cache_miss_is_described():
    from huggingface_hub.errors import LocalEntryNotFoundError

    msg = R._describe(LocalEntryNotFoundError("missing"))
    assert "not in the local cache" in msg and "offline" in msg


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


def test_equivalence_groups_and_scope(outputs):
    _, summary, fm = outputs
    groups = {g["representative"]: g["members"] for g in summary["equivalence_groups"]}
    assert groups == {"jais-3-375b-a23b": ["k2-horizon-375b-a23b"], "Qwen/Qwen2.5-3B-Instruct": ["acegpt-v2-32b"]}
    a = fm["adapters"]
    assert a["k2-horizon-375b-a23b"]["equivalence"]["scope"] == "identical tokenizer files"
    ace = a["acegpt-v2-32b"]["equivalence"]
    assert ace["scope"].startswith("same token ids on the 200 corpus texts only")
    assert ace["divergent_added_tokens"]["count"] > 0 and "<tool_call>" in ace["divergent_added_tokens"]["examples"]
    assert a["k2-horizon-375b-a23b"]["checks"]["ids_sha256"] == a["jais-3-375b-a23b"]["checks"]["ids_sha256"]
    assert a["acegpt-v2-32b"]["checks"]["ids_sha256"] == \
        summary["reference_models"]["Qwen/Qwen2.5-3B-Instruct"]["ids_sha256"]
    digests = [a[k]["checks"]["ids_sha256"] for k, v in a.items() if v["status"] == "MEASURED"]
    digests += [m["ids_sha256"] for m in summary["reference_models"].values()]
    assert len(digests) == len(set(digests))  # every reported row is a distinct tokenizer


def test_runtimes_and_crosscheck_recorded_from_execution(outputs):
    _, _, fm = outputs
    a = fm["adapters"]
    assert a["allam-7b-instruct-preview"]["runtime"].startswith("sentencepiece 0.2.1 ")
    assert a["jais-3-375b-a23b"]["runtime"].startswith("tokenizers 0.22.1 ")
    c = a["fanar-2-27b-instruct"]["official_crosscheck"]
    assert c["texts"] == c["identical_ids"] == 200 and "sentencepiece 0.2.1" in c["reference"]


def test_exclusion_evidence(outputs):
    _, _, fm = outputs
    ex = fm["adapters"]["arabiangpt-08b-v2"]
    assert ex["checks"]["failed_texts"] == 48 and "unknown" in ex["reason"]
    assert "U+064B ARABIC FATHATAN" in ex["checks"]["unknown_token_characters"]
    for a in fm["adapters"].values():
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


def test_accepted_baseline_numbers(outputs):
    """The independently reproduced audit baseline (totals per tokenizer) is unchanged."""
    _, summary, _ = outputs
    got = {s["model_key"]: (s["ar_tokens_total"], s["en_tokens_total"]) for s in summary["models"].values()}
    assert got == {"allam-7b-instruct-preview": (6097, 7645), "jais-3-375b-a23b": (6015, 7202),
                   "fanar-2-27b-instruct": (8780, 7279), "aragpt2-mega": (5942, 13796)}


def test_reference_models_match_published_results(outputs):
    _, summary, _ = outputs
    published = json.loads((ROOT / F.OUTPUTS["summary"]).read_text())["models"]
    ref = summary["reference_models"]
    assert set(ref) == {m for m, s in published.items() if s["measurement_method"] == F.RAW_CONTENT}
    for m, s in ref.items():
        for f in ("ar_tokens_total", "en_tokens_total", "ttr", "median_article_ratio"):
            assert s[f] == published[m][f]
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


def test_aragpt2_reported_separately(outputs):
    _, summary, _ = outputs
    assert {s["model_key"] for s in summary["models"].values() if s["ranking"] == "separate"} == {"aragpt2-mega"}
    rep = (ROOT / R.OUTPUTS["report"]).read_text(encoding="utf-8")
    ranking = rep.split("## Bilingual ranking")[1].split("## Arabic-focused result")[0]
    separate = rep.split("## Arabic-focused result")[1].split("## Per-language")[0]
    assert "AraGPT2" not in ranking and "5,942 | 13,796" in separate
    assert "diacritics" in separate and "ArabertPreprocessor" in separate


# ---------------------------------------------------------------- needs the pinned tokenizer files

REF = json.loads((ROOT / "tests" / "regional_reference_ids.json").read_text(encoding="utf-8"))


@pytest.mark.network
def test_official_sentencepiece_reproduces_reference_ids():
    c = R.load(R.ALLAM, ROOT / R.HF_CACHE)
    assert isinstance(c, R.SentencePieceCounter)
    for text, ref in zip(REF["samples"], REF["ids"]["allam-7b-instruct-preview"]):
        assert c.sp.encode(text, out_type=int) == ref, text
    fanar = R.load(R.FANAR2, ROOT / R.HF_CACHE)
    for text, ref in zip(REF["samples"], REF["ids"]["fanar-2-27b-instruct"]):
        assert fanar.tok.encode(text, add_special_tokens=False).ids == ref, text


@pytest.mark.network
def test_rows_reproduce_byte_for_byte(outputs):
    rows, _, _ = outputs
    m = json.loads((ROOT / v2.MANIFEST_PATH).read_text())
    records = v2.verify(m, ROOT / v2.RAW)
    for spec in R.SPECS:
        committed = [r for r in rows if r["model_key"] == spec.key]
        if committed:
            fresh = F.measure_rows(spec, R.load(spec, ROOT / R.HF_CACHE), records, m,
                                   committed[0]["measurement_meta"])
            assert [{k: str(v) for k, v in r.items()} for r in fresh] == committed
    assert F.weights_present(ROOT / R.HF_CACHE) == []


def _sandbox(tmp_path, link_regional_cache=True):
    for d in ("manifest", "results", "reports"):
        shutil.copytree(ROOT / d, tmp_path / d)
    (tmp_path / "data").mkdir()
    for d in ("raw_v2", "hf", F.HF_CACHE.name) + ((R.HF_CACHE.name,) if link_regional_cache else ()):
        (tmp_path / "data" / d).symlink_to(ROOT / "data" / d)
    return tmp_path


def _published(root):
    return {p: (root / p).read_bytes() for p in R.OUTPUTS.values()}


@pytest.mark.network
def test_full_run_regenerates_every_regional_artifact_byte_for_byte(tmp_path):
    root = _sandbox(tmp_path)
    R.run(root)
    assert _published(root) == _published(ROOT)
    for d in ("manifest", "results", "reports"):  # nothing else touched
        for p in (ROOT / d).iterdir():
            assert (root / d / p.name).read_bytes() == p.read_bytes(), p


@pytest.mark.network
def test_integrity_failure_keeps_verified_outputs(tmp_path, monkeypatch):
    """K2 Horizon tokenizer_config.json hash mismatch: abort, keep its published EQUIVALENT record."""
    root = _sandbox(tmp_path)
    bad = replace(R.K2_HORIZON, assets={**R.K2_HORIZON.assets, "tokenizer_config.json": "0" * 64})
    monkeypatch.setattr(R, "SPECS", tuple(bad if s.key == bad.key else s for s in R.SPECS))
    before = _published(root)
    with pytest.raises(R.RegionalError, match="k2-horizon-375b-a23b: AssetIntegrityError"):
        R.run(root)
    assert _published(root) == before


@pytest.mark.network
def test_offline_cache_miss_keeps_verified_outputs(tmp_path, monkeypatch):
    import huggingface_hub
    from huggingface_hub.errors import LocalEntryNotFoundError

    root = _sandbox(tmp_path, link_regional_cache=False)
    (root / R.HF_CACHE).mkdir()  # empty regional cache
    real = huggingface_hub.hf_hub_download
    regional_repos = {s.repo_id for s in R.SPECS}

    def offline(repo_id, *a, **k):
        if repo_id in regional_repos:
            raise LocalEntryNotFoundError("offline mode is enabled and the file is not cached")
        return real(repo_id, *a, **k)

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", offline)
    before = _published(root)
    with pytest.raises(R.RegionalError, match="not in the local cache"):
        R.run(root)
    assert _published(root) == before


@pytest.mark.network
def test_unexpected_tokenizer_failure_keeps_verified_outputs(tmp_path, monkeypatch):
    root = _sandbox(tmp_path)
    real = R.check

    def boom(counter, records):
        if counter.spec.key == "arabiangpt-08b-v2":
            raise RuntimeError("tokenizer crashed")
        return real(counter, records)

    monkeypatch.setattr(R, "check", boom)
    before = _published(root)
    with pytest.raises(R.RegionalError, match="arabiangpt-08b-v2: RuntimeError"):
        R.run(root)
    assert _published(root) == before


@pytest.mark.network
def test_changed_evidence_is_refused(tmp_path):
    root = _sandbox(tmp_path)
    path = root / R.OUTPUTS["manifest"]
    doc = json.loads(path.read_text())
    doc["adapters"]["acegpt-v2-32b"]["equivalent_to"] = "jais-3-375b-a23b"
    path.write_text(F.dumps(doc))
    before = _published(root)
    with pytest.raises(F.PublishedResultsError, match="acegpt-v2-32b: its published equivalence would change"):
        R.run(root)
    assert _published(root) == before


@pytest.mark.network
def test_changed_published_rows_are_refused(tmp_path):
    root = _sandbox(tmp_path)
    path = root / R.OUTPUTS["csv"]
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    head, first = lines[0], lines[1].split(",")
    col = head.strip().split(",").index("ar_tokens")
    first[col] = str(int(first[col]) + 1)
    path.write_text(head + ",".join(first) + "".join(lines[2:]), encoding="utf-8")
    before = _published(root)
    with pytest.raises(F.PublishedResultsError, match="would change"):
        R.run(root)
    assert _published(root) == before
