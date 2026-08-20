"""CLI: rebuild the database from scratch. python init_db.py [--force]

Refuses to run over an existing database. --force is the old unconditional
behaviour, kept for a rebuild that is meant to throw the current one away."""

import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

import config
import db

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"
SEED_PATH = BASE_DIR / "db" / "seed.sql"

# Every table in schema.sql, in dependency order. A table missing here is
# still created — it just goes uncounted in the summary, which is how rundown
# and rundown_item slipped past unnoticed.
TABLES = ["categories", "vendors", "vendor_categories", "items", "events",
          "requests", "outbox", "spk", "rundown", "rundown_item",
          "sponsors", "sponsor_item"]


def hitung_baris(db_path: Path):
    """[(table, count)] for the tables the file actually has, or None when it
    cannot be read at all.

    Opened read-only, because this runs against a database the caller has not
    yet agreed to lose: a plain connection would checkpoint the WAL back into
    the main file on close. A table missing from an older database is skipped
    rather than raised on — the job here is to report what is there, not to
    validate the schema against today's schema.sql.
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None

    hasil = []
    with closing(conn):
        for table in TABLES:
            try:
                jumlah = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                continue
            hasil.append((table, jumlah))
    return hasil


def tolak(db_path: Path) -> int:
    """The refusal: what is in the file, and how to keep it. Returns the exit
    code so the caller reads as one line."""
    cadangan = db_path.with_name(
        f"{db_path.stem}-backup-{datetime.now():%Y%m%d-%H%M%S}{db_path.suffix}"
    )

    print(f"refusing: {db_path} already exists, and rebuilding deletes it.",
          file=sys.stderr)

    baris = hitung_baris(db_path)
    if baris is None:
        print("  it could not be opened to count rows — back it up anyway.",
              file=sys.stderr)
    else:
        print("\n  rows that would be destroyed:", file=sys.stderr)
        for table, jumlah in baris:
            print(f"    {table:<18} {jumlah:>4}", file=sys.stderr)
        print(f"    {'total':<18} {sum(j for _, j in baris):>4}", file=sys.stderr)

    # VACUUM INTO, not a file copy: it writes one consistent database including
    # pages still sitting in the -wal, which copying rfq.db alone would miss.
    #
    # The python one-liner is offered FIRST because it is the one that works
    # everywhere. The sqlite3 CLI is not installed on every machine this runs
    # on, and the fallback printed here used to be `python -m sqlite3`, which
    # is a dead end: that module has no dot commands to drive, so the line sent
    # people to something that could not do the job.
    # as_posix() on both paths, and it is load-bearing rather than cosmetic:
    # on Windows these render as db\rfq.db, and a backslash inside the Python
    # string literal below is an escape — 'file:db\rfq.db' carries a carriage
    # return, not an r. Forward slashes work for SQLite on every platform.
    sumber = db_path.as_posix()
    tujuan = cadangan.as_posix()

    print("\n  back it up first:", file=sys.stderr)
    print(
        f"    python -c \"import sqlite3; c=sqlite3.connect('file:{sumber}?mode=ro',"
        f" uri=True); c.execute(\\\"VACUUM INTO '{tujuan}'\\\"); c.close()\"",
        file=sys.stderr,
    )
    print(f"    or, with the sqlite3 CLI:  sqlite3 {sumber} \"VACUUM INTO '{tujuan}'\"",
          file=sys.stderr)
    print("\n  then re-run, or pass --force to delete it now.", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    db_path = Path(config.DB_PATH)

    # The whole guard. Everything below this line is what the script always
    # did, and --force reaches it unchanged.
    if db_path.exists() and "--force" not in argv:
        return tolak(db_path)

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
    sys.exit(main(sys.argv[1:]))
