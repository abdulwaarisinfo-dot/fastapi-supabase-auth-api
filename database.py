"""PostgreSQL connection handling.

Loads the database connection string from the environment and exposes a
helper to obtain psycopg connections, along with a startup routine that
waits for PostgreSQL to become available before the application starts
serving requests.
"""

import os
import time
from contextlib import contextmanager
from typing import Generator

import psycopg
from dotenv import load_dotenv
from psycopg import Connection
from psycopg.rows import dict_row

load_dotenv()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://postgres:password@postgres:5432/tasks_db"
)

MAX_STARTUP_RETRIES = 30
RETRY_DELAY_SECONDS = 1.0


def get_connection() -> Connection:
    """Return a new psycopg connection using dict-style rows."""
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


@contextmanager
def get_db() -> Generator[Connection, None, None]:
    """Yield a database connection, committing on success and rolling back on error."""
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def wait_for_database() -> None:
    """Block until PostgreSQL accepts connections or retries are exhausted."""
    last_error: Exception | None = None
    for attempt in range(1, MAX_STARTUP_RETRIES + 1):
        try:
            connection = psycopg.connect(DATABASE_URL)
            connection.close()
            return
        except psycopg.OperationalError as error:
            last_error = error
            time.sleep(RETRY_DELAY_SECONDS)
    raise ConnectionError(
        f"Could not connect to PostgreSQL after {MAX_STARTUP_RETRIES} attempts"
    ) from last_error


def run_init_script(init_sql_path: str = "init.sql") -> None:
    """Execute the init.sql script to create tables and seed initial data."""
    with open(init_sql_path, "r", encoding="utf-8") as sql_file:
        init_sql = sql_file.read()

    with get_db() as connection:
        connection.execute(init_sql)