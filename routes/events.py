"""Events: create, list and edit the day an RFQ batch is quoted for.

The event owns judul_acara, tanggal_acara and lokasi, and is the only place
they are typed. Everything downstream — batches, outbox rows, SPK, the
rundown — reaches them through a join on event_id, so correcting a title here
corrects it everywhere it is printed without rewriting a single other row."""

from datetime import date

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

import db
from deps import templates

router = APIRouter()


def parse_tanggal_form(raw: str) -> tuple[str | None, str | None]:
    """Read the optional event date off this form. Returns (value, error).

    Named apart from send.parse_tanggal on purpose: that one answers "what date
    is this?" and hands back a date or None, while this one answers "may this be
    stored?" and hands back the string to write plus a message for the field.
    Two questions, two shapes — each router keeps its own field parsers.

    Blank is a real answer: an event can be booked before its day is fixed, and
    the send form only compares a deadline against the date when there is one.
    Stored as '' rather than NULL, like every other optional text field here."""
    teks = (raw or "").strip()
    if not teks:
        return "", None
    try:
        date.fromisoformat(teks)
    except ValueError:
        return None, "Use a date in YYYY-MM-DD form."
    return teks, None


def validasi_event(data: dict) -> tuple[dict, dict]:
    """Returns (parsed, errors). Empty errors means valid, and parsed then
    holds the one field that is not plain text: the date.

    No uniqueness check. events.judul_acara carries no UNIQUE, deliberately —
    an annual gathering is the same title in two different years, and two rows
    is the right answer."""
    errors = {}
    parsed = {}

    if not data["judul_acara"].strip():
        errors["judul_acara"] = "Event title is required."

    parsed["tanggal_acara"], pesan = parse_tanggal_form(data["tanggal_acara"])
    if pesan:
        errors["tanggal_acara"] = pesan

    return parsed, errors


def kosong() -> dict:
    return {"judul_acara": "", "tanggal_acara": "", "lokasi": ""}


def form_context(request: Request, acara, v: dict, errors: dict) -> dict:
    """One context for one template. acara is the row being edited, or None
    when adding — that single value is what decides the page title and the post
    target."""
    return {
        "request": request,
        "acara": acara,
        "judul": f"Edit {acara['judul_acara']}" if acara else "New event",
        "action": f"/events/{acara['id']}" if acara else "/events",
        "v": v,
        "errors": errors,
    }


@router.get("/events")
async def event_list(request: Request):
    events = db.list_events()
    return templates.TemplateResponse(
        request, "events.html", {"events": events, "jumlah": len(events)}
    )


# Declared before the parameterised routes, the same way /sponsors/new is:
# FastAPI matches in registration order and "new" is not an int.
@router.get("/events/new")
async def event_form_baru(request: Request):
    return templates.TemplateResponse(
        request, "event_form.html", form_context(request, None, kosong(), {})
    )


@router.post("/events")
async def event_create(
    request: Request,
    judul_acara: str = Form(""),
    tanggal_acara: str = Form(""),
    lokasi: str = Form(""),
):
    data = {"judul_acara": judul_acara, "tanggal_acara": tanggal_acara,
            "lokasi": lokasi}
    parsed, errors = validasi_event(data)

    if errors:
        return templates.TemplateResponse(
            request, "event_form.html",
            form_context(request, None, data, errors),
            status_code=422,
        )

    db.create_event(judul_acara.strip(), parsed["tanggal_acara"], lokasi.strip())
    return RedirectResponse("/events", status_code=303)


@router.get("/events/{event_id}/edit")
async def event_form_edit(request: Request, event_id: int):
    acara = db.get_event(event_id)
    if acara is None:
        raise HTTPException(status_code=404, detail="Event not found")

    v = {
        "judul_acara": acara["judul_acara"],
        # The date input wants ISO, which is what the column already holds.
        "tanggal_acara": acara["tanggal_acara"] or "",
        "lokasi": acara["lokasi"] or "",
    }
    return templates.TemplateResponse(
        request, "event_form.html", form_context(request, acara, v, {})
    )


@router.post("/events/{event_id}")
async def event_update(
    request: Request,
    event_id: int,
    judul_acara: str = Form(""),
    tanggal_acara: str = Form(""),
    lokasi: str = Form(""),
):
    acara = db.get_event(event_id)
    if acara is None:
        raise HTTPException(status_code=404, detail="Event not found")

    data = {"judul_acara": judul_acara, "tanggal_acara": tanggal_acara,
            "lokasi": lokasi}
    parsed, errors = validasi_event(data)

    if errors:
        return templates.TemplateResponse(
            request, "event_form.html",
            form_context(request, acara, data, errors),
            status_code=422,
        )

    db.update_event(event_id, judul_acara.strip(), parsed["tanggal_acara"],
                    lokasi.strip())
    return RedirectResponse("/events", status_code=303)
