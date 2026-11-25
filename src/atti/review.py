"""Human-validation materials for a corpus.

Three separate files, by design:
  review/<corpus>_ai_review.json         AI-generated notes + proposed status (committable)
  review/<corpus>_human_decisions.json   decisions recorded by a human (committable)
  data/review/<corpus>_review_sheet.md   full bilingual texts side by side (git-ignored)

Nothing here changes manifests, results or the selection. A decision binds
to one manifest version through ``manifest_sha256``.
"""

from __future__ import annotations

import collections
import datetime as dt
import html
import json
import re
from pathlib import Path

from atti.sources import UntrustedURLError, require_https_host, sha256_bytes

AI_STATUSES = ("PASS", "NEEDS_REVIEW", "FAIL")
HUMAN_DECISIONS = ("APPROVE", "REJECT", "REQUEST_EXAMINATION")
# every AI proposed status the review files may use (v1: AI_STATUSES; current_law_v2 adds the rest)
REVIEW_STATUSES = (*AI_STATUSES, "PROPOSED_PASS", "MISSING_SOURCE", "VERSION_MISMATCH")
_ARTICLE_KEY = re.compile(r"\d+(?:bis)?")
# Optional findings a human reviewer may record with a decision (all text is the reviewer's own).
EQUIVALENCE = ("EQUIVALENT", "MINOR_DIFFERENCES", "MATERIAL_DIFFERENCE")
SEVERITIES = ("MATERIAL", "MINOR")
ADJUDICATIONS = ("AGREE", "PARTLY_AGREE", "DISAGREE")
_DECISION_FIELDS = ("decision", "reviewer", "date", "comment")
FINDING_FIELDS = ("review_period", "equivalence", "terminology", "discrepancies", "ai_adjudication")
# Whole-word AI markers. A reviewer may use a stable pseudonym; a civil name is never required.
_NOT_HUMAN = re.compile(r"\b(?:llm|chatgpt|copilot|bot|gpt[\w.-]*|deepseek[\w.-]*|gemini[\w.-]*"
                        r"|claude[\s_-]*(?:opus|sonnet|haiku|fable|\d)[\w.-]*"
                        r"|ai[\s_-]*(?:agent|assistant|system|model|reviewer|bot))\b|\(\s*ai\b"
                        r"|^\s*(?:ai|claude|assistant)\s*$",  # bare names are ambiguous: add a surname or handle
                        re.IGNORECASE)

INSTRUCTIONS = [
    "Open the review sheet (data/review/<corpus>_review_sheet.md) and read each pair side by side.",
    "For each article, edit review/<corpus>_human_decisions.json and set decision to APPROVE, REJECT "
    "or REQUEST_EXAMINATION, with your name in reviewer, the ISO date (YYYY-MM-DD) in date, and a "
    "comment (required for REJECT and REQUEST_EXAMINATION).",
    "The AI notes and proposed statuses are advisory; your decision is independent of them.",
    "Run `uv run atti review-sheet` to validate the file and refresh the sheet. Decisions are only valid "
    "for the manifest version whose SHA-256 is recorded in the file.",
    "Rejections do not change the corpus automatically: excluding an article requires a separate, "
    "reported change (selection.EXCLUDED + re-selection), which changes the expanded results.",
]


def keys(manifest: dict) -> list[str]:
    """Article keys as strings ("4", "79bis"); historical manifests use integer ``article``."""
    return [str(e.get("key", e.get("article"))) for e in manifest["articles"]]


def _sort(k: str):
    m = re.match(r"\d+", k)
    return (int(m.group()) if m else 0, k)


def manifest_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def decisions_template(corpus: str, manifest: dict, manifest_hash: str) -> dict:
    return {
        "corpus": corpus,
        "manifest_sha256": manifest_hash,
        "kind": "HUMAN decisions only. Do not fill in on behalf of a human; AI notes live in the "
                "separate *_ai_review.json file.",
        "allowed_decisions": list(HUMAN_DECISIONS),
        "instructions": INSTRUCTIONS,
        "decisions": {k: {"decision": None, "reviewer": None, "date": None, "comment": ""}
                      for k in keys(manifest)},
    }


