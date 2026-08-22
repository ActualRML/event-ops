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
- Pico.css v2, HTMX 2.0.4 and the Inter webfont, all three via CDN, with
  --pico-font-family repointed at Inter. All custom CSS is one <style>
  block in base.html — no .css files, no Tailwind, no React, no build step.
  App-wide behaviour scripts follow the same rule: one <script> block at the
  end of base.html, delegated from document so it covers htmx swaps too. It
  holds exactly one thing — clicking anywhere in an <input type="date"> opens
  the calendar rather than only its ~16px icon. Page-specific scripts stay on
  their page (send.html has the vendor picker); anything two pages would both
  want goes in base.html instead of being copied, for the same reason the CSS
  does.
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
- Routes and comments: English. Commit messages: English. Docstrings too.
- Identifiers are MIXED, deliberately and consistently. "English for new
  code" was never what this codebase did — the rule below is, and it is
  what to follow. Read it as one rule with a split, not as an exception
  list:

  **The verb is English where a caller scans for it. The noun is whatever
  the domain calls the thing, and this domain is Indonesian.**

  So `format_tanggal`, `parse_harga`, `kode_exists`, `harga_zona` and
  `next_nomor` are all correct — an English verb on an Indonesian noun is
  the normal case here, not a half-finished translation.

  Where each side of that lands:

  - **English, because something outside the code binds to the name** —
    route handler functions (`event_list`, `send_dispatch`,
    `tracker_retry`), URL paths, template filenames, Jinja filter names.
    The one deliberate exception is the vendor-facing filter pair
    `tanggal`/`durasi`, whose Indonesian names are the whole point; see
    Presentation split.
  - **English verb, leading, for every public db.py function** — `list_`,
    `get_`, `create_`, `update_`, `set_`, `mark_`, `add_`, `remove_`,
    `delete_`, `move_`, `bump_`. That prefix is how the file is read.
  - **Indonesian throughout for pure domain operations in core/** —
    `terbilang`, `buat_spk_docx`, `buat_kode`, `tandai_subjek`,
    `hitung_jadwal`, `kirim_email`, `ke_tanggal`. These name a domain
    action, not a CRUD one.
  - **Indonesian as a matter of course for local variables and for
    module-private helpers** — `baris`, `hasil`, `calon`, `acara`,
    `permintaan`, `muat_spk`, `validasi_brief`, `pilih_event`,
    `pakai_kode`, `brief_dari_row`. This is the bulk of the code and it is
    uniform; matching it matters more than any of the above.
  - **Schema columns follow the domain noun** — nama_pt, judul_acara,
    lingkup_kerja, zona, kode. New columns included: `kode` is named for
    what the domain calls it, exactly as `zona` was. Never rename a column
    to translate it — it buys nothing and breaks every query.

  When in doubt, match the file you are editing. A name that reads like
  its neighbours is right even if this section did not anticipate it.

## Layout

    main.py          app object, Jinja filters and globals (merek, tahun,
                     perlu_perhatian), static mount, router includes
    deps.py          templates, parse_ids, parse_harga, parse_halaman,
                     query_ganti — what more than one router needs.
                     parse_harga takes label, allow_zero and contoh (the "not
                     a number" example, so the same parse also serves a
                     quantity field), capped at terbilang.MAKS
    tasks.py         SEND_TASKS, dispatch_batch, schedule_batch (phase B)
    replies.py       the reply check: IMAP fetch, gate, match ladder, store.
                     tasks.py's peer — see Import direction
    config.py        .env loading, and ZONA — the one mapping of zone key to
                     label and surcharge percentage, read by both the event
                     form and the price maths
    db.py            all SQL
    init_db.py       schema/seed CLI
    cek_email.py     one-off send test CLI
    cek_message_id.py  one-off round-trip check: does the server preserve the
                     Message-ID we set? Sends one real mail to ourselves and
                     reads it back. See "Reply matching" below
    core/            domain logic, no web layer
      mailer.py      SMTP send, honours DRY_RUN
      inbox.py       IMAP fetch and message parsing. mailer's counterpart,
                     and pure of db — bytes in, plain dicts out
      kode.py        the RFQ batch reference code — minting it, stamping it
                     onto a subject, reading it back off one. The one place
                     the format lives
      renderer.py    email subject/body rendering (vendor-facing)
      tampilan.py    interface formatting + SMTP error labels (staff-facing)
      dokumen.py     SPK .docx generation, format_rupiah
      terbilang.py   number to Indonesian words
      penomoran.py   nomor surat formatting and sequence
      rundown.py     schedule arithmetic, pure functions
    routes/          one APIRouter per area
      vendors.py     /, /vendors, /categories
      items.py       /items and its subpaths
      sponsors.py    /sponsors (the create form — no list), and every
                     sponsor RECORD under /tracker/sponsors/{id}
      events.py      /events, /events/new, /events/{id}/edit — no detail page
      send.py        /send and its subpaths
      tracker.py     /tracker (events), /tracker/{event_id} (that event's
                     batches), /tracker/batch/{request_id} and its retry
      spk.py         /tracker/batch/{request_id}/spk/{vendor_id} and download
      rundown.py     /events/{event_id}/rundown and its items
    templates/  static/  email_templates/  db/  README.md

config is also where the IMAP settings live. IMAP_USER and IMAP_PASS fall back
to the SMTP pair — same Gmail account, same app password, no second credential
— and exist only so the two CAN be separated. DRY_RUN does not gate them; see
invariant 2.

**db/rfq.db is no longer the whole system.** Attachment bytes live on the
filesystem under `attachments/`, so a `VACUUM INTO` of the database restores
every reply row with its filename, size and content type and not one byte of
any attachment — the rows look intact and the downloads 404. Copy
`attachments/` alongside the database. Nothing automates this.

Nothing prunes it either: **inbox rows and attachment files are never deleted;
revisit before the mailbox holds a year.** That is a decision, not an
oversight, and the two facts compound — the directory only grows, and only a
manual copy protects it.

**Schema changes are made by editing db/schema.sql and rebuilding.** There are
no migrations. `python init_db.py --force` deletes the database and builds a
new one from schema.sql and seed.sql; without `--force` it refuses, lists the
rows it would destroy, and prints the backup command it wants.

The data is demo data and it is regenerated, not preserved, so an ALTER TABLE
path buys nothing. There was a db/migrations/ directory of hand-applied
numbered SQL for four changes; every one of them was also folded into
schema.sql, which is what every build actually used, so the files were a second
description of the schema that nobody ran. Verified equivalent and deleted.

Column ORDER in schema.sql is therefore free — put a new column where it reads
best. Several existing ones sit at the end of their table for no better reason
than that ALTER TABLE could only append when they were added; that is history,
not a rule to follow.

Import direction is one-way. core/ may import config and other core
modules, and nothing else from this project: never db, deps, tasks,
replies, or anything under routes/. Routers may import db, deps, tasks,
replies and core. Nothing imports main.

tasks.py and replies.py are the same layer and the only two modules in it:
orchestration that needs db and core together but has no web layer of its
own. tasks.py runs the send batch; replies.py runs the reply check. Both
may import config, db and core; neither may import deps, routes or the
other. A router imports them, never the reverse.

That layer is not a general dumping ground. A third module belongs there
only if it, too, is a whole operation that a handler starts and then stops
caring about. Anything a handler needs *during* a request goes in deps.py,
and anything with no db dependency goes in core/.

config is importable from anywhere, routers included, and it is the one
module with that freedom. It earns it by being a leaf: it imports os and
dotenv and nothing from this project, so no import of it can ever close a
cycle, and it sits below every layer rather than beside one. Test a new
shared module against that before widening this list — a module that
imports any project code is not a leaf, and putting it here would let two
layers reach each other through it.

Imports of core are absolute — `from core import renderer`, or
`from core.terbilang import terbilang`. No relative imports.

templates/, static/ and db/ are addressed CWD-relative, so the app is
started from the project root and the uvicorn command is unchanged.
core/renderer.py is the one exception: it resolves email_templates/ from
__file__, and therefore climbs one level out of the package.

The product name lives in ONE place: `templates.env.globals["merek"]` in
main.py. It is in the header, the footer and the suffix of every page title,
and it used to be typed out in all twenty-two of them — so renaming the app
meant editing twenty-two files and missing one. Write `{{ merek }}`, never the
name. Four pages carry no suffix at all and name their record instead
(rundown.html, spk_form.html, sponsor_print.html, tracker_batch.html); that
predates the global and is left alone.

Template filenames are English, and the shape says what the page is:

    {plural}.html            a list page      vendors.html, items.html,
                                              events.html, tracker.html
    {singular}_form.html     a record form    vendor_form.html, item_form.html,
                                              sponsor_form.html, event_form.html,
                                              category_form.html, spk_form.html
    {singular}_detail.html   one record       sponsor_detail.html,
                                              reply_detail.html

The tracker is the one place the shapes do not reach, because it has TWO
record levels and the convention has a slot for one. It names the record
instead: tracker.html lists events, tracker_event.html is one event,
tracker_batch.html is one batch. `_detail` would have to mean two different
things here, so neither page uses it.
    {singular}_print.html    a printable      sponsor_print.html
    _{name}.html             a partial        _vendor_table.html, _progress.html,
                                              _vendor_stats.html, _send_pick_vendor.html,
                                              _sponsor_package.html, _sponsor_summary.html

send.html, preview.html, send_rejected.html and rundown.html predate the
convention and are named for the step they are, not the shape — they stay.

Out-of-band swaps follow one mechanism, and there is no second pattern:
the route sets `oob` on a real HTMX request; the swap target includes the
oob partial only when that flag is set; the partial itself carries
hx-swap-oob="true" only then. On a full page load the flag is false, the
target omits it, and the page includes the same partial in its own place
instead — one piece of markup either way, so the two halves cannot
disagree.

Two pairs use it. /vendors swaps the table (_vendor_table.html) and sends
the chips along (_vendor_stats.html), because the counts describe the rows.
Sponsor detail swaps the package table (_sponsor_package.html) and sends
the summary along (_sponsor_summary.html), because a quantity change moves
the totals and can cross the budget in either direction. Anything the swap
target does not contain but the change affects belongs in an oob partial.

One form template serves both create and edit, with the mode decided by
whether a record was passed in (item_form.html, sponsor_form.html read
`item` / `sponsor`). Two templates for one form drift; one cannot.

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
- tampilan.pesan_imap is its sibling for a failed reply check, with its own
  table rather than more branches in pesan_error: the two share no exception
  names, and the actions they suggest differ — a send failure is about one
  vendor's address, a read failure about the account or the network.
  Authentication is singled out because it is the one a user can fix, and it
  is what a fresh setup hits first, since Gmail also needs IMAP switched on in
  its own settings.
- tampilan.pesan_error maps an aiosmtplib exception name to one plain
  English line for the tracker's failure column. Translation happens on
  display, not on write: the raw "ExceptionName: detail" string stays in
  outbox.error_msg, so rows that already failed pick up reworded
  messages with no migration, and the full server response is still
  available in the cell's tooltip.

The Jinja filters, and which one you reach for is decided by audience, not
by convenience:

- staff-facing, from tampilan — `date`, `datetime`, `error_message`,
  `imap_error`, `duration`. Everything the interface renders.
- vendor-facing, from renderer — `tanggal`, `durasi`. The printed rundown
  and the printed sponsor sheet; the email body calls renderer directly
  rather than through a filter. Indonesian filter names on purpose:
  `| tanggal` sitting next to `| date` in a template says which audience
  the value is for without looking anything up.
- neither, from dokumen — `rupiah`. The odd one out: thousands grouped
  with dots is a locale convention rather than a language, so the SPK, the
  catalog table, the sponsor summary and the printed sheet all format an
  amount the same way and share dokumen.format_rupiah.

`rupiah` renders a negative as `Rp -750.000`, which reads as a broken
amount rather than a negative one. The one place a negative can occur —
Remaining on a sponsor — puts the sign outside the symbol in the template
instead (`−Rp 750.000`, U+2212). Do that anywhere else a negative appears.

mailer.kirim_email belongs to the mailer API, not the Send page family —
it is also called by cek_email.py. The send_* rename covered the page's
handlers, templates and context builder only; kirim_email keeps its name.

## Flow
pick event + category → check vendors (one category per batch) →
preview → send (batched, with progress) → tracker

The event is picked, never typed: /send offers a select over what exists
and links out to /events/new. See invariant 16.

Top-level pages, each with a drawer entry: Send (/send), Tracker
(/tracker), Vendors (/vendors), Items (/items), Sponsors (/sponsors),
Events (/events). Five of those six are lists; **Sponsors is a CREATE FORM**
and has no list at all — see below. Rundown and SPK have no entry of their own — both are
per-event or per-batch with no top-level list, and are reached from
Tracker. The rundown does light Events in the trigger, since it lives
under /events/{id}; that is the same parent-lighting `/categories` gets.

The rundown is offered from the EVENT page only, not from each batch. It
belongs to the event, so a link on every quote round of that event was the
same destination repeated — three batches, three identical buttons. One
level up, beside "All batches", is where it is reached.

**The tracker is three levels, and the top one is EVENTS.** /tracker lists one
row per event that has been quoted at least once, as COUNTS ONLY: the title,
the date, how many batches and how many sponsors. It never names them — which
categories went out and which sponsors are on the event are the event page's
job. A list is for finding the row; the row's contents are one click in.
/tracker/{event_id} opens that event and lists its batches and its sponsors.
/tracker/batch/{request_id} is the per-vendor page — status, retry, SPK — and
is where the work actually happens.

DELIVERY IS NOT ON THE LIST, deliberately. It was, and the column now carries
sponsors instead. Sent/failed/pending are per BATCH, so an event's summed
tallies answer a question nobody asks — "6 of 11 sent" across three rounds
names no round you can act on, and the Retry that would fix it lives one level
in. The counts are exact where they mean something, on the event page and the
batch page. The tracker list says what an event HAS; the pages inside say how
it WENT.

Batches are named by their CATEGORY, never by their id: a round is recognised
by what it asked for (Tenda, Sound System), and a bare id says nothing to the
person reading it. The id survives only in the URL and in one chip on the batch
page, which is where it is still the key.

/events is untouched by this and stays the place an event is created and
CORRECTED. The split is by verb, not by noun: /events edits the event,
/tracker reads what was sent for it. That is why there is still no event
detail page under /events — the reading surface is the tracker's, and two
pages describing one event is how they drift.

An event with no batch appears NOWHERE on the tracker. The query joins
requests rather than left-joining them, so creating an event on /events does
not put an empty row here; the tracker is send history, and an event nothing
was sent for has no history yet.

The held-reply section stays a section on /tracker and is deliberately NOT
folded into an event. A tier 4 carries no request_id at all, so it belongs to
no batch and therefore to no event — grouping the list by event would give
those rows nowhere to render, which is the exact failure invariant 18 exists
to prevent. It sits beside the table rather than inside it, which is what let
the table change shape without touching it.

**Sponsors has NO LIST PAGE, and /sponsors is the create form.** There was a
list and it is deleted. Do not rebuild it.

The reason is in the schema rather than in taste. sponsors.event_id is NOT
NULL and the table is UNIQUE(event_id, nama_pt), so a sponsor row belongs to
exactly one event BY CONSTRUCTION — there is no sponsor master table and a
company sponsoring two events is two rows, not one row seen twice. That is the
opposite of vendors, which are a master list joined to categories many-to-many
and genuinely span every event. So the page had to group by event to render at
all, and a list that must group by its parent to make sense is that parent's
list wearing a top-level entry.

It lives on the parent now: /tracker/{event_id} renders the event's sponsors
beside its batches, from db.list_sponsors(event_id=...) — the same query the
old page called unfiltered. Reaching a sponsor is Tracker → the event → the
sponsor, and sponsor_detail's back button goes to /tracker/{event_id} rather
than to a list that no longer exists.

**The sponsor RECORD lives under the tracker: /tracker/sponsors/{id}**, with
its edit form, its printed sheet and all four package endpoints beneath it.
Only three paths are left on /sponsors — the create form, `GET /sponsors/new`
as a 307 alias for it, and the create POST.

That split is the one /send and /tracker already have: a batch is created at
/send and read at /tracker/batch/{id}. Sponsors now match — created at
/sponsors, read at /tracker/sponsors/{id}. Create where the nav entry is, read
where the event is.

It also fixes the drawer with no code. The trigger label comes from
`path.startswith(tujuan)` over the nav list, so while the record sat on
/sponsors/{id} it lit **Sponsors** — a page that no longer lists sponsors and
that the record is never reached from. The URL now says where the page
belongs, /tracker/sponsors/1 starts with /tracker, and the highlight follows
without a special case. Compare `/categories`, which needs an explicit line in
base.html precisely because its URL does not say where it lives.

`GET /sponsors/new` is kept for the same reason `GET /tracker/replies` is —
without a handler the path used to fall through to /sponsors/{sponsor_id} and
422 on int conversion. That parameterised route has moved away, so today it
would 404 instead, but the redirect is the better answer to an old bookmark
either way.

Note this is NOT the same argument that deleted /tracker/replies. That page
went because it was empty every time on a healthy mailbox. This one was never
empty; it went because its rows belonged to a page that already existed.

Replies get no entry either, and no LIST PAGE at all. There was a
/tracker/replies once and it is deleted: /tracker already carried the check
button, the last-checked chip and the failure banner, so the page repeated all
three, and on a mailbox where matching works it was empty every single time.
The one thing only it had — the replies the ladder could not place — is now a
section on /tracker rendered only when the list is non-empty, so a healthy run
shows nothing and a failed match is impossible to miss.

Do not rebuild it. The question these pages answer — who has not replied yet —
is a fact about a batch, so it belongs on the batch page; a list of its own is
the second inbox this feature exists not to be. What survives under
/tracker/replies/ is the DETAIL page, where a reply is assigned and approved,
plus the check POST and the attachment route. `GET /tracker/replies` is a bare
307 to /tracker, kept only because without a handler the path falls through to
/tracker/{event_id} and 422s on int conversion, which is a worse answer to an
old bookmark than a redirect.

The drawer trigger carries a count of incoming mail not yet dealt with:
unread attached replies plus everything waiting to be assigned. On the TRIGGER,
not only on the panel entry, because the panel is collapsed by default and a
number nobody can see is not a badge.

The badge counts by PLACEMENT, not by tier: a reply carrying both a batch and
a vendor counts until it is read, one missing either counts until it is
placed. Two kinds are shown in the list and deliberately left out of the
count, on one rule — a row no click on that page can finish must not sit in
the badge forever, because a number that never goes down stops being read.
Those are a reply matching no batch at all (tier 4: a deleted batch, a mangled
forward, a code from another install), and a tier 3 whose vendor is in no
batch, whose chooser therefore has nothing to offer. The honest remedy for the
second is to write that vendor into a batch, which is not something that
screen can do. The count comes from `perlu_perhatian()`, a Jinja global wired in
main.py: a callable, because base.html renders on every page and a value read
at startup would be stale on the second load.

**routes/replies.py must be included BEFORE routes/tracker.py.** Tracker owns
/tracker/{event_id}, which matches any single segment, so "replies" would be
captured as an event_id and 422 on int conversion — a path parameter that
fails validation does not fall through to the next route.

The batch pages carry a literal `batch` segment for the same class of reason,
though not the same mechanism: /tracker/batch/{request_id} has three segments
and /tracker/{event_id} has two, so those two cannot collide and their include
order is free. What the segment buys is that the meaning of /tracker/{id} was
ALLOWED to change. Event ids and request ids are both ints in overlapping
ranges, so leaving the batch page on /tracker/{id} would have made every old
bookmark render a different record with no error to say so. A 404 is a
truthful answer to a stale link; a wrong page is not.

## Schema

categories(id PK, nama UNIQUE COLLATE NOCASE)

vendors(id PK, nama_pt, pic_nama, email, no_hp, area, catatan,
        aktif DEFAULT 1 CHECK(aktif IN (0,1)), created_at)

vendor_categories(vendor_id FK, category_id FK,
                  PRIMARY KEY(vendor_id, category_id))

items(id PK, nama TEXT NOT NULL COLLATE NOCASE UNIQUE, satuan DEFAULT '',
      cost INTEGER NOT NULL CHECK(cost >= 0),
      value INTEGER NOT NULL CHECK(value >= 0),
      catatan DEFAULT '', aktif DEFAULT 1 CHECK(aktif IN (0,1)))

events(id PK, judul_acara NOT NULL, tanggal_acara, lokasi, created_at,
       zona TEXT NOT NULL DEFAULT 'jabodetabek'
            CHECK (zona IN ('jabodetabek','luar_jabodetabek','luar_jawa')))

requests(id PK, event_id FK ON DELETE CASCADE, category_id FK,
         kebutuhan, deadline, pengirim_nama,
         subject_template NOT NULL, body_template NOT NULL, created_at,
         kode TEXT — UNIQUE via idx_requests_kode, nullable)

sponsors(id PK, event_id FK ON DELETE CASCADE,
         nama_pt TEXT NOT NULL COLLATE NOCASE,
         kontribusi INTEGER NOT NULL CHECK(kontribusi > 0),
         persen_budget INTEGER NOT NULL DEFAULT 12
                       CHECK(persen_budget BETWEEN 1 AND 100),
         catatan DEFAULT '', created_at, UNIQUE(event_id, nama_pt))

sponsor_item(id PK, sponsor_id FK ON DELETE CASCADE, item_id FK,
             qty INTEGER NOT NULL CHECK(qty > 0),
             cost INTEGER NOT NULL CHECK(cost >= 0),
             value INTEGER NOT NULL CHECK(value >= 0),
             created_at, zona_pct INTEGER NOT NULL DEFAULT 0,
             UNIQUE(sponsor_id, item_id))

rundown(id PK, event_id FK UNIQUE ON DELETE CASCADE, jam_mulai NOT NULL,
        batas_venue, created_at)

rundown_item(id PK, rundown_id FK ON DELETE CASCADE, urutan NOT NULL,
             kegiatan NOT NULL, durasi_menit CHECK(durasi_menit > 0),
             pic, catatan, UNIQUE(rundown_id, urutan))

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

inbox(id PK, message_id TEXT NOT NULL UNIQUE, from_email NOT NULL, from_nama,
      subject NOT NULL, received_at NOT NULL, body NOT NULL,
      tier INTEGER NOT NULL CHECK(tier IN (1,2,3,4)),
      request_id FK ON DELETE CASCADE, outbox_id FK ON DELETE CASCADE,
      vendor_id FK, read_at, created_at,
      auto_reply INTEGER NOT NULL DEFAULT 0 CHECK(auto_reply IN (0,1)),
      approved_at TEXT — the SPK gate; see invariant 14)

inbox_attachment(id PK, inbox_id FK ON DELETE CASCADE, filename NOT NULL,
                 content_type NOT NULL, size_bytes CHECK(size_bytes >= 0),
                 stored_name TEXT NOT NULL UNIQUE)

inbox_check(id PK, started_at NOT NULL, ok CHECK(ok IN (0,1)), error_msg,
            examined DEFAULT 0, kept DEFAULT 0)

Indexes: idx_vendor_categories_category, idx_requests_event,
idx_requests_kode (UNIQUE), idx_inbox_request,
idx_inbox_tier, idx_inbox_attachment_inbox,
idx_outbox_request, idx_outbox_status, idx_vendors_aktif, idx_spk_request,
idx_sponsors_event, idx_sponsor_item_sponsor.

There was an idx_inbox_outbox on inbox(outbox_id) and it is gone: the column
is written and never searched, so no query could use it. Two of the twelve
above are not chosen by the planner either — idx_requests_event and
idx_vendors_aktif — but those have real queries behind them (`list_events`
joins on the first, four queries filter `aktif = 1` for the second) and are
only skipped because six requests and twenty-five vendors are faster to scan.
"The planner ignores it at demo size" and "nothing would ever use it" are
different findings; only the second is a reason to delete.

### Domain boundary — categories and items are not linked

`categories` is the **vendor side**: the trades we buy in and ask for
quotes on. A category exists so a vendor can be found and an RFQ batch can
be addressed at one trade.

`items` is the **sponsor side**: the things we own and sell on, each with a
cost we pay and a value a sponsor is charged.

They are different domains and there is no key between them. `items`
carried a `category_id` into `categories` for one revision; it read as if a
thing we sell and a thing we buy were the same kind of object, and it was
removed. Do not add it back, and do not add an items-only category table
either — a catalog this size does not need grouping. Revisit past roughly
thirty rows.

Rationale:
- vendor↔category is many-to-many; tent vendors commonly also supply
  chairs and staging
- outbox.email_tujuan is denormalized so history stays accurate if a
  vendor's email changes
- outbox.message_id is the id WE mint and set, not one the server hands back —
  core/mailer.py calls make_msgid() and puts it on the message. It is minted
  above the DRY_RUN branch and returned by both paths, so a dry-run row gets a
  real unique id too. It used to return the literal "dry-run", which meant
  every dry-run row shared one value and any lookup keyed on the column matched
  all of them at once. Whether the id survives the trip is a separate question;
  see "Reply matching" below
- requests.kode is the batch reference code, printed into the outgoing subject
  as [RFQ-3F2A]. Nullable because NULL is the true history: every batch sent
  before codes existed carried no marker, and backfilling one would claim a
  code no vendor ever saw. UNIQUE across all time, not per open batch — there
  is no closed state here and a vendor may answer a six-month-old thread
- subject_template separate from body: subject must be unique per vendor
  or Gmail collapses the batch into one thread
- spk is stored rather than generated on demand: the SPK must be
  re-downloadable with the same nomor. Storing it makes the number
  stable and gives procurement a record of what was issued.
- inbox.message_id is the incoming message's OWN id, not ours, and it is the
  dedupe key — see Reply matching for why that is load-bearing
- inbox.received_at is the SENDER's clock, from their Date header. It can be
  skewed or even earlier than the RFQ it answers; created_at is ours and is
  the tie-break. A reply that appears to predate its own request is a badly
  set clock, not corruption
- inbox_check is a log rather than a settings row because it answers three
  questions at once with no session to hold them: where to resume, when the
  last check ran, and what went wrong on it. "Never checked" is then the
  natural absence of rows rather than a sentinel value
- inbox.auto_reply marks a generated message. Set from headers only, never
  from the subject. Excluded from the replied count and the badge, included
  everywhere else — see Reply matching for why the gate cannot do this job
- inbox_attachment.stored_name is the name WE chose; filename is the vendor's
  and is display-only. The split is the security guarantee, not a convention
- sponsor_item.cost and .value are snapshots, not a join. See invariant 15.
- sponsor_item.zona_pct is not data the app computes with — it is the
  surcharge rate that produced the snapshot beside it, kept so a line
  priced under an older zone stays visible as history rather than as an
  error. See invariant 17.
- events.zona is what the surcharge is computed from; events.lokasi stays
  free text next to it, because lokasi is printed verbatim into RFQ emails
  and the SPK and must not be reduced to three values.
- requests.event_id is required, and so is db.create_request's event_id
  argument. It was optional, and None meant "mint an event from this
  brief" — reachable only while /send carried the event fields. See
  invariant 16.
- sponsor_item.item_id has no ON DELETE, so SQLite refuses to delete a
  catalog item that any package uses. Items are archive-only, so the app
  never reaches it; it will stop a hand-written DELETE.

A CHECK constraint must admit exactly what the validator admits. harga was
CHECK(harga >= 0) DEFAULT 0 while deps.parse_harga already rejected zero,
so a zero-value SPK was reachable through SQL but not through the form;
harga is now CHECK(harga > 0). items.cost/value, sponsors.kontribusi,
sponsors.persen_budget and sponsor_item.qty were all written to match their
validators from the start, for the same reason.

SQLite cannot alter a CHECK in place, so a live db/rfq.db built before a
constraint changed still carries the old one and picks the new one up on
the next rebuild from schema.sql.

## Reply matching

Half-built on purpose. The OUTGOING half is done; the incoming half is not
started, and there is one unanswered question gating it.

**What exists.** Every batch carries a reference code (requests.kode), and
core/kode.py stamps it onto the rendered subject as `[RFQ-3F2A]`. A subject
survives a vendor pressing Reply, so the code comes back on the answer without
the vendor doing anything. Nothing can be matched retroactively — only mail
sent after this landed carries a marker at all, which is why the outgoing half
had to ship first and alone.

The marker is appended by renderer.render_email, NOT offered as a `{{ kode }}`
placeholder in email_templates/rfq_subject.txt. That template is editable on
the Send page, and a placeholder can be deleted by whoever is editing the copy.
The marker is protocol, not copy, so it is not the copy editor's to remove.

Order inside render_email is load-bearing: render, collapse whitespace, run the
unresolved-placeholder check, THEN append. Appending before the check would
have the function inspecting its own output; appending before the collapse
would let the marker be folded into a line break.

**The Message-ID question — ANSWERED 2026-08-19: Gmail PRESERVES it.**

core/mailer.py mints a Message-ID and stores it on the outbox row. The
strongest way to match a reply is to look for that id in the reply's
In-Reply-To or References — an exact hit lands on an exact outbox row. That
rested on an assumption no code here can check: that the submission server
sends OUR id rather than replacing it. Gmail is widely reported to rewrite
Message-ID on smtp.gmail.com, and the SMTP response cannot settle it because it
carries a queue id, not a Message-ID.

`cek_message_id.py` settled it by sending one real message and reading the
delivered copy back:

    generated : <178715512756.11756.11676591822792965433@DESKTOP-0TU80TQ>
    received  : <178715512756.11756.11676591822792965433@DESKTOP-0TU80TQ>

Identical. Our id survives submission, so outbox.message_id is a usable
matching key and the In-Reply-To tier is worth building.

**Confirmed again on 2026-08-21, this time end to end.** The result above came
from a self-addressed check, which left a fair objection standing: both ends
were the same Gmail account, so it was not a real delivery. That objection is
now settled. A batch went out to four separate addresses, one was replied to,
and the reply came back carrying:

    In-Reply-To : <178724662804.15892.13172911242195124227@DESKTOP-0TU80TQ>
    outbox row  : <178724662804.15892.13172911242195124227@DESKTOP-0TU80TQ>

Our id, sent, delivered, quoted back by the replying client, matched at tier 1.
Three separate observations now agree.

It remains one mail provider's behaviour rather than a guarantee, so anything
built on this tier should still degrade to the subject code rather than depend
on it — `[RFQ-xxxx]` plus the sender needs no Message-ID at all. But the tier
is proven, not assumed.

Re-run `cek_message_id.py` and update the block above if this ever looks wrong.
It sends a real email — and note that .env carries DRY_RUN=false, so nothing
short-circuits that. It is run deliberately, never as part of a build.

**The incoming half.** `replies.py` holds the whole check — fetch, gate,
ladder, writes. No scheduler and no poller; a button starts it, and the handler
calls it through `asyncio.to_thread` because imaplib is synchronous and would
otherwise block the event loop, in-flight send batches included.

*The watermark.* `IMAP SEARCH SINCE` has DATE granularity only — there is no
"since 14:32" — so every run re-examines the whole day of the last successful
one. `inbox.message_id UNIQUE` is what makes that overlap a no-op, which is why
it is the dedupe key rather than a defensive extra. The watermark is
`MAX(started_at) WHERE ok = 1`: a failed run must not advance it, or the day it
failed on is skipped forever and a visible error becomes silent data loss.

*A refused SEARCH is not an empty mailbox.* They were collapsed in the first
draft, and that is precisely the failure this feature exists to prevent — the
run records as a success finding nothing, the watermark advances past unread
mail, and the interface says "no replies" with total confidence. A non-OK
SEARCH raises. A non-OK FETCH does not: the difference is scope. Failing to
search means we learned nothing about the mailbox; failing to fetch means we
lost one message, which is still on the server next time.

*The gate* admits a message only if the sender is a known vendor OR the subject
carries a well-formed `[RFQ-xxxx]` — shape, not resolution, which is what makes
tier 4 reachable at all. Everything else is dropped before it is written.

The gate also prevents a wrong answer the ladder would otherwise give. **A
bounce from mailer-daemon carries References pointing at our own sent
Message-ID** — verified, three of them sit in the live mailbox. Reaching tier 1
it would attach to that vendor's outbox row and display as their reply, the
exact opposite of what it means. It never gets there because mailer-daemon is
not a vendor and "Delivery Status Notification (Failure)" carries no code.

*Auto-replies are the case the gate CANNOT catch.* A bounce never reaches the
ladder because mailer-daemon is not a vendor — but an out-of-office **is** the
vendor: same address, usually with In-Reply-To, so it matches at tier 1 against
the exact outbox row, correctly. It would then count toward "5 of 8 vendors
have replied", and that count is the point of the feature.

So it is flagged rather than blocked. `inbox.auto_reply` is set from headers
and the row is stored and displayed like any other — an admin should see that
the vendor's server answered — but it is left out of the replied count and out
of the nav badge. Same shape as `tier`: record what the thing is, let the
display decide. The badge exclusion has its own reason: an out-of-office needs
no action, and a badge that counts things nobody must act on gets ignored.

Detection is **by header, never by subject**. Sniffing for "Out of Office" or
"Automatic reply" is localised guesswork, and this app writes to Indonesian
vendors whose servers answer in Indonesian. Three mechanisms:
`Auto-Submitted` (RFC 3834) present with any value but `no`, allowing for a
`; type=vacation` parameter · `X-Autoreply` or `X-Autorespond` present ·
`Precedence` of `auto_reply`, `bulk` or `junk`.

Checked against the real mailbox rather than trusted from the spec: of its 9
messages, the three mailer-daemon bounces carry `Auto-Submitted: auto-replied`
and **nothing carries X-Autoreply, X-Autorespond or Precedence at all**. So the
RFC 3834 path is confirmed against live traffic and the other two are
unexercised there — they exist for vendors' own mail servers, which that
mailbox contains no example of. Google's notifications carry none of the three
(they use `Feedback-ID` and a `bounces.google.com` return path) and are gated
out by sender anyway.

*The code match is case-insensitive* even though every code minted is
uppercase. The failure modes are not symmetric: matching loosely costs a stray
tier-4 row someone glances at, while matching strictly drops a real vendor
reply at the gate, silently, because a human retyped the code in lowercase.

*Attachments* live on the filesystem under `attachments/`, never in a column.
The on-disk name is built from the reply id and the file's position in the
message; the vendor's filename is stored for display and for the
Content-Disposition header only. Path traversal is not defended against — the
attacker-controlled string never touches a path, so it is unreachable, the same
shape of guarantee the sponsor print route has about cost.

## Invariants

1. PRAGMA foreign_keys = ON and journal_mode = WAL on EVERY new connection,
    not once at init; init_db.py deletes the -wal/-shm sidecars on rebuild,
    since a stale -wal replays old pages into the fresh db.
2. DRY_RUN defaults True. When true, never open an SMTP connection —
   log to/subject/body only. It is a SEND guard and nothing more: reading the
   mailbox over IMAP sends nothing and changes nothing, so DRY_RUN deliberately
   does not gate it. A demo with the send guard on can still show real replies
   arriving. A Message-ID is still minted under DRY_RUN — an id is not a
   connection, and minting it in both branches is what keeps dry-run rows from
   all sharing one value.
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

   ONE STATED EXCEPTION, and it is bounded to four characters. The subject
   marker is rendered from requests.kode, but the code has to exist before the
   subject can be rendered and the row that owns it is not written until
   dispatch. So /send mints a code at preview and checks it free — and nothing
   owns a code until the INSERT, so another batch can take it in between. When
   that happens db.create_request re-rolls on the UNIQUE index rather than
   failing the dispatch, and the sent subject differs from the previewed one
   inside the marker.

   The body and every other character of the subject cannot diverge: those come
   from the templates, which ride the form verbatim. Rejected fix: a
   reservation table handing out codes at preview — it removes the exception at
   the price of a table whose whole job is owning four characters, plus an
   orphan row for every abandoned preview.
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

    An SPK is issued ONLY to a vendor whose quote a person APPROVED —
    inbox.approved_at, gathered by db.vendors_approved. REPLYING IS NOT
    AGREEING: a vendor who answered and was turned down never opens the gate.

    Approving is its own act with its own button, on the reply detail page and
    nowhere else. That placement does two jobs. The price is in front of you
    when you accept it, and opening that page has already stamped read_at — so
    "cannot be approved unread" is guaranteed by where the button is rather
    than by a check that could be forgotten. The chain is: place the reply if
    the ladder could not (Assign), read it, approve it, then issue.

    Assign and Approve are different questions and must not be conflated.
    Assign answers "which batch and vendor is this?" — a technical repair, only
    ever offered for a reply the ladder failed to place. Approve answers "do we
    accept this offer?" — a business decision, offered on every placed reply.

    An approval is withdrawable until an SPK exists for that pair, and refused
    after: the document has a nomor and is on the books (invariant 12), and
    cancelling a real work order is not something this screen models.

    Two earlier gates are recorded here as dead ends, not as stricter rules:

    - `tier IN (3, 4)` — only a hand-assigned reply. A tier 1 or 2 attaches
      itself, never passes through the chooser, and has no Assign action
      anywhere, so every normally matched vendor was locked out PERMANENTLY
      while the only ones qualifying were those the ladder had FAILED to place.
    - any reply at all — no way to express "this vendor answered and we said
      no", so a rejected price still opened the gate.

    All of these close the original rule that the action was offered on every
    row so a vendor who won the job by phone could still be issued one. That
    escape hatch stays closed: no approval, no SPK, no override in the UI.

    The gate lives in routes/spk.py's muat_spk, which the form, the save and
    the download all pass through, so the three cannot drift; hiding the table
    button is the courtesy and the 403 is the guarantee. `boleh_spk` must be in
    BOTH contexts that render _progress.html — tracker_batch and
    send_progress — or the poll's last swap reopens every button.
15. Money on a sold line never moves. sponsor_item.cost and .value are
    copied from the catalog when the line is created and are never read
    from items again — not to display it, not to edit it, not in any
    operation the line later undergoes. Repricing the catalog must leave
    every package already built exactly as it was.

    The rule is about the two columns, not about any one operation, and
    that is what makes it survive: the test for anything new touching
    sponsor_item is whether cost or value appears in its SET list. They
    must not. Quantity is adjusted in place today and the snapshot is
    carried through untouched; when the mechanism changes again the test
    is unchanged. A reprice reaches a package only by removing the line
    and adding it back — a deliberate act, with a visible before and
    after.

    This is the OPPOSITE of the rundown rule: rundown times are always
    recomputed from jam_mulai, package prices are always frozen. A rundown
    describes what will happen and has to follow the plan; a package
    records what was promised and has to stay put.
17. A price is decided once, at the moment the line is created, and every
    input to that decision is frozen with it. The catalog base is one such
    input; the event's zone surcharge is another. Both are resolved in the
    same transaction that writes the row, and neither is consulted again.

    Store the inputs, not just the result. sponsor_item.zona_pct records the
    rate that produced cost and value — it is summed by nothing and read by
    no total. It exists so that a line priced under one rate stays
    *distinguishable* from one priced under another after the event moves.
    Without it, correct history is indistinguishable from an arithmetic
    error, and the honest answer looks like a bug.

    A rate that no longer matches is REPORTED, never reconciled. The page
    names the lines and says what changed; the fix is to remove the line and
    add it again, which prices it afresh as a deliberate act. Nothing may
    quietly bring an old line onto today's rate — that is invariant 15 with a
    second input, and the test is the same: cost, value and zona_pct must not
    appear in any SET list touching sponsor_item.

    The rate itself lives in exactly one place (config.ZONA). Anything that
    displays a percentage and anything that multiplies by one read from
    there, so a rate cannot be changed for the maths and missed on the form.
18. A reply's tier is HISTORY and is never rewritten. inbox.tier records how
    the message was matched; assigning a held reply by hand fills request_id
    and outbox_id — and vendor_id when the reply had none — and leaves tier
    standing. So "needs assigning" is `request_id IS NULL OR vendor_id IS
    NULL` — SOMETHING IS MISSING, not a list of tiers — and never a status that
    flips. A reply the ladder could not place stays a tier 4 forever even after
    a human puts it on a batch.

    Written as a tier list it was wrong, and silently: a tier 2 whose code
    named a batch but whose sender was not one of its vendors carries a
    request_id and a NULL vendor_id. It matched no page — not the held list,
    not replies_by_vendor, not progress() — while the badge counted it, so the
    badge named a number nothing on any screen could clear. Ask what a row is
    MISSING, and the cases enumerate themselves.

    This is invariant 17's shape with a different input: store what produced
    the outcome, so a hand-assigned reply stays distinguishable from one the
    ladder resolved. Without it, correct history is indistinguishable from a
    mis-match, and the honest answer looks like a bug. The test for anything
    new touching inbox is whether `tier` appears in its SET list. It must not.

    Tier 3 NEVER attaches on its own, and that is the point rather than
    caution: one vendor working two concurrent events cannot be told apart by
    their address, and concurrent events are normal here. Tier 4 does not
    either, for the stronger reason that it has no vendor at all.

    Every incompletely placed reply is held in ONE list, the held section on
    /tracker, because they share one remedy — a person says where it belongs.
    What differs is which half is missing, and therefore which chooser opens:

    - missing a batch (tier 3) — offered that vendor's own batches, since the
      only open question is which of THEIR conversations this answers
    - missing a vendor (tier 2, code resolved, sender not in that batch) —
      offered that ONE batch's vendors. The batch is settled and is not up for
      revision: a posted batch that is not the reply's own is refused
    - missing both (tier 4) — offered every (batch, vendor) pair

    A pair rather than a batch, always, because picking a batch alone leaves
    vendor_id NULL and replies_by_vendor and progress() both filter that out:
    the reply would leave the Replies page and appear on no other. Assignment
    fills vendor_id in exactly these cases and never overwrites one the ladder
    resolved.

    The pair choosers are GROUPED by batch with <optgroup>, not flattened: the
    options are batches × vendors, so a flat list repeats the batch name on
    every row and, for a tier 4, is offered every pair there is. Grouped rather
    than truncated, deliberately — a cap on recent batches would drop
    legitimate targets, since codes are unique across all time precisely
    because a vendor may answer a six-month-old thread. Note that Jinja's
    groupby SORTS by its key and so undoes the query's newest-first order; the
    `| reverse` after it is load-bearing, not decoration.

    The chooser is gated on what is missing, NOT on `request_id is none` — the
    missing-a-vendor case has a request_id and still needs the form.

20. A generated reply is RECORDED and not COUNTED. inbox.auto_reply is set
    from headers, and the row is stored, listed and openable like any other —
    but it is excluded from progress()'s replied count and from
    count_needs_attention(). The gate cannot do this job: an out-of-office
    comes from the vendor's own address with In-Reply-To and is a legitimate
    tier-1 match.

    This is invariant 18's shape again — store what the thing is, let the
    display decide — and the same test applies: anything new that counts
    replies must say `auto_reply = 0`, or a vacation notice silently becomes
    an answer.

19. outbox.status is a DELIVERY outcome and reply state is derived, never
    written onto it. The CHECK admits 'replied' and _progress.html has a label
    for it; both are deliberately unused. Writing it would overwrite 'sent' and
    lose whether the mail actually went, and reply state is per reply rather
    than per vendor — a revised quote has to read as new, which one column
    cannot express.

16. judul_acara, tanggal_acara and lokasi live in events and nowhere else.
    Every other table reaches them by joining on event_id — requests,
    outbox, spk and rundown all carry the id and none of them carries a
    copy. So editing an event on /events is a correction everywhere it is
    displayed, and rewrites no other row. Nothing outside routes/events.py
    writes those three columns, and no form outside /events offers them.

    This is the opposite call from outbox.email_tujuan, which is
    denormalized on purpose, and the two differ by what the value is FOR.
    The event is the thing being described, so a corrected title should
    propagate to every batch that describes it. email_tujuan is a record
    of where a message actually went, so it must not move when the vendor
    row does. Ask which of the two a new column is before copying either.

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

The root font size is deliberately **not** pinned: the current rendering
is approved, and overriding the root would resize every rem value still
in the sheet at once — a full visual re-review for no gain. Those
literals are legacy, not a documented set, so do not treat any list of
them as complete — grep base.html for `rem` and multiply by 20.

Table body text still renders 18px against a 14px form control — the one
remaining rem/px gap, left alone on purpose: closing it means restating
the whole table scale in px, a visual change rather than a cleanup.

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
  `15px 24px 32px`, margin-block `10px 12px` (10px of grey above,
  12px below to the footer). The top 15px is the same 15px the title gives
  its chips, so the space above the heading matches the space below it.
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
| padding-block (inner) | 12px | 12px |
| background | `#fff` | `#fff` |
| border | bottom `1px #e7eaf0` (`--pico-muted-border-color`) | top `1px #eef0f3` |
| text | brand 15.6px/600/uppercase/1.09px tracking, muted | 12px/1.4 muted |

The header's 12px is arithmetic, not taste: the drawer trigger is a real
34px control, and 12 + 34 + 12 + the 1px border is what holds the bar at
59px. It was 14px while the nav was four inline links, whose padding did
not affect the line box.

The footer border is one step lighter than the header's on purpose — the
header stays the heavier of the two. `.kaki` uses `margin-top: auto`
against a flex-column body, so the slack lands on the grey page, not
inside the panel.

### Drawer menu

The four visible nav links are gone. The header carries the brand and then
one collapsed menu, and `.tautan-nav` no longer exists — do not resurrect
it.

Pico v2's native `<details class="dropdown">` supplies the whole
interaction. **No script.** That includes outside-click dismissal: Pico
draws `details.dropdown[open] > summary::before` as a fixed full-viewport
backdrop at `z-index: 1`, so a click anywhere while open lands on the
summary and closes it. The panel's own `z-index: 99` keeps its links
clickable above that backdrop. Escape does **not** close it — native
`<details>` has no Escape handling and Pico adds none.

Trigger is `☰` plus the current page name (`.ikon-menu` 19px, then
`.nama-halaman` 600 in `--teks-gelap`), falling back to `☰ Menu` on any
page outside the list. That name is the whole "where am I" signal now, so
the panel's current entry is marked with `aria-current="page"` and left to
Pico, which fills it from `--pico-dropdown-hover-background-color`. No
class of our own for active state.

    .menu-ringkas    the <details>
    .ikon-menu       the hamburger glyph, aria-hidden
    .nama-halaman    the current page name in the trigger
    summary          34px, 7px 14px, radius 8px, 17px/500, muted,
                     hover fill rgba(128,138,148,.14), open fill .16
    summary + ul      panel: absolute, top 100% + 6px, min-width 184px,
                     6px padding, #fff on 1px #e4e7eb, radius 8px
    li[role=separator]  height 0, margin 6px 4px, border-top 1px #eef0f3

Entries live in one `{% set %}` list in base.html, two groups, and the split
is per-event WORK above, master DATA below.

The first group is the order the work happens in: Events, Send RFQ, Sponsors,
Tracker. The three creates come first — an event exists before anything can be
quoted for it or sold against it — and Tracker is last because it is
DOWNSTREAM OF ALL THREE: /tracker/{event_id} renders that event's batches and
its sponsors on one screen, so it is where everything made above shows up
again. Order the group by what makes a record, then what reads them back.

The second group is Vendors and Items, the two master tables. They are not
steps in doing one event; they are data you maintain between events, which is
what the separator now means. The separator is the gap between the groups, not an entry. The trigger label
and the marked entry both derive from that list, so they cannot disagree.
`/categories` has no entry and lights Vendors, since it is reached from
there and returns there.

**Everything the drawer computes lives inside a `{% with %}` that also
wraps the header markup.** `path`, `kelompok` and `ns` are assignments, and
a top-level `{% set %}` in a parent shadows a context key of the same name
in every child template — silently. That cost one page a wrong count with
no error to show for it. Any new top-level computation in base.html goes
inside a scope.

Overriding Pico here takes more specificity than it looks. Two of its rules
style a dropdown summary as a select-shaped box:

    details.dropdown > summary:not([role])          (0,2,2)
    nav details.dropdown > summary:not([role])      (0,2,3)

between them supplying a 1px `#cfd5e2` border, 5px radius, `#fbfcfd` fill
and a 50px height. Carrying the same `:not([role])` puts our rules at
(0,3,3), which clears both outright rather than leaning on source order.
Pico also adds 7.5px above the first panel row and below the last through
`li:first-of-type` (0,2,4), so those pseudo-classes are named in our rule
too. Pico's stylesheet is cross-origin, so `document.styleSheets[…]
.cssRules` throws and in-page rule enumeration silently shows only our
own — read the CDN file directly when chasing an override.

### Page title block

Two shapes, chosen by whether the page has a context line:

- **With chips** — plain `<hgroup>`: h2 (30px/1.25, `-.02em`)
  → 15px → `.chips` → **24px** to whatever follows. Every list page and
  every record-detail page.
- **Title only** — `<hgroup class="judul-rapat">`: h2 margin-bottom 0,
  hgroup margin-bottom **16px**. Every form page, and the Send flow.

The 16px/24px split is a rule, not drift: it tracks whether the page has
a context line. Chips carry their own visual mass, so the block below
them needs the extra room to sit clear. Pick the shape by whether the
page has chips, and the spacing follows — do not list pages here, read the
template.

The two chip-page numbers were 4px and 20px. 4px let the chips sit right
under the 30px title, so the row of pills read as part of the heading rather
than as a line under it; 15px separates them and 24px below keeps the gap
under the chips larger than the gap above them, which is what makes the block
read as title-then-context instead of one lump. Both come off the spacing
scale. **Only chip pages moved.** `.judul-rapat h2` pins its own
margin-bottom to 0 and `.judul-rapat` its own 16px, and a class outranks the
`main h2` / `main hgroup` element pairs, so every title-only page renders
exactly as before — verified on /send.

One page does not follow it. `spk_form.html` carries `.judul-rapat` in both
states and adds its chips inside that hgroup when editing, so an SPK being
edited shows a context line with 16px under it instead of 24px. Known, not
yet fixed; fixing it is a visual change, so it needs its own pass.

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
- Two-column grid: `.grid-isian` — short field pairs inside a form.
  `1fr 1fr`, column-gap 20px, row-gap 12px, an odd count leaving the last
  cell empty; grep templates/ for current users. Send instead uses Pico's
  own `.grid` for its one paired row (the two date fields, 20px gap).
  Full-width fields (Notes, Requirements, Scope of work) sit outside the
  grid as direct children.
- `.form-sempit` caps a form at 420px — /categories/new only.
- Checkbox rows are not field groups: `.kotak-kategori` is a wrapping
  flex row, 6px/16px gap, 13px labels at weight 400.

Sections (`main section > h3`) group fields on Send and preview and label
the tables on tracker event and reply detail: **18px/600**,
`border-top: 1px #eef0f3`, padding-top 16px, margin-bottom 12px. The rule
is the section divider — no nested panels anywhere in the app.

It was 13px, which put the heading BELOW the size of everything it labelled —
under 14px form controls on Send, under 18px table text on the tracker event
page — so it read as a caption rather than a heading. 18px is one rule for all
eight templates that use it; there is deliberately no second heading class,
because two section styles is the exact drift the audit below exists to
undo.

`main section:first-of-type > h3` drops both the border and the
padding-top: the first section on a page has nothing above it to divide
from, and the rule would otherwise draw a hairline immediately under the
page title. Its heading lands the same 16px below the title that
`.judul-rapat` gives every other title-only page.

### Buttons

Three levels, all 34px tall / 14px / 6px 14px padding / radius 5px when
they sit in an action row:

1. **Primary** — Pico default fill `#0172ad`, white text. The action the
   row exists for, always last in it. One per action row, not one per
   page — a page with two independent forms has two.
2. **Secondary** — `class="secondary outline"`, transparent on `#5d6b89`
   border and text. Navigating away, cancelling, or one choice among
   several — including every in-table action button.
3. **Muted (`.btn-mati`)** — transparent on `--pico-muted-border-color`,
   muted text, turning `#b3261e` on hover/focus only. The destructive
   action wherever it sits, taking the metrics of the row it is in —
   usually a table row, but not always.

Row containers — which pages use which drifts; grep templates/:

- `.baris-aksi` — left-aligned, 8px gap, no top margin of its own. The
  action row belonging to a form. Only here does the submit get a fixed
  110px width (`.form-vendor .baris-aksi button[type=submit]`).
- `.baris-aksi-kanan` — right-aligned, 8px gap, margin-top 20px, primary
  last. The action row belonging to a page.
- `.aksi-halaman` — right-aligned, 8px gap, inside the controls row. Every
  list page whose actions sit above the table. It must be a direct child
  of `main > .grid`:
  `main > .grid :is(select, input, button, [role=button])` pins every
  control in that row to the same 34px/14px as a form control, so a filter
  select, a search box and the page buttons all match the record forms. The
  explicit height is load-bearing: Pico gives input and `[role=button]` a
  height derived from 1rem while select and button stay content-sized, so
  the row stair-steps without it.
- `.kolom-spk` is the one exception to the right-alignment above: the SPK
column carries a value (a nomor, or an em-dash meaning none) as often as it
carries buttons, and its header is left-aligned like every other, so a
right-aligned em-dash under it read as belonging to nothing. It adds
`text-align: left` and nothing else — the buttons already start at the cell's
left edge, because `.aksi-grup` children take `flex: 1 1 0` and fill the cell
rather than sitting at one end of it. Releasing that basis would size Edit and
Download to their own labels and lose the equal-width pair.

`.aksi-grup` — in-table actions, right-aligned, .25rem gap, children
  `flex: 1 1 0; max-width: 6rem` so a pair measures equal down the column.
  A lone button fills to that 6rem cap rather than shrinking to its label —
  that is the established look, and `.btn-spk` lifts the cap when it needs
  the whole cell.

`.btn-mini` (in-table): 14.4px, `.2rem/.25rem` padding, full-width in its
flex slot, ellipsised — 32px tall, not 34px. **32px is for table rows
only.** It never sits beside a form control; anything outside a row is
34px.

The quantity stepper on a sponsor package row is the one thing smaller
than that, and the reason is that three controls share one cell:
`.kendali-qty` is the flex row (right-aligned, 4px gap, no margin),
`.btn-qty` the 24px square − and +, `.kotak-qty` the 40px typed box —
40px holds the 4-digit cap with room to spare. All three are 24px tall.
**In-row sizes are decided by what has to fit in the cell, not by a
scale** — a lone action button is 32px, a cluster is smaller. Anything
outside a row is still 34px.

Both stepper rules are written as `.kendali-qty .btn-qty` and
`.kendali-qty input.kotak-qty`, and both need the extra weight:

- Pico sizes text inputs through three rules shaped like
  `input:not([type=checkbox],[type=radio],[type=range])`. **A `:not()`
  holding a LIST is the specificity of its most specific argument, not
  the sum**, so those are (0,1,1) — and a lone class at (0,1,0) loses to
  them by one element name. Left bare, the qty box rendered 114×62.5 with
  Pico's 15px/20px padding instead of 40×24.
- Pico gives every button `margin-bottom: 20px`, and `align-items:
  center` centres the **margin** box — so the two buttons sat 10px above
  the input they belong beside until the rule reset the margin.

Neither is visible in the markup, and both look like the rule simply not
applying. Measure the rendered box before assuming a value took.

Disabled: `opacity: .45; cursor: not-allowed; filter: grayscale(35%)`.
`.btn-qty` uses it for real: the − is disabled at qty 1, and is never the
control that removes a line.

### Pagination

Every list page is paged — /vendors, /items, /events, /tracker —
through one mechanism, and there is no second one.

`deps.parse_halaman(per, page, total)` takes the two query params and a count
and returns the dict the pager renders from. Both params come off the URL and
are treated as hostile: a `per` outside `PER_PILIHAN` (10, 25, 50) falls back
to 25, and a page below one or past the end is CLAMPED, never 404'd — a
bookmark to page 9 of a list that has shrunk should show the last page, since
a page is a window onto a resource rather than a resource that can be missing.

The order is COUNT, then parse, then fetch: the clamp cannot be applied before
the total is known. Every `list_*` takes `limit`/`offset` defaulting to
None/0, so the callers that must see everything — /send's vendor picker and
its event select — are unaffected by leaving them out.

**A count is a SQL question, never `rows|length`.** Every chip that reports a
total reads a `count_*`; summing the fetched rows was exact only while every
row was fetched, and with a page of 25 out of 120 it reports the page and calls
it the table. /vendors goes further and shares `_saring_vendor` between its
list and its count, so the filter cannot drift between "of 120" and the 120.

`_pagination.html` renders only when `total` exceeds the smallest page size:
below that every control on it is dead, and a pager on a six-row table is
furniture. Links are plain `<a>` — paging is a deliberate click and a full
repaint is honest — and `deps.query_ganti(request, **ubah)` keeps the rest of
the query, so page 2 of a search stays page 2 of THAT search. Changing the
page size drops `page` rather than setting it to 1.

On /vendors the pager rides OUT OF BAND with the table, the same mechanism
`_vendor_stats.html` uses and for the same reason: the swap target is the
`<table>` itself, a pager cannot live inside one, and a pager left behind after
a search would still link to pages of the previous query.

The pager's buttons are 34px, not `.btn-mini` — 32px is for table rows only.
Pico sizes an `<a role=button>` from 1rem (20px at desktop widths) and gives
every button a 20px bottom margin; both are reset explicitly, or the row
renders half again too tall and off-centre.

### Tables

One look everywhere via `.tabel`; `table-layout: fixed` with a per-table
`<colgroup>` in percentages is how every column width is set — no
`min-width`, no `<th>` sizing. The percentages must total 100, and they are
sized to the widest thing the column actually holds: a column of controls
is measured against the controls, a column of text against the longest
value it renders. grep templates/ for `<colgroup` to read the current set —
this file does not list them, because a list of nine tables is wrong the
first time a column is added to any one of them.

A `#` header is not used anywhere. Three tables number their rows and all say
`No.` — the rundown's `urutan`, the tracker event page's `batch_ke` (round 1,
round 2), and its sponsor rows by `loop.index`. The tracker LIST had one too and
it was deleted rather than relabelled: that column held `events.id`, a
database key that names nothing a person here works with, appears in no URL
anyone types, and counted DOWN the page because the list is newest-first —
which reads as a broken sort. Before labelling a number column, check whether
it is a POSITION or a KEY; only the first is a `No.`, and a key on a list page
usually should not be shown at all.

Cells `12px 12px`, `vertical-align: middle`,
`overflow-wrap: break-word`. First and last columns zero their outer
padding so the table's edges line up with the heading above and the
button beside it. Header row: 14.4px uppercase, `.04em` tracking, muted,
nowrap, `border-bottom: 3px` (Pico's thead default) against 1px on body
rows, both `#e7eaf0`.

The vertical padding was `.35rem` (7px) and is now 12px. 7px against 18px body
text is 39% of the text height, which reads as cramped — a row of one-line
cells looked like a rule with words on it rather than a row. 12px is about
two-thirds of the text height, which is the ordinary proportion. It costs
roughly 5px per row, so a 25-row page gets ~125px taller; that was weighed and
accepted, because the pages that are long are long either way and the ones
that are short are the ones that looked thin.

Secondary text: `.redup` (muted, .85em) for PIC, email, timestamps.
`.sel-teks` clips single-token values to one line with the full value on
`title`. Numbers have THREE alignment classes and no fourth: `.angka`
right, `.angka-kiri` left, `.nomor` centred. All three carry tabular numerals;
they differ only in `text-align`, so the choice is about how the column is
read, never about the digits.

`.nomor` is the CENTRED number column: tabular numerals, applied to the
`<th>` and the `<td>` together so the header sits over its values. It is
deliberately not `.angka`: a short number shoved to one side of a narrow
column reads as if it belongs to the neighbouring cell. Four columns use it —
the rundown's `urutan`, the tracker event page's `batch_ke`, that page's
sponsor rows (numbered by `loop.index`, since sponsors have no position of
their own and the query orders them alphabetically inside the event), and the
sponsor package's Qty header.

`.angka-kiri` is for tables that read OUTWARD FROM A NAME rather than
lining their digits up on the column edge — the sponsor package and the event
page's sponsor list. It started as a rule scoped to `.tabel-paket` and became
a class the moment a second table wanted it: a per-table override is one
override, but two of them is a pattern, and the third would have been a third
rule. Reach for the class.

Qty on the package table is an exception twice over: a stepper is a control
rather than a value, so `.tabel-paket .kendali-qty` centres it — the one
remaining table-scoped rule, because it aligns a flex row rather than text —
and the header carries `.nomor` so the two agree. The printed sponsor sheet
builds its own table and is untouched by any of this.

Badges — 15px, radius 999px, `.15rem .55rem`, white text, nowrap,
ellipsised, one class per status keyed off the raw DB value:

| class | colour | shown as |
|---|---|---|
| `.badge-aktif` / `.badge-sent` | `#2e7d32` | Active / Sent |
| `.badge-nonaktif` / `.badge-draft` | `#78848f` | Inactive / N pending / Pending |
| `.badge-gagal` / `.badge-failed` | `#b3261e` | N failed / Failed |
| `.badge-replied` | `#1565c0` | Replied |

Inactive rows get `opacity: .45` on the whole row.

A `<tfoot>` is a totals row, not a data row: `border-top: 1px #e7eaf0`,
`border-bottom: none`, weight 600, `padding-top: .5rem`. Used by the
sponsor package table and the printed sheet. The totals are recomputed
server-side on every change — nothing sums in the browser.

Metric cards (tracker detail only): 3-up grid, 20px gap, 30px below,
dropping to 2-up under 720px. Card is `1px --pico-muted-border-color`,
radius **8px** — the same as `.konteks` and `.pratinjau`, all three
being the same idea — `.9rem 1rem` padding, no fill. Number 38px/600,
label 15px uppercase muted. Sent green `#2e7d32`, Failed red `#b3261e`,
Total inherits. A bare Pico `<progress>` sits under the status line below
them — the one unstyled Pico element in the app.

`.ringkas-paket` (sponsor detail only) is the other read-only summary and
deliberately not a metric card: four rupiah amounts and a multiple on one
row, so 38px numbers would wrap every one. Five-column grid inside one box
that shares the `.konteks` surface — `#fbfcfd` on `1px #e4e7eb`, radius
8px, `12px 14px` padding, `10px 20px` gap — with `dt` 11px uppercase muted
over `dd` 15px/500 in `--teks-gelap`. Drops to 3-up under 900px and 2-up
under 620px. It is its own rule rather than a second class on `.konteks`,
whose 3rd and 5th cells are pinned full-width.

`.nilai-minus` is the app's failure red `#b3261e` on a number that has gone
negative — Remaining on a sponsor is the only one today. It marks the
value; the row is not otherwise styled, and nothing is disabled.

### Warnings and empty states

- **Validation** — bare Pico `<article>`: white, radius 5px, 20px
  padding, 20px below, Pico's own large shadow. Bold lead sentence, then
  one plain line. Same shape on every form page.
- **Serious, as opposed to routine** — `article.peringatan` adds
  `border-left: 3px #b3261e`. The uses differ in whether they block:
  - SPK form — the vendor or request is missing required data, and the
    submit is disabled alongside it.
  - Rundown — the schedule runs past the venue limit. A real schedule to be
    flagged, not an error, so nothing is disabled.
  - Sponsor detail — the package is over budget. Staff may knowingly
    overspend, so it reports the overspend and offers the two ways out;
    nothing is disabled.

  The red rule marks weight, not a blocked state — read the surrounding
  controls for that.
- **Empty table** — a single `<td class="kosong" colspan=…>`: muted,
  italic, `padding-block: 30px`. Every empty state is written as
  a sentence plus the next action ("Start with 'Add Vendor' — …"), and
  /vendors varies it three ways (search / filter / genuinely empty).
- **Inline reassurance** — `p.redup` under the tracker detail table when
  a batch finished clean.
- Read-only value blocks share one surface: `#fbfcfd` on `1px #e4e7eb`,
  radius 8px, `12px 14px` padding — `.konteks` (2-col dl for values shown
  rather than asked for; 11px dt over 14px dd, 3rd/5th cells full-width,
  1 col under 720px; grep templates/) and `.pratinjau` (preview).

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

The pages meant to leave the screen take opposite approaches, for a reason.

**The rundown prints from the screen DOM.** There is no print route, so
there is no second copy to drift. One element carries both audiences:
`.layar` shows on screen, `.cetak` in print, and `@media print` swaps the
pair.

**The sponsor sheet has its own route**, `/tracker/sponsors/{id}/print` →
`sponsor_print.html`, because the two versions are not the same document.
The screen page is a staff worksheet showing cost; the sheet is what a
sponsor reads. So the sheet carries no `.layar`/`.cetak` pairs — it is
Indonesian throughout — and its route hands the template a context with no
cost in it at all. **That is the guarantee: the forbidden numbers cannot
print because they are never passed.** Do not "simplify" it into rendering
the detail row objects. Its two buttons stay English, since staff open the
URL and print hides them anyway, and the path says `print` rather than `cetak`
for the same reason every route and template filename is English: a URL is not
read by the sponsor. The `.cetak` / `.layar` CLASS names are untouched — those
follow the Indonesian class convention and are not renamed piecemeal.

The shared `@media print` block at the end of `base.html` hides everything
that is not the document: nav, footer, editing forms (picked by
`section:has(.form-rapat)`, not by position), every action row, and the
rundown table's two action columns. px throughout, as everywhere else — in
print 96px is one inch, and `@page` margin is 48px. Measured: the sponsor
sheet is 761px at ten lines against 1027px of printable A4 height, and
about 42px per row, so roughly fifteen lines still fit one page. Nothing
forces a longer one.

Colour is the first thing a mono printer discards, so nothing may depend
on it: every muted value returns to black, and the over-limit warning
prints as a plain sentence with a bold lead rather than a red-ruled card.

Language follows the audience, not the file. The printed rundown is carried
by crew and vendors on site, so the **whole sheet** is Indonesian under the
vendor-facing rule, alongside the SPK and the sponsor sheet — while the
screen stays staff-facing English. On the rundown the pair covers the table
headers, the section title (Susunan Acara), every chip label, the duration
cells, the totals line and the over-limit warning. Values follow too where
the language changes them: the event date goes through `| tanggal` and
every duration through `| durasi`.

`.alamat-lembar` and `.kalimat-lembar` are the sponsor sheet's body copy —
the "Kepada:" line and the sentence introducing the table — at 14px/1.5,
12px below, 16px under the sentence. Both are restated black inside the
print block so a later colour on either cannot quietly print grey, and
`.tabel tfoot td` takes a black top border there for the same reason: that
rule is the only thing separating a total from the rows it adds up.

What carries no `.layar`/`.cetak` pair, because it reads the same either
way: `No.` (the abbreviation is the same in both languages), `PIC`, clock
times, the venue name, and the item text itself,
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

`2 · 4 · 6 · 8 · 10 · 12 · 14 · 15 · 16 · 20 · 24 · 30 · 32`

15 is the one value here that is not a multiple of 2 from its neighbours.
It is the title's own spacing and nothing else — panel top→h2 and h2→chips,
deliberately the same number so the heading sits evenly between the panel
edge above it and its context line below. Chosen by eye against the 30px
title rather than off the scale; do not reach for it for anything new.

The recurring ones and what they mean: **4px** label→control · **8px**
every action-row and chip gap, vendor-row padding · **15px** panel top→h2 and h2→chips ·
**12px** field→field on record forms, section h3→content, footer
padding, panel→footer, table cell padding · **16px** field→field on Send,
section rule→heading, title-only block→content, controls row→table ·
**20px** grid column gap, action row top margin, metric gap,
`<article>` padding · **24px** the horizontal gutter everywhere, and
title+chips block→content · **30px** metric cards→status line,
empty-state padding-block · **32px** panel bottom padding.

Radii in play, after the audit fixes:

- **8px** — every form control (input, textarea, select), every bordered
  read-only box (`.konteks`, `.pratinjau`, `.metrik-kartu`,
  `.ringkas-paket`), and the drawer trigger and its panel. This is the
  default for new work.
- **6px** — rows inside the drawer panel, and only those.
- **5px** — buttons, `<article>`, checkboxes and radios, all inheriting
  Pico's `--pico-border-radius` at this root size.
- **10px** — the panel, and only the panel.
- **999px** — chips and badges.

### Resolved by the audit

The first audit found every place two pages disagreed on the same element.
All of them are fixed; the rules above are what replaced them, and they are
recorded here so the same ground is not re-litigated.

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
auth/login · extracting quoted prices from reply attachments · rendering HTML
mail · quotations table · price
comparison · file attachments · per-category templates · calendar
integration · Docker · CI · comprehensive tests

Catalog and sponsors, declared out of scope when those modules were
specified and still unbuilt: item grouping of any kind · price history ·
Excel import · bulk edit · slot capacity · cost sharing between sponsors ·
event-level rollup across sponsors · sponsor tiers · payment tracking ·
any PDF library — the browser's print-to-PDF is the whole mechanism.

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