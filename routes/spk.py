"""SPK: issue, edit, and download the work order for one vendor of one request."""

import re
import sqlite3

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse

import db
from core import dokumen
from core import terbilang
from deps import templates

router = APIRouter()

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
    teks = re.sub(r"[\s ]", "", teks)

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


@router.get("/tracker/{request_id}/spk/{vendor_id}")
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


@router.post("/tracker/{request_id}/spk/{vendor_id}")
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


@router.get("/tracker/{request_id}/spk/{vendor_id}/download")
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
