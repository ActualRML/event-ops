-- 002_kode.sql — the RFQ batch reference code.
--
-- One column and one index, no data movement, no table rebuild.
--
-- Applied by hand. There is no version table, so nothing records that this
-- ran; re-running it fails with "duplicate column name: kode" and stops before
-- the index. That error is the whole idempotency guard, and it is a safe one —
-- it refuses rather than half-applying.
--
--   python -c "import sqlite3,sys; c=sqlite3.connect('db/rfq.db'); c.executescript(open(sys.argv[1],encoding='utf-8').read()); c.close()" db/migrations/002_kode.sql
--
-- NOT `python -m sqlite3 db/rfq.db ".read ..."`: that module has no .read and
-- dies with `OperationalError (SQLITE_ERROR): near ".": syntax error` before
-- running a single statement. The real sqlite3 CLI does support .read, but it
-- is not installed here.
--
-- Take a backup first. init_db.py prints the VACUUM INTO command it wants.
--
-- WHAT THIS IS FOR. A vendor's reply has to be traceable back to the batch it
-- answers. The code is printed into the outgoing subject as [RFQ-3F2A], and a
-- subject survives a vendor pressing Reply — so it comes back to us on the
-- answer without the vendor doing anything. Nothing can be matched
-- retroactively: only mail sent after this lands carries a marker at all.
--
-- WHY THE COLUMN IS NULLABLE. NULL is the true history, exactly as
-- sponsor_item.zona_pct DEFAULT 0 was: every batch that already exists went
-- out before codes existed, and no marker was ever in those subjects. A
-- backfill would be a lie — it would claim a code that no vendor ever saw.
-- Rendering skips the marker when kode is NULL, so old batches keep working
-- and simply cannot be matched by subject.
--
-- WHY A UNIQUE INDEX RATHER THAN A COLUMN CONSTRAINT. SQLite's ALTER TABLE ADD
-- COLUMN cannot carry UNIQUE, so the constraint has to arrive as its own
-- index. That is not a compromise here: SQLite treats NULLs as distinct in a
-- unique index, so every pre-existing batch coexists under it without a
-- sentinel value.
--
-- Uniqueness is across ALL TIME, not "among open batches". This schema has no
-- closed state, and a vendor replying to a six-month-old thread is ordinary.

BEGIN;

ALTER TABLE requests ADD COLUMN kode TEXT;

CREATE UNIQUE INDEX idx_requests_kode ON requests(kode);

COMMIT;
