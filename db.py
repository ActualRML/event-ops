"""SQLite access layer. All SQL lives here."""

import sqlite3
from contextlib import closing, contextmanager
from datetime import date

import config
from core import penomoran
# Aliased: this module already has a `kode` in scope as a parameter name in
# more than one place, and shadowing an imported module with an argument is the
# kind of bug that only shows up on the line that finally calls it.
from core import kode as core_kode


def get_conn() -> sqlite3.Connection:
    """Open a connection. Pragmas are per-connection, so they are set here."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def transaksi(conn: sqlite3.Connection | None = None):
    """Own a connection and commit, or borrow the caller's and leave the commit
    to them. Phase A of a send needs several writes inside one transaction."""
    if conn is not None:
        yield conn
        return
    milik = get_conn()
    try:
        yield milik
        milik.commit()
    finally:
        milik.close()


def list_categories() -> list[sqlite3.Row]:
    """All categories in seed order. Send opens on the first one, so id order
    keeps Tenda in front rather than whatever sorts first alphabetically."""
    with closing(get_conn()) as conn:
        return conn.execute("SELECT id, nama FROM categories ORDER BY id").fetchall()


def category_exists(nama: str) -> bool:
    """The UNIQUE COLLATE NOCASE on the column is the real guard; this only
    exists so the form can say which name collided instead of raising."""
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT 1 FROM categories WHERE nama = ? COLLATE NOCASE", (nama,)
        ).fetchone()
    return row is not None


def create_category(nama: str) -> int:
    """Insert one category. Returns the new id."""
    with closing(get_conn()) as conn:
        cur = conn.execute("INSERT INTO categories (nama) VALUES (?)", (nama,))
        conn.commit()
        return cur.lastrowid


def pola_cari(q: str) -> str:
    """Wrap a search term for LIKE. The wildcards a user types are escaped so
    they match literally — otherwise a stray _ silently matches any character."""
    aman = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{aman}%"


def list_vendors(kategori: str | None = None, q: str | None = None,
                 aktif_only: bool = True) -> list[sqlite3.Row]:
    """Vendors with their categories flattened. Filter is by category membership,
    so a vendor listed under several categories matches each of them. q narrows
    that further by name, PIC, or email; the two combine with AND."""
    clauses = []
    params: list[object] = []

    if aktif_only:
        clauses.append("aktif = 1")

    if q and q.strip():
        # LIKE is already case-insensitive for ASCII in SQLite, so no lower().
        clauses.append(
            r"""(nama_pt  LIKE ? ESCAPE '\'
              OR pic_nama LIKE ? ESCAPE '\'
              OR email    LIKE ? ESCAPE '\')"""
        )
        pola = pola_cari(q.strip())
        params.extend([pola, pola, pola])

    if kategori:
        clauses.append(
            """id IN (SELECT vc.vendor_id
                        FROM vendor_categories vc
                        JOIN categories c ON c.id = vc.category_id
                       WHERE c.nama = ?)"""
        )
        params.append(kategori)

    sql = "SELECT * FROM v_vendor_lengkap"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY nama_pt"

    with closing(get_conn()) as conn:
        return conn.execute(sql, params).fetchall()


def get_vendor(vendor_id: int) -> sqlite3.Row | None:
    """One vendor by id, or None."""
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM v_vendor_lengkap WHERE id = ?", (vendor_id,)
        ).fetchone()


def list_vendors_by_category(category_id: int, aktif_only: bool = True) -> list[sqlite3.Row]:
    """Vendors in one category, by id. kategori_ids carries every category the
    vendor belongs to, so the page can count categories across a selection
    without another query per vendor."""
    sql = """SELECT v.id, v.nama_pt, v.pic_nama, v.email, v.aktif,
                    (SELECT group_concat(vc2.category_id)
                       FROM vendor_categories vc2
                      WHERE vc2.vendor_id = v.id) AS kategori_ids
               FROM vendors v
               JOIN vendor_categories vc ON vc.vendor_id = v.id
              WHERE vc.category_id = ?"""
    if aktif_only:
        sql += " AND v.aktif = 1"
    sql += " ORDER BY v.nama_pt"

    with closing(get_conn()) as conn:
        return conn.execute(sql, (category_id,)).fetchall()


def get_vendor_categories(vendor_id: int) -> list[int]:
    """Category ids for one vendor. The view flattens names for display;
    the edit form needs the ids to tick the right boxes."""
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT category_id FROM vendor_categories WHERE vendor_id = ?", (vendor_id,)
        ).fetchall()
    return [r["category_id"] for r in rows]