def flagged_articles(ai: dict) -> list[str]:
    """Articles the AI review flagged: any status other than a pass, plus its priority list."""
    flagged = [str(k) for k, v in ai["articles"].items() if v["proposed_status"] not in ("PASS", "PROPOSED_PASS")]
    flagged += [str(k) for k in ai.get("priority_for_human", []) if str(k) not in flagged]
    return sorted(flagged, key=_sort)


def parse_review_period(value: str) -> tuple[dt.date, dt.date]:
    """``YYYY-MM-DD`` or ``YYYY-MM-DD/YYYY-MM-DD`` (ISO 8601 interval): when the review itself took place."""
    parts = value.split("/")
    if len(parts) not in (1, 2):
        raise ValueError(value)
    start, end = dt.date.fromisoformat(parts[0]), dt.date.fromisoformat(parts[-1])
    if end < start:
        raise ValueError(value)
    return start, end


def _check_findings(n: str, d: dict, flagged) -> list[str]:
    e = []
    unknown = set(d) - set(_DECISION_FIELDS) - set(FINDING_FIELDS)
    if unknown:
        e.append(f"Article {n}: unknown fields {sorted(unknown)}")
    present = [f for f in FINDING_FIELDS if d.get(f) not in (None, "", [])]
    if d.get("decision") is None:
        return e + ([f"Article {n}: findings {present} need a recorded decision"] if present else [])
    if d.get("review_period") is not None:
        try:
            _, end = parse_review_period(d["review_period"])
            if end > dt.date.fromisoformat(d.get("date") or ""):
                e.append(f"Article {n}: review_period must not end after the recording date")
        except (ValueError, TypeError, AttributeError):
            e.append(f"Article {n}: review_period must be YYYY-MM-DD or YYYY-MM-DD/YYYY-MM-DD, start <= end")
    eq = d.get("equivalence")
    if eq is not None and eq not in EQUIVALENCE:
        e.append(f"Article {n}: equivalence must be one of {EQUIVALENCE}")
    if d.get("terminology") is not None and not isinstance(d["terminology"], str):
        e.append(f"Article {n}: terminology must be text")
    disc = d.get("discrepancies") or []
    if not isinstance(disc, list) or any(
            not isinstance(x, dict) or set(x) != {"severity", "note"} or x["severity"] not in SEVERITIES
            or not isinstance(x["note"], str) or not x["note"].strip() for x in disc):
        e.append(f"Article {n}: discrepancies must be a list of {{severity: {'|'.join(SEVERITIES)}, note: text}}")
    else:
        sev = {x["severity"] for x in disc}
        if "MATERIAL" in sev and eq != "MATERIAL_DIFFERENCE":
            e.append(f"Article {n}: a MATERIAL discrepancy requires equivalence MATERIAL_DIFFERENCE")
        if eq == "MATERIAL_DIFFERENCE" and "MATERIAL" not in sev:
            e.append(f"Article {n}: MATERIAL_DIFFERENCE requires at least one MATERIAL discrepancy")
        if eq == "EQUIVALENT" and sev:
            e.append(f"Article {n}: EQUIVALENT cannot list discrepancies; use MINOR_DIFFERENCES")
        if eq == "MATERIAL_DIFFERENCE" and not (d.get("comment") or "").strip():
            e.append(f"Article {n}: justify the decision in comment when there is a material difference")
    adj = d.get("ai_adjudication")
    if adj is not None and (not isinstance(adj, dict) or set(adj) != {"verdict", "note"}
                            or adj["verdict"] not in ADJUDICATIONS
                            or not isinstance(adj["note"], str) or not adj["note"].strip()):
        e.append(f"Article {n}: ai_adjudication must be {{verdict: {'|'.join(ADJUDICATIONS)}, note: text}}")
    if str(n) in flagged and adj is None:
        e.append(f"Article {n}: flagged by the AI review, so ai_adjudication is required")
    return e


