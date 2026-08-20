"""Configuration loaded from .env."""

import os

from dotenv import load_dotenv

load_dotenv()

TRUE_VALUES = {"1", "true", "yes", "on", "y", "t"}
FALSE_VALUES = {"0", "false", "no", "off", "n", "f"}


def _get_bool(name: str, default: bool) -> bool:
    """Parse a boolean env var. Falls back to default when unset or unparseable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False
    return default


def _get_int(name: str, default: int) -> int:
    """Parse an int env var. Falls back to default when unset or unparseable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = _get_int("SMTP_PORT", 587)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "")

# Reading mail, for the Message-ID round-trip check and, later, reply matching.
#
# NO NEW CREDENTIALS. IMAP_USER and IMAP_PASS default to the SMTP pair, which
# is the same Gmail account and the same app password — the vars exist only so
# the two CAN be separated, not because they need to be. Gmail wants IMAP
# switched on in its settings; nothing else changes.
#
# DRY_RUN deliberately does NOT gate any of this. DRY_RUN is a send guard —
# invariant 2 is about not opening an SMTP connection — and reading a mailbox
# sends nothing and changes nothing. A demo with the send guard on can still
# show real replies arriving.
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = _get_int("IMAP_PORT", 993)
IMAP_FOLDER = os.getenv("IMAP_FOLDER", "INBOX")
IMAP_USER = os.getenv("IMAP_USER", "") or SMTP_USER
IMAP_PASS = os.getenv("IMAP_PASS", "") or SMTP_PASS

# Most messages examined in one check. The button is synchronous, so this is
# what stops a mailbox with a long history behind the watermark from turning
# one click into a minute of waiting.
IMAP_MAX = _get_int("IMAP_MAX", 200)

# Socket timeout. A hung connection has to become a visible failure rather
# than a page that never returns.
IMAP_TIMEOUT = _get_int("IMAP_TIMEOUT", 20)

# Where attachment bytes go. NOT in the database: one 4 MB quote PDF per reply
# would take the demo db from ~200 KB to tens of MB and every VACUUM INTO
# backup would copy them again, and db.py's habit of SELECT * would pull
# megabytes into a list page by accident.
#
# The cost, and it is written down in CLAUDE.md rather than left implicit:
# db/rfq.db on its own is no longer a complete backup. Copy this directory
# alongside it.
ATTACHMENT_DIR = os.getenv("ATTACHMENT_DIR", "attachments")

# Per-file and per-message caps. Anything over is skipped and counted, never
# silently dropped — a vendor whose 40 MB scan did not save should be able to
# find out why.
ATTACHMENT_MAX_BYTES = _get_int("ATTACHMENT_MAX_BYTES", 10 * 1024 * 1024)
ATTACHMENT_MAX_TOTAL = _get_int("ATTACHMENT_MAX_TOTAL", 25 * 1024 * 1024)

# Extensions we are willing to put on disk. The stored name is built from ids
# plus one of these; anything else lands as .bin. This is not about trusting
# the vendor's filename — that string never reaches a path — it is so a saved
# file opens in the right application.
ATTACHMENT_EXT = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".xlsx", ".xls", ".csv", ".docx", ".doc", ".zip", ".rar", ".txt",
}

DRY_RUN = _get_bool("DRY_RUN", True)
SEND_DELAY_SECONDS = _get_int("SEND_DELAY_SECONDS", 2)

DB_PATH = os.getenv("DB_PATH", "db/rfq.db")


# Zone surcharge on sponsor package lines. Getting an event further out costs
# more to service, and the same percentage is added to what we pay and to what
# the sponsor is charged, so the margin ratio survives the move.
#
# THE ONLY PLACE THE PERCENTAGES ARE WRITTEN. The event form builds its
# dropdown from this mapping and db.harga_zona reads the same numbers, so a
# rate cannot be changed in one and missed in the other. The keys are the
# values stored in events.zona and are matched by the CHECK constraint there —
# adding a zone here without adding it to the CHECK gets an insert refused.
#
# Keys are Indonesian because they are stored domain values, like nama_pt.
# Labels are English because only procurement staff read them; Jabodetabek is
# a proper noun and stays.
#
# Insertion order is the dropdown order, cheapest first.
ZONA = {
    "jabodetabek":      {"label": "Jabodetabek",         "pct": 0},
    "luar_jabodetabek": {"label": "Outside Jabodetabek", "pct": 5},
    "luar_jawa":        {"label": "Outside Java",        "pct": 10},
}

ZONA_DEFAULT = "jabodetabek"


def zona_pct(zona: str) -> int:
    """Surcharge percentage for a zone key.

    An unknown key falls back to the default's rate rather than raising: the
    CHECK on events.zona is what keeps unknown keys from existing, and a
    reporting page should not 500 over a value the database already refused
    to store."""
    return ZONA.get(zona, ZONA[ZONA_DEFAULT])["pct"]


def zona_label(zona: str) -> str:
    """Display name for a zone key, for the one line that names it on screen."""
    return ZONA.get(zona, ZONA[ZONA_DEFAULT])["label"]


if __name__ == "__main__":
    print(f"SMTP_HOST           = {SMTP_HOST}")
    print(f"SMTP_PORT           = {SMTP_PORT}")
    print(f"SMTP_USER           = {SMTP_USER}")
    print(f"SMTP_PASS           = <{len(SMTP_PASS)} chars>")
    print(f"SMTP_FROM_NAME      = {SMTP_FROM_NAME}")
    print(f"IMAP_HOST           = {IMAP_HOST}")
    print(f"IMAP_PORT           = {IMAP_PORT}")
    print(f"IMAP_FOLDER         = {IMAP_FOLDER}")
    print(f"IMAP_USER           = {IMAP_USER}")
    print(f"IMAP_PASS           = <{len(IMAP_PASS)} chars>")
    print(f"DRY_RUN             = {DRY_RUN}")
    print(f"SEND_DELAY_SECONDS  = {SEND_DELAY_SECONDS}")
    print(f"DB_PATH             = {DB_PATH}")
