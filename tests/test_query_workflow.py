import csv
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.proxy import aiohttp_proxy, proxy_server
from src.query_workflow import (
    create_run_name,
    export_table_to_csv,
    load_queries,
    quote_identifier,
)


class QueryWorkflowTests(unittest.TestCase):
    def test_load_queries_reads_query_column_and_skips_blank_rows(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "places.csv"
            path.write_text(
                "query,notes\ncoffee shops in Bandung,first\n,blank\n restaurants in Jakarta ,second\n",
                encoding="utf-8",
            )
            self.assertEqual(
                load_queries(path), ["coffee shops in Bandung", "restaurants in Jakarta"]
            )

    def test_load_queries_rejects_missing_query_column(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "places.csv"
            path.write_text("search\ncoffee shops\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "query"):
                load_queries(path)

    def test_create_run_name_uses_timestamp_and_sanitizes_csv_stem(self):
        self.assertEqual(
            create_run_name("My queries (Jakarta).csv", "2026-10-05 14:30:22"),
            "20261005_143022_my_queries_jakarta",
        )

    def test_export_table_to_csv_exports_current_partial_results(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "runs.sqlite"
            output = root / "output"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE run_1 (NAME TEXT, SOURCE_QUERY TEXT)")
                connection.execute(
                    "INSERT INTO run_1 VALUES (?, ?)", ("Cafe A", "coffee shops")
                )
                connection.commit()

            csv_path = export_table_to_csv(database, "run_1", output)

            self.assertEqual(csv_path, output / "run_1.csv")
            with csv_path.open(newline="", encoding="utf-8") as handle:
                self.assertEqual(
                    list(csv.DictReader(handle)),
                    [{"NAME": "Cafe A", "SOURCE_QUERY": "coffee shops"}],
                )

    def test_quote_identifier_rejects_sql_injection(self):
        with self.assertRaises(ValueError):
            quote_identifier("bad; DROP TABLE users")

    def test_authenticated_proxy_urls_escape_credentials(self):
        config = {
            "Proxy": {
                "Enabled": True,
                "Scheme": "http",
                "Host": "proxy.example.com",
                "Port": 8080,
                "User": "user@example.com",
                "Password": "p@ss:word",
            }
        }
        self.assertEqual(proxy_server(config), "http://proxy.example.com:8080")
        self.assertEqual(
            aiohttp_proxy(config),
            "http://user%40example.com:p%40ss%3Aword@proxy.example.com:8080",
        )

    def test_disabled_proxy_returns_none(self):
        self.assertIsNone(aiohttp_proxy({"Proxy": {"Enabled": False}}))


if __name__ == "__main__":
    unittest.main()
