"""Send history: the event list, one event's batches, one batch's detail, and
retry.

The list is EVENTS, not batches. An event is what procurement thinks in — one
job, quoted in several rounds — so the top level names the job and the rounds
live one level in. Batches are reached at /tracker/{event_id} and named by
their category (Tenda, Sound System), which is what tells them apart; the id
never appears.

That makes /tracker/{event_id} an EVENT id where it used to be a request id.
Both are ints in overlapping ranges, so an old bookmark to /tracker/5 would
otherwise show a different record with no error to say so — which is why the
batch pages moved to an unambiguous /tracker/batch/{request_id} rather than
staying on a path whose meaning changed underneath them.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

import db
import tasks
from deps import parse_halaman, templates

router = APIRouter()


@router.get("/tracker")
async def tracker(request: Request, per: str = "", page: str = ""):
    # The check state rides along so this page can say when the mailbox was
    # last read and surface a failed run as a banner.
    #
    # Read straight from db rather than borrowed from routes/replies.py: one
    # router importing another is what deps.py exists to prevent, and two db
    # calls are not worth widening deps for. cek_berhasil is the last
    # SUCCESSFUL run, which is not the same as cek_terakhir — a first-ever
    # check that failed must not show its own timestamp as a result.
    hal = parse_halaman(per, page, db.count_tracker_events())
    terakhir = db.last_check()
    return templates.TemplateResponse(
        request, "tracker.html",
        {
            "events": db.list_tracker_events(limit=hal["per"],
                                             offset=hal["offset"]),
            "hal": hal,
            # Replies the ladder could not fully place. This page is their only
            # surface now that /tracker/replies is gone; the template renders
            # the section only when the list is non-empty.
            #
            # Deliberately NOT grouped under an event: a tier 4 carries no
            # request_id at all, so it belongs to no batch and therefore to no
            # event. The section sits beside the table rather than inside it,
            # which is what lets the table change shape without touching it.
            "perlu_assign": db.list_unassigned(),
            "cek_terakhir": terakhir,
            "cek_berhasil": db.watermark(),
            "pernah": terakhir is not None,
        },
    )


# Declared before /tracker/{event_id} for readability only — the two cannot
# collide, since this path has three segments and that one has two. The rule
# that IS load-bearing is routes/replies.py being included first: /tracker/
# replies has two segments and would be captured as an event id.
@router.get("/tracker/batch/{request_id}")
async def tracker_batch(request: Request, request_id: int):
    permintaan = db.request_detail(request_id)
    if permintaan is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return templates.TemplateResponse(
        request, "tracker_batch.html",
        {
            "permintaan": permintaan,
            "request_id": request_id,
            "p": db.progress(request_id),
            "rows": db.list_outbox_rows(request_id),
            "spk": db.spk_by_vendor(request_id),
            # _progress.html is rendered by TWO handlers — this one and
            # send.send_progress. Both contexts need this key or the poll's
            # next swap wipes the Replies column mid-batch, the same way it
            # once wiped the SPK column.
            "balasan": db.replies_by_vendor(request_id),
            # Which vendors may be issued an SPK. Same rule as routes/spk.py
            # enforces, so the button and the route cannot disagree — and in
            # BOTH _progress.html contexts, or the poll's next swap hands back
            # a table with every SPK button open again.
            "boleh_spk": db.vendors_approved(request_id),
        },
    )


@router.post("/tracker/batch/{request_id}/retry")
async def tracker_retry(request_id: int):
    if db.request_detail(request_id) is None:
        raise HTTPException(status_code=404, detail="Request not found")

    # Only failed rows return to draft. Rows still draft from an interrupted
    # batch are picked up by the same dispatch.
    db.reset_failed_to_draft(request_id)
    tasks.schedule_batch(request_id)
    return RedirectResponse(f"/tracker/batch/{request_id}", status_code=303)


@router.get("/tracker/{event_id}")
async def tracker_event(request: Request, event_id: int):
    """One event's batches and sponsors. Not paged: an event is quoted in
    rounds, and the handful of them is the whole point of the page — a window
    onto three rows would be furniture."""
    acara = db.get_event(event_id)
    if acara is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return templates.TemplateResponse(
        request, "tracker_event.html",
        {
            "acara": acara,
            "event_id": event_id,
            "batches": db.list_requests(event_id=event_id),
            # Whether the Rundown button opens one or starts one, the same
            # question tracker_batch asks and for the same reason.
            "rundown": db.get_rundown(event_id),
            # The event's sponsors, so one job reads as one job. The list page
            # keeps its own grouping; this is the same query narrowed.
            "sponsors": db.list_sponsors(event_id=event_id),
        },
    )
