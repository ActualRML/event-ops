"""Sponsors and their packages: what a sponsor pays, and what they get for it.

Two numbers per package line, both snapshotted when the line is added and never
re-read from the catalog: cost is what the line costs us, value the rate the
sponsor is shown. Everything on the summary strip is arithmetic on those two
plus the sponsor's own kontribusi, worked out on the way to the template.

The printed sheet is the one page here a sponsor reads, so it is Indonesian and
it is built from a context that carries no cost at all — see sponsor_print."""

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

import db
from core import dokumen
from deps import parse_harga, templates

router = APIRouter()

# A package line is a count of things at one event. Four figures is already
# absurd for a booth package; the cap exists so a typo in the box cannot write
# a number the totals row has to render.
QTY_MAKS = 9999


def parse_qty(raw: str) -> int | None:
    """Read the typed quantity box. Returns a clamped qty, or None when there
    is no number in it at all.

    Clamped rather than rejected: the box is edited in place beside a stepper,
    with nowhere to put an error message, so an out-of-range number becomes the
    nearest allowed one. A blank or non-numeric entry leaves the line alone."""
    teks = (raw or "").strip().replace(".", "").replace(",", "")
    if not teks.isdigit():
        return None
    return max(1, min(QTY_MAKS, int(teks)))


def muat_baris(sponsor_id: int, line_id: int):
    """One package line, checked against the sponsor in the URL. A line id
    belonging to another sponsor is a 404, not somebody else's row edited
    through this page."""
    baris = db.get_sponsor_item(line_id)
    if baris is None or baris["sponsor_id"] != sponsor_id:
        raise HTTPException(status_code=404, detail="Line not found")
    return baris


def parse_persen(raw: str) -> tuple[int | None, str | None]:
    """Read the budget share. A percentage, so it is bounded at both ends: 0
    would mean no package is affordable at all, and over 100 would mean
    spending more than the sponsor pays before a single line is added."""
    teks = str(raw).strip().rstrip("%").strip()
    if not teks:
        return None, "Budget share is required."
    if not teks.isdigit():
        return None, "Budget share must be a whole number between 1 and 100."
    nilai = int(teks)
    if not 1 <= nilai <= 100:
        return None, "Budget share must be between 1 and 100."
    return nilai, None


def parse_event(raw: str) -> tuple[int | None, str | None]:
    """Read the event picker. Required — a sponsor sponsors something, and the
    package is priced for that specific day."""
    teks = str(raw).strip()
    if not teks:
        return None, "Choose an event."
    try:
        event_id = int(teks)
    except ValueError:
        return None, "Choose an event from the list."
    if db.get_event(event_id) is None:
        return None, "That event is unknown."
    return event_id, None


def validasi_sponsor(data: dict, sponsor_id: int | None,
                     event_id: int | None) -> tuple[dict, dict]:
    """Returns (parsed, errors). event_id is already resolved by the caller,
    because the name's uniqueness is scoped to it and cannot be checked until
    it is known. sponsor_id is the row being edited, so it does not collide
    with its own name; None on create."""
    errors = {}
    parsed = {}

    nama = data["nama_pt"].strip()
    if not nama:
        errors["nama_pt"] = "Sponsor name is required."
    elif event_id is not None and db.sponsor_name_exists(
        event_id, nama, exclude_id=sponsor_id
    ):
        errors["nama_pt"] = f"“{nama}” already sponsors this event."

    parsed["kontribusi"], pesan = parse_harga(data["kontribusi"],
                                              label="Contribution")
    if pesan:
        errors["kontribusi"] = pesan

    parsed["persen_budget"], pesan = parse_persen(data["persen_budget"])
    if pesan:
        errors["persen_budget"] = pesan

    return parsed, errors


