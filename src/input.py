from src.logger import logger
from src.query_workflow import run_queries


def input_worker(config, query_file):
    """Run one CSV query batch without an interactive menu."""
    database_path, csv_path, processed, saved = run_queries(config, query_file)
    logger.info(
        "Run finished: %s queries processed, %s rows saved. SQLite: %s. CSV: %s",
        processed,
        saved,
        database_path,
        csv_path,
    )