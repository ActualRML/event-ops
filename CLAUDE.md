# Event Ops — MVP

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
      rundown.py     schedule arithmetic, pure functions
    routes/          one APIRouter per area
      vendors.py     /, /vendors, /categories
      send.py        /send and its subpaths
      tracker.py     /tracker, detail, retry
      spk.py         /tracker/{id}/spk/...
      rundown.py     /tracker/{id}/rundown and its items
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

- renderer.format_tanggal → Indonesian long form. Vendor-facing, which is
  now two things: the message body, and the printed rundown, which crew
  and vendors read on site. renderer.format_durasi is its companion —
  minutes as "1 j 30 mnt", the print counterpart of tampilan.format_durasi
  ("1 h 30 min"). Same shape and rounding; only the unit words differ.
  renderer.render_email is the single render path: preview, dispatch and
  subject pre-rendering all call it (invariant 9).
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

Six Jinja filters, and which one you reach for is decided by audience,
not by convenience:

- staff-facing, from tampilan — `date`, `datetime`, `error_message`,
  `duration`. Everything the interface renders.
- vendor-facing, from renderer — `tanggal`, `durasi`. The printed rundown
  only; the email body calls renderer directly rather than through a
  filter. Indonesian filter names on purpose: `| tanggal` sitting next to
  `| date` in a template says which audience the value is for without
  looking anything up.

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

## UI conventions

Recorded from the running app at a 1366px viewport, reading computed
styles rather than the stylesheet, and re-measured after the audit fixes
landed. Every value below is what renders today, not what ought to
render. All custom CSS lives in the one `<style>` block in
`templates/base.html`.

### Units — all new CSS is written in px

**Write px. Do not use rem.** Pico's responsive root font size makes rem
a moving target: 16px base, stepping up at 576/768/1024/1280/1536px, so
at any desktop width from 1280px up **1rem = 20px**, not 16px. Mixing
the two units is what produced every size mismatch the audit found.

The root font size is deliberately **not** pinned. The current rendering
is approved, and overriding the root would resize every rem value still
in the sheet at once — a full visual re-review for no gain. Existing rem
values stay; new ones are not added.

Still in rem, rendering at 1280px and up: tables (.9rem → 18px body,
.72rem → 14.4px headers), badges (.75rem → 15px), chips (.8rem → 16px),
nav links (.85rem → 17px), brand (.78rem → 15.6px), h2 (1.5rem → 30px),
metric numbers (1.9rem → 38px), `.btn-mini` (.72rem → 14.4px), and the
`.metrik` / `.aksi-grup` gaps.

Everything else is px and fixed: every form control (34px tall, 14px
text, 13px labels, 12px helper text), the /vendors controls row, section
h3 (13px), `.status-batch` (14px), `.konteks` (11px/14px), `.pratinjau`
(13px), vendor picker rows (14px), `#counter` (13px), footer (12px).

Table body text still renders 18px against a 14px form control. That is
the one remaining rem/px gap, left alone on purpose — closing it means
restating the whole table scale in px, which is a visual change rather
than a cleanup.

### Text colour

One dark value, `#3c3a38`, written once as `--teks-gelap` on
`:root[data-theme="light"]` and fed to `--pico-color` and
`--pico-h1-color`…`--pico-h6-color`. Body text, table text and every
heading inherit it; nothing restates the literal.

Two things to know before reusing it:

- The override sits on `:root[data-theme="light"]`, not a bare `:root` —
  Pico defines its palette under a two-part selector that a bare `:root`
  loses to.
- Inside an `hgroup`, and in some other Pico components, Pico redefines
  `--pico-color` locally to the muted colour. Read `--teks-gelap`
  directly in those places. `.chip-angka` is the live example.

