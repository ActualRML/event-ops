"""Vendor RFQ Blast — app entrypoint."""

import asyncio
import re
import sqlite3
from contextlib import closing
from datetime import date
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config
import db
import dokumen
import mailer
import renderer
import tampilan
import terbilang

app = FastAPI(title="Vendor RFQ Blast")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
# Presentation only, all from tampilan — renderer.format_tanggal stays
# Indonesian and is reserved for the email body.
templates.env.filters["date"] = tampilan.format_date
# created_at carries a clock time, which the date-only filter cannot parse.
templates.env.filters["datetime"] = tampilan.format_datetime
# Raw SMTP exceptions are unreadable for the procurement staff who use this.
templates.env.filters["error_message"] = tampilan.pesan_error
# Footer year. Read at startup — a demo restarts far more often than a year turns.
templates.env.globals["tahun"] = date.today().year

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
async def vendor_list(request: Request, category: str = "", q: str = ""):
    # Search-as-you-type and the category filter both land here. HTMX gets the
    # table fragment; a normal navigation or a refresh gets the whole page, off
    # the same query — so a swapped view and a reloaded one always agree.
    # A history restore also arrives with HX-Request set but wants the whole
    # page: it replaces the body, and a fragment there deletes the controls.
    htmx = (request.headers.get("HX-Request") == "true"
            and request.headers.get("HX-History-Restore-Request") != "true")
    return templates.TemplateResponse(
        request,
        "_vendor_table.html" if htmx else "vendors.html",
        {
            # Inactive vendors stay listed here; aktif_only is for the send path.
            "vendors": db.list_vendors(
                kategori=category or None, q=q or None, aktif_only=False
            ),
            "categories": db.list_categories(),
            "category": category,
            "q": q,
            # The chips swap out of band, but only when there is a swap.
            "oob": htmx,
        },
    )


@app.get("/categories/new")
async def category_form_baru(request: Request):
    return templates.TemplateResponse(
        request,
        "category_form.html",
        {"nama": "", "errors": {}, "categories": db.list_categories()},
    )


@app.post("/categories")
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


@app.get("/vendors/new")
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


@app.get("/vendors/{vendor_id}/edit")
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


@app.get("/send")
async def send_form(request: Request):
    # Selection starts empty; it lives in the page, not the session.
    return templates.TemplateResponse(
        request, "send.html", send_context(request, dict(BRIEF_KOSONG), [], None, {})
    )


@app.post("/send/back")
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


@app.post("/send/preview")
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


@app.get("/send/vendors")
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


def brief_dari_request(row) -> dict:
    return {
        "judul_acara": row["judul_acara"], "tanggal_acara": row["tanggal_acara"],
        "lokasi": row["lokasi"], "kebutuhan": row["kebutuhan"],
        "deadline": row["deadline"], "pengirim_nama": row["pengirim_nama"],
    }


# Keeps background tasks from being garbage collected mid-batch.
SEND_TASKS: set[asyncio.Task] = set()


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


def schedule_batch(request_id: int) -> None:
    tugas = asyncio.create_task(dispatch_batch(request_id))
    SEND_TASKS.add(tugas)
    tugas.add_done_callback(SEND_TASKS.discard)


@app.post("/send/dispatch")
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
        schedule_batch(existing)
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

    schedule_batch(baru)
    return RedirectResponse(f"/tracker/{baru}", status_code=303)


@app.get("/send/{request_id}/progress")
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
            "spk": peta_spk(request_id),
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


@app.post("/tracker/{request_id}/retry")
async def tracker_retry(request_id: int):
    if db.request_detail(request_id) is None:
        raise HTTPException(status_code=404, detail="Request not found")

    # Only failed rows return to draft. Rows still draft from an interrupted
    # batch are picked up by the same dispatch.
    db.reset_failed_to_draft(request_id)
    schedule_batch(request_id)
    return RedirectResponse(f"/tracker/{request_id}", status_code=303)


# --- SPK ---------------------------------------------------------------

MEDIA_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Grouped digits: 15.000.000 or 15,000,000, but not 15.5 — a stray decimal
# must be rejected, not silently multiplied by ten.
HARGA_BERKELOMPOK = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")


def parse_harga(raw: str) -> tuple[int | None, str | None]:
    """Read what procurement actually types. "15000000", "15.000.000" and
    "Rp 15.000.000" all mean the same amount; the separators are stripped and
    the value is stored as whole rupiah."""
    teks = str(raw).strip()
    if not teks:
        return None, "Amount is required."

    # Currency prefix and any spacing inside the digits.
    teks = re.sub(r"^rp\.?\s*", "", teks, flags=re.IGNORECASE)
    teks = re.sub(r"[\s ]", "", teks)

    if HARGA_BERKELOMPOK.match(teks):
        teks = teks.replace(".", "").replace(",", "")
    elif not teks.isdigit():
        return None, "Enter a whole rupiah amount, e.g. 15.000.000."

    nilai = int(teks)
    if nilai <= 0:
        return None, "Amount must be greater than zero."
    # The document spells the amount out, and terbilang stops here.
    if nilai > terbilang.MAKS:
        maks = dokumen.format_rupiah(terbilang.MAKS, prefix=False)
        return None, f"Amount is above the maximum of {maks}."
    return nilai, None