def create_vendor(
    nama_pt: str,
    pic_nama: str,
    email: str,
    no_hp: str,
    area: str,
    catatan: str,
    aktif: int = 1,
) -> int:
    """Insert one vendor. Returns the new id."""
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """INSERT INTO vendors (nama_pt, pic_nama, email, no_hp, area, catatan, aktif)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (nama_pt, pic_nama, email, no_hp, area, catatan, aktif),
        )
        conn.commit()
        return cur.lastrowid


def update_vendor(
    vendor_id: int,
    nama_pt: str,
    pic_nama: str,
    email: str,
    no_hp: str,
    area: str,
    catatan: str,
    aktif: int,
) -> None:
    """Overwrite one vendor row."""
    with closing(get_conn()) as conn:
        conn.execute(
            """UPDATE vendors
                  SET nama_pt = ?, pic_nama = ?, email = ?, no_hp = ?,
                      area = ?, catatan = ?, aktif = ?
                WHERE id = ?""",
            (nama_pt, pic_nama, email, no_hp, area, catatan, aktif, vendor_id),
        )
        conn.commit()


def set_vendor_aktif(vendor_id: int, aktif: int) -> None:
    """Set the active flag to an explicit value."""
    with closing(get_conn()) as conn:
        conn.execute("UPDATE vendors SET aktif = ? WHERE id = ?", (aktif, vendor_id))
        conn.commit()


def list_catalog_items(include_inactive: bool = False) -> list[sqlite3.Row]:
    """Catalog items by name. The column is COLLATE NOCASE, so the ordering is
    case-insensitive without saying so here.

    No join and no grouping: the table used to carry a category_id into the
    vendor-side `categories` list, which put two different domains on one key.
    See the note in schema.sql.

    Archived items are left out unless asked for: the page hides them by
    default and the toggle is what brings them back."""
    sql = "SELECT * FROM items"
    if not include_inactive:
        sql += " WHERE aktif = 1"
    sql += " ORDER BY nama"

    with closing(get_conn()) as conn:
        return conn.execute(sql).fetchall()


def get_catalog_item(item_id: int) -> sqlite3.Row | None:
    """One catalog item by id, or None. Archived rows come back too — the edit
    form has to be able to open one."""
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM items WHERE id = ?", (item_id,)
        ).fetchone()


def item_name_exists(nama: str, exclude_id: int | None = None) -> bool:
    """The UNIQUE COLLATE NOCASE on the column is the real guard; this only
    exists so the form can say which name collided instead of raising.
    exclude_id lets an edit keep its own name — same shape as
    category_exists, one argument wider because items can be renamed."""
    sql = "SELECT 1 FROM items WHERE nama = ? COLLATE NOCASE"
    params: list[object] = [nama]
    if exclude_id is not None:
        sql += " AND id <> ?"
        params.append(exclude_id)

    with closing(get_conn()) as conn:
        return conn.execute(sql, params).fetchone() is not None


def create_catalog_item(nama: str, satuan: str, cost: int, value: int,
                        catatan: str) -> int:
    """Insert one catalog item. Returns the new id. The optional text fields are
    stored as '' rather than NULL, so nothing downstream tests for both."""
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """INSERT INTO items (nama, satuan, cost, value, catatan)
               VALUES (?, ?, ?, ?, ?)""",
            (nama, satuan, cost, value, catatan),
        )
        conn.commit()
        return cur.lastrowid


def update_catalog_item(item_id: int, nama: str, satuan: str, cost: int,
                        value: int, catatan: str) -> None:
    """Overwrite one catalog item. aktif is left out of the statement
    deliberately — archiving has its own route and its own function, so an
    edit can never quietly restore a row."""
    with closing(get_conn()) as conn:
        conn.execute(
            """UPDATE items
                  SET nama = ?, satuan = ?, cost = ?, value = ?, catatan = ?
                WHERE id = ?""",
            (nama, satuan, cost, value, catatan, item_id),
        )
        conn.commit()


def set_catalog_item_aktif(item_id: int, aktif: int) -> None:
    """Archive or restore one item, to an explicit value. Nothing deletes a
    catalog row — a price that was quoted once stays on the books."""
    with closing(get_conn()) as conn:
        conn.execute("UPDATE items SET aktif = ? WHERE id = ?", (aktif, item_id))
        conn.commit()


def create_event(judul_acara: str, tanggal_acara: str, lokasi: str,
                 zona: str = config.ZONA_DEFAULT,
                 conn: sqlite3.Connection | None = None) -> int:
    """Insert one event. Returns the new id.

    zona defaults rather than being required: it is the cheapest zone and the
    column's own DEFAULT says the same, so a caller that has no opinion writes
    the same row either way."""
    with transaksi(conn) as c:
        cur = c.execute(
            """INSERT INTO events (judul_acara, tanggal_acara, lokasi, zona)
               VALUES (?, ?, ?, ?)""",
            (judul_acara, tanggal_acara, lokasi, zona),
        )
        return cur.lastrowid


def list_events() -> list[sqlite3.Row]:
    """Events newest first, with how many batches each has gone out in."""
    with closing(get_conn()) as conn:
        return conn.execute(
            """SELECT e.*, COUNT(r.id) AS batches
                 FROM events e
                 LEFT JOIN requests r ON r.event_id = e.id
                GROUP BY e.id
                ORDER BY e.id DESC"""
        ).fetchall()


def get_event(event_id: int) -> sqlite3.Row | None:
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()


def update_event(event_id: int, judul_acara: str, tanggal_acara: str,
                 lokasi: str, zona: str) -> None:
    """Overwrite one event's own fields.

    Nothing else moves. Batches, outbox rows, SPK and the rundown all reference
    the event by id, and every one of them reads the title, date and location
    back through a join — so correcting a title here is a correction everywhere
    it is displayed, and rewrites no other row."""
    with closing(get_conn()) as conn:
        conn.execute(
            """UPDATE events
                  SET judul_acara = ?, tanggal_acara = ?, lokasi = ?, zona = ?
                WHERE id = ?""",
            (judul_acara, tanggal_acara, lokasi, zona, event_id),
        )
        conn.commit()


# The one place event fields are grafted back onto a request row. Everything
# that hands a row to core/ reads through this, so judul_acara, tanggal_acara
# and lokasi arrive under exactly the names renderer and dokumen expect —
# only their storage moved.
SQL_REQUEST_WITH_EVENT = """
    SELECT r.*, e.judul_acara, e.tanggal_acara, e.lokasi, c.nama AS kategori
      FROM requests r
      JOIN events e ON e.id = r.event_id
      JOIN categories c ON c.id = r.category_id
"""

# What core.renderer.render_email reads out of a brief. Named here so the
# shape has one definition rather than one per caller.
#
# kode rides along because the subject marker is rendered from it. A batch
# created before codes existed carries NULL and renders no marker, so the field
# is present-but-empty rather than absent — renderer reads it with .get() and
# treats blank and missing alike.
BRIEF_FIELDS = ("judul_acara", "tanggal_acara", "lokasi", "kategori",
                "kebutuhan", "deadline", "pengirim_nama", "kode")


def brief_dari_row(row) -> dict:
    """Flatten a joined request row into the brief dict core/ expects.

    The merge itself is the JOIN in SQL_REQUEST_WITH_EVENT; this is where the
    resulting shape is pinned down. Pass it anything request_detail returns."""
    return {nama: row[nama] for nama in BRIEF_FIELDS}


def konteks_vendor(vendor, kategori: str) -> dict:
    """The vendor half of what core.renderer.render_email expects.

    The one place {{ kategori }} is decided. renderer reads it off the vendor
    dict, not the brief, so this is where the batch's category replaces the
    vendor's own list: a vendor in three categories quoted on a Tenda batch is
    written to about Tenda, and nothing else."""
    return {
        "nama_pt": vendor["nama_pt"],
        "pic_nama": vendor["pic_nama"],
        "kategori": kategori,
    }


def kode_exists(kode: str) -> bool:
    """The UNIQUE index on requests.kode is the real guard; this exists so the
    send page can re-roll a colliding code before it ever reaches an INSERT,
    rather than letting the user's dispatch be the thing that discovers it."""
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT 1 FROM requests WHERE kode = ?", (kode,)
        ).fetchone()
    return row is not None


def request_by_kode(kode: str) -> sqlite3.Row | None:
    """The batch carrying one reference code, or None.

    None is a real answer rather than only a bad input: a code can be
    well-formed and still match nothing, because deleting an event cascades its
    batches away while the mail quoting that code is still in someone's inbox."""
    if not kode:
        return None
    with closing(get_conn()) as conn:
        return conn.execute(
            SQL_REQUEST_WITH_EVENT + " WHERE r.kode = ?", (kode,)
        ).fetchone()


# How many times create_request re-rolls a colliding code before giving up.
# 65,536 codes against a demo's worth of batches makes one collision unlikely
# and two vanishingly so: the cap bounds the loop, it is not a limit anything
# is expected to approach.
MAKS_UNDIAN_KODE = 10


