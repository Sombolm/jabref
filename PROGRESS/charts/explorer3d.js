// ===================== 3D Metric Explorer + Correlations =====================
// Data: DATA.explorer (built by generate_dashboard.py), rendering: Plotly.js (CDN).
const EX = DATA.explorer;
const EX_N = EX.files.length;
const EX_M = Object.fromEntries(EX.metrics.map(m => [m.k, m]));
const EX_TOP5 = new Set(DATA.meta.top5);
const EX_IDX = new Map(EX.files.map((f, i) => [f, i]));
const EX_MOD_COLORS = {
  jablib: '#38bdf8', jabgui: '#f472b6', jabsrv: '#a3e635', jabkit: '#fbbf24', jabls: '#c084fc',
  'jabls-cli': '#fb923c', 'jabsrv-cli': '#2dd4bf', 'test-support': '#94a3b8', 'build-support': '#e2e8f0'
};
const EX_PRESETS = [
  { label: 'Preset: Hotspot (churn x complexity x size)', x: 'c24', y: 'cog', z: 'sloc', c: 'cbo', s: 'hs', l: [1, 1, 1] },
  { label: 'Preset: Coupling (fan-in x fan-out x CBO)', x: 'fanin', y: 'fanout', z: 'cbo', c: 'c24', s: 'sloc', l: [1, 1, 1] },
  { label: 'Preset: Knowledge risk (authors x owner share x complexity)', x: 'auth', y: 'share', z: 'cog', c: 'active', s: 'sloc', l: [1, 0, 1] },
  { label: 'Preset: Cohesion (methods x fields x LCOM)', x: 'methods', y: 'fields', z: 'lcom', c: 'smells', s: 'sloc', l: [1, 1, 0] },
  { label: 'Preset: Smells (complexity x smells x churn)', x: 'cog', y: 'smells', z: 'c24', c: 'module', s: 'sloc', l: [1, 1, 1] },
  { label: 'Preset: Is it all just size? (SLOC x WMC x RFC)', x: 'sloc', y: 'wmc', z: 'rfc', c: 'cbo', s: 'none', l: [1, 1, 1] },
];
const EX_SCALE = [[0, '#2563eb'], [0.3, '#22d3ee'], [0.55, '#a3e635'], [0.75, '#facc15'], [1, '#ef4444']];
const EX_CATS = { module: 'Module', active: 'Owner active (6m)', god: 'GodClass flag' };
let exSel = -1, exInited = false, corrInited = false, exDown = null, exDragged = false, exPending = null;
const EX_DEFAULT_CAMERA = { eye: { x: 1.15, y: 1.15, z: 0.75 } };
// Keep whatever view the user rotated/zoomed to when the plot is re-rendered (metric change, selection, filters).
function exCurrentCamera() {
  try {
    const sc = document.getElementById('ex-plot')._fullLayout.scene._scene;
    return sc.getCamera();
  } catch (e) { return EX_DEFAULT_CAMERA; }
}