def peta_spk(request_id: int) -> dict:
    """vendor_id -> SPK row, for the per-vendor action in the outbox table."""
    return {r["vendor_id"]: r for r in db.list_spk_for_request(request_id)}


def muat_spk(request_id: int, vendor_id: int):
    """The rows every SPK route needs. The vendor must belong to this request:
    the action is offered per outbox row, so a hand-typed pair that was never
    invited is a 404, not a new orphan SPK."""
    permintaan = db.request_detail(request_id)
    if permintaan is None:
        raise HTTPException(status_code=404, detail="Request not found")

    vendor = db.get_vendor(vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found")

    if not any(r["vendor_id"] == vendor_id for r in db.list_outbox_rows(request_id)):
        raise HTTPException(status_code=404, detail="Vendor is not part of this request")

    return permintaan, vendor, db.get_spk(request_id, vendor_id)


def spk_context(request_id: int, vendor_id: int, permintaan, vendor, spk,
                v: dict, errors: dict) -> dict:
    return {
        "request_id": request_id,
        "vendor_id": vendor_id,
        "permintaan": permintaan,
        "vendor": vendor,
        "spk": spk,
        "v": v,
        "errors": errors,
        # What dokumen.py would raise on. Checked here so it never can.
        "hambatan": dokumen.periksa_konteks(vendor, permintaan),
    }


@app.get("/tracker/{request_id}/spk/{vendor_id}")
async def spk_form(request: Request, request_id: int, vendor_id: int):
    permintaan, vendor, spk = muat_spk(request_id, vendor_id)
    v = {
        "harga": dokumen.format_rupiah(spk["harga"], prefix=False) if spk else "",
        "lingkup_kerja": (spk["lingkup_kerja"] or "") if spk else "",
        "termin": (spk["termin"] or "") if spk else "",
    }
    return templates.TemplateResponse(
        request, "spk_form.html",
        spk_context(request_id, vendor_id, permintaan, vendor, spk, v, {}),
    )


@app.post("/tracker/{request_id}/spk/{vendor_id}")
async def spk_save(
    request: Request,
    request_id: int,
    vendor_id: int,
    harga: str = Form(""),
    lingkup_kerja: str = Form(""),
    termin: str = Form(""),
):
    permintaan, vendor, spk = muat_spk(request_id, vendor_id)
    v = {"harga": harga, "lingkup_kerja": lingkup_kerja, "termin": termin}

    errors = {}
    nilai, pesan = parse_harga(harga)
    if pesan:
        errors["harga"] = pesan
    if not lingkup_kerja.strip():
        errors["lingkup_kerja"] = "Scope of work is required."
    if not termin.strip():
        errors["termin"] = "Payment terms are required."

    konteks = spk_context(request_id, vendor_id, permintaan, vendor, spk, v, errors)
    if errors or konteks["hambatan"]:
        return templates.TemplateResponse(
            request, "spk_form.html", konteks, status_code=422
        )

    if spk is None:
        try:
            db.create_spk(request_id, vendor_id, nilai,
                          lingkup_kerja.strip(), termin.strip())
        except sqlite3.IntegrityError:
            # UNIQUE(request_id, vendor_id): a second submit got here first.
            # One SPK per pair, so the later one edits it rather than failing.
            lama = db.get_spk(request_id, vendor_id)
            db.update_spk(lama["id"], nilai, lingkup_kerja.strip(), termin.strip())
    else:
        db.update_spk(spk["id"], nilai, lingkup_kerja.strip(), termin.strip())

    return RedirectResponse(f"/tracker/{request_id}", status_code=303)


@app.get("/tracker/{request_id}/spk/{vendor_id}/download")
async def spk_download(request_id: int, vendor_id: int):
    permintaan, vendor, spk = muat_spk(request_id, vendor_id)
    if spk is None:
        raise HTTPException(status_code=404, detail="No SPK issued for this vendor")

    # A vendor edited after issue can have lost its area or PIC. The form says
    # which; generating here would raise instead.
    if dokumen.periksa_konteks(vendor, permintaan):
        return RedirectResponse(f"/tracker/{request_id}/spk/{vendor_id}",
                                status_code=303)

    # Rebuilt from the stored row on every download — nothing is cached, so an
    # updated amount is in the file the moment it is saved.
    aliran = dokumen.buat_spk_docx(spk, vendor, permintaan)
    nama = dokumen.nama_berkas_spk(spk["nomor"], vendor["nama_pt"])
    return StreamingResponse(
        aliran,
        media_type=MEDIA_DOCX,
        headers={"Content-Disposition": f'attachment; filename="{nama}"'},
    )


@app.post("/vendors/{vendor_id}/toggle-active")
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
