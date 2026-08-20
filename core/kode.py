"""The RFQ batch reference code: how it is made, and how it is written into a
subject.

ONE MODULE OWNS THE FORMAT. Generating a code, stamping it onto a subject and
(later) reading it back off a reply are three views of the same four
characters, so they live together for the reason config.ZONA does: a format
cannot be changed for the writer and missed for the reader.

Pure. Nothing here touches the database, so nothing here can tell whether a
code is free — that is db.kode_exists, and the caller pairs the two.
"""

import re
import secrets

# Four uppercase hex characters. Short enough that a human reads it back over
# the phone, long enough that 65,536 values make a collision rare rather than
# routine — and rare is all it needs to be, because db.create_request re-rolls
# on the UNIQUE index rather than trusting the odds.
PANJANG_BYTE = 2

# The literal that goes in the subject. Square brackets and a fixed prefix so
# the marker is recognisable in a subject line a vendor has quoted, forwarded
# and prefixed with "Re:" twice over.
AWALAN = "RFQ-"

# What to look for coming back. Anchored to the same shape TANDA writes, and
# deliberately strict about the alphabet: [0-9A-F] is what secrets.token_hex
# produces uppercased, so anything else was not minted here.
#
# Used by the reply gate to decide whether a message is plausibly about an RFQ
# at all, which is why it tests SHAPE and not existence — a well-formed code
# that matches no batch is a real case (a deleted batch, a mangled forward) and
# has to be admitted so it can be reported rather than silently dropped.
POLA = re.compile(r"\[" + AWALAN + r"([0-9A-F]{4})\]")


def buat_kode() -> str:
    """A fresh code. Random, never derived from the request id.

    Deriving it from the id would leak how many batches exist and would make
    two installs mint the same codes; neither matters much, but neither buys
    anything either, and random costs nothing. The caller checks it is free.
    """
    return secrets.token_hex(PANJANG_BYTE).upper()


def tanda(kode: str) -> str:
    """The marker as it appears in a subject: 3F2A -> [RFQ-3F2A]."""
    return f"[{AWALAN}{kode}]"


def tandai_subjek(subject: str, kode: str | None) -> str:
    """Stamp the marker onto a rendered subject.

    A blank or missing kode returns the subject untouched, which is what keeps
    every batch sent before codes existed rendering exactly as it always did.

    Appended mechanically here rather than offered as a {{ kode }} placeholder
    in email_templates/rfq_subject.txt, because that template is editable on
    the Send page: a placeholder can be deleted by whoever is editing the copy,
    and then the reply comes back with nothing to match on. The marker is
    protocol, not copy, so it is not the copy editor's to remove.

    Idempotent on its own output — a subject that already carries this exact
    marker is returned unchanged rather than gaining a second one.
    """
    if not kode:
        return subject
    penanda = tanda(kode)
    if penanda in subject:
        return subject
    return f"{subject} {penanda}"


def dari_subjek(subject: str) -> str | None:
    """The code carried by a subject, or None.

    Returns the LAST match, not the first, and the two differ only in the odd
    case where a subject carries more than one marker. The asymmetry that
    settles it: markers are APPENDED to the end of a subject, while reply and
    forward prefixes are PREPENDED to the front. So the marker belonging to the
    original subject is always the last one on the line, however many "Re:" and
    "Fwd:" have accumulated in front of it.
    """
    hasil = POLA.findall(subject or "")
    return hasil[-1] if hasil else None