// ---------- helpers ----------
const exVal = (k, i) => EX.cols[k][i];
const exT = (v, log) => (log ? Math.log10(1 + Math.max(0, v)) : v);
const exFmt = v => (v === null || v === undefined) ? '-' : (Number.isInteger(v) ? v.toLocaleString() : v.toFixed(2));
const exSorted = {};
EX.metrics.forEach(m => { exSorted[m.k] = EX.cols[m.k].filter(v => v !== null).sort((a, b) => a - b); });
function exPct(k, v) {
  const a = exSorted[k]; if (v === null || !a.length) return null;
  let lo = 0, hi = a.length; while (lo < hi) { const mid = (lo + hi) >> 1; if (a[mid] <= v) lo = mid + 1; else hi = mid; }
  return lo / a.length * 100;
}
function exLogTicks(maxRaw) {
  const base = [0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000];
  const raw = base.filter(v => v <= maxRaw * 1.05);
  return { tickvals: raw.map(v => exT(v, true)), ticktext: raw.map(v => v.toLocaleString()) };
}
function exRanks(arr) {
  const idx = arr.map((v, i) => [v, i]).sort((a, b) => a[0] - b[0]);
  const r = new Array(arr.length);
  for (let i = 0; i < idx.length;) {
    let j = i; while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++;
    const avg = (i + j) / 2 + 1; for (let k = i; k <= j; k++) r[idx[k][1]] = avg; i = j + 1;
  }
  return r;
}
function exSpearman(xs, ys) {
  const n = xs.length; if (n < 5) return null;
  const rx = exRanks(xs), ry = exRanks(ys);
  const mx = rx.reduce((s, v) => s + v, 0) / n, my = ry.reduce((s, v) => s + v, 0) / n;
  let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < n; i++) { const a = rx[i] - mx, b = ry[i] - my; num += a * b; dx += a * a; dy += b * b; }
  return dx && dy ? num / Math.sqrt(dx * dy) : null;
}
function exStrength(r) {
  const a = Math.abs(r);
  if (a >= 0.7) return ['very strong', 'b-red'];
  if (a >= 0.5) return ['strong', 'b-warn'];
  if (a >= 0.3) return ['moderate', 'b-blue'];
  return ['weak', 'b-ok'];
}
function exEsc(s) { return String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

// ---------- controls ----------
function exMetricOptions(withCats, withNone) {
  let html = '';
  if (withNone) html += '<option value="none">(constant)</option>';
  if (withCats) html += '<optgroup label="Category">' + Object.entries(EX_CATS).map(([k, l]) => `<option value="${k}">${l}</option>`).join('') + '</optgroup>';
  const groups = [...new Set(EX.metrics.map(m => m.g))];
  groups.forEach(g => {
    html += `<optgroup label="${g}">` + EX.metrics.filter(m => m.g === g).map(m => `<option value="${m.k}" title="${exEsc(m.d)}">${m.label}</option>`).join('') + '</optgroup>';
  });
  return html;
}
function exInitControls() {
  ['ex-x', 'ex-y', 'ex-z'].forEach(id => document.getElementById(id).innerHTML = exMetricOptions(false, false));
  document.getElementById('ex-c').innerHTML = exMetricOptions(true, false);
  document.getElementById('ex-s').innerHTML = exMetricOptions(false, true);
  const mods = [...new Set(EX.module)].sort();
  document.getElementById('ex-mod').innerHTML = '<option value="ALL">All</option>' + mods.map(m => `<option value="${m}">${m}</option>`).join('');
  document.getElementById('ex-preset').innerHTML = '<option value="">Presets...</option>' + EX_PRESETS.map((p, i) => `<option value="${i}">${p.label}</option>`).join('');
  document.getElementById('ex-names').innerHTML = [...new Set(EX.names)].sort().map(n => `<option value="${n}">`).join('');
  exApplyPreset(0, true);
}
function exApplyPreset(i, silent) {
  if (i === '' || i === null) return;
  const p = EX_PRESETS[+i];
  document.getElementById('ex-x').value = p.x; document.getElementById('ex-y').value = p.y; document.getElementById('ex-z').value = p.z;
  document.getElementById('ex-c').value = p.c; document.getElementById('ex-s').value = p.s;
  document.getElementById('ex-lx').checked = !!p.l[0]; document.getElementById('ex-ly').checked = !!p.l[1]; document.getElementById('ex-lz').checked = !!p.l[2];
  document.getElementById('ex-preset').value = '';
  if (!silent) exRender();
}
function exState() {
  const g = id => document.getElementById(id);
  return {
    x: g('ex-x').value, y: g('ex-y').value, z: g('ex-z').value, c: g('ex-c').value, s: g('ex-s').value,
    lx: g('ex-lx').checked, ly: g('ex-ly').checked, lz: g('ex-lz').checked,
    mod: g('ex-mod').value, minc: +g('ex-minc').value || 0, god: g('ex-god').checked, inact: g('ex-inact').checked,
    top5: g('ex-top5').checked, q: g('ex-search').value.trim().toLowerCase(),
  };
}
function exFilter(st) {
  const need = [st.x, st.y, st.z];
  if (EX_M[st.c]) need.push(st.c);
  if (EX_M[st.s]) need.push(st.s);
  const out = [];
  for (let i = 0; i < EX_N; i++) {
    if (st.mod !== 'ALL' && EX.module[i] !== st.mod) continue;
    if (st.god && !EX.god[i]) continue;
    if (st.inact && EX.active[i]) continue;
    if (exVal('c24', i) < st.minc) continue;
    if (need.some(k => exVal(k, i) === null)) continue;
    out.push(i);
  }
  return out;
}
function exMatches(st, idx) {
  if (st.q.length < 2) return [];
  return idx.filter(i => EX.names[i].toLowerCase().includes(st.q) || EX.files[i].toLowerCase().includes(st.q));
}

// ---------- 3D plot ----------
function exHover(i, st) {
  const line = k => `${EX_M[k].label}: <b>${exFmt(exVal(k, i))}</b>`;
  const parts = [`<b>${EX.names[i]}</b> (${EX.module[i]})`, line(st.x), line(st.y), line(st.z)];
  if (EX_M[st.c] && ![st.x, st.y, st.z].includes(st.c)) parts.push(line(st.c));
  if (EX_M[st.s] && ![st.x, st.y, st.z, st.c].includes(st.s)) parts.push(line(st.s));
  parts.push(`Owner: ${exEsc(EX.owner[i] || '-')}${EX.active[i] ? '' : ' (inactive)'}`);
  return parts.join('<br>');
}
function exSizes(st, idx) {
  if (!EX_M[st.s]) return idx.map(() => 4.5);
  const vals = idx.map(i => Math.max(0, exVal(st.s, i)));
  const mx = Math.max(1e-9, ...vals);
  return vals.map(v => 3 + 17 * Math.sqrt(v / mx));
}
function exAxis(k, log, idx) {
  const m = EX_M[k];
  const ax = {
    title: { text: m.label + (log ? ' (log)' : ''), font: { size: 12, color: '#e2e8f0' } }, color: '#94a3b8', gridcolor: '#334155', zerolinecolor: '#475569',
    backgroundcolor: '#0b1120', showbackground: true,
  };
  if (log) Object.assign(ax, exLogTicks(Math.max(1, ...idx.map(i => exVal(k, i)))));
  return ax;
}
function exTrace(idx, st, extra) {
  return Object.assign({
    type: 'scatter3d', mode: 'markers',
    x: idx.map(i => exT(exVal(st.x, i), st.lx)),
    y: idx.map(i => exT(exVal(st.y, i), st.ly)),
    z: idx.map(i => exT(exVal(st.z, i), st.lz)),
    customdata: idx, text: idx.map(i => exHover(i, st)), hoverinfo: 'text',
    hoverlabel: { bgcolor: '#0b1120', bordercolor: '#38bdf8', font: { color: '#f1f5f9' } },
  }, extra);
}
function exRender() {
  if (!window.Plotly) { document.getElementById('ex-plot').innerHTML = '<div class="sub" style="padding:20px">Plotly.js failed to load (no internet?). The 3D Explorer needs the Plotly CDN.</div>'; return; }
  const st = exState();
  const idx = exFilter(st);
  const traces = [];
  if (EX_CATS[st.c]) {
    let groups;
    if (st.c === 'module') groups = [...new Set(idx.map(i => EX.module[i]))].sort().map(m => [m, idx.filter(i => EX.module[i] === m), EX_MOD_COLORS[m] || '#e2e8f0']);
    else if (st.c === 'active') groups = [['Owner active', idx.filter(i => EX.active[i]), '#38bdf8'], ['Owner inactive >6m', idx.filter(i => !EX.active[i]), '#ef4444']];
    else groups = [['No GodClass', idx.filter(i => !EX.god[i]), '#38bdf8'], ['GodClass', idx.filter(i => EX.god[i]), '#ef4444']];
    groups.forEach(([name, gi, color]) => {
      if (!gi.length) return;
      const sz = exSizes(st, gi);
      traces.push(exTrace(gi, st, { name: `${name} (${gi.length})`, marker: { size: sz, color, opacity: 0.75, line: { width: 0 } } }));
    });
  } else {
    const logC = EX_M[st.c].log;
    const cv = idx.map(i => exT(exVal(st.c, i), logC));
    const cb = { title: { text: EX_M[st.c].label + (logC ? ' (log)' : ''), side: 'right', font: { color: '#e2e8f0' } }, tickfont: { color: '#94a3b8' }, len: 0.75, thickness: 14 };
    if (logC) Object.assign(cb, exLogTicks(Math.max(1, ...idx.map(i => exVal(st.c, i)))));
    traces.push(exTrace(idx, st, {
      name: 'files', showlegend: false,
      marker: { size: exSizes(st, idx), color: cv, colorscale: EX_SCALE, opacity: 0.8, line: { width: 0 }, colorbar: cb },
    }));
  }
  // highlights: top5 + search matches + selection
  const hl = new Set(exMatches(st, idx).slice(0, 60));
  if (st.top5) idx.forEach(i => { if (EX_TOP5.has(EX.files[i])) hl.add(i); });
  const hli = [...hl];
  if (hli.length) {
    traces.push(exTrace(hli, st, {
      mode: 'markers+text', name: 'highlighted', showlegend: false,
      text: hli.map(i => EX.names[i]), hovertext: hli.map(i => exHover(i, st)), hoverinfo: 'text',
      textfont: { color: '#f8fafc', size: 11 }, textposition: 'top center',
      marker: { size: 9, symbol: 'diamond', color: '#ffffff', opacity: 0.95, line: { color: '#0f172a', width: 1 } },
    }));
  }
  if (exSel >= 0 && idx.includes(exSel)) {
    traces.push(exTrace([exSel], st, {
      mode: 'markers+text', name: 'selected', showlegend: false, text: [EX.names[exSel]], hovertext: [exHover(exSel, st)], hoverinfo: 'text',
      textfont: { color: '#fde047', size: 13 }, textposition: 'top center',
      marker: { size: 16, symbol: 'circle-open', color: '#fde047', line: { color: '#fde047', width: 3 } },
    }));
  }
  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)', font: { color: '#cbd5e1', size: 11 }, margin: { l: 0, r: 0, t: 0, b: 0 },
    uirevision: 'keep', showlegend: !!EX_CATS[st.c], legend: { x: 0.01, y: 0.99, bgcolor: 'rgba(15,23,42,0.75)', bordercolor: '#334155', borderwidth: 1 },
    scene: { xaxis: exAxis(st.x, st.lx, idx), yaxis: exAxis(st.y, st.ly, idx), zaxis: exAxis(st.z, st.lz, idx), aspectmode: 'cube', bgcolor: '#0b1120', camera: exCurrentCamera() },
  };
  Plotly.react('ex-plot', traces, layout, { displaylogo: false, responsive: true, modeBarButtonsToRemove: ['resetCameraLastSave3d'] });
  if (!exInited) {
    const gd = document.getElementById('ex-plot');
    // Plotly's 3D scene emits plotly_click while the mouse button is still held down over a point, i.e. at
    // the start of a rotate drag. Re-rendering at that moment kills the rotation, so the click is only
    // remembered here and applied on button release, and only if the pointer did not move (= not a drag).
    gd.addEventListener('pointerdown', e => { exDown = [e.clientX, e.clientY]; exDragged = false; exPending = null; }, true);
    gd.addEventListener('pointermove', e => { if (exDown && Math.hypot(e.clientX - exDown[0], e.clientY - exDown[1]) > 5) exDragged = true; }, true);
    window.addEventListener('pointerup', () => {
      if (!exDown) return;
      exDown = null;
      if (!exDragged && exPending !== null) { const i = exPending; exPending = null; setTimeout(() => exSelect(i), 0); }
      exPending = null;
    }, true);
    gd.on('plotly_click', ev => {
      const p = ev.points && ev.points[0];
      if (!p || p.customdata === undefined) return;
      if (exDown) exPending = p.customdata;          // button still held: decide on release
      else if (!exDragged) exSelect(p.customdata);   // emitted after release: plain click
    });
    exInited = true;
  }
  const nm = exMatches(st, idx).length;
  document.getElementById('ex-count').textContent = `${idx.length.toLocaleString()} files plotted` + (st.q.length >= 2 ? ` | ${nm} match "${st.q}"` : '');
  exRenderCorr(st, idx);
}
function exRenderCorr(st, idx) {
  const pairs = [[st.x, st.y], [st.x, st.z], [st.y, st.z]];
  if (EX_M[st.c]) [st.x, st.y, st.z].forEach(a => { if (a !== st.c) pairs.push([a, st.c]); });
  const seen = new Set();
  const chips = pairs.filter(([a, b]) => a !== b).filter(([a, b]) => { const k = [a, b].sort().join('|'); if (seen.has(k)) return false; seen.add(k); return true; })
    .map(([a, b]) => {
      const r = exSpearman(idx.map(i => exVal(a, i)), idx.map(i => exVal(b, i)));
      if (r === null) return '';
      const [lbl, cls] = exStrength(r);
      return `<span class="ex-chip">&rho;(${EX_M[a].label}, ${EX_M[b].label}) = <strong>${r.toFixed(2)}</strong> <span class="badge ${cls}">${lbl}${r < 0 ? ', inverse' : ''}</span></span>`;
    }).join('');
  document.getElementById('ex-corr').innerHTML = chips ? `<span class="sub">Spearman correlation on the plotted files:</span> ${chips}` : '';
}
function exSelectFirstMatch() {
  const st = exState(); const m = exMatches(st, exFilter(st));
  if (m.length) exSelect(m[0]);
}

