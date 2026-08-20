"""Email dispatch."""

from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import aiosmtplib

import config


async def kirim_email(to: str, subject: str, body: str) -> tuple[bool, str]:
    """Send one email. Returns (ok, detail) where detail is a message id or error.

    The Message-ID is minted HERE, above the DRY_RUN branch, and returned by
    both paths. It used to be generated only on the real send, with dry runs
    returning the literal string "dry-run" — which meant every dry-run row in
    outbox shared one message_id, and any lookup keyed on that column matched
    all of them at once. Minting it either way costs nothing, keeps the two
    branches the same shape, and leaves reply-matching with a key that is
    actually unique per row.

    Invariant 2 is untouched: no connection is opened under DRY_RUN. An id is
    not a connection.
    """
    message_id = make_msgid()

    if config.DRY_RUN:
        print("--- DRY RUN ---")
        print(f"To      : {to}")
        print(f"Subject : {subject}")
        print(f"Msg-ID  : {message_id}")
        print("Body    :")
        print(body)
        print("--- END ---")
        return True, message_id

    try:
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
