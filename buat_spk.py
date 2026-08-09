"""CLI: write one SPK to a .docx in the current directory.

    python buat_spk.py <request_id> <vendor_id>
"""

import re
import sys
from pathlib import Path

import db
import dokumen


def nama_file(nomor: str, nama_pt: str) -> str:
    """Filename from the nomor and the vendor. The slashes in a nomor are path
    separators, and Windows refuses the rest of the set outright."""
    aman = re.sub(r'[\\/:*?"<>|]+', "-", f"SPK {nomor} {nama_pt}")
    return f"{re.sub(r'\s+', ' ', aman).strip()}.docx"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not all(a.isdigit() for a in argv):
        print("usage: python buat_spk.py <request_id> <vendor_id>", file=sys.stderr)
        return 2

    request_id, vendor_id = int(argv[0]), int(argv[1])

    request = db.request_detail(request_id)
    if request is None:
        print(f"request {request_id} not found", file=sys.stderr)
        return 1

    vendor = db.get_vendor(vendor_id)
    if vendor is None:
        print(f"vendor {vendor_id} not found", file=sys.stderr)
        return 1

    spk = db.get_spk(request_id, vendor_id)
    if spk is None:
        # Nothing issues an SPK yet — that is the next phase — so the CLI says
        # exactly how to create one rather than leaving the tester guessing.
        print(f"no SPK for request {request_id} / vendor {vendor_id}. Create one:",
              file=sys.stderr)
        print(
            f'  python -c "import db; db.create_spk({request_id}, {vendor_id}, '
            f"15000000, 'Sewa tenda roder 10x20 m', '50% DP, 50% H+7')\"",
            file=sys.stderr,
        )
        return 1

    aliran = dokumen.buat_spk_docx(spk, vendor, request)

    tujuan = Path.cwd() / nama_file(spk["nomor"], vendor["nama_pt"])
    tujuan.write_bytes(aliran.getvalue())
    print(tujuan.name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