def validate_decisions(dec: dict, manifest: dict, manifest_hash: str, flagged=()) -> list[str]:
    """Return a list of problems (empty if the file is valid; undecided entries are valid).
    ``flagged``: articles the AI review flagged; a decision on one must carry the human's adjudication."""
    errors = []
    flagged = {str(k) for k in flagged}
    if dec.get("manifest_sha256") != manifest_hash:
        errors.append("manifest_sha256 does not match the current manifest: decisions refer to another version")
    expected = set(keys(manifest))
    got = set(dec.get("decisions", {}))
    if got != expected:
        errors.append(f"articles missing {sorted(expected - got, key=_sort)} / unexpected {sorted(got - expected, key=_sort)}")
    for n, d in sorted(dec.get("decisions", {}).items(), key=lambda kv: _sort(kv[0])):
        errors += _check_findings(n, d, flagged)
        if d.get("decision") is None:
            continue
        if d["decision"] not in HUMAN_DECISIONS:
            errors.append(f"Article {n}: decision must be one of {HUMAN_DECISIONS}")
        reviewer = (d.get("reviewer") or "").strip()
        if not reviewer:
            errors.append(f"Article {n}: reviewer name required")
        elif _NOT_HUMAN.search(reviewer):
            errors.append(f"Article {n}: reviewer must be a human, not an AI system")
        try:
            dt.date.fromisoformat(d.get("date") or "")
        except ValueError:
            errors.append(f"Article {n}: date must be YYYY-MM-DD")
        if d["decision"] != "APPROVE" and not (d.get("comment") or "").strip():
            errors.append(f"Article {n}: comment required for {d['decision']}")
    return errors


def summarize(ai: dict, dec: dict) -> dict:
    ai_counts = {s: 0 for s in AI_STATUSES} if not any(
        v["proposed_status"] == "PROPOSED_PASS" for v in ai["articles"].values()) else {}
    for st, n in sorted(collections.Counter(v["proposed_status"] for v in ai["articles"].values()).items()):
        ai_counts[st] = ai_counts.get(st, 0) + n
    human = {k: 0 for k in (*HUMAN_DECISIONS, "UNDECIDED")}
    for d in dec["decisions"].values():
        human[d["decision"] or "UNDECIDED"] += 1
    return {"ai_proposed": ai_counts, "human": human,
            "fully_human_approved": human["APPROVE"] == len(dec["decisions"])}


def _findings_text(d: dict) -> list[str]:
    out = []
    if d.get("review_period"):
        out.append(f"reviewed {d['review_period']}")
    if d.get("equivalence"):
        out.append(f"equivalence {d['equivalence']}")
    for x in d.get("discrepancies") or []:
        out.append(f"{x['severity']} discrepancy: {x['note']}")
    if d.get("terminology"):
        out.append(f"terminology: {d['terminology']}")
    if d.get("ai_adjudication"):
        out.append(f"AI flag {d['ai_adjudication']['verdict']}: {d['ai_adjudication']['note']}")
    return out


def _human_cell(d: dict) -> str:
    if d["decision"] is None:
        return "_not recorded_"
    return (f"**{d['decision']}** by {d['reviewer']}, recorded {d['date']}" + (f": {d['comment']}" if d["comment"] else "")
            + "".join(f"; {x}" for x in _findings_text(d)))


