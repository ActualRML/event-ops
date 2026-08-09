"""Shape of a nomor surat. Formatting and parsing only — the sequence is read
in db.py, so no SQL lives here."""

# The one place the shape of a nomor is defined: 041/SPK/PROC/VIII/2026.
# Sequence first and year last are assumed by pola_tahun() and urut_dari()
# below — if either moves, those two move with it.
FORMAT_NOMOR = "{urutan:03d}/SPK/PROC/{bulan}/{tahun}"

# Month as a Roman numeral, the way Indonesian office correspondence writes it.
ROMAWI = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def format_nomor(urutan: int, bulan: int, tahun: int) -> str:
    """Build one nomor from its parts."""
    return FORMAT_NOMOR.format(urutan=urutan, bulan=ROMAWI[bulan - 1], tahun=tahun)


def pola_tahun(tahun: int) -> str:
    """LIKE pattern matching every nomor issued in one year. Lives here rather
    than in the query so the trailing-year assumption sits beside the format
    it comes from."""
    return f"%/{tahun}"


def urut_dari(nomor: str, tahun: int) -> int:
    """Sequence out of a stored nomor, or 0 when the row belongs to another
    year or predates this format. Never raises: one unreadable row must not
    stop the next number from being issued."""
    bagian = str(nomor).split("/")
    if len(bagian) < 2 or bagian[-1] != str(tahun):
        return 0
    try:
        return int(bagian[0])
    except ValueError:
        return 0
