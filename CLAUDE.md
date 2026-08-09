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
- Pico.css v2 via CDN. Custom CSS limited to status badges and metric
  cards. No Tailwind, no React, no build step.
- Config via .env

Dependencies: fastapi, uvicorn[standard], jinja2, python-multipart,
python-dotenv, aiosmtplib. Nothing else without asking.

Language:
- UI labels, page titles, and button text: Indonesian.
- Route paths, column names, function names, variables, comments, and commit
  messages: English.

email_templates/ stays Indonesian — the emails go to Indonesian vendors.
renderer.format_tanggal renders dates in Indonesian for the message body;
format_date and format_datetime render them for the interface.

## Flow
brief → select category + check vendors (cross-category) → preview →
send (batched, with progress) → tracker

Three pages: Vendor (CRUD), Kirim, Tracker.

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

Rationale:
- vendor↔category is many-to-many; tent vendors commonly also supply
  chairs and staging
- outbox.email_tujuan is denormalized so history stays accurate if a
  vendor's email changes
- outbox.message_id is groundwork for future reply-matching
- subject_template separate from body: subject must be unique per vendor
  or Gmail collapses the batch into one thread

## Invariants

1. PRAGMA foreign_keys = ON on EVERY new connection, not once at init.
2. DRY_RUN defaults True. When true, never open an SMTP connection —
   log to/subject/body only.
3. Preview screen is mandatory before send. Send button must never
   dispatch directly.
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
10. All SQL lives in db.py. No queries in handlers.
11. status='sent' never reverts to 'draft'. Retry only from 'failed'.

## Out of scope — do not build
auth/login · automated reply parsing · quotations table · price
comparison · file attachments · per-category templates · calendar
integration · Docker · CI · comprehensive tests

If you believe one is necessary, state the reason first. Do not build it.

## Working style
- One phase at a time. Stop at each checkpoint and await confirmation.
- Small functions, no premature abstraction.
- No UI polish before phase 5 is complete.
- Do not create files outside the current phase's spec.

## Reporting
After each phase, report in this format only:
- Files created/modified — paths only
- Deviations from spec + one-line rationale each
- Blockers or decisions needing my input

No summaries, no next-step suggestions, no restating what was asked.

## Dependency addition
python-docx — document generation. No other new dependencies.

## Schema addition

spk(id PK, request_id FK, vendor_id FK, nomor TEXT UNIQUE,
    harga INTEGER, lingkup_kerja TEXT, termin TEXT,
    tanggal_terbit TEXT, created_at TEXT,
    UNIQUE(request_id, vendor_id))

Rationale: the SPK must be re-downloadable with the same nomor. Storing
it makes the number stable and gives procurement a record of what was
issued.

## Additional invariants

12. Nomor surat is allocated once, at row insert, inside a transaction.
    It must never be recomputed on download — a document reprinted next
    month must carry its original number.
13. harga stored as INTEGER rupiah, no decimals, no formatting. Display
    formatting and terbilang are presentation concerns.
14. One SPK per (request_id, vendor_id). Re-issuing means editing the
    existing row, not creating a second.