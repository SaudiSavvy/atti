"""Local human-review workspace for every pair in the pilot, expanded_v1 and current_law_v2 corpora.

``atti review-workspace`` verifies every pair against its pinned hashes, then serves one page on
127.0.0.1. The page autosaves drafts and notes to ``data/review/workspace_drafts.json``
(git-ignored, local only). A decision is written to ``review/<corpus>_human_decisions.json``
only when the reviewer confirms the exact record shown to them, and the existing validator runs
(``review.record_decision``) before anything is written.

- A pair whose Arabic and English hashes are both identical in two corpora is reviewed once.
  The pilot's pairs are the same bytes as ten expanded_v1 pairs, so they are recorded in the
  expanded_v1 file, as the methodology already describes. Pairs that differ in either language
  are reviewed separately.
- AI material (proposed statuses, notes, discrepancy flags) is not sent to the page. It is
  fetched only when the reviewer asks to see it for one article, and the time is logged in the
  drafts file.
- Nothing here changes manifests, results, reports or legal texts.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import secrets
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from atti import corpus, review
from atti.sources import UntrustedURLError, require_https_host, sha256_text

CORPORA = ("pilot", "expanded_v1", "current_law_v2")
SIZES = {"pilot": 10, "expanded_v1": 30, "current_law_v2": 100}
DECISION_HOME = ("expanded_v1", "current_law_v2")  # corpora that have a human decisions file
DRAFTS = Path("data") / "review" / "workspace_drafts.json"
ASSESS = ("OK", "MINOR_ISSUE", "MATERIAL_ISSUE")
CRITERIA = {  # draft field -> label used in the recorded discrepancy note
    "terminology": "Legal terminology",
    "completeness": "Completeness of clauses and conditions",
    "consistency": "Numbers, exceptions and legal references",
}
_TEXT_MAX = 4000


class WorkspaceError(RuntimeError):
    pass


@dataclass
class Item:
    id: str
    home: str
    key: str
    ar: str
    en: str
    ar_sha256: str
    en_sha256: str
    part: str
    members: list = field(default_factory=list)   # [{"corpus", "id"}]
    version: str = ""
    sources: list = field(default_factory=list)   # [{"label", "url"}]
    source_note: str = ""
    related: list = field(default_factory=list)   # other versions of the same article number
    ai: dict = field(default_factory=dict)        # never sent to the page unless revealed
    ai_flagged: bool = False

    def public(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k not in ("ai", "ai_flagged")}
        d["ar_chars"], d["en_chars"] = len(self.ar), len(self.en)
        return d


def _link(label: str, url: str | None, host: str) -> dict:
    if not url:
        return {"label": f"{label}: none", "url": None}
    try:
        require_https_host(url.split("#")[0], host)
    except UntrustedURLError:
        return {"label": f"{label}: unexpected URL withheld", "url": None}
    return {"label": label, "url": url}


def _check_hashes(corpus_name: str, entries: list[dict], texts: dict[str, tuple[str, str]]) -> None:
    """Second, independent check of what the page will display: hash the exact strings."""
    for e in entries:
        k = str(e.get("key", e.get("article")))
        ar, en = texts[k]
        if sha256_text(ar) != e["ar_sha256"] or sha256_text(en) != e["en_sha256"]:
            raise WorkspaceError(f"{corpus_name} Article {k}: displayed text does not match the pinned hash")


def load_corpora(root: Path) -> dict:
    """Verify all three corpora (fail closed) and return their entries, texts and AI material."""
    from atti import v2

    out = {}
    raw = root / "data" / "raw"
    for name in ("pilot", "expanded_v1"):
        m = corpus.read_json(root / "manifest" / f"{name}_manifest.json")
        pairs = corpus.verify(m, raw)  # raises corpus.VerificationError
        texts = {str(p.article): (p.ar_text, p.en_text) for p in pairs}
        _check_hashes(name, m["articles"], texts)
        out[name] = {"manifest": m, "texts": texts, "parts": {}}
    ar_articles, _ = corpus.load_sources(raw)
    boe_parts = {str(a.number): str(a.part) for a in ar_articles if not a.bis}
    for name in ("pilot", "expanded_v1"):
        out[name]["parts"] = {k: boe_parts.get(k, "") for k in out[name]["texts"]}
    m = corpus.read_json(root / "manifest" / "current_law_v2_manifest.json")
    recs = v2.verify(m, root / v2.RAW)  # raises v2.VerificationError
    texts = {r.key: (r.ar_text, r.en_text) for r in recs}
    _check_hashes("current_law_v2", m["articles"], texts)
    out["current_law_v2"] = {"manifest": m, "texts": texts, "parts": {r.key: str(r.part) for r in recs},
                             "records": {r.key: r for r in recs}}
    for name, n in SIZES.items():
        if len(out[name]["texts"]) != n:
            raise WorkspaceError(f"{name}: expected {n} verified pairs, got {len(out[name]['texts'])}")
    out["ai"] = {
        "pilot": corpus.read_json(root / "manifest" / "review.json"),
        "expanded_v1": corpus.read_json(root / "review" / "expanded_v1_ai_review.json"),
        "expanded_v1_nuances": corpus.read_json(root / "manifest" / "expanded_v1_review.json"),
        "current_law_v2": corpus.read_json(root / "manifest" / "current_law_v2_review.json"),
    }
    return out


def _ai_material(data: dict, corpus_name: str, key: str, entry: dict) -> dict:
    ai = data["ai"]
    notes = []
    if corpus_name == "pilot":
        if key in ai["pilot"].get("articles", {}):
            notes.append(("Pilot AI review note", ai["pilot"]["articles"][key]))
    else:
        f = ai[corpus_name]
        a = f["articles"].get(key, {})
        if a:
            notes.append((f"{corpus_name} AI proposed status", a.get("proposed_status", "")))
            notes.append((f"{corpus_name} AI evidence", a.get("evidence", "")))
        for d in f.get("material_discrepancies", []):
            if str(d["article"]) == key:
                notes.append((f"{corpus_name} AI possible material discrepancy", d["issue"]))
        if corpus_name == "current_law_v2":
            for d in f.get("discrepancy_matrix", []):
                if str(d["article"]) == key:
                    notes.append(("current_law_v2 AI discrepancy matrix",
                                  f"{d.get('category', '')}: {d.get('finding', '')}"))
            if key in (f.get("previously_disputed") or {}):
                notes.append(("current_law_v2 AI note on the earlier BOE version", f["previously_disputed"][key]))
        else:
            nu = data["ai"]["expanded_v1_nuances"].get("articles", {}).get(key)
            if nu:
                notes.append(("expanded_v1 AI translation note", nu if isinstance(nu, str) else json.dumps(nu, ensure_ascii=False)))
    cr = (entry.get("verification") or {}).get("content_review")
    if cr:
        notes.append((f"{corpus_name} manifest AI content note", cr))
    return {"notes": [{"label": a, "text": str(b)} for a, b in notes if b]}


def build_items(data: dict) -> tuple[list[Item], dict]:
    """One item per distinct (Arabic hash, English hash); report duplicates and version differences."""
    items: dict[tuple[str, str], Item] = {}
    boe = data["expanded_v1"]["manifest"]
    boe_version = (f"{boe['law']['instrument']}; BOE 2005 base text (articles amended later are excluded); "
                   f"latest amendment in both sources: {boe['law']['latest_amendment_in_both_sources']}")
    v2m = data["current_law_v2"]["manifest"]
    v2_version = f"{v2m['law']['instrument']}; HRSD {v2m['law']['version']}"
    from atti.hrsd import HOST as HRSD_HOST
    from atti.sources import BOE_HOST

    flagged = {c: set(review.flagged_articles(data["ai"][c])) for c in DECISION_HOME}
    order = ["expanded_v1", "current_law_v2", "pilot"]  # homes first, so the pilot joins expanded_v1
    for c in order:
        m = data[c]["manifest"]
        for e in m["articles"]:
            k = str(e.get("key", e.get("article")))
            h = (e["ar_sha256"], e["en_sha256"])
            member = {"corpus": c, "id": e["id"]}
            if h in items:
                items[h].members.append(member)
                items[h].ai["notes"] += _ai_material(data, c, k, e)["notes"]
                continue
            if c not in DECISION_HOME:
                raise WorkspaceError(f"{c} Article {k} has no identical pair in a corpus with a decision file")
            ar, en = data[c]["texts"][k]
            it = Item(id=f"{c}:{k}", home=c, key=k, ar=ar, en=en, ar_sha256=h[0], en_sha256=h[1],
                      part=data[c]["parts"].get(k, ""), members=[member], ai=_ai_material(data, c, k, e),
                      ai_flagged=k in flagged[c])
            if c == "current_law_v2":
                r = data[c]["records"][k]
                it.version = v2_version
                pdf = v2m["sources"]["ar_pdf"]
                pages = list(r.ar_pages)
                it.sources = [_link(f"Arabic PDF (p. {', '.join(map(str, pages))})",
                                    f"{pdf['url']}#page={pages[0]}" if pages else pdf["url"], HRSD_HOST),
                              _link("Arabic HTML page", r.ar_html_url, HRSD_HOST),
                              _link("English page", r.en_url, HRSD_HOST)]
                it.source_note = f"Arabic PDF SHA-256 {pdf['sha256']}"
            else:
                it.version = boe_version
                it.sources = [_link("Arabic (BOE law page)", boe["sources"]["ar"]["url"], BOE_HOST),
                              _link("English (BOE official translation PDF)", boe["sources"]["en"]["url"], BOE_HOST)]
                it.source_note = f"English PDF SHA-256 {boe['sources']['en']['pdf_sha256']}"
            items[h] = it
    out = sorted(items.values(), key=lambda i: (DECISION_HOME.index(i.home), review._sort(i.key)))
    by_num: dict[str, list[Item]] = {}
    for it in out:
        by_num.setdefault(it.key, []).append(it)
    differences = []
    for k, group in by_num.items():
        if len(group) < 2:
            continue
        for it in group:
            for other in group:
                if other is it:
                    continue
                same_ar = other.ar_sha256 == it.ar_sha256
                same_en = other.en_sha256 == it.en_sha256
                it.related.append({"item": other.id, "note":
                                   f"Arabic {'identical' if same_ar else 'differs'}, "
                                   f"English {'identical' if same_en else 'differs'}"})
        a, b = group[0], group[1]
        differences.append({"article": k, "items": [g.id for g in group],
                            "arabic": "identical" if a.ar_sha256 == b.ar_sha256 else "differs",
                            "english": "identical" if a.en_sha256 == b.en_sha256 else "differs"})
    duplicates = [{"item": it.id, "corpora": [m["corpus"] for m in it.members]} for it in out if len(it.members) > 1]
    summary = {"verified": {c: len(data[c]["texts"]) for c in CORPORA},
               "slots": sum(len(data[c]["texts"]) for c in CORPORA), "unique_pairs": len(out),
               "duplicates": duplicates, "version_differences": differences}
    return out, summary


# ---------------------------------------------------------------- drafts (local, git-ignored)

def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _s(v, n=_TEXT_MAX) -> str:
    return v[:n] if isinstance(v, str) else ""


def _choice(v, allowed):
    return v if v in allowed else None


def clean_draft(d: dict, old: dict | None) -> dict:
    """Keep only known draft fields with valid values; reveal and first-save metadata are server-owned."""
    old = old or {}
    d = d if isinstance(d, dict) else {}
    out = {"equivalence": _choice(d.get("equivalence"), review.EQUIVALENCE),
           "decision": _choice(d.get("decision"), review.HUMAN_DECISIONS),
           "comment": _s(d.get("comment")), "notes": _s(d.get("notes"), 20000), "flag": bool(d.get("flag"))}
    for c in CRITERIA:
        v = d.get(c) if isinstance(d.get(c), dict) else {}
        out[c] = {"assessment": _choice(v.get("assessment"), ASSESS), "note": _s(v.get("note"))}
    disc = d.get("discrepancies") if isinstance(d.get("discrepancies"), list) else []
    out["discrepancies"] = [{"severity": _choice(x.get("severity"), review.SEVERITIES), "note": _s(x.get("note"))}
                            for x in disc[:20] if isinstance(x, dict)]
    adj = d.get("ai_adjudication") if isinstance(d.get("ai_adjudication"), dict) else {}
    out["ai_adjudication"] = {"verdict": _choice(adj.get("verdict"), review.ADJUDICATIONS), "note": _s(adj.get("note"))}
    for k in ("first_saved", "ai_revealed_at", "judgment_before_reveal"):
        if k in old:
            out[k] = old[k]
    return out


def has_judgment(d: dict) -> bool:
    return bool(d.get("equivalence") or d.get("decision")
                or any((d.get(c) or {}).get("assessment") for c in CRITERIA))


def build_record(draft: dict, item: Item, today: str) -> tuple[dict | None, list[str]]:
    """Map the reviewer's draft onto the existing decision schema. Returns (record, problems)."""
    p = []
    if not draft.get("equivalence"):
        p.append("Assess semantic equivalence.")
    for c, label in CRITERIA.items():
        a = (draft.get(c) or {}).get("assessment")
        if not a:
            p.append(f"Assess: {label.lower()}.")
        elif a != "OK" and not (draft[c].get("note") or "").strip():
            p.append(f"Describe the {label.lower()} issue.")
    if not draft.get("decision"):
        p.append("Choose a benchmark decision (APPROVE, REJECT or REQUEST_EXAMINATION).")
    disc = []
    for c, label in CRITERIA.items():
        v = draft.get(c) or {}
        if v.get("assessment") in ("MINOR_ISSUE", "MATERIAL_ISSUE") and v.get("note", "").strip():
            disc.append({"severity": "MINOR" if v["assessment"] == "MINOR_ISSUE" else "MATERIAL",
                         "note": f"{label}: {v['note'].strip()}"})
    for x in draft.get("discrepancies") or []:
        if (x.get("note") or "").strip() or x.get("severity"):
            if not x.get("severity") or not x.get("note", "").strip():
                p.append("Each additional discrepancy needs a severity and a note.")
            else:
                disc.append({"severity": x["severity"], "note": x["note"].strip()})
    adj = draft.get("ai_adjudication") or {}
    revealed = bool(draft.get("ai_revealed_at"))
    if item.ai_flagged and not revealed:
        p.append("The AI review flagged this article: after forming your judgment, reveal the AI "
                 "assessment and give your verdict on it.")
    adjudication = None
    if revealed and (adj.get("verdict") or (adj.get("note") or "").strip()):
        if not adj.get("verdict") or not adj.get("note", "").strip():
            p.append("Your verdict on the AI assessment needs both a verdict and a note.")
        else:
            adjudication = {"verdict": adj["verdict"], "note": adj["note"].strip()}
    elif item.ai_flagged and revealed:
        p.append("Give your verdict on the AI assessment (required for AI-flagged articles).")
    if p:
        return None, p
    t = draft["terminology"]
    term = {"OK": "Accurate", "MINOR_ISSUE": "Minor issue", "MATERIAL_ISSUE": "Material issue"}[t["assessment"]]
    if t["note"].strip():
        term += f": {t['note'].strip()}"
    start = draft.get("first_saved") or today
    findings = {"review_period": start if start == today else f"{start}/{today}",
                "equivalence": draft["equivalence"], "terminology": term, "discrepancies": disc,
                "ai_adjudication": adjudication}
    rec = {"decision": draft["decision"], "comment": (draft.get("comment") or "").strip(), "date": today,
           **{k: v for k, v in findings.items() if v not in (None, "", [])}}
    return rec, []


