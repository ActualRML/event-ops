"""The reply check: fetch, gate, match, store.

tasks.py's peer, and the same layer — orchestration that needs db and core
together but has no web layer of its own. Imports config, db and core; never
deps, never routes, never tasks. A router imports this, never the reverse.

Synchronous throughout, because imaplib is. The router calls it through
asyncio.to_thread; calling it directly from an async handler blocks the whole
event loop, in-flight send batches included.
"""

import re
from datetime import datetime
from pathlib import Path

import config
import db
from core import inbox, kode

# Vendor filenames never reach a path, but they do reach a Content-Disposition
# header, and a newline or a quote in one would let the sender write their own
# headers. Stripped on the way in rather than on the way out, so every consumer
# of the stored value is safe rather than only the one that remembered.
TAK_AMAN = re.compile(r'[\r\n"\\/\x00]')

# Tier numbers, named. The database stores the integer; nothing outside this
# module should have to remember which is which.
TIER_MESSAGE_ID = 1
TIER_KODE = 2
TIER_PENGIRIM = 3
TIER_TAK_COCOK = 4


def nama_aman(nama: str) -> str:
    """A vendor's filename, made safe to store and to echo in a header.

    This is NOT what keeps files inside the attachments directory — that is
    handled by never using this string as a path at all. This only stops a
    crafted filename from breaking the header it is later quoted into."""
    bersih = TAK_AMAN.sub("_", (nama or "").strip())
    bersih = bersih.replace("..", "_")
    return bersih[:200] or "lampiran"


def ekstensi(nama: str) -> str:
    """The extension to store a file under: the sender's if we recognise it,
    .bin otherwise. Cosmetic — it decides which application opens a saved
    file, not where the file goes."""
    akhir = Path((nama or "").lower()).suffix
    return akhir if akhir in config.ATTACHMENT_EXT else ".bin"


def simpan_lampiran(inbox_id: int, lampiran) -> int:
    """Write one reply's attachments to disk and record them. Returns how many
    were saved.

    THE ON-DISK NAME IS OURS. It is built from the two row ids plus a
    whitelisted extension, so the vendor's filename — the only
    attacker-controlled string in play — never touches a path. Traversal is not
    defended against here; it is unreachable, the same way the sponsor print
    route cannot leak cost because cost is never passed to it.

    Oversized files are skipped and NOT recorded, so nothing shows a download
    that would 404. The caps are per file and per message; the running total is
    what stops fifty small attachments doing what one large one cannot.
    """
    tujuan = Path(config.ATTACHMENT_DIR)
    tujuan.mkdir(parents=True, exist_ok=True)

    disimpan = 0
    total = 0
    for urutan, (nama, tipe, isi) in enumerate(lampiran, start=1):
        if len(isi) > config.ATTACHMENT_MAX_BYTES:
            continue
        if total + len(isi) > config.ATTACHMENT_MAX_TOTAL:
            break
        total += len(isi)

        # Name built from the reply id and this file's position in it, not
        # from the attachment ROW id: the row does not exist yet, and a
        # placeholder written first would collide on stored_name's UNIQUE the
        # moment a second attachment wanted the same placeholder. inbox_id is
        # unique and the position is unique within it, so the pair is enough.
        simpan_nama = f"{inbox_id}-{urutan}{ekstensi(nama)}"
        try:
            (tujuan / simpan_nama).write_bytes(isi)
        except OSError:
            # Disk full, name too long, permissions. Skip the file rather than
            # the message: the body is usually still worth having.
            continue

        db.create_inbox_attachment(
            inbox_id, nama_aman(nama), tipe or "application/octet-stream",
            len(isi), simpan_nama,
        )
        disimpan += 1

    return disimpan