def render_sheet(manifest: dict, pairs, parts: dict[int, int], ai: dict, dec: dict, errors: list[str]) -> str:
    by_num = dict(zip(keys(manifest), manifest["articles"]))
    s = summarize(ai, dec)
    L = [f"# ATTI {manifest['corpus']}: bilingual review sheet\n",
         "> **AI-assisted review material, NOT human-approved.** Proposed statuses and notes were "
         f"generated by {ai['reviewer']}. {ai.get('independence_caveat', '')} Human decisions are read from "
         "`review/" + manifest["corpus"] + "_human_decisions.json`.\n",
         "> Local file under git-ignored `data/`: it contains full legal texts and must not be "
         "committed or redistributed.\n",
         f"- Manifest SHA-256: `{dec['manifest_sha256']}`",
         f"- AI proposed: {s['ai_proposed']}",
         f"- Human decisions: {s['human']}"]
    if errors:
        L.append("- **Decision file problems:** " + "; ".join(errors))
    L += ["", "## How to record human decisions\n"] + [f"{i}. {t}" for i, t in enumerate(INSTRUCTIONS, 1)]
    L += ["", "## Status criteria (AI proposal)\n"] + [f"- **{k}**: {v}" for k, v in (ai.get("status_criteria") or ai.get("status_categories", {})).items()]
    L += ["", "## Discrepancies that could materially undermine equivalence\n",
          "Only these items; style-level differences are in the per-article notes.\n"]
    L += [f"- **Article {d['article']}**: {d['issue']}" for d in ai["material_discrepancies"]]
    L += [f"\n{ai.get('no_fail_found', '')}\n", "## Overview\n",
          "| ID | Art. | Part | AR chars | EN chars | AI proposed | Human decision |",
          "|---|---:|---:|---:|---:|---|---|"]
    for p in pairs:
        e, a = by_num[str(p.article)], ai["articles"][str(p.article)]
        L.append(f"| {e['id']} | {p.article} | {parts[p.article]} | {e['ar_chars']} | {e['en_chars']} | "
                 f"{a['proposed_status']} | {_human_cell(dec['decisions'][str(p.article)])} |")
    L.append("\n## Pairs\n")
    for p in pairs:
        e, a = by_num[str(p.article)], ai["articles"][str(p.article)]
        L += [f"### {e['id']}: Article {p.article} (Part {parts[p.article]}), AI proposed {a['proposed_status']}\n",
              f"- AI evidence: {a['evidence']}",
              f"- Human decision: {_human_cell(dec['decisions'][str(p.article)])}",
              f"- Text SHA-256: AR `{e['ar_sha256'][:16]}…`, EN `{e['en_sha256'][:16]}…`\n",
              "<table><tr><th>Arabic (governing text)</th><th>English (official translation)</th></tr>",
              f'<tr><td dir="rtl" lang="ar" valign="top">{html.escape(p.ar_text)}</td>'
              f'<td lang="en" valign="top">{html.escape(p.en_text)}</td></tr></table>\n']
    return "\n".join(L)


