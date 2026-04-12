#!/usr/bin/env python3
"""
Genera un único index.html con índice navegable de la base de datos URSEC.
Uso: python3 generate_index.py [--output index.html] [--db db/files.csv]
"""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

DB_FILE = Path("db/files.csv")
BASE_DIR = Path(".").resolve()


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_records(db_path: Path) -> list[dict]:
    records = []
    with open(db_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lp = row.get("local_path", "").strip()
            row["local_file_url"] = (BASE_DIR / lp).resolve().as_uri() if lp else ""
            try:
                row["size_bytes"] = int(row["size_bytes"])
            except (ValueError, KeyError):
                row["size_bytes"] = 0
            fname = row.get("filename", "")
            row["ext"] = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
            row.setdefault("source", "datos")
            records.append(row)
    return records


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>URSEC · Índice de Datos Públicos</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:         #080b10;
  --surface:    #0f1318;
  --surface2:   #161b22;
  --surface3:   #1c2230;
  --border:     #21283a;
  --border2:    #2d3748;
  --text:       #d4dcea;
  --muted:      #5a6580;
  --muted2:     #8090a8;
  --accent:     #d4a017;
  --accent-glow:#d4a01740;
  --accent-dim: #7a5c08;
  --pdf:        #d95f5f;
  --xlsx:       #3dab6a;
  --ods:        #4d94d4;
  --docx:       #9b7fe8;
  --mark-bg:    #d4a01730;
  --mark-text:  #f0c040;
  --sidebar-w:  300px;
  --radius:     6px;
  --transition: 140ms ease;
  font-size: 14px;
}

html, body { height: 100%; overflow: hidden; }
body {
  display: flex;
  background: var(--bg);
  color: var(--text);
  font-family: 'Trebuchet MS', 'Segoe UI', system-ui, sans-serif;
  line-height: 1.5;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--surface); }
::-webkit-scrollbar-thumb { background: var(--border2); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--muted); }

/* ── Sidebar ─────────────────────────────────────────────── */
#sidebar {
  width: var(--sidebar-w); min-width: var(--sidebar-w);
  height: 100vh; background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column; overflow: hidden;
}
#sidebar-header {
  padding: 20px 18px 16px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.logo-eyebrow {
  font-size: 9px; letter-spacing: 0.2em; text-transform: uppercase;
  color: var(--accent); font-weight: 600; margin-bottom: 4px;
}
.logo-title {
  font-size: 16px; font-weight: 700; color: var(--text);
  letter-spacing: -0.02em; line-height: 1.2;
}
.logo-sub { font-size: 11px; color: var(--muted); margin-top: 3px; font-family: 'Courier New', monospace; }

#stats-bar { display: flex; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.stat-cell { flex: 1; padding: 9px 10px; border-right: 1px solid var(--border); text-align: center; }
.stat-cell:last-child { border-right: none; }
.stat-value { font-size: 18px; font-weight: 700; color: var(--accent); font-family: 'Courier New', monospace; line-height: 1; }
.stat-label { font-size: 9px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin-top: 2px; }

#sidebar-body {
  flex: 1; overflow-y: auto; padding: 14px 12px;
  display: flex; flex-direction: column; gap: 18px;
}
.filter-section { display: flex; flex-direction: column; gap: 7px; }
.filter-label {
  font-size: 9px; text-transform: uppercase; letter-spacing: 0.15em;
  color: var(--muted); font-weight: 600; padding-left: 2px;
}

/* search */
.search-wrap { position: relative; }
.search-wrap svg { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: var(--muted); pointer-events: none; }
#search-input {
  width: 100%; background: var(--surface2); border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--text);
  padding: 8px 30px 8px 32px; font-size: 13px; font-family: inherit; outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
}
#search-input::placeholder { color: var(--muted); }
#search-input:focus { border-color: var(--accent-dim); box-shadow: 0 0 0 2px var(--accent-glow); }
#search-clear {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  background: none; border: none; color: var(--muted); cursor: pointer;
  padding: 2px; display: none; line-height: 1; font-size: 13px;
}
#search-clear:hover { color: var(--text); }
#search-clear.visible { display: block; }

/* sort */
.sort-row { display: flex; gap: 4px; align-items: center; }
.sort-btn {
  flex: 1; background: var(--surface2); border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--muted2); padding: 6px 4px;
  font-size: 11px; cursor: pointer; transition: all var(--transition);
  text-align: center; font-family: inherit;
}
.sort-btn:hover { border-color: var(--border2); color: var(--text); }
.sort-btn.active { background: var(--surface3); border-color: var(--accent-dim); color: var(--accent); font-weight: 600; }
#sort-dir {
  background: var(--surface2); border: 1px solid var(--border); border-radius: var(--radius);
  color: var(--muted2); padding: 6px 8px; font-size: 13px; cursor: pointer;
  transition: all var(--transition); line-height: 1; font-family: inherit;
}
#sort-dir:hover { color: var(--text); border-color: var(--border2); }

