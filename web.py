#!/usr/bin/env python3
"""
Genera docs/index.html para GitHub Pages con el índice de datos públicos de URSEC.
Uso: python3 web.py [--output docs/index.html] [--db db/files.csv]
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

DB_FILE     = Path("db/files.csv")
OUTPUT_FILE = Path("docs/index.html")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def load_records(db_path: Path) -> list[dict]:
    """Carga el CSV y devuelve sólo los campos necesarios para la web (sin rutas locales)."""
    records = []
    with open(db_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                size_bytes = int(row.get("size_bytes", 0) or 0)
            except ValueError:
                size_bytes = 0
            fname = row.get("filename", "")
            ext   = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
            records.append({
                "url":            row.get("url", ""),
                "title":          row.get("title", ""),
                "filename":       fname,
                "date_published": row.get("date_published", ""),
                "category":       row.get("category", ""),
                "size_str":       row.get("size_str", ""),
                "size_bytes":     size_bytes,
                "ext":            ext,
                "source":         row.get("source", "datos"),
            })
    return records


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>URSEC · Datos Públicos</title>
<meta name="description" content="Índice navegable de datos públicos de la Unidad Reguladora de Servicios de Comunicaciones de Uruguay.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --brand:         #1B4F8A;
  --brand-dark:    #133A6B;
  --brand-mid:     #2563EB;
  --brand-light:   #EFF6FF;
  --brand-border:  #BFDBFE;
  --accent:        #2563EB;
  --accent-hover:  #1D4ED8;
  --bg:            #F1F5F9;
  --surface:       #FFFFFF;
  --surface2:      #F8FAFC;
  --border:        #E2E8F0;
  --border-mid:    #CBD5E1;
  --text:          #0F172A;
  --text-muted:    #475569;
  --text-subtle:   #94A3B8;
  --mark-bg:       #FEF08A;
  --mark-text:     #713F12;
  --pdf:           #DC2626;
  --xlsx:          #16A34A;
  --ods:           #2563EB;
  --docx:          #7C3AED;
  --radius:        6px;
  --sidebar-w:     264px;
  --header-h:      60px;
  --transition:    140ms ease;
}

html, body {
  height: 100%; overflow: hidden;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  font-size: 14px; color: var(--text); background: var(--bg);
  line-height: 1.5; -webkit-font-smoothing: antialiased;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-mid); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-subtle); }

/* ── Header ──────────────────────────────────────────────────────── */
#header {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  height: var(--header-h);
  background: var(--brand);
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  display: flex; align-items: center; padding: 0 20px; gap: 18px;
}
.logo-badge {
  background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25);
  border-radius: var(--radius); padding: 5px 10px;
  font-size: 12px; font-weight: 700; color: #fff;
  letter-spacing: 0.08em; text-transform: uppercase; flex-shrink: 0;
}
.header-text { flex-shrink: 0; }
.header-title { color: #fff; font-size: 15px; font-weight: 600; letter-spacing: -0.01em; }
.header-sub { color: rgba(255,255,255,0.6); font-size: 11px; margin-top: 1px; }
.header-div { width: 1px; height: 26px; background: rgba(255,255,255,0.2); flex-shrink: 0; }
.header-stats { display: flex; gap: 20px; }
.hstat { color: rgba(255,255,255,0.7); font-size: 12px; display: flex; align-items: baseline; gap: 5px; }
.hstat strong { color: #fff; font-size: 17px; font-weight: 700; font-variant-numeric: tabular-nums; }
.header-right { margin-left: auto; display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.gen-at { font-size: 11px; color: rgba(255,255,255,0.45); }
.ursec-link {
  font-size: 11px; color: rgba(255,255,255,0.7); text-decoration: none;
  padding: 5px 11px; border: 1px solid rgba(255,255,255,0.25); border-radius: var(--radius);
  transition: all var(--transition); white-space: nowrap;
}
.ursec-link:hover { color: #fff; border-color: rgba(255,255,255,0.5); background: rgba(255,255,255,0.1); }

/* ── Layout ───────────────────────────────────────────────────────── */
#layout { display: flex; height: 100vh; padding-top: var(--header-h); }

/* ── Sidebar ──────────────────────────────────────────────────────── */
#sidebar {
  width: var(--sidebar-w); min-width: var(--sidebar-w);
  height: 100%; background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex; flex-direction: column; overflow: hidden;
}
#sidebar-body {
  flex: 1; overflow-y: auto; padding: 14px 12px;
  display: flex; flex-direction: column; gap: 16px;
}
.filter-section {}
.filter-label {
  display: block; font-size: 10px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--text-subtle); margin-bottom: 7px; padding: 0 2px;
}
/* search */
.search-wrap { position: relative; }
.search-wrap svg {
  position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
  color: var(--text-subtle); pointer-events: none; width: 14px; height: 14px;
}
#search-input {
  width: 100%; background: var(--surface2); border: 1px solid var(--border-mid);
  border-radius: var(--radius); color: var(--text);
  padding: 8px 30px 8px 33px; font-size: 13px; font-family: inherit; outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
}
#search-input::placeholder { color: var(--text-subtle); }
#search-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(37,99,235,0.12); }
#search-clear {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  background: none; border: none; color: var(--text-subtle);
  cursor: pointer; padding: 2px; display: none; line-height: 1; font-size: 13px;
  transition: color var(--transition);
}
#search-clear:hover { color: var(--text); }
#search-clear.visible { display: block; }
/* ext */
.ext-row { display: flex; gap: 4px; flex-wrap: wrap; }
.ext-btn {
  flex: 1; min-width: 40px; padding: 5px 4px; border-radius: var(--radius);
  border: 1px solid var(--border-mid); background: var(--surface2); color: var(--text-muted);
  font-size: 10px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
  cursor: pointer; transition: all var(--transition); text-align: center; font-family: inherit;
}
.ext-btn:hover { color: var(--text); background: var(--surface); }
.ext-btn.active[data-ext="pdf"]  { border-color: var(--pdf);  color: var(--pdf);  background: #FEF2F2; }
.ext-btn.active[data-ext="xlsx"] { border-color: var(--xlsx); color: var(--xlsx); background: #F0FDF4; }
.ext-btn.active[data-ext="ods"]  { border-color: var(--ods);  color: var(--ods);  background: #EFF6FF; }
.ext-btn.active[data-ext="docx"] { border-color: var(--docx); color: var(--docx); background: #F5F3FF; }
/* source */
.source-row { display: flex; gap: 4px; }
.src-btn {
  flex: 1; padding: 6px 4px; border-radius: var(--radius);
  border: 1px solid var(--border-mid); background: var(--surface2); color: var(--text-muted);
  font-size: 11px; font-weight: 500; cursor: pointer; text-align: center;
  transition: all var(--transition); font-family: inherit;
}
.src-btn:hover { color: var(--text); }
.src-btn.active { border-color: var(--accent); color: var(--accent); background: var(--brand-light); font-weight: 600; }
/* categories */
#cat-list { display: flex; flex-direction: column; gap: 1px; max-height: 260px; overflow-y: auto; }
.cat-item {
  display: flex; align-items: center; gap: 8px; padding: 5px 7px;
  border-radius: var(--radius); cursor: pointer; transition: background var(--transition); user-select: none;
}
.cat-item:hover { background: var(--surface2); }
.cat-item.active { background: var(--brand-light); }
.cat-check {
  width: 14px; height: 14px; border: 1.5px solid var(--border-mid); border-radius: 3px;
  flex-shrink: 0; display: flex; align-items: center; justify-content: center;
  font-size: 9px; transition: all var(--transition);
}
.cat-item.active .cat-check { background: var(--accent); border-color: var(--accent); color: #fff; }
.cat-name { font-size: 12px; color: var(--text-muted); flex: 1; line-height: 1.3; transition: color var(--transition); }
.cat-item.active .cat-name { color: var(--accent); font-weight: 500; }
.cat-count { font-size: 10px; color: var(--text-subtle); font-variant-numeric: tabular-nums; }
/* sidebar footer */
#sidebar-footer { padding: 10px 12px; border-top: 1px solid var(--border); flex-shrink: 0; }
#clear-filters {
  width: 100%; padding: 7px; background: none; border: 1px solid var(--border-mid);
  border-radius: var(--radius); color: var(--text-muted); font-size: 12px;
  cursor: pointer; transition: all var(--transition); font-family: inherit;
}
#clear-filters:hover { border-color: var(--accent); color: var(--accent); background: var(--brand-light); }

/* ── Main ─────────────────────────────────────────────────────────── */
#main { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
/* topbar */
#topbar {
  height: 44px; flex-shrink: 0; border-bottom: 1px solid var(--border);
  background: var(--surface); display: flex; align-items: center; padding: 0 16px; gap: 10px;
}
#result-count { font-size: 12px; color: var(--text-muted); white-space: nowrap; }
#result-count strong { color: var(--accent); font-size: 14px; font-weight: 700; font-variant-numeric: tabular-nums; }
.tb-sep { width: 1px; height: 16px; background: var(--border); flex-shrink: 0; }
#active-filters-bar { display: flex; gap: 4px; flex: 1; overflow: hidden; align-items: center; min-width: 0; }
.active-filter-pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px 2px 7px;
  background: var(--brand-light); border: 1px solid var(--brand-border);
  border-radius: 20px; font-size: 11px; color: var(--accent);
  white-space: nowrap; cursor: pointer; transition: all var(--transition); font-weight: 500;
}
.active-filter-pill:hover { background: #DBEAFE; }
.active-filter-pill .pill-x { opacity: 0.6; font-size: 11px; }
.sort-group { display: flex; gap: 4px; align-items: center; margin-left: auto; flex-shrink: 0; }
.sort-lbl { font-size: 10px; color: var(--text-subtle); text-transform: uppercase; letter-spacing: 0.06em; }
.sort-btn {
  padding: 4px 9px; background: var(--surface2); border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--text-muted); font-size: 11px;
  cursor: pointer; font-family: inherit; transition: all var(--transition);
}
.sort-btn:hover { border-color: var(--border-mid); color: var(--text); }
.sort-btn.active { background: var(--brand-light); border-color: var(--brand-border); color: var(--accent); font-weight: 600; }
#sort-dir {
  padding: 4px 8px; background: var(--surface2); border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--text-muted); font-size: 12px;
  cursor: pointer; font-family: inherit; transition: all var(--transition);
}
#sort-dir:hover { color: var(--text); border-color: var(--border-mid); }
#chart-toggle-btn {
  padding: 4px 10px; background: var(--surface2); border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--text-muted); font-size: 11px;
  cursor: pointer; font-family: inherit; transition: all var(--transition); white-space: nowrap;
}
#chart-toggle-btn:hover { border-color: var(--border-mid); color: var(--text); }
#chart-toggle-btn.active { background: var(--brand-light); border-color: var(--brand-border); color: var(--accent); }

/* ── Chart ────────────────────────────────────────────────────────── */
#chart-panel {
  border-bottom: 1px solid var(--border); background: var(--surface);
  flex-shrink: 0; overflow: hidden;
  max-height: 0; transition: max-height 320ms cubic-bezier(0.4,0,0.2,1);
}
#chart-panel.open { max-height: 260px; }
#chart-inner { padding: 12px 16px 10px; display: flex; flex-direction: column; gap: 8px; }
.chart-toolbar { display: flex; gap: 4px; align-items: center; }
.chart-tb-lbl { font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-subtle); margin-right: 4px; }
.chart-mode-btn {
  padding: 3px 10px; background: var(--surface2); border: 1px solid var(--border);
  border-radius: var(--radius); color: var(--text-muted); font-size: 11px;
  cursor: pointer; font-family: inherit; transition: all var(--transition);
}
.chart-mode-btn:hover { border-color: var(--border-mid); color: var(--text); }
.chart-mode-btn.active { background: var(--brand-light); border-color: var(--brand-border); color: var(--accent); font-weight: 600; }
#chart-svg-wrap { overflow-x: auto; overflow-y: hidden; }
#chart-svg { display: block; }
.act-cell:hover { opacity: 0.75 !important; cursor: default; }

/* ── Table ────────────────────────────────────────────────────────── */
#table-wrap { flex: 1; overflow: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
thead {
  position: sticky; top: 0; z-index: 10;
  background: var(--surface2); border-bottom: 2px solid var(--border-mid);
}
th {
  padding: 10px 12px; text-align: left;
  font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--text-muted); white-space: nowrap; user-select: none;
}
th:first-child { padding-left: 16px; }
th:last-child { padding-right: 16px; }
tbody tr { border-bottom: 1px solid var(--border); transition: background var(--transition); }
tbody tr:hover { background: #F5F8FF; }
tbody tr:last-child { border-bottom: none; }
td { padding: 10px 12px; vertical-align: middle; }
td:first-child { padding-left: 16px; }
td:last-child { padding-right: 16px; }
.td-date { font-size: 12px; color: var(--text-muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
.td-ext { width: 54px; }
.ext-badge {
  display: inline-block; padding: 2px 6px; border-radius: 4px;
  font-size: 10px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
}
.ext-pdf  { background: #FEF2F2; color: var(--pdf);  border: 1px solid #FECACA; }
.ext-xlsx { background: #F0FDF4; color: var(--xlsx); border: 1px solid #BBF7D0; }
.ext-ods  { background: #EFF6FF; color: var(--ods);  border: 1px solid #BFDBFE; }
.ext-docx { background: #F5F3FF; color: var(--docx); border: 1px solid #DDD6FE; }
.ext-other{ background: var(--surface2); color: var(--text-muted); border: 1px solid var(--border); }
.td-cat { min-width: 110px; max-width: 170px; }
.cat-badge { display: inline-block; max-width: 100%; font-size: 11px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.td-title { min-width: 200px; }
.row-title { font-size: 13px; font-weight: 500; color: var(--text); line-height: 1.4; }
.row-filename { font-size: 11px; color: var(--text-subtle); margin-top: 2px; }
.td-size { font-size: 12px; color: var(--text-muted); white-space: nowrap; font-variant-numeric: tabular-nums; text-align: right; }
.td-src { white-space: nowrap; }
.src-badge {
  display: inline-block; padding: 2px 7px; border-radius: 20px;
  font-size: 10px; font-weight: 500; background: var(--surface2);
  border: 1px solid var(--border); color: var(--text-subtle);
}
.td-actions { width: 46px; }
.dl-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 30px; height: 30px;
  background: var(--brand-light); border: 1px solid var(--brand-border);
  border-radius: var(--radius); color: var(--accent); text-decoration: none;
  transition: all var(--transition);
}
.dl-btn:hover { background: var(--accent); border-color: var(--accent); color: #fff; }
mark { background: var(--mark-bg); color: var(--mark-text); padding: 0 1px; border-radius: 2px; }
/* empty state */
#empty { display: none; flex-direction: column; align-items: center; justify-content: center; padding: 80px 20px; color: var(--text-muted); text-align: center; gap: 10px; }
#empty.show { display: flex; }
#empty .empty-icon { font-size: 36px; opacity: 0.3; }
#empty p { font-size: 14px; }
#empty small { font-size: 12px; color: var(--text-subtle); }
</style>
</head>
<body>

<!-- Header -->
<header id="header">
  <div class="logo-badge">URSEC</div>
  <div class="header-text">
    <div class="header-title">Datos Públicos</div>
    <div class="header-sub">Unidad Reguladora de Servicios de Comunicaciones · Uruguay</div>
  </div>
  <div class="header-div"></div>
  <div class="header-stats">
    <div class="hstat"><strong id="stat-total">0</strong> documentos</div>
    <div class="hstat"><strong id="stat-cats">0</strong> categorías</div>
  </div>
  <div class="header-right">
    <span class="gen-at">Actualizado: /*GENERATED_AT*/</span>
    <a class="ursec-link" href="https://www.gub.uy/unidad-reguladora-servicios-comunicaciones/datos-y-estadisticas/datos" target="_blank" rel="noopener">↗ Fuente</a>
  </div>
</header>

<!-- Layout -->
<div id="layout">

  <!-- Sidebar -->
  <aside id="sidebar">
    <div id="sidebar-body">

      <div class="filter-section">
        <label class="filter-label" for="search-input">Buscar</label>
        <div class="search-wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input id="search-input" type="search" placeholder="Título, archivo…" autocomplete="off" spellcheck="false">
          <button id="search-clear" aria-label="Limpiar">✕</button>
        </div>
      </div>

      <div class="filter-section">
        <span class="filter-label">Formato</span>
        <div class="ext-row">
          <button class="ext-btn" data-ext="pdf">PDF</button>
          <button class="ext-btn" data-ext="xlsx">XLSX</button>
          <button class="ext-btn" data-ext="ods">ODS</button>
          <button class="ext-btn" data-ext="docx">DOCX</button>
        </div>
      </div>

      <div class="filter-section">
        <span class="filter-label">Fuente</span>
        <div class="source-row">
          <button class="src-btn active" data-src="">Todas</button>
          <button class="src-btn" data-src="datos">Datos</button>
          <button class="src-btn" data-src="telecom">Telecom</button>
        </div>
      </div>

      <div class="filter-section">
        <span class="filter-label">Categoría</span>
        <div id="cat-list"></div>
      </div>

    </div>
    <div id="sidebar-footer">
      <button id="clear-filters">Limpiar filtros</button>
    </div>
  </aside>

  <!-- Main -->
  <main id="main">

    <div id="topbar">
      <span id="result-count">Mostrando <strong id="count-shown">0</strong> de <span id="count-total">0</span></span>
      <div class="tb-sep"></div>
      <div id="active-filters-bar"></div>
      <div class="sort-group">
        <span class="sort-lbl">Orden:</span>
        <button class="sort-btn active" data-sort="date">Fecha</button>
        <button class="sort-btn" data-sort="title">Título</button>
        <button class="sort-btn" data-sort="size">Tamaño</button>
        <button id="sort-dir">↓</button>
        <div class="tb-sep"></div>
        <button id="chart-toggle-btn">▲ Gráfico</button>
      </div>
    </div>

    <div id="chart-panel">
      <div id="chart-inner">
        <div class="chart-toolbar">
          <span class="chart-tb-lbl">Vista:</span>
          <button class="chart-mode-btn active" data-mode="year">Por año</button>
          <button class="chart-mode-btn" data-mode="month">Por mes</button>
          <button class="chart-mode-btn" data-mode="category">Por categoría</button>
          <button class="chart-mode-btn" data-mode="activity">Actividad</button>
        </div>
        <div id="chart-svg-wrap"><svg id="chart-svg"></svg></div>
      </div>
    </div>

    <div id="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Fmt</th>
            <th>Categoría</th>
            <th>Documento</th>
            <th style="text-align:right">Tamaño</th>
            <th>Fuente</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
      <div id="empty">
        <div class="empty-icon">📂</div>
        <p>No se encontraron documentos</p>
        <small>Ajustá los filtros o la búsqueda</small>
      </div>
    </div>

  </main>
</div>

<script>
window.__DATA__ = /*INJECT_DATA*/[];

// ── State ─────────────────────────────────────────────────────────────
const state = { query:'', exts:new Set(), cats:new Set(), src:'', sort:'date', dir:-1, chartOpen:false, chartMode:'year' };

// ── Utils ─────────────────────────────────────────────────────────────
function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function highlight(text,q) {
  if(!q) return esc(text);
  const safeQ=q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  return esc(text).replace(new RegExp('('+safeQ+')','gi'),'<mark>$1</mark>');
}
function fmtSize(b) {
  if(!b) return '—';
  if(b<1024) return b+'B';
  if(b<1048576) return (b/1024).toFixed(1)+'KB';
  return (b/1048576).toFixed(1)+'MB';
}
function extClass(ext) {
  const e=(ext||'').toLowerCase();
  return ['pdf','xlsx','ods','docx'].includes(e)?'ext-'+e:'ext-other';
}

// ── Filter & sort ─────────────────────────────────────────────────────
function applyFilters() {
  let d=window.__DATA__.slice();
  const q=state.query.toLowerCase().trim();
  if(q) d=d.filter(r=>(r.title||'').toLowerCase().includes(q)||(r.filename||'').toLowerCase().includes(q)||(r.category||'').toLowerCase().includes(q));
  if(state.exts.size) d=d.filter(r=>state.exts.has((r.ext||'').toLowerCase()));
  if(state.cats.size) d=d.filter(r=>state.cats.has(r.category||''));
  if(state.src) d=d.filter(r=>(r.source||'')=== state.src);
  d.sort((a,b)=>{
    let va,vb;
    if(state.sort==='date'){va=a.date_published||'';vb=b.date_published||'';}
    else if(state.sort==='title'){va=(a.title||'').toLowerCase();vb=(b.title||'').toLowerCase();}
    else{va=a.size_bytes||0;vb=b.size_bytes||0;}
    return va<vb?-state.dir:va>vb?state.dir:0;
  });
  return d;
}

// ── Charts ────────────────────────────────────────────────────────────
function renderBarChart(filtered,mode) {
  const svg=document.getElementById('chart-svg');
  const wrap=document.getElementById('chart-svg-wrap');
  const counts={};
  filtered.forEach(r=>{
    let k;
    if(mode==='year') k=(r.date_published||'').slice(0,4);
    else if(mode==='month') k=(r.date_published||'').slice(0,7);
    else k=r.category||'Sin categoría';
    if(k) counts[k]=(counts[k]||0)+1;
  });
  const data=Object.entries(counts).sort((a,b)=>mode==='category'?b[1]-a[1]:a[0]<b[0]?-1:1);
  if(!data.length){svg.innerHTML='';return;}
  const PAD={top:28,right:16,bottom:40,left:32};
  const maxVal=Math.max(...data.map(d=>d[1]));
  const barW=mode==='category'?Math.max(20,Math.min(56,Math.floor(540/data.length)-4)):28;
  const gap=mode==='category'?3:6;
  const W=PAD.left+data.length*(barW+gap)+PAD.right;
  const H=200,plotH=H-PAD.top-PAD.bottom;
  svg.setAttribute('width',Math.max(W,wrap.clientWidth||300));
  svg.setAttribute('height',H);
  let out='';
  for(let t=0;t<=4;t++){
    const val=Math.round(maxVal*t/4);
    const y=PAD.top+plotH-Math.round((val/maxVal)*plotH);
    out+=`<line x1="${PAD.left}" x2="${W-PAD.right}" y1="${y}" y2="${y}" stroke="${t===0?'var(--border-mid)':'var(--border)'}" stroke-width="1"/>`;
    if(t>0) out+=`<text x="${PAD.left-4}" y="${y+4}" font-size="9" fill="var(--text-subtle)" text-anchor="end" font-family="Inter,system-ui">${val}</text>`;
  }
  const yearMeta={};
  if(mode==='month') data.forEach(([k],i)=>{const yr=k.slice(0,4);if(!yearMeta[yr]) yearMeta[yr]={first:i,last:i};else yearMeta[yr].last=i;});
  const MS_ABBR=['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
  data.forEach(([key,val],i)=>{
    const x=PAD.left+i*(barW+gap);
    const bh=Math.max(2,Math.round((val/maxVal)*plotH));
    const y=PAD.top+plotH-bh;
    out+=`<rect x="${x}" y="${y}" width="${barW}" height="${bh}" rx="3" fill="var(--accent)" opacity="0.82"><title>${esc(key)}: ${val} documento${val>1?'s':''}</title></rect>`;
    if(mode==='year'){
      out+=`<text x="${x+barW/2}" y="${H-8}" font-size="10" fill="var(--text-subtle)" text-anchor="middle" font-family="Inter,system-ui">${key}</text>`;
    } else if(mode==='month'){
      const mo=parseInt(key.slice(5),10);
      out+=`<text x="${x+barW/2}" y="${H-26}" font-size="8" fill="var(--text-subtle)" text-anchor="middle" font-family="Inter,system-ui">${mo}</text>`;
      const yr=key.slice(0,4);
      if(yearMeta[yr]&&yearMeta[yr].first===i&&i>0){const lx=x-gap/2-0.5;out+=`<line x1="${lx}" x2="${lx}" y1="${PAD.top}" y2="${H-20}" stroke="var(--border-mid)" stroke-width="1" stroke-dasharray="3,2"/>`;}
    } else {
      const lbl=key.length>14?key.slice(0,13)+'…':key;
      out+=`<text x="${x+barW/2}" y="${H-6}" font-size="9" fill="var(--text-subtle)" text-anchor="end" transform="rotate(-35 ${x+barW/2} ${H-6})" font-family="Inter,system-ui">${esc(lbl)}</text>`;
    }
  });
  if(mode==='month'){
    Object.entries(yearMeta).forEach(([yr,{first,last}])=>{
      const x1=PAD.left+first*(barW+gap),x2=PAD.left+last*(barW+gap)+barW,cx=(x1+x2)/2;
      out+=`<text x="${cx}" y="${PAD.top-8}" font-size="10" fill="var(--accent)" text-anchor="middle" font-weight="600" font-family="Inter,system-ui">${yr}</text>`;
      out+=`<line x1="${x1}" x2="${x2}" y1="${PAD.top-3}" y2="${PAD.top-3}" stroke="var(--brand-border)" stroke-width="1"/>`;
    });
    if((barW+gap)>=12) data.forEach(([key],i)=>{
      const x=PAD.left+i*(barW+gap);
      out+=`<text x="${x+barW/2}" y="${H-10}" font-size="8" fill="var(--text-subtle)" text-anchor="middle" font-family="Inter,system-ui">${MS_ABBR[parseInt(key.slice(5),10)-1]||''}</text>`;
    });
  }
  svg.innerHTML=out;
}

function renderActivity(filtered) {
  const svg=document.getElementById('chart-svg');
  const wrap=document.getElementById('chart-svg-wrap');
  const day={};
  filtered.forEach(r=>{const d=r.date_published||'';if(d.length===10) day[d]=(day[d]||0)+1;});
  const allDays=Object.keys(day).sort();
  if(!allDays.length){svg.innerHTML='';return;}
  const MS=86400000,CELL=11,GAP=2,CS=CELL+GAP;
  const first=new Date(allDays[0]),last=new Date();
  const sun=new Date(first);sun.setDate(sun.getDate()-sun.getDay());
  const weeks=Math.ceil((Math.ceil((last-sun)/MS)+1)/7);
  const LP=22,TP=22,H=TP+7*CS+4,W=LP+weeks*CS;
  const maxC=Math.max(...Object.values(day),1);
  function cc(n){if(!n)return '#EFF6FF';const t=n/maxC;if(t<0.2)return '#BFDBFE';if(t<0.45)return '#93C5FD';if(t<0.75)return '#3B82F6';return '#1D4ED8';}
  let out='';
  const MN=['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
  let lm=-1,ly=-1;
  for(let w=0;w<weeks;w++){
    const d=new Date(sun.getTime()+w*7*MS);const mo=d.getMonth(),yr=d.getFullYear();
    if(mo!==lm){const x=LP+w*CS;if(yr!==ly){out+=`<text x="${x}" y="10" font-size="9" fill="var(--accent)" font-weight="600" font-family="Inter,system-ui">${yr}</text>`;ly=yr;}else{out+=`<text x="${x}" y="10" font-size="9" fill="var(--text-subtle)" font-family="Inter,system-ui">${MN[mo]}</text>`;}lm=mo;}
  }
  ['L','M','X','J','V'].forEach((l,i)=>{const y=TP+(i+1)*CS+CELL-2;out+=`<text x="${LP-4}" y="${y}" font-size="8" fill="var(--text-subtle)" text-anchor="end" font-family="Inter,system-ui">${l}</text>`;});
  for(let w=0;w<weeks;w++){for(let d=0;d<7;d++){const cd=new Date(sun.getTime()+(w*7+d)*MS);if(cd>last)continue;const ds=cd.toISOString().slice(0,10);const c=day[ds]||0;out+=`<rect class="act-cell" x="${LP+w*CS}" y="${TP+d*CS}" width="${CELL}" height="${CELL}" rx="2" fill="${cc(c)}" opacity="${c?1:0.85}"><title>${c?ds+': '+c+' doc'+(c>1?'s':''):ds}</title></rect>`;}}
  const lx=LP+2,ly2=H-1;
  out+=`<text x="${lx}" y="${ly2}" font-size="8" fill="var(--text-subtle)" font-family="Inter,system-ui">Menos</text>`;
  [0,0.2,0.45,0.75,1].forEach((t,i)=>{out+=`<rect x="${lx+36+i*14}" y="${ly2-9}" width="${CELL}" height="${CELL}" rx="2" fill="${cc(t===0?0:Math.ceil(t*maxC))}"/>`;});
  out+=`<text x="${lx+36+5*14+2}" y="${ly2}" font-size="8" fill="var(--text-subtle)" font-family="Inter,system-ui">Más</text>`;
  svg.setAttribute('width',W);svg.setAttribute('height',H+10);svg.innerHTML=out;
}

function renderChart(filtered) {
  if(!state.chartOpen) return;
  if(state.chartMode==='activity') renderActivity(filtered);
  else renderBarChart(filtered,state.chartMode);
}

// ── Render table ──────────────────────────────────────────────────────
function render() {
  const filtered=applyFilters();
  const tbody=document.getElementById('tbody');
  const empty=document.getElementById('empty');
  const q=state.query.trim();
  document.getElementById('count-shown').textContent=filtered.length;
  renderChart(filtered);
  if(!filtered.length){tbody.innerHTML='';empty.classList.add('show');return;}
  empty.classList.remove('show');
  tbody.innerHTML=filtered.map(r=>`<tr>
    <td class="td-date">${esc(r.date_published||'—')}</td>
    <td class="td-ext"><span class="ext-badge ${extClass(r.ext)}">${esc(r.ext||'?')}</span></td>
    <td class="td-cat"><span class="cat-badge" title="${esc(r.category)}">${highlight(r.category||'—',q)}</span></td>
    <td class="td-title">
      <div class="row-title">${highlight(r.title||r.filename,q)}</div>
      <div class="row-filename">${highlight(r.filename,q)}</div>
    </td>
    <td class="td-size">${fmtSize(r.size_bytes)}</td>
    <td class="td-src"><span class="src-badge">${esc(r.source||'datos')}</span></td>
    <td class="td-actions">
      <a class="dl-btn" href="${esc(r.url||'#')}" target="_blank" rel="noopener" title="Descargar">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
      </a>
    </td>
  </tr>`).join('');
}

function renderActiveFilters() {
  const pills=[];
  if(state.query) pills.push(`<span class="active-filter-pill" data-action="clear-query">🔍 "${esc(state.query)}" <span class="pill-x">✕</span></span>`);
  state.exts.forEach(e=>pills.push(`<span class="active-filter-pill" data-action="clear-ext" data-val="${esc(e)}">.${esc(e)} <span class="pill-x">✕</span></span>`));
  state.cats.forEach(c=>pills.push(`<span class="active-filter-pill" data-action="clear-cat" data-val="${esc(c)}">${esc(c||'Sin cat')} <span class="pill-x">✕</span></span>`));
  if(state.src) pills.push(`<span class="active-filter-pill" data-action="clear-src">${esc(state.src)} <span class="pill-x">✕</span></span>`);
  document.getElementById('active-filters-bar').innerHTML=pills.join('');
}

function updateAll(){render();renderActiveFilters();}

function buildCatList() {
  const counts={};
  window.__DATA__.forEach(r=>{const c=r.category||'';counts[c]=(counts[c]||0)+1;});
  const cats=Object.entries(counts).sort((a,b)=>b[1]-a[1]||(a[0]||'zzz').localeCompare(b[0]||'zzz','es'));
  document.getElementById('stat-total').textContent=window.__DATA__.length;
  document.getElementById('stat-cats').textContent=Object.keys(counts).length;
  document.getElementById('count-total').textContent=window.__DATA__.length;
  document.getElementById('cat-list').innerHTML=cats.map(([c,n])=>`
    <div class="cat-item" data-cat="${esc(c)}">
      <div class="cat-check">✓</div>
      <div class="cat-name">${esc(c||'Sin categoría')}</div>
      <div class="cat-count">${n}</div>
    </div>`).join('');
}

// ── Events ────────────────────────────────────────────────────────────
let st;
document.getElementById('search-input').addEventListener('input',e=>{
  clearTimeout(st);const v=e.target.value;
  document.getElementById('search-clear').classList.toggle('visible',!!v);
  st=setTimeout(()=>{state.query=v;updateAll();},220);
});
document.getElementById('search-clear').addEventListener('click',()=>{
  document.getElementById('search-input').value='';
  document.getElementById('search-clear').classList.remove('visible');
  state.query='';updateAll();
});
document.querySelectorAll('.sort-btn').forEach(btn=>btn.addEventListener('click',()=>{
  const s=btn.dataset.sort;
  state.dir=(state.sort===s)?state.dir*-1:(s==='date'?-1:1);state.sort=s;
  document.querySelectorAll('.sort-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('sort-dir').textContent=state.dir===-1?'↓':'↑';render();
}));
document.getElementById('sort-dir').addEventListener('click',()=>{
  state.dir*=-1;document.getElementById('sort-dir').textContent=state.dir===-1?'↓':'↑';render();
});
document.querySelectorAll('.ext-btn').forEach(btn=>btn.addEventListener('click',()=>{
  const e=btn.dataset.ext;if(state.exts.has(e))state.exts.delete(e);else state.exts.add(e);
  btn.classList.toggle('active',state.exts.has(e));updateAll();
}));
document.querySelectorAll('.src-btn').forEach(btn=>btn.addEventListener('click',()=>{
  state.src=btn.dataset.src;
  document.querySelectorAll('.src-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');updateAll();
}));
document.getElementById('cat-list').addEventListener('click',e=>{
  const item=e.target.closest('.cat-item');if(!item)return;
  const c=item.dataset.cat;if(state.cats.has(c))state.cats.delete(c);else state.cats.add(c);
  item.classList.toggle('active',state.cats.has(c));updateAll();
});
document.getElementById('active-filters-bar').addEventListener('click',e=>{
  const pill=e.target.closest('.active-filter-pill');if(!pill)return;
  const {action,val}=pill.dataset;
  if(action==='clear-query'){state.query='';document.getElementById('search-input').value='';document.getElementById('search-clear').classList.remove('visible');}
  else if(action==='clear-ext'){state.exts.delete(val);document.querySelector(`.ext-btn[data-ext="${val}"]`)?.classList.remove('active');}
  else if(action==='clear-cat'){state.cats.delete(val);document.querySelector(`.cat-item[data-cat="${CSS.escape(val)}"]`)?.classList.remove('active');}
  else if(action==='clear-src'){state.src='';document.querySelector('.src-btn[data-src=""]')?.classList.add('active');document.querySelectorAll('.src-btn:not([data-src=""])').forEach(b=>b.classList.remove('active'));}
  updateAll();
});
document.getElementById('clear-filters').addEventListener('click',()=>{
  state.query='';state.exts.clear();state.cats.clear();state.src='';
  document.getElementById('search-input').value='';
  document.getElementById('search-clear').classList.remove('visible');
  document.querySelectorAll('.sort-btn').forEach(b=>b.classList.remove('active'));
  document.querySelector('.sort-btn[data-sort="date"]').classList.add('active');
  state.sort='date';state.dir=-1;document.getElementById('sort-dir').textContent='↓';
  document.querySelectorAll('.ext-btn,.cat-item').forEach(el=>el.classList.remove('active'));
  document.querySelector('.src-btn[data-src=""]').classList.add('active');
  document.querySelectorAll('.src-btn:not([data-src=""])').forEach(b=>b.classList.remove('active'));
  updateAll();
});
document.getElementById('chart-toggle-btn').addEventListener('click',()=>{
  state.chartOpen=!state.chartOpen;
  document.getElementById('chart-panel').classList.toggle('open',state.chartOpen);
  const btn=document.getElementById('chart-toggle-btn');
  btn.classList.toggle('active',state.chartOpen);
  btn.textContent=state.chartOpen?'▼ Gráfico':'▲ Gráfico';
  if(state.chartOpen) renderChart(applyFilters());
});
document.querySelectorAll('.chart-mode-btn').forEach(btn=>btn.addEventListener('click',()=>{
  state.chartMode=btn.dataset.mode;
  document.querySelectorAll('.chart-mode-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');renderChart(applyFilters());
}));
window.addEventListener('resize',()=>{if(state.chartOpen)renderChart(applyFilters());});

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
    parser = argparse.ArgumentParser(description="Genera docs/index.html para GitHub Pages")
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    parser.add_argument("--db",     default=str(DB_FILE))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: no se encontró {db_path}", file=sys.stderr)
        raise SystemExit(1)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    records      = load_records(db_path)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    data_json    = json.dumps(records, ensure_ascii=False, separators=(",", ":"))

    html = (
        TEMPLATE
        .replace("/*INJECT_DATA*/[]", data_json)
        .replace("/*GENERATED_AT*/",  generated_at)
    )

    out_path.write_text(html, encoding="utf-8")
    size_kb = out_path.stat().st_size / 1024
    print(f"Generado: {out_path}  ({len(records)} registros, {size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
