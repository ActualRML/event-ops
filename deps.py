"""Shared by more than one router.

Anything only one router uses stays with that router — this module is for
what would otherwise force one router to import another."""

import re

from fastapi.templating import Jinja2Templates

from core import dokumen, terbilang

templates = Jinja2Templates(directory="templates")

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