/* ext filter */
.ext-row { display: flex; gap: 4px; flex-wrap: wrap; }
.ext-btn {
  flex: 1; min-width: 40px; padding: 5px 3px; border-radius: var(--radius);
  border: 1px solid var(--border); background: var(--surface2); color: var(--muted2);
  font-size: 10px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
  cursor: pointer; transition: all var(--transition); text-align: center;
  font-family: 'Courier New', monospace;
}
.ext-btn:hover { border-color: var(--border2); color: var(--text); }
.ext-btn.active[data-ext="pdf"]  { border-color: var(--pdf);  color: var(--pdf);  background: #d95f5f18; }
.ext-btn.active[data-ext="xlsx"] { border-color: var(--xlsx); color: var(--xlsx); background: #3dab6a18; }
.ext-btn.active[data-ext="ods"]  { border-color: var(--ods);  color: var(--ods);  background: #4d94d418; }
.ext-btn.active[data-ext="docx"] { border-color: var(--docx); color: var(--docx); background: #9b7fe818; }

/* category list */
#cat-list { display: flex; flex-direction: column; gap: 2px; max-height: 220px; overflow-y: auto; }
.cat-item {
  display: flex; align-items: center; gap: 8px; padding: 5px 7px; border-radius: 4px;
  cursor: pointer; transition: background var(--transition); user-select: none;
}
.cat-item:hover { background: var(--surface2); }
.cat-item.active { background: var(--surface3); }
.cat-check {
  width: 12px; height: 12px; border: 1px solid var(--border2); border-radius: 3px;
  flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  font-size: 9px; transition: all var(--transition);
}
.cat-item.active .cat-check { background: var(--accent); border-color: var(--accent); color: #000; }
.cat-name { font-size: 12px; color: var(--muted2); flex: 1; line-height: 1.3; transition: color var(--transition); }
.cat-item.active .cat-name { color: var(--text); }
.cat-count { font-size: 10px; color: var(--muted); font-family: 'Courier New', monospace; }

#clear-filters {
  width: 100%; padding: 7px; background: none; border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--muted); font-size: 12px;
  cursor: pointer; transition: all var(--transition); font-family: inherit;
}
#clear-filters:hover { border-color: var(--accent-dim); color: var(--accent); background: var(--accent-glow); }
#gen-at { font-size: 10px; color: var(--muted); text-align: center; padding: 8px 0 2px; font-family: 'Courier New', monospace; }

/* ── Main ────────────────────────────────────────────────── */
#main { flex: 1; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

#topbar {
  height: 44px; border-bottom: 1px solid var(--border); background: var(--surface);
  display: flex; align-items: center; padding: 0 18px; gap: 10px; flex-shrink: 0;
}
#result-count { font-size: 12px; color: var(--muted); white-space: nowrap; }
#result-count strong { color: var(--accent); font-family: 'Courier New', monospace; font-size: 14px; }
.topbar-divider { width: 1px; height: 18px; background: var(--border); flex-shrink: 0; }
#active-filters-bar { display: flex; gap: 5px; flex: 1; overflow: hidden; align-items: center; min-width: 0; }
.active-filter-pill {
  display: inline-flex; align-items: center; gap: 4px; padding: 2px 7px 2px 6px;
  background: var(--surface3); border: 1px solid var(--border2); border-radius: 20px;
  font-size: 11px; color: var(--muted2); white-space: nowrap; cursor: pointer;
  transition: all var(--transition);
}
.active-filter-pill:hover { border-color: var(--accent-dim); color: var(--accent); }
.active-filter-pill .pill-x { font-size: 11px; color: var(--muted); }

#chart-toggle-btn {
  margin-left: auto; padding: 4px 10px; background: var(--surface2);
  border: 1px solid var(--border2); border-radius: var(--radius);
  color: var(--muted2); font-size: 11px; cursor: pointer;
  transition: all var(--transition); white-space: nowrap; font-family: inherit; flex-shrink: 0;
}
#chart-toggle-btn:hover, #chart-toggle-btn.active { border-color: var(--accent-dim); color: var(--accent); background: var(--accent-glow); }

/* ── Chart panel ──────────────────────────────────────────── */
#chart-panel {
  border-bottom: 1px solid var(--border); background: var(--surface);
  flex-shrink: 0; overflow: hidden;
  max-height: 0; transition: max-height 320ms cubic-bezier(0.4,0,0.2,1);
}
#chart-panel.open { max-height: 280px; }

