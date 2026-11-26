"""Local review workspace: drafts, explicit confirmation, schema mapping, AI concealment, local-only server.

Toy corpora and placeholder text only; no real article, decision or finding is written."""

import http.client
import json

import pytest

from atti import corpus, review, workspace
from atti.workspace import Item, Workspace, WorkspaceError

TODAY = "2026-12-01"
TOY = {"corpus": "expanded_v1", "articles": [{"article": 1, "id": "T-1"}, {"article": 2, "id": "T-2"}]}
TOY2 = {"corpus": "current_law_v2", "articles": [{"key": "1", "id": "V-1"}]}


def item(cid="expanded_v1:1", flagged=False, members=("expanded_v1",)):
    home, key = cid.split(":")
    return Item(id=cid, home=home, key=key, ar="نص", en="text", ar_sha256="a" * 64, en_sha256="b" * 64, part="1",
                members=[{"corpus": c, "id": f"T-{key}"} for c in members],
                ai={"notes": [{"label": "AI evidence", "text": "placeholder AI note"}]}, ai_flagged=flagged)


@pytest.fixture
def ws(tmp_path):
    for m in (TOY, TOY2):
        p = tmp_path / "manifest" / f"{m['corpus']}_manifest.json"
        corpus.write_json(p, m)
        corpus.write_json(tmp_path / "review" / f"{m['corpus']}_human_decisions.json",
                          review.decisions_template(m["corpus"], m, review.manifest_sha256(p)))
    items = [item(), item("expanded_v1:2", flagged=True), item("current_law_v2:1", members=("current_law_v2",))]
    return Workspace(tmp_path, "SaudiSavvy", items, {}, today=lambda: TODAY)


def full(**over):
    d = {"equivalence": "EQUIVALENT", "decision": "APPROVE", "comment": "",
         "terminology": {"assessment": "OK", "note": ""}, "completeness": {"assessment": "OK", "note": ""},
         "consistency": {"assessment": "OK", "note": ""}}
    d.update(over)
    return d


def decisions(ws, corpus_name="expanded_v1"):
    return corpus.read_json(ws.root / "review" / f"{corpus_name}_human_decisions.json")["decisions"]


def test_drafts_never_reach_the_decision_file(ws):
    ws.save_draft("expanded_v1:1", full())
    assert decisions(ws)["1"]["decision"] is None
    assert ws.drafts_path.exists() and str(workspace.DRAFTS).startswith("data/")


def test_record_requires_preview_fingerprint_and_explicit_confirmation(ws):
    ws.save_draft("expanded_v1:1", full())
    p = ws.preview("expanded_v1:1")
    assert p["ok"] and p["record"]["reviewer"] == "SaudiSavvy" and decisions(ws)["1"]["decision"] is None
    for fp, confirm in ((p["fingerprint"], False), (p["fingerprint"], "yes"), ("0" * 64, True), (None, True)):
        with pytest.raises(WorkspaceError):
            ws.record("expanded_v1:1", fp, confirm)
    assert decisions(ws)["1"]["decision"] is None
    ws.record("expanded_v1:1", p["fingerprint"], True)
    d = decisions(ws)["1"]
    assert (d["decision"], d["reviewer"], d["date"], d["review_period"]) == ("APPROVE", "SaudiSavvy", TODAY, TODAY)


def test_a_draft_edited_after_preview_is_not_recorded(ws):
    ws.save_draft("expanded_v1:1", full())
    p = ws.preview("expanded_v1:1")
    ws.save_draft("expanded_v1:1", full(decision="REJECT", comment="note C"))
    with pytest.raises(WorkspaceError, match="changed after the preview"):
        ws.record("expanded_v1:1", p["fingerprint"], True)


def test_every_criterion_and_the_decision_are_required():
    rec, problems = workspace.build_record({"decision": "APPROVE"}, item(), TODAY)
    assert rec is None and len(problems) == 4
    rec, problems = workspace.build_record(full(terminology={"assessment": "MINOR_ISSUE", "note": " "}), item(), TODAY)
    assert rec is None and any("terminology" in p for p in problems)


