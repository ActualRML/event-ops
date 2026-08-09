"""Email rendering. Preview and send both call render_email() and nothing else."""

from datetime import date, datetime
from pathlib import Path

from jinja2 import StrictUndefined, Template

TEMPLATE_DIR = Path(__file__).resolve().parent / "email_templates"
SUBJECT_FILE = TEMPLATE_DIR / "rfq_subject.txt"
BODY_FILE = TEMPLATE_DIR / "rfq_default.txt"

# Two month tables on purpose. The interface is English, but the emails go to
# Indonesian vendors, so BULAN must stay — format_tanggal feeds
# {{ tanggal_acara }} and {{ deadline }} inside the email body.
BULAN = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def default_subject() -> str:
    """Read on every call so editing the file needs no restart."""
    return SUBJECT_FILE.read_text(encoding="utf-8").strip()


def default_body() -> str:
    return BODY_FILE.read_text(encoding="utf-8")


def _ke_tanggal(value):
    """Shared parsing for both formatters. Returns a date, or the original text
    when it is not an ISO date, or None for blank."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    teks = str(value).strip()
    if not teks:
        return None
    try:
        return date.fromisoformat(teks)
    except ValueError:
        return teks


def format_tanggal(value) -> str:
    """ISO date to Indonesian long form: 2026-09-18 -> 18 September 2026.
    EMAIL ONLY — this is what fills {{ tanggal_acara }} and {{ deadline }} in
    the message body, which stays Indonesian. The interface uses format_date.
    Anything that is not an ISO date passes through untouched."""
    hasil = _ke_tanggal(value)
    if hasil is None:
        return ""
    if isinstance(hasil, str):
        return hasil
    return f"{hasil.day} {BULAN[hasil.month - 1]} {hasil.year}"


def format_date(value) -> str:
    """ISO date to English long form: 2026-09-18 -> 18 September 2026.
    Interface only — never use this for the email body."""
    hasil = _ke_tanggal(value)
    if hasil is None:
        return ""
    if isinstance(hasil, str):
        return hasil
    return f"{hasil.day} {MONTHS[hasil.month - 1]} {hasil.year}"


def format_datetime(value) -> str:
    """Timestamp to English long form with the clock:
    2026-08-04 18:16:21 -> 4 August 2026, 18:16.
    Seconds are dropped — nobody reads a batch log to the second. Anything that
    is not a parseable timestamp passes through untouched, same as format_date,
    so a stray value is never swallowed. Interface only."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        waktu = value
    else:
        teks = str(value).strip()
        if not teks:
            return ""
        try:
            waktu = datetime.fromisoformat(teks)
        except ValueError:
            return teks
    return f"{waktu.day} {MONTHS[waktu.month - 1]} {waktu.year}, {waktu:%H:%M}"


def gabung_kategori(value) -> str:
    """A vendor in three categories yields all three, comma-joined."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return ", ".join(str(v) for v in value)


# Plain-Indonesian labels for the tracker, keyed by exception class name.
# Names are aiosmtplib's, not smtplib's — the two differ (aiosmtplib has
# SMTPNotSupported where smtplib has SMTPNotSupportedError, and it adds its own
# TimeoutError). Short on purpose: the cell is narrow and clips, and the raw
# exception is still one hover away.
PESAN_ERROR = {
    "SMTPSenderRefused": "Sender address rejected",
    "SMTPAuthenticationError": "Email login failed",
    "SMTPConnectError": "Could not reach mail server",
    "SMTPConnectResponseError": "Could not reach mail server",
    "SMTPServerDisconnected": "Connection to server dropped",
    "SMTPTimeoutError": "Mail server did not respond",
    "SMTPConnectTimeoutError": "Mail server did not respond",
    "SMTPReadTimeoutError": "Mail server did not respond",
    "TimeoutError": "Mail server did not respond",
    "SMTPDataError": "Message rejected by server",
    "SMTPNotSupported": "Server refused the connection mode",
    "SMTPHeloError": "Server refused the initial handshake",
    "SMTPResponseException": "Mail server refused the request",
    "SMTPException": "Send failed",
    "gaierror": "Mail server address not found",
    "ConnectionRefusedError": "Connection refused by server",
}

# Both the batch form and the single-recipient form reach us; Gmail raises the
# plural wrapping the singular, but the singular can surface on its own.
DITOLAK_PENERIMA = ("SMTPRecipientsRefused", "SMTPRecipientRefused")


def pesan_error(error_msg) -> str:
    """One human line for an outbox failure, from the stored
    'ExceptionName: detail' string. Translating on display rather than on write
    keeps the raw error in the database — rows that already failed get the new
    wording too, with no migration."""
    if not error_msg:
        return ""

    nama, _, detail = str(error_msg).partition(":")
    nama = nama.strip()

    # The overwhelmingly common failure, and the only one procurement can act
    # on themselves, so it is split by what the server actually objected to.
    if nama in DITOLAK_PENERIMA:
        if "553" in detail or "not a valid" in detail:
            return "Invalid email address"
        if "550" in detail or "does not exist" in detail:
            return "Email address not found"
        return "Rejected by recipient server"

    return PESAN_ERROR.get(nama, "Send failed")


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
            raise ValueError(f"Unresolved placeholder left in the {nama}.")

    return subject, body
