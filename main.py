"""Event Ops — app entrypoint.

Wiring only: the app object, the Jinja filters, the static mount and the
router includes. Every handler lives under routes/."""

from datetime import date

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import db
from core import dokumen, renderer, tampilan
from deps import query_ganti, templates
from routes import (events, items, replies, rundown, send, spk, sponsors,
                    tracker, vendors)

app = FastAPI(title="Event Ops")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Presentation only, all from tampilan — renderer.format_tanggal stays
# Indonesian and is reserved for the email body.
templates.env.filters["date"] = tampilan.format_date
# created_at carries a clock time, which the date-only filter cannot parse.
templates.env.filters["datetime"] = tampilan.format_datetime
# Raw SMTP exceptions are unreadable for the procurement staff who use this.
templates.env.filters["error_message"] = tampilan.pesan_error
# The same for raw imaplib exceptions on a failed reply check.
templates.env.filters["imap_error"] = tampilan.pesan_imap
# Rundown durations and totals, stored as plain minutes.
templates.env.filters["duration"] = tampilan.format_durasi
# The Indonesian pair, for the printed rundown only — it is carried on site by
# crew and vendors, so it follows the same rule as the email body. Indonesian
# names on purpose: in a template, `| tanggal` next to `| date` says which
# audience the value is for without looking anything up.
templates.env.filters["tanggal"] = renderer.format_tanggal
templates.env.filters["durasi"] = renderer.format_durasi
# Money, dot-grouped: Rp 3.000.000. The odd one out in the split above — the
# thousands convention is a locale, not a language, so the catalog table and
# the SPK print an amount identically and share dokumen's one formatter.
templates.env.filters["rupiah"] = dokumen.format_rupiah
# The product name, in ONE place. It is in the header, the footer and the
# suffix of every page title, and before this it was typed out in all twenty-two
# of them — so renaming the app meant editing twenty-two files and missing one.
# A global rather than a per-handler context key, for the same reason the badge
# is one: base.html and every title block need it, and no handler should have to
# remember to pass it.
# Builds a page link that keeps the rest of the query. A global, because every
# list page's pager needs it and none of them should have to pass it; it takes
# `request`, which templates already have.
templates.env.globals["query_ganti"] = query_ganti
templates.env.globals["merek"] = "Event Ops"
# Footer year. Read at startup — a demo restarts far more often than a year turns.
templates.env.globals["tahun"] = date.today().year
# The nav badge, as a CALLABLE rather than a value: base.html renders on every
# page, so the count has to be read per request, not once at startup. Wired
# here rather than added to twenty handler contexts, which would drift the
# first time someone adds a page and forgets it.
#
# This is why main.py imports db. It adds no edge that is not already there —
# main imports every router and every router imports db — and nothing imports
# main, so no cycle is reachable.
templates.env.globals["perlu_perhatian"] = db.count_needs_attention

# Include order reproduces the original registration order. No prefixes: the
# routers carry their own full paths, so every URL resolves as it did before.
app.include_router(vendors.router)
app.include_router(items.router)
app.include_router(sponsors.router)
# /events and its two subpaths. rundown keeps /events/{id}/rundown — the paths
# do not overlap, so include order between the two does not matter.
app.include_router(events.router)
app.include_router(send.router)
# BEFORE tracker, and this is load-bearing: tracker owns /tracker/{request_id},
# which matches any single segment, so "replies" would be captured as a
# request_id and 422 on int conversion. A path parameter that fails validation
# does not fall through to the next route.
app.include_router(replies.router)
app.include_router(tracker.router)
app.include_router(spk.router)
app.include_router(rundown.router)
