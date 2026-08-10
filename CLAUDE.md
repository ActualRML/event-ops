# Vendor RFQ Blast — MVP

## Context
Internal tool for an event-organizer company. Procurement staff currently
email vendors one-by-one to request quotes (RFQ). That manual send loop is
the bottleneck this tool removes.

Demo MVP, not production. Priority: complete end-to-end flow over code
quality. Optimize for something demonstrable, not something maintainable.

## Stack
- Python 3.12, FastAPI, Jinja2, HTMX
- SQLite, raw SQL via sqlite3 stdlib. No ORM.
- aiosmtplib, Gmail SMTP + app password
- Pico.css v2 and HTMX 2.0.4, both via CDN. All custom CSS is one
  <style> block in base.html — no .css files, no Tailwind, no React,
  no build step.
- CSS class names are Indonesian by convention (.baris-vendor,
  .metrik-kartu, .form-kirim). This is deliberate and uniform — do not
  rename them piecemeal.
- Config via .env

Dependencies: fastapi, uvicorn[standard], jinja2, python-multipart,
python-dotenv, aiosmtplib, python-docx. Nothing else without asking —
everything else in requirements.txt is transitive (lxml from
python-docx; httptools, watchfiles, websockets, PyYAML from
uvicorn[standard]).

Language — the split is by audience, not by file:

- Anything a vendor reads is Indonesian: email_templates/, the rendered
  subject and body, and the generated SPK .docx. These are outbound
  correspondence and formal documents; never translate them.
- Anything only procurement staff reads is English: UI labels, page
  titles, button text, table headers, empty states, validation messages.
  (Originally specified as Indonesian; the UI was translated in full and
  the spec, not the code, was what was out of date.)
- Indonesian survives in the interface only as domain vocabulary with no
  English equivalent — "SPK" is the document's actual name — and as
  placeholder examples in fields whose contents get printed verbatim
  into the Indonesian document (scope of work, payment terms).
- Routes and comments: English. Commit messages: English.
- Identifiers: English for new code. Existing schema columns and the
  domain helpers around them are Indonesian (nama_pt, judul_acara,
  lingkup_kerja, terbilang, buat_spk_docx) — leave them; renaming a
  column to translate it buys nothing and breaks every query.

## Layout

    main.py          app object, Jinja filters, static mount, router includes
    deps.py          templates + parse_ids — what more than one router needs
    tasks.py         SEND_TASKS, dispatch_batch, schedule_batch (phase B)
    config.py        .env loading
    db.py            all SQL
    init_db.py       schema/seed CLI
    cek_email.py     one-off send test CLI
    core/            domain logic, no web layer
      mailer.py      SMTP send, honours DRY_RUN
      renderer.py    email subject/body rendering (vendor-facing)
      tampilan.py    interface formatting + SMTP error labels (staff-facing)
      dokumen.py     SPK .docx generation
      terbilang.py   number to Indonesian words
      penomoran.py   nomor surat formatting and sequence
    routes/          one APIRouter per area
      vendors.py     /, /vendors, /categories
      send.py        /send and its subpaths
      tracker.py     /tracker, detail, retry
      spk.py         /tracker/{id}/spk/...
    templates/  static/  email_templates/  db/

Import direction is one-way. core/ may import config and other core
modules, and nothing else from this project: never db, deps, tasks, or
anything under routes/. Routers may import db, deps, tasks and core.
Nothing imports main.

Imports of core are absolute — `from core import renderer`, or
`from core.terbilang import terbilang`. No relative imports.

templates/, static/ and db/ are addressed CWD-relative, so the app is
started from the project root and the uvicorn command is unchanged.
core/renderer.py is the one exception: it resolves email_templates/ from
__file__, and therefore climbs one level out of the package.

## Presentation split

core/renderer.py is vendor-facing, core/tampilan.py is staff-facing. Both
format the same values; they differ only in which audience reads the result.

- renderer.format_tanggal → Indonesian long form, for the message body
  only. renderer.render_email is the single render path: preview,
  dispatch and subject pre-rendering all call it (invariant 9).
- tampilan.format_date and tampilan.format_datetime → English long form,
  for the interface only. Both parse through renderer.ke_tanggal, so the
  two languages accept and reject exactly the same inputs and only the
  month table differs.
- tampilan.pesan_error maps an aiosmtplib exception name to one plain
  English line for the tracker's failure column. Translation happens on
  display, not on write: the raw "ExceptionName: detail" string stays in
  outbox.error_msg, so rows that already failed pick up reworded
  messages with no migration, and the full server response is still
  available in the cell's tooltip.

All three of tampilan's functions are registered as Jinja filters
(date, datetime, error_message) and are used by templates only.

mailer.kirim_email belongs to the mailer API, not the Send page family —
it is also called by cek_email.py. The send_* rename covered the page's
handlers, templates and context builder only; kirim_email keeps its name.

