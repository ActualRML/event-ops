"""Vendor CRUD and category creation."""

import re
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

import db
from deps import parse_halaman, parse_ids, templates

router = APIRouter()

NO_HP_ALLOWED = re.compile(r"^[0-9 +\-]+$")


def validasi_email(email: str) -> str | None:
    """Reject anything Gmail would accept but never deliver. Surrounding
    whitespace comes along with pasted addresses and is invisible, so it is
    trimmed first; whitespace left inside is the actual defect."""
    email = email.strip()
    if not email:
        return "Email is required."
    if any(ch.isspace() for ch in email):
        return "Email cannot contain spaces."
    if "," in email:
        return "Email cannot contain commas."
    if "@" not in email:
        return "Email must contain @."
    if email.count("@") > 1:
        return "Email can only have one @."

    local, _, domain = email.partition("@")
    if not local:
        return "The part before @ cannot be empty."
    if not domain:
        return "The part after @ cannot be empty."
    if ".." in email:
        return "Email cannot contain consecutive dots."
    if local.startswith(".") or local.endswith("."):
        return "The part before @ cannot start or end with a dot."
    if domain.startswith(".") or domain.endswith("."):
        return "The domain cannot start or end with a dot."
    if "." not in domain:
        return "The domain must contain a dot."
    return None


def validasi_vendor(data: dict, category_ids: list[int]) -> dict:
    """Returns {field: message}. Empty dict means valid."""
    errors = {}

    if not data["nama_pt"].strip():
        errors["nama_pt"] = "Company name is required."

    pesan = validasi_email(data["email"])
    if pesan:
        errors["email"] = pesan

    no_hp = data["no_hp"].strip()
    if no_hp and not NO_HP_ALLOWED.match(no_hp):
        errors["no_hp"] = "Phone may only contain digits, spaces, plus and minus signs."

    if not category_ids:
        errors["kategori"] = "Select at least one category."
    else:
        dikenal = {c["id"] for c in db.list_categories()}
        if not set(category_ids) <= dikenal:
            errors["kategori"] = "One of the categories is unknown."

    return errors


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


@router.get("/")
async def index(request: Request):
    return RedirectResponse("/vendors", status_code=303)


@router.get("/vendors")
async def vendor_list(request: Request, category: str = "", q: str = "",
                      per: str = "", page: str = ""):
    # Search-as-you-type and the category filter both land here. HTMX gets the
    # table fragment; a normal navigation or a refresh gets the whole page, off
    # the same query — so a swapped view and a reloaded one always agree.
    # A history restore also arrives with HX-Request set but wants the whole
    # page: it replaces the body, and a fragment there deletes the controls.
    htmx = (request.headers.get("HX-Request") == "true"
            and request.headers.get("HX-History-Restore-Request") != "true")
    # Count first: the page number cannot be clamped to a range that is not
    # known yet, and the same filter has to answer both questions.
    hal = parse_halaman(per, page, db.count_vendors(
        kategori=category or None, q=q or None, aktif_only=False))
    return templates.TemplateResponse(
        request,
        "_vendor_table.html" if htmx else "vendors.html",
        {
            # Inactive vendors stay listed here; aktif_only is for the send path.
            "vendors": db.list_vendors(
                kategori=category or None, q=q or None, aktif_only=False,
                limit=hal["per"], offset=hal["offset"],
            ),
            "hal": hal,
            "categories": db.list_categories(),
            "category": category,
            "q": q,
            # The chips swap out of band, but only when there is a swap.
            "oob": htmx,
        },
    )


@router.get("/categories/new")
async def category_form_baru(request: Request):
    return templates.TemplateResponse(
        request,
        "category_form.html",
        {"nama": "", "errors": {}, "categories": db.list_categories()},
    )


@router.post("/categories")
async def category_create(request: Request, nama: str = Form("")):
    bersih = nama.strip()
    errors = {}
    if not bersih:
        errors["nama"] = "Category name is required."
    elif db.category_exists(bersih):
        errors["nama"] = f"Category “{bersih}” already exists."

    if errors:
        return templates.TemplateResponse(
            request,
            "category_form.html",
            {"nama": nama, "errors": errors, "categories": db.list_categories()},
            status_code=422,
        )

    db.create_category(bersih)
    return RedirectResponse("/vendors", status_code=303)


@router.get("/vendors/new")
async def vendor_form_baru(request: Request):
    kosong = {
        "nama_pt": "", "pic_nama": "", "email": "",
        "no_hp": "", "area": "", "catatan": "", "aktif": 1,
    }
    return templates.TemplateResponse(
        request,
        "vendor_form.html",
        form_context(request, "Add Vendor", "/vendors", kosong, [], {}),
    )


@router.post("/vendors")
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
            form_context(request, "Add Vendor", "/vendors", data, ids, errors),
            status_code=422,
        )

    vendor_id = db.create_vendor(
        data["nama_pt"].strip(), data["pic_nama"].strip(), data["email"].strip(),
        data["no_hp"].strip(), data["area"].strip(), data["catatan"].strip(),
        data["aktif"],
    )
    db.set_vendor_categories(vendor_id, ids)
    return RedirectResponse("/vendors", status_code=303)


@router.get("/vendors/{vendor_id}/edit")
async def vendor_form_edit(request: Request, vendor_id: int):
    vendor = db.get_vendor(vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

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


@router.post("/vendors/{vendor_id}")
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
        raise HTTPException(status_code=404, detail="Vendor not found")

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


@router.post("/vendors/{vendor_id}/toggle-active")
async def vendor_toggle_aktif(vendor_id: int, category: str = Form(""),
                              q: str = Form("")):
    vendor = db.get_vendor(vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    db.set_vendor_aktif(vendor_id, 0 if vendor["aktif"] else 1)
    # Both filters ride back so the row does not vanish from view on toggle.
    # urlencode rather than an f-string: a search term may hold & or a space.
    saring = urlencode({k: v for k, v in (("category", category), ("q", q)) if v})
    return RedirectResponse(f"/vendors?{saring}" if saring else "/vendors",
                            status_code=303)
