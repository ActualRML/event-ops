"""Rundown schedule arithmetic.

Pure functions: no database, no request, no imports from db or routes. The
schedule is never stored — it is recomputed from jam_mulai and the item
durations every time it is shown.

Past midnight
-------------
A rundown is a sequence of durations starting at jam_mulai, not a set of
wall-clock instants. Internally every time is minutes elapsed since
jam_mulai, so the arithmetic is plain addition with no special case at
midnight. Only on the way out is a time rendered as HH:MM, and that
rendering wraps modulo 24 hours: a 22:00 start with 180 minutes of items
ends at "01:00".

The strings therefore carry no date. "01:00" after a 22:00 start is the
next calendar day, and the caller is expected to read it that way — an
event that runs past midnight is normal here, not an error. The one place
this would bite is comparing two HH:MM strings directly to see which is
later, so nothing in this module does that: the batas_venue check works in
elapsed minutes, where 01:00 is 180 and orders correctly against a limit.
"""

MENIT_PER_HARI = 24 * 60


def ke_menit(jam: str) -> int:
    """"HH:MM" to minutes since midnight. Raises ValueError on anything else."""
    teks = (jam or "").strip()
    jam_str, pemisah, menit_str = teks.partition(":")
    if not pemisah or not jam_str.isdigit() or not menit_str.isdigit():
        raise ValueError(f"Expected HH:MM, got {jam!r}")

    j, m = int(jam_str), int(menit_str)
    if not (0 <= j <= 23) or not (0 <= m <= 59):
        raise ValueError(f"Time out of range: {jam!r}")
    return j * 60 + m


def ke_jam(menit: int) -> str:
    """Minutes since midnight to "HH:MM", wrapping at 24 hours.

    The wrap is what lets a rundown cross midnight: minute 1500 renders as
    "01:00", the next day, and no caller needs a special case for it."""
    menit %= MENIT_PER_HARI
    return f"{menit // 60:02d}:{menit % 60:02d}"


def hitung_jadwal(jam_mulai: str, durasi: list[int],
                  batas_venue: str | None) -> dict:
    """Lay a list of durations out from jam_mulai.

    Returns:
      baris        [{"mulai": "HH:MM", "selesai": "HH:MM"}, ...], one per duration
      jam_selesai  end of the last item, or jam_mulai when there are none
      lewat_batas  True when the rundown runs past batas_venue
      lebih_menit  minutes past batas_venue, 0 when not over

    batas_venue is a wall-clock time, so it is first converted to a window
    length: how many minutes after jam_mulai the limit falls. A limit that
    reads earlier on the clock than the start time is taken as being on the
    following day — 22:00 start with a 23:00 limit is a 60-minute window,
    and a 01:00 limit is a 180-minute one. Landing exactly on the limit is
    not over.
    """
    mulai = ke_menit(jam_mulai)

    baris = []
    berjalan = 0
    for menit in durasi:
        awal = berjalan
        berjalan += menit
        baris.append({
            "mulai": ke_jam(mulai + awal),
            "selesai": ke_jam(mulai + berjalan),
        })

    # No items: the rundown ends where it starts. Nothing can be over a
    # limit that has not been reached.
    jam_selesai = ke_jam(mulai + berjalan)

    lewat_batas = False
    lebih_menit = 0
    if batas_venue is not None:
        jendela = (ke_menit(batas_venue) - mulai) % MENIT_PER_HARI
        if berjalan > jendela:
            lewat_batas = True
            lebih_menit = berjalan - jendela

    return {
        "baris": baris,
        "jam_selesai": jam_selesai,
        "lewat_batas": lewat_batas,
        "lebih_menit": lebih_menit,
    }
