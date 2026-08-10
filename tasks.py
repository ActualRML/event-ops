"""Phase B of the send: the background batch.

Imports no router — the routers import this."""

import asyncio

import config
import db
import mailer
import renderer


def brief_dari_request(row) -> dict:
    return {
        "judul_acara": row["judul_acara"], "tanggal_acara": row["tanggal_acara"],
        "lokasi": row["lokasi"], "kebutuhan": row["kebutuhan"],
        "deadline": row["deadline"], "pengirim_nama": row["pengirim_nama"],
    }


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
                {"nama_pt": row["nama_pt"], "pic_nama": row["pic_nama"],
                 "kategori": row["kategori"]},
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
