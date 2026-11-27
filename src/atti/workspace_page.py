"""Static CSS and JavaScript for the local review workspace page (see ``atti.workspace``).

The page builds every element with textContent / DOM APIs: no legal or reviewer text is parsed as HTML."""

CSS = r"""
:root{--bg:#f7f6f2;--fg:#1c1c1e;--muted:#68686e;--card:#fff;--line:#e2e0da;--soft:#f0eee9;
--accent:#2f5d8a;--accentbg:#e8eff6;--ok:#2f7d4f;--okbg:#e6f3eb;--warn:#a15c07;--warnbg:#fdf3e4;
--bad:#b3261e;--badbg:#fbeae8;--ai:#6b4fa3;--aibg:#f1ecf9}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececee;--muted:#a3a3a8;--card:#1d1d20;
--line:#323236;--soft:#26262a;--accent:#8ab4e0;--accentbg:#1d2a38;--ok:#6cc58d;--okbg:#17291f;
--warn:#f0a35e;--warnbg:#2c2216;--bad:#f28b82;--badbg:#2e1b1a;--ai:#b9a2e8;--aibg:#251f33}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Helvetica Neue",Segoe UI,sans-serif}
button,select,input,textarea{font:inherit;color:inherit}
button{cursor:pointer;border:1px solid var(--line);background:var(--card);border-radius:7px;padding:5px 12px}
button:hover{border-color:var(--accent)}button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
button.danger{border-color:var(--bad);color:var(--bad)}button:disabled{opacity:.45;cursor:not-allowed}
.top{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:10px 18px;display:flex;flex-wrap:wrap;gap:14px 24px;align-items:center}
.top h1{font-size:16px;margin:0}.top .who{color:var(--muted);font-size:13px}
.prog{display:flex;gap:16px;flex-wrap:wrap;flex:1}
.pg{min-width:150px;font-size:12px;color:var(--muted)}.pg b{color:var(--fg)}
.bar{height:6px;border-radius:4px;background:var(--soft);overflow:hidden;display:flex;margin-top:3px}
.bar i{display:block;height:100%}.bar .r{background:var(--ok)}.bar .d{background:var(--warn);opacity:.6}
.save{font-size:12px;color:var(--muted);min-width:90px;text-align:right}
.layout{display:grid;grid-template-columns:270px 1fr;min-height:calc(100vh - 60px)}
aside{border-right:1px solid var(--line);padding:12px;position:sticky;top:60px;height:calc(100vh - 60px);overflow:auto;font-size:13px}
aside select{width:100%;padding:5px;border:1px solid var(--line);border-radius:7px;background:var(--card)}
.chips{display:flex;flex-wrap:wrap;gap:5px;margin:8px 0}
.chip{font-size:12px;padding:2px 9px;border-radius:999px}.chip.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.list a{display:flex;justify-content:space-between;gap:6px;padding:4px 8px;border-radius:6px;color:var(--fg);text-decoration:none}
.list a:hover{background:var(--soft)}.list a.cur{background:var(--accentbg);font-weight:600}
.list .c{color:var(--muted);font-size:11px}.list .m{width:18px;text-align:center}
.aiflag{color:var(--ai)}
main{padding:18px 26px 120px;max-width:1300px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin-bottom:16px}
.hdr{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:baseline}
.hdr h2{margin:0;font-size:22px}
.tag{font-size:12px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);color:var(--muted)}
.tag.rec{color:var(--ok);border-color:var(--ok);background:var(--okbg)}.tag.dr{color:var(--warn);border-color:var(--warn);background:var(--warnbg)}
.meta{font-size:13px;color:var(--muted);margin:6px 0}.meta a{color:var(--accent)}
.verified{color:var(--ok)}code{font:12px ui-monospace,Menlo,monospace;background:var(--soft);padding:1px 5px;border-radius:4px}
.related{background:var(--warnbg);border:1px solid var(--warn);border-radius:8px;padding:6px 10px;font-size:13px;margin-top:8px}
.related a{color:var(--accent);cursor:pointer}
.texts{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.texts>div{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 18px}
.texts h3{margin:0 0 8px;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.ar{font-family:"Geeza Pro","Noto Naskh Arabic","Amiri","Arial",sans-serif;font-size:21px;line-height:2.05;text-align:right}
.en{font-size:16px;line-height:1.7}
.txt{white-space:pre-wrap;overflow-wrap:anywhere}
fieldset{border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:0 0 12px}
legend{font-weight:600;padding:0 6px}
.crit{display:grid;grid-template-columns:250px 1fr;gap:6px 14px;align-items:start;padding:8px 0;border-top:1px dashed var(--line)}
.crit:first-of-type{border-top:0}.crit .lbl{font-weight:600}.crit .lbl small{display:block;font-weight:400;color:var(--muted)}
.opts{display:flex;flex-wrap:wrap;gap:6px}
.opts label{border:1px solid var(--line);border-radius:7px;padding:3px 10px;cursor:pointer;font-size:13px}
.opts input{margin:0 5px 0 0}.opts label:has(input:checked){border-color:var(--accent);background:var(--accentbg)}
textarea,input[type=text]{width:100%;padding:6px 8px;border:1px solid var(--line);border-radius:7px;background:var(--bg)}
textarea{min-height:52px;resize:vertical}
.hint{font-size:12px;color:var(--muted);margin:4px 0}
.disc{display:grid;grid-template-columns:150px 1fr auto;gap:6px;margin:6px 0}
.ai{border:1px solid var(--ai);background:var(--aibg);border-radius:10px;padding:10px 14px;margin-bottom:12px}
.ai h3{margin:0 0 6px;font-size:14px;color:var(--ai)}.ai dl{margin:6px 0}.ai dt{font-size:12px;color:var(--muted)}.ai dd{margin:0 0 8px}
.rec{border:1px solid var(--accent);border-radius:10px;padding:10px 14px}
.rec pre{background:var(--soft);padding:10px;border-radius:8px;white-space:pre-wrap;font-size:12px;overflow-wrap:anywhere}
.problems{color:var(--bad);font-size:13px;margin:6px 0;padding-left:18px}
.ok{color:var(--ok)}.nav{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
.banner{background:var(--accentbg);border:1px solid var(--accent);border-radius:10px;padding:8px 12px;font-size:13px;margin-bottom:14px}
@media (max-width:980px){.layout{grid-template-columns:1fr}aside{position:static;height:auto;border-right:0;border-bottom:1px solid var(--line)}
.texts{grid-template-columns:1fr}.crit{grid-template-columns:1fr}main{padding:14px 16px 100px}.list{max-height:240px;overflow:auto}}
"""