## Flow
brief → select category + check vendors (cross-category) → preview →
send (batched, with progress) → tracker

Three pages: Vendors (CRUD, /vendors), Send (/send), Tracker (/tracker).

## Schema

categories(id PK, nama UNIQUE COLLATE NOCASE)

vendors(id PK, nama_pt, pic_nama, email, no_hp, area, catatan,
        aktif DEFAULT 1 CHECK(aktif IN (0,1)), created_at)

vendor_categories(vendor_id FK, category_id FK,
                  PRIMARY KEY(vendor_id, category_id))

requests(id PK, judul_acara, tanggal_acara, lokasi, kebutuhan, deadline,
         pengirim_nama, subject_template, body_template, created_at)

outbox(id PK, request_id FK, vendor_id FK, email_tujuan, subject,
       status CHECK(status IN ('draft','sent','failed','replied')),
       error_msg, message_id, sent_at, created_at,
       UNIQUE(request_id, vendor_id))

spk(id PK, request_id FK, vendor_id FK, nomor TEXT NOT NULL UNIQUE,
    harga INTEGER NOT NULL CHECK(harga > 0),
    lingkup_kerja TEXT, termin TEXT,
    tanggal_terbit TEXT NOT NULL DEFAULT (date('now','localtime')),
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE(request_id, vendor_id))

v_vendor_lengkap — one row per vendor, with the vendor's categories
flattened into a single comma-joined `kategori` string. LEFT JOIN, so a
vendor with no category still appears with kategori NULL. Load-bearing:
the vendor list, the send-page picker and the outbox/tracker queries all
read the view rather than re-joining vendor_categories.

Indexes: idx_vendor_categories_category, idx_outbox_request,
idx_outbox_status, idx_vendors_aktif, idx_spk_request.

Rationale:
- vendor↔category is many-to-many; tent vendors commonly also supply
  chairs and staging
- outbox.email_tujuan is denormalized so history stays accurate if a
  vendor's email changes
- outbox.message_id is groundwork for future reply-matching
- subject_template separate from body: subject must be unique per vendor
  or Gmail collapses the batch into one thread
- spk is stored rather than generated on demand: the SPK must be
  re-downloadable with the same nomor. Storing it makes the number
  stable and gives procurement a record of what was issued.

harga was CHECK(harga >= 0) DEFAULT 0, which admitted a zero-value SPK
the validator in main.parse_harga already rejected. The constraint now
matches the validator. SQLite cannot alter a CHECK in place, so the live
db/rfq.db still carries the old one — it picks the new constraint up on
the next rebuild from schema.sql. No existing row violates it.

## Invariants

1. PRAGMA foreign_keys = ON on EVERY new connection, not once at init.
2. DRY_RUN defaults True. When true, never open an SMTP connection —
   log to/subject/body only.
3. The UI must expose no path that sends without passing through the
   preview screen. The send route is not independently authenticated —
   this is a demo MVP with no auth layer.
4. SEND_DELAY_SECONDS between sends.
5. A failed send never halts the batch — record status='failed' +
   error_msg, continue.
6. Send is two-phase: (A) persist request + outbox rows status='draft'
   in one fast transaction, then (B) dispatch in background, commit per
   email. Never wrap the send loop in a single transaction.
7. Progress is read from DB, never from in-memory state.
8. Double-send prevented at three layers: disabled button, server-side
   check, UNIQUE(request_id, vendor_id).
9. Preview and send must call the identical render function.
10. All application queries live in db.py. Route handlers contain no SQL.
    Standalone CLI scripts may run schema and maintenance SQL directly.
11. status='sent' never reverts to 'draft'. Retry only from 'failed'.
12. Nomor surat is allocated once, at row insert, inside a transaction.
    It must never be recomputed on download — a document reprinted next
    month must carry its original number.
13. harga stored as INTEGER rupiah, no decimals, no formatting. Display
    formatting and terbilang are presentation concerns.
14. One SPK per (request_id, vendor_id). Re-issuing means editing the
    existing row, not creating a second.

## Out of scope — do not build
auth/login · automated reply parsing · quotations table · price
comparison · file attachments · per-category templates · calendar
integration · Docker · CI · comprehensive tests

If you believe one is necessary, state the reason first. Do not build it.

## Working style
Feature work is complete. What remains is maintenance on a working
system, not phased delivery.

- Changes are targeted and scoped to what was asked. Do not widen a
  request into adjacent cleanup, and do not narrow it either — if part
  of it is blocked, do the rest and say what was left.
- Small functions, no premature abstraction.
- Propose structural changes — renames, new modules, schema edits,
  refactors — rather than applying them. Describe the change and what it
  touches, then wait.

## Reporting
- What changed — paths, and what each edit did
- Deviations from what was asked + one-line rationale each
- What was verified, and how — commands run and their actual result.
  Distinguish what was checked from what was assumed.
- Blockers or decisions needing my input