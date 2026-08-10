"""Email dispatch."""

from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import aiosmtplib

import config


async def kirim_email(to: str, subject: str, body: str) -> tuple[bool, str]:
    """Send one email. Returns (ok, detail) where detail is a message id or error."""
    if config.DRY_RUN:
        print("--- DRY RUN ---")
        print(f"To      : {to}")
        print(f"Subject : {subject}")
        print("Body    :")
        print(body)
        print("--- END ---")
        return True, "dry-run"

    try:
        message_id = make_msgid()

        msg = EmailMessage()
        msg["From"] = formataddr((config.SMTP_FROM_NAME, config.SMTP_USER))
        msg["To"] = to
        msg["Subject"] = subject
        msg["Message-ID"] = message_id
        msg.set_content(body)

        await aiosmtplib.send(
            msg,
            hostname=config.SMTP_HOST,
            port=config.SMTP_PORT,
            start_tls=True,
            username=config.SMTP_USER,
            password=config.SMTP_PASS,
        )
        return True, message_id
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
