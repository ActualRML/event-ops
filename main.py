"""Vendor RFQ Blast — app entrypoint."""

import re

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import db

app = FastAPI(title="Vendor RFQ Blast")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

NO_HP_ALLOWED = re.compile(r"^[0-9 +\-]+$")


def validasi_email(email: str) -> str | None:
    """Reject anything Gmail would accept but never deliver. Surrounding
    whitespace comes along with pasted addresses and is invisible, so it is
    trimmed first; whitespace left inside is the actual defect."""
    email = email.strip()
    if not email:
        return "Email wajib diisi."
    if any(ch.isspace() for ch in email):
        return "Email tidak boleh mengandung spasi."
    if "," in email:
        return "Email tidak boleh mengandung koma."
    if "@" not in email:
        return "Email harus mengandung @."
    if email.count("@") > 1:
        return "Email hanya boleh punya satu @."

    local, _, domain = email.partition("@")
    if not local:
        return "Bagian sebelum @ tidak boleh kosong."
    if not domain:
        return "Bagian setelah @ tidak boleh kosong."
    if ".." in email:
        return "Email tidak boleh punya titik berurutan."
    if local.startswith(".") or local.endswith("."):
        return "Bagian sebelum @ tidak boleh diawali atau diakhiri titik."
    if domain.startswith(".") or domain.endswith("."):
        return "Domain tidak boleh diawali atau diakhiri titik."
    if "." not in domain:
        return "Domain harus mengandung titik."
    return None


def validasi_vendor(data: dict, category_ids: list[int]) -> dict:
    """Returns {field: message}. Empty dict means valid."""
    errors = {}

    if not data["nama_pt"].strip():
        errors["nama_pt"] = "Nama PT wajib diisi."

    pesan = validasi_email(data["email"])
    if pesan:
        errors["email"] = pesan

    no_hp = data["no_hp"].strip()
    if no_hp and not NO_HP_ALLOWED.match(no_hp):
        errors["no_hp"] = "No HP hanya boleh berisi angka, spasi, tanda plus, dan tanda minus."

    if not category_ids:
        errors["kategori"] = "Pilih minimal satu kategori."
    else:
        dikenal = {c["id"] for c in db.list_categories()}
        if not set(category_ids) <= dikenal:
            errors["kategori"] = "Ada kategori yang tidak dikenal."

    return errors


def parse_ids(raw: list[str]) -> list[int]:
    """Form values are strings. Non-numeric input is dropped here and caught
    by validation as 'no category selected' rather than a 422."""
    ids = []
    for value in raw:
        try:
            ids.append(int(value))
        except ValueError:
            continue
    return ids


def form_context(request: Request, judul: str, action: str, data: dict,
                 selected: list[int], errors: dict) -> dict:
    return {
        "request": request,
        "judul": judul,
        "action": action,
        "v": data,
        "selected": set(selected),
        "errors": errors,
        "categories": db.list_categories(),
    }


@app.get("/")
async def index(request: Request):
    return RedirectResponse("/vendors", status_code=303)


@app.get("/vendors")
async def vendor_list(request: Request, kategori: str = ""):
    return templates.TemplateResponse(
        request,
        "vendors.html",
        {
            # Inactive vendors stay listed here; aktif_only is for the send path.
            "vendors": db.list_vendors(kategori=kategori or None, aktif_only=False),
            "categories": db.list_categories(),
            "kategori": kategori,
        },
    )


@app.get("/vendors/baru")
async def vendor_form_baru(request: Request):
    kosong = {
        "nama_pt": "", "pic_nama": "", "email": "",
        "no_hp": "", "area": "", "catatan": "", "aktif": 1,
    }
    return templates.TemplateResponse(
        request,
        "vendor_form.html",
        form_context(request, "Tambah Vendor", "/vendors", kosong, [], {}),
    )


