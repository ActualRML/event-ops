"""SQLite access layer. All SQL lives here."""

import sqlite3
from contextlib import closing, contextmanager

import config


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
    """All categories in seed order. Kirim opens on the first one, so id order
    keeps Tenda in front rather than whatever sorts first alphabetically."""
    with closing(get_conn()) as conn:
        return conn.execute("SELECT id, nama FROM categories ORDER BY id").fetchall()


def list_vendors(kategori: str | None = None, aktif_only: bool = True) -> list[sqlite3.Row]:
    """Vendors with their categories flattened. Filter is by category membership,
    so a vendor listed under several categories matches each of them."""
    clauses = []
    params: list[object] = []

    if aktif_only:
        clauses.append("aktif = 1")

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


def create_request(brief: dict, subject_template: str, body_template: str,
                   conn: sqlite3.Connection | None = None) -> int:
    """Insert the request row. Returns the new id."""
    with transaksi(conn) as c:
        cur = c.execute(
            """INSERT INTO requests (judul_acara, tanggal_acara, lokasi, kebutuhan,
                                     deadline, pengirim_nama, subject_template, body_template)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                brief.get("judul_acara", ""), brief.get("tanggal_acara", ""),
                brief.get("lokasi", ""), brief.get("kebutuhan", ""),
                brief.get("deadline", ""), brief.get("pengirim_nama", ""),
                subject_template, body_template,
            ),
        )
        return cur.lastrowid


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
    """Counted in SQL every time. Never derived from in-flight state."""
    with closing(get_conn()) as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS total,
                      COALESCE(SUM(status = 'sent'), 0)   AS sent,
                      COALESCE(SUM(status = 'failed'), 0) AS failed,
                      COALESCE(SUM(status = 'draft'), 0)  AS draft
                 FROM outbox WHERE request_id = ?""",
            (request_id,),
        ).fetchone()

    return {
        "total": row["total"],
        "sent": row["sent"],
        "failed": row["failed"],
        "draft": row["draft"],
        "selesai": row["total"] > 0 and row["draft"] == 0,
    }


def list_requests() -> list[sqlite3.Row]:
    """Requests newest first, with their outbox tallies."""
    with closing(get_conn()) as conn:
        return conn.execute(
            """SELECT r.id, r.judul_acara, r.tanggal_acara, r.created_at,
                      COUNT(o.id) AS total,
                      COALESCE(SUM(o.status = 'sent'), 0)   AS sent,
                      COALESCE(SUM(o.status = 'failed'), 0) AS failed,
                      COALESCE(SUM(o.status = 'draft'), 0)  AS draft
                 FROM requests r
                 LEFT JOIN outbox o ON o.request_id = r.id
                GROUP BY r.id
                ORDER BY r.id DESC"""
        ).fetchall()


def request_detail(request_id: int) -> sqlite3.Row | None:
    """The request row itself, templates included."""
    with closing(get_conn()) as conn:
        return conn.execute(
            "SELECT * FROM requests WHERE id = ?", (request_id,)
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