Muted text is `--pico-muted-color` (#646b79) throughout. Links keep
their own colour: Pico redefines `--pico-color` inside `<a>`, which is
what leaves the nav untouched. Semantic colours are unaffected by the
above — `#2e7d32` sent/active, `#b3261e` failed/danger, `#1565c0`
replied, `#78848f` draft/inactive.

### Page shell

- Page background `#f6f7f9`; every surface on it is `#fff`.
- Panel is `main.container` itself — no page adds a wrapper.
  `max-width: min(1200px, calc(100% - 48px))`, centred, so the gutter to
  the viewport is 24px each side and never collapses on narrow screens.
- Panel border `1px solid #e4e7eb`, radius **10px**, padding
  `14px 24px 32px`, margin-block `10px 12px` (10px of grey above,
  12px below to the footer).
- Shadow, deliberately barely visible:
  `0 1px 2px rgba(16,24,40,.04), 0 2px 6px rgba(16,24,40,.03)`.
- 24px is the horizontal gutter everywhere — panel, header nav, footer
  all share the same `max-width` + `padding-inline: 24px` pair, so the
  brand, the page title and the footer text sit on one vertical line.
- A page ending in `table.tabel` drops the panel's bottom padding, the
  table's bottom margin and the last row's hairline (`:has()` rule), so
  the panel border closes the table.

### Header bar and footer

| | header `.bilah` | footer `.kaki` |
|---|---|---|
| height | 59px | 42px |
| padding-block (inner) | 14px | 12px |
| background | `#fff` | `#fff` |
| border | bottom `1px #e7eaf0` (`--pico-muted-border-color`) | top `1px #eef0f3` |
| text | brand 15.6px/600/uppercase/1.09px tracking, muted; nav links 17px/500 | 12px/1.4 muted |

The footer border is one step lighter than the header's on purpose — the
header stays the heavier of the two. `.kaki` uses `margin-top: auto`
against a flex-column body, so the slack lands on the grey page, not
inside the panel.

Nav links: muted, 8px/15px padding, radius 8px, hover fills
`rgba(128,138,148,.14)`. Active page = weight 600, fill
`rgba(128,138,148,.16)`, plus `inset 0 -2px 0` underline in the link
colour.

### Page title block

Two shapes, chosen by whether the page has a context line:

- **With chips** — plain `<hgroup>`: h2 (30px/1.25, `-.02em`)
  → 4px → `.chips` → **20px** to whatever follows. Used by /vendors,
  /tracker, /tracker/{id}, and the SPK form when editing an existing SPK.
- **Title only** — `<hgroup class="judul-rapat">`: h2 margin-bottom 0,
  hgroup margin-bottom **16px**. Used by /vendors/new, /send, preview,
  /categories/new, and the SPK form when issuing a new one.

The 16px/20px split is a rule, not drift: it tracks whether the page has
a context line. Chips carry their own visual mass, so the block below
them needs the extra 4px to sit clear. Pick the shape by whether the
page has chips, and the spacing follows.

Chips are the only context-line form in use — no prose subtitles exist,
though `main hgroup > p` is styled for one (.875rem muted). A chip is
white on `1px #e4e7eb`, radius 999px, 4px/10px padding, 16px muted text,
with `.chip-angka` carrying the value at weight 500 in `--teks-gelap`.
Gap between chips 8px. Chips are used for counts (`25 vendors`), for
labelled values (`event 19 September 2026`), and for bare state labels
(`newest first`).

### Forms

The whole form scale lives on `.form-rapat`, and every form page carries
it plus one of `.form-vendor` (record forms) or `.form-kirim` (Send).

- Control height **34px** for input/select — 14px/1.4 text + 6px/10px
  padding + 1px border. Textarea is `height: auto` at the same padding.
  34px is the height for every control outside a table row, including
  the /vendors controls row.
- One border and one radius across every text control: **`#e4e7eb`,
  8px**, matching the select and the read-only blocks. This overrides
  Pico's own `#cfd5e2`/5px and the pill radius Pico gives
  `type="search"`. Set by two rules in `base.html` whose `:not()` chains
  clear Pico's specificity; border-color is applied separately so an
  `aria-invalid` field keeps its red border (`#b86a6b`) and still takes
  the radius. Checkboxes, radios and the switch are deliberately outside
  this and keep Pico's `#cfd5e2` at 5px.
- Label 13px/1.3, weight 500, margin-bottom 0.
- Label → its control: **4px** (`margin-top` on the control; the whole
  `<label>` is the field group, control nested inside).
- Helper/error `<small>`: block, 12px, 4px above.
- Field row → next field row: **12px** on `.form-vendor` (`> label`,
  `> fieldset`, `> .grid-isian`), **16px** on `.form-kirim`
  (`section > label`, `section > .grid`).
- Two-column grid: `.grid-isian` on the vendor form —
  `1fr 1fr`, column-gap 20px, row-gap 12px, short fields two per row, an
  odd count leaving the last cell empty. Send instead uses Pico's own
  `.grid` for its one paired row (the two date fields, 20px gap).
  Full-width fields (Notes, Requirements, Scope of work) sit outside the
  grid as direct children.
- `.form-sempit` caps a form at 420px — /categories/new only.
- Checkbox rows are not field groups: `.kotak-kategori` is a wrapping
  flex row, 6px/16px gap, 13px labels at weight 400.

Sections (`main section > h3`) group fields on Send and preview: 13px/600,
`border-top: 1px #eef0f3`, padding-top 16px, margin-bottom 12px. The rule
is the section divider — no nested panels anywhere in the app.

`main section:first-of-type > h3` drops both the border and the
padding-top: the first section on a page has nothing above it to divide
from, and the rule would otherwise draw a hairline immediately under the
page title. Its heading lands the same 16px below the title that
`.judul-rapat` gives every other title-only page.

### Buttons

Three levels, all 34px tall / 14px / 6px 14px padding / radius 5px when
they sit in an action row:

1. **Primary** — Pico default fill `#0172ad`, white text. One per page,
   always last in the row. Save (vendor, category), Continue to preview,
   Send now, Retry failed, Issue SPK / Update, Add Vendor.
2. **Secondary** — `class="secondary outline"`, transparent on `#5d6b89`
   border and text. Cancel, Back, All requests, Add Category, and every
   in-table action button.
3. **Muted (`.btn-mati`)** — transparent on `--pico-muted-border-color`,
   muted text, turning `#b3261e` on hover/focus only. The destructive
   in-table action: Deactivate/Activate in the vendor table, Remove in
   the rundown table.

Row containers:

- `.baris-aksi` — left-aligned, 8px gap, no top margin. Data-entry
  forms: vendor form, category form, SPK form. Only here does the submit
  get a fixed 110px width (`.form-vendor .baris-aksi button[type=submit]`).
- `.baris-aksi-kanan` — right-aligned, 8px gap, margin-top 20px,
  primary last. Send, preview, tracker detail.
- `.aksi-halaman` — right-aligned, 8px gap, inside the controls row.
  /vendors only. `main > .grid :is(select, input, button, [role=button])`
  pins every control in that row to the same 34px/14px as a form control,
  so the filter select, the search box and both page buttons match the
  record forms. The explicit height is load-bearing: Pico gives input and
  `[role=button]` a height derived from 1rem while select and button stay
  content-sized, so the row stair-steps without it.
- `.aksi-grup` — in-table pair, right-aligned, .25rem gap, children
  `flex: 1 1 0; max-width: 6rem` so both measure equal down the column.
  `.btn-spk` lifts the cap when it is alone in the cell.

`.btn-mini` (in-table): 14.4px, `.2rem/.25rem` padding, full-width in its
flex slot, ellipsised — 32px tall, not 34px. **32px is for table rows
only.** It never sits beside a form control; anything outside a row is
34px.

Disabled: `opacity: .45; cursor: not-allowed; filter: grayscale(35%)`.

### Tables

One look everywhere via `.tabel`; `table-layout: fixed` with a per-table
`<colgroup>` in percentages is how every column width is set — no
`min-width`, no `<th>` sizing. Widths in use:

- vendors: 24/14/20/13/11/18
- tracker: 6/32/16/18/18/10
- tracker detail: 19/11/17/11/13/13/16
- preview: 34/40/26
- rundown: 5/13/26/10/13/15/18 — the last two columns are a pair of
  `.btn-mini` each, and 15/18 is what stops "Down" and "Remove" clipping

Cells `.35rem .6rem` (7px/12px), `vertical-align: middle`,
`overflow-wrap: break-word`. First and last columns zero their outer
padding so the table's edges line up with the heading above and the
button beside it. Header row: 14.4px uppercase, `.04em` tracking, muted,
nowrap, `border-bottom: 3px` (Pico's thead default) against 1px on body
rows, both `#e7eaf0`.

Secondary text: `.redup` (muted, .85em) for PIC, email, timestamps.
`.sel-teks` clips single-token values to one line with the full value on
`title`. `.angka` right-aligns with tabular numerals.

Badges — 15px, radius 999px, `.15rem .55rem`, white text, nowrap,
ellipsised, one class per status keyed off the raw DB value:

| class | colour | shown as |
|---|---|---|
| `.badge-aktif` / `.badge-sent` | `#2e7d32` | Active / Sent |
| `.badge-nonaktif` / `.badge-draft` | `#78848f` | Inactive / Pending |
| `.badge-gagal` / `.badge-failed` | `#b3261e` | N failed / Failed |
| `.badge-replied` | `#1565c0` | Replied |

Inactive rows get `opacity: .45` on the whole row.

Metric cards (tracker detail only): 3-up grid, 20px gap, 30px below,
dropping to 2-up under 720px. Card is `1px --pico-muted-border-color`,
radius **8px** — the same as `.konteks` and `.pratinjau`, all three
being the same idea — `.9rem 1rem` padding, no fill. Number 38px/600,
label 15px uppercase muted. Sent green `#2e7d32`, Failed red `#b3261e`,
Total inherits.

### Warnings and empty states

- **Validation** — bare Pico `<article>`: white, radius 5px, 20px
  padding, 20px below, Pico's own large shadow. Bold lead sentence, then
  one plain line. Same shape on every form page.
- **Serious, as opposed to routine** — `article.peringatan` adds
  `border-left: 3px #b3261e`. Two uses, and they differ in whether they
  block: on the SPK form the vendor or request is missing required data
  and the submit is disabled alongside it; on the rundown the schedule
  runs past the venue limit, which is a real schedule to be flagged, not
  an error, so nothing is disabled. The red rule marks weight, not a
  blocked state — read the surrounding controls for that.
- **Empty table** — a single `<td class="kosong" colspan=…>`: muted,
  italic, `padding-block: 30px`. Every empty state is written as
  a sentence plus the next action ("Start with 'Add Vendor' — …"), and
  /vendors varies it three ways (search / filter / genuinely empty).
- **Inline reassurance** — `p.redup` under the tracker detail table when
  a batch finished clean.
- Read-only value blocks share one surface: `#fbfcfd` on `1px #e4e7eb`,
  radius 8px, `12px 14px` padding — `.konteks` (SPK form, 2-col dl,
  11px uppercase dt over 14px dd, collapsing to 1 col under 720px) and
  `.pratinjau` (preview).

### Preview page

Measured on a rendered preview, not read off the stylesheet.

- `.pratinjau` — the rendered email body, a `<pre>`: 13px /
  line-height 20.15px in Pico's monospace stack (`ui-monospace,
  SFMono-Regular, "SF Mono", Menlo, Consolas, …`), background `#fbfcfd`,
  `1px solid #e4e7eb`, radius 8px, padding `12px 14px`, margin 0,
  `white-space: pre-wrap`, `overflow-x: auto`. It is the only monospace
  surface in the app — the real email is plain text, so only the box
  around it is brought into line.
- `.subjek` above it — 14px/1.5 in `--teks-gelap`, 12px below, with a
  bold `Subject:` lead.
- Action row is `.baris-aksi-kanan` (right-aligned, 8px gap, 20px top
  margin), both buttons 34px tall at 14px with 14px inline padding and
  radius 5px: **Back** secondary-outline, 63px wide, transparent on
  `#5d6b89`; **Send now** primary, 96px wide, `#0172ad` filled.
  Back is first in source order on purpose — implicit form submission
  picks the first submit button, so Enter can never reach the dispatch
  route.
- Both sections follow the shared rule: `Sample email` is
  `:first-of-type` and draws no top border; `Recipients` draws its
  `1px #eef0f3` divider with 16px above.

### Print

The rundown is the one page meant to leave the screen, and it prints from
the screen DOM — there is no print route, so there is no second copy to
drift. The `@media print` block at the end of `base.html` hides everything
that is not the schedule: nav, footer, both editing forms (picked by
`section:has(.form-rapat)`, not by position), every action row, and the
rundown table's two action columns. px throughout, as everywhere else —
in print 96px is one inch, and `@page` margin is 48px.

Colour is the first thing a mono printer discards, so nothing may depend
on it: every muted value returns to black, and the over-limit warning
prints as a plain sentence with a bold lead rather than a red-ruled card.

Language follows the audience, not the file. The printed sheet is carried
by crew and vendors on site, so the **whole sheet** is Indonesian under
the vendor-facing rule, alongside the SPK — while the screen stays
staff-facing English. Both versions live in the same element: `.layar`
shows on screen, `.cetak` in print, and `@media print` swaps the pair.
That covers the table headers, the section title (Susunan Acara), all six
chip labels, the duration cells, the totals line and the over-limit
warning. Values follow too where the language changes them: the event
date goes through `| tanggal` and every duration through `| durasi`.

What carries no `.layar`/`.cetak` pair, because it reads the same either
way: `#`, `PIC`, clock times, the venue name, and the item text itself,
which procurement already types in Indonesian. Indonesian has no plural
inflection, so the `.cetak` half never needs the `"s" if n != 1` suffix
its English twin carries.

Catatan has no header of its own — it prints as the second line inside
Kegiatan, which is where it sits on screen too, so no value is duplicated
in the markup.

Column hiding is scoped to `.tabel-rundown` rather than keyed off
`td.aksi` + `th:empty`, because that pairing misfires elsewhere: preview
has an empty header over a data cell, and tracker detail has a labelled
`SPK` header over an action cell.

**The one `!important` in the codebase** — `.tabel-rundown col { width:
auto !important }` — is a reasoned exception, not a precedent. The column
widths are inline `style` attributes on `<col>`, which no stylesheet rule
can outrank; without releasing them the two hidden action columns go on
reserving a third of the table and the five printed columns stay squeezed.
Any future `!important` has to clear the same bar: the value it overrides
must be genuinely unreachable by the cascade — an inline style, or a
third-party rule that cannot be edited — not merely tedious to outweigh.
If a selector can win on specificity or source order, it must.

### Spacing scale actually in use

`2 · 4 · 6 · 8 · 10 · 12 · 14 · 16 · 20 · 24 · 30 · 32`

The recurring ones and what they mean: **4px** label→control and
h2→chips · **8px** every action-row and chip gap, vendor-row padding ·
**12px** field→field on record forms, section h3→content, footer
padding, panel→footer · **16px** field→field on Send, section rule→
heading, title-only block→content, controls row→table · **20px** grid
column gap, title+chips block→content, action row top margin, metric
gap, `<article>` padding · **24px** the horizontal gutter, everywhere ·
**30px** metric cards→status line, empty-state padding-block · **32px**
panel bottom padding.

Radii in play, after the audit fixes:

- **8px** — every form control (input, textarea, select) and every
  bordered read-only box (`.konteks`, `.pratinjau`, `.metrik-kartu`),
  plus nav links. This is the default for new work.
- **5px** — buttons, `<article>`, checkboxes and radios, all inheriting
  Pico's `--pico-border-radius` at this root size.
- **10px** — the panel, and only the panel.
- **999px** — chips and badges.

### Resolved by the audit

The first audit found six places where two pages disagreed on the same
element. All six are fixed; the rules above are what replaced them, and
they are recorded here so the same ground is not re-litigated.

1. **Text-control border and radius** — inputs and textareas kept Pico's
   `#cfd5e2` at 5px beside selects at `#e4e7eb`/8px. Now one treatment,
   `#e4e7eb` at 8px, for every text control. See Forms.
2. **Metric-card radius** — 5px → 8px, matching the other bordered
   read-only boxes. See Tables.
3. **Control height** — the /vendors controls row ran at 32px against
   34px everywhere else. Now 34px, with 32px reserved for `.btn-mini`
   inside a table row. See Buttons.
4. **Two dark text colours** — `#3c3a38` and Pico's `#373c44` both in
   use. Now one value, `--teks-gelap`. See Text colour.
5. **First section's rule** — `section > h3` drew a hairline directly
   under the page title on Send and preview. Now suppressed on
   `:first-of-type`. See Forms.
6. **Title-block spacing, 16 vs 20** — kept as-is. It tracks whether the
   page has a context line, which is a rule rather than drift; it is
   written up under Page title block.

One rem/px gap is knowingly left open: table body text renders 18px
against 14px form controls. See Units.

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