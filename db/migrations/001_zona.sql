-- 001_zona.sql — zone-based pricing for sponsor package lines.
--
-- Two columns, no data movement, no table rebuild.
--
-- Applied by hand. There is no version table yet, so nothing records that
-- this ran; re-running it fails with "duplicate column name: zona" and stops
-- before the second statement. That error is the whole idempotency guard
-- until a version table exists, and it is a safe one — it refuses rather
-- than half-applying.
--
--   python -c "import sqlite3,sys; c=sqlite3.connect('db/rfq.db'); c.executescript(open(sys.argv[1],encoding='utf-8').read()); c.close()" db/migrations/001_zona.sql
--
-- NOT `python -m sqlite3 db/rfq.db ".read ..."`, which is what this line used
-- to say: that module has no .read, and the invocation dies with
-- `OperationalError (SQLITE_ERROR): near ".": syntax error` before running a
-- single statement. The real sqlite3 CLI does support .read, but it is not
-- installed here, so the one-liner above is the working route.
--
-- Take a backup first. init_db.py prints the VACUUM INTO command it wants.
--
-- events.zona is the FACT: where the event happens, in the terms the
-- surcharge is expressed in. `lokasi` stays free text beside it and is not
-- touched — that string is printed into RFQ emails and the SPK document, and
-- constraining it to a list would change what a vendor reads.
--
-- sponsor_item.zona_pct is the REASON: the percentage in force when that line
-- was priced. It is not summed and no total reads it. It exists so a line
-- priced under one zone stays identifiable after its event moves to another.
-- Without it a stale snapshot is indistinguishable from a current one, and
-- the surcharge shows up as an unexplained difference — which reads as a bug.
-- Invariant 15 is unaffected: this records why the money is what it is, it
-- does not license anything to move it.

BEGIN;

-- NOT NULL with a non-NULL default is what SQLite requires of ADD COLUMN, and
-- it is also what backfills: every event that already exists reads back
-- 'jabodetabek' without a separate UPDATE.
ALTER TABLE events ADD COLUMN zona TEXT NOT NULL DEFAULT 'jabodetabek'
    CHECK (zona IN ('jabodetabek', 'luar_jabodetabek', 'luar_jawa'));

-- 0 is the true history, not merely a convenient default: every line that
-- exists today was priced before zones existed, so none of them carried a
-- surcharge.
ALTER TABLE sponsor_item ADD COLUMN zona_pct INTEGER NOT NULL DEFAULT 0;

COMMIT;