JS = r"""
(() => {
const D = JSON.parse(document.getElementById('data').textContent);
const ITEMS = D.items, BY = Object.fromEntries(ITEMS.map(i => [i.id, i]));
const CRIT = D.criteria;
const ASSESS = {terminology: ['Accurate', 'Minor issue', 'Material issue'],
  completeness: ['Complete', 'Minor issue', 'Material issue'],
  consistency: ['Consistent', 'Minor issue', 'Material issue']};
const ASSESS_V = ['OK', 'MINOR_ISSUE', 'MATERIAL_ISSUE'];
const HINT = {terminology: 'Are legal terms rendered accurately and consistently?',
  completeness: 'Are all clauses, conditions, list items and qualifiers present in both?',
  consistency: 'Do numbers, periods, percentages, exceptions and cross-references agree?'};
let S = {drafts: {}, recorded: {}, last_item: null};
let cur = null, filter = {corpus: 'all', status: 'all'}, aiFlags = null, aiCache = {}, saveTimer = null, preview = null;

function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'text') e.textContent = v;
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false)
    e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
}
async function api(path, body) {
  const r = await fetch(path === 'state' ? 'api/state' : 'api/' + path, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-ATTI-Token': D.token},
    body: JSON.stringify(body)});
  const j = await r.json().catch(() => ({error: 'bad response'}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
const blank = () => ({equivalence: null, decision: null, comment: '', notes: '', flag: false,
  terminology: {assessment: null, note: ''}, completeness: {assessment: null, note: ''},
  consistency: {assessment: null, note: ''}, discrepancies: [], ai_adjudication: {verdict: null, note: ''}});
const draftOf = id => S.drafts[id] || (S.drafts[id] = blank());
function judged(d) { return !!(d && (d.equivalence || d.decision || Object.keys(CRIT).some(c => d[c] && d[c].assessment))); }
function status(id) {
  if (S.recorded[id]) return 'recorded';
  const d = S.drafts[id];
  return judged(d) || (d && (d.notes || d.comment)) ? 'draft' : 'unreviewed';
}
function mark(id) {
  const st = status(id), d = S.drafts[id] || {};
  const r = S.recorded[id];
  let m = st === 'recorded' ? (r.decision === 'APPROVE' ? '✓' : r.decision === 'REJECT' ? '✗' : '?') : st === 'draft' ? '◐' : '·';
  return m + (d.flag ? '★' : '');
}
function members(i) { return i.members.map(m => m.corpus); }

function progress() {
  const wrap = el('div', {class: 'prog'});
  const groups = [['pilot', 'Pilot'], ['expanded_v1', 'Expanded v1'], ['current_law_v2', 'Current Law v2'], ['all', 'Distinct pairs']];
  for (const [c, label] of groups) {
    const its = c === 'all' ? ITEMS : ITEMS.filter(i => members(i).includes(c));
    const n = c === 'all' ? its.length : D.sizes[c];
    const r = its.filter(i => status(i.id) === 'recorded').length, d = its.filter(i => status(i.id) === 'draft').length;
    wrap.append(el('div', {class: 'pg', title: `${r} recorded, ${d} in progress, ${n - r - d} not started`},
      el('div', {}, label, ': ', el('b', {}, `${r}/${n}`), ` recorded · ${d} in progress`),
      el('div', {class: 'bar'}, el('i', {class: 'r', style: `width:${100 * r / n}%`}), el('i', {class: 'd', style: `width:${100 * d / n}%`}))));
  }
  return wrap;
}
function visible() {
  return ITEMS.filter(i => {
    if (filter.corpus !== 'all' && !members(i).includes(filter.corpus)) return false;
    const st = status(i.id), d = S.drafts[i.id] || {};
    switch (filter.status) {
      case 'unreviewed': return st === 'unreviewed';
      case 'draft': return st === 'draft';
      case 'recorded': return st === 'recorded';
      case 'flag': return !!d.flag || (S.recorded[i.id] && S.recorded[i.id].decision === 'REQUEST_EXAMINATION') || d.decision === 'REQUEST_EXAMINATION';
      case 'ai': return aiFlags && aiFlags.includes(i.id);
      default: return true;
    }
  });
}
function go(id) { flush(); cur = id; preview = null; api('last', {id}).catch(() => {}); render(); window.scrollTo(0, 0); }
function nextOf(pred, dir = 1) {
  const v = visible(); const ix = v.findIndex(i => i.id === cur);
  for (let k = 1; k <= v.length; k++) { const i = v[(ix + dir * k + v.length * 2) % v.length]; if (pred(i)) return i.id; }
  return null;
}

function sidebar() {
  const corpusSel = el('select', {onchange: e => { filter.corpus = e.target.value; render(); }},
    ...[['all', 'All corpora'], ['pilot', 'Pilot (10)'], ['expanded_v1', 'Expanded v1 (30)'], ['current_law_v2', 'Current Law v2 (100)']]
      .map(([v, l]) => el('option', {value: v, selected: filter.corpus === v}, l)));
  const chips = el('div', {class: 'chips'});
  for (const [v, l] of [['all', 'All'], ['unreviewed', 'Not started'], ['draft', 'In progress'], ['recorded', 'Recorded'], ['flag', 'Flagged by me']])
    chips.append(el('button', {class: 'chip' + (filter.status === v ? ' on' : ''), onclick: () => { filter.status = v; render(); }}, l));
  chips.append(el('button', {class: 'chip aiflag' + (filter.status === 'ai' ? ' on' : ''),
    title: 'Shows which articles the AI review flagged. This reveals AI judgments; use it after your own review.',
    onclick: async () => {
      if (!aiFlags) { if (!revealConfirm('ai-flags')) return; aiFlags = (await api('ai-flags', {})).items; }
      filter.status = 'ai'; render(); }}, aiFlags ? 'AI-flagged ⚑' : 'AI-flagged (hidden)'));
  const list = el('div', {class: 'list'});
  const v = visible();
  for (const i of v) list.append(el('a', {href: '#', class: i.id === cur ? 'cur' : '', onclick: e => { e.preventDefault(); go(i.id); }},
    el('span', {}, `Art. ${i.key} `, el('span', {class: 'c'}, i.members.map(m => m.corpus.replace('current_law_v2', 'v2').replace('expanded_v1', 'v1')).join(' + '))),
    el('span', {class: 'm' + (aiFlags && aiFlags.includes(i.id) ? ' aiflag' : '')}, mark(i.id) + (aiFlags && aiFlags.includes(i.id) ? '⚑' : ''))));
  if (!v.length) list.append(el('p', {class: 'hint'}, 'No articles match this filter.'));
  return el('aside', {}, corpusSel, chips, el('div', {class: 'hint'}, `${v.length} shown · ✓ approve ✗ reject ? examine ◐ in progress ★ my flag`), list);
}
let pendingReveal = null;
function revealConfirm(kind) { if (pendingReveal === kind) { pendingReveal = null; return true; } pendingReveal = kind; render(); return false; }

function radios(name, values, labels, value, onpick) {
  return el('div', {class: 'opts'}, ...values.map((v, k) => el('label', {},
    el('input', {type: 'radio', name, value: v, checked: value === v, onchange: () => onpick(v)}), labels[k])));
}
function changed() { preview = null; const p = document.getElementById('preview'); if (p) p.replaceChildren(); scheduleSave(); }
function scheduleSave() { setSave('Unsaved changes…'); clearTimeout(saveTimer); saveTimer = setTimeout(flush, 500); }
function setSave(t) { const s = document.getElementById('save'); if (s) s.textContent = t; }
async function flush() {
  if (!saveTimer || !cur) return; clearTimeout(saveTimer); saveTimer = null;
  const id = cur;
  try { const saved = await api('draft', {id, draft: S.drafts[id]});
    for (const k of ['first_saved', 'updated_at', 'ai_revealed_at', 'judgment_before_reveal']) if (k in saved) S.drafts[id][k] = saved[k];
    setSave('Saved ' + new Date().toLocaleTimeString()); refreshChrome(); }
  catch (e) { setSave('NOT SAVED: ' + e.message); }
}
function refreshChrome() {
  const t = document.querySelector('.prog'); if (t) t.replaceWith(progress());
  const a = document.querySelector('aside'); if (a) a.replaceWith(sidebar());
}

function articleView(i) {
  const d = draftOf(i.id), rec = S.recorded[i.id], st = status(i.id);
  const head = el('div', {class: 'card'},
    el('div', {class: 'hdr'}, el('h2', {}, `Article ${i.key}`),
      ...i.members.map(m => el('span', {class: 'tag'}, `${m.corpus} · ${m.id}`)),
      i.part ? el('span', {class: 'tag'}, `Part ${i.part}`) : null,
      el('span', {class: 'tag ' + (st === 'recorded' ? 'rec' : st === 'draft' ? 'dr' : '')},
        st === 'recorded' ? `Recorded: ${rec.decision} (${rec.date})` : st === 'draft' ? 'In progress (draft)' : 'Not started')),
    el('div', {class: 'meta'}, el('span', {class: 'verified'}, '✓ Verified against pinned SHA-256 before display'),
      ' · AR ', el('code', {title: i.ar_sha256}, i.ar_sha256.slice(0, 16) + '…'),
      ' · EN ', el('code', {title: i.en_sha256}, i.en_sha256.slice(0, 16) + '…'),
      ` · ${i.ar_chars} AR / ${i.en_chars} EN characters`),
    el('div', {class: 'meta'}, 'Legal version: ', i.version),
    el('div', {class: 'meta'}, 'Official sources: ', ...i.sources.flatMap((s, k) => [k ? ' · ' : '',
      s.url ? el('a', {href: s.url, target: '_blank', rel: 'noopener noreferrer'}, s.label) : s.label]), ' · ', i.source_note),
    i.members.length > 1 ? el('div', {class: 'meta'}, `Identical Arabic and English bytes in ${i.members.map(m => m.corpus).join(' and ')}: reviewed once, recorded in review/${i.home}_human_decisions.json.`) : null,
    ...i.related.map(r => el('div', {class: 'related'}, `A different version of Article ${i.key} is in ${BY[r.item].home} (${r.note}); it is reviewed separately. `,
      el('a', {onclick: () => go(r.item)}, 'Open it →'))));
  const texts = el('div', {class: 'texts'},
    el('div', {lang: 'en', dir: 'ltr'}, el('h3', {}, 'English · published translation'), el('div', {class: 'en txt'}, i.en)),
    el('div', {lang: 'ar', dir: 'rtl'}, el('h3', {dir: 'ltr', style: 'text-align:right'}, 'Arabic · original (governing)'), el('div', {class: 'ar txt'}, i.ar)));

  const f = el('fieldset', {}, el('legend', {}, 'Your assessment'),
    el('div', {class: 'crit'}, el('div', {class: 'lbl'}, '1. Semantic equivalence', el('small', {}, 'Do both texts say the same thing?')),
      radios('eq', ['EQUIVALENT', 'MINOR_DIFFERENCES', 'MATERIAL_DIFFERENCE'], ['Equivalent', 'Minor differences', 'Material difference'],
        d.equivalence, v => { d.equivalence = v; changed(); })));
  let n = 2;
  for (const c of Object.keys(CRIT)) {
    const note = el('textarea', {rows: 2, placeholder: 'Describe the issue (required for an issue); optional otherwise',
      oninput: e => { d[c].note = e.target.value; changed(); }}); note.value = d[c].note || '';
    f.append(el('div', {class: 'crit'}, el('div', {class: 'lbl'}, `${n++}. ${CRIT[c]}`, el('small', {}, HINT[c])),
      el('div', {}, radios(c, ASSESS_V, ASSESS[c], d[c].assessment, v => { d[c].assessment = v; changed(); }), note)));
  }
  const dl = el('div', {});
  const drawDisc = () => { dl.replaceChildren(...d.discrepancies.map((x, k) => {
    const s = el('select', {onchange: e => { x.severity = e.target.value || null; changed(); }},
      el('option', {value: ''}, 'Severity…'), el('option', {value: 'MINOR', selected: x.severity === 'MINOR'}, 'Minor'),
      el('option', {value: 'MATERIAL', selected: x.severity === 'MATERIAL'}, 'Material'));
    const t = el('input', {type: 'text', placeholder: 'What differs', oninput: e => { x.note = e.target.value; changed(); }}); t.value = x.note || '';
    return el('div', {class: 'disc'}, s, t, el('button', {onclick: () => { d.discrepancies.splice(k, 1); drawDisc(); changed(); }}, 'Remove'));
  })); };
  drawDisc();
  f.append(el('div', {class: 'crit'}, el('div', {class: 'lbl'}, `${n++}. Other textual discrepancies`,
      el('small', {}, 'Anything not covered above. A material item requires “Material difference”.')),
    el('div', {}, dl, el('button', {onclick: () => { d.discrepancies.push({severity: null, note: ''}); drawDisc(); }}, '+ Add discrepancy'))));

  const comment = el('textarea', {rows: 2, placeholder: 'Justification (recorded). Required for REJECT, REQUEST_EXAMINATION, or a material difference.',
    oninput: e => { d.comment = e.target.value; changed(); }}); comment.value = d.comment || '';
  const bench = el('fieldset', {}, el('legend', {}, `${n}. Suitability for comparative tokenization benchmarking`),
    el('p', {class: 'hint'}, 'This is your decision on the pair’s place in the benchmark, separate from semantic equivalence: a pair with documented translation discrepancies may still be accepted.'),
    radios('dec', ['APPROVE', 'REJECT', 'REQUEST_EXAMINATION'], ['APPROVE: accept for benchmarking', 'REJECT', 'REQUEST_EXAMINATION'],
      d.decision, v => { d.decision = v; changed(); }), el('p', {}), comment);
  const notes = el('textarea', {rows: 3, placeholder: 'Private working notes: saved locally in data/review/, never recorded or committed.',
    oninput: e => { d.notes = e.target.value; changed(); }}); notes.value = d.notes || '';
  const own = el('fieldset', {}, el('legend', {}, 'Notes'), notes,
    el('label', {}, el('input', {type: 'checkbox', checked: !!d.flag, onchange: e => { d.flag = e.target.checked; changed(); }}), ' Flag this article for later'));

  return [head, texts, el('div', {style: 'height:16px'}), f, bench, own, aiPanel(i, d), recordPanel(i, d, rec), navBar()];
}

function aiPanel(i, d) {
  const box = el('div', {class: 'ai'}, el('h3', {}, 'AI-generated assessment'));
  if (!d.ai_revealed_at) {
    box.append(el('p', {class: 'hint'}, 'Hidden to avoid anchoring. Reveal it only after forming your own judgment; the time of the reveal is logged locally.' +
      (judged(d) ? '' : ' You have not entered a judgment for this article yet.')));
    box.append(pendingReveal === i.id
      ? el('div', {}, el('button', {class: 'primary', onclick: () => doReveal(i.id)}, 'Yes, reveal the AI assessment'), ' ',
          el('button', {onclick: () => { pendingReveal = null; render(); }}, 'Cancel'))
      : el('button', {onclick: () => { pendingReveal = i.id; render(); }}, 'Reveal AI assessment for this article…'));
    if (pendingReveal === 'ai-flags') box.append(el('p', {class: 'problems'}, 'Click “AI-flagged” again to confirm showing AI flags for all articles.'));
    return box;
  }
  const a = aiCache[i.id];
  if (!a) { doReveal(i.id); box.append(el('p', {class: 'hint'}, 'Loading…')); return box; }
  box.append(el('p', {class: 'hint'}, `Revealed ${a.revealed_at}` + (a.judgment_before_reveal ? ' (after you had entered a judgment).' : ' (before any judgment was entered).')
    + (a.flagged ? ' The AI review flagged this article: your verdict on its assessment is required.' : '')));
  box.append(el('dl', {}, ...a.notes.flatMap(x => [el('dt', {}, x.label), el('dd', {}, x.text)])));
  if (!a.notes.length) box.append(el('p', {}, 'No AI notes for this pair.'));
  const note = el('textarea', {rows: 2, placeholder: 'Your note on the AI assessment', oninput: e => { d.ai_adjudication.note = e.target.value; changed(); }});
  note.value = d.ai_adjudication.note || '';
  box.append(el('div', {class: 'crit'}, el('div', {class: 'lbl'}, 'Your verdict on the AI assessment', el('small', {}, a.flagged ? 'required' : 'optional')),
    el('div', {}, radios('adj', ['AGREE', 'PARTLY_AGREE', 'DISAGREE'], ['Agree', 'Partly agree', 'Disagree'], d.ai_adjudication.verdict,
      v => { d.ai_adjudication.verdict = v; changed(); }), note)));
  return box;
}
async function doReveal(id) {
  pendingReveal = null;
  try { await flush(); const a = await api('reveal', {id}); aiCache[id] = a; draftOf(id).ai_revealed_at = a.revealed_at;
    draftOf(id).judgment_before_reveal = a.judgment_before_reveal; render(); }
  catch (e) { alertBox(e.message); }
}
function alertBox(msg) { const p = document.getElementById('preview'); if (p) p.replaceChildren(el('p', {class: 'problems'}, msg)); }

function recordPanel(i, d, rec) {
  const box = el('div', {class: 'rec'}, el('h3', {style: 'margin:0 0 6px;font-size:15px'}, `Record decision as ${D.reviewer}`),
    el('p', {class: 'hint'}, `Nothing is recorded until you preview the exact record and confirm it. It is then validated and written to review/${i.home}_human_decisions.json (Article ${i.key}), bound to that corpus's manifest hash.`));
  if (rec) box.append(el('p', {class: 'ok'}, `Currently recorded: ${rec.decision} by ${rec.reviewer} on ${rec.date}. Recording again replaces it.`),
    recordedFindings(rec));
  box.append(el('button', {onclick: doPreview}, 'Preview record'));
  box.append(el('div', {id: 'preview'}, preview ? previewView(preview) : null));
  return box;
}
function recordedFindings(rec) {
  const rows = [];
  if (rec.review_period) rows.push(['Review period', rec.review_period]);
  if (rec.equivalence) rows.push(['Semantic equivalence', rec.equivalence]);
  if (rec.terminology) rows.push(['Legal terminology', rec.terminology]);
  for (const x of rec.discrepancies || []) rows.push([`${x.severity} discrepancy`, x.note]);
  if (rec.ai_adjudication) rows.push([`Verdict on AI assessment: ${rec.ai_adjudication.verdict}`, rec.ai_adjudication.note]);
  if (rec.comment) rows.push(['Comment', rec.comment]);
  return rows.length ? el('dl', {class: 'meta'}, ...rows.flatMap(([k, v]) => [el('dt', {}, k), el('dd', {}, v)])) : null;
}
async function doPreview() {
  try { await flush(); preview = await api('preview', {id: cur}); }
  catch (e) { preview = {ok: false, problems: [e.message]}; }
  document.getElementById('preview').replaceChildren(previewView(preview));
}
function previewView(p) {
  if (!p.ok) return el('ul', {class: 'problems'}, ...p.problems.map(x => el('li', {}, x)));
  return el('div', {}, el('pre', {}, `${p.file} → Article ${p.article}\n` + JSON.stringify(p.record, null, 2)),
    p.replace ? el('p', {class: 'problems'}, `This replaces the recorded decision (${p.existing.decision}, ${p.existing.date}).`) : null,
    el('button', {class: p.replace ? 'danger' : 'primary', onclick: async e => {
      e.target.disabled = true;
      try { const r = await api('record', {id: cur, fingerprint: p.fingerprint, confirm: true});
        S.recorded[cur] = r.recorded; preview = null; render(); setSave(`Recorded Article ${BY[cur].key}`); }
      catch (err) { alertBox('NOT RECORDED: ' + err.message); }
    }}, p.replace ? `Confirm: replace and record as ${D.reviewer}` : `Confirm: record as ${D.reviewer}`));
}
function navBar() {
  const prev = nextOf(() => true, -1), next = nextOf(() => true), un = nextOf(i => status(i.id) !== 'recorded');
  return el('div', {class: 'nav'},
    el('button', {disabled: !prev, onclick: () => go(prev)}, '← Previous'),
    el('button', {disabled: !next, onclick: () => go(next)}, 'Next →'),
    el('button', {disabled: !un, onclick: () => go(un)}, 'Next not recorded ⇥'));
}

function render() {
  const app = document.getElementById('app');
  const v = visible();
  if (!cur || !BY[cur]) cur = (v[0] || ITEMS[0]).id;
  const top = el('div', {class: 'top'}, el('div', {}, el('h1', {}, 'ATTI review workspace'),
      el('div', {class: 'who'}, `Reviewer: ${D.reviewer} · ${D.summary.unique_pairs} distinct pairs (${D.summary.slots} corpus slots)`)),
    progress(), el('div', {class: 'save', id: 'save'}, 'All changes saved'));
  const main = el('main', {}, el('div', {class: 'banner'},
    'Local workspace: drafts and notes autosave to data/review/workspace_drafts.json (git-ignored). Legal texts are shown exactly as published and verified; nothing here edits them.'),
    ...articleView(BY[cur]));
  app.replaceChildren(top, el('div', {class: 'layout'}, sidebar(), main));
}
window.addEventListener('beforeunload', () => { if (saveTimer) flush(); });
api('state').then(s => { S = s; S.drafts = S.drafts || {}; cur = s.last_item && BY[s.last_item] ? s.last_item : ITEMS[0].id;
  for (const [id, d] of Object.entries(S.drafts)) { const b = blank(); S.drafts[id] = Object.assign(b, d); }
  render(); }).catch(e => { document.getElementById('app').textContent = 'Could not load state: ' + e.message; });
})();
"""