def _findings(rec: dict) -> dict:
    return {k: rec[k] for k in review.FINDING_FIELDS if k in rec}


def fingerprint(rec: dict, reviewer: str, replace: bool) -> str:
    blob = json.dumps({"rec": rec, "reviewer": reviewer, "replace": replace}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


class Workspace:
    def __init__(self, root: Path, reviewer: str, items: list[Item], summary: dict, today=None):
        if not reviewer.strip() or review._NOT_HUMAN.search(reviewer):
            raise WorkspaceError("reviewer must be a human name or pseudonym")
        self.root, self.reviewer, self.summary = root, reviewer, summary
        self.items = {i.id: i for i in items}
        self.order = [i.id for i in items]
        self.lock = threading.Lock()
        self.today = today or (lambda: dt.date.today().isoformat())
        self.drafts_path = root / DRAFTS
        self.drafts = (corpus.read_json(self.drafts_path) if self.drafts_path.exists()
                       else {"kind": "Local review drafts (git-ignored). Not a record of decisions.",
                             "items": {}, "last_item": None, "events": []})
        for c in DECISION_HOME:  # make sure every decision file is valid before starting
            self._decisions(c)

    # decision files
    def _paths(self, c):
        return (self.root / "manifest" / f"{c}_manifest.json", self.root / "review" / f"{c}_human_decisions.json")

    def _decisions(self, c):
        m_path, d_path = self._paths(c)
        m = corpus.read_json(m_path)
        h = review.manifest_sha256(m_path)
        if not d_path.exists():
            review.write_json_new(d_path, review.decisions_template(c, m, h))
        dec = corpus.read_json(d_path)
        flagged = [i.key for i in self.items.values() if i.home == c and i.ai_flagged]
        errs = review.validate_decisions(dec, m, h, flagged)
        if errs:
            raise WorkspaceError(f"{d_path.name} is invalid: " + "; ".join(errs))
        return m, h, dec, flagged

    def recorded(self) -> dict:
        out = {}
        for c in DECISION_HOME:
            _, _, dec, _ = self._decisions(c)
            for k, d in dec["decisions"].items():
                if d.get("decision") is not None:
                    out[f"{c}:{k}"] = d
        return out

    def _save(self):
        _atomic_write(self.drafts_path, self.drafts)

    def _item(self, item_id) -> Item:
        if not isinstance(item_id, str) or item_id not in self.items:
            raise WorkspaceError("unknown article")
        return self.items[item_id]

    def state(self) -> dict:
        return {"drafts": self.drafts["items"], "recorded": self.recorded(), "last_item": self.drafts.get("last_item")}

    def save_draft(self, item_id, draft) -> dict:
        self._item(item_id)
        with self.lock:
            old = self.drafts["items"].get(item_id)
            new = clean_draft(draft, old)
            if has_judgment(new) and "first_saved" not in new:
                new["first_saved"] = self.today()
            new["updated_at"] = dt.datetime.now().isoformat(timespec="seconds")
            self.drafts["items"][item_id] = new
            self.drafts["last_item"] = item_id
            self._save()
            return new

    def set_last(self, item_id):
        self._item(item_id)
        with self.lock:
            self.drafts["last_item"] = item_id
            self._save()

    def reveal(self, item_id) -> dict:
        it = self._item(item_id)
        with self.lock:
            d = self.drafts["items"].setdefault(item_id, clean_draft({}, None))
            if not d.get("ai_revealed_at"):
                d["ai_revealed_at"] = dt.datetime.now().isoformat(timespec="seconds")
                d["judgment_before_reveal"] = has_judgment(d)
            self._save()
        return {"flagged": it.ai_flagged, **it.ai, "revealed_at": d["ai_revealed_at"],
                "judgment_before_reveal": d.get("judgment_before_reveal")}

    def ai_flags(self) -> list[str]:
        with self.lock:
            self.drafts.setdefault("events", []).append(
                {"event": "ai_flags_shown", "at": dt.datetime.now().isoformat(timespec="seconds")})
            self._save()
        return [i for i in self.order if self.items[i].ai_flagged]

    def preview(self, item_id) -> dict:
        it = self._item(item_id)
        draft = self.drafts["items"].get(item_id) or {}
        rec, problems = build_record(draft, it, self.today())
        existing = self.recorded().get(item_id)
        if rec is None:
            return {"ok": False, "problems": problems, "existing": existing}
        m, h, dec, flagged = self._decisions(it.home)
        try:
            review.record_decision(dec, m, h, it.key, rec["decision"], self.reviewer, rec["date"], rec["comment"],
                                   replace=existing is not None, findings=_findings(rec), flagged=flagged)
        except ValueError as exc:
            return {"ok": False, "problems": [str(exc)], "existing": existing}
        shown = {"decision": rec["decision"], "reviewer": self.reviewer, **{k: v for k, v in rec.items() if k != "decision"}}
        return {"ok": True, "record": shown, "file": f"review/{it.home}_human_decisions.json", "article": it.key,
                "replace": existing is not None, "existing": existing,
                "fingerprint": fingerprint(rec, self.reviewer, existing is not None)}

    def record(self, item_id, fp, confirm) -> dict:
        if confirm is not True:
            raise WorkspaceError("explicit confirmation is required")
        it = self._item(item_id)
        with self.lock:
            draft = self.drafts["items"].get(item_id) or {}
            rec, problems = build_record(draft, it, self.today())
            if rec is None:
                raise WorkspaceError("; ".join(problems))
            existing = self.recorded().get(item_id)
            if not isinstance(fp, str) or fp != fingerprint(rec, self.reviewer, existing is not None):
                raise WorkspaceError("the draft changed after the preview; preview again and confirm")
            m, h, dec, flagged = self._decisions(it.home)
            try:
                new = review.record_decision(dec, m, h, it.key, rec["decision"], self.reviewer, rec["date"],
                                             rec["comment"], replace=existing is not None, findings=_findings(rec),
                                             flagged=flagged)
            except ValueError as exc:
                raise WorkspaceError(str(exc)) from exc
            _atomic_write(self._paths(it.home)[1], new)
            self.drafts.setdefault("events", []).append(
                {"event": "recorded", "item": item_id, "decision": rec["decision"],
                 "replace": existing is not None, "at": dt.datetime.now().isoformat(timespec="seconds")})
            self._save()
            return new["decisions"][it.key]


# ---------------------------------------------------------------- HTTP server (127.0.0.1 only)

def make_handler(ws: Workspace, token: str, page: str, port_ref: dict):
    class H(BaseHTTPRequestHandler):
        server_version = "atti-review"

        def log_message(self, *a):  # keep the terminal quiet; nothing sensitive is logged
            pass

        def _host_ok(self):
            port = port_ref["port"]
            return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                             "connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'none'; "
                             "frame-ancestors 'none'")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, {"error": "forbidden"})
            if self.path == f"/{token}/":
                return self._send(200, page, "text/html; charset=utf-8")
            if self.path == f"/{token}/api/state":
                try:
                    return self._send(200, ws.state())
                except WorkspaceError as exc:
                    return self._send(409, {"error": str(exc)})
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            if (not self._host_ok() or self.headers.get("X-ATTI-Token") != token
                    or not (self.headers.get("Content-Type") or "").startswith("application/json")):
                return self._send(403, {"error": "forbidden"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > 200_000:
                    return self._send(413, {"error": "too large"})
                body = json.loads(self.rfile.read(n) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self._send(400, {"error": "bad request"})
            route = self.path.removeprefix(f"/{token}/api/")
            try:
                if route == "draft":
                    return self._send(200, ws.save_draft(body.get("id"), body.get("draft")))
                if route == "last":
                    ws.set_last(body.get("id"))
                    return self._send(200, {"ok": True})
                if route == "reveal":
                    return self._send(200, ws.reveal(body.get("id")))
                if route == "ai-flags":
                    return self._send(200, {"items": ws.ai_flags()})
                if route == "preview":
                    return self._send(200, ws.preview(body.get("id")))
                if route == "record":
                    return self._send(200, {"recorded": ws.record(body.get("id"), body.get("fingerprint"),
                                                                  body.get("confirm"))})
            except WorkspaceError as exc:
                return self._send(409, {"error": str(exc)})
            return self._send(404, {"error": "not found"})

    return H


def serve(ws: Workspace, page_builder, port: int = 0):
    """Bind 127.0.0.1 only; every URL carries a fresh random token. Returns (server, url)."""
    token = secrets.token_urlsafe(24)
    port_ref = {"port": port}
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(ws, token, page_builder(token), port_ref))
    port_ref["port"] = srv.server_address[1]
    return srv, f"http://127.0.0.1:{port_ref['port']}/{token}/"


def json_for_script(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def render_page(items: list[Item], summary: dict, reviewer: str, token: str) -> str:
    from atti.workspace_page import CSS, JS

    data = {"items": [i.public() for i in items], "summary": summary, "reviewer": reviewer, "token": token,
            "sizes": SIZES, "criteria": CRITERIA}
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>ATTI Review Workspace</title><style>{CSS}</style></head><body>"
            f"<script id=\"data\" type=\"application/json\">{json_for_script(data)}</script>"
            "<div id=\"app\"><p style=\"padding:24px\">Loading…</p></div>"
            f"<script>{JS}</script></body></html>\n")
