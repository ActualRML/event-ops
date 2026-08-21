-- Vendor RFQ Blast — schema

CREATE TABLE categories (
    id   INTEGER PRIMARY KEY,
    nama TEXT NOT NULL COLLATE NOCASE UNIQUE
);

CREATE TABLE vendors (
    id         INTEGER PRIMARY KEY,
    nama_pt    TEXT NOT NULL,
    pic_nama   TEXT,
    email      TEXT NOT NULL,
    no_hp      TEXT,
    area       TEXT,
    catatan    TEXT,
    aktif      INTEGER NOT NULL DEFAULT 1 CHECK (aktif IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE vendor_categories (
    vendor_id   INTEGER NOT NULL REFERENCES vendors(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (vendor_id, category_id)
);

-- The item catalog: the things an event is quoted and billed for, priced once
-- and reused. cost is what procurement pays per unit, value the sponsor-facing
-- rate; both are whole rupiah like spk.harga, and both may be zero — an item
-- carried at no cost is a real entry, not a defect.
--
-- Deliberately not grouped. This table carried a category_id into `categories`,
-- which was a modelling error: `categories` is the vendor-side trade list —
-- what we buy in and ask for quotes on — while an item is something we own and
-- sell on. The two are different domains and the FK read as if they were one.
-- No replacement column and no items-only category table either: a catalog this
-- size does not need grouping. Revisit past roughly thirty rows.
CREATE TABLE items (
    id      INTEGER PRIMARY KEY,
    nama    TEXT NOT NULL COLLATE NOCASE UNIQUE,
    satuan  TEXT NOT NULL DEFAULT '',
    cost    INTEGER NOT NULL CHECK (cost >= 0),
    value   INTEGER NOT NULL CHECK (value >= 0),
    catatan TEXT NOT NULL DEFAULT '',
    aktif   INTEGER NOT NULL DEFAULT 1 CHECK (aktif IN (0, 1))
);

-- The event itself: what is being run, when, and where. One row per event
-- however many quote rounds it takes. judul_acara, tanggal_acara and lokasi
-- live here and nowhere else — db.py grafts them back onto a request row so
-- core/renderer and core/dokumen keep receiving the names they always had.
-- zona is the fact the surcharge is computed from; lokasi is free text beside
-- it and stays that way, because lokasi is printed into RFQ emails and the SPK
-- and must not be reduced to a list of three.
--
-- zona sits after created_at rather than next to lokasi purely because it was
-- added later, when the only way to add a column was to append one. That is
-- history, not a rule: schema changes are made by editing this file and
-- rebuilding, so a new column goes wherever it reads best. Nothing depends on
-- column order — every INSERT names its columns.
CREATE TABLE events (
    id            INTEGER PRIMARY KEY,
    judul_acara   TEXT NOT NULL,
    tanggal_acara TEXT,
    lokasi        TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    zona          TEXT NOT NULL DEFAULT 'jabodetabek'
                  CHECK (zona IN ('jabodetabek', 'luar_jabodetabek', 'luar_jawa'))
);

-- One RFQ batch. An event can have several: a first round for tenda and
-- sound, a later one for catering. kebutuhan and deadline stay here because
-- they differ per round; the templates stay because each batch records what
-- it actually sent.
CREATE TABLE requests (
    id               INTEGER PRIMARY KEY,
    event_id         INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    -- One send is one category. It is the batch's own field, not a filter the
    -- picker happened to be on: it decides which vendors can be in the batch
    -- and it is the {{ kategori }} every email in it is written about.
    category_id      INTEGER NOT NULL REFERENCES categories(id),
    kebutuhan        TEXT,
    deadline         TEXT,
    pengirim_nama    TEXT,
    subject_template TEXT NOT NULL,
    body_template    TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    -- The reference code printed into the outgoing subject as [RFQ-3F2A]. A
    -- subject survives a vendor pressing Reply, so this is what comes back on
    -- the answer and says which batch it belongs to.
    --
    -- Nullable, because NULL is the true history for any batch that went out
    -- before codes existed — a backfill would claim a code no vendor ever saw.
    -- The seed gives every batch one, since a seeded database with no codes
    -- cannot demonstrate matching a reply by its subject.
    --
    -- Sits at the end for the same reason events.zona does: it was added when
    -- appending was the only option. Not a rule to follow.
    --
    -- UNIQUE lives in idx_requests_kode below rather than on the column, and
    -- that is worth keeping: SQLite treats NULLs as distinct in an index, so
    -- every code-less batch coexists under it without needing a sentinel.
    kode             TEXT
);

CREATE TABLE outbox (
    id           INTEGER PRIMARY KEY,
    -- Cascades so deleting an event takes its batches and their history with
    -- it in one statement. Without this the delete is blocked by the FK.
    request_id   INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    vendor_id    INTEGER NOT NULL REFERENCES vendors(id),
    email_tujuan TEXT NOT NULL,
    subject      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'draft'
                 CHECK (status IN ('draft', 'sent', 'failed', 'replied')),
    error_msg    TEXT,
    message_id   TEXT,
    sent_at      TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (request_id, vendor_id)
);

-- One work order per vendor per request. nomor is allocated at insert and
-- never recomputed, so a document reprinted later carries its original number.
-- harga is whole rupiah; formatting and terbilang happen on the way out.
CREATE TABLE spk (
    id             INTEGER PRIMARY KEY,
    -- Keyed to the batch, not the event: an SPK comes out of one specific
    -- quote round. Cascades with its batch when the event goes.
    request_id     INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    vendor_id      INTEGER NOT NULL REFERENCES vendors(id),
    nomor          TEXT NOT NULL UNIQUE,
    harga          INTEGER NOT NULL CHECK (harga > 0),
    lingkup_kerja  TEXT,
    termin         TEXT,
    tanggal_terbit TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (request_id, vendor_id)
);

-- One rundown per event, hung off events rather than requests: the running
-- order belongs to the day, not to whichever quote round happened to be open
-- when someone typed it. UNIQUE on event_id is what makes that exact.
-- jam_mulai and batas_venue are HH:MM wall-clock strings; batas_venue is
-- optional. No column here stores a computed time — every start and end time
-- is derived from jam_mulai plus cumulative duration, never persisted.
CREATE TABLE rundown (
    id          INTEGER PRIMARY KEY,
    event_id    INTEGER NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
    jam_mulai   TEXT NOT NULL,
    batas_venue TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- urutan is 1-based and contiguous: delete and move renumber so there is
-- never a gap. UNIQUE(rundown_id, urutan) is what forces that discipline,
-- and doubles as the lookup index for list_items.
CREATE TABLE rundown_item (
    id           INTEGER PRIMARY KEY,
    rundown_id   INTEGER NOT NULL REFERENCES rundown(id) ON DELETE CASCADE,
    urutan       INTEGER NOT NULL,
    kegiatan     TEXT NOT NULL,
    durasi_menit INTEGER NOT NULL CHECK (durasi_menit > 0),
    pic          TEXT,
    catatan      TEXT,
    UNIQUE (rundown_id, urutan)
);

-- One sponsor of one event. kontribusi is what they pay us, whole rupiah like
-- every other amount here. persen_budget is the share of that contribution we
-- are willing to spend on their package; the budget itself is derived, never
-- stored. UNIQUE(event_id, nama_pt) is per event on purpose — the same company
-- sponsoring two events is two rows, and nama_pt is COLLATE NOCASE so a
-- difference of case is a collision, not a second sponsor.
CREATE TABLE sponsors (
    id            INTEGER PRIMARY KEY,
    event_id      INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    nama_pt       TEXT NOT NULL COLLATE NOCASE,
    kontribusi    INTEGER NOT NULL CHECK (kontribusi > 0),
    persen_budget INTEGER NOT NULL DEFAULT 12
                  CHECK (persen_budget BETWEEN 1 AND 100),
    catatan       TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (event_id, nama_pt)
);

-- One line of a sponsor's package.
--
-- cost and value are SNAPSHOTS, copied from the catalog when the line is added
-- and never joined live from items afterwards. Repricing an item must not
-- silently rewrite a package that has already been agreed. This is the exact
-- opposite of the rundown rule, where every displayed time is recomputed from
-- jam_mulai so that moving the start reschedules the whole day: a rundown
-- describes what will happen and has to follow the plan, a package records what
-- was promised and has to stay put.
-- zona_pct records WHY cost and value are what they are: the zone surcharge in
-- force when the line was priced. Nothing sums it and no total reads it. It
-- exists so that a line priced under one zone stays identifiable after its
-- event moves to another — otherwise a stale snapshot is indistinguishable
-- from a current one, and the difference reads as a bug rather than as
-- history. It does not license repricing; see invariant 15.
CREATE TABLE sponsor_item (
    id         INTEGER PRIMARY KEY,
    sponsor_id INTEGER NOT NULL REFERENCES sponsors(id) ON DELETE CASCADE,
    item_id    INTEGER NOT NULL REFERENCES items(id),
    qty        INTEGER NOT NULL CHECK (qty > 0),
    cost       INTEGER NOT NULL CHECK (cost >= 0),
    value      INTEGER NOT NULL CHECK (value >= 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    zona_pct   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (sponsor_id, item_id)
);

-- One received vendor reply that got past the gate in replies.py.
--
-- message_id is the DEDUPE KEY, and load-bearing rather than defensive: IMAP
-- SEARCH SINCE has date granularity only, so every check re-examines the whole
-- day of the last successful run. UNIQUE is what makes that a no-op.
--
-- received_at is the SENDER's clock, from their Date header. It can be skewed,
-- wrong, or earlier than the RFQ it answers — a badly-set clock, not
-- corruption. created_at is our clock and is the tie-break when one is needed.
--
-- tier records HOW it matched and is never rewritten. Assigning a tier-3 reply
-- by hand fills request_id and leaves tier at 3, which is why "needs assigning"
-- is `tier = 3 AND request_id IS NULL` rather than a status that flips — the
-- same reasoning as sponsor_item.zona_pct. All three FKs are nullable because
-- the tiers resolve different amounts: 1 fills all three, 2 fills request_id
-- and sometimes the rest, 3 fills vendor_id only, 4 fills none.
CREATE TABLE inbox (
    id          INTEGER PRIMARY KEY,
    message_id  TEXT NOT NULL UNIQUE,
    from_email  TEXT NOT NULL,
    from_nama   TEXT,
    subject     TEXT NOT NULL,
    received_at TEXT NOT NULL,
    body        TEXT NOT NULL,
    tier        INTEGER NOT NULL CHECK (tier IN (1, 2, 3, 4)),
    request_id  INTEGER REFERENCES requests(id) ON DELETE CASCADE,
    outbox_id   INTEGER REFERENCES outbox(id) ON DELETE CASCADE,
    vendor_id   INTEGER REFERENCES vendors(id),
    read_at     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    -- An out-of-office comes from the vendor's OWN address and usually carries
    -- In-Reply-To, so it passes the gate and matches at tier 1 against the
    -- exact outbox row — correctly, because it really is that vendor on that
    -- thread. It must still not count toward "5 of 8 vendors have replied",
    -- which is the whole point of the feature. A bounce never gets this far
    -- (mailer-daemon is not a vendor); an auto-reply IS the vendor, so the
    -- gate cannot be what stops it.
    --
    -- Set from headers only — Auto-Submitted (RFC 3834), X-Autoreply /
    -- X-Autorespond, Precedence — never from the subject line, which would be
    -- localised guesswork against Indonesian mail servers.
    --
    -- Recorded, not filtered: stored and displayed like any other reply, and
    -- left out of the count and the badge. Same shape as tier — store what it
    -- is, let the display decide.
    auto_reply  INTEGER NOT NULL DEFAULT 0 CHECK (auto_reply IN (0, 1)),
    -- When a person accepted this quote, and NULL until they do. It is the
    -- gate an SPK has to pass: procurement reads the reply, agrees with what
    -- the vendor offered, and says so here.
    --
    -- Deliberately not read_at and deliberately not outbox.status. read_at
    -- means "seen", which is not agreement — the whole point of this column is
    -- that opening a quote and accepting it are different acts. outbox.status
    -- is a DELIVERY outcome (invariant 19) and is per vendor, while agreement
    -- is per reply: a vendor who sends a revised quote is a second row, and
    -- which of the two was accepted has to stay answerable.
    --
    -- A timestamp rather than a flag, for the same reason read_at is one: when
    -- it was agreed is worth as much as whether. Cleared back to NULL by
    -- un-approving, which is refused once an SPK exists for that pair.
    approved_at TEXT
);

-- One file attached to a reply. The BYTES are on the filesystem under
-- attachments/, not here — which is why db/rfq.db alone is no longer a
-- complete backup. See CLAUDE.md.
--
-- filename is the vendor's, for display and Content-Disposition. stored_name
-- is ours, and that split is the guarantee: the attacker-controlled string
-- never touches a path, so traversal is unreachable rather than defended.
CREATE TABLE inbox_attachment (
    id           INTEGER PRIMARY KEY,
    inbox_id     INTEGER NOT NULL REFERENCES inbox(id) ON DELETE CASCADE,
    filename     TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes   INTEGER NOT NULL CHECK (size_bytes >= 0),
    stored_name  TEXT NOT NULL UNIQUE
);

-- One row per check run: a log, not a settings row, because it answers three
-- questions at once with no session to hold them — where to resume, when the
-- last check was, and what went wrong on it.
--
-- The watermark is MAX(started_at) WHERE ok = 1. A FAILED RUN MUST NOT ADVANCE
-- IT: that is the difference between "the check errored" and "the check
-- quietly skipped a day". No rows means never checked, which the UI says out
-- loud rather than rendering as zero. error_msg is the raw exception string,
-- translated on display like outbox.error_msg.
CREATE TABLE inbox_check (
    id         INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    ok         INTEGER NOT NULL CHECK (ok IN (0, 1)),
    error_msg  TEXT,
    examined   INTEGER NOT NULL DEFAULT 0,
    kept       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_vendor_categories_category ON vendor_categories(category_id);
CREATE INDEX idx_requests_event ON requests(event_id);
-- UNIQUE, not a plain index: this is requests.kode's constraint, which
-- ALTER TABLE ADD COLUMN could not carry. See the column comment.
CREATE UNIQUE INDEX idx_requests_kode ON requests(kode);
CREATE INDEX idx_outbox_request ON outbox(request_id);
CREATE INDEX idx_outbox_status ON outbox(status);
CREATE INDEX idx_vendors_aktif ON vendors(aktif);
CREATE INDEX idx_spk_request ON spk(request_id);
CREATE INDEX idx_sponsors_event ON sponsors(event_id);
CREATE INDEX idx_sponsor_item_sponsor ON sponsor_item(sponsor_id);
CREATE INDEX idx_inbox_request ON inbox(request_id);
CREATE INDEX idx_inbox_tier ON inbox(tier);
CREATE INDEX idx_inbox_attachment_inbox ON inbox_attachment(inbox_id);

-- One row per vendor; categories flattened into a single display string.
-- Vendors with no category still appear, with kategori NULL.
CREATE VIEW v_vendor_lengkap AS
SELECT v.id,
       v.nama_pt,
       v.pic_nama,
       v.email,
       v.no_hp,
       v.area,
       v.catatan,
       v.aktif,
       v.created_at,
       group_concat(c.nama, ', ' ORDER BY c.nama) AS kategori
FROM vendors v
LEFT JOIN vendor_categories vc ON vc.vendor_id = v.id
LEFT JOIN categories c ON c.id = vc.category_id
GROUP BY v.id;
