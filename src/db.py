"""Run validated SQL against the IPL database in read-only mode.

Try it from the project root:
    python -m src.db "SELECT season, COUNT(*) AS matches FROM matches GROUP BY season"
"""
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

from src.guardrails import validate_sql

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "ipl.db"
MAX_ROWS = 1000
TIMEOUT_SECONDS = 10


class QueryTimeoutError(RuntimeError):
    """Raised when a query runs longer than TIMEOUT_SECONDS."""


def run_query(sql: str, db_path: Path = DB_PATH) -> tuple[str, pd.DataFrame]:
    """Validate and execute the SQL.

    Returns (final_sql, result_dataframe). Raises UnsafeSQLError if validation
    fails, QueryTimeoutError on timeout, or sqlite3.Error for SQL errors.
    """
    final_sql = validate_sql(sql)

    # mode=ro makes SQLite itself reject any write, even if validation is bypassed.
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        deadline = time.monotonic() + TIMEOUT_SECONDS
        # Returning non-zero from the progress handler aborts the query.
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        try:
            cursor = conn.execute(final_sql)
            rows = cursor.fetchmany(MAX_ROWS)
            columns = [c[0] for c in cursor.description]
        except sqlite3.OperationalError as e:
            if "interrupted" in str(e).lower():
                raise QueryTimeoutError(f"Query exceeded {TIMEOUT_SECONDS}s.") from e
            raise
    finally:
        conn.close()

    return final_sql, pd.DataFrame(rows, columns=columns)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('Usage: python -m src.db "SELECT ..."')
    sql_used, df = run_query(" ".join(sys.argv[1:]))
    print(sql_used)
    print(df.to_string(index=False))
