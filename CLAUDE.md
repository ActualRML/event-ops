# Vendor RFQ Blast — MVP

## Konteks
Tool internal untuk perusahaan event organizer. Mereka mencari vendor
lewat email. Tiap ada acara, staf harus kirim permintaan penawaran (RFQ)
ke belasan vendor satu per satu secara manual — ini bottleneck-nya.

Ini MVP untuk demo, bukan production. Prioritasnya alur lengkap yang
jalan end-to-end, bukan kode production-grade.

## Stack
- Python 3.12, FastAPI, Jinja2, HTMX
- SQLite (file lokal, SQL mentah, tanpa ORM — pakai sqlite3 stdlib)
- aiosmtplib untuk kirim email (SMTP Gmail, app password)
- Pico.css v2 via CDN + sedikit CSS custom untuk badge status dan
  kartu angka. JANGAN tulis CSS panjang, jangan pakai Tailwind/React.
- Config lewat .env

Dependency: fastapi, uvicorn[standard], jinja2, python-multipart,
python-dotenv, aiosmtplib. Tidak lebih.

## Alur aplikasi
Isi brief acara → pilih kategori + centang vendor (bisa lintas kategori)
→ preview email → kirim (bertahap, ada progress) → tracker status

Tiga halaman: Vendor (CRUD), Kirim, Tracker.

## Skema database

categories(id PK, nama UNIQUE COLLATE NOCASE)

vendors(id PK, nama_pt, pic_nama, email, no_hp, area, catatan,
        aktif DEFAULT 1 CHECK(aktif IN (0,1)), created_at)

vendor_categories(vendor_id FK, category_id FK,
                  PRIMARY KEY(vendor_id, category_id))

requests(id PK, judul_acara, tanggal_acara, lokasi, kebutuhan,
         deadline, pengirim_nama, subject_template, body_template,
         created_at)

outbox(id PK, request_id FK, vendor_id FK, email_tujuan, subject,
       status CHECK(status IN ('draft','sent','failed','replied')),
       error_msg, message_id, sent_at, created_at,
       UNIQUE(request_id, vendor_id))

Catatan:
- Vendor bisa punya banyak kategori (many-to-many) — vendor tenda
  sering sekalian menyewakan kursi/panggung
- email_tujuan disimpan di outbox agar riwayat tetap akurat kalau
  email vendor berubah
- message_id disimpan sebagai fondasi fitur baca balasan nanti
- subject_template terpisah dari body karena subject harus unik per
  vendor (kalau sama, Gmail menggabungkannya jadi satu thread)

## Aturan yang tidak boleh dilanggar

1. PRAGMA foreign_keys = ON dijalankan di SETIAP koneksi baru, bukan
   sekali saat inisialisasi.
2. DRY_RUN=true adalah default. Kalau aktif, jangan kirim email —
   cukup log tujuan, subject, dan body.
3. Wajib ada layar preview sebelum kirim. Tombol kirim TIDAK BOLEH
   langsung mengirim.
4. Jeda SEND_DELAY_SECONDS antar email.
5. Satu email gagal tidak menghentikan sisanya — catat status 'failed'
   dan error_msg, lanjut ke vendor berikutnya.
6. Pengiriman dipisah dua tahap: (A) simpan request + baris outbox
   status 'draft' dalam satu transaksi cepat, lalu (B) kirim di
   background, commit per email.
7. Progress dibaca dari database, bukan variabel di memori.
8. Cegah kirim dobel di tiga lapis: tombol disable, cek server,
   UNIQUE(request_id, vendor_id).
9. Preview dan kirim harus memanggil fungsi render yang sama persis.
10. Semua query SQL ditaruh di satu modul db.py, jangan disebar di
    handler.

## Di luar scope — JANGAN dibangun
Login/auth · parsing balasan otomatis · tabel harga/penawaran ·
perbandingan harga · lampiran file · template per kategori ·
integrasi kalender · Docker · CI · test menyeluruh

Kalau menurutmu salah satu di atas perlu, sebutkan alasannya dulu,
jangan langsung dibangun.

## Gaya kerja
- Kerjakan per fase, jangan lompat. Selesai sampai checkpoint,
  berhenti, tunggu konfirmasi.
- Fungsi kecil, tanpa abstraksi berlebih. Ini MVP.
- UI seadanya sampai fase 5 selesai. Jangan poles tampilan di awal.
- Komentar dan pesan commit boleh bahasa Indonesia.
