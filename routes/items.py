"""Item catalog: create, list, edit and archive priced catalog entries.

Two prices per item. cost is what procurement pays a vendor for one unit;
value is the sponsor-facing rate for the same unit. The ratio between them is
computed on the way out and never stored — see the Multiple column."""

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

import db
from core import dokumen
from deps import parse_halaman, parse_harga, templates

router = APIRouter()


def validasi_item(data: dict, item_id: int | None) -> tuple[dict, dict]:
    """Returns (parsed, errors). Empty errors means valid, and parsed then
    holds the two fields that are not plain text: the amounts. item_id is the
    row being edited, so it does not collide with its own name; None on
    create."""
    errors = {}
    parsed = {}

    nama = data["nama"].strip()
    if not nama:
        errors["nama"] = "Item name is required."
    elif db.item_name_exists(nama, exclude_id=item_id):
        errors["nama"] = f"Item “{nama}” already exists."

    # Zero is allowed on both: an item carried at no cost, or one offered to a
    # sponsor at none, is a real entry rather than a mistake.
    for field, label in (("cost", "Cost"), ("value", "Value")):
        parsed[field], pesan = parse_harga(data[field], label=label,
                                           allow_zero=True)
        if pesan:
            errors[field] = pesan

    return parsed, errors


def kosong() -> dict:
    return {"nama": "", "satuan": "", "cost": "", "value": "", "catatan": ""}


def form_context(request: Request, item, v: dict, errors: dict) -> dict:
    """One context for one template. item is the row being edited, or None when
    issuing a new one — that single value is what decides the page title, the
    post target, and whether the archive block is on the page at all."""
    return {
        "request": request,
        "item": item,
        "judul": f"Edit {item['nama']}" if item else "New item",
        "action": f"/items/{item['id']}" if item else "/items",
        "v": v,
        "errors": errors,
    }


@router.get("/items")
async def item_list(request: Request, arsip: str = "", per: str = "",
                    page: str = ""):
    hal = parse_halaman(per, page, db.count_catalog_items(bool(arsip)))
    items = db.list_catalog_items(include_inactive=bool(arsip),
                                  limit=hal["per"], offset=hal["offset"])
    # Counted in SQL, not from `items`. They used to be summed over the fetched
    # rows, which was exact while every row was fetched — with a page of 25 out
    # of 120 it would report the page and call it the catalog.
    aktif = db.count_catalog_items(False)
    return templates.TemplateResponse(
        request,
        "items.html",
        {
            "items": items,
            "arsip": bool(arsip),
            "hal": hal,
            "jumlah_aktif": aktif,
            "jumlah_arsip": db.count_catalog_items(True) - aktif,
        },
    )


@router.get("/items/new")
async def item_form_baru(request: Request):
    return templates.TemplateResponse(
        request, "item_form.html", form_context(request, None, kosong(), {})
    )


@router.post("/items")
async def item_create(
    request: Request,
    nama: str = Form(""),
    satuan: str = Form(""),
    cost: str = Form(""),
    value: str = Form(""),
    catatan: str = Form(""),
):
    data = {"nama": nama, "satuan": satuan, "cost": cost, "value": value,
            "catatan": catatan}
    parsed, errors = validasi_item(data, None)

    if errors:
        return templates.TemplateResponse(
            request, "item_form.html",
            form_context(request, None, data, errors),
            status_code=422,
        )

    db.create_catalog_item(
        nama.strip(), satuan.strip(), parsed["cost"], parsed["value"],
        catatan.strip(),
    )
    return RedirectResponse("/items", status_code=303)


@router.get("/items/{item_id}/edit")
async def item_form_edit(request: Request, item_id: int):
    item = db.get_catalog_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    v = {
        "nama": item["nama"],
        "satuan": item["satuan"] or "",
        # Read back in the shape the field accepts, the same way the SPK form
        # reads its amount back.
        "cost": dokumen.format_rupiah(item["cost"], prefix=False),
        "value": dokumen.format_rupiah(item["value"], prefix=False),
        "catatan": item["catatan"] or "",
    }
    return templates.TemplateResponse(
        request, "item_form.html", form_context(request, item, v, {})
    )


@router.post("/items/{item_id}")
async def item_update(
    request: Request,
    item_id: int,
    nama: str = Form(""),
    satuan: str = Form(""),
    cost: str = Form(""),
    value: str = Form(""),
    catatan: str = Form(""),
):
    item = db.get_catalog_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    data = {"nama": nama, "satuan": satuan, "cost": cost, "value": value,
            "catatan": catatan}
    parsed, errors = validasi_item(data, item_id)

    if errors:
        return templates.TemplateResponse(
            request, "item_form.html",
            form_context(request, item, data, errors),
            status_code=422,
        )

    db.update_catalog_item(
        item_id, nama.strip(), satuan.strip(), parsed["cost"],
        parsed["value"], catatan.strip(),
    )
    return RedirectResponse("/items", status_code=303)


@router.post("/items/{item_id}/arsip")
async def item_toggle_arsip(item_id: int):
    """Archive or restore, from the item's own edit page — it is a rare action
    and has no place in every row of the list."""
    item = db.get_catalog_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    db.set_catalog_item_aktif(item_id, 0 if item["aktif"] else 1)
    return RedirectResponse("/items", status_code=303)