def create_request(brief: dict, subject_template: str, body_template: str,
                   category_id: int, event_id: int, kode: str | None = None,
                   conn: sqlite3.Connection | None = None) -> int:
    """Insert one RFQ batch against an event that already exists. Returns the
    new request id.

    event_id is required. It was optional, and None meant "create the event
    from this brief" — a branch that existed only because /send used to carry
    the event fields on its own form. Events are now created on /events, so the
    only thing that branch could still do is mint an untitled orphan event from
    a brief whose title happens to be blank. A function must admit exactly what
    its callers can produce, the same rule a CHECK constraint follows.
    Something that genuinely needs a new event calls create_event.

    kode is the caller's PREFERRED code, not a promise. /send mints one at
    preview so the subject shown is the subject sent, and checks it free — but
    nothing owns a code until this row exists, so another batch can take it in
    between. A collision here is caught on the UNIQUE index and re-rolled
    rather than raised: losing that race must not cost the user their dispatch.
    The re-roll is the one case where a sent subject differs from the previewed
    one, and it differs only inside the marker. Passing None mints one outright,
    for any caller with no preview step to mint it earlier."""
    with transaksi(conn) as c:
        for percobaan in range(MAKS_UNDIAN_KODE):
            calon = kode if (kode and percobaan == 0) else core_kode.buat_kode()
            try:
                # SAVEPOINT rather than a bare retry: the caller may have handed
                # us their connection mid-transaction — Phase A of a send does
                # exactly that — and a failed INSERT would otherwise poison it.
                # This unwinds the one statement and leaves the rest standing.
                c.execute("SAVEPOINT undian_kode")
                cur = c.execute(
                    """INSERT INTO requests (event_id, category_id, kebutuhan, deadline,
                                             pengirim_nama, subject_template,
                                             body_template, kode)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event_id, category_id, brief.get("kebutuhan", ""),
                        brief.get("deadline", ""), brief.get("pengirim_nama", ""),
                        subject_template, body_template, calon,
                    ),
                )
            except sqlite3.IntegrityError:
                c.execute("ROLLBACK TO undian_kode")
                c.execute("RELEASE undian_kode")
                continue
            c.execute("RELEASE undian_kode")
            return cur.lastrowid

    raise RuntimeError(
        f"no free RFQ code found in {MAKS_UNDIAN_KODE} attempts"
    )


def create_outbox_rows(request_id: int, vendor_ids, subjects: dict | None = None,
                       conn: sqlite3.Connection | None = None) -> int:
    """One draft row per vendor. email_tujuan is snapshotted from the vendor row
    now, so later edits to the vendor never rewrite history. A duplicate
    (request_id, vendor_id) raises IntegrityError — the last double-send guard."""
    subjects = subjects or {}
    ditulis = 0
    with transaksi(conn) as c:
        for vendor_id in vendor_ids:
            vendor = c.execute(
                "SELECT email FROM vendors WHERE id = ?", (vendor_id,)
            ).fetchone()
            if vendor is None:
                continue
            c.execute(
                """INSERT INTO outbox (request_id, vendor_id, email_tujuan, subject, status)
                   VALUES (?, ?, ?, ?, 'draft')""",
                (request_id, vendor_id, vendor["email"], subjects.get(vendor_id, "")),
            )
            ditulis += 1
    return ditulis


def list_draft_rows(request_id: int) -> list[sqlite3.Row]:
    """Draft rows plus what the renderer needs for each vendor."""
    with closing(get_conn()) as conn:
        return conn.execute(
            """SELECT o.id, o.vendor_id, o.email_tujuan, o.subject,
                      v.nama_pt, v.pic_nama, v.kategori
                 FROM outbox o
                 JOIN v_vendor_lengkap v ON v.id = o.vendor_id
                WHERE o.request_id = ? AND o.status = 'draft'
                ORDER BY o.id""",
            (request_id,),
        ).fetchall()


def mark_sent(outbox_id: int, message_id: str) -> None:
    """Only a draft row becomes sent."""
    with closing(get_conn()) as conn:
        conn.execute(
            """UPDATE outbox
                  SET status = 'sent', message_id = ?, error_msg = NULL,
                      sent_at = datetime('now', 'localtime')
                WHERE id = ? AND status = 'draft'""",
            (message_id, outbox_id),
        )
        conn.commit()


def mark_failed(outbox_id: int, error_msg: str) -> None:
    """Only a draft row becomes failed."""
    with closing(get_conn()) as conn:
        conn.execute(
            "UPDATE outbox SET status = 'failed', error_msg = ? WHERE id = ? AND status = 'draft'",
            (error_msg, outbox_id),
        )
        conn.commit()


def progress(request_id: int) -> dict:
    """Counted in SQL every time. Never derived from in-flight state.

    `replied` counts VENDORS, not replies: a vendor who sends a quote and then
    a revision has replied once for the purpose of "5 of 8 vendors have
    replied". Both callers of _progress.html already call this, so the summary
    line costs neither of them a new context key."""
    with closing(get_conn()) as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS total,
                      COALESCE(SUM(status = 'sent'), 0)   AS sent,
                      COALESCE(SUM(status = 'failed'), 0) AS failed,
                      COALESCE(SUM(status = 'draft'), 0)  AS draft
                 FROM outbox WHERE request_id = ?""",
            (request_id,),
        ).fetchone()
        # auto_reply = 0 is what keeps an out-of-office from counting as an
        # answer. It arrives from the vendor's own address and matches the
        # exact outbox row, so nothing earlier in the pipeline can exclude it —
        # this count is the right place, because the row is still worth
        # storing and showing.
        balas = conn.execute(
            """SELECT COUNT(DISTINCT vendor_id) AS n FROM inbox
                WHERE request_id = ? AND vendor_id IS NOT NULL
                  AND auto_reply = 0""",
            (request_id,),
        ).fetchone()

    return {
        "total": row["total"],
        "sent": row["sent"],
        "failed": row["failed"],
        "draft": row["draft"],
        "replied": balas["n"],
        "selesai": row["total"] > 0 and row["draft"] == 0,
    }


def list_requests() -> list[sqlite3.Row]:
    """Batches newest first, with their outbox tallies. judul_acara and
    tanggal_acara come from the event, so callers read the same keys they
    always did."""
    with closing(get_conn()) as conn:
        return conn.execute(
            """SELECT r.id, r.event_id, e.judul_acara, e.tanggal_acara,
                      c.nama AS kategori, r.created_at,
                      -- Window functions run after GROUP BY, so these count
                      -- batches per event, not outbox rows.
                      COUNT(*)     OVER (PARTITION BY r.event_id) AS event_batches,
                      ROW_NUMBER() OVER (PARTITION BY r.event_id
                                             ORDER BY r.id)       AS batch_ke,
                      COUNT(o.id) AS total,
                      COALESCE(SUM(o.status = 'sent'), 0)   AS sent,
                      COALESCE(SUM(o.status = 'failed'), 0) AS failed,
                      COALESCE(SUM(o.status = 'draft'), 0)  AS draft
                 FROM requests r
                 JOIN events e ON e.id = r.event_id
                 JOIN categories c ON c.id = r.category_id
                 LEFT JOIN outbox o ON o.request_id = r.id
                GROUP BY r.id
                ORDER BY r.id DESC"""
        ).fetchall()


def request_detail(request_id: int) -> sqlite3.Row | None:
    """One batch, templates included, with its event's fields grafted on so
    the row can go straight to core.renderer or core.dokumen."""
    with closing(get_conn()) as conn:
        return conn.execute(
            SQL_REQUEST_WITH_EVENT + " WHERE r.id = ?", (request_id,)
        ).fetchone()


