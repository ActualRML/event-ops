"""Vendor replies: the check, the held list, one reply, its attachments.

Every path lives under /tracker/, so the drawer lights Tracker with no entry
of its own — the same way /categories lights Vendors. That is deliberate: the
question these pages answer is "who hasn't replied yet", which is a fact about
a batch, so they belong to Tracker rather than to a second inbox screen.

THIS ROUTER MUST BE INCLUDED BEFORE tracker.router. /tracker/{request_id}
matches any single segment, so "replies" would be captured as a request_id and
422 on int conversion — a path parameter does not fall through to the next
route when validation fails.
"""

import asyncio
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

import config
import db
import replies
from core import tampilan
from deps import templates

router = APIRouter()


def konteks_cek() -> dict:
    """When the check last ran, and whether that run failed.

    `cek_berhasil` is the last SUCCESSFUL run and is not the same as
    `cek_terakhir` — a first-ever check that failed gives a row with no
    successful predecessor, and the page must still say the mailbox has never
    been read rather than show that failed run's timestamp as a result.

    /tracker builds the same three keys inline instead of calling this. That
    duplication is deliberate: one router importing another is what deps.py
    exists to prevent, and two db calls are not worth widening deps for."""
    terakhir = db.last_check()
    return {
        "cek_terakhir": terakhir,
        "cek_berhasil": db.watermark(),
        "pernah": terakhir is not None,
    }


@router.post("/tracker/replies/check")
async def replies_check(request: Request):
    """Run one check, then redirect. No scheduler and no poller — a button.

    to_thread because imaplib is synchronous: called directly from here it
    would block the event loop for the whole fetch, freezing every other
    request including an in-flight send batch's delays between emails.

    The result is not carried in the redirect. It is already in inbox_check,
    which is where the page reads it from — so a refresh shows the same answer
    rather than an empty one, and there is no flash message to lose."""
    await asyncio.to_thread(replies.check_replies)
    return RedirectResponse("/tracker/replies", status_code=303)


@router.get("/tracker/replies")
async def replies_list(request: Request):
    konteks = {
        "request": request,
        "perlu_assign": db.list_unassigned(),
        "tak_cocok": db.list_unmatched(),
    }
    konteks.update(konteks_cek())
    return templates.TemplateResponse(request, "replies.html", konteks)


@router.get("/tracker/replies/{reply_id}")
async def reply_detail(request: Request, reply_id: int):
    """One reply. Opening it marks it read.

    A GET with a side effect, deliberately: it is what every mail client does,
    and the alternative is a button the user has to remember to press for the
    badge to ever go down. Marking is idempotent — read_at keeps the first
    time, so a refresh does not rewrite it."""
    balasan = db.get_reply(reply_id)
    if balasan is None:
        raise HTTPException(status_code=404, detail="Reply not found")

    db.mark_reply_read(reply_id)

    # Only a held reply needs a chooser, and only one with a known vendor has
    # anything to offer in it.
    pilihan = []
    if balasan["request_id"] is None and balasan["vendor_id"] is not None:
        pilihan = db.batches_for_vendor(balasan["vendor_id"])

    # Dibelah di sini, bukan di parser: inbox.body menyimpan pesan utuh dan
    # pemotongan terjadi di jalan keluar, aturan yang sama dengan pesan_error.
    # Dibawa sebagai dua kunci konteks, bukan filter, karena hasilnya sepasang
    # nilai — filter yang mengembalikan tuple memaksa template membongkarnya
    # dan itu lebih berisik daripada dua nama yang jelas.
    jawaban, kutipan = tampilan.belah_kutipan(balasan["body"])

    return templates.TemplateResponse(
        request, "reply_detail.html",
        {
            "request": request,
            "balasan": balasan,
            "jawaban": jawaban,
            "kutipan": kutipan,
            "lampiran": db.list_attachments(reply_id),
            "pilihan": pilihan,
        },
    )


@router.post("/tracker/replies/{reply_id}/assign")
async def reply_assign(reply_id: int, request_id: str = Form("")):
    """Attach a held reply to one of the vendor's batches.

    The batch must be one this vendor was actually written to. db.assign_reply
    resolves the outbox row itself and refuses a reply that is already
    assigned, so a double submit is a no-op rather than a move."""
    balasan = db.get_reply(reply_id)
    if balasan is None:
        raise HTTPException(status_code=404, detail="Reply not found")

    try:
        tujuan = int(request_id)
    except (TypeError, ValueError):
        return RedirectResponse(f"/tracker/replies/{reply_id}", status_code=303)

    # The chooser only ever offers this vendor's own batches; a hand-posted id
    # for someone else's batch is refused here rather than trusted.
    if balasan["vendor_id"] is None:
        raise HTTPException(status_code=400, detail="Reply has no vendor to assign")
    if not any(b["id"] == tujuan for b in db.batches_for_vendor(balasan["vendor_id"])):
        raise HTTPException(status_code=404, detail="Vendor is not part of that batch")

    db.assign_reply(reply_id, tujuan)
    return RedirectResponse(f"/tracker/{tujuan}", status_code=303)


@router.get("/tracker/replies/{reply_id}/attachment/{attachment_id}")
async def reply_attachment(reply_id: int, attachment_id: int):
    """Download one attachment.

    The file is located by its STORED name, which this app generated from two
    row ids. The vendor's own filename is used for nothing but the download
    name the browser shows. resolve() and the parent check are belt-and-braces
    over a string that cannot contain a separator in the first place.

    Always an attachment disposition, never inline: a vendor-supplied PDF or
    HTML file rendered in the app's own origin is a different problem."""
    lampiran = db.get_attachment(attachment_id)
    if lampiran is None or lampiran["inbox_id"] != reply_id:
        raise HTTPException(status_code=404, detail="Attachment not found")

    akar = Path(config.ATTACHMENT_DIR).resolve()
    berkas = (akar / lampiran["stored_name"]).resolve()
    if akar not in berkas.parents or not berkas.is_file():
        raise HTTPException(status_code=404, detail="Attachment file is missing")

    return FileResponse(
        berkas,
        media_type=lampiran["content_type"] or "application/octet-stream",
        filename=lampiran["filename"],
    )
