# Vendor RFQ Blast

Internal tool untuk tim procurement event organizer: kirim satu permintaan
penawaran (RFQ) ke banyak vendor sekaligus, lalu pantau hasilnya per vendor.

## Masalah

Untuk satu acara, staf procurement mengirim RFQ ke vendor satu per satu lewat
email. Untuk 25 vendor tenda, sound system, lighting, dan katering, itu berarti
25 kali menyalin brief yang sama, mengganti nama PT dan nama PIC, lalu menekan
kirim. Prosesnya memakan waktu, gampang salah tempel, dan setelah terkirim tidak
ada catatan siapa saja yang sudah dihubungi — kalau ada yang terlewat, baru
ketahuan saat vendor tidak membalas.

## Solusi

Satu brief acara diisi sekali, vendor dipilih lewat checkbox (boleh lintas
kategori — vendor tenda biasanya juga menyediakan kursi dan panggung), lalu
sistem merender satu email personal per vendor dan mengirimnya berurutan.

Alur: **brief → pilih kategori + centang vendor → preview → kirim → tracker**

Tiga halaman:

- **Vendor** — CRUD data vendor, kategori, dan status aktif/nonaktif.
- **Kirim** — brief acara, pemilihan vendor, preview email, lalu kirim.
- **Tracker** — riwayat pengiriman dan status per vendor: terkirim, gagal,
  menunggu, beserta pesan error kalau ada.

Beberapa keputusan yang menentukan bentuk tool ini:

- **Preview wajib.** Tombol kirim tidak pernah mengirim langsung; email contoh
  selalu ditampilkan lebih dulu, dan template subject/body masih bisa diedit di
  layar itu.
- **Kirim dua fase.** Semua baris outbox disimpan sebagai `draft` dalam satu
  transaksi cepat, pengiriman jalan di background dan commit per email. Satu
  email gagal dicatat sebagai `failed` lalu batch lanjut — tidak pernah
  menghentikan sisanya.
- **Progress dibaca dari database**, bukan dari state di memori, jadi refresh
  atau restart tidak membuat angkanya bohong.
- **Subject unik per vendor**, kalau tidak Gmail menggabungkan satu batch
  menjadi satu thread.
- **Dobel kirim dijaga tiga lapis**: tombol yang mengunci diri, pengecekan di
  server, dan `UNIQUE(request_id, vendor_id)` di database.
- **Retry hanya untuk yang gagal.** Baris berstatus `sent` tidak pernah kembali
  jadi `draft`.

## Stack

- Python 3.12, FastAPI, Jinja2, HTMX
- SQLite, raw SQL lewat modul `sqlite3` — tanpa ORM, semua query di `db.py`
- aiosmtplib, Gmail SMTP + app password
- Pico.css v2 dan font Inter via CDN — tanpa build step
- Konfigurasi lewat `.env`

## Cara menjalankan

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

copy .env.example .env          # macOS/Linux: cp .env.example .env
python init_db.py               # buat skema + seed (6 kategori, 25 vendor)

uvicorn main:app --reload
```

Buka http://127.0.0.1:8000 — halaman akan diarahkan ke `/vendors`.

### Konfigurasi `.env`

| Variabel | Default | Keterangan |
| --- | --- | --- |
| `SMTP_HOST` | `smtp.gmail.com` | Server SMTP |
| `SMTP_PORT` | `587` | Port STARTTLS |
| `SMTP_USER` | — | Alamat Gmail pengirim |
| `SMTP_PASS` | — | **App password**, bukan password akun |
| `SMTP_FROM_NAME` | — | Nama tampil pengirim |
| `DRY_RUN` | `true` | `true` = tidak ada koneksi SMTP sama sekali, isi email hanya dicetak ke log |
| `SEND_DELAY_SECONDS` | `2` | Jeda antar email |
| `DB_PATH` | `db/rfq.db` | Lokasi file SQLite |

`DRY_RUN=true` adalah default yang disengaja: demo bisa dijalankan penuh sampai
tracker tanpa satu pun email benar-benar terkirim. Set ke `false` hanya kalau
memang mau mengirim sungguhan.

Cek kredensial SMTP tanpa menjalankan aplikasi:

```bash
python test_email.py            # kirim satu email percobaan
python config.py                # tampilkan konfigurasi yang terbaca
python init_db.py               # reset database ke kondisi awal
```

## Batas scope

Ini MVP demo, bukan aplikasi produksi. Yang berikut **sengaja tidak dibangun**,
bukan karena terlewat:

| Tidak dibangun | Alasan |
| --- | --- |
| Login / autentikasi | Tool internal, dipakai di jaringan kantor oleh satu tim kecil. Menambah login berarti menambah user, session, dan reset password — semuanya di luar masalah yang mau diselesaikan. |
| Parsing balasan otomatis | Butuh IMAP polling dan pencocokan thread. `outbox.message_id` sudah disimpan sebagai fondasi, dan status `replied` sudah ada di skema, tapi pengisiannya belum dikerjakan. |
| Tabel quotations + perbandingan harga | Fitur ini baru masuk akal setelah balasan bisa dibaca otomatis. Tanpa itu, harga tetap harus diketik manual — sama saja dengan spreadsheet yang sudah dipakai sekarang. |
| Lampiran file | Bikin RFQ berisiko masuk spam dan menambah urusan penyimpanan file. Detail kebutuhan cukup ditulis di body email. |
| Template per kategori | Satu template dengan placeholder sudah menutup semua kategori. Template bisa diedit langsung di layar preview kalau perlu penyesuaian. |
| Integrasi kalender | Tidak menyentuh bottleneck-nya, yaitu loop kirim manual. |
| Docker, CI, test menyeluruh | Dijalankan lokal untuk demo. Yang dites manual: alur penuh brief sampai tracker, termasuk jalur gagal dan retry. |

Batasan lain yang perlu diketahui saat demo:

- Pengiriman berjalan sebagai background task di dalam proses uvicorn. Kalau
  server dimatikan di tengah batch, baris yang belum terkirim tetap berstatus
  `draft` dan bisa dilanjutkan lewat tombol retry di halaman tracker.
- Gmail punya batas kirim harian. Untuk batch besar, naikkan
  `SEND_DELAY_SECONDS`.
- Tracker hanya menampilkan status pengiriman, bukan status balasan. Status
  `replied` sudah ada di skema tapi belum pernah diisi, jadi tidak ditampilkan
  di mana pun.