def ringkasan(sponsor, totals: dict) -> dict:
    """The summary strip. Every value here is derived and none is stored.

    budget floors rather than rounds: it is a spending ceiling in whole rupiah,
    and rounding one up would authorise a rupiah nobody agreed to. sisa is
    allowed to go negative — going over budget is a decision staff are entitled
    to make, so it is reported, not prevented."""
    budget = sponsor["kontribusi"] * sponsor["persen_budget"] // 100
    cost_pakai = totals["cost_pakai"]
    return {
        "budget": budget,
        "cost_pakai": cost_pakai,
        "sisa": budget - cost_pakai,
        "value_total": totals["value_total"],
        # kontribusi is CHECK(> 0), so this cannot divide by zero.
        "multiple": totals["value_total"] / sponsor["kontribusi"],
    }


def kosong() -> dict:
    return {"event_id": "", "nama_pt": "", "kontribusi": "",
            "persen_budget": "12", "catatan": ""}


def form_context(request: Request, sponsor, v: dict, errors: dict) -> dict:
    """One context for one template, both modes. sponsor is the row being
    edited, or None when adding — that single value decides the title and the
    post target, and whether the event picker is offered at all."""
    return {
        "request": request,
        "sponsor": sponsor,
        "judul": f"Edit {sponsor['nama_pt']}" if sponsor else "New sponsor",
        "action": f"/sponsors/{sponsor['id']}" if sponsor else "/sponsors",
        "v": v,
        "errors": errors,
        "events": db.list_events(),
    }


def muat_detail(request: Request, sponsor_id: int, errors: dict,
                oob: bool = False) -> dict:
    """Everything the staff detail page renders, rebuilt from the database on
    every add, every remove and every quantity change — the totals are never
    carried in the session or patched in the browser.

    oob is for a quantity swap, which returns the package table alone: it tells
    the table partial to bring the summary with it out of band, since the
    totals and the budget warning both move when a quantity does."""
    sponsor = db.get_sponsor(sponsor_id)
    if sponsor is None:
        raise HTTPException(status_code=404, detail="Sponsor not found")

    return {
        "request": request,
        "sponsor": sponsor,
        "baris": db.list_sponsor_items(sponsor_id),
        "r": ringkasan(sponsor, db.sponsor_totals(sponsor_id)),
        "pilihan": db.items_available_for_sponsor(sponsor_id),
        "errors": errors,
        "oob": oob,
    }


def jawab_qty(request: Request, sponsor_id: int):
    """What a quantity change sends back.

    HTMX gets the package table plus the summary out of band. A plain form post
    — no JS, so the box's own action fired — gets a redirect to the page it
    came from, which re-renders both from the same context builder."""
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            request, "_sponsor_package.html",
            muat_detail(request, sponsor_id, {}, oob=True),
        )
    return RedirectResponse(f"/sponsors/{sponsor_id}", status_code=303)


@router.get("/sponsors")
async def sponsor_list(request: Request):
    sponsors = db.list_sponsors()
    # Grouped in Python rather than in the template: the rows arrive already
    # ordered by event, so this only has to break them where the event changes.
    kelompok: list[dict] = []
    for s in sponsors:
        if not kelompok or kelompok[-1]["event_id"] != s["event_id"]:
            kelompok.append({
                "event_id": s["event_id"],
                "judul_acara": s["judul_acara"],
                "tanggal_acara": s["tanggal_acara"],
                "baris": [],
            })
        kelompok[-1]["baris"].append(
            {"s": s, "r": ringkasan(s, {"cost_pakai": s["cost_pakai"],
                                        "value_total": s["value_total"]})}
        )

    return templates.TemplateResponse(
        request, "sponsors.html",
        {"kelompok": kelompok, "jumlah": len(sponsors)},
    )


# Declared before /sponsors/{sponsor_id}: FastAPI matches in registration
# order, and "new" is not an int, so the parameterised route would 422 it.
@router.get("/sponsors/new")
async def sponsor_form_baru(request: Request):
    return templates.TemplateResponse(
        request, "sponsor_form.html", form_context(request, None, kosong(), {})
    )