def test_benchmark_acceptance_is_separate_from_semantic_equivalence(ws):
    draft = full(equivalence="MATERIAL_DIFFERENCE", comment="note C",
                 completeness={"assessment": "MATERIAL_ISSUE", "note": "note X"},
                 terminology={"assessment": "MINOR_ISSUE", "note": "note T"},
                 discrepancies=[{"severity": "MINOR", "note": "note D"}])
    ws.save_draft("expanded_v1:1", draft)
    p = ws.preview("expanded_v1:1")
    assert p["ok"], p
    ws.record("expanded_v1:1", p["fingerprint"], True)
    d = decisions(ws)["1"]
    assert d["decision"] == "APPROVE" and d["equivalence"] == "MATERIAL_DIFFERENCE"
    assert d["terminology"] == "Minor issue: note T"
    assert {"severity": "MATERIAL", "note": "Completeness of clauses and conditions: note X"} in d["discrepancies"]
    assert {"severity": "MINOR", "note": "note D"} in d["discrepancies"]


def test_existing_validator_still_applies(ws):
    ws.save_draft("expanded_v1:1", full(decision="REJECT", comment=""))
    p = ws.preview("expanded_v1:1")
    assert not p["ok"] and any("comment required" in x for x in p["problems"])


def test_ai_material_is_hidden_until_revealed_and_the_reveal_is_logged(ws):
    page = workspace.render_page(list(ws.items.values()), {"unique_pairs": 3, "slots": 3}, "SaudiSavvy", "tok")
    assert "placeholder AI note" not in page and "ai_flagged" not in page
    ws.save_draft("expanded_v1:2", full())
    p = ws.preview("expanded_v1:2")
    assert not p["ok"] and any("reveal" in x for x in p["problems"])
    a = ws.reveal("expanded_v1:2")
    assert a["notes"][0]["text"] == "placeholder AI note" and a["judgment_before_reveal"] is True
    assert ws.drafts["items"]["expanded_v1:2"]["ai_revealed_at"]
    assert not ws.preview("expanded_v1:2")["ok"]  # adjudication still required for a flagged article
    ws.save_draft("expanded_v1:2", full(ai_adjudication={"verdict": "AGREE", "note": "note A"}))
    p = ws.preview("expanded_v1:2")
    assert p["ok"] and p["record"]["ai_adjudication"] == {"verdict": "AGREE", "note": "note A"}


def test_reveal_metadata_cannot_be_forged_or_cleared_by_the_page(ws):
    ws.save_draft("expanded_v1:2", {"ai_revealed_at": "2020-01-01T00:00:00"})
    assert "ai_revealed_at" not in ws.drafts["items"]["expanded_v1:2"]
    ws.reveal("expanded_v1:2")
    ws.save_draft("expanded_v1:2", {"ai_revealed_at": None})
    assert ws.drafts["items"]["expanded_v1:2"]["ai_revealed_at"]


def test_replacing_a_recorded_decision_is_explicit(ws):
    ws.save_draft("expanded_v1:1", full())
    ws.record("expanded_v1:1", ws.preview("expanded_v1:1")["fingerprint"], True)
    ws.save_draft("expanded_v1:1", full(decision="REQUEST_EXAMINATION", comment="note C"))
    p = ws.preview("expanded_v1:1")
    assert p["replace"] and p["existing"]["decision"] == "APPROVE"
    ws.record("expanded_v1:1", p["fingerprint"], True)
    assert decisions(ws)["1"]["decision"] == "REQUEST_EXAMINATION"


def test_drafts_survive_a_restart(ws):
    ws.save_draft("current_law_v2:1", full(notes="note N", flag=True))
    again = Workspace(ws.root, "SaudiSavvy", list(ws.items.values()), {}, today=lambda: TODAY)
    d = again.state()["drafts"]["current_law_v2:1"]
    assert d["notes"] == "note N" and d["flag"] and again.state()["last_item"] == "current_law_v2:1"


def test_review_period_runs_from_first_draft_to_recording(ws):
    ws.today = lambda: "2026-11-28"
    ws.save_draft("expanded_v1:1", full(decision=None))
    ws.today = lambda: TODAY
    ws.save_draft("expanded_v1:1", full())
    assert ws.preview("expanded_v1:1")["record"]["review_period"] == f"2026-11-28/{TODAY}"


def test_ai_reviewer_names_are_refused(tmp_path):
    with pytest.raises(WorkspaceError):
        Workspace(tmp_path, "Claude Opus 5", [], {})


