#!/usr/bin/env python3
"""
URSEC Data Downloader
Descarga comunicaciones de URSEC y las organiza por fecha de publicación.
Ejecutar diariamente. Omite archivos ya descargados.
"""

import csv
import logging
import math
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, unquote, urljoin

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
SOURCES = [
    {
        "url":   "https://www.gub.uy/unidad-reguladora-servicios-comunicaciones/datos-y-estadisticas/datos",
        "label": "datos",
    },
    {
        "url":   "https://www.gub.uy/unidad-reguladora-servicios-comunicaciones/tematica/servicios-telecomunicaciones",
        "label": "telecom",
    },
    {
        # Two-level: listing page → sub-pages → Download links
        "url":   "https://www.gub.uy/unidad-reguladora-servicios-comunicaciones/institucion/unidad-reguladora-servicios-comunicaciones",
        "label": "institucion",
        "mode":  "indexed",
    },
]
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-UY,es;q=0.9,en;q=0.8",
}

BASE_URL = "https://www.gub.uy"

DB_DIR          = Path("db")
DOWNLOADS_DIR   = Path("downloads")
LOGS_DIR        = Path("logs")
RUNS_DIR        = DB_DIR / "runs"
CUMULATIVE_CSV  = DB_DIR / "files.csv"
VISITED_PAGES   = DB_DIR / "visited_pages.txt"

CSV_FIELDS = [
    "url", "filename", "title", "date_published", "category",
    "size_str", "size_bytes", "page_url", "first_seen", "local_path", "source",
]

TODAY = date.today().isoformat()

# ---------------------------------------------------------------------------
# Helpers: setup
# ---------------------------------------------------------------------------