@app.post("/vendors")
async def vendor_create(
    request: Request,
    nama_pt: str = Form(""),
    pic_nama: str = Form(""),
    email: str = Form(""),
    no_hp: str = Form(""),
    area: str = Form(""),
    catatan: str = Form(""),
    aktif: str = Form(None),
    kategori_ids: list[str] = Form([]),
):
    data = {
        "nama_pt": nama_pt, "pic_nama": pic_nama, "email": email,
        "no_hp": no_hp, "area": area, "catatan": catatan,
        "aktif": 1 if aktif is not None else 0,
    }
    ids = parse_ids(kategori_ids)
    errors = validasi_vendor(data, ids)

    if errors:
        return templates.TemplateResponse(
            request,
            "vendor_form.html",
            form_context(request, "Tambah Vendor", "/vendors", data, ids, errors),
            status_code=422,
        )

    vendor_id = db.create_vendor(
        data["nama_pt"].strip(), data["pic_nama"].strip(), data["email"].strip(),
        data["no_hp"].strip(), data["area"].strip(), data["catatan"].strip(),
        data["aktif"],
    )
    db.set_vendor_categories(vendor_id, ids)
    return RedirectResponse("/vendors", status_code=303)


@app.get("/vendors/{vendor_id}/edit")
async def vendor_form_edit(request: Request, vendor_id: int):
    vendor = db.get_vendor(vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor tidak ditemukan")

    data = {
        "nama_pt": vendor["nama_pt"] or "",
        "pic_nama": vendor["pic_nama"] or "",
        "email": vendor["email"] or "",
        "no_hp": vendor["no_hp"] or "",
        "area": vendor["area"] or "",
        "catatan": vendor["catatan"] or "",
        "aktif": vendor["aktif"],
    }
    return templates.TemplateResponse(
        request,
        "vendor_form.html",
        form_context(
            request,
            f"Edit {vendor['nama_pt']}",
            f"/vendors/{vendor_id}",
            data,
            db.get_vendor_categories(vendor_id),
            {},
        ),
    )


@app.post("/vendors/{vendor_id}")
async def vendor_update(
    request: Request,
    vendor_id: int,
    nama_pt: str = Form(""),
    pic_nama: str = Form(""),
    email: str = Form(""),
    no_hp: str = Form(""),
    area: str = Form(""),
    catatan: str = Form(""),
    aktif: str = Form(None),
    kategori_ids: list[str] = Form([]),
):
    if db.get_vendor(vendor_id) is None:
        raise HTTPException(status_code=404, detail="Vendor tidak ditemukan")

    data = {
        "nama_pt": nama_pt, "pic_nama": pic_nama, "email": email,
        "no_hp": no_hp, "area": area, "catatan": catatan,
        "aktif": 1 if aktif is not None else 0,
    }
    ids = parse_ids(kategori_ids)
    errors = validasi_vendor(data, ids)

    if errors:
        return templates.TemplateResponse(
            request,
            "vendor_form.html",
            form_context(
                request, f"Edit {nama_pt}", f"/vendors/{vendor_id}", data, ids, errors
            ),
            status_code=422,
        )

    db.update_vendor(
        vendor_id,
        data["nama_pt"].strip(), data["pic_nama"].strip(), data["email"].strip(),
        data["no_hp"].strip(), data["area"].strip(), data["catatan"].strip(),
        data["aktif"],
    )
    db.set_vendor_categories(vendor_id, ids)
    return RedirectResponse("/vendors", status_code=303)


@app.get("/kirim")
async def kirim(request: Request):
    categories = db.list_categories()
    category_id = categories[0]["id"] if categories else None
    return templates.TemplateResponse(
        request,
        "kirim.html",
        {
            "categories": categories,
            "category_id": category_id,
            # Selection starts empty; it lives in the page, not the session.
            "vendors": db.list_vendors_by_category(category_id) if category_id else [],
            "selected": set(),
        },
    )


@app.get("/kirim/vendors")
async def kirim_vendors(
    request: Request,
    category_id: int,
    vendor_ids: list[str] = Query([]),
):
    """HTMX partial. vendor_ids arrives from the hidden container so a vendor
    already picked under another category renders checked here too."""
    return templates.TemplateResponse(
        request,
        "_vendor_list.html",
        {
            "vendors": db.list_vendors_by_category(category_id),
            "selected": set(parse_ids(vendor_ids)),
        },
    )


@app.post("/vendors/{vendor_id}/aktif")
async def vendor_toggle_aktif(vendor_id: int, kategori: str = Form("")):
    vendor = db.get_vendor(vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor tidak ditemukan")

    db.set_vendor_aktif(vendor_id, 0 if vendor["aktif"] else 1)
    tujuan = f"/vendors?kategori={kategori}" if kategori else "/vendors"
    return RedirectResponse(tujuan, status_code=303)