#chart-inner { padding: 10px 18px 8px; display: flex; flex-direction: column; gap: 8px; }

.chart-toolbar { display: flex; gap: 5px; align-items: center; }
.chart-toolbar-label { font-size: 9px; text-transform: uppercase; letter-spacing: 0.12em; color: var(--muted); margin-right: 2px; }
.chart-mode-btn {
  padding: 3px 10px; background: var(--surface2); border: 1px solid var(--border2);
  border-radius: 4px; color: var(--muted2); font-size: 10px; cursor: pointer;
  transition: all var(--transition); font-family: inherit;
}
.chart-mode-btn.active { border-color: var(--accent-dim); color: var(--accent); background: var(--accent-glow); }

#chart-svg-wrap { overflow-x: auto; overflow-y: hidden; }
#chart-svg, #activity-svg { display: block; }

/* activity chart */
.act-cell { rx: 2; }
.act-cell:hover { opacity: 0.75 !important; cursor: default; }

/* ── Table ────────────────────────────────────────────────── */
#table-wrap { flex: 1; overflow-y: auto; }
table { width: 100%; border-collapse: collapse; }
thead { position: sticky; top: 0; z-index: 10; background: var(--surface); }
thead th {
  padding: 9px 13px; text-align: left; font-size: 10px; text-transform: uppercase;
  letter-spacing: 0.1em; color: var(--muted); border-bottom: 1px solid var(--border);
  font-weight: 600; white-space: nowrap;
}
tbody tr { border-bottom: 1px solid var(--border); transition: background var(--transition); animation: fadeRow 220ms ease both; }
tbody tr:hover { background: var(--surface2); }
@keyframes fadeRow { from { opacity:0; transform:translateY(3px); } to { opacity:1; transform:translateY(0); } }
td { padding: 9px 13px; vertical-align: top; }

