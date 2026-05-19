"""
Initialize the SQLite database from schema.sql.
Run once during setup: python db/initializedb.py
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = os.getenv("DATABASE_PATH", "db/hackathon.db")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(db_path: str | Path = DB_PATH) -> None:
    """Create tables from schema.sql if they don't exist."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    with open(SCHEMA_PATH, "r") as f:
        schema = f.read()

    cursor.executescript(schema)

    # v2: Add USD columns to deals table if they don't exist
    existing_cols = {
        row[1] for row in cursor.execute("PRAGMA table_info(deals)").fetchall()
    }
    if "amount_usd" not in existing_cols:
        cursor.execute("ALTER TABLE deals ADD COLUMN amount_usd REAL")
    if "usd_to_algo_rate" not in existing_cols:
        cursor.execute("ALTER TABLE deals ADD COLUMN usd_to_algo_rate REAL")

    conn.commit()
    conn.close()

    print(f"Database initialized at: {db_path.resolve()}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize AgentTrade SQLite database")
    parser.add_argument(
        "--db",
        default=DB_PATH,
        help=f"Path to database file (default: {DB_PATH})",
    )
    args = parser.parse_args()
    init_db(args.db)
