"""Simple CSV-driven Google Maps query batch workflow."""

from __future__ import annotations

import csv
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from src.logger import logger

RESULT_COLUMNS = (
    "NAME",
    "LONGITUDE",
    "LATITUDE",
    "ADDRESS",
    "RATING",
    "RATING_COUNT",
    "GOOGLE_TAGS",
    "GOOGLE_URL",
    "SOURCE_QUERY",
    "SCRAPED_AT",
)


def load_queries(path: str | Path) -> list[str]:
    """Load non-empty query values from a CSV with a required query column."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Query CSV not found: {path}")

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "query" not in reader.fieldnames:
            raise ValueError(f'Query CSV must contain a "query" column: {path}')
        return [row["query"].strip() for row in reader if row.get("query", "").strip()]


def create_run_name(csv_filename: str, started_at: str | None = None) -> str:
    """Return YYYYMMDD_HHMMSS_sanitized_csv_stem."""
    timestamp = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S") if started_at else datetime.now()
    stem = Path(csv_filename).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_") or "queries"
    return f"{timestamp:%Y%m%d_%H%M%S}_{stem}"


def quote_identifier(identifier: str) -> str:
    """Validate a SQLite identifier and quote it."""
    if not re.fullmatch(r"[A-Za-z0-9_]+", identifier):
        raise ValueError(f"Invalid SQLite identifier: {identifier}")
    return f'"{identifier}"'


def create_result_table(database_path: str | Path, table_name: str) -> None:
    columns = ", ".join(f'{quote_identifier(column)} TEXT' for column in RESULT_COLUMNS)
    with sqlite3.connect(database_path) as connection:
        connection.execute(f"CREATE TABLE IF NOT EXISTS {quote_identifier(table_name)} ({columns})")
        connection.commit()


def insert_results(database_path: str | Path, table_name: str, rows: Iterable[tuple]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    placeholders = ", ".join("?" for _ in RESULT_COLUMNS)
    query = (
        f"INSERT INTO {quote_identifier(table_name)} "
        f"({', '.join(quote_identifier(column) for column in RESULT_COLUMNS)}) "
        f"VALUES ({placeholders})"
    )
    with sqlite3.connect(database_path) as connection:
        connection.executemany(query, rows)
        connection.commit()
    return len(rows)


def export_table_to_csv(database_path: str | Path, table_name: str, output_folder: str | Path) -> Path:
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    csv_path = output_folder / f"{table_name}.csv"
    with sqlite3.connect(database_path) as connection, csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        cursor = connection.execute(f"SELECT * FROM {quote_identifier(table_name)}")
        writer.writerow([column[0] for column in cursor.description])
        writer.writerows(cursor.fetchall())
    return csv_path


def _result_row(result: tuple, query: str, scraped_at: str) -> tuple:
    # process_target returns location hierarchy fields for the legacy workflow.
    return (*result[:8], query, scraped_at)


def run_queries(config: dict, query_file: str | Path) -> tuple[Path, Path, int, int]:
    """Run all CSV queries and always export the partial table on exit."""
    import asyncio
    import time

    from src.browser import get_driver
    from src.proxy import aiohttp_proxy
    from src.scraper import main as scrape_targets
    from src.scraper import parent_query
    from src.utilities import create_search_link

    query_file = Path(query_file)
    queries = load_queries(query_file)
    database_path = Path(config.get("Database_file", "output/gmaps_scraper.sqlite"))
    output_folder = Path(config.get("Output_folder", "output"))
    database_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    table_name = create_run_name(query_file.name, started_at)
    create_result_table(database_path, table_name)

    driver = None
    processed = 0
    saved = 0
    try:
        driver = get_driver(config)
        proxy_detail = aiohttp_proxy(config)

        for index, query in enumerate(queries):
            scrape_started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            search_url = create_search_link(query)
            targets, proxy_check = asyncio.run(
                parent_query(index, driver, config.get("Log_level") or "info", queries, "", "", "", "", search_url, lambda: None, time.time())
            )
            if targets in ("continue", "break") or not targets:
                processed += 1
                if targets == "break":
                    break
                continue
            results = asyncio.run(
                scrape_targets(targets, proxy_detail, "", "", "", "", query, 0, scrape_started)
            )
            rows = [_result_row(result, query, scrape_started) for result in results]
            saved += insert_results(database_path, table_name, rows)
            processed += 1
            logger.info("Query %s/%s completed: %s rows", processed, len(queries), len(rows))
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        csv_path = export_table_to_csv(database_path, table_name, output_folder)
        logger.info("Exported %s rows from %s to %s", saved, table_name, csv_path)

    return database_path, csv_path, processed, saved