def list_outbox_rows(request_id: int) -> list[sqlite3.Row]:
    """Per-vendor status for the tracker detail page."""
    with closing(get_conn()) as conn:
        return conn.execute(
            """SELECT o.id, o.vendor_id, o.email_tujuan, o.subject, o.status,
                      o.error_msg, o.message_id, o.sent_at,
                      v.nama_pt, v.kategori
                 FROM outbox o
                 JOIN v_vendor_lengkap v ON v.id = o.vendor_id
                WHERE o.request_id = ?
                ORDER BY o.id""",
            (request_id,),
        ).fetchall()


def request_has_dispatched(request_id: int) -> bool:
    """True once any row has left draft. Blocks a second send of the same request."""
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM outbox WHERE request_id = ? AND status <> 'draft'",
            (request_id,),
        ).fetchone()
    return row["n"] > 0


def reset_failed_to_draft(request_id: int) -> int:
    """Retry. The status filter is what keeps a sent row from ever reverting."""
    with closing(get_conn()) as conn:
        cur = conn.execute(
            "UPDATE outbox SET status = 'draft', error_msg = NULL WHERE request_id = ? AND status = 'failed'",
            (request_id,),
        )
        conn.commit()
        return cur.rowcount


def next_nomor(conn: sqlite3.Connection, bulan: int, tahun: int) -> str:
    """The next free nomor for tahun.

    Takes the caller's connection so the read sits inside the transaction that
    consumes it. The sequence is derived rather than stored: the highest number
    already issued this year, plus one. Rows from other years never enter the
    max, so the count restarts at 001 in January.
    """
    rows = conn.execute(
        "SELECT nomor FROM spk WHERE nomor LIKE ?", (penomoran.pola_tahun(tahun),)
    ).fetchall()

    tertinggi = max(
        (penomoran.urut_dari(r["nomor"], tahun) for r in rows), default=0
    )
    return penomoran.format_nomor(tertinggi + 1, bulan, tahun)