// ---------- detail panel ----------
function exSelect(i) {
  exSel = i;
  const f = EX.files[i];
  const badges = [`<span class="badge b-blue">${EX.module[i]}</span>`];
  if (EX_TOP5.has(f)) badges.push('<span class="badge b-red">Top 5 hotspot</span>');
  if (EX.god[i]) badges.push('<span class="badge b-red">GodClass</span>');
  badges.push(EX.active[i] ? '<span class="badge b-ok">owner active</span>' : '<span class="badge b-red">owner inactive &gt;6m</span>');
  let html = `<h3 style="margin:0 0 4px;">${EX.names[i]}</h3><div class="path" style="white-space:normal;max-width:none;" title="${f}">${f}</div>
    <div style="margin:6px 0;display:flex;gap:6px;flex-wrap:wrap;">${badges.join('')}</div>
    <div class="sub">Main author: <strong>${exEsc(EX.owner[i] || '-')}</strong></div>
    <table class="ex-mtable"><thead><tr><th>Metric</th><th>Value</th><th>Percentile</th></tr></thead><tbody>`;
  let lastG = '';
  EX.metrics.forEach(m => {
    if (m.g !== lastG) { html += `<tr><td colspan="3" class="ex-grp">${m.g}</td></tr>`; lastG = m.g; }
    const v = exVal(m.k, i), p = exPct(m.k, v);
    const col = p === null ? '#334155' : (p >= 95 ? '#ef4444' : p >= 80 ? '#f59e0b' : '#38bdf8');
    html += `<tr title="${exEsc(m.d)}"><td>${m.label}</td><td><strong>${exFmt(v)}</strong></td><td><div class="ex-pbar"><div style="width:${p === null ? 0 : p.toFixed(0)}%;background:${col}"></div></div><span class="ex-ptxt">${p === null ? '-' : 'P' + p.toFixed(0)}</span></td></tr>`;
  });
  html += '</tbody></table>';
  const cpl = DATA.coupling.filter(r => r.file_a === f || r.file_b === f);
  if (cpl.length) {
    html += '<div class="ex-sec">Change-coupled with (&gt;70%)</div>' + cpl.map(r => {
      const other = r.file_a === f ? r.file_b : r.file_a;
      const conf = r.file_a === f ? r.confidence_a_to_b : r.confidence_b_to_a;
      return `<div class="ex-li"><a href="#" onclick="exSelectPath('${other}');return false;">${other.split('/').pop()}</a> - ${r.shared_commits} shared, ${(conf * 100).toFixed(0)}% ${r.has_direct_dep ? '(direct dep)' : '<span class="badge b-red">no direct dep</span>'}</div>`;
    }).join('');
  }
  const kl = DATA.knowledge_loss.find(r => r.file_path === f);
  if (kl) html += `<div class="ex-sec">Knowledge-loss risk</div><div class="ex-li">All-time authors: <strong>${kl.all_time_authors}</strong>, top owner ${exEsc(kl.all_time_top_author)} (${(kl.all_time_top_share * 100).toFixed(0)}%)</div>`;
  const cl = DATA.clones.filter(c => c.locations.some(l => l.startsWith(f + ':')));
  if (cl.length) html += '<div class="ex-sec">Duplicated code (CPD)</div>' + cl.map(c => `<div class="ex-li">${c.lines} lines / ${c.tokens} tokens with ${c.locations.filter(l => !l.startsWith(f + ':')).map(l => l.split('/').pop()).join(', ')}</div>`).join('');
  document.getElementById('ex-detail').innerHTML = html;
  if (exInited) exRender();
}
function exSelectPath(path) {
  const i = EX_IDX.get(path);
  if (i === undefined) return;
  // make sure the point is visible with current filters
  document.getElementById('ex-mod').value = 'ALL'; document.getElementById('ex-god').checked = false;
  document.getElementById('ex-inact').checked = false; document.getElementById('ex-minc').value = 0;
  const btn = document.getElementById('tabbtn-explorer3d');
  if (!document.getElementById('panel-explorer3d').classList.contains('active')) showTab('explorer3d', btn);
  exSelect(i);
}

