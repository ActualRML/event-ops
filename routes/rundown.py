"""Rundown: the running order for one event.

No schedule is ever stored. Every start and end time on the page comes from
core.rundown, recomputed from jam_mulai and the item durations on each
render — so changing the start time reschedules the whole event without
rewriting a single item row.

One page handles everything. Editing an item reopens the same add form with
?item=<id>, rather than a second page: the fields are identical, and a
rundown is edited by nudging rows around, not by visiting a record."""

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

import db
from core import rundown as jadwal
from deps import templates

router = APIRouter()

# A single item is a slot inside one event. Anything longer is a typo — most
# often minutes typed where hours were meant.
DURASI_MAKS = 24 * 60


def parse_jam(raw: str, wajib: bool, label: str):
    """Read one HH:MM field. Returns (value or None, error or None).

    The parse is core's, so the page accepts exactly what the schedule
    arithmetic accepts and rejects the rest with one message."""
    teks = (raw or "").strip()
    if not teks:
        return None, (f"{label} is required." if wajib else None)
    try:
        jadwal.ke_menit(teks)
    except ValueError:
        return None, "Use HH:MM, e.g. 09:00."
    return teks, None


def parse_durasi(raw: str):
    """Read the duration field as whole minutes."""
    teks = (raw or "").strip()
    if not teks:
        return None, "Duration is required."
    if not teks.isdigit():
        return None, "Duration must be a whole number of minutes."

    nilai = int(teks)
    if nilai <= 0:
        return None, "Duration must be greater than zero."
    if nilai > DURASI_MAKS:
        return None, "Duration must be under 24 hours."
    return nilai, None


def muat(request_id: int):
    """The request and its rundown, if it has one yet."""
    permintaan = db.request_detail(request_id)
    if permintaan is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return permintaan, db.get_rundown(request_id)


def muat_item(rundown, item_id: int):
    """One item, checked against this rundown. An id from another event is a
    404, not somebody else's row rendered into this page."""
    if rundown is None:
        raise HTTPException(status_code=404, detail="No rundown for this request")
    for item in db.list_items(rundown["id"]):
        if item["id"] == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found in this rundown")


def rundown_context(request_id: int, permintaan, rundown, *, item_id=None,
                    v_atur=None, v_item=None, errors=None) -> dict:
    """Everything the template renders.

    v_atur and v_item carry back what was typed on a validation bounce; when
    they are None the stored values are shown instead."""
    items = db.list_items(rundown["id"]) if rundown else []

    hasil = None
    baris = []
    if rundown:
        hasil = jadwal.hitung_jadwal(
            rundown["jam_mulai"],
            [i["durasi_menit"] for i in items],
            rundown["batas_venue"],
        )
        # zip, not index arithmetic: hitung_jadwal returns one row per
        # duration in the order it was given, so the two lists always align.
        baris = [
            {"item": item, "mulai": waktu["mulai"], "selesai": waktu["selesai"]}
            for item, waktu in zip(items, hasil["baris"])
        ]

    if v_atur is None:
        v_atur = {
            "jam_mulai": rundown["jam_mulai"] if rundown else "",
            "batas_venue": (rundown["batas_venue"] or "") if rundown else "",
        }

    # Edit mode prefills from the row being edited; add mode starts empty.
    if v_item is None:
        sedang_edit = muat_item(rundown, item_id) if item_id else None
        v_item = {
            "kegiatan": sedang_edit["kegiatan"] if sedang_edit else "",
            "durasi_menit": str(sedang_edit["durasi_menit"]) if sedang_edit else "",
            "pic": (sedang_edit["pic"] or "") if sedang_edit else "",
            "catatan": (sedang_edit["catatan"] or "") if sedang_edit else "",
        }

    return {
        "request_id": request_id,
        "permintaan": permintaan,
        "rundown": rundown,
        "baris": baris,
        "jadwal": hasil,
        "total_menit": sum(i["durasi_menit"] for i in items),
        "item_id": item_id,
        "v_atur": v_atur,
        "v_item": v_item,
        "errors": errors or {},
    }


@router.get("/tracker/{request_id}/rundown")
async def rundown_page(request: Request, request_id: int, item: int | None = None):
    permintaan, r = muat(request_id)
    # A stale ?item= from a deleted row would otherwise 404 the whole page.
    if item is not None and (r is None or not any(
            i["id"] == item for i in db.list_items(r["id"]))):
        return RedirectResponse(f"/tracker/{request_id}/rundown", status_code=303)

    return templates.TemplateResponse(
        request, "rundown.html",
        rundown_context(request_id, permintaan, r, item_id=item),
    )