.td-date { white-space: nowrap; font-family: 'Courier New', monospace; font-size: 12px; color: var(--muted2); width: 94px; }
.td-ext  { width: 50px; }
.ext-badge {
  display: inline-block; padding: 2px 5px; border-radius: 3px; font-size: 10px;
  font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; font-family: 'Courier New', monospace;
}
.ext-badge.pdf  { background: #d95f5f22; color: var(--pdf);  border: 1px solid #d95f5f44; }
.ext-badge.xlsx { background: #3dab6a22; color: var(--xlsx); border: 1px solid #3dab6a44; }
.ext-badge.ods  { background: #4d94d422; color: var(--ods);  border: 1px solid #4d94d444; }
.ext-badge.docx { background: #9b7fe822; color: var(--docx); border: 1px solid #9b7fe844; }
.ext-badge.other{ background: var(--surface3); color: var(--muted); border: 1px solid var(--border); }

.td-cat { width: 140px; }
.cat-badge {
  display: inline-block; padding: 2px 7px; border-radius: 20px; font-size: 10px;
  background: var(--surface3); color: var(--muted2); border: 1px solid var(--border2);
  line-height: 1.4; max-width: 128px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.td-title { min-width: 220px; }
.row-title { font-size: 13px; color: var(--text); line-height: 1.4; margin-bottom: 3px; }
.row-filename { font-family: 'Courier New', monospace; font-size: 11px; color: var(--muted); word-break: break-all; }
.td-size { width: 78px; text-align: right; white-space: nowrap; font-family: 'Courier New', monospace; font-size: 12px; color: var(--muted); }
.td-actions { width: 68px; }
.action-row { display: flex; gap: 5px; align-items: center; }
.action-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 27px; height: 27px; border-radius: 5px; border: 1px solid var(--border2);
  background: var(--surface2); color: var(--muted2); text-decoration: none;
  cursor: pointer; transition: all var(--transition);
}
.action-btn:hover { border-color: var(--accent-dim); color: var(--accent); background: var(--accent-glow); }
.action-btn.local:hover { border-color: #3dab6a80; color: var(--xlsx); background: #3dab6a12; }
.action-btn.disabled { opacity: 0.25; pointer-events: none; }

#empty { display: none; text-align: center; padding: 70px 40px; color: var(--muted); }
#empty.show { display: block; }
#empty svg { margin: 0 auto 14px; display: block; opacity: 0.3; }
#empty h3 { font-size: 15px; color: var(--muted2); margin-bottom: 6px; }
#empty p { font-size: 13px; }
mark { background: var(--mark-bg); color: var(--mark-text); border-radius: 2px; padding: 0 1px; }

@media (max-width: 1000px) { :root { --sidebar-w: 260px; } .td-cat { display: none; } }
@media (max-width: 700px)  { #sidebar { display: none; } html, body { overflow: auto; } #main { height: auto; } }
</style>
</head>
<body>

<aside id="sidebar">
  <div id="sidebar-header">
    <div class="logo-eyebrow">República Oriental del Uruguay</div>
    <div class="logo-title">URSEC · Datos Públicos</div>
    <div class="logo-sub">Índice local · /*GENERATED_AT*/</div>
  </div>
  <div id="stats-bar">
    <div class="stat-cell"><div class="stat-value" id="stat-total">—</div><div class="stat-label">Total</div></div>
    <div class="stat-cell"><div class="stat-value" id="stat-shown">—</div><div class="stat-label">Visibles</div></div>
    <div class="stat-cell"><div class="stat-value" id="stat-cats">—</div><div class="stat-label">Categorías</div></div>
  </div>
  <div id="sidebar-body">
    <div class="filter-section">
      <div class="filter-label">Buscar</div>
      <div class="search-wrap">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <input id="search-input" type="text" placeholder="título, archivo, categoría…" autocomplete="off" spellcheck="false">
        <button id="search-clear" title="Limpiar">✕</button>
      </div>
    </div>
    <div class="filter-section">
      <div class="filter-label">Ordenar por</div>
      <div class="sort-row">
        <button class="sort-btn active" data-sort="date">Fecha</button>
        <button class="sort-btn" data-sort="title">Título</button>
        <button class="sort-btn" data-sort="size">Tamaño</button>
        <button id="sort-dir" title="Invertir orden">↓</button>
      </div>
    </div>
    <div class="filter-section">
      <div class="filter-label">Formato</div>
      <div class="ext-row">
        <button class="ext-btn" data-ext="pdf">PDF</button>
        <button class="ext-btn" data-ext="xlsx">XLSX</button>
        <button class="ext-btn" data-ext="ods">ODS</button>
        <button class="ext-btn" data-ext="docx">DOCX</button>
      </div>
    </div>
    <div class="filter-section">
      <div class="filter-label">Categoría</div>
      <div id="cat-list"></div>
    </div>
    <button id="clear-filters">✕ Limpiar todos los filtros</button>
    <div id="gen-at">Generado: /*GENERATED_AT*/</div>
  </div>
</aside>

<main id="main">
  <div id="topbar">
    <div id="result-count">Mostrando <strong id="count-shown">0</strong> de <strong id="count-total">0</strong> documentos</div>
    <div class="topbar-divider"></div>
    <div id="active-filters-bar"></div>
    <button id="chart-toggle-btn" class="active">▼ Gráfico</button>
  </div>

  <div id="chart-panel" class="open">
    <div id="chart-inner">
      <div class="chart-toolbar">
        <span class="chart-toolbar-label">Vista</span>
        <button class="chart-mode-btn active" data-mode="month">Barras / mes</button>
        <button class="chart-mode-btn" data-mode="year">Barras / año</button>
        <button class="chart-mode-btn" data-mode="activity">Actividad</button>
      </div>
      <div id="chart-svg-wrap">
        <svg id="chart-svg" height="180"></svg>
      </div>
    </div>
  </div>

  <div id="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Fecha</th>
          <th>Fmt</th>
          <th class="td-cat">Categoría</th>
          <th>Título / Archivo</th>
          <th style="text-align:right">Tamaño</th>
          <th>Links</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
    <div id="empty">
      <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        <line x1="8" y1="11" x2="14" y2="11"/>
      </svg>
      <h3>Sin resultados</h3>
      <p>No hay documentos que coincidan con los filtros aplicados.</p>
    </div>
  </div>
</main>

<script>
window.__DATA__ = /*INJECT_DATA*/[];

const state = {
  query: '', sort: 'date', dir: -1,
  exts: new Set(), cats: new Set(),
  chartMode: 'month', chartOpen: true,
};

// ── Helpers ──────────────────────────────────────────────────────────
function esc(s) {
  return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); }
function highlight(text,q) {
  const safe=esc(text); if(!q) return safe;
  return safe.replace(new RegExp(`(${escRe(esc(q))})`,'gi'),'<mark>$1</mark>');
}
function fmtSize(b) {
  if(!b) return '—';
  if(b<1024) return b+' B';
  if(b<1048576) return (b/1024).toFixed(1)+' KB';
  return (b/1048576).toFixed(1)+' MB';
}
function extClass(ext) { return ['pdf','xlsx','ods','docx'].includes(ext)?ext:'other'; }

// ── Filter & sort ────────────────────────────────────────────────────
function applyFilters() {
  const q = state.query.toLowerCase().trim();
  return window.__DATA__.filter(r => {
    if (state.exts.size && !state.exts.has(r.ext)) return false;
    if (state.cats.size && !state.cats.has(r.category)) return false;
    if (!q) return true;
    return r.title.toLowerCase().includes(q) ||
           r.filename.toLowerCase().includes(q) ||
           (r.category||'').toLowerCase().includes(q);
  }).sort((a,b) => {
    let cmp=0;
    if(state.sort==='date')  cmp=(a.date_published||'').localeCompare(b.date_published||'');
    if(state.sort==='title') cmp=a.title.localeCompare(b.title,'es');
    if(state.sort==='size')  cmp=(a.size_bytes||0)-(b.size_bytes||0);
    return cmp*state.dir;
  });
}

// ── Bar chart ────────────────────────────────────────────────────────
function renderBarChart(filtered, mode) {
  const svg  = document.getElementById('chart-svg');
  const wrap = document.getElementById('chart-svg-wrap');
  svg.style.display = 'block';

  // Build groups
  const groups = {};
  filtered.forEach(r => {
    const d = r.date_published||'';
    const key = mode==='year' ? d.slice(0,4) : d.slice(0,7);
    if(!key||key.length<4) return;
    groups[key] = (groups[key]||0)+1;
  });
  const data = Object.entries(groups).sort((a,b)=>a[0].localeCompare(b[0]));
  if(!data.length) { svg.innerHTML=''; return; }

  const H    = 180;
  const PAD  = { top: mode==='month'?30:16, bottom: mode==='month'?38:28, left:8, right:8 };
  const barW = mode==='year' ? 34 : 14;
  const gap  = mode==='year' ? 10 : 3;
  const plotH = H - PAD.top - PAD.bottom;
  const maxVal = Math.max(...data.map(([,v])=>v), 1);
  const totalW = Math.max(
    wrap.getBoundingClientRect().width || 500,
    PAD.left + data.length*(barW+gap) + PAD.right
  );

  svg.setAttribute('width',  totalW);
  svg.setAttribute('height', H);

  let out = '';

  // Gridlines + y-axis labels
  [0.25,0.5,0.75,1].forEach(f => {
    const val = Math.round(f*maxVal);
    const y   = PAD.top + plotH - Math.round(f*plotH);
    out += `<line x1="${PAD.left}" x2="${totalW-PAD.right}" y1="${y}" y2="${y}"
      stroke="var(--border)" stroke-width="1"/>`;
    out += `<text x="${PAD.left+2}" y="${y-3}" font-size="8" fill="var(--muted)"
      font-family="'Courier New',monospace">${val}</text>`;
  });

  // Year group metadata (month mode only)
  const yearMeta = {}; // year -> {firstIdx, lastIdx}
  if(mode==='month') {
    data.forEach(([key],i)=>{
      const yr = key.slice(0,4);
      if(!yearMeta[yr]) yearMeta[yr]={first:i,last:i};
      else yearMeta[yr].last = i;
    });
  }

  // Bars + x-axis labels
  const MONTHS = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
  data.forEach(([key,val],i) => {
    const x   = PAD.left + i*(barW+gap);
    const bh  = Math.max(2, Math.round((val/maxVal)*plotH));
    const y   = PAD.top + plotH - bh;

    // Bar
    out += `<rect x="${x}" y="${y}" width="${barW}" height="${bh}" rx="2"
      fill="var(--accent)" opacity="0.85">
      <title>${key}: ${val} doc${val>1?'s':''}</title>
    </rect>`;

    // X label
    if(mode==='year') {
      out += `<text x="${x+barW/2}" y="${H-6}" font-size="11" fill="var(--muted2)"
        text-anchor="middle" font-family="'Courier New',monospace">${key}</text>`;
    } else {
      // Month number below bar
      const mo = parseInt(key.slice(5),10);
      out += `<text x="${x+barW/2}" y="${H-24}" font-size="8" fill="var(--muted)"
        text-anchor="middle" font-family="'Courier New',monospace">${mo}</text>`;

      // Year separator: thin vertical line before first bar of year
      const yr = key.slice(0,4);
      if(yearMeta[yr] && yearMeta[yr].first===i && i>0) {
        const lx = x - gap/2 - 0.5;
        out += `<line x1="${lx}" x2="${lx}" y1="${PAD.top}" y2="${H-20}"
          stroke="var(--border2)" stroke-width="1" stroke-dasharray="3,2"/>`;
      }
    }
  });

  // Year labels above bars (month mode): centered over each year's bars
  if(mode==='month') {
    Object.entries(yearMeta).forEach(([yr,{first,last}]) => {
      const x1 = PAD.left + first*(barW+gap);
      const x2 = PAD.left + last*(barW+gap) + barW;
      const cx = (x1+x2)/2;
      out += `<text x="${cx}" y="${PAD.top-8}" font-size="10" fill="var(--accent)"
        text-anchor="middle" font-weight="700"
        font-family="'Trebuchet MS',sans-serif">${yr}</text>`;
      // Bracket line under year label
      out += `<line x1="${x1}" x2="${x2}" y1="${PAD.top-3}" y2="${PAD.top-3}"
        stroke="var(--accent-dim)" stroke-width="1"/>`;
    });

    // Month abbreviations on bottom axis (Ene, Feb…) — skip months if crowded
    const showAbbr = (barW+gap) >= 12;
    if(showAbbr) {
      data.forEach(([key],i) => {
        const x   = PAD.left + i*(barW+gap);
        const mo  = parseInt(key.slice(5),10) - 1;
        const lbl = MONTHS[mo]||'';
        out += `<text x="${x+barW/2}" y="${H-8}" font-size="8" fill="var(--muted)"
          text-anchor="middle" font-family="'Courier New',monospace">${lbl}</text>`;
      });
    }
  }

  svg.innerHTML = out;
}

// ── Activity heatmap ─────────────────────────────────────────────────
function renderActivity(filtered) {
  const svg  = document.getElementById('chart-svg');
  const wrap = document.getElementById('chart-svg-wrap');
  svg.style.display = 'block';

  // Build day counts
  const dayCounts = {};
  filtered.forEach(r => {
    const d = (r.date_published||'');
    if(d.length===10) dayCounts[d] = (dayCounts[d]||0)+1;
  });

  const allDays  = Object.keys(dayCounts).sort();
  if(!allDays.length) { svg.innerHTML=''; return; }

  const MS  = 86400000;
  const CELL= 11;
  const GAP = 2;
  const CS  = CELL+GAP; // cell step

  // Date range: earliest record → today
  const firstDate  = new Date(allDays[0]);
  const lastDate   = new Date();

  // Align start to previous Sunday
  const startSun = new Date(firstDate);
  startSun.setDate(startSun.getDate() - startSun.getDay());

  const totalDays  = Math.ceil((lastDate - startSun)/MS)+1;
  const totalWeeks = Math.ceil(totalDays/7);

  const LEFT_PAD = 22; // day labels
  const TOP_PAD  = 22; // month + year labels
  const H        = TOP_PAD + 7*CS + 4;
  const W        = LEFT_PAD + totalWeeks*CS;

  const maxCount = Math.max(...Object.values(dayCounts), 1);

  function cellColor(n) {
    if(!n) return '#1c2230';
    const t = n/maxCount;
    if(t<0.2)  return '#7a5c0888';
    if(t<0.45) return '#b08010bb';
    if(t<0.75) return '#d4a017cc';
    return '#f0c040';
  }

  let out = '';

  // Month + year labels at top
  const MNAMES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
  let lastMonthLabel = -1, lastYrLabel = -1;
  for(let w=0; w<totalWeeks; w++) {
    const d = new Date(startSun.getTime() + w*7*MS);
    const mo = d.getMonth(), yr = d.getFullYear();
    if(mo!==lastMonthLabel) {
      const x = LEFT_PAD + w*CS;
      if(yr!==lastYrLabel) {
        // Year label: bold, accent
        out += `<text x="${x}" y="10" font-size="9" fill="var(--accent)" font-weight="700"
          font-family="'Courier New',monospace">${yr}</text>`;
        lastYrLabel = yr;
      } else {
        // Month label: muted
        out += `<text x="${x}" y="10" font-size="9" fill="var(--muted2)"
          font-family="'Courier New',monospace">${MNAMES[mo]}</text>`;
      }
      lastMonthLabel = mo;
    }
  }

  // Day-of-week labels (L M X J V — skip D S)
  const DOW = ['D','L','M','X','J','V','S'];
  [1,2,3,4,5].forEach(d => {
    const y = TOP_PAD + d*CS + CELL - 2;
    out += `<text x="${LEFT_PAD-4}" y="${y}" font-size="8" fill="var(--muted)"
      text-anchor="end" font-family="'Courier New',monospace">${DOW[d]}</text>`;
  });

  // Cells
  for(let w=0; w<totalWeeks; w++) {
    for(let d=0; d<7; d++) {
      const cellDate = new Date(startSun.getTime()+(w*7+d)*MS);
      if(cellDate > lastDate) continue;
      const dateStr = cellDate.toISOString().slice(0,10);
      const count   = dayCounts[dateStr]||0;
      const x       = LEFT_PAD + w*CS;
      const y       = TOP_PAD + d*CS;
      const tip     = count ? `${dateStr}: ${count} doc${count>1?'s':''}` : dateStr;
      out += `<rect class="act-cell" x="${x}" y="${y}" width="${CELL}" height="${CELL}"
        rx="2" fill="${cellColor(count)}" opacity="${count?1:0.7}">
        <title>${tip}</title>
      </rect>`;
    }
  }

  // Color scale legend
  const lx = LEFT_PAD + 2;
  const ly  = H - 1;
  out += `<text x="${lx}" y="${ly}" font-size="8" fill="var(--muted)" font-family="'Courier New',monospace">Menos</text>`;
  [0,0.2,0.45,0.75,1].forEach((t,i) => {
    out += `<rect x="${lx+36+i*14}" y="${ly-9}" width="${CELL}" height="${CELL}" rx="2" fill="${cellColor(t===0?0:Math.ceil(t*maxCount))}"/>`;
  });
  out += `<text x="${lx+36+5*14+2}" y="${ly}" font-size="8" fill="var(--muted)" font-family="'Courier New',monospace">Más</text>`;

  svg.setAttribute('width',  W);
  svg.setAttribute('height', H+10);
  svg.innerHTML = out;
}

// ── Dispatch chart render ─────────────────────────────────────────────
function renderChart(filtered) {
  if(!state.chartOpen) return;
  if(state.chartMode==='activity') renderActivity(filtered);
  else renderBarChart(filtered, state.chartMode);
}

// ── Render table rows ─────────────────────────────────────────────────
function render() {
  const filtered = applyFilters();
  const tbody = document.getElementById('tbody');
  const empty = document.getElementById('empty');
  const q = state.query.trim();

  document.getElementById('count-shown').textContent = filtered.length;
  document.getElementById('stat-shown').textContent  = filtered.length;
  renderChart(filtered);

  if(!filtered.length) { tbody.innerHTML=''; empty.classList.add('show'); return; }
  empty.classList.remove('show');

  tbody.innerHTML = filtered.map((r,i) => {
    const ec      = extClass(r.ext);
    const srcHref = esc(r.url||'');
    const locHref = esc(r.local_file_url||'');
    const hasLocal= !!r.local_file_url;
    return `<tr style="animation-delay:${Math.min(i*16,400)}ms">
      <td class="td-date">${esc(r.date_published||'—')}</td>
      <td class="td-ext"><span class="ext-badge ${ec}">${esc(r.ext||'?')}</span></td>
      <td class="td-cat"><span class="cat-badge" title="${esc(r.category)}">${highlight(r.category||'—',q)}</span></td>
      <td class="td-title">
        <div class="row-title">${highlight(r.title,q)}</div>
        <div class="row-filename">${highlight(r.filename,q)}</div>
      </td>
      <td class="td-size">${fmtSize(r.size_bytes)}</td>
      <td class="td-actions">
        <div class="action-row">
          <a class="action-btn" href="${srcHref}" target="_blank" rel="noopener" title="Fuente original">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
              <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
          </a>
          <a class="action-btn local ${hasLocal?'':'disabled'}" href="${locHref}" title="Abrir local">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/>
            </svg>
          </a>
        </div>
      </td>
    </tr>`;
  }).join('');
}

function renderActiveFilters() {
  const bar = document.getElementById('active-filters-bar');
  const pills = [];
  if(state.query)
    pills.push(`<span class="active-filter-pill" data-action="clear-query">🔍 "${esc(state.query)}" <span class="pill-x">✕</span></span>`);
  state.exts.forEach(e =>
    pills.push(`<span class="active-filter-pill" data-action="clear-ext" data-val="${esc(e)}">.${esc(e)} <span class="pill-x">✕</span></span>`));
  state.cats.forEach(c =>
    pills.push(`<span class="active-filter-pill" data-action="clear-cat" data-val="${esc(c)}">${esc(c||'Sin cat')} <span class="pill-x">✕</span></span>`));
  bar.innerHTML = pills.join('');
}

function updateAll() { render(); renderActiveFilters(); }

function buildCatList() {
  const counts = {};
  window.__DATA__.forEach(r => { const c=r.category||''; counts[c]=(counts[c]||0)+1; });
  const cats = Object.entries(counts).sort((a,b)=>b[1]-a[1]||(a[0]||'zzz').localeCompare(b[0]||'zzz','es'));
  document.getElementById('stat-total').textContent  = window.__DATA__.length;
  document.getElementById('stat-cats').textContent   = Object.keys(counts).length;
  document.getElementById('count-total').textContent = window.__DATA__.length;
  document.getElementById('cat-list').innerHTML = cats.map(([c,n])=>`
    <div class="cat-item" data-cat="${esc(c)}">
      <div class="cat-check">✓</div>
      <div class="cat-name">${esc(c||'Sin categoría')}</div>
      <div class="cat-count">${n}</div>
    </div>`).join('');
}

// ── Events ────────────────────────────────────────────────────────────
let searchTimer;
document.getElementById('search-input').addEventListener('input', e => {
  clearTimeout(searchTimer);
  const v = e.target.value;
  document.getElementById('search-clear').classList.toggle('visible', !!v);
  searchTimer = setTimeout(() => { state.query=v; updateAll(); }, 220);
});
document.getElementById('search-clear').addEventListener('click', () => {
  document.getElementById('search-input').value='';
  document.getElementById('search-clear').classList.remove('visible');
  state.query=''; updateAll();
});

document.querySelectorAll('.sort-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const s=btn.dataset.sort;
    state.dir = (state.sort===s) ? state.dir*-1 : (s==='date'?-1:1);
    state.sort=s;
    document.querySelectorAll('.sort-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('sort-dir').textContent = state.dir===-1?'↓':'↑';
    render();
  });
});
document.getElementById('sort-dir').addEventListener('click', () => {
  state.dir*=-1;
  document.getElementById('sort-dir').textContent=state.dir===-1?'↓':'↑';
  render();
});

document.querySelectorAll('.ext-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const e=btn.dataset.ext;
    if(state.exts.has(e)) state.exts.delete(e); else state.exts.add(e);
    btn.classList.toggle('active', state.exts.has(e));
    updateAll();
  });
});

