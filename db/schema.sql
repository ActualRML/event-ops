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

CREATE TABLE requests (
    id               INTEGER PRIMARY KEY,
    judul_acara      TEXT NOT NULL,
    tanggal_acara    TEXT,
    lokasi           TEXT,
    kebutuhan        TEXT,
    deadline         TEXT,
    pengirim_nama    TEXT,
    subject_template TEXT NOT NULL,
    body_template    TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE outbox (
    id           INTEGER PRIMARY KEY,
    request_id   INTEGER NOT NULL REFERENCES requests(id),
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
    request_id     INTEGER NOT NULL REFERENCES requests(id),
    vendor_id      INTEGER NOT NULL REFERENCES vendors(id),
    nomor          TEXT NOT NULL UNIQUE,
    harga          INTEGER NOT NULL CHECK (harga > 0),
    lingkup_kerja  TEXT,
    termin         TEXT,
    tanggal_terbit TEXT NOT NULL DEFAULT (date('now', 'localtime')),
    created_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (request_id, vendor_id)
);

CREATE INDEX idx_vendor_categories_category ON vendor_categories(category_id);
CREATE INDEX idx_outbox_request ON outbox(request_id);
CREATE INDEX idx_outbox_status ON outbox(status);
CREATE INDEX idx_vendors_aktif ON vendors(aktif);
CREATE INDEX idx_spk_request ON spk(request_id);

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
