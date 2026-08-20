"""CLI: does the mail server preserve the Message-ID we set?

    python cek_message_id.py

Sends ONE real email from SMTP_USER to itself, waits for it to arrive, and
compares the Message-ID header on the delivered copy with the one core/mailer
generated. Prints both and says whether they match.

WHY THIS EXISTS. core/mailer.py mints a Message-ID with make_msgid(), sets it
on the outgoing message, and db.mark_sent stores it on the outbox row. Reply
matching wants to use that stored id as its strongest key: a vendor's reply
carries the id it is answering in In-Reply-To or References, so an exact match
attaches the reply to the exact outbox row.

That whole tier rests on an assumption nothing in the codebase can check —
that the submission server sends our id rather than replacing it with one of
its own. Gmail is widely reported to rewrite Message-ID on smtp.gmail.com. If
it does, the stored id never appears in any reply, and the tier does not fail
loudly; it just never matches, and every reply quietly falls through to the
next rung. The SMTP response cannot settle it either — it carries a queue id,
not a Message-ID.

So: send one, read it back, look.

Not a test in the automated sense and not wired into the app. It touches the
network and the real mailbox, so it is run deliberately, by hand, and its
answer is written down rather than re-derived.

Requires DRY_RUN=0 — under DRY_RUN nothing is sent and there is nothing to
read back. Gmail also needs IMAP enabled in its settings; the existing app
password works for it unchanged.
"""

import asyncio
import email
import imaplib
import sys
import time

import config
from core.mailer import kirim_email

SUBJECT = "Message-ID round trip - Vendor RFQ Blast"
BODY = """Halo,

Ini email percobaan untuk memeriksa header Message-ID.
Abaikan pesan ini.

Terima kasih.
"""

# How long to wait for the message to come back, and how often to look. Gmail
# usually loops a message to itself within a few seconds; a minute is generous
# enough that a slow delivery is not mistaken for a rewrite.
BATAS_TUNGGU = 60
JEDA = 5


def cari_pesan(imap: imaplib.IMAP4_SSL, message_id: str) -> str | None:
    """The Message-ID header on the delivered copy, or None if not there yet.

    Searched by SUBJECT rather than by HEADER Message-ID, and that is the whole
    point: searching for our own id would only ever find a message that still
    carries it, so a rewritten one would look like a message that never
    arrived. Subject survives whatever the server does to the headers.
    """
    ok, data = imap.search(None, "SUBJECT", f'"{SUBJECT}"')
    if ok != "OK" or not data or not data[0]:
        return None

    # Newest last in an IMAP search result; take the most recent match so a
    # previous run's copy still sitting in the mailbox is not what gets read.
    nomor = data[0].split()[-1]
    ok, isi = imap.fetch(nomor, "(RFC822)")
    if ok != "OK" or not isi or not isinstance(isi[0], tuple):
        return None

    pesan = email.message_from_bytes(isi[0][1])
    return pesan.get("Message-ID")


def main() -> int:
    if config.DRY_RUN:
        print("DRY_RUN is on, so nothing would be sent and there would be",
              file=sys.stderr)
        print("nothing to read back. Set DRY_RUN=0 in .env and re-run.",
              file=sys.stderr)
        return 1

    if not config.SMTP_USER or not config.SMTP_PASS:
        print("SMTP_USER and SMTP_PASS must be set in .env.", file=sys.stderr)
        return 1

    alamat = config.SMTP_USER
    print(f"sending to {alamat} ...")

    ok, dikirim = asyncio.run(kirim_email(alamat, SUBJECT, BODY))
    if not ok:
        print(f"send failed: {dikirim}", file=sys.stderr)
        return 1

    print(f"  generated Message-ID : {dikirim}")
    print(f"waiting up to {BATAS_TUNGGU}s for it to arrive ...")

    try:
        imap = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT,
                                 timeout=20)
    except Exception as e:
        print(f"IMAP connect failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    try:
        imap.login(config.IMAP_USER, config.IMAP_PASS)
        imap.select(config.IMAP_FOLDER)

        diterima = None
        batas = time.monotonic() + BATAS_TUNGGU
        while time.monotonic() < batas:
            diterima = cari_pesan(imap, dikirim)
            if diterima:
                break
            time.sleep(JEDA)
    except imaplib.IMAP4.error as e:
        print(f"IMAP failed: {type(e).__name__}: {e}", file=sys.stderr)
        print("  check that IMAP is enabled in Gmail settings.", file=sys.stderr)
        return 1
    finally:
        try:
            imap.logout()
        except Exception:
            pass

    if not diterima:
        print("the message did not arrive within the wait.", file=sys.stderr)
        print("  inconclusive — this says nothing either way about rewriting.",
              file=sys.stderr)
        return 1

    print(f"  received  Message-ID : {diterima}")
    print()

    if diterima.strip() == dikirim.strip():
        print("PRESERVED. The server sends the id we set, so a reply's")
        print("In-Reply-To will carry it and outbox.message_id is a usable")
        print("matching key.")
        return 0

    print("REWRITTEN. The server replaced our id, so the value stored in")
    print("outbox.message_id never reaches the vendor and will never appear")
    print("in a reply. Matching on it cannot work as things stand.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
