"""SQLite access layer. All SQL lives here."""

import sqlite3
from contextlib import closing

import config


def get_conn() -> sqlite3.Connection:
    """Open a connection. Pragmas are per-connection, so they are set here."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


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
