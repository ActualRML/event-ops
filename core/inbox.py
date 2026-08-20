"""Reading mail: connect, fetch, and parse one message into a plain dict.

Pure of the database. Nothing here knows what a vendor or a batch is — it
turns bytes on a socket into dicts, and replies.py decides what they mean.
That split is what lets the parsing be exercised on a saved .eml with no
database at all.

The counterpart of core/mailer.py: mailer sends, this reads. Neither is
gated by DRY_RUN — that is a send guard, and reading a mailbox sends nothing.
"""

import email
import imaplib
import re
from email.header import decode_header, make_header
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser

import config

# Tags whose CONTENT is never text: dropped entirely rather than stripped to
# their inner text, which would otherwise dump CSS and JavaScript into the body.
TAG_BUANG = {"script", "style", "head", "title"}

# Tags that end a line. Without these the whole message collapses into one
# paragraph, because HTML's own newlines are not significant.
TAG_BARIS = {"p", "br", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
             "table", "blockquote", "pre", "hr"}

KOSONG_BERLEBIH = re.compile(r"\n{3,}")


class _Teks(HTMLParser):
    """Strip HTML to plain text.

    convert_charrefs=True is the default and is why nothing here decodes
    entities by hand — &amp; and &#8212; arrive already converted.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bagian: list[str] = []
        self._lewati = 0

    def handle_starttag(self, tag, attrs):
        if tag in TAG_BUANG:
            self._lewati += 1
        elif tag in TAG_BARIS:
            self.bagian.append("\n")

    def handle_endtag(self, tag):
        if tag in TAG_BUANG:
            # Guarded: a stray </style> with no opener would drive this
            # negative and then swallow the rest of the message.
            self._lewati = max(0, self._lewati - 1)
        elif tag in TAG_BARIS:
            self.bagian.append("\n")

    def handle_data(self, data):
        if not self._lewati:
            self.bagian.append(data)

    def teks(self) -> str:
        gabung = "".join(self.bagian)
        # Trailing spaces come from indented markup and would otherwise show
        # up as ragged whitespace in a <pre> block on the reply page.
        baris = [b.rstrip() for b in gabung.splitlines()]
        return KOSONG_BERLEBIH.sub("\n\n", "\n".join(baris)).strip()


def html_ke_teks(html: str) -> str:
    """HTML to plain text. Never used to render — the result is stored and
    displayed as text, and the markup is gone before it reaches the database.

    A malformed document is not an error here: HTMLParser is tolerant by
    design, and half a body beats none."""
    p = _Teks()
    p.feed(html)
    p.close()
    return p.teks()


def _decode(bagian) -> str:
    """One part's payload as str, whatever it says its charset is.

    errors="replace" rather than raising: a mojibake body is still readable
    enough to act on, and dropping the message loses a quote."""
    isi = bagian.get_payload(decode=True)
    if isi is None:
        return ""
    charset = bagian.get_content_charset() or "utf-8"
    try:
        return isi.decode(charset, errors="replace")
    except LookupError:
        # A charset name the codec registry does not know.
        return isi.decode("utf-8", errors="replace")


def _judul(raw) -> str:
    """A header that may be RFC 2047 encoded, as plain str."""
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        # Malformed encoded-words are common in the wild; the raw form is
        # still more useful than nothing.
        return str(raw)


def alamat_bersih(raw: str) -> str:
    """An address normalised for comparison: the bare addr-spec, lowercased.

    "PT Alpha <Budi@Example.COM>" and "budi@example.com" are the same vendor,
    and the gate compares against vendors.email, which is typed by hand and
    inconsistently cased. Returns "" when there is no address to find."""
    if not raw:
        return ""
    pasangan = getaddresses([raw])
    if not pasangan:
        return ""
    return (pasangan[0][1] or "").strip().lower()


def _nama_pengirim(raw: str) -> str:
    """The display name on a From header, or "" if it carries none."""
    if not raw:
        return ""
    pasangan = getaddresses([raw])
    if not pasangan:
        return ""
    return _judul(pasangan[0][0] or "").strip()


def rujukan(pesan) -> list[str]:
    """Every Message-ID this message points at, In-Reply-To first.

    References is a space-separated chain and In-Reply-To is normally its last
    entry, but not every client sets both — so both are read and the result is
    deduped with order kept. Order matters: In-Reply-To is the direct parent
    and is the one worth matching first."""
    hasil: list[str] = []
    for header in ("In-Reply-To", "References"):
        nilai = pesan.get(header) or ""
        hasil.extend(re.findall(r"<[^<>@\s]+@[^<>\s]+>", nilai))
    return list(dict.fromkeys(hasil))


def _waktu(pesan) -> str:
    """The Date header as 'YYYY-MM-DD HH:MM:SS' local time.

    THIS IS THE SENDER'S CLOCK. It can be skewed, plain wrong, or earlier than
    the RFQ it answers — a reply that appears to predate its own request is a
    badly-set clock, not corruption. inbox.created_at is ours and is the
    tie-break when a listing needs one.

    An unparseable or absent Date falls back to empty, and the caller supplies
    its own clock rather than inventing one here."""
    raw = pesan.get("Date")
    if not raw:
        return ""
    try:
        waktu = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return ""
    if waktu is None:
        return ""
    if waktu.tzinfo is not None:
        waktu = waktu.astimezone()
    return waktu.strftime("%Y-%m-%d %H:%M:%S")


# Precedence values that mean "generated, not typed". Not a standard header —
# it predates RFC 3834 and is still what a lot of older autoresponders set.
PRECEDENCE_OTOMATIS = {"auto_reply", "bulk", "junk"}


def otomatis(pesan) -> bool:
    """Was this message generated rather than typed by a person?

    WHY THIS MATTERS ENOUGH TO HAVE ITS OWN COLUMN. An out-of-office comes from
    the vendor's OWN address and usually carries In-Reply-To, so it sails past
    the gate and lands at tier 1 — a perfect match to the exact outbox row. It
    then counts as a reply, and "5 of 8 vendors have replied" is wrong. That
    count is the whole point of the feature, so a vacation notice must not be
    able to inflate it.

    This is the opposite situation from a bounce, which never reaches the
    ladder because mailer-daemon is not a vendor. An auto-reply IS the vendor.

    BY HEADER, NEVER BY HEURISTIC. No subject sniffing for "Out of Office" or
    "Automatic reply": those are localised, and this app writes to Indonesian
    vendors whose servers answer in Indonesian, so a word list would be both
    incomplete and quietly wrong. A header is a statement by the sending
    system about itself.

    Three mechanisms, in the order they became conventional:

    1. Auto-Submitted (RFC 3834). Present and anything other than "no" means
       automatic — the values are auto-generated, auto-replied, auto-notified,
       and a parameter may follow a semicolon.
    2. X-Autoreply / X-Autorespond. Presence alone; these carry no meaningful
       value.
    3. Precedence: auto_reply, bulk or junk.
    """
    nilai = pesan.get("Auto-Submitted")
    if nilai:
        # "auto-generated; type=vacation" -> "auto-generated"
        pokok = str(nilai).split(";")[0].strip().lower()
        if pokok and pokok != "no":
            return True

    if pesan.get("X-Autoreply") or pesan.get("X-Autorespond"):
        return True

    precedence = pesan.get("Precedence")
    if precedence and str(precedence).strip().lower() in PRECEDENCE_OTOMATIS:
        return True

    return False


def _lampiran_p(bagian) -> bool:
    """True when a part is an attachment rather than body text.

    Tests the disposition, not the content type: a quote sent as text/plain
    with a filename is an attachment, and treating it as the body would put a
    file's contents in the message and lose the file."""
    disposisi = (bagian.get_content_disposition() or "").lower()
    if disposisi == "attachment":
        return True
    # inline with a filename is still a file — usually an embedded image, but
    # a vendor's scanned quote arrives this way too.
    return disposisi == "inline" and bool(bagian.get_filename())


