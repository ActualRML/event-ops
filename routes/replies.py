"""Vendor replies: the check, one reply, its attachments.

Every path lives under /tracker/, so the drawer lights Tracker with no entry
of its own — the same way /categories lights Vendors. That is deliberate: the
question these pages answer is "who hasn't replied yet", which is a fact about
a batch, so they belong to Tracker rather than to a second inbox screen.

There is no reply LIST any more. It was deleted: /tracker already carried the
check button, the last-checked chip and the failure banner, so the page
duplicated all three and, on a mailbox where matching works, was empty every
time. What only it had — the replies the ladder could not place — is now a
section on /tracker that renders only when there is something in it. The
detail page stays; it is where a reply is assigned and approved.

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


@router.post("/tracker/replies/check")
async def replies_check(request: Request):
    """Run one check, then redirect. No scheduler and no poller — a button.

    to_thread because imaplib is synchronous: called directly from here it
    would block the event loop for the whole fetch, freezing every other
    request including an in-flight send batch's delays between emails.

    The result is not carried in the redirect. It is already in inbox_check,
    which /tracker reads it from — so a refresh shows the same answer rather
    than an empty one, and there is no flash message to lose.

    Back to /tracker, which is where the button is and where the answer shows:
    a matched reply lands on its batch in the list, and anything that could not
    be placed appears in that page's own held section. There used to be a
    /tracker/replies list to land on and it was deleted — it duplicated the
    check state /tracker already carried, and on a healthy mailbox it was an
    empty page every single time."""
    await asyncio.to_thread(replies.check_replies)
    return RedirectResponse("/tracker", status_code=303)


@router.get("/tracker/replies")
async def replies_gone():
    """The deleted list, kept as a redirect and nothing more.

    Not a page and not coming back. It exists because without a handler the
    path falls through to /tracker/{request_id}, which captures "replies" as an
    id and 422s on int conversion — so a bookmark or a history entry from
    before the deletion produces a validation error rather than a page. Three
    lines to turn that into the page that replaced it."""
    return RedirectResponse("/tracker", status_code=307)


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

    # Only a held reply needs a chooser, and which one it gets depends on what
    # the ladder left missing. `mode` names that, and the template reads it for
    # the field label rather than re-deriving the condition.
    #
    #   batch  — the vendor is known; pick which of THEIR batches this answers
    #   vendor — the batch is known; pick which of ITS vendors sent this
    #   both   — neither is known; one pick answers both questions
    #
    # "both" falls back to every (batch, vendor) pair. The narrower two are
    # preferred wherever possible: an unscoped list is a scrolling one.
    pilihan = []
    mode = None
    if balasan["vendor_id"] is None and balasan["request_id"] is not None:
        mode = "vendor"
        pilihan = db.outbox_targets(balasan["request_id"])
    elif balasan["request_id"] is None:
        if balasan["vendor_id"] is not None:
            mode = "batch"
            pilihan = db.batches_for_vendor(balasan["vendor_id"])
        else:
            mode = "both"
            pilihan = db.outbox_targets()

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
            "mode": mode,
            # Approving is only meaningful once the reply names a pair, and an
            # approval can only be withdrawn while no work order rests on it.
            "bisa_approve": (balasan["request_id"] is not None
                             and balasan["vendor_id"] is not None
                             and not balasan["auto_reply"]),
            "spk_terbit": (db.spk_exists_for(balasan["request_id"],
                                             balasan["vendor_id"])
                           if balasan["request_id"] is not None
                           and balasan["vendor_id"] is not None else False),
        },
    )


@router.post("/tracker/replies/{reply_id}/approve")
async def reply_approve(reply_id: int, approved: str = Form("1")):
    """Accept this vendor's quote, or withdraw that acceptance.

    The one act that opens the SPK gate. It lives here rather than on the
    tracker table on purpose: the button sits on the page that shows the quote
    and its attachments, so accepting is done with the offer in front of you,
    and opening that page has already stamped read_at. Nothing can be approved
    unread, and that is enforced by where the button is rather than by a check.

    db.set_reply_approved refuses a reply that names no pair, an auto-reply,
    and a withdrawal once an SPK exists — so a stale form posting into any of
    those is a no-op that lands back on the page, not an error."""
    if db.get_reply(reply_id) is None:
        raise HTTPException(status_code=404, detail="Reply not found")

    db.set_reply_approved(reply_id, approved == "1")
    return RedirectResponse(f"/tracker/replies/{reply_id}", status_code=303)


@router.post("/tracker/replies/{reply_id}/assign")
async def reply_assign(reply_id: int, request_id: str = Form("")):
    """Attach a held reply to a batch.

    Two shapes, because the two choosers answer different questions. When the
    ladder named the vendor, the value is a bare batch id and the batch must be
    one that vendor was actually written to. When it did not — a tier 4 — the
    value is "batch:vendor", since picking a batch alone would leave vendor_id
    NULL and the reply visible on no page at all.

    Whichever shape arrives, the pick is checked against the same list the
    chooser offered rather than trusted: a hand-posted id for someone else's
    batch is refused here. db.assign_reply refuses a reply that is already
    assigned, so a double submit is a no-op rather than a move."""
    balasan = db.get_reply(reply_id)
    if balasan is None:
        raise HTTPException(status_code=404, detail="Reply not found")

    batch, _, vendor = request_id.partition(":")
    try:
        tujuan = int(batch)
        vendor_id = int(vendor) if vendor else None
    except (TypeError, ValueError):
        return RedirectResponse(f"/tracker/replies/{reply_id}", status_code=303)

    if balasan["vendor_id"] is not None:
        # The vendor is known; only the batch was chosen.
        if not any(b["id"] == tujuan
                   for b in db.batches_for_vendor(balasan["vendor_id"])):
            raise HTTPException(status_code=404,
                                detail="Vendor is not part of that batch")
    else:
        if vendor_id is None:
            raise HTTPException(status_code=400,
                                detail="Reply has no vendor, so one must be chosen")
        # A batch the code already resolved is not up for revision here: the
        # only open question was who sent it, so a posted batch that is not the
        # reply's own is refused rather than honoured.
        if (balasan["request_id"] is not None
                and tujuan != balasan["request_id"]):
            raise HTTPException(status_code=404,
                                detail="That is not this reply's batch")
        if not any(t["id"] == tujuan and t["vendor_id"] == vendor_id
                   for t in db.outbox_targets(balasan["request_id"])):
            raise HTTPException(status_code=404,
                                detail="Vendor is not part of that batch")

    db.assign_reply(reply_id, tujuan, vendor_id)
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
