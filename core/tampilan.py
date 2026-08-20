"""Interface presentation. Everything here is registered as a Jinja filter and
used by the templates only — never by the email body, which stays Indonesian
and goes through renderer.format_tanggal."""

from datetime import datetime

from core import renderer

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def format_date(value) -> str:
    """ISO date to English long form: 2026-09-18 -> 18 September 2026.
    Interface only — never use this for the email body."""
    # The ISO parse is renderer's: both formatters accept the same inputs and
    # pass the same non-dates through, so only the month table differs.
    hasil = renderer.ke_tanggal(value)
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
    so a stray value is never swallowed."""
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


def format_durasi(menit) -> str:
    """Minutes as "1 h 30 min", for the rundown's duration column and totals.

    Stays in hours and minutes: a rundown item is a slot in a day, so a day
    unit would never be reached and would only read oddly. Zero is "0 min"
    rather than blank — a total of nothing is a real answer here."""
    if menit is None or str(menit).strip() == "":
        return ""
    try:
        nilai = int(menit)
    except (TypeError, ValueError):
        return str(menit)

    jam, sisa = divmod(nilai, 60)
    if jam and sisa:
        return f"{jam} h {sisa} min"
    if jam:
        return f"{jam} h"
    return f"{sisa} min"


# Plain labels for the tracker, keyed by exception class name. Names are
# aiosmtplib's, not smtplib's — the two differ (aiosmtplib has SMTPNotSupported
# where smtplib has SMTPNotSupportedError, and it adds its own TimeoutError).
# Short on purpose: the cell is narrow and clips, and the raw exception is
# still one hover away.
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


# Reading the mailbox fails differently from sending to it, so it gets its own
# table rather than more branches in pesan_error: the two share no exception
# names, and the actions they suggest are different — a send failure is about
# one vendor's address, a read failure is about the account or the network.
PESAN_IMAP = {
    "IMAP4.error": "Mailbox rejected the login — check the app password",
    "IMAP4.abort": "Mailbox closed the connection mid-check",
    "IMAP4.readonly": "Mailbox is read-only",
    "error": "Mailbox rejected the request",
    "abort": "Mailbox closed the connection mid-check",
    "gaierror": "Mail server address not found",
    "timeout": "Mail server did not respond in time",
    "TimeoutError": "Mail server did not respond in time",
    "ConnectionRefusedError": "Connection refused by mail server",
    "ConnectionResetError": "Mail server dropped the connection",
    "SSLError": "Secure connection to the mail server failed",
    "SSLCertVerificationError": "Mail server certificate could not be verified",
    "OSError": "Could not reach the mail server",
}


def pesan_imap(error_msg) -> str:
    """One human line for a failed reply check, from the stored
    'ExceptionName: detail' string.

    Same rule as pesan_error: the raw string stays in inbox_check.error_msg and
    translation happens here, so reworded messages need no migration and the
    full server response is still available in a tooltip.

    Authentication is singled out because it is the one failure the user can
    fix themselves, and because it is what a fresh setup hits first — Gmail
    also needs IMAP switched on in its own settings, which surfaces as the same
    login rejection."""
    if not error_msg:
        return ""

    nama, _, detail = str(error_msg).partition(":")
    nama = nama.strip()

    # imaplib raises IMAP4.error for everything from a bad password to a
    # malformed command, so the detail is what separates them.
    if "AUTHENTICATIONFAILED" in detail or "Invalid credentials" in detail:
        return "Mailbox rejected the login — check the app password, and that IMAP is enabled in Gmail"

    return PESAN_IMAP.get(nama, "Could not read the mailbox")
