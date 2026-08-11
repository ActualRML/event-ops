"""Vendor RFQ Blast — app entrypoint.

Wiring only: the app object, the Jinja filters, the static mount and the
router includes. Every handler lives under routes/."""

from datetime import date

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core import renderer, tampilan
from deps import templates
from routes import rundown, send, spk, tracker, vendors

app = FastAPI(title="Vendor RFQ Blast")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Presentation only, all from tampilan — renderer.format_tanggal stays
# Indonesian and is reserved for the email body.
templates.env.filters["date"] = tampilan.format_date
# created_at carries a clock time, which the date-only filter cannot parse.
templates.env.filters["datetime"] = tampilan.format_datetime
# Raw SMTP exceptions are unreadable for the procurement staff who use this.
templates.env.filters["error_message"] = tampilan.pesan_error
# Rundown durations and totals, stored as plain minutes.
templates.env.filters["duration"] = tampilan.format_durasi
# The Indonesian pair, for the printed rundown only — it is carried on site by
# crew and vendors, so it follows the same rule as the email body. Indonesian
# names on purpose: in a template, `| tanggal` next to `| date` says which
# audience the value is for without looking anything up.
templates.env.filters["tanggal"] = renderer.format_tanggal
templates.env.filters["durasi"] = renderer.format_durasi
# Footer year. Read at startup — a demo restarts far more often than a year turns.
templates.env.globals["tahun"] = date.today().year

# Include order reproduces the original registration order. No prefixes: the
# routers carry their own full paths, so every URL resolves as it did before.
app.include_router(vendors.router)
app.include_router(send.router)
app.include_router(tracker.router)
app.include_router(spk.router)
app.include_router(rundown.router)
