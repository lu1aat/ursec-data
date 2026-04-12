#!/usr/bin/env python3
"""
URSEC Data Downloader
Descarga comunicaciones de URSEC y las organiza por fecha de publicación.
Ejecutar diariamente. Omite archivos ya descargados.
"""

import csv
import json
import logging
import math
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import paho.mqtt.publish as mqtt_publish

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

MQTT_HOST  = "test.mosquitto.org"
MQTT_PORT  = 1883
MQTT_TOPIC = "udata"

DB_DIR        = Path("db")
DOWNLOADS_DIR = Path("downloads")
LOGS_DIR      = Path("logs")
RUNS_DIR      = DB_DIR / "runs"
CUMULATIVE_CSV = DB_DIR / "files.csv"

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
                # Este span tiene la fecha
                date_published = parse_date(box_text)
                strong = box.find("strong")
                if strong:
                    category = strong.get_text(strip=True)
            elif box_text and not category:
                # Span de solo categoría (patrón telecom: Box-info u-h5)
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

            # Si aria no tenía título, usar el del item
            if not dl_title:
                dt_div = dl.find("div", class_="Download-title")
                if dt_div:
                    dt_text = dt_div.get_text(strip=True)
                    # quitar el "(.ext SIZE)" del final
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
# Descarga de archivo individual
# ---------------------------------------------------------------------------

def download_file(url: str, dest: Path, session: requests.Session) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Evitar sobreescribir si existe (mismo nombre, distinta ejecución)
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
# MQTT
# ---------------------------------------------------------------------------

def notify_mqtt(payload: dict, log):
    try:
        mqtt_publish.single(
            topic=MQTT_TOPIC,
            payload=json.dumps(payload, ensure_ascii=False),
            hostname=MQTT_HOST,
            port=MQTT_PORT,
            client_id="ursec-downloader",
            keepalive=10,
        )
        log.info(f"MQTT OK → {MQTT_HOST}:{MQTT_PORT} [{MQTT_TOPIC}]")
    except Exception as exc:
        log.warning(f"MQTT falló: {exc}")


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

    # ── Cargar DB existente ────────────────────────────────────────────────
    db = load_cumulative_db()
    log.info(f"DB cargada: {len(db)} archivos conocidos")

    # ── Scraping de todas las fuentes ─────────────────────────────────────
    all_items: list[dict] = []

    for source in SOURCES:
        base_url    = source["url"]
        src_label   = source["label"]
        log.info(f"Fuente [{src_label}]: {base_url}")

        try:
            resp = session.get(base_url, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as exc:
            log.error(f"  Error al cargar {base_url}: {exc}")
            continue

        total_results, per_page, total_pages = get_pagination(soup)
        log.info(
            f"  Paginador: {total_results} resultados | "
            f"{per_page} por página | {total_pages} páginas"
        )

        # página 0 ya descargada
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

    log.info(f"Total archivos encontrados en todas las fuentes: {len(all_items)}")

    # ── Clasificar nuevos vs conocidos ─────────────────────────────────────
    new_items     = [i for i in all_items if i["url"] not in db]
    skipped_items = [db[i["url"]] for i in all_items if i["url"] in db]
    log.info(f"Nuevos: {len(new_items)} | Ya descargados: {len(skipped_items)}")

    # ── Descargar nuevos ───────────────────────────────────────────────────
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

    # ── Persistir ──────────────────────────────────────────────────────────
    save_cumulative_db(db)
    run_csv = save_run_csv(downloaded, skipped_items, failed)
    log.info(f"DB acumulativa guardada: {CUMULATIVE_CSV}")
    log.info(f"CSV de esta ejecución:   {run_csv}")

    # ── Resumen ────────────────────────────────────────────────────────────
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

    # ── Notificación MQTT ──────────────────────────────────────────────────
    notify_mqtt(summary, log)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
