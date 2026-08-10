"""Send history: the batch list, one batch's detail, and retry."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

import db
import tasks
from deps import peta_spk, templates

router = APIRouter()


@router.get("/tracker")
async def tracker(request: Request):
    return templates.TemplateResponse(
        request, "tracker.html", {"requests": db.list_requests()}
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
            "spk": peta_spk(request_id),
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