def setup_dirs():
    for d in (DB_DIR, DOWNLOADS_DIR, LOGS_DIR, RUNS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def setup_logging():
    log_file = LOGS_DIR / f"{TODAY}.log"
    fmt = "%(asctime)s %(levelname)-8s %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("ursec"), log_file


# ---------------------------------------------------------------------------
# Helpers: CSV / DB
# ---------------------------------------------------------------------------

def load_cumulative_db() -> dict:
    """Devuelve {url: row_dict} con todos los archivos conocidos."""
    db = {}
    if CUMULATIVE_CSV.exists():
        with open(CUMULATIVE_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row.setdefault("source", "datos")  # retrocompat
                db[row["url"]] = row
    return db


def save_cumulative_db(db: dict):
    with open(CUMULATIVE_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(db.values())


def save_run_csv(downloaded: list, skipped: list, failed: list):
    run_csv = RUNS_DIR / f"{TODAY}.csv"
    fields = ["status"] + CSV_FIELDS
    rows = (
        [{"status": "downloaded", **r} for r in downloaded]
        + [{"status": "skipped",    **r} for r in skipped]
        + [{"status": "failed",     **r} for r in failed]
    )
    with open(run_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return run_csv


def load_visited_pages() -> set:
    if VISITED_PAGES.exists():
        return set(VISITED_PAGES.read_text(encoding="utf-8").splitlines())
    return set()


def save_visited_pages(visited: set):
    VISITED_PAGES.write_text("\n".join(sorted(visited)), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers: parsing
# ---------------------------------------------------------------------------

def parse_date(text: str) -> str:
    """Convierte 'DD/MM/YYYY' (o 'DD/MM/YYYY - Categoría') en 'YYYY-MM-DD'."""
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return TODAY  # fallback


def parse_size_bytes(size_str: str) -> int:
    """'43.06 KB' -> int bytes."""
    m = re.match(r"([\d.]+)\s*(B|KB|MB|GB)", size_str.strip(), re.I)
    if not m:
        return 0
    val  = float(m.group(1))
    unit = m.group(2).upper()
    return int(val * {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}[unit])


def extract_size_from_aria(aria: str) -> tuple[str, str]:
    """
    Parsea aria-label: 'Descargar: Título (.ext 43.06 KB)'
    Devuelve (título_descarga, '43.06 KB').
    """
    m = re.match(r"Descargar:\s+(.+?)\s+\(\.[^)]+\s+([\d.]+\s+[KMG]?B)\)", aria)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # Fallback: buscar el tamaño solo
    m2 = re.search(r"([\d.]+\s+[KMG]?B)\)", aria)
    size = m2.group(1).strip() if m2 else ""
    # Título: todo lo que hay tras "Descargar: " y antes del paréntesis final
    m3 = re.match(r"Descargar:\s+(.+?)\s+\(", aria)
    title = m3.group(1).strip() if m3 else ""
    return title, size


def parse_page(soup: BeautifulSoup, page_url: str, source_label: str = "") -> list[dict]:
    """Extrae todos los items de descarga de una página ya parseada.

    Soporta dos estructuras de categoría:
    - <span class="Box-info">DD/MM/YYYY - <strong>Categoría</strong></span>  (página /datos)
    - <span class="Box-info">DD/MM/YYYY</span>
      <span class="Box-info u-h5 ...">Categoría</span>                       (página /telecom)
    """
    items = []

    for li in soup.find_all("li", class_="Media"):
        body = li.find("div", class_="Media-body")
        if not body:
            continue

        # ── Fecha y categoría ──────────────────────────────────────────────
        date_published = TODAY
        category = ""
        for box in body.find_all("span", class_="Box-info"):
            box_text = box.get_text(strip=True)
            if re.search(r"\d{2}/\d{2}/\d{4}", box_text):
                date_published = parse_date(box_text)
                strong = box.find("strong")
                if strong:
                    category = strong.get_text(strip=True)
            elif box_text and not category:
                category = box_text

        # ── Título del item ────────────────────────────────────────────────
        h3 = body.find("h3")
        item_title = h3.get_text(strip=True) if h3 else ""

        # ── Links de descarga (puede haber varios por item) ────────────────
        for dl in body.find_all("a", class_="Download"):
            href = dl.get("href", "").strip()
            if not href:
                continue

            aria = dl.get("aria-label", "")
            dl_title, size_str = extract_size_from_aria(aria)

            if not dl_title:
                dt_div = dl.find("div", class_="Download-title")
                if dt_div:
                    dt_text = dt_div.get_text(strip=True)
                    dl_title = re.sub(r"\s+\(\.[^)]+\)$", "", dt_text).strip()
            if not dl_title:
                dl_title = item_title

            filename = unquote(urlparse(href).path.split("/")[-1])

            items.append({
                "url":            href,
                "filename":       filename,
                "title":          dl_title or item_title,
                "date_published": date_published,
                "category":       category,
                "size_str":       size_str,
                "size_bytes":     parse_size_bytes(size_str),
                "page_url":       page_url,
                "first_seen":     TODAY,
                "local_path":     "",
                "source":         source_label,
            })

    return items


def parse_subpage(
    soup: BeautifulSoup,
    page_url: str,
    source_label: str,
    fallback_title: str,
    fallback_date: str,
    fallback_category: str,
) -> list[dict]:
    """
    Extrae archivos de sub-páginas del tipo 'institucion'.
    Estructura: <ul class="Page-downloads"><li><a class="Download" aria-label="..."></li></ul>
    Los links usan el mismo aria-label que las fuentes planas, pero no están
    dentro de <li class="Media">, por eso parse_page no los encuentra.
    """
    items = []

    for dl in soup.find_all("a", class_="Download"):
        href = dl.get("href", "").strip()
        if not href:
            continue
        href = urljoin(BASE_URL, href)

        aria = dl.get("aria-label", "")
        dl_title, size_str = extract_size_from_aria(aria)

        if not dl_title:
            dt_div = dl.find("div", class_="Download-title")
            if dt_div:
                dl_title = re.sub(r"\s+\(\.[^)]+\)$", "", dt_div.get_text(strip=True)).strip()
        if not dl_title:
            dl_title = fallback_title

        filename = unquote(urlparse(href).path.split("/")[-1])
        if not filename:
            continue

        items.append({
            "url":            href,
            "filename":       filename,
            "title":          dl_title,
            "date_published": fallback_date,
            "category":       fallback_category,
            "size_str":       size_str,
            "size_bytes":     parse_size_bytes(size_str),
            "page_url":       page_url,
            "first_seen":     TODAY,
            "local_path":     "",
            "source":         source_label,
        })

    return items


def parse_listing_page(soup: BeautifulSoup) -> list[dict]:
    """
    Para fuentes de tipo 'indexed': extrae los sub-enlaces de cada <li class="Media">.
    Devuelve lista de {url, title, date_published, category}.
    """
    entries = []
    for li in soup.find_all("li", class_="Media"):
        body = li.find("div", class_="Media-body")
        if not body:
            continue

        h3 = body.find("h3")
        if not h3:
            continue
        a = h3.find("a", href=True)
        if not a:
            continue

        href = urljoin(BASE_URL, a["href"])
        title = a.get_text(strip=True)

        date_published = TODAY
        category = ""
        for box in body.find_all(["span", "div"], class_="Box-info"):
            box_text = box.get_text(strip=True)
            if re.search(r"\d{2}/\d{2}/\d{4}", box_text):
                date_published = parse_date(box_text)
            elif box_text and not category and not re.search(r"\d{2}/\d{2}/\d{4}", box_text):
                category = box_text

        entries.append({
            "url":            href,
            "title":          title,
            "date_published": date_published,
            "category":       category,
        })
    return entries


def get_pagination(soup: BeautifulSoup) -> tuple[int, int, int]:
    """
    Devuelve (total_results, per_page, total_pages) leyendo
    'Mostrando X - Y de Z resultados'.
    """
    div = soup.find("div", class_="Pagination-text")
    if div:
        m = re.search(
            r"Mostrando\s+(\d+)\s*-\s*(\d+)\s+de\s+(\d+)\s+resultados",
            div.get_text(),
        )
        if m:
            start    = int(m.group(1))
            end      = int(m.group(2))
            total    = int(m.group(3))
            per_page = end - start + 1
            pages    = math.ceil(total / per_page)
            return total, per_page, pages
    return 0, 10, 1


# ---------------------------------------------------------------------------
# Scraping strategies
# ---------------------------------------------------------------------------

def scrape_flat_source(source: dict, session: requests.Session, log) -> list[dict]:
    """Fuente directa: cada página de listado contiene <a class='Download'>."""
    base_url  = source["url"]
    src_label = source["label"]
    all_items = []

    try:
        resp = session.get(base_url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        log.error(f"  Error al cargar {base_url}: {exc}")
        return all_items

    total_results, per_page, total_pages = get_pagination(soup)
    log.info(
        f"  Paginador: {total_results} resultados | "
        f"{per_page} por página | {total_pages} páginas"
    )

    items_p0 = parse_page(soup, base_url, src_label)
    all_items.extend(items_p0)
    log.info(f"  Página 1/{total_pages}: {len(items_p0)} archivos")

    with tqdm(total=total_pages, desc=f"  {src_label}", unit="pág") as pbar:
        pbar.update(1)
        for page_num in range(1, total_pages):
            page_url = f"{base_url}?page={page_num}"
            try:
                r = session.get(page_url, timeout=30)
                r.raise_for_status()
                s = BeautifulSoup(r.text, "html.parser")
                items_pn = parse_page(s, page_url, src_label)
                all_items.extend(items_pn)
                log.info(f"  Página {page_num+1}/{total_pages}: {len(items_pn)} archivos")
            except Exception as exc:
                log.error(f"  Error en página {page_num+1}: {exc}")
            pbar.update(1)

    return all_items


def scrape_indexed_source(
    source: dict,
    session: requests.Session,
    visited: set,
    log,
) -> list[dict]:
    """
    Fuente de dos niveles: el listado enlaza a sub-páginas que contienen
    archivos en <div class="descargas">. Solo visita sub-páginas nuevas.
    """
    base_url  = source["url"]
    src_label = source["label"]
    all_items = []

    # ── Paso 1: recolectar sub-URLs del listado paginado ──────────────────
    try:
        resp = session.get(base_url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        log.error(f"  Error al cargar {base_url}: {exc}")
        return all_items

    total_results, per_page, total_pages = get_pagination(soup)
    log.info(
        f"  Paginador: {total_results} resultados | "
        f"{per_page} por página | {total_pages} páginas"
    )

    sub_entries: list[dict] = parse_listing_page(soup)

    with tqdm(total=total_pages, desc=f"  {src_label} listado", unit="pág") as pbar:
        pbar.update(1)
        for page_num in range(1, total_pages):
            page_url = f"{base_url}?page={page_num}"
            try:
                r = session.get(page_url, timeout=30)
                r.raise_for_status()
                s = BeautifulSoup(r.text, "html.parser")
                sub_entries.extend(parse_listing_page(s))
            except Exception as exc:
                log.error(f"  Error en página {page_num+1}: {exc}")
            pbar.update(1)

    # ── Paso 2: visitar solo sub-páginas nuevas ────────────────────────────
    new_entries = [e for e in sub_entries if e["url"] not in visited]
    log.info(
        f"  Sub-páginas: {len(sub_entries)} encontradas | "
        f"{len(new_entries)} nuevas | {len(sub_entries)-len(new_entries)} ya visitadas"
    )

    found_files = 0
    with tqdm(total=len(new_entries), desc=f"  {src_label} sub-páginas", unit="pág") as pbar:
        for entry in new_entries:
            try:
                r = session.get(entry["url"], timeout=30)
                r.raise_for_status()
                s = BeautifulSoup(r.text, "html.parser")
                items = parse_subpage(
                    s,
                    entry["url"],
                    src_label,
                    fallback_title=entry["title"],
                    fallback_date=entry["date_published"],
                    fallback_category=entry["category"],
                )
                all_items.extend(items)
                found_files += len(items)
            except Exception as exc:
                log.error(f"  Error en sub-página {entry['url']}: {exc}")
            finally:
                visited.add(entry["url"])
            pbar.update(1)

    log.info(f"  Archivos encontrados en sub-páginas: {found_files}")
    return all_items


# ---------------------------------------------------------------------------
# Descarga de archivo individual
# ---------------------------------------------------------------------------

def download_file(url: str, dest: Path, session: requests.Session) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        dest = dest.parent / f"{stem}_{TODAY}{suffix}"

    resp = session.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))

    with open(dest, "wb") as f:
        with tqdm(
            total=total or None,
            unit="B", unit_scale=True,
            desc=dest.name[:40],
            leave=False,
        ) as pbar:
            for chunk in resp.iter_content(chunk_size=16_384):
                f.write(chunk)
                pbar.update(len(chunk))

    return dest


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    setup_dirs()
    log, log_file = setup_logging()

    log.info("=" * 60)
    log.info("URSEC Downloader iniciado")
    log.info(f"Fecha de ejecución: {TODAY}")
    log.info("=" * 60)

    session = requests.Session()
    session.headers.update(HEADERS)

    db      = load_cumulative_db()
    visited = load_visited_pages()
    log.info(f"DB cargada: {len(db)} archivos conocidos | {len(visited)} sub-páginas visitadas")

    all_items: list[dict] = []

    for source in SOURCES:
        log.info(f"Fuente [{source['label']}]: {source['url']}")
        if source.get("mode") == "indexed":
            items = scrape_indexed_source(source, session, visited, log)
        else:
            items = scrape_flat_source(source, session, log)
        all_items.extend(items)

    log.info(f"Total archivos encontrados en todas las fuentes: {len(all_items)}")

    new_items     = [i for i in all_items if i["url"] not in db]
    skipped_items = [db[i["url"]] for i in all_items if i["url"] in db]
    log.info(f"Nuevos: {len(new_items)} | Ya descargados: {len(skipped_items)}")

    downloaded: list[dict] = []
    failed:     list[dict] = []

    with tqdm(total=len(new_items), desc="Descargando", unit="archivo") as pbar:
        for item in new_items:
            pub_date = item["date_published"] or TODAY
            dest = DOWNLOADS_DIR / pub_date / item["filename"]

            try:
                dest = download_file(item["url"], dest, session)
                item["local_path"] = str(dest)
                db[item["url"]] = item
                downloaded.append(item)
                log.info(f"  OK  {item['filename']}  →  {dest}")
            except Exception as exc:
                log.error(f"  FAIL {item['url']}: {exc}")
                failed.append(item)

            pbar.update(1)

    save_cumulative_db(db)
    save_visited_pages(visited)
    run_csv = save_run_csv(downloaded, skipped_items, failed)
    log.info(f"DB acumulativa guardada: {CUMULATIVE_CSV}")
    log.info(f"CSV de esta ejecución:   {run_csv}")

    summary = {
        "run_date":        TODAY,
        "total_found":     len(all_items),
        "new_downloaded":  len(downloaded),
        "skipped":         len(skipped_items),
        "failed":          len(failed),
        "total_in_db":     len(db),
        "log_file":        str(log_file),
    }

    log.info("=" * 60)
    log.info("RESUMEN")
    for k, v in summary.items():
        log.info(f"  {k:20s}: {v}")
    log.info("=" * 60)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