def cocokkan(pesan: dict, email_vendor: dict):
    """The ladder. Returns (tier, request_id, outbox_id, vendor_id).

    Stops at the first tier that resolves. The tier is recorded and never
    rewritten, so it stays a record of HOW this message was matched even after
    a human assigns it by hand.
    """
    # Tier 1 — the reply points at a message we sent. Exact, per outbox row.
    baris = db.outbox_by_message_id(pesan["rujukan"])
    if baris is not None:
        return (TIER_MESSAGE_ID, baris["request_id"], baris["id"],
                baris["vendor_id"])

    vendor_id = email_vendor.get(pesan["from_email"])

    # Tier 2 — the subject still carries the batch code. Resolves the batch;
    # resolves the vendor too when the sender is one of that batch's.
    k = kode.dari_subjek(pesan["subject"])
    if k:
        permintaan = db.request_by_kode(k)
        if permintaan is not None:
            outbox_id = None
            if vendor_id is not None:
                kotak = db.outbox_row_for(permintaan["id"], vendor_id)
                outbox_id = kotak["id"] if kotak else None
                # A vendor who is not in this batch does not get attached to
                # it: they may have been forwarded the thread.
                if kotak is None:
                    vendor_id = None
            return (TIER_KODE, permintaan["id"], outbox_id, vendor_id)

    # Tier 3 — we know the sender and nothing else. NEVER ATTACHES. One vendor
    # working two concurrent events cannot be told apart by their address, and
    # concurrent events are normal here, so this is held for a human.
    if vendor_id is not None:
        return (TIER_PENGIRIM, None, None, vendor_id)

    # Tier 4 — past the gate, resolved to nothing. Reachable only because the
    # gate admits a well-formed code that names no batch: a deleted batch, a
    # mangled forward, a code from another install.
    return (TIER_TAK_COCOK, None, None, None)


def lolos_gerbang(pesan: dict, email_vendor: dict) -> bool:
    """Is this message plausibly about an RFQ at all?

    Admitted when the sender is a known vendor, OR the subject carries a
    WELL-FORMED [RFQ-xxxx] — whether or not it resolves. Everything else is
    dropped here and never written: not stored, not counted, not shown. That
    is what keeps this from becoming a second inbox.

    Shape, not resolution, and the difference is what makes tier 4 reachable.
    Gating on resolution would mean a code that resolves is tier 2 and a known
    sender is tier 3, leaving nothing able to fall through — a bottom rung that
    could never hold anything. A code shaped like ours but naming no batch is a
    real case worth reporting rather than silently dropping.

    THE GATE ALSO CATCHES SOMETHING THE LADDER WOULD GET WRONG. A bounce from
    mailer-daemon carries References pointing at the message it failed to
    deliver — our own sent Message-ID. Reaching tier 1, it would attach to that
    vendor's outbox row and be displayed as their reply, which is the exact
    opposite of what it means. It never gets there because mailer-daemon is not
    a vendor and "Delivery Status Notification (Failure)" carries no code. The
    gate is doing real work here, not just keeping the volume down."""
    if pesan["from_email"] in email_vendor:
        return True
    return kode.dari_subjek(pesan["subject"]) is not None


def check_replies() -> dict:
    """One whole check. Returns a summary dict; never raises.

    The failure path is the point. An IMAP error is recorded as a run with
    ok = 0 and surfaced as a banner, and the watermark stays where it was — a
    user looking at zero replies must be able to tell "nobody replied" from
    "the check never ran", and a failed run must not skip the day it failed on.
    """
    mulai = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sejak = db.watermark()

    try:
        mentah = inbox.ambil(sejak)
    except Exception as e:
        db.record_check(mulai, False, f"{type(e).__name__}: {e}", 0, 0)
        return {"ok": False, "error": f"{type(e).__name__}: {e}",
                "examined": 0, "kept": 0}

    email_vendor = db.vendor_emails()
    diperiksa = 0
    disimpan = 0

    for isi in mentah:
        diperiksa += 1
        try:
            pesan = inbox.urai(isi)
        except Exception:
            # A message that cannot be parsed at all is skipped, never fatal.
            # One bad message must not halt the run — the same rule invariant 5
            # sets for sends.
            continue

        if not pesan["message_id"]:
            # Nothing to dedupe on. Storing it would mean re-storing it on
            # every future check, which is worse than missing it.
            continue
        if not lolos_gerbang(pesan, email_vendor):
            continue
        if db.inbox_exists(pesan["message_id"]):
            continue

        if not pesan["received_at"]:
            # Their Date header was missing or unparseable, so fall back to
            # our own clock rather than storing a blank and sorting oddly.
            pesan["received_at"] = mulai

        tier, request_id, outbox_id, vendor_id = cocokkan(pesan, email_vendor)
        baris_id = db.create_inbox(pesan, tier, request_id, outbox_id, vendor_id)
        if baris_id is None:
            # Lost a race with another check. The UNIQUE did its job.
            continue

        simpan_lampiran(baris_id, pesan["lampiran"])
        disimpan += 1

    db.record_check(mulai, True, None, diperiksa, disimpan)
    return {"ok": True, "error": None, "examined": diperiksa, "kept": disimpan}
