"""Interface presentation. Everything here is registered as a Jinja filter and
used by the templates only — never by the email body, which stays Indonesian
and goes through renderer.format_tanggal."""

import re
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


# Baris atribusi yang dipasang klien email tepat di atas kutipan. Dikenali dari
# BENTUKNYA, bukan dari kata-katanya: alamat dalam kurung siku lalu titik dua.
#
# Sengaja tidak mencocokkan "wrote:" atau "menulis:". Balasan nyata pertama yang
# masuk ke sistem ini berbahasa Inggris ("On Fri, 21 Aug 2026 at 00:23,
# Procurement <...> wrote:") padahal seluruh korespondensinya Indonesia — Gmail
# memakai bahasa antarmuka si pembalas, bukan bahasa pesannya. Daftar kata akan
# meleset pada bahasa keempat; kurung siku dan titik dua tidak.
ATRIBUSI = re.compile(r"<[^<>@\s]+@[^<>\s]+>[^:]*:\s*$")

# Sejauh mana menengok ke belakang untuk baris atribusi. Baris itu bisa terlipat
# jadi dua ("...gmail.com>" lalu "wrote:"), tiga sudah lebih dari cukup.
MAKS_ATRIBUSI = 3


def belah_kutipan(body) -> tuple[str, str]:
    """Pisahkan balasan jadi (jawaban, kutipan).

    Klien email menyalin seluruh pesan asli di bawah jawaban. Pada balasan nyata
    pertama di sistem ini: 55 baris, 39 di antaranya kutipan — jawaban vendornya
    11 baris pertama, sisanya email kami sendiri dipantulkan balik. Lampiran,
    yang justru dicari orang, terdorong jauh di bawah lipatan.

    DIPOTONG SAAT TAMPIL, TIDAK SAAT SIMPAN. inbox.body tetap menyimpan pesan
    utuh — aturan yang sama dengan pesan_error di atas: yang mentah tinggal di
    database, penyesuaian terjadi di jalan keluar. Jadi kutipannya tidak hilang,
    hanya dilipat, dan memperbaiki pemotong ini tidak butuh migrasi apa pun.

    Kutipan dikenali dari baris diawali ">" — konvensi yang jauh lebih tua dari
    Gmail dan dipakai semua klien. Tidak ada baris ">" berarti tidak ada yang
    dipotong, dan seluruh isinya dikembalikan apa adanya.
    """
    if not body:
        return "", ""

    baris = str(body).splitlines()
    awal = next((i for i, b in enumerate(baris) if b.lstrip().startswith(">")), None)
    if awal is None:
        return str(body).strip(), ""

    jawaban = baris[:awal]
    kutipan = baris[awal:]

    # Baris kosong tepat sebelum kutipan bukan milik siapa-siapa.
    while jawaban and not jawaban[-1].strip():
        jawaban.pop()

    # Lalu baris atribusinya, kalau ada. DICOBA DARI YANG TERPENDEK, dan itu
    # bukan selera: ATRIBUSI memakai .search(), jadi menggabung tiga baris lalu
    # mencocokkan akan tetap kena meski polanya hanya ada di baris terakhir —
    # dan tiga baris itu ikut terhapus, termasuk jawaban vendornya. Versi
    # pertama fungsi ini mencoba dari terpanjang dan menelan "Jawaban saya."
    # pada atribusi satu baris. Mulai dari satu baris: yang terlipat tidak akan
    # cocok pada n=1 (potongan "wrote:" tidak memuat alamat) lalu tertangkap
    # di n=2, sedangkan yang satu baris berhenti tepat di n=1.
    # BATASNYA, dan ini disengaja: atribusi yang terlipat TIGA baris menyisakan
    # baris pertamanya ("On Fri, 21 Aug 2026") karena n=2 sudah cocok lebih
    # dulu. Dibiarkan. Salahnya mengarah ke sisi yang benar — satu baris nyasar
    # yang jelek dipandang, bukan jawaban vendor yang hilang tanpa jejak. Untuk
    # membereskannya perlu menebak baris pembuka atribusi, dan itu balik lagi
    # ke daftar kata per bahasa yang justru dihindari di atas.
    for n in range(1, MAKS_ATRIBUSI + 1):
        if len(jawaban) < n:
            break
        if ATRIBUSI.search(" ".join(x.strip() for x in jawaban[-n:])):
            del jawaban[-n:]
            break

    while jawaban and not jawaban[-1].strip():
        jawaban.pop()

    return "\n".join(jawaban).strip(), "\n".join(kutipan).strip()
