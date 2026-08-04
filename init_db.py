"""CLI: rebuild the database from scratch. python init_db.py"""

import sys
from contextlib import closing
from pathlib import Path

import config
import db

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"
SEED_PATH = BASE_DIR / "db" / "seed.sql"

TABLES = ["categories", "vendors", "vendor_categories", "requests", "outbox"]


def main() -> int:
    db_path = Path(config.DB_PATH)

    # WAL keeps sidecar files; a stale -wal would replay old pages into the
    # fresh database, so they go too.
    for path in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        if path.exists():
            path.unlink()
            print(f"deleted  {path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(db.get_conn()) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.executescript(SEED_PATH.read_text(encoding="utf-8"))
        conn.commit()

        print(f"created  {db_path}")
        for table in TABLES:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:<18} {count:>3}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
