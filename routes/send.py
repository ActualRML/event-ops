"""The send path: brief, vendor picking, preview, dispatch, progress."""

import sqlite3
from contextlib import closing
from datetime import date

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

import db
from core import renderer
import tasks
from deps import parse_ids, templates

router = APIRouter()

BRIEF_KOSONG = {
    "judul_acara": "", "tanggal_acara": "", "lokasi": "",
    "kebutuhan": "", "deadline": "", "pengirim_nama": "",
}


def parse_tanggal(teks: str):
    """ISO date string to date, or None if blank/unparseable."""
    teks = (teks or "").strip()
    if not teks:
        return None
    try:
        return date.fromisoformat(teks)
    except ValueError:
        return None


def validasi_brief(brief: dict, vendor_ids: list[int]) -> dict:
    """Runs before rendering. Returns {field: message}."""
    errors = {}

    if not brief["judul_acara"].strip():
        errors["judul_acara"] = "Event title is required."
    if not brief["kebutuhan"].strip():
        errors["kebutuhan"] = "Requirements are required."
    if not vendor_ids:
        errors["vendor"] = "Select at least one vendor."

    tanggal_acara = parse_tanggal(brief["tanggal_acara"])
    deadline = parse_tanggal(brief["deadline"])

    if brief["tanggal_acara"].strip() and tanggal_acara is None:
        errors["tanggal_acara"] = "Invalid date format."
    if brief["deadline"].strip() and deadline is None:
        errors["deadline"] = "Invalid date format."

    if deadline is not None:
        if deadline < date.today():
            errors["deadline"] = "Deadline cannot be before today."
        elif tanggal_acara is not None and deadline > tanggal_acara:
            errors["deadline"] = "Deadline must be on or before the event date."

    return errors


def send_context(request: Request, brief: dict, selected_ids: list[int],
                  category_id: int | None, errors: dict,
                  templat: dict | None = None) -> dict:
    """Context for send.html. Rebuilds the hidden container from selected_ids
    so a validation bounce never costs the user their selection. templat holds
    the edited email templates when there are any; empty strings mean the file
    defaults still apply."""
    categories = db.list_categories()
    if category_id is None and categories:
        category_id = categories[0]["id"]

    terpilih = [
        {"id": vid, "kategori": ",".join(str(c) for c in db.get_vendor_categories(vid))}
        for vid in selected_ids
    ]

    return {
        "request": request,
        "categories": categories,
        "category_id": category_id,
        "vendors": db.list_vendors_by_category(category_id) if category_id else [],
        "selected": set(selected_ids),
        "terpilih": terpilih,
        "brief": brief,
        "errors": errors,
        "templat": templat or {"subject": "", "body": ""},
    }


@router.get("/send")
async def send_form(request: Request):
    # Selection starts empty; it lives in the page, not the session.
    return templates.TemplateResponse(
        request, "send.html", send_context(request, dict(BRIEF_KOSONG), [], None, {})
    )


@router.post("/send/back")
async def send_back(
    request: Request,
    judul_acara: str = Form(""),
    tanggal_acara: str = Form(""),
    lokasi: str = Form(""),
    kebutuhan: str = Form(""),
    deadline: str = Form(""),
    pengirim_nama: str = Form(""),
    category_id: str = Form(""),
    vendor_ids: list[str] = Form([]),
    subject_template: str = Form(""),
    body_template: str = Form(""),
):
    """Back from preview. Same rebuild path the validation bounce uses, minus
    the errors, so the brief and the vendor selection both come back. The edited
    templates ride along too, so a detour to add a vendor does not undo them."""
    brief = {
        "judul_acara": judul_acara, "tanggal_acara": tanggal_acara,
        "lokasi": lokasi, "kebutuhan": kebutuhan,
        "deadline": deadline, "pengirim_nama": pengirim_nama,
    }
    ids = list(dict.fromkeys(parse_ids(vendor_ids)))
    kategori = parse_ids([category_id])

    return templates.TemplateResponse(
        request,
        "send.html",
        send_context(
            request, brief, ids, kategori[0] if kategori else None, {},
            {"subject": subject_template, "body": body_template},
        ),
    )