def urai(mentah: bytes) -> dict:
    """One raw RFC822 message as a plain dict.

    Body extraction prefers text/plain and falls back to STRIPPING text/html,
    because a large share of corporate senders emit no text/plain part at all.
    Reading only text/plain would store an empty body for those and fail
    silently — the row exists, the attachment is there, the message is blank.

    The HTML is never rendered. What is stored is text, which is what makes
    rendering it unavailable as a later mistake.
    """
    pesan = email.message_from_bytes(mentah)

    teks_biasa: list[str] = []
    teks_html: list[str] = []
    lampiran: list[tuple[str, str, bytes]] = []

    for bagian in pesan.walk():
        if bagian.get_content_maintype() == "multipart":
            continue

        if _lampiran_p(bagian):
            isi = bagian.get_payload(decode=True)
            if isi is None:
                continue
            nama = _judul(bagian.get_filename() or "") or "lampiran"
            lampiran.append((nama, bagian.get_content_type(), isi))
            continue

        tipe = bagian.get_content_type()
        if tipe == "text/plain":
            teks_biasa.append(_decode(bagian))
        elif tipe == "text/html":
            teks_html.append(_decode(bagian))

    if teks_biasa:
        body = "\n".join(teks_biasa).strip()
    else:
        body = html_ke_teks("\n".join(teks_html))

    # Line endings normalised so a body reads the same whichever branch above
    # produced it: real text/plain parts arrive CRLF off the wire, while
    # html_ke_teks emits LF. Without this the stored text differs by sender
    # rather than by content.
    body = body.replace("\r\n", "\n").replace("\r", "\n")

    dari = pesan.get("From") or ""
    return {
        "message_id": (pesan.get("Message-ID") or "").strip(),
        "from_email": alamat_bersih(dari),
        "from_nama": _nama_pengirim(dari),
        "subject": _judul(pesan.get("Subject")),
        "received_at": _waktu(pesan),
        "body": body,
        "rujukan": rujukan(pesan),
        "lampiran": lampiran,
        # Recorded, never acted on here. Storing it and letting the display
        # decide is the same shape as tier: an out-of-office is still worth
        # seeing, it just must not be counted as an answer.
        "otomatis": otomatis(pesan),
    }