def write_json_new(path: Path, data: dict) -> bool:
    """Write only if the file does not exist (never overwrite recorded decisions)."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def record_decision(dec: dict, manifest: dict, manifest_hash: str, article: int, decision: str,
                    reviewer: str, date: str, comment: str, replace: bool = False,
                    findings: dict | None = None, flagged=()) -> dict:
    """Return an updated copy of ``dec``; raise ValueError (file untouched) on any problem."""
    import copy

    key = str(article)
    if key not in dec.get("decisions", {}):
        raise ValueError(f"Article {article} is not in this corpus")
    if dec["decisions"][key]["decision"] is not None and not replace:
        raise ValueError(f"Article {article} already has a recorded decision "
                         f"({dec['decisions'][key]['decision']}); pass --replace to change it")
    new = copy.deepcopy(dec)
    new["decisions"][key] = {"decision": decision, "reviewer": reviewer, "date": date, "comment": comment,
                             **{k: v for k, v in (findings or {}).items() if v not in (None, "", [])}}
    errors = validate_decisions(new, manifest, manifest_hash, flagged)
    if errors:
        raise ValueError("; ".join(errors))
    return new


_CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1f;--muted:#6b6b70;--card:#fff;--line:#e3e1dc;--accent:#2f5d8a;
--flag:#b45309;--flagbg:#fff7ed;--pass:#2f7d4f;--warn:#b45309;--fail:#b3261e;--code:#f2f1ed}
@media (prefers-color-scheme:dark){:root{--bg:#161618;--fg:#ececee;--muted:#a1a1a6;--card:#1f1f22;
--line:#333338;--accent:#8ab4e0;--flag:#f0a35e;--flagbg:#2a2116;--pass:#6cc58d;--warn:#f0a35e;
--fail:#f28b82;--code:#2a2a2e}}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:12px}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Helvetica Neue",sans-serif}
.layout{display:grid;grid-template-columns:230px 1fr;min-height:100vh}
nav{position:sticky;top:0;height:100vh;overflow:auto;padding:16px;border-right:1px solid var(--line);font-size:14px}
nav h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:16px 0 6px}
nav a{display:flex;justify-content:space-between;padding:3px 8px;border-radius:6px;color:var(--fg);text-decoration:none}
nav a:hover{background:var(--code)}nav a.flag{color:var(--flag);font-weight:600}
main{padding:24px 32px 80px;max-width:1280px}
.banner{border:1px solid var(--flag);background:var(--flagbg);border-radius:10px;padding:12px 16px;margin-bottom:16px}
.meta{color:var(--muted);font-size:14px}
.flaglist a{display:inline-block;margin:4px 8px 4px 0;padding:4px 10px;border-radius:999px;border:1px solid var(--flag);color:var(--flag);text-decoration:none;font-weight:600}
article{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:18px 0}
article.flagged{border:2px solid var(--flag);box-shadow:0 0 0 4px var(--flagbg)}
article header{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;justify-content:space-between}
article h3{margin:0;font-size:20px}
.badge{font-size:12px;font-weight:700;padding:2px 8px;border-radius:999px;border:1px solid currentColor}
.PASS,.PROPOSED_PASS{color:var(--pass)}.NEEDS_REVIEW{color:var(--warn)}.FAIL{color:var(--fail)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:14px 0}
.cols>div{border-top:3px solid var(--line);padding-top:8px}
.cols h4{margin:0 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.ar{font-family:"Geeza Pro","Noto Naskh Arabic","Arial",sans-serif;font-size:20px;line-height:2}
.notes{background:var(--code);border-radius:8px;padding:10px 12px;font-size:14px}
.issue{color:var(--flag);font-weight:600}
.recorded{font-size:14px;margin:10px 0}
fieldset{border:1px dashed var(--line);border-radius:8px;margin:12px 0 0;padding:10px 12px}
legend{font-size:12px;color:var(--muted);padding:0 4px}
fieldset label{margin-right:16px;font-size:14px;white-space:nowrap}
textarea,input[type=text]{width:100%;font:inherit;font-size:14px;padding:6px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
.cmd{display:flex;gap:8px;margin-top:8px}.cmd input{font-family:ui-monospace,Menlo,monospace;font-size:12px}
button{font:inherit;font-size:13px;padding:4px 12px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
.pager{display:flex;justify-content:space-between;font-size:13px;margin-top:10px}.pager a{color:var(--accent)}
code{background:var(--code);padding:1px 5px;border-radius:4px;font-size:13px}
@media (max-width:900px){.layout{grid-template-columns:1fr}nav{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}
.cols{grid-template-columns:1fr}main{padding:16px}}
"""

_JS = """
function q(s){return "'"+String(s).replace(/'/g,"'\\\\''")+"'";}
function build(n){
  const d=document.querySelector('input[name="d'+n+'"]:checked');
  const r=document.getElementById('reviewer').value.trim();
  const c=document.getElementById('c'+n).value.trim();
  const out=document.getElementById('cmd'+n);
  if(!d){out.value='Choose a draft decision above to build the command';return;}
  let cmd='uv run atti decide '+n+' '+d.value+' --reviewer '+q(r||'YOUR NAME');
  if(CORPUS!=='expanded_v1') cmd+=' --corpus '+CORPUS;
  if(c) cmd+=' --comment '+q(c);
  out.value=cmd;
}
function copyCmd(n){const o=document.getElementById('cmd'+n);o.select();
  try{document.execCommand('copy');}catch(e){}
  if(navigator.clipboard){navigator.clipboard.writeText(o.value).catch(()=>{});}}
document.addEventListener('input',e=>{
  if(e.target.id==='reviewer'){document.querySelectorAll('[data-n]').forEach(a=>build(a.dataset.n));}
  else if(e.target.dataset.for){build(e.target.dataset.for);}});
"""


