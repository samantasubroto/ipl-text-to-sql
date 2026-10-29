"""Load the IPL CSV files into a SQLite database (data/ipl.db).

Run from the project root:
    python scripts/load_db.py
"""
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "ipl.db"

TABLES = {
    "matches": DATA_DIR / "matches.csv",
    "deliveries": DATA_DIR / "deliveries.csv",
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_matches_id ON matches(id)",
    "CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(season)",
    "CREATE INDEX IF NOT EXISTS idx_deliveries_match_id ON deliveries(match_id)",
    "CREATE INDEX IF NOT EXISTS idx_deliveries_batsman ON deliveries(batsman)",
    "CREATE INDEX IF NOT EXISTS idx_deliveries_bowler ON deliveries(bowler)",
]


def main() -> None:
    engine = create_engine(f"sqlite:///{DB_PATH}")

    for table, csv_path in TABLES.items():
        df = pd.read_csv(csv_path)
        df.to_sql(table, engine, if_exists="replace", index=False, chunksize=10_000)
        print(f"Loaded {len(df):>7} rows into '{table}'")

    with engine.begin() as conn:
        for stmt in INDEXES:
            conn.execute(text(stmt))
    print(f"Created {len(INDEXES)} indexes")
    print(f"Database ready: {DB_PATH}")


if __name__ == "__main__":
    main()
