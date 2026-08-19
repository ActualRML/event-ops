"""Sponsors and their packages: what a sponsor pays, and what they get for it.

Two numbers per package line, both snapshotted when the line is added and never
re-read from the catalog: cost is what the line costs us, value the rate the
sponsor is shown. Everything on the summary strip is arithmetic on those two
plus the sponsor's own kontribusi, worked out on the way to the template.

The printed sheet is the one page here a sponsor reads, so it is Indonesian and
it is built from a context that carries no cost at all — see sponsor_print."""

import sqlite3

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

import db
from core import dokumen
from deps import parse_harga, templates

router = APIRouter()

# What a quantity field says when it is not a number. The parse is the money
# parser's — grouped digits and all — but the example has to be a count.
CONTOH_QTY = "a whole number of units, e.g. 12"


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


def muat_detail(request: Request, sponsor_id: int, errors: dict) -> dict:
    """Everything the staff detail page renders, rebuilt from the database on
    every add and every remove — the totals are never carried in the session or
    patched in the browser."""
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
    }


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
    qty: str = Form(""),
):
    if db.get_sponsor(sponsor_id) is None:
        raise HTTPException(status_code=404, detail="Sponsor not found")

    errors = {}
    # Only what the picker actually offered: active, and not already on this
    # package. A hand-posted id for an archived or duplicated item is rejected
    # here rather than reaching the UNIQUE.
    boleh = {i["id"] for i in db.items_available_for_sponsor(sponsor_id)}
    try:
        pilihan = int(item_id)
    except ValueError:
        pilihan = None
    if pilihan is None:
        errors["item_id"] = "Choose an item."
    elif pilihan not in boleh:
        errors["item_id"] = "That item is not available for this sponsor."

    jumlah, pesan = parse_harga(qty, label="Quantity", contoh=CONTOH_QTY)
    if pesan:
        errors["qty"] = pesan

    if errors:
        konteks = muat_detail(request, sponsor_id, errors)
        # The submitted values ride back so the row is not retyped.
        konteks["v"] = {"item_id": item_id, "qty": qty}
        return templates.TemplateResponse(
            request, "sponsor_detail.html", konteks, status_code=422
        )

    try:
        db.add_sponsor_item(sponsor_id, pilihan, jumlah)
    except sqlite3.IntegrityError:
        # UNIQUE(sponsor_id, item_id): a second submit got here first. The line
        # exists, which is what was wanted, so this is not an error to show.
        pass
    return RedirectResponse(f"/sponsors/{sponsor_id}", status_code=303)


@router.post("/sponsors/{sponsor_id}/items/{line_id}/hapus")
async def sponsor_item_remove(sponsor_id: int, line_id: int):
    if db.get_sponsor(sponsor_id) is None:
        raise HTTPException(status_code=404, detail="Sponsor not found")
    if not db.remove_sponsor_item(line_id):
        raise HTTPException(status_code=404, detail="Line not found")
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
