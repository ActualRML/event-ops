"""Email rendering. Preview and send both call render_email() and nothing else."""

from datetime import date
from pathlib import Path

from jinja2 import StrictUndefined, Template

TEMPLATE_DIR = Path(__file__).resolve().parent / "email_templates"
SUBJECT_FILE = TEMPLATE_DIR / "rfq_subject.txt"
BODY_FILE = TEMPLATE_DIR / "rfq_default.txt"

BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def default_subject() -> str:
    """Read on every call so editing the file needs no restart."""
    return SUBJECT_FILE.read_text(encoding="utf-8").strip()


def default_body() -> str:
    return BODY_FILE.read_text(encoding="utf-8")


def format_tanggal(value) -> str:
    """ISO date to Indonesian long form: 2026-09-18 -> 18 September 2026.
    Anything that is not an ISO date passes through untouched."""
    if value is None:
        return ""
    if isinstance(value, date):
        tanggal = value
    else:
        teks = str(value).strip()
        if not teks:
            return ""
        try:
            tanggal = date.fromisoformat(teks)
        except ValueError:
            return teks
    return f"{tanggal.day} {BULAN[tanggal.month - 1]} {tanggal.year}"


def gabung_kategori(value) -> str:
    """A vendor in three categories yields all three, comma-joined."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return ", ".join(str(v) for v in value)


def render_email(
    subject_template: str,
    body_template: str,
    brief: dict,
    vendor: dict,
) -> tuple[str, str]:
    """Render one email for one vendor. Returns (subject, body)."""
    konteks = {
        "nama_pt": vendor.get("nama_pt") or "",
        "pic_nama": vendor.get("pic_nama") or "",
        "kategori": gabung_kategori(vendor.get("kategori")),
        "judul_acara": brief.get("judul_acara") or "",
        "tanggal_acara": format_tanggal(brief.get("tanggal_acara")),
        "lokasi": brief.get("lokasi") or "",
        "kebutuhan": brief.get("kebutuhan") or "",
        "deadline": format_tanggal(brief.get("deadline")),
        "pengirim_nama": brief.get("pengirim_nama") or "",
    }

    subject = Template(subject_template, undefined=StrictUndefined).render(**konteks)
    body = Template(body_template, undefined=StrictUndefined).render(**konteks)

    # A subject spanning lines would break the SMTP header.
    subject = " ".join(subject.split())

    for nama, hasil in (("subject", subject), ("body", body)):
        if "{{" in hasil or "}}" in hasil:
            raise ValueError(f"Masih ada placeholder yang belum tergantikan di {nama}.")

    return subject, body
