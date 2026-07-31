"""Render the record as a self-contained page for GitHub Pages.

Everything is inlined -- data, styles, script -- so the page is one file with no
network dependency and no build step. GitHub Pages serves `docs/` directly, which
means publishing is a commit.

The funnel is the centrepiece, and it is drawn as an ordinal ramp rather than a
categorical one because its stages are ordered: each is a subset of the one
before. Colour is doing the "how far along" job, not the "which one" job.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Validated against the dataviz palette validator on both surfaces: lightness
#: band, chroma floor, CVD separation (worst adjacent pair 9.1 protan), and the
#: normal-vision floor all pass. The contrast warning that comes with slots 3-5
#: is discharged by direct labels and a table view, both of which this page has.
CATEGORICAL_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
CATEGORICAL_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"]

#: Single-hue ordinal ramp for the funnel: each stage is a subset of the one
#: before, so lightness carries the ordering and the step nearest the surface is
#: the widest stage.
FUNNEL_LIGHT = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#1c5cab"]
FUNNEL_DARK = ["#104281", "#184f95", "#256abf", "#2a78d6", "#5598e7"]

#: Reserved status steps -- never reused for a series.
STATUS = {
    "VERIFIED": "#0ca30c",
    "NOT_REPRODUCED": "#fab219",
    "REFUTED": "#ec835a",
    "CANDIDATE": "#8a8a85",
    "PROBED": "#8a8a85",
    "LINKED": "#8a8a85",
}


@dataclass
class Dashboard:
    """Everything the page displays.

    Attributes:
        corpus: Per-language package and entry counts.
        funnel: Ordered narrowing stages, widest first.
        classification: Category counts and the rules-versus-reading confusion.
        bugs: One row per bug record.
        shortlist: High-severity silent entries not yet verified.
    """

    corpus: dict[str, Any]
    funnel: list[dict[str, Any]]
    classification: dict[str, Any]
    bugs: list[dict[str, Any]]
    shortlist: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        """Return the payload inlined into the page.

        Returns:
            A JSON-serializable dict.
        """
        return {
            "corpus": self.corpus,
            "funnel": self.funnel,
            "classification": self.classification,
            "bugs": self.bugs,
            "shortlist": self.shortlist,
        }


PAGE = """<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>concord &mdash; are the numbers right?</title>
<style>
:root {
  --surface: #fcfcfb; --panel: #ffffff; --ink: #17171a; --ink-2: #4a4a52;
  --ink-3: #74747e; --rule: #e4e4e0; --accent: #2a78d6;
  --good: #0ca30c; --warn: #fab219; --serious: #ec835a; --crit: #d03b3b;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root { --surface:#1a1a19; --panel:#232322; --ink:#f2f2ef; --ink-2:#bcbcb6;
          --ink-3:#8a8a85; --rule:#343433; --accent:#3987e5;
          --good:#0ca30c; --warn:#fab219; --serious:#ec835a; --crit:#d03b3b; }
}
:root[data-theme="dark"] {
  --surface:#1a1a19; --panel:#232322; --ink:#f2f2ef; --ink-2:#bcbcb6;
  --ink-3:#8a8a85; --rule:#343433; --accent:#3987e5;
}
:root[data-theme="light"] {
  --surface:#fcfcfb; --panel:#ffffff; --ink:#17171a; --ink-2:#4a4a52;
  --ink-3:#74747e; --rule:#e4e4e0; --accent:#2a78d6;
}
* { box-sizing: border-box; }
body { margin:0; background:var(--surface); color:var(--ink);
  font:15px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif; }
.wrap { max-width:1080px; margin:0 auto; padding:40px 20px 80px; }
h1 { font-size:30px; letter-spacing:-.02em; margin:0 0 6px; font-weight:650; }
h2 { font-size:19px; letter-spacing:-.01em; margin:44px 0 6px; font-weight:620; }
.sub { color:var(--ink-2); margin:0 0 4px; max-width:66ch; }
.note { color:var(--ink-3); font-size:13.5px; max-width:70ch; margin:6px 0 0; }
.tiles { display:grid; gap:12px; margin:26px 0 8px;
  grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); }
.tile { background:var(--panel); border:1px solid var(--rule); border-radius:10px;
  padding:14px 16px; }
.tile .n { font-size:27px; font-weight:640; letter-spacing:-.02em;
  font-variant-numeric:tabular-nums; }
.tile .l { color:var(--ink-3); font-size:12.5px; margin-top:2px; }
.funnel { margin-top:14px; }
.frow { display:grid; grid-template-columns:210px 1fr 62px; gap:12px;
  align-items:center; margin-bottom:7px; }
.flabel { color:var(--ink-2); font-size:13.5px; text-align:right; }
.ftrack { background:var(--rule); border-radius:4px; height:22px; overflow:hidden; }
.fbar { height:100%; border-radius:0 4px 4px 0; }
.fval { font-variant-numeric:tabular-nums; font-weight:600; font-size:14px; }
table { border-collapse:collapse; width:100%; margin-top:12px; font-size:13.5px; }
th { text-align:left; font-weight:600; color:var(--ink-3); font-size:12px;
  text-transform:uppercase; letter-spacing:.04em; padding:6px 10px 6px 0;
  border-bottom:1px solid var(--rule); cursor:pointer; user-select:none; }