@router.post("/sponsors")
async def sponsor_create(
    request: Request,
    event_id: str = Form(""),
    nama_pt: str = Form(""),
    kontribusi: str = Form(""),
    persen_budget: str = Form(""),
    catatan: str = Form(""),
):
    data = {"event_id": event_id, "nama_pt": nama_pt, "kontribusi": kontribusi,
            "persen_budget": persen_budget, "catatan": catatan}
    acara, pesan_acara = parse_event(event_id)
    parsed, errors = validasi_sponsor(data, None, acara)
    if pesan_acara:
        errors["event_id"] = pesan_acara

    if errors:
        return templates.TemplateResponse(
            request, "sponsor_form.html",
            form_context(request, None, data, errors),
            status_code=422,
        )

    sponsor_id = db.create_sponsor(
        acara, nama_pt.strip(), parsed["kontribusi"],
        parsed["persen_budget"], catatan.strip(),
    )
    return RedirectResponse(f"/sponsors/{sponsor_id}", status_code=303)


@router.get("/sponsors/{sponsor_id}")
async def sponsor_detail(request: Request, sponsor_id: int):
    return templates.TemplateResponse(
        request, "sponsor_detail.html", muat_detail(request, sponsor_id, {})
    )


@router.get("/sponsors/{sponsor_id}/edit")
async def sponsor_form_edit(request: Request, sponsor_id: int):
    sponsor = db.get_sponsor(sponsor_id)
    if sponsor is None:
        raise HTTPException(status_code=404, detail="Sponsor not found")

    v = {
        "event_id": str(sponsor["event_id"]),
        "nama_pt": sponsor["nama_pt"],
        # Read back in the shape the field accepts, as the SPK form does.
        "kontribusi": dokumen.format_rupiah(sponsor["kontribusi"], prefix=False),
        "persen_budget": str(sponsor["persen_budget"]),
        "catatan": sponsor["catatan"] or "",
    }
    return templates.TemplateResponse(
        request, "sponsor_form.html", form_context(request, sponsor, v, {})
    )


@router.post("/sponsors/{sponsor_id}")
async def sponsor_update(
    request: Request,
    sponsor_id: int,
    nama_pt: str = Form(""),
    kontribusi: str = Form(""),
    persen_budget: str = Form(""),
    catatan: str = Form(""),
):
    sponsor = db.get_sponsor(sponsor_id)
    if sponsor is None:
        raise HTTPException(status_code=404, detail="Sponsor not found")

    # The event is not editable, so uniqueness is checked against the one the
    # sponsor already belongs to.
    data = {"event_id": str(sponsor["event_id"]), "nama_pt": nama_pt,
            "kontribusi": kontribusi, "persen_budget": persen_budget,
            "catatan": catatan}
    parsed, errors = validasi_sponsor(data, sponsor_id, sponsor["event_id"])

    if errors:
        return templates.TemplateResponse(
            request, "sponsor_form.html",
            form_context(request, sponsor, data, errors),
            status_code=422,
        )

    db.update_sponsor(
        sponsor_id, nama_pt.strip(), parsed["kontribusi"],
        parsed["persen_budget"], catatan.strip(),
    )
    return RedirectResponse(f"/sponsors/{sponsor_id}", status_code=303)


@router.post("/sponsors/{sponsor_id}/items")
async def sponsor_item_add(
    request: Request,
    sponsor_id: int,
    item_id: str = Form(""),
):
    """Add one line at qty 1. The quantity is adjusted in the table afterwards,
    which is why this form no longer asks for one."""
    if db.get_sponsor(sponsor_id) is None:
        raise HTTPException(status_code=404, detail="Sponsor not found")

    errors = {}
    # Only what the picker actually offered: active, and not already on this
    # package. A hand-posted id for an archived item is rejected here.
    boleh = {i["id"] for i in db.items_available_for_sponsor(sponsor_id)}
    try:
        pilihan = int(item_id)
    except ValueError:
        pilihan = None
    if pilihan is None:
        errors["item_id"] = "Choose an item."
    elif pilihan not in boleh:
        errors["item_id"] = "That item is not available for this sponsor."

    if errors:
        konteks = muat_detail(request, sponsor_id, errors)
        # The submitted value rides back so the picker is not reset.
        konteks["v"] = {"item_id": item_id}
        return templates.TemplateResponse(
            request, "sponsor_detail.html", konteks, status_code=422
        )

    # No IntegrityError to catch any more: add_sponsor_item upserts, so a race
    # that gets two requests past the check above increments once rather than
    # raising, and a second row still cannot exist.
    db.add_sponsor_item(sponsor_id, pilihan)
    return RedirectResponse(f"/sponsors/{sponsor_id}", status_code=303)


