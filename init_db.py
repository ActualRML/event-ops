"""CLI: rebuild the database from scratch.

    python init_db.py [--force] [--no-seed]

Refuses to run over an existing database. --force is the old unconditional
behaviour, kept for a rebuild that is meant to throw the current one away.
--no-seed builds the schema and nothing else, for starting genuinely empty."""

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
SEED_FILES = BASE_DIR / "db" / "seed_files"

# The one seeded attachment, and the row that has to agree with it.
#
# Attachments are the payload of the reply feature — a vendor's quote is
# almost always a PDF and the body is often just "terlampir penawaran kami" —
# so a demo where nothing opens is showing the shell. seed.sql cannot do this
# itself: the bytes live on the filesystem, and SQL cannot copy a file.
#
# A committed placeholder copied into place, never a generated one. No PDF
# library is a dependency here and adding one for a fixture would be the
# tail wagging the dog.
#
# The reply this attachment belongs to is found by its MESSAGE-ID, never by a
# hardcoded row id. inbox.id depends on the order of the INSERTs in seed.sql,
# so seeding one more reply above this one would shift it — and the failure is
# the worst kind: the file and the row stop agreeing, the download 404s, and
# nothing on the page explains why. message_id is UNIQUE, so the lookup cannot
# quietly match the wrong row either.
#
# stored_name is then derived from the id that lookup returns, in the same
# {inbox_id}-{position} shape replies.py writes, so a seeded attachment is
# indistinguishable from a fetched one and the download route needs no special
# case.
SEED_LAMPIRAN = {
    "sumber": SEED_FILES / "penawaran-contoh.pdf",
    # Must match the tier-1 reply seeded in db/seed.sql.
    "message_id": "<20260715.9f2a41@mail.gemasuara.co.id>",
    "filename": "Penawaran Sound System - PT Gema Suara Perkasa.pdf",
    "content_type": "application/pdf",
}


def salin_lampiran(conn) -> None:
    """Copy the seeded attachment into place and record it.

    Runs after seed.sql, because the inbox row it hangs off has to exist
    first. Both failure modes warn rather than raise: a database with one
    download missing is still a usable demo, and refusing to build at all over
    a fixture would be worse. A silent skip would not be — that is what the
    warnings are for.
    """
    sumber = SEED_LAMPIRAN["sumber"]
    if not sumber.is_file():
        print(f"  warning: {sumber} is missing, seeded reply will have no attachment",
              file=sys.stderr)
        return

    baris = conn.execute(
        "SELECT id FROM inbox WHERE message_id = ?",
        (SEED_LAMPIRAN["message_id"],),
    ).fetchone()
    if baris is None:
        print(f"  warning: no seeded reply with message_id "
              f"{SEED_LAMPIRAN['message_id']}, attachment skipped", file=sys.stderr)
        return

    inbox_id = baris["id"]
    # Position 1: this reply has exactly one attachment. A second would be
    # 2, matching what replies.simpan_lampiran does with enumerate().
    stored_name = f"{inbox_id}-1{sumber.suffix}"

    tujuan_dir = Path(config.ATTACHMENT_DIR)
    tujuan_dir.mkdir(parents=True, exist_ok=True)
    tujuan = tujuan_dir / stored_name
    isi = sumber.read_bytes()
    tujuan.write_bytes(isi)

    conn.execute(
        """INSERT INTO inbox_attachment
                  (inbox_id, filename, content_type, size_bytes, stored_name)
           VALUES (?, ?, ?, ?, ?)""",
        (inbox_id, SEED_LAMPIRAN["filename"], SEED_LAMPIRAN["content_type"],
         len(isi), stored_name),
    )
    print(f"copied   {sumber.name} -> {tujuan} ({len(isi)} bytes)")

# Every table in schema.sql, in dependency order. A table missing here is
# still created — it just goes uncounted in the summary, which is how rundown
# and rundown_item slipped past unnoticed.
TABLES = ["categories", "vendors", "vendor_categories", "items", "events",
          "requests", "outbox", "spk", "rundown", "rundown_item",
          "sponsors", "sponsor_item", "inbox", "inbox_attachment",
          "inbox_check"]


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

    # --no-seed builds the schema and stops: no vendors, no catalog, no
    # batches, every page on its own empty state. The demo default is the
    # opposite — seeded, so nothing looks broken on first load — so this is
    # the flag you reach for when you want to walk the flow from nothing and
    # see what a new install actually feels like.
    #
    # It also skips salin_lampiran: that copies the placeholder PDF into place
    # for an inbox row seed.sql creates, and with no seed there is no row to
    # hang it off.
    tanpa_seed = "--no-seed" in argv

    with closing(db.get_conn()) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        if not tanpa_seed:
            conn.executescript(SEED_PATH.read_text(encoding="utf-8"))
            # After the seed: this hangs off an inbox row seed.sql creates.
            salin_lampiran(conn)
        conn.commit()

        print(f"created  {db_path}" + ("  (schema only, no seed)" if tanpa_seed else ""))
        for table in TABLES:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:<18} {count:>3}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