def create_spk(request_id: int, vendor_id: int, harga: int,
               lingkup_kerja: str, termin: str) -> int:
    """Issue one SPK. Returns the new id.

    BEGIN IMMEDIATE takes the write lock before the sequence is read, so the
    read and the insert that consumes it are one transaction — two SPK issued
    at the same moment cannot claim the same nomor. UNIQUE(nomor) is the
    backstop.

    tanggal_terbit is passed in rather than defaulted by SQLite, and the same
    date supplies the month and year of the nomor — one reading of the clock,
    so the printed date and the number can never disagree.

    A second SPK for the same (request_id, vendor_id) raises IntegrityError.
    Re-issuing goes through update_spk; it is never a new row.
    """
    terbit = date.today()
    with closing(get_conn()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        nomor = next_nomor(conn, terbit.month, terbit.year)
        cur = conn.execute(
            """INSERT INTO spk (request_id, vendor_id, nomor, harga,
                                lingkup_kerja, termin, tanggal_terbit)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (request_id, vendor_id, nomor, harga, lingkup_kerja, termin,
             terbit.isoformat()),
        )
        conn.commit()
        return cur.lastrowid


# SPK rows reach core.dokumen needing the event's title, date and location.
# They are two joins away now, so the path is written once here rather than
# left to each caller to remember.
SQL_SPK_WITH_EVENT = """
    SELECT s.*, e.judul_acara, e.tanggal_acara, e.lokasi, r.pengirim_nama
      FROM spk s
      JOIN requests r ON r.id = s.request_id
      JOIN events e ON e.id = r.event_id
"""


def get_spk(request_id: int, vendor_id: int) -> sqlite3.Row | None:
    """The SPK for one vendor on one batch, or None. The pair is unique, so
    this is at most one row. Carries the document fields through the join."""
    with closing(get_conn()) as conn:
        return conn.execute(
            SQL_SPK_WITH_EVENT + " WHERE s.request_id = ? AND s.vendor_id = ?",
            (request_id, vendor_id),
        ).fetchone()


def update_spk(spk_id: int, harga: int, lingkup_kerja: str, termin: str) -> None:
    """Re-issue: the editable fields only. nomor and tanggal_terbit are left
    out of the statement deliberately — a document reprinted next month still
    carries the number and date it was issued under."""
    with closing(get_conn()) as conn:
        conn.execute(
            "UPDATE spk SET harga = ?, lingkup_kerja = ?, termin = ? WHERE id = ?",
            (harga, lingkup_kerja, termin, spk_id),
        )
        conn.commit()


def list_spk_for_request(request_id: int) -> list[sqlite3.Row]:
    """Every SPK issued against one batch, in issue order."""
    with closing(get_conn()) as conn:
        return conn.execute(
            SQL_SPK_WITH_EVENT + " WHERE s.request_id = ? ORDER BY s.id",
            (request_id,),
        ).fetchall()


def spk_by_vendor(request_id: int) -> dict:
    """vendor_id -> SPK row, for the per-vendor action in the outbox table."""
    return {r["vendor_id"]: r for r in list_spk_for_request(request_id)}


def get_rundown(event_id: int) -> sqlite3.Row | None:
    """The rundown for one event, or None. At most one exists — the column is
    UNIQUE — and that is the point of hanging it off events: an event with two
    quote rounds still has exactly one running order."""
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM rundown WHERE event_id = ?", (event_id,)
        ).fetchone()


def create_rundown(event_id: int, jam_mulai: str,
                   batas_venue: str | None) -> int:
    """Start a rundown for one event. Returns the new id. A second one for the
    same event raises IntegrityError — UNIQUE(event_id)."""
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """INSERT INTO rundown (event_id, jam_mulai, batas_venue)
               VALUES (?, ?, ?)""",
            (event_id, jam_mulai, batas_venue or None),
        )
        conn.commit()
        return cur.lastrowid


def update_rundown(rundown_id: int, jam_mulai: str,
                   batas_venue: str | None) -> None:
    """Overwrite the start time and venue limit. The items are untouched:
    every displayed time is derived, so moving jam_mulai reschedules the
    whole rundown without rewriting a single item row."""
    with closing(get_conn()) as conn:
        conn.execute(
            "UPDATE rundown SET jam_mulai = ?, batas_venue = ? WHERE id = ?",
            (jam_mulai, batas_venue or None, rundown_id),
        )
        conn.commit()


def list_items(rundown_id: int) -> list[sqlite3.Row]:
    """Items in running order. urutan is contiguous from 1, so this order is
    also the position shown to the user."""
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM rundown_item WHERE rundown_id = ? ORDER BY urutan",
            (rundown_id,),
        ).fetchall()


def add_item(rundown_id: int, kegiatan: str, durasi_menit: int,
             pic: str, catatan: str) -> int:
    """Append one item at the end. Returns the new id.

    Reading MAX(urutan) and inserting share one transaction, so two items
    added at the same moment cannot claim the same position — the UNIQUE is
    the backstop."""
    with closing(get_conn()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        berikutnya = conn.execute(
            "SELECT COALESCE(MAX(urutan), 0) + 1 FROM rundown_item WHERE rundown_id = ?",
            (rundown_id,),
        ).fetchone()[0]
        cur = conn.execute(
            """INSERT INTO rundown_item
                      (rundown_id, urutan, kegiatan, durasi_menit, pic, catatan)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (rundown_id, berikutnya, kegiatan, durasi_menit, pic, catatan),
        )
        conn.commit()
        return cur.lastrowid


def update_item(item_id: int, kegiatan: str, durasi_menit: int,
                pic: str, catatan: str) -> None:
    """Overwrite one item's content. urutan is not editable here — ordering
    moves through move_item so the contiguity rule stays in one place."""
    with closing(get_conn()) as conn:
        conn.execute(
            """UPDATE rundown_item
                  SET kegiatan = ?, durasi_menit = ?, pic = ?, catatan = ?
                WHERE id = ?""",
            (kegiatan, durasi_menit, pic, catatan, item_id),
        )
        conn.commit()


def delete_item(item_id: int) -> bool:
    """Remove one item and close the gap it leaves, so urutan stays 1..n.

    Returns True when a row was removed, False when the id does not exist,
    so a route can 404 without looking the item up first.

    The shift runs in two passes through negative values. UNIQUE(rundown_id,
    urutan) would otherwise fire mid-statement when a row moves onto a
    position its neighbour has not vacated yet; no real urutan is negative,
    so the parking range is always free."""
    with closing(get_conn()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        baris = conn.execute(
            "SELECT rundown_id, urutan FROM rundown_item WHERE id = ?", (item_id,)
        ).fetchone()
        if baris is None:
            conn.commit()
            return False

        conn.execute("DELETE FROM rundown_item WHERE id = ?", (item_id,))
        conn.execute(
            """UPDATE rundown_item SET urutan = -(urutan - 1)
                WHERE rundown_id = ? AND urutan > ?""",
            (baris["rundown_id"], baris["urutan"]),
        )
        conn.execute(
            "UPDATE rundown_item SET urutan = -urutan WHERE rundown_id = ? AND urutan < 0",
            (baris["rundown_id"],),
        )
        conn.commit()
        return True


def move_item(item_id: int, direction: str) -> bool:
    """Swap one item with its neighbour. direction is "up" or "down".

    Returns True when the swap happened, False when nothing moved: an
    unknown id, an unknown direction, or the first item asked to go up and
    the last asked to go down. A route can treat False as "no change" and
    decide for itself whether that is a 404 or a redirect.

    The swap parks one row at urutan 0 first, for the same reason
    delete_item uses negatives: the pair would otherwise collide on UNIQUE
    halfway through."""
    if direction not in ("up", "down"):
        return False

    with closing(get_conn()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        baris = conn.execute(
            "SELECT rundown_id, urutan FROM rundown_item WHERE id = ?", (item_id,)
        ).fetchone()
        if baris is None:
            conn.commit()
            return False

        tetangga_urutan = baris["urutan"] + (-1 if direction == "up" else 1)
        tetangga = conn.execute(
            "SELECT id FROM rundown_item WHERE rundown_id = ? AND urutan = ?",
            (baris["rundown_id"], tetangga_urutan),
        ).fetchone()
        # No neighbour means first item moving up or last moving down.
        if tetangga is None:
            conn.commit()
            return False

        conn.execute("UPDATE rundown_item SET urutan = 0 WHERE id = ?", (item_id,))
        conn.execute(
            "UPDATE rundown_item SET urutan = ? WHERE id = ?",
            (baris["urutan"], tetangga["id"]),
        )
        conn.execute(
            "UPDATE rundown_item SET urutan = ? WHERE id = ?",
            (tetangga_urutan, item_id),
        )
        conn.commit()
        return True


# Sponsors need their event's title, date and location on the printed sheet, so
# the join is written once here rather than left to each caller.
SQL_SPONSOR_WITH_EVENT = """
    SELECT s.*, e.judul_acara, e.tanggal_acara, e.lokasi, e.zona
      FROM sponsors s
      JOIN events e ON e.id = s.event_id
"""


def list_sponsors(event_id: int | None = None) -> list[sqlite3.Row]:
    """Sponsors with their event and their package tallied up.

    event_id None means every sponsor, newest event first and alphabetical
    inside it — which is the grouping the list page renders. Passing an id
    narrows to one event.

    The two sums come from the snapshot columns, never from items, so a row
    here reports what the package was agreed at. COALESCE because a sponsor
    with no lines yet still has to appear, at zero."""
    # Written out rather than built on SQL_SPONSOR_WITH_EVENT: this one needs a
    # LEFT JOIN and a GROUP BY, and the shared string is the plain row shape.
    sql = """
        SELECT s.*, e.judul_acara, e.tanggal_acara, e.lokasi, e.zona,
               COUNT(si.id) AS baris,
               COALESCE(SUM(si.qty * si.cost), 0)  AS cost_pakai,
               COALESCE(SUM(si.qty * si.value), 0) AS value_total
          FROM sponsors s
          JOIN events e ON e.id = s.event_id
          LEFT JOIN sponsor_item si ON si.sponsor_id = s.id
    """
    params: list[object] = []
    if event_id is not None:
        sql += " WHERE s.event_id = ?"
        params.append(event_id)
    sql += " GROUP BY s.id ORDER BY s.event_id DESC, s.nama_pt"

    with closing(get_conn()) as conn:
        return conn.execute(sql, params).fetchall()


def get_sponsor(sponsor_id: int) -> sqlite3.Row | None:
    """One sponsor by id, or None, carrying its event's fields through."""
    with closing(get_conn()) as conn:
        return conn.execute(
            SQL_SPONSOR_WITH_EVENT + " WHERE s.id = ?", (sponsor_id,)
        ).fetchone()


def sponsor_name_exists(event_id: int, nama_pt: str,
                        exclude_id: int | None = None) -> bool:
    """The UNIQUE(event_id, nama_pt) is the real guard; this only exists so the
    form can say which name collided. Scoped to the event — the same company
    may sponsor a different event. exclude_id lets an edit keep its own name."""
    sql = """SELECT 1 FROM sponsors
              WHERE event_id = ? AND nama_pt = ? COLLATE NOCASE"""
    params: list[object] = [event_id, nama_pt]
    if exclude_id is not None:
        sql += " AND id <> ?"
        params.append(exclude_id)

    with closing(get_conn()) as conn:
        return conn.execute(sql, params).fetchone() is not None


def create_sponsor(event_id: int, nama_pt: str, kontribusi: int,
                   persen_budget: int, catatan: str) -> int:
    """Insert one sponsor. Returns the new id."""
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """INSERT INTO sponsors
                      (event_id, nama_pt, kontribusi, persen_budget, catatan)
               VALUES (?, ?, ?, ?, ?)""",
            (event_id, nama_pt, kontribusi, persen_budget, catatan),
        )
        conn.commit()
        return cur.lastrowid


def update_sponsor(sponsor_id: int, nama_pt: str, kontribusi: int,
                   persen_budget: int, catatan: str) -> None:
    """Overwrite one sponsor's own fields. event_id is left out deliberately:
    moving a sponsor between events would carry a package priced for one day
    onto another, and the package lines are what make that wrong."""
    with closing(get_conn()) as conn:
        conn.execute(
            """UPDATE sponsors
                  SET nama_pt = ?, kontribusi = ?, persen_budget = ?, catatan = ?
                WHERE id = ?""",
            (nama_pt, kontribusi, persen_budget, catatan, sponsor_id),
        )
        conn.commit()


def list_sponsor_items(sponsor_id: int) -> list[sqlite3.Row]:
    """One sponsor's package lines, in the order they were added.

    The join to items supplies the name and unit only — display text, which is
    fine to follow the catalog. cost and value come from sponsor_item and are
    never read from items here: those are the snapshot, and the whole point is
    that they do not move when the catalog does.

    zona_pct rides along so the page can tell a line priced under the event's
    current zone from one priced under an older zone. It is reported, never
    acted on."""
    with closing(get_conn()) as conn:
        return conn.execute(
            """SELECT si.id, si.item_id, si.qty, si.cost, si.value, si.zona_pct,
                      i.nama, i.satuan
                 FROM sponsor_item si
                 JOIN items i ON i.id = si.item_id
                WHERE si.sponsor_id = ?
                ORDER BY si.id""",
            (sponsor_id,),
        ).fetchall()


def items_available_for_sponsor(sponsor_id: int) -> list[sqlite3.Row]:
    """Active catalog items this sponsor does not already have a line for.

    Archived items are out because the picker is for building a package now.
    An item already on the package is out because the quantity on the line
    itself is how you get more of it.

    Each row carries cost_zona and value_zona: the catalog base with this
    event's zone surcharge already applied, which is what the line will
    actually be priced at. The picker must offer the real number — a sponsor
    shown the base and charged the surcharge sees the difference as a defect.
    Returns dicts rather than Rows because of those two derived keys; every
    caller reads by name, and Jinja treats the two the same."""
    pct = config.zona_pct(zona_sponsor(sponsor_id) or config.ZONA_DEFAULT)
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """SELECT * FROM items
                WHERE aktif = 1
                  AND id NOT IN (SELECT item_id FROM sponsor_item
                                  WHERE sponsor_id = ?)
                ORDER BY nama""",
            (sponsor_id,),
        ).fetchall()

    hasil = []
    for r in rows:
        d = dict(r)
        d["cost_zona"] = harga_zona(r["cost"], pct)
        d["value_zona"] = harga_zona(r["value"], pct)
        hasil.append(d)
    return hasil


def harga_zona(base: int, pct: int) -> int:
    """One catalog amount with a zone surcharge applied. Whole rupiah in,
    whole rupiah out, and no float touches it at any point.

    (base * (100 + pct) + 50) // 100 rounds half up on a non-negative amount:
    multiplying first keeps full precision, and the + 50 is what carries a
    half rupiah upward instead of truncating it away. One expression, so there
    is no intermediate value that could be rounded twice.

    The rate is never written here — it comes from config.ZONA, which is the
    only place the percentages exist."""
    return (base * (100 + pct) + 50) // 100


def zona_sponsor(sponsor_id: int) -> str | None:
    """The zone key of the event this sponsor belongs to, or None when the
    sponsor does not exist. The zone lives on the event, never on the sponsor:
    it is a property of where the thing happens."""
    with closing(get_conn()) as conn:
        row = conn.execute(
            """SELECT e.zona FROM sponsors s
                 JOIN events e ON e.id = s.event_id
                WHERE s.id = ?""",
            (sponsor_id,),
        ).fetchone()
    return row["zona"] if row else None


def add_sponsor_item(sponsor_id: int, item_id: int, qty: int = 1) -> int | None:
    """Add one line, snapshotting the catalog price into it.

    Returns the line id, or None when the item does not exist. The read of
    items and the insert share one transaction, so the price written is the one
    that was on the catalog at this instant and cannot be half-updated by a
    concurrent edit. After this the line never consults items for money again.

    The zone surcharge is applied HERE, at insert, and frozen into the row
    alongside the zona_pct that produced it. Reading the event's zone, the
    catalog price and writing the line all happen in one transaction, so the
    rate stored is the rate that was in force at that instant.

    Adding an item the sponsor already has increments the line that is there
    rather than raising: UNIQUE(sponsor_id, item_id) makes it a conflict, and
    DO UPDATE adds to qty. cost, value and zona_pct are deliberately absent
    from the SET list — an existing line keeps the snapshot it was created
    with, however the catalog has been repriced or the event moved zone since.
    Invariant 15."""
    with closing(get_conn()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        item = conn.execute(
            "SELECT cost, value FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        if item is None:
            conn.commit()
            return None
        # Read inside the same transaction as the price it modifies.
        acara = conn.execute(
            """SELECT e.zona FROM sponsors s
                 JOIN events e ON e.id = s.event_id
                WHERE s.id = ?""",
            (sponsor_id,),
        ).fetchone()
        if acara is None:
            conn.commit()
            return None
        pct = config.zona_pct(acara["zona"])
        conn.execute(
            """INSERT INTO sponsor_item
                      (sponsor_id, item_id, qty, cost, value, zona_pct)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(sponsor_id, item_id)
               DO UPDATE SET qty = qty + excluded.qty""",
            (sponsor_id, item_id, qty,
             harga_zona(item["cost"], pct), harga_zona(item["value"], pct), pct),
        )
        # Read back rather than lastrowid: after DO UPDATE that is the rowid of
        # the conflicting insert attempt, not of the row that actually moved.
        baris = conn.execute(
            "SELECT id FROM sponsor_item WHERE sponsor_id = ? AND item_id = ?",
            (sponsor_id, item_id),
        ).fetchone()
        conn.commit()
        return baris["id"]


def get_sponsor_item(line_id: int) -> sqlite3.Row | None:
    """One package line by id, or None. Carries sponsor_id, so a route can
    check the line actually belongs to the sponsor in its own URL."""
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM sponsor_item WHERE id = ?", (line_id,)
        ).fetchone()


def bump_sponsor_item_qty(line_id: int, delta: int) -> bool:
    """Move one line's qty by delta. Returns True when it moved.

    `qty = qty + ?` in SQL, not a read-then-write: two fast clicks on + are two
    increments, and neither can lose the other. The `qty + ? >= 1` guard is what
    turns a decrement past the floor into a no-op rather than a
    CHECK(qty > 0) failure — this never deletes a line, remove_sponsor_item is
    the only thing that does.

    cost and value are not in the SET list: adjusting a quantity must not
    re-read the catalog. Invariant 15."""
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """UPDATE sponsor_item SET qty = qty + :d
                WHERE id = :id AND qty + :d >= 1""",
            {"d": delta, "id": line_id},
        )
        conn.commit()
        return cur.rowcount > 0


def set_sponsor_item_qty(line_id: int, qty: int) -> bool:
    """Set one line's qty outright — what the typed box sends. Returns True
    when a row was written.

    The caller clamps; anything below 1 is refused here as well, so a
    hand-posted zero cannot reach CHECK(qty > 0). cost and value untouched,
    for the same reason as bump."""
    if qty < 1:
        return False
    with closing(get_conn()) as conn:
        cur = conn.execute(
            "UPDATE sponsor_item SET qty = ? WHERE id = ?", (qty, line_id)
        )
        conn.commit()
        return cur.rowcount > 0


def remove_sponsor_item(line_id: int) -> bool:
    """Delete one line. Returns True when a row went, False when the id is
    unknown, so a route can 404 without looking it up first. Lines are the one
    thing here that is genuinely deleted — an unwanted line is a mistake being
    corrected, not a record worth keeping."""
    with closing(get_conn()) as conn:
        cur = conn.execute("DELETE FROM sponsor_item WHERE id = ?", (line_id,))
        conn.commit()
        return cur.rowcount > 0


def sponsor_totals(sponsor_id: int) -> dict:
    """The two sums the summary strip is built from, counted in SQL every time.

    Both read the snapshot columns. Everything else on the strip — budget, what
    is left, the multiple — is arithmetic on these two plus the sponsor's own
    kontribusi, and is worked out at render rather than stored."""
    with closing(get_conn()) as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS baris,
                      COALESCE(SUM(qty * cost), 0)  AS cost_pakai,
                      COALESCE(SUM(qty * value), 0) AS value_total
                 FROM sponsor_item WHERE sponsor_id = ?""",
            (sponsor_id,),
        ).fetchone()

    return {"baris": row["baris"], "cost_pakai": row["cost_pakai"],
            "value_total": row["value_total"]}


# ---------------------------------------------------------------------------
# Replies. Everything below reads or writes inbox, inbox_attachment or
# inbox_check.
# ---------------------------------------------------------------------------


def last_check() -> sqlite3.Row | None:
    """The most recent check run, successful or not, or None if none ever ran.

    None means NEVER CHECKED, and the interface has to say that rather than
    render a zero — "nobody replied" and "the check has not run" look identical
    otherwise, and only one of them is worth acting on."""
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM inbox_check ORDER BY id DESC LIMIT 1"
        ).fetchone()


def watermark() -> str | None:
    """Where the next check resumes from: the start of the last SUCCESSFUL run.

    Successful only. A failed run must not advance the watermark, or the day it
    failed on is skipped forever and the failure turns into silent data loss
    instead of a banner."""
    with closing(get_conn()) as conn:
        row = conn.execute(
            "SELECT MAX(started_at) AS m FROM inbox_check WHERE ok = 1"
        ).fetchone()
    return row["m"] if row and row["m"] else None


def record_check(started_at: str, ok: bool, error_msg: str | None,
                 examined: int, kept: int) -> int:
    """Log one check run. error_msg is the RAW exception string — translation
    happens on display, so reworded messages need no migration."""
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """INSERT INTO inbox_check (started_at, ok, error_msg, examined, kept)
               VALUES (?, ?, ?, ?, ?)""",
            (started_at, 1 if ok else 0, error_msg, examined, kept),
        )
        conn.commit()
        return cur.lastrowid


def vendor_emails() -> dict:
    """{normalised email: vendor_id} for the gate.

    Every vendor, not only active ones: an archived vendor answering an RFQ
    that went out before they were archived is still a real reply, and dropping
    it at the door would be silent. Lowercased here so the gate compares like
    with like — the column is typed by hand and inconsistently cased.

    Later duplicates lose. Two vendors sharing an address is a data problem the
    reply check should not try to adjudicate; it attributes to the first."""
    with closing(get_conn()) as conn:
        rows = conn.execute(
            "SELECT id, email FROM vendors WHERE email <> '' ORDER BY id"
        ).fetchall()
    hasil: dict[str, int] = {}
    for r in rows:
        kunci = (r["email"] or "").strip().lower()
        if kunci and kunci not in hasil:
            hasil[kunci] = r["id"]
    return hasil


def outbox_by_message_id(message_ids) -> sqlite3.Row | None:
    """The outbox row one of these Message-IDs was sent as, or None. Tier 1.

    The ids come from a reply's In-Reply-To and References, in that order, and
    the first hit wins — In-Reply-To is the direct parent.

    `message_id LIKE '<%>'` excludes the four legacy rows that stored the
    literal string "dry-run" before every send minted its own id. Without it
    one lookup would match all of them at once. Nothing repairs those rows:
    they are history, and no reply can arrive against a mail never sent."""
    ids = [m for m in (message_ids or []) if m]
    if not ids:
        return None
    with closing(get_conn()) as conn:
        for m in ids:
            row = conn.execute(
                """SELECT o.*, r.kode
                     FROM outbox o
                     JOIN requests r ON r.id = o.request_id
                    WHERE o.message_id = ? AND o.message_id LIKE '<%>'""",
                (m,),
            ).fetchone()
            if row is not None:
                return row
    return None


def outbox_row_for(request_id: int, vendor_id: int) -> sqlite3.Row | None:
    """One vendor's row in one batch, or None. Tier 2's second half: the code
    names the batch, and this is what turns that into a per-vendor match."""
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM outbox WHERE request_id = ? AND vendor_id = ?",
            (request_id, vendor_id),
        ).fetchone()


def inbox_exists(message_id: str) -> bool:
    """Have we already stored this message? The UNIQUE on inbox.message_id is
    the real guard; this lets the check skip the parse and the attachment
    writes for a message it has seen, which is most of them on every run."""
    if not message_id:
        return False
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT 1 FROM inbox WHERE message_id = ?", (message_id,)
        ).fetchone() is not None


def create_inbox(pesan: dict, tier: int, request_id: int | None,
                 outbox_id: int | None, vendor_id: int | None) -> int | None:
    """Store one matched reply. Returns the new id, or None if it was already
    stored — a duplicate is the expected case, not an error, because every
    check re-reads the whole day of the last one."""
    with closing(get_conn()) as conn:
        try:
            cur = conn.execute(
                """INSERT INTO inbox (message_id, from_email, from_nama, subject,
                                      received_at, body, tier,
                                      request_id, outbox_id, vendor_id,
                                      auto_reply)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pesan["message_id"], pesan["from_email"], pesan["from_nama"],
                 pesan["subject"], pesan["received_at"], pesan["body"], tier,
                 request_id, outbox_id, vendor_id,
                 1 if pesan.get("otomatis") else 0),
            )
            conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def create_inbox_attachment(inbox_id: int, filename: str, content_type: str,
                            size_bytes: int, stored_name: str) -> int:
    """Record one saved attachment. The bytes are already on disk; this is the
    row that makes them findable."""
    with closing(get_conn()) as conn:
        cur = conn.execute(
            """INSERT INTO inbox_attachment
                      (inbox_id, filename, content_type, size_bytes, stored_name)
               VALUES (?, ?, ?, ?, ?)""",
            (inbox_id, filename, content_type, size_bytes, stored_name),
        )
        conn.commit()
        return cur.lastrowid


