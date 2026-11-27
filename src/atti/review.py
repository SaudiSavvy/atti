"""Human-validation materials for a corpus.

Three separate files, by design:
  review/<corpus>_ai_review.json         AI-generated notes + proposed status (committable)
  review/<corpus>_human_decisions.json   decisions recorded by a human (committable)
  data/review/<corpus>_review_sheet.md   full bilingual texts side by side (git-ignored)

Decisions are recorded with ``atti decide`` or in the local review workspace (``atti.workspace``).

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

from atti.sources import sha256_bytes, write_atomic

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


def save_json(path: Path, data: dict) -> None:
    """Write a decision (or drafts) file atomically, in the repository's JSON layout."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(path, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


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


def check_review_inputs(ai: dict, article_keys) -> None:
    """Article keys and AI proposed statuses are written into the review sheet: allow only known values."""
    for k in article_keys:
        if not _ARTICLE_KEY.fullmatch(str(k)):
            raise ValueError(f"unexpected article key {str(k)!r}")
        st = ai["articles"].get(str(k), {}).get("proposed_status")
        if st not in REVIEW_STATUSES:
            raise ValueError(f"Article {k}: unknown AI proposed status {st!r}")