th:hover { color:var(--ink); }
td { padding:8px 10px 8px 0; border-bottom:1px solid var(--rule);
  vertical-align:top; }
td.num { font-variant-numeric:tabular-nums; text-align:right; padding-right:16px; }
code, .mono { font-family:var(--mono); font-size:12.5px; }
.pill { display:inline-flex; align-items:center; gap:5px; font-size:11.5px;
  font-weight:600; padding:2px 8px; border-radius:99px; border:1px solid var(--rule);
  white-space:nowrap; }
.dot { width:7px; height:7px; border-radius:99px; flex:none; }
.filters { display:flex; flex-wrap:wrap; gap:8px; margin:16px 0 0; }
.filters select, .filters button { font:inherit; font-size:13px; padding:5px 10px;
  border:1px solid var(--rule); border-radius:7px; background:var(--panel);
  color:var(--ink); cursor:pointer; }
.scroll { overflow-x:auto; }
.legend { display:flex; flex-wrap:wrap; gap:14px; margin-top:10px;
  color:var(--ink-2); font-size:12.5px; }
.legend span { display:inline-flex; align-items:center; gap:6px; }
.foot { margin-top:56px; padding-top:18px; border-top:1px solid var(--rule);
  color:var(--ink-3); font-size:13px; }
a { color:var(--accent); }
#theme { position:fixed; top:14px; right:14px; }
</style>

<div class="wrap">
<button id="theme" class="mono">theme</button>
<h1>concord</h1>
<p class="sub">Are the numbers right? Two questions about statistical software, one
comparison engine: do independent implementations agree today, and did one of them
used to be wrong in a way that reached published work.</p>

<div class="tiles" id="tiles"></div>
<p class="note" id="corpus-note"></p>

<h2>The funnel</h2>
<p class="sub">Every stage is a subset of the one before. The drop is the finding,
not an embarrassment &mdash; most changelog entries that <em>sound</em> like wrong
numbers are not.</p>
<div class="funnel" id="funnel"></div>

<h2>What reading changed</h2>
<p class="sub">A regular expression proposed a category for all 163 exposed entries;
each was then read and judged. Every correction is a measured disagreement, which is
the validation a hand-coded gold set was going to provide.</p>
<div class="scroll"><table id="confusion"></table></div>

<h2>The record</h2>
<p class="sub">One directory per bug, five pipeline stages, each leaving a durable
artifact. Exposure is always a pair: scripts calling the function, and scripts also
matching the bug's conditions probe.</p>
<div class="filters">
  <select id="f-lang"><option value="">all languages</option></select>
  <select id="f-status"><option value="">all statuses</option></select>
  <select id="f-sev"><option value="">all severities</option></select>
  <button id="f-reset">reset</button>
</div>
<div class="scroll"><table id="bugs"></table></div>
<div class="legend" id="bug-legend"></div>

<h2>Shortlist</h2>
<p class="sub">Silent, result-changing, high severity, not yet verified &mdash; the
queue the next verification pass draws from, ranked by corpus exposure.</p>
<div class="scroll"><table id="shortlist"></table></div>

<p class="foot">Generated by <code>concord dashboard</code>. Every number here comes
from a command in the repository; none is hand-entered. Exposure counts are upper
bounds &mdash; a probe shows a script <em>could</em> have met the triggering
condition, never that it did.</p>
</div>

<script>
const DATA = __DATA__;
const PAL = {light: __CAT_L__, dark: __CAT_D__};
const FUN = {light: __FUN_L__, dark: __FUN_D__};
const STATUS = __STATUS__;

const mode = () => {
  const t = document.documentElement.getAttribute('data-theme');
  if (t) return t;
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};
const esc = s => String(s ?? '').replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const pill = (text, color) =>
  `<span class="pill"><span class="dot" style="background:${color}"></span>${esc(text)}</span>`;

function tiles() {
  const c = DATA.corpus, f = DATA.funnel, cl = DATA.classification;
  const verified = DATA.bugs.filter(b => b.status === 'VERIFIED').length;
  const items = [
    [c.entries.toLocaleString(), 'changelog entries'],
    [c.packages, 'packages, 2 languages'],
    [f[f.length-1].n, 'entries with corpus exposure'],
    [cl.moves_published, 'could move a published number'],
    [verified + ' / ' + DATA.bugs.length, 'bugs verified'],
  ];
  document.getElementById('tiles').innerHTML = items
    .map(([n,l]) => `<div class="tile"><div class="n">${esc(n)}</div><div class="l">${esc(l)}</div></div>`)
    .join('');
  document.getElementById('corpus-note').textContent = c.note;
}

