"""Rupiah amounts spelled out in Indonesian, for the SPK body."""

MAKS = 999_999_999_999

# 0..11 are listed rather than composed, because the se- forms are single
# words: sepuluh not "satu puluh", sebelas not "satu belas". Everything from
# 12 up is built out of this table.
DASAR = [
    "nol", "satu", "dua", "tiga", "empat", "lima",
    "enam", "tujuh", "delapan", "sembilan", "sepuluh", "sebelas",
]


def _kata(n: int) -> str:
    """The recursion. Returns "" for zero so a caller can append the remainder
    unconditionally and strip; terbilang() handles a standalone zero itself.

    Each band above brackets its own se- form: 100..199 is seratus, and
    1000..1999 is seribu, so neither can come out as "satu ratus"/"satu ribu".
    """
    if n == 0:
        return ""
    if n < 12:
        return DASAR[n]
    if n < 20:
        return f"{_kata(n - 10)} belas"
    if n < 100:
        return f"{_kata(n // 10)} puluh {_kata(n % 10)}".strip()
    if n < 200:
        return f"seratus {_kata(n - 100)}".strip()
    if n < 1_000:
        return f"{_kata(n // 100)} ratus {_kata(n % 100)}".strip()
    if n < 2_000:
        return f"seribu {_kata(n - 1_000)}".strip()
    if n < 1_000_000:
        return f"{_kata(n // 1_000)} ribu {_kata(n % 1_000)}".strip()
    if n < 1_000_000_000:
        return f"{_kata(n // 1_000_000)} juta {_kata(n % 1_000_000)}".strip()
    # No se- form above ribu: it is "satu miliar", never "semiliar".
    return f"{_kata(n // 1_000_000_000)} miliar {_kata(n % 1_000_000_000)}".strip()


def terbilang(n: int) -> str:
    """Whole rupiah in words: 15000000 -> "lima belas juta rupiah".

    Raises on anything outside 0..999,999,999 rather than returning a wrong
    figure — an SPK that understates its own amount is worse than one that
    fails to render.
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise ValueError(f"terbilang needs a whole number, got {n!r}")
    if n < 0 or n > MAKS:
        raise ValueError(f"terbilang covers 0..{MAKS}, got {n}")
    return f"{_kata(n) or DASAR[0]} rupiah"
