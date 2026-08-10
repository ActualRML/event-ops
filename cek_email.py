"""CLI smoke test: python cek_email.py <email>"""

import asyncio
import sys

from core.mailer import kirim_email

SUBJECT = "Test RFQ - Vendor RFQ Blast"
BODY = """Halo,

Ini adalah email percobaan dari tool Vendor RFQ Blast.
Abaikan pesan ini.

Terima kasih.
"""


async def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python cek_email.py <email>")
        return 1

    ok, detail = await kirim_email(sys.argv[1], SUBJECT, BODY)
    print(f"Result: ok={ok} detail={detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