@router.post("/tracker/{request_id}/rundown")
async def rundown_settings(
    request: Request,
    request_id: int,
    jam_mulai: str = Form(""),
    batas_venue: str = Form(""),
):
    """Create the rundown, or overwrite its start time and venue limit."""
    permintaan, r = muat(request_id)
    v_atur = {"jam_mulai": jam_mulai, "batas_venue": batas_venue}

    errors = {}
    mulai, pesan = parse_jam(jam_mulai, True, "Start time")
    if pesan:
        errors["jam_mulai"] = pesan
    batas, pesan = parse_jam(batas_venue, False, "Venue limit")
    if pesan:
        errors["batas_venue"] = pesan

    if errors:
        return templates.TemplateResponse(
            request, "rundown.html",
            rundown_context(request_id, permintaan, r, v_atur=v_atur,
                            errors=errors),
            status_code=422,
        )

    if r is None:
        db.create_rundown(request_id, mulai, batas)
    else:
        db.update_rundown(r["id"], mulai, batas)
    return RedirectResponse(f"/tracker/{request_id}/rundown", status_code=303)


@router.post("/tracker/{request_id}/rundown/items")
async def item_add(
    request: Request,
    request_id: int,
    kegiatan: str = Form(""),
    durasi_menit: str = Form(""),
    pic: str = Form(""),
    catatan: str = Form(""),
):
    permintaan, r = muat(request_id)
    if r is None:
        raise HTTPException(status_code=404, detail="No rundown for this request")

    v_item = {"kegiatan": kegiatan, "durasi_menit": durasi_menit,
              "pic": pic, "catatan": catatan}
    errors = {}
    if not kegiatan.strip():
        errors["kegiatan"] = "Activity is required."
    menit, pesan = parse_durasi(durasi_menit)
    if pesan:
        errors["durasi_menit"] = pesan

    if errors:
        return templates.TemplateResponse(
            request, "rundown.html",
            rundown_context(request_id, permintaan, r, v_item=v_item,
                            errors=errors),
            status_code=422,
        )

    db.add_item(r["id"], kegiatan.strip(), menit, pic.strip(), catatan.strip())
    return RedirectResponse(f"/tracker/{request_id}/rundown", status_code=303)


@router.post("/tracker/{request_id}/rundown/items/{item_id}")
async def item_update(
    request: Request,
    request_id: int,
    item_id: int,
    kegiatan: str = Form(""),
    durasi_menit: str = Form(""),
    pic: str = Form(""),
    catatan: str = Form(""),
):
    permintaan, r = muat(request_id)
    muat_item(r, item_id)

    v_item = {"kegiatan": kegiatan, "durasi_menit": durasi_menit,
              "pic": pic, "catatan": catatan}
    errors = {}
    if not kegiatan.strip():
        errors["kegiatan"] = "Activity is required."
    menit, pesan = parse_durasi(durasi_menit)
    if pesan:
        errors["durasi_menit"] = pesan

    if errors:
        return templates.TemplateResponse(
            request, "rundown.html",
            rundown_context(request_id, permintaan, r, item_id=item_id,
                            v_item=v_item, errors=errors),
            status_code=422,
        )

    db.update_item(item_id, kegiatan.strip(), menit, pic.strip(), catatan.strip())
    return RedirectResponse(f"/tracker/{request_id}/rundown", status_code=303)


@router.post("/tracker/{request_id}/rundown/items/{item_id}/delete")
async def item_delete(request_id: int, item_id: int):
    _, r = muat(request_id)
    muat_item(r, item_id)
    db.delete_item(item_id)
    return RedirectResponse(f"/tracker/{request_id}/rundown", status_code=303)


@router.post("/tracker/{request_id}/rundown/items/{item_id}/move")
async def item_move(request_id: int, item_id: int, direction: str = Form("")):
    """Swap one item with its neighbour. Already at the end is not an error —
    db.move_item returns False and the page simply comes back unchanged."""
    _, r = muat(request_id)
    muat_item(r, item_id)
    db.move_item(item_id, direction)
    return RedirectResponse(f"/tracker/{request_id}/rundown", status_code=303)