document.getElementById('cat-list').addEventListener('click', e => {
  const item=e.target.closest('.cat-item'); if(!item) return;
  const c=item.dataset.cat;
  if(state.cats.has(c)) state.cats.delete(c); else state.cats.add(c);
  item.classList.toggle('active', state.cats.has(c));
  updateAll();
});

document.getElementById('active-filters-bar').addEventListener('click', e => {
  const pill=e.target.closest('.active-filter-pill'); if(!pill) return;
  const {action,val}=pill.dataset;
  if(action==='clear-query') {
    state.query='';
    document.getElementById('search-input').value='';
    document.getElementById('search-clear').classList.remove('visible');
  } else if(action==='clear-ext') {
    state.exts.delete(val);
    document.querySelector(`.ext-btn[data-ext="${val}"]`)?.classList.remove('active');
  } else if(action==='clear-cat') {
    state.cats.delete(val);
    document.querySelector(`.cat-item[data-cat="${CSS.escape(val)}"]`)?.classList.remove('active');
  }
  updateAll();
});

document.getElementById('clear-filters').addEventListener('click', () => {
  state.query=''; state.exts.clear(); state.cats.clear();
  document.getElementById('search-input').value='';
  document.getElementById('search-clear').classList.remove('visible');
  document.querySelectorAll('.sort-btn').forEach(b=>b.classList.remove('active'));
  document.querySelector('.sort-btn[data-sort="date"]').classList.add('active');
  state.sort='date'; state.dir=-1;
  document.getElementById('sort-dir').textContent='↓';
  document.querySelectorAll('.ext-btn,.cat-item').forEach(el=>el.classList.remove('active'));
  updateAll();
});

