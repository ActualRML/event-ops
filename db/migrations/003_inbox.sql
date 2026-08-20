-- 003_inbox.sql — vendor replies: the incoming side.
--
-- Three new tables, no changes to anything that exists, no data movement.
--
-- Applied by hand. There is no version table, so nothing records that this
-- ran; re-running it fails with "table inbox already exists" and stops before
-- the rest. That error is the whole idempotency guard, and it is a safe one —
-- it refuses rather than half-applying.
--
--   python -c "import sqlite3,sys; c=sqlite3.connect('db/rfq.db'); c.executescript(open(sys.argv[1],encoding='utf-8').read()); c.close()" db/migrations/003_inbox.sql
--
-- NOT `python -m sqlite3 db/rfq.db ".read ..."`: that module has no .read and
-- dies with `OperationalError (SQLITE_ERROR): near ".": syntax error` before
-- running a single statement. The real sqlite3 CLI does support .read, but it
-- is not installed here.
--
-- Take a backup first. init_db.py prints the command it wants.
--
-- ONE THING THIS MIGRATION DOES NOT COVER. Attachment BYTES live on the
-- filesystem under attachments/, not in any column here. So from this point on
-- db/rfq.db is no longer a complete backup of the system: restoring it alone
-- brings back every reply row with its filename, size and content type, and
-- not one byte of any attachment — the rows look intact and the downloads 404.
-- Copy attachments/ alongside the database. See CLAUDE.md.

BEGIN;

-- One received message that got past the gate.
--
-- message_id is the DEDUPE KEY and that is load-bearing, not defensive. IMAP
-- SEARCH SINCE has date granularity only — there is no "since 14:32" — so
-- every check re-examines the whole day of the last successful run. UNIQUE
-- here is what turns that re-examination into a no-op instead of duplicates.
--
-- received_at comes from the sender's Date header, which is THEIR clock. It
-- can be skewed, wrong, or even earlier than the RFQ it answers; a reply that
-- appears to predate its own request is a badly-set clock, not corruption.
-- created_at is our clock and is the tie-break when one is needed.
--
-- tier records HOW the message was matched and is never rewritten — assigning
-- a tier-3 reply by hand fills request_id and leaves tier at 3. That is why
-- "needs assigning" is `tier = 3 AND request_id IS NULL` rather than a status
-- that flips. Same reasoning as sponsor_item.zona_pct: store the input that
-- produced the outcome, so a hand-assigned reply stays distinguishable from a
-- matched one instead of looking like a bug.
--
-- The three FKs are all nullable because the tiers differ in how much they
-- resolve: tier 1 fills all three, tier 2 fills request_id and sometimes the
-- other two, tier 3 fills vendor_id only, tier 4 fills none.
CREATE TABLE inbox (
    id          INTEGER PRIMARY KEY,
    message_id  TEXT NOT NULL UNIQUE,
    from_email  TEXT NOT NULL,
    from_nama   TEXT,
    subject     TEXT NOT NULL,
    received_at TEXT NOT NULL,
    body        TEXT NOT NULL,
    tier        INTEGER NOT NULL CHECK (tier IN (1, 2, 3, 4)),
    -- Cascades with the batch, so deleting an event takes its replies too.
    request_id  INTEGER REFERENCES requests(id) ON DELETE CASCADE,
    outbox_id   INTEGER REFERENCES outbox(id) ON DELETE CASCADE,
    -- No ON DELETE: vendors are archive-only and never deleted, and if one
    -- ever were, SQLite refusing is better than a reply losing its sender.
    vendor_id   INTEGER REFERENCES vendors(id),
    read_at     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- One file that arrived attached to a reply.
--
-- filename is the vendor's, kept for display and for the Content-Disposition
-- header. stored_name is OURS, and the split is the security guarantee: the
-- attacker-controlled string never touches a path, so traversal is not
-- defended against, it is structurally unreachable.
CREATE TABLE inbox_attachment (
    id           INTEGER PRIMARY KEY,
    inbox_id     INTEGER NOT NULL REFERENCES inbox(id) ON DELETE CASCADE,
    filename     TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes   INTEGER NOT NULL CHECK (size_bytes >= 0),
    stored_name  TEXT NOT NULL UNIQUE
);

-- One row per check run. A log, not a settings row, because it has to answer
-- three questions at once and there is no session to hold a flash message in:
-- where to resume from, when the last check was, and what went wrong on it.
--
-- The watermark reads MAX(started_at) WHERE ok = 1. A FAILED RUN MUST NOT
-- ADVANCE IT — that is the difference between "the check errored" and "the
-- check quietly skipped a day". No rows at all means never checked, which the
-- UI must say out loud rather than rendering as zero.
--
-- error_msg holds the raw "ExceptionName: detail" string. Translation happens
-- on display, the same rule outbox.error_msg follows, so reworded messages
-- need no migration.
CREATE TABLE inbox_check (
    id         INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    ok         INTEGER NOT NULL CHECK (ok IN (0, 1)),
    error_msg  TEXT,
    examined   INTEGER NOT NULL DEFAULT 0,
    kept       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_inbox_request ON inbox(request_id);
CREATE INDEX idx_inbox_outbox ON inbox(outbox_id);
CREATE INDEX idx_inbox_tier ON inbox(tier);
CREATE INDEX idx_inbox_attachment_inbox ON inbox_attachment(inbox_id);

COMMIT;