def test_dedupe_only_identical_pairs():
    def entry(k, ar, en):
        return {"article": k, "id": f"T-{k}", "ar_sha256": ar * 64, "en_sha256": en * 64}
    data = {"expanded_v1": {"manifest": {"articles": [entry(1, "a", "b"), entry(2, "c", "d")],
                                         "law": {"instrument": "I", "latest_amendment_in_both_sources": "L"},
                                         "sources": {"ar": {"url": "https://laws.boe.gov.sa/x"},
                                                     "en": {"url": "https://laws.boe.gov.sa/y", "pdf_sha256": "0"}}},
                            "texts": {"1": ("ع", "e"), "2": ("ع", "e")}, "parts": {}},
            "pilot": {"manifest": {"articles": [entry(1, "a", "b")]}, "texts": {"1": ("ع", "e")}, "parts": {}},
            "current_law_v2": {"manifest": {"articles": [], "law": {"instrument": "I", "version": "V"},
                                            "sources": {"ar_pdf": {"url": "https://www.hrsd.gov.sa/p", "sha256": "0"}}},
                               "texts": {}, "parts": {}, "records": {}},
            "ai": {"pilot": {"articles": {}}, "expanded_v1": {"articles": {}, "material_discrepancies": []},
                   "expanded_v1_nuances": {"articles": {}}, "current_law_v2": {"articles": {}}}}
    items, summary = workspace.build_items(data)
    assert [i.id for i in items] == ["expanded_v1:1", "expanded_v1:2"]
    assert [m["corpus"] for m in items[0].members] == ["expanded_v1", "pilot"]
    assert summary["duplicates"] == [{"item": "expanded_v1:1", "corpora": ["expanded_v1", "pilot"]}]
    data["pilot"]["manifest"]["articles"] = [entry(1, "a", "f")]  # same Arabic, different English
    with pytest.raises(WorkspaceError, match="no identical pair"):
        workspace.build_items(data)


def test_script_embedding_cannot_close_the_script_tag():
    s = workspace.json_for_script({"t": "</script><script>x()</script>"})
    assert "</" not in s and "<" not in s


@pytest.fixture
def server(ws):
    srv, url = workspace.serve(ws, lambda tok: workspace.render_page(list(ws.items.values()), {}, "SaudiSavvy", tok))
    import threading
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv, url
    srv.shutdown()
    srv.server_close()


def req(url, method="GET", path="", body=None, headers=None, host=None):
    port = int(url.split(":")[2].split("/")[0])
    token = url.rstrip("/").rsplit("/", 1)[1]
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    h = {"Host": host or f"127.0.0.1:{port}", **(headers or {})}
    c.request(method, f"/{token}/{path}", body=json.dumps(body) if body is not None else None, headers=h)
    r = c.getresponse()
    return r.status, r.read(), token


def test_server_is_local_and_token_protected(server):
    srv, url = server
    assert srv.server_address[0] == "127.0.0.1"
    status, body, token = req(url)
    assert status == 200 and b"ATTI Review Workspace" in body
    assert req(url, host="evil.example:80")[0] == 403  # DNS rebinding
    port = srv.server_address[1]
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", "/wrong-token/", headers={"Host": f"127.0.0.1:{port}"})
    assert c.getresponse().status == 404
    ok = {"Content-Type": "application/json", "X-ATTI-Token": token}
    draft = {"id": "expanded_v1:1", "draft": full()}
    assert req(url, "POST", "api/draft", draft, {"Content-Type": "application/json"})[0] == 403
    assert req(url, "POST", "api/draft", draft, {"X-ATTI-Token": token, "Content-Type": "text/plain"})[0] == 403
    assert req(url, "POST", "api/draft", draft, ok)[0] == 200
    status, body, _ = req(url, "POST", "api/preview", {"id": "expanded_v1:1"}, ok)
    fp = json.loads(body)["fingerprint"]
    assert req(url, "POST", "api/record", {"id": "expanded_v1:1", "fingerprint": fp}, ok)[0] == 409
    assert req(url, "POST", "api/record", {"id": "expanded_v1:1", "fingerprint": fp, "confirm": True}, ok)[0] == 200
    assert req(url, "POST", "api/draft", {"id": "../../etc", "draft": {}}, ok)[0] == 409
