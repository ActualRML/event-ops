"""Shared by more than one router.

Anything only one router uses stays with that router — this module is for
what would otherwise force one router to import another."""

from fastapi.templating import Jinja2Templates

import db

templates = Jinja2Templates(directory="templates")


def parse_ids(raw: list[str]) -> list[int]:
    """Form values are strings. Non-numeric input is dropped here and caught
    by validation as 'no category selected' rather than a 422."""
    ids = []
    for value in raw:
        try:
            ids.append(int(value))
        except ValueError:
            continue
    return ids


def peta_spk(request_id: int) -> dict:
    """vendor_id -> SPK row, for the per-vendor action in the outbox table."""
    return {r["vendor_id"]: r for r in db.list_spk_for_request(request_id)}