def count_needs_attention() -> int:
    """The nav badge: incoming mail not yet dealt with.

    Two populations, and the difference matters. An ATTACHED reply counts until
    it is read. An UNASSIGNED one counts until it is assigned, read or not,
    because reading it does not put it anywhere.

    Tier 4 is excluded on purpose. Unmatched mail is not "not yet dealt with",
    it is mail we could not place, and a number that never goes down stops
    being read at all.

    Auto-replies are excluded for a different reason: an out-of-office is not
    something anyone has to act on. Counting it would put a number on the nav
    that means "a mail server answered", which trains people to ignore the
    badge — and a badge that gets ignored is worse than no badge."""
    with closing(get_conn()) as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS n FROM inbox
                WHERE auto_reply = 0
                  AND ((tier IN (1, 2) AND read_at IS NULL)
                       OR (tier = 3 AND request_id IS NULL))"""
        ).fetchone()
    return row["n"]


def replies_by_vendor(request_id: int) -> dict:
    """{vendor_id: [reply rows]} for one batch's outbox table, newest first.

    Keyed by vendor rather than by outbox row so a reply attached to the batch
    but not to a specific row is still reachable — tier 2 without a sender
    match resolves the batch only."""
    with closing(get_conn()) as conn:
        rows = conn.execute(
            """SELECT * FROM inbox
                WHERE request_id = ? AND vendor_id IS NOT NULL
                ORDER BY received_at DESC, id DESC""",
            (request_id,),
        ).fetchall()
    hasil: dict[int, list] = {}
    for r in rows:
        hasil.setdefault(r["vendor_id"], []).append(r)
    return hasil


def get_reply(reply_id: int) -> sqlite3.Row | None:
    """One reply with the names its page needs, or None."""
    with closing(get_conn()) as conn:
        return conn.execute(
            """SELECT i.*, v.nama_pt, e.judul_acara, c.nama AS kategori
                 FROM inbox i
                 LEFT JOIN vendors v ON v.id = i.vendor_id
                 LEFT JOIN requests r ON r.id = i.request_id
                 LEFT JOIN events e ON e.id = r.event_id
                 LEFT JOIN categories c ON c.id = r.category_id
                WHERE i.id = ?""",
            (reply_id,),
        ).fetchone()


def list_attachments(reply_id: int) -> list[sqlite3.Row]:
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM inbox_attachment WHERE inbox_id = ? ORDER BY id",
            (reply_id,),
        ).fetchall()


def get_attachment(attachment_id: int) -> sqlite3.Row | None:
    """One attachment row, carrying its inbox_id so a route can check the file
    actually belongs to the reply in its own URL."""
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM inbox_attachment WHERE id = ?", (attachment_id,)
        ).fetchone()


def mark_reply_read(reply_id: int) -> None:
    """Stamp read_at, once. The `read_at IS NULL` guard keeps the FIRST time it
    was opened rather than overwriting with the most recent — when it was seen
    is the useful fact, not when it was last looked at."""
    with closing(get_conn()) as conn:
        conn.execute(
            """UPDATE inbox SET read_at = datetime('now', 'localtime')
                WHERE id = ? AND read_at IS NULL""",
            (reply_id,),
        )
        conn.commit()


def assign_reply(reply_id: int, request_id: int) -> bool:
    """Attach a held reply to a batch by hand. Returns True when it moved.

    tier IS NOT IN THE SET LIST, and that is the rule rather than an oversight.
    tier records how the message was matched, which is history: a reply that
    could only be matched by sender stays a tier 3 forever, and "needs
    assigning" is `tier = 3 AND request_id IS NULL` rather than a status that
    flips. Without that, a hand-assigned reply is indistinguishable from one
    the ladder resolved, and the honest answer looks like a bug.

    outbox_id is filled in the same statement when the vendor is actually in
    the chosen batch, so the reply lands on the right row of the outbox table
    rather than only on the batch."""
    with closing(get_conn()) as conn:
        conn.execute("BEGIN IMMEDIATE")
        baris = conn.execute(
            "SELECT vendor_id, request_id FROM inbox WHERE id = ?", (reply_id,)
        ).fetchone()
        if baris is None or baris["request_id"] is not None:
            # Already assigned, or gone. Not an error — two clicks on the same
            # chooser is the ordinary way this happens.
            conn.commit()
            return False

        kotak = conn.execute(
            "SELECT id FROM outbox WHERE request_id = ? AND vendor_id = ?",
            (request_id, baris["vendor_id"]),
        ).fetchone()

        cur = conn.execute(
            "UPDATE inbox SET request_id = ?, outbox_id = ? WHERE id = ?",
            (request_id, kotak["id"] if kotak else None, reply_id),
        )
        conn.commit()
        return cur.rowcount > 0


def list_unassigned() -> list[sqlite3.Row]:
    """Replies held for a human decision: matched to a vendor and nothing else.

    Tier 3 never attaches on its own, and that is the whole point — one vendor
    working two concurrent events cannot be told apart by their address, and
    concurrent events are normal here."""
    with closing(get_conn()) as conn:
        return conn.execute(
            """SELECT i.*, v.nama_pt
                 FROM inbox i
                 LEFT JOIN vendors v ON v.id = i.vendor_id
                WHERE i.tier = 3 AND i.request_id IS NULL
                ORDER BY i.received_at DESC, i.id DESC"""
        ).fetchall()


def list_unmatched() -> list[sqlite3.Row]:
    """Replies that got past the gate and resolved to nothing: a well-formed
    code naming no batch, from an address that is not a vendor. Read-only —
    there is nothing to choose from, so there is no chooser."""
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM inbox WHERE tier = 4 ORDER BY received_at DESC, id DESC"
        ).fetchall()


def batches_for_vendor(vendor_id: int) -> list[sqlite3.Row]:
    """The batches this vendor was actually written to, newest first — the
    options the one-click chooser offers.

    Restricted to batches containing that vendor rather than every batch: the
    chooser exists to resolve which of a vendor's own conversations a reply
    belongs to, and offering batches they were never sent turns a two-item
    decision into a scrolling list."""
    with closing(get_conn()) as conn:
        return conn.execute(
            """SELECT r.id, r.kode, r.created_at, e.judul_acara,
                      e.tanggal_acara, c.nama AS kategori
                 FROM requests r
                 JOIN outbox o ON o.request_id = r.id AND o.vendor_id = ?
                 JOIN events e ON e.id = r.event_id
                 JOIN categories c ON c.id = r.category_id
                ORDER BY r.id DESC""",
            (vendor_id,),
        ).fetchall()


def set_vendor_categories(vendor_id: int, category_ids) -> None:
    """Replace a vendor's category set. Delete and insert share one
    transaction so the vendor is never briefly uncategorised."""
    with closing(get_conn()) as conn:
        conn.execute("DELETE FROM vendor_categories WHERE vendor_id = ?", (vendor_id,))
        conn.executemany(
            "INSERT INTO vendor_categories (vendor_id, category_id) VALUES (?, ?)",
            [(vendor_id, cid) for cid in category_ids],
        )
        conn.commit()
