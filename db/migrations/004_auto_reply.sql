-- 004_auto_reply.sql — mark generated replies so they stop being counted.
--
-- One column, no data movement, no table rebuild.
--
--   python -c "import sqlite3,sys; c=sqlite3.connect('db/rfq.db'); c.executescript(open(sys.argv[1],encoding='utf-8').read()); c.close()" db/migrations/004_auto_reply.sql
--
-- NOT `python -m sqlite3 db/rfq.db ".read ..."`: that module has no .read and
-- dies with `OperationalError (SQLITE_ERROR): near ".": syntax error` before
-- running a single statement. The real sqlite3 CLI does support .read, but it
-- is not installed here.
--
-- Take a backup first. init_db.py prints the command it wants.
--
-- THE PROBLEM THIS FIXES. An out-of-office comes from the vendor's OWN address
-- and usually carries In-Reply-To, so it passes the gate and matches at tier 1
-- — against the exact outbox row, correctly, because it genuinely is a message
-- from that vendor about that thread. It then counts toward "5 of 8 vendors
-- have replied", and that count is the entire point of the feature.
--
-- A bounce never gets that far, because mailer-daemon is not a vendor. An
-- auto-reply IS the vendor, which is why the gate cannot be what stops it.
--
-- Detected from headers only, never from the subject line: Auto-Submitted
-- (RFC 3834) with any value but "no", X-Autoreply or X-Autorespond present, or
-- Precedence of auto_reply/bulk/junk. Subject sniffing for "Out of Office"
-- would be localised guesswork, and this app writes to Indonesian vendors
-- whose servers answer in Indonesian.
--
-- Recorded, not filtered. The row is stored and displayed like any other — an
-- admin should see that the vendor's mail server answered — but it is left out
-- of the replied count and the badge. Same shape as tier: store what the thing
-- is, and let the display decide what to do about it.
--
-- 0 is the true history for rows already stored: they were matched before this
-- existed, and none was examined for these headers. Re-checking them is not
-- possible from here — the headers were never kept, only the parsed fields.
-- Anything already miscounted stays miscounted until it is re-fetched.

BEGIN;

ALTER TABLE inbox ADD COLUMN auto_reply INTEGER NOT NULL DEFAULT 0
    CHECK (auto_reply IN (0, 1));

COMMIT;
