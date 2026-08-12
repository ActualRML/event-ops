"""Phase B of the send: the background batch.

Imports no router — the routers import this."""

import asyncio

import config
import db
from core import mailer
from core import renderer


def brief_dari_request(row) -> dict:
    """Kept as the name the send path already calls. The shape itself lives in
    db.brief_dari_row — event fields and batch fields are merged there, once,
    so nothing here has to know that judul_acara moved tables."""
    return db.brief_dari_row(row)


# Keeps background tasks from being garbage collected mid-batch.
SEND_TASKS: set[asyncio.Task] = set()


async def dispatch_batch(request_id: int) -> None:
    """Phase B. Runs outside the request handler, commits after every email.
    One bad row is recorded and skipped; the batch always continues."""
    permintaan = db.request_detail(request_id)
    if permintaan is None:
        return
    brief = brief_dari_request(permintaan)

    baris = db.list_draft_rows(request_id)
    for i, row in enumerate(baris):
        try:
            subject, body = renderer.render_email(
                permintaan["subject_template"],
                permintaan["body_template"],
                brief,
                # The batch's category, not the vendor's own list.
                db.konteks_vendor(row, permintaan["kategori"]),
            )
            ok, hasil = await mailer.kirim_email(row["email_tujuan"], subject, body)
            if ok:
                db.mark_sent(row["id"], hasil)
            else:
                db.mark_failed(row["id"], hasil)
        except Exception as e:
            db.mark_failed(row["id"], f"{type(e).__name__}: {e}")

        if i < len(baris) - 1:
            await asyncio.sleep(config.SEND_DELAY_SECONDS)


def schedule_batch(request_id: int) -> None:
    tugas = asyncio.create_task(dispatch_batch(request_id))
    SEND_TASKS.add(tugas)
    tugas.add_done_callback(SEND_TASKS.discard)
