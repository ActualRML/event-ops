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
CREATE TABLE events (
    id            INTEGER PRIMARY KEY,
    judul_acara   TEXT NOT NULL,
    tanggal_acara TEXT,
    lokasi        TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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
    created_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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
CREATE TABLE sponsor_item (
    id         INTEGER PRIMARY KEY,
    sponsor_id INTEGER NOT NULL REFERENCES sponsors(id) ON DELETE CASCADE,
    item_id    INTEGER NOT NULL REFERENCES items(id),
    qty        INTEGER NOT NULL CHECK (qty > 0),
    cost       INTEGER NOT NULL CHECK (cost >= 0),
    value      INTEGER NOT NULL CHECK (value >= 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (sponsor_id, item_id)
);

CREATE INDEX idx_vendor_categories_category ON vendor_categories(category_id);
CREATE INDEX idx_requests_event ON requests(event_id);
CREATE INDEX idx_outbox_request ON outbox(request_id);
CREATE INDEX idx_outbox_status ON outbox(status);
CREATE INDEX idx_vendors_aktif ON vendors(aktif);
CREATE INDEX idx_spk_request ON spk(request_id);
CREATE INDEX idx_sponsors_event ON sponsors(event_id);
CREATE INDEX idx_sponsor_item_sponsor ON sponsor_item(sponsor_id);

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