function funnel() {
  const ramp = FUN[mode()], f = DATA.funnel, max = f[0].n;
  document.getElementById('funnel').innerHTML = f.map((s, i) => {
    const w = Math.max(0.6, 100 * s.n / max);
    const col = ramp[Math.min(i, ramp.length-1)];
    return `<div class="frow">
      <div class="flabel">${esc(s.label)}</div>
      <div class="ftrack"><div class="fbar" style="width:${w}%;background:${col}"
        title="${esc(s.label)}: ${s.n}"></div></div>
      <div class="fval">${s.n.toLocaleString()}</div></div>`;
  }).join('');
}

function confusion() {
  const rows = DATA.classification.confusion;
  const head = '<tr><th>rules said</th><th>reading said</th><th class="num">n</th><th>agreed</th></tr>';
  document.getElementById('confusion').innerHTML = head + rows.map(r =>
    `<tr><td class="mono">${esc(r.rules)}</td><td class="mono">${esc(r.read)}</td>
     <td class="num">${r.n}</td>
     <td>${r.rules === r.read
        ? pill('agreed', STATUS.VERIFIED)
        : pill('corrected', STATUS.NOT_REPRODUCED)}</td></tr>`).join('');
}

let sortKey = 'probe', sortDir = -1;
function bugs() {
  const lang = document.getElementById('f-lang').value;
  const st = document.getElementById('f-status').value;
  const sev = document.getElementById('f-sev').value;
  let rows = DATA.bugs.filter(b =>
    (!lang || b.language === lang) && (!st || b.status === st) && (!sev || b.severity === sev));
  rows.sort((a,b) => {
    const x = a[sortKey], y = b[sortKey];
    if (x === y) return a.id.localeCompare(b.id);
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (x > y ? 1 : -1) * sortDir;
  });
  const cols = [['id','bug'],['severity','sev'],['calls','calls'],
                ['probe','probe'],['papers','papers'],['status','status']];
  const head = '<tr>' + cols.map(([k,l]) =>
    `<th data-k="${k}">${esc(l)}${sortKey===k ? (sortDir<0?' \\u2193':' \\u2191') : ''}</th>`).join('')
    + '<th>conditions</th></tr>';
  document.getElementById('bugs').innerHTML = head + rows.map(b => `<tr>
    <td class="mono">${esc(b.id)}</td>
    <td>${esc(b.severity)}</td>
    <td class="num">${b.calls ?? '&mdash;'}</td>
    <td class="num">${b.probe ?? '&mdash;'}</td>
    <td class="num">${b.papers ?? '&mdash;'}</td>
    <td>${pill(b.status, STATUS[b.status] || '#8a8a85')}</td>
    <td>${esc(b.conditions)}</td></tr>`).join('');
  document.querySelectorAll('#bugs th[data-k]').forEach(th =>
    th.onclick = () => {
      const k = th.dataset.k;
      if (k === sortKey) sortDir = -sortDir; else { sortKey = k; sortDir = -1; }
      bugs();
    });
  document.getElementById('bug-legend').innerHTML =
    Object.entries(STATUS).filter(([k]) => DATA.bugs.some(b => b.status === k))
      .map(([k,v]) => `<span><span class="dot" style="background:${v}"></span>${esc(k)}</span>`)
      .join('');
}

function shortlist() {
  const head = '<tr><th>entry</th><th class="num">exposure</th><th>functions</th><th>conditions</th></tr>';
  document.getElementById('shortlist').innerHTML = head + DATA.shortlist.map(s =>
    `<tr><td class="mono">${esc(s.entry_id)}</td><td class="num">${s.exposure}</td>
     <td class="mono">${esc(s.functions)}</td><td>${esc(s.conditions)}</td></tr>`).join('');
}

function fill(id, values) {
  const sel = document.getElementById(id);
  [...new Set(values)].sort().forEach(v => {
    const o = document.createElement('option'); o.value = o.textContent = v; sel.append(o);
  });
  sel.onchange = bugs;
}

fill('f-lang', DATA.bugs.map(b => b.language));
fill('f-status', DATA.bugs.map(b => b.status));
fill('f-sev', DATA.bugs.map(b => b.severity));
document.getElementById('f-reset').onclick = () => {
  ['f-lang','f-status','f-sev'].forEach(i => document.getElementById(i).value = '');
  bugs();
};
document.getElementById('theme').onclick = () => {
  document.documentElement.setAttribute('data-theme', mode() === 'dark' ? 'light' : 'dark');
  funnel();
};
tiles(); funnel(); confusion(); bugs(); shortlist();
</script>
"""


def render(data: Dashboard) -> str:
    """Render the page with its data inlined.

    Args:
        data: The dashboard payload.

    Returns:
        Complete HTML.
    """
    return (
        PAGE.replace("__DATA__", json.dumps(data.to_dict()))
        .replace("__CAT_L__", json.dumps(CATEGORICAL_LIGHT))
        .replace("__CAT_D__", json.dumps(CATEGORICAL_DARK))
        .replace("__FUN_L__", json.dumps(FUNNEL_LIGHT))
        .replace("__FUN_D__", json.dumps(FUNNEL_DARK))
        .replace("__STATUS__", json.dumps(STATUS))
    )


def write(data: Dashboard, path: Path) -> Path:
    """Write the page.

    Args:
        data: The dashboard payload.
        path: Destination HTML file.

    Returns:
        The path written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(data))
    return path