@router.post("/send/preview")
async def send_preview(
    request: Request,
    judul_acara: str = Form(""),
    tanggal_acara: str = Form(""),
    lokasi: str = Form(""),
    kebutuhan: str = Form(""),
    deadline: str = Form(""),
    pengirim_nama: str = Form(""),
    category_id: str = Form(""),
    vendor_ids: list[str] = Form([]),
    subject_template: str = Form(""),
    body_template: str = Form(""),
):
    brief = {
        "judul_acara": judul_acara, "tanggal_acara": tanggal_acara,
        "lokasi": lokasi, "kebutuhan": kebutuhan,
        "deadline": deadline, "pengirim_nama": pengirim_nama,
    }
    # dict.fromkeys dedupes while keeping click order; the first id drives the example.
    ids = list(dict.fromkeys(parse_ids(vendor_ids)))
    kategori_aktif = parse_ids([category_id])
    kategori_aktif = kategori_aktif[0] if kategori_aktif else None

    vendors = [v for v in (db.get_vendor(i) for i in ids) if v is not None]
    if not vendors:
        ids = []

    errors = validasi_brief(brief, ids)
    if errors:
        return templates.TemplateResponse(
            request,
            "send.html",
            send_context(
                request, brief, ids, kategori_aktif, errors,
                {"subject": subject_template, "body": body_template},
            ),
            status_code=422,
        )

    subject_template = subject_template or renderer.default_subject()
    body_template = body_template or renderer.default_body()

    # First vendor in click order supplies the data for the sample email. The
    # preview no longer names it — the Penerima table marks its row instead.
    contoh = vendors[0]
    render_error = None
    subject, body = "", ""
    try:
        subject, body = renderer.render_email(
            subject_template,
            body_template,
            brief,
            {"nama_pt": contoh["nama_pt"], "pic_nama": contoh["pic_nama"],
             "kategori": contoh["kategori"]},
        )
    except Exception as e:
        render_error = f"{type(e).__name__}: {e}"

    return templates.TemplateResponse(
        request,
        "preview.html",
        {
            "brief": brief,
            "vendors": vendors,
            "vendor_ids": [v["id"] for v in vendors],
            "category_id": kategori_aktif or "",
            "subject_template": subject_template,
            "body_template": body_template,
            "subject": subject,
            "body": body,
            "render_error": render_error,
        },
        status_code=422 if render_error else 200,
    )


@router.get("/send/vendors")
async def send_vendors(
    request: Request,
    category_id: int,
    vendor_ids: list[str] = Query([]),
):
    """HTMX partial. vendor_ids arrives from the hidden container so a vendor
    already picked under another category renders checked here too."""
    return templates.TemplateResponse(
        request,
        "_send_pick_vendor.html",
        {
            "vendors": db.list_vendors_by_category(category_id),
            "selected": set(parse_ids(vendor_ids)),
        },
    )


@router.post("/send/dispatch")
async def send_dispatch(
    request: Request,
    judul_acara: str = Form(""),
    tanggal_acara: str = Form(""),
    lokasi: str = Form(""),
    kebutuhan: str = Form(""),
    deadline: str = Form(""),
    pengirim_nama: str = Form(""),
    vendor_ids: list[str] = Form([]),
    subject_template: str = Form(""),
    body_template: str = Form(""),
    request_id: str = Form(""),
):
    """Phase A: one fast transaction, then hand off to the background."""
    brief = {
        "judul_acara": judul_acara, "tanggal_acara": tanggal_acara,
        "lokasi": lokasi, "kebutuhan": kebutuhan,
        "deadline": deadline, "pengirim_nama": pengirim_nama,
    }
    ids = list(dict.fromkeys(parse_ids(vendor_ids)))
    lama = parse_ids([request_id])

    # Layer 2: a request that already dispatched is never sent again.
    if lama:
        existing = lama[0]
        if db.request_detail(existing) is None:
            raise HTTPException(status_code=404, detail="Request not found")
        if db.request_has_dispatched(existing):
            return templates.TemplateResponse(
                request, "send_rejected.html",
                {"request_id": existing, "alasan": "This request has already been sent."},
                status_code=409,
            )
        tasks.schedule_batch(existing)
        return RedirectResponse(f"/tracker/{existing}", status_code=303)

    errors = validasi_brief(brief, ids)
    if errors:
        return templates.TemplateResponse(
            request, "send.html",
            send_context(
                request, brief, ids, None, errors,
                {"subject": subject_template, "body": body_template},
            ),
            status_code=422,
        )

    subject_template = subject_template or renderer.default_subject()
    body_template = body_template or renderer.default_body()

    # Subjects are rendered up front so every draft row carries its final
    # subject; Gmail threads a batch together if they are not distinct.
    subjects = {}
    for vendor_id in ids:
        vendor = db.get_vendor(vendor_id)
        if vendor is None:
            continue
        subject, _ = renderer.render_email(
            subject_template, body_template, brief,
            {"nama_pt": vendor["nama_pt"], "pic_nama": vendor["pic_nama"],
             "kategori": vendor["kategori"]},
        )
        subjects[vendor_id] = subject

    try:
        with closing(db.get_conn()) as conn:
            baru = db.create_request(brief, subject_template, body_template, conn=conn)
            db.create_outbox_rows(baru, ids, subjects=subjects, conn=conn)
            conn.commit()
    except sqlite3.IntegrityError as e:
        # Layer 3: UNIQUE(request_id, vendor_id).
        return templates.TemplateResponse(
            request, "send_rejected.html",
            {"request_id": None, "alasan": f"Duplicate outbox row rejected by the database: {e}"},
            status_code=409,
        )

    tasks.schedule_batch(baru)
    return RedirectResponse(f"/tracker/{baru}", status_code=303)


@router.get("/send/{request_id}/progress")
async def send_progress(request: Request, request_id: int):
    if db.request_detail(request_id) is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return templates.TemplateResponse(
        request, "_progress.html",
        {
            "request_id": request_id,
            "p": db.progress(request_id),
            "rows": db.list_outbox_rows(request_id),
            # The poll swaps the whole table, so the SPK column has to come
            # with it — otherwise the last swap of a batch wipes the actions.
            "spk": db.spk_by_vendor(request_id),
        },
    )