@router.post("/sponsors/{sponsor_id}/items/{line_id}/qty")
async def sponsor_item_qty_bump(
    request: Request,
    sponsor_id: int,
    line_id: int,
    delta: str = Form("0"),
):
    """The − and + buttons. A delta, never an absolute value: the write is
    `qty = qty + ?` in SQL, so two clicks that overlap are two steps.

    A step that would take the line below 1 is a no-op — the row is not
    removed and CHECK(qty > 0) is never reached. Remove is the only delete."""
    muat_baris(sponsor_id, line_id)
    try:
        langkah = int(delta)
    except ValueError:
        langkah = 0
    # One step at a time. A hand-posted delta of 500 is not what the two
    # buttons on the page can produce, and the typed box is the way to jump.
    if langkah in (-1, 1):
        db.bump_sponsor_item_qty(line_id, langkah)
    return jawab_qty(request, sponsor_id)


@router.post("/sponsors/{sponsor_id}/items/{line_id}/qty-exact")
async def sponsor_item_qty_set(
    request: Request,
    sponsor_id: int,
    line_id: int,
    qty: str = Form(""),
):
    """The typed box. Absolute, and therefore idempotent — which is why it can
    safely fire on both change and submit without a double edit mattering."""
    muat_baris(sponsor_id, line_id)
    jumlah = parse_qty(qty)
    if jumlah is not None:
        db.set_sponsor_item_qty(line_id, jumlah)
    return jawab_qty(request, sponsor_id)


@router.post("/sponsors/{sponsor_id}/items/{line_id}/hapus")
async def sponsor_item_remove(sponsor_id: int, line_id: int):
    """Delete one line. Ownership is checked first, the same way the two
    quantity routes check it: a line id belonging to another sponsor is a 404,
    not a deletion carried out on somebody else's package through this URL."""
    muat_baris(sponsor_id, line_id)
    db.remove_sponsor_item(line_id)
    return RedirectResponse(f"/sponsors/{sponsor_id}", status_code=303)


@router.get("/sponsors/{sponsor_id}/cetak")
async def sponsor_print(request: Request, sponsor_id: int):
    """The sheet the sponsor reads. Indonesian, and deliberately built from a
    context that has no cost in it at all: what the package costs us, what the
    budget was, how much is left and the multiple are all internal, and the way
    to guarantee none of them prints is to never hand them to the template."""
    sponsor = db.get_sponsor(sponsor_id)
    if sponsor is None:
        raise HTTPException(status_code=404, detail="Sponsor not found")

    baris = [
        {"nama": b["nama"], "satuan": b["satuan"], "qty": b["qty"],
         "value": b["value"], "nilai": b["qty"] * b["value"]}
        for b in db.list_sponsor_items(sponsor_id)
    ]
    return templates.TemplateResponse(
        request,
        "sponsor_print.html",
        {
            "sponsor_id": sponsor_id,
            "nama_pt": sponsor["nama_pt"],
            "kontribusi": sponsor["kontribusi"],
            "judul_acara": sponsor["judul_acara"],
            "tanggal_acara": sponsor["tanggal_acara"],
            "lokasi": sponsor["lokasi"],
            "baris": baris,
            "nilai_total": sum(b["nilai"] for b in baris),
        },
    )
