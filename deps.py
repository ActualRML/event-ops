"""Shared by more than one router.

Anything only one router uses stays with that router — this module is for
what would otherwise force one router to import another."""

from fastapi.templating import Jinja2Templates

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