// ---------- correlation heatmap ----------
function corrRender() {
  if (!window.Plotly) { document.getElementById('corr-plot').innerHTML = '<div class="sub">Plotly.js failed to load.</div>'; return; }
  const keys = EX.corr.keys, labels = keys.map(k => EX_M[k].label);
  const z = EX.corr.rho;
  Plotly.newPlot('corr-plot', [{
    type: 'heatmap', z, x: labels, y: labels, zmin: -1, zmax: 1, zmid: 0, colorscale: 'RdBu', reversescale: true,
    texttemplate: '%{z:.2f}', textfont: { size: 8 }, hovertemplate: '%{y} vs %{x}<br>rho = %{z:.3f}<extra></extra>',
    colorbar: { title: { text: 'rho' }, tickfont: { color: '#94a3b8' }, thickness: 14 },
  }], {
    paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', font: { color: '#cbd5e1', size: 10 },
    height: 820, margin: { l: 150, r: 20, t: 10, b: 150 },
    xaxis: { tickangle: -50, automargin: true }, yaxis: { autorange: 'reversed', automargin: true },
  }, { displaylogo: false, responsive: true });
  document.getElementById('corr-plot').on('plotly_click', ev => {
    const p = ev.points[0]; const kx = keys[labels.indexOf(p.x)], ky = keys[labels.indexOf(p.y)];
    if (kx === ky) return;
    document.getElementById('ex-x').value = kx; document.getElementById('ex-y').value = ky;
    document.getElementById('ex-lx').checked = EX_M[kx].log; document.getElementById('ex-ly').checked = EX_M[ky].log;
    showTab('explorer3d', document.getElementById('tabbtn-explorer3d'));
  });
  const rows = [];
  for (let a = 0; a < keys.length; a++) for (let b = a + 1; b < keys.length; b++) {
    if (EX_M[keys[a]].g === EX_M[keys[b]].g || z[a][b] === null) continue;
    rows.push([keys[a], keys[b], z[a][b]]);
  }
  rows.sort((p, q) => Math.abs(q[2]) - Math.abs(p[2]));
  document.getElementById('corr-table').innerHTML = '<thead><tr><th>Metric A</th><th>Metric B</th><th>&rho;</th><th>Strength</th><th></th></tr></thead><tbody>' +
    rows.slice(0, 30).map(([a, b, r]) => { const [l, c] = exStrength(r); return `<tr><td>${EX_M[a].label} <span class="sub">(${EX_M[a].g})</span></td><td>${EX_M[b].label} <span class="sub">(${EX_M[b].g})</span></td><td><strong>${r.toFixed(2)}</strong></td><td><span class="badge ${c}">${l}${r < 0 ? ', inverse' : ''}</span></td><td><a href="#" onclick="exOpenPair('${a}','${b}');return false;">open in 3D</a></td></tr>`; }).join('') + '</tbody>';
}
function exOpenPair(a, b) {
  document.getElementById('ex-x').value = a; document.getElementById('ex-y').value = b;
  document.getElementById('ex-lx').checked = EX_M[a].log; document.getElementById('ex-ly').checked = EX_M[b].log;
  showTab('explorer3d', document.getElementById('tabbtn-explorer3d'));
}

// ---------- wiring ----------
window.onTabShown = function (id) {
  if (id === 'explorer3d') { exRender(); if (window.Plotly) Plotly.Plots.resize('ex-plot'); }
  if (id === 'corr') { if (!corrInited) { corrRender(); corrInited = true; } else if (window.Plotly) Plotly.Plots.resize('corr-plot'); }
};
// clicking a row in the Top 10 / All Classes tables opens that class in the 3D Explorer
['top10-table', 'classes-table'].forEach(id => {
  document.getElementById(id).addEventListener('click', ev => {
    if (ev.target.closest('th')) return;
    const tr = ev.target.closest('tr'); const p = tr && tr.querySelector('.path');
    if (p) exSelectPath(p.getAttribute('title'));
  });
});
exInitControls();