def check_review_inputs(ai: dict, article_keys) -> None:
    """Article keys and AI proposed statuses end up in HTML attributes and scripts: allow only known values."""
    for k in article_keys:
        if not _ARTICLE_KEY.fullmatch(str(k)):
            raise ValueError(f"unexpected article key {str(k)!r}")
        st = ai["articles"].get(str(k), {}).get("proposed_status")
        if st not in REVIEW_STATUSES:
            raise ValueError(f"Article {k}: unknown AI proposed status {st!r}")


def source_links(ar_pages, en_url: str | None, ar_html_url: str | None) -> str:
    """Escaped source line for the review page; only official HRSD HTTPS URLs become links."""
    from atti.hrsd import HOST

    def link(label, url):
        if not url:
            return html.escape(f"{label}: none")
        try:
            require_https_host(url, HOST)
        except UntrustedURLError:
            return html.escape(f"{label}: unexpected URL withheld")
        return f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'

    pages = ", ".join(str(int(p)) for p in ar_pages)
    return f"Arabic PDF p. {pages} · {link('English page', en_url)} · {link('Arabic HTML page', ar_html_url)}"


def render_html(manifest: dict, pairs, parts: dict, ai: dict, dec: dict, errors: list[str],
                flagged: list, sources: dict | None = None) -> str:
    """Local, self-contained review page. It never saves anything: decision
    controls are drafts that only build an `atti decide` command. ``sources`` values are trusted
    HTML built by ``source_links``."""
    esc = html.escape
    check_review_inputs(ai, [*(p.article for p in pairs), *flagged])
    by_num = dict(zip(keys(manifest), manifest["articles"]))
    issues = {str(d["article"]): d["issue"] for d in ai["material_discrepancies"]}
    flagged = [str(f) for f in flagged]
    sources = sources or {}
    parts = {str(k): v for k, v in parts.items()}
    s = summarize(ai, dec)
    order = [str(p.article) for p in pairs]
    nav = ['<nav><h2>Flagged for closer examination</h2>']
    nav += [f'<a class="flag" href="#a{n}">Article {n}<span>⚑</span></a>' for n in flagged]
    nav.append(f'<h2>All {len(pairs)} articles</h2>')
    for n in order:
        st = ai["articles"][str(n)]["proposed_status"]
        rec = dec["decisions"][str(n)]["decision"]
        mark = "⚑" if n in flagged else ("✓" if rec == "APPROVE" else "")
        nav.append(f'<a class="{"flag" if n in flagged else ""}" href="#a{n}">Article {n}'
                   f'<span class="{st}" title="AI proposed {st}">{mark or "·"}</span></a>')
    nav.append("</nav>")
    body = [
        f'<h1>ATTI {esc(manifest["corpus"])}: bilingual review ({len(pairs)} articles)</h1>',
        '<div class="banner"><strong>Reading and drafting page: nothing on this page is saved.</strong> '
        'The authoritative record is <code>review/' + esc(manifest["corpus"]) + '_human_decisions.json</code>. '
        'To record a decision, choose a draft below, copy the generated command and run it in the '
        'repository: <code>atti decide</code> validates it and refuses to overwrite an existing '
        'decision unless you add <code>--replace</code>. AI statuses and notes are advisory only and '
        'are <strong>not</strong> human approval.</div>',
        f'<p class="meta">Manifest SHA-256 <code>{esc(dec["manifest_sha256"][:16])}…</code> · AI proposed: '
        + esc(", ".join(f"{k} {v}" for k, v in s["ai_proposed"].items()))
        + " · Recorded human decisions: "
        + esc(", ".join(f"{k} {v}" for k, v in s["human"].items())) + "</p>",
    ]
    if errors:
        body.append('<div class="banner"><strong>Decision file problems:</strong> '
                    + esc("; ".join(errors)) + "</div>")
    body += ['<p><label>Your name or a stable pseudonym (used only to build commands; not stored): '
             '<input type="text" id="reviewer" autocomplete="off" placeholder="e.g. a GitHub handle"></label></p>',
             '<div class="flaglist">Jump to flagged: '
             + "".join(f'<a href="#a{n}">Article {n}</a>' for n in flagged) + "</div>"]
    for i, p in enumerate(pairs):
        n = str(p.article)
        e, a = by_num[n], ai["articles"][n]
        rec = dec["decisions"][n]
        recorded = ("<em>No human decision recorded.</em>" if rec["decision"] is None else
                    f'<strong>Recorded: {esc(rec["decision"])}</strong> by {esc(rec["reviewer"])} on '
                    f'{esc(rec["date"])}' + (f": {esc(rec['comment'])}" if rec["comment"] else "")
                    + "".join(f"<br>{esc(x)}" for x in _findings_text(rec)))
        radios = "".join(
            f'<label><input type="radio" name="d{n}" value="{d}" data-for="{n}"> {d}</label>'
            for d in HUMAN_DECISIONS)
        prev_a = f'<a href="#a{order[i-1]}">← Article {order[i-1]}</a>' if i else "<span></span>"
        next_a = f'<a href="#a{order[i+1]}">Article {order[i+1]} →</a>' if i + 1 < len(order) else "<span></span>"
        body.append(
            f'<article id="a{n}" class="{"flagged" if n in flagged else ""}">'
            f'<header><h3>{"⚑ " if n in flagged else ""}Article {n} <span class="meta">· {esc(e["id"])} · '
            f'Part {esc(str(parts[n]))} · {esc(str(e["ar_chars"]))} AR / {esc(str(e["en_chars"]))} EN chars</span></h3>'
            f'<span class="badge {esc(a["proposed_status"])}">AI proposed: {esc(a["proposed_status"])}</span></header>'
            + (f'<p class="issue">Possible material discrepancy: {esc(issues[n])}</p>' if n in issues else "")
            + (f'<p class="meta">Sources: {sources[n]}</p>' if n in sources else "")
            + '<div class="cols">'
            f'<div lang="en" dir="ltr"><h4>English · official translation</h4>{esc(p.en_text)}</div>'
            f'<div lang="ar" dir="rtl" class="ar"><h4 dir="ltr" style="text-align:right">'
            f'Arabic · original (governing)</h4>{esc(p.ar_text)}</div></div>'
            f'<div class="notes"><strong>AI review note</strong> (advisory): {esc(a["evidence"])}</div>'
            f'<p class="recorded">{recorded}</p>'
            f'<fieldset data-n="{n}"><legend>Draft decision for Article {n}: NOT saved by this page</legend>'
            f'{radios}<p><textarea id="c{n}" rows="2" data-for="{n}" '
            f'placeholder="Comment (required for REJECT and REQUEST_EXAMINATION)"></textarea></p>'
            f'<div class="cmd"><input type="text" id="cmd{n}" readonly '
            f'value="Choose a draft decision above to build the command">'
            f'<button type="button" onclick="copyCmd(\'{n}\')">Copy</button></div></fieldset>'
            f'<div class="pager">{prev_a}<a href="#top">↑ Top</a>{next_a}</div></article>')
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>ATTI Review {esc(manifest['corpus'])}</title><style>{_CSS}</style></head>"
            f"<script>const CORPUS={json.dumps(manifest['corpus'])};</script>"
            f'<body id="top"><div class="layout">{"".join(nav)}<main>{"".join(body)}</main></div>'
            f"<script>{_JS}</script></body></html>\n")
