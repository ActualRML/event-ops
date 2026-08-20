"""Send history: the batch list, one batch's detail, and retry."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

import db
import tasks
from deps import templates

router = APIRouter()


@router.get("/tracker")
async def tracker(request: Request):
    # The check state rides along so this page can say when the mailbox was
    # last read and surface a failed run as a banner.
    #
    # Read straight from db rather than borrowed from routes/replies.py: one
    # router importing another is what deps.py exists to prevent, and two db
    # calls are not worth widening deps for. cek_berhasil is the last
    # SUCCESSFUL run, which is not the same as cek_terakhir — a first-ever
    # check that failed must not show its own timestamp as a result.
    terakhir = db.last_check()
    return templates.TemplateResponse(
        request, "tracker.html",
        {
            "requests": db.list_requests(),
            "cek_terakhir": terakhir,
            "cek_berhasil": db.watermark(),
            "pernah": terakhir is not None,
        },
    )


@router.get("/tracker/{request_id}")
async def tracker_detail(request: Request, request_id: int):
    permintaan = db.request_detail(request_id)
    if permintaan is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return templates.TemplateResponse(
        request, "tracker_detail.html",
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
            # Only so the Rundown button can say whether it opens one or
            # starts one. The rundown page itself is reached by event id and
            # loads its own row.
            "rundown": db.get_rundown(permintaan["event_id"]),
        },
    )


@router.post("/tracker/{request_id}/retry")
async def tracker_retry(request_id: int):
    if db.request_detail(request_id) is None:
        raise HTTPException(status_code=404, detail="Request not found")

    # Only failed rows return to draft. Rows still draft from an interrupted
    # batch are picked up by the same dispatch.
    db.reset_failed_to_draft(request_id)
    tasks.schedule_batch(request_id)
    return RedirectResponse(f"/tracker/{request_id}", status_code=303)