document.getElementById('chart-toggle-btn').addEventListener('click', () => {
  state.chartOpen = !state.chartOpen;
  document.getElementById('chart-panel').classList.toggle('open', state.chartOpen);
  const btn = document.getElementById('chart-toggle-btn');
  btn.classList.toggle('active', state.chartOpen);
  btn.textContent = state.chartOpen ? '▼ Gráfico' : '▲ Gráfico';
  if(state.chartOpen) renderChart(applyFilters());
});

document.querySelectorAll('.chart-mode-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    state.chartMode=btn.dataset.mode;
    document.querySelectorAll('.chart-mode-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    renderChart(applyFilters());
  });
});

window.addEventListener('resize', () => { if(state.chartOpen) renderChart(applyFilters()); });

// ── Init ──────────────────────────────────────────────────────────────
buildCatList();
updateAll();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Genera index.html desde db/files.csv")
    parser.add_argument("--output", default="index.html")
    parser.add_argument("--db",     default=str(DB_FILE))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: no se encontró {db_path}", file=__import__("sys").stderr)
        raise SystemExit(1)

    records      = load_records(db_path)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    data_json    = json.dumps(records, ensure_ascii=False, separators=(",", ":"))

    html = (
        TEMPLATE
        .replace("/*INJECT_DATA*/[]", data_json)
        .replace("/*GENERATED_AT*/",  generated_at)
    )

    out = Path(args.output)
    out.write_text(html, encoding="utf-8")
    size_kb = out.stat().st_size / 1024
    print(f"Generado: {out}  ({len(records)} registros, {size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