def ambil(sejak: str | None, batas: int | None = None):
    """Every message received since a date, newest last, as raw bytes.

    sejak is a 'YYYY-MM-DD' date or None for "today only". IMAP SEARCH SINCE
    has DATE GRANULARITY ONLY — there is no "since 14:32" — so this always
    re-examines the whole of that day. Deduping on inbox.message_id is what
    turns the overlap into a no-op, which is why that UNIQUE is load-bearing
    rather than defensive.

    Raises whatever imaplib raises. The caller records the failure and leaves
    the watermark where it was; a failed run must never look like an empty one.
    """
    batas = batas or config.IMAP_MAX

    imap = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT,
                             timeout=config.IMAP_TIMEOUT)
    try:
        imap.login(config.IMAP_USER, config.IMAP_PASS)
        imap.select(config.IMAP_FOLDER, readonly=True)

        kriteria = ["SINCE", _tanggal_imap(sejak)]
        ok, data = imap.search(None, *kriteria)
        # A REFUSED SEARCH IS NOT AN EMPTY MAILBOX. Collapsing the two — which
        # this did — is the exact failure the whole feature is built to avoid:
        # the run would be recorded as a success with nothing found, the
        # watermark would advance past mail nobody read, and the interface
        # would say "no replies" with complete confidence. Raise instead, so it
        # lands in the failed-run path and shows as a banner.
        if ok != "OK":
            raise imaplib.IMAP4.error(f"SEARCH refused: {ok} {data!r}")
        if not data or not data[0]:
            return []

        nomor = data[0].split()
        # Newest last in a SEARCH result, so the tail is the recent end. A
        # mailbox with a year of history behind the watermark cannot make one
        # check unbounded.
        if len(nomor) > batas:
            nomor = nomor[-batas:]

        hasil = []
        for n in nomor:
            ok, isi = imap.fetch(n, "(RFC822)")
            # One unreadable message is skipped rather than raised on: the rest
            # of the run is still worth having, and the message is still on the
            # server to be picked up next time. This is the opposite call from
            # SEARCH above, and the difference is scope — a refused SEARCH
            # means we learned nothing about the whole mailbox, a refused FETCH
            # means we lost one message.
            if ok != "OK" or not isi or not isinstance(isi[0], tuple):
                continue
            hasil.append(isi[0][1])
        return hasil
    finally:
        # logout can itself raise on a half-dead socket, and that must not
        # replace the real error the caller is about to record.
        try:
            imap.logout()
        except Exception:
            pass


def _tanggal_imap(sejak: str | None) -> str:
    """'YYYY-MM-DD' to the DD-Mon-YYYY form IMAP SEARCH wants.

    The month is a fixed English table on purpose — RFC 3501 specifies these
    three-letter names, so this is protocol, not presentation, and it must not
    follow the interface's language or the machine's locale."""
    from datetime import date

    BULAN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    try:
        hari = date.fromisoformat((sejak or "")[:10])
    except ValueError:
        hari = date.today()
    return f"{hari.day:02d}-{BULAN[hari.month - 1]}-{hari.year}"
