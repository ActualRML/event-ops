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
    """All categories, alphabetical."""
    with closing(get_conn()) as conn:
        return conn.execute("SELECT id, nama FROM categories ORDER BY nama").fetchall()


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
