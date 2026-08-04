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

DRY_RUN = _get_bool("DRY_RUN", True)
SEND_DELAY_SECONDS = _get_int("SEND_DELAY_SECONDS", 2)

DB_PATH = os.getenv("DB_PATH", "db/rfq.db")


if __name__ == "__main__":
    print(f"SMTP_HOST           = {SMTP_HOST}")
    print(f"SMTP_PORT           = {SMTP_PORT}")
    print(f"SMTP_USER           = {SMTP_USER}")
    print(f"SMTP_PASS           = <{len(SMTP_PASS)} chars>")
    print(f"SMTP_FROM_NAME      = {SMTP_FROM_NAME}")
    print(f"DRY_RUN             = {DRY_RUN}")
    print(f"SEND_DELAY_SECONDS  = {SEND_DELAY_SECONDS}")
    print(f"DB_PATH             = {DB_PATH}")
