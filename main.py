"""Vendor RFQ Blast — app entrypoint."""

import asyncio
import re
import sqlite3
from contextlib import closing
from datetime import date

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config
import db
import mailer
import renderer

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
        errors["judul_acara"] = "Judul acara wajib diisi."
    if not brief["kebutuhan"].strip():
        errors["kebutuhan"] = "Kebutuhan wajib diisi."
    if not vendor_ids:
        errors["vendor"] = "Pilih minimal satu vendor."

    tanggal_acara = parse_tanggal(brief["tanggal_acara"])
    deadline = parse_tanggal(brief["deadline"])

    if brief["tanggal_acara"].strip() and tanggal_acara is None:
        errors["tanggal_acara"] = "Format tanggal tidak valid."
    if brief["deadline"].strip() and deadline is None:
        errors["deadline"] = "Format tanggal tidak valid."

    if deadline is not None:
        if deadline < date.today():
            errors["deadline"] = "Deadline tidak boleh sebelum hari ini."
        elif tanggal_acara is not None and deadline > tanggal_acara:
            errors["deadline"] = "Deadline harus sebelum atau sama dengan tanggal acara."

    return errors


def kirim_context(request: Request, brief: dict, selected_ids: list[int],
                  category_id: int | None, errors: dict) -> dict:
    """Context for kirim.html. Rebuilds the hidden container from selected_ids
    so a validation bounce never costs the user their selection."""
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
    }


@app.get("/kirim")
async def kirim(request: Request):
    # Selection starts empty; it lives in the page, not the session.
    return templates.TemplateResponse(
        request, "kirim.html", kirim_context(request, dict(BRIEF_KOSONG), [], None, {})
    )


@app.post("/kirim/preview")
async def kirim_preview(
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
            "kirim.html",
            kirim_context(request, brief, ids, kategori_aktif, errors),
            status_code=422,
        )

    subject_template = subject_template or renderer.default_subject()
    body_template = body_template or renderer.default_body()

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
            "contoh": contoh,
            "render_error": render_error,
        },
        status_code=422 if render_error else 200,
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


def brief_dari_request(row) -> dict:
    return {
        "judul_acara": row["judul_acara"], "tanggal_acara": row["tanggal_acara"],
        "lokasi": row["lokasi"], "kebutuhan": row["kebutuhan"],
        "deadline": row["deadline"], "pengirim_nama": row["pengirim_nama"],
    }


# Keeps background tasks from being garbage collected mid-batch.
TUGAS_KIRIM: set[asyncio.Task] = set()


async def dispatch_batch(request_id: int) -> None:
    """Phase B. Runs outside the request handler, commits after every email.
    One bad row is recorded and skipped; the batch always continues."""
    permintaan = db.request_detail(request_id)
    if permintaan is None:
        return
    brief = brief_dari_request(permintaan)

    baris = db.list_draft_rows(request_id)
    for i, row in enumerate(baris):
        try:
            subject, body = renderer.render_email(
                permintaan["subject_template"],
                permintaan["body_template"],
                brief,
                {"nama_pt": row["nama_pt"], "pic_nama": row["pic_nama"],
                 "kategori": row["kategori"]},
            )
            ok, hasil = await mailer.kirim_email(row["email_tujuan"], subject, body)
            if ok:
                db.mark_sent(row["id"], hasil)
            else:
                db.mark_failed(row["id"], hasil)
        except Exception as e:
            db.mark_failed(row["id"], f"{type(e).__name__}: {e}")

        if i < len(baris) - 1:
            await asyncio.sleep(config.SEND_DELAY_SECONDS)


def jadwalkan(request_id: int) -> None:
    tugas = asyncio.create_task(dispatch_batch(request_id))
    TUGAS_KIRIM.add(tugas)
    tugas.add_done_callback(TUGAS_KIRIM.discard)


@app.post("/kirim/send")
async def kirim_send(
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
            raise HTTPException(status_code=404, detail="Request tidak ditemukan")
        if db.request_has_dispatched(existing):
            return templates.TemplateResponse(
                request, "kirim_ditolak.html",
                {"request_id": existing, "alasan": "Request ini sudah pernah dikirim."},
                status_code=409,
            )
        jadwalkan(existing)
        return RedirectResponse(f"/tracker/{existing}", status_code=303)

    errors = validasi_brief(brief, ids)
    if errors:
        return templates.TemplateResponse(
            request, "kirim.html",
            kirim_context(request, brief, ids, None, errors),
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
            request, "kirim_ditolak.html",
            {"request_id": None, "alasan": f"Duplikat baris outbox ditolak database: {e}"},
            status_code=409,
        )

    jadwalkan(baru)
    return RedirectResponse(f"/tracker/{baru}", status_code=303)


@app.get("/kirim/{request_id}/progress")
async def kirim_progress(request: Request, request_id: int):
    if db.request_detail(request_id) is None:
        raise HTTPException(status_code=404, detail="Request tidak ditemukan")
    return templates.TemplateResponse(
        request, "_progress.html",
        {
            "request_id": request_id,
            "p": db.progress(request_id),
            "rows": db.list_outbox_rows(request_id),
        },
    )


@app.get("/tracker")
async def tracker(request: Request):
    return templates.TemplateResponse(
        request, "tracker.html", {"requests": db.list_requests()}
    )


@app.get("/tracker/{request_id}")
async def tracker_detail(request: Request, request_id: int):
    permintaan = db.request_detail(request_id)
    if permintaan is None:
        raise HTTPException(status_code=404, detail="Request tidak ditemukan")
    return templates.TemplateResponse(
        request, "tracker_detail.html",
        {
            "permintaan": permintaan,
            "request_id": request_id,
            "p": db.progress(request_id),
            "rows": db.list_outbox_rows(request_id),
        },
    )


@app.post("/tracker/{request_id}/retry")
async def tracker_retry(request_id: int):
    if db.request_detail(request_id) is None:
        raise HTTPException(status_code=404, detail="Request tidak ditemukan")

    # Only failed rows return to draft. Rows still draft from an interrupted
    # batch are picked up by the same dispatch.
    db.reset_failed_to_draft(request_id)
    jadwalkan(request_id)
    return RedirectResponse(f"/tracker/{request_id}", status_code=303)


@app.post("/vendors/{vendor_id}/aktif")
async def vendor_toggle_aktif(vendor_id: int, kategori: str = Form("")):
    vendor = db.get_vendor(vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor tidak ditemukan")

    db.set_vendor_aktif(vendor_id, 0 if vendor["aktif"] else 1)
    tujuan = f"/vendors?kategori={kategori}" if kategori else "/vendors"
    return RedirectResponse(tujuan, status_code=303)
