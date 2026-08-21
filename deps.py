"""Shared by more than one router.

Anything only one router uses stays with that router — this module is for
what would otherwise force one router to import another."""

import re
from urllib.parse import urlencode

from fastapi.templating import Jinja2Templates

from core import dokumen, terbilang

templates = Jinja2Templates(directory="templates")

# Page sizes offered on every list page. Not free-form: the value rides in the
# URL where anyone can type it, and an unbounded `per` is a way to ask the
# database for every row at once.
PER_PILIHAN = (10, 25, 50)
PER_DEFAULT = 25


def parse_halaman(per_raw: str, page_raw: str, total: int) -> dict:
    """Everything a paginated list page needs, from two query params and a count.

    Both params are strings off the URL and are treated as hostile: anything
    that is not one of PER_PILIHAN falls back to the default, and a page below
    one or past the end is clamped rather than 404'd. A stale bookmark to page
    9 of a list that has shrunk to two should show the last page, not an error
    — nothing here is a resource that can be missing, only a window onto one.

    Returned as a dict rather than a tuple because the template reads five of
    these by name; a five-tuple at the call site would be unreadable.

    `offset` is what the query needs, so callers COUNT first, call this, then
    fetch — the clamp cannot be applied before the total is known."""
    try:
        per = int(per_raw)
    except (TypeError, ValueError):
        per = PER_DEFAULT
    if per not in PER_PILIHAN:
        per = PER_DEFAULT

    try:
        page = int(page_raw)
    except (TypeError, ValueError):
        page = 1

    # -(-a // b) is ceiling division. At least one page, so an empty list still
    # renders "0 of 0" on page 1 rather than page 0 of 0.
    total_halaman = max(1, -(-total // per))
    page = max(1, min(page, total_halaman))
    offset = (page - 1) * per

    return {
        "per": per,
        "page": page,
        "offset": offset,
        "total": total,
        "total_halaman": total_halaman,
        # 1-based inclusive range for the chip. Both zero when nothing matched.
        "dari": offset + 1 if total else 0,
        "sampai": min(offset + per, total),
        "pilihan": PER_PILIHAN,
    }


def query_ganti(request, **ubah) -> str:
    """The current query string with some params replaced, for a page link.

    The point is that a page link must not lose the rest of the URL. /vendors
    carries a search and a category filter, /items an archive toggle; a link
    that rebuilt the query from scratch would silently drop them and page 2 of
    a search would show page 2 of everything.

    A param set to None is removed, so `page=1` links can drop the param
    instead of pinning it. Returns "" rather than "?" when nothing is left,
    which keeps a bare URL bare."""
    params = dict(request.query_params)
    for k, v in ubah.items():
        if v is None:
            params.pop(k, None)
        else:
            params[k] = str(v)
    return ("?" + urlencode(params)) if params else ""


# Grouped digits: 15.000.000 or 15,000,000, but not 15.5 — a stray decimal
# must be rejected, not silently multiplied by ten.
HARGA_BERKELOMPOK = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")


def parse_harga(raw: str, label: str = "Amount", allow_zero: bool = False,
                contoh: str = "a whole rupiah amount, e.g. 15.000.000",
                ) -> tuple[int | None, str | None]:
    """Read what procurement actually types. "15000000", "15.000.000" and
    "Rp 15.000.000" all mean the same amount; the separators are stripped and
    the value is stored as whole rupiah.

    label names the field in the messages: the SPK asks for an Amount, the item
    catalog for a Cost and a Value. allow_zero is the catalog's — an item may
    be carried at no cost, while an SPK issued for nothing is a defect, which
    is why the default stays the stricter of the two.

    contoh is what the "not a number" message suggests instead. It defaults to
    the rupiah wording every money field wants, and exists because the same
    grouped-digit parse is right for a quantity — someone typing 1.000 units
    means a thousand — while "e.g. 15.000.000" would not be.
    """
    teks = str(raw).strip()
    if not teks:
        return None, f"{label} is required."

    # Currency prefix and any spacing inside the digits.
    teks = re.sub(r"^rp\.?\s*", "", teks, flags=re.IGNORECASE)
    teks = re.sub(r"[\s ]", "", teks)

    if HARGA_BERKELOMPOK.match(teks):
        teks = teks.replace(".", "").replace(",", "")
    elif not teks.isdigit():
        return None, f"Enter {contoh}."

    nilai = int(teks)
    # Zero is the only non-positive value that can reach here — the digit test
    # above has already turned a minus sign away as non-numeric.
    if nilai == 0 and not allow_zero:
        return None, f"{label} must be greater than zero."
    # The SPK spells its amount out, and terbilang stops here. The cap is
    # applied to every field rather than only that one: an amount this side of
    # a trillion rupiah is a typo wherever it is typed.
    if nilai > terbilang.MAKS:
        maks = dokumen.format_rupiah(terbilang.MAKS, prefix=False)
        return None, f"{label} is above the maximum of {maks}."
    return nilai, None


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
