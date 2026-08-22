# Event Ops

Internal tool untuk event organizer. Satu acara ditangani dari mencari vendor
sampai hari-H: sebar RFQ ke banyak vendor sekaligus, baca balasannya, terbitkan
SPK untuk yang menang, jual paket ke sponsor, lalu susun rundown acaranya.
Semuanya menggantung pada satu baris `events` — batch RFQ, sponsor, dan rundown
sama-sama membawa `event_id` dan tidak satu pun menyalin judul, tanggal, atau
lokasinya. Satu acara, satu benang. Membetulkan judul acara yang salah ketik
membetulkannya di setiap tempat sekaligus.

## Masalah

Untuk satu acara, staf procurement mengirim RFQ ke vendor satu per satu lewat
email: 25 vendor berarti 25 kali menyalin brief yang sama dan mengganti nama PT
dan nama PIC. Setelah terkirim tidak ada catatan siapa saja yang sudah
dihubungi, SPK untuk vendor yang menang diketik ulang di Word, dan rundown
hari-H hidup di spreadsheet terpisah yang jam-jamnya harus dihitung ulang
manual setiap ada satu durasi berubah.

## Empat modul

### 1. Vendor & RFQ blast

Data vendor disimpan beserta kategorinya — tenda, sound system, lighting,
katering, AC, genset — dan status aktif/nonaktif. Satu vendor boleh masuk
beberapa kategori sekaligus, karena vendor tenda biasanya juga menyediakan
kursi dan panggung.

Brief acara diisi sekali, vendor dicentang lintas kategori, lalu sistem
merender satu email personal per vendor. Preview wajib: tombol kirim tidak
pernah mengirim langsung, email contoh selalu ditampilkan dulu. Pengiriman
jalan di background dengan jeda antar email, dan satu email gagal dicatat
sebagai `failed` lalu batch lanjut — tidak pernah menghentikan sisanya. Pesan
errornya diterjemahkan jadi kalimat biasa saat ditampilkan, bukan saat
disimpan: string `"ExceptionName: detail"` mentahnya tetap ada di
`outbox.error_msg`, jadi baris yang sudah telanjur gagal ikut memungut
kalimat yang diperbaiki tanpa migrasi apa pun.
Tracker tersusun tiga lapis, mengikuti cara acara itu dikerjakan. Halaman
depannya mendaftar **acara** — satu baris per acara, dengan jumlah batch dan
jumlah sponsornya. Membukanya menampilkan **batch-batch** acara itu, dinamai
kategorinya (Tenda, Sound System), bukan nomor. Membuka satu batch menampilkan
**status per vendor** beserta pesan error yang sudah diterjemahkan jadi
kalimat biasa, tombol retry, dan penerbitan SPK.

Pembagiannya begitu karena angka gabungan lintas batch tidak bisa
ditindaklanjuti: "6 dari 11 terkirim" untuk tiga ronde tidak menunjuk ronde
mana pun, dan tombol retry-nya ada di dalam. Daftar menyebut acara punya apa;
halaman di dalamnya menyebut bagaimana jalannya.

Balasan vendor dibaca di dalam app. Setiap batch membawa kode referensi
(`requests.kode`) yang dicetak ke subject sebagai `[RFQ-3F2A]`, dan subject itu
ikut terbawa saat vendor menekan Reply — jadi penanda itu pulang sendiri tanpa
vendor melakukan apa pun. Sebuah tombol menarik kotak masuk lewat IMAP dan
mencocokkan tiap pesan lewat empat tingkat, dari `In-Reply-To` yang menunjuk
persis satu baris outbox sampai kode subject saja. Yang tidak bisa dicocokkan
tidak dibuang diam-diam: ia muncul di daftar tersendiri di halaman tracker
untuk ditempatkan manual.

Alur: **brief → pilih kategori + centang vendor → preview → kirim → tracker
(acara → batch → vendor) → baca balasan**

### 2. Penerbitan SPK

SPK (Surat Perintah Kerja) diterbitkan dari baris vendor itu di halaman batch,
tapi hanya untuk vendor yang penawarannya **disetujui seseorang**. Membalas
bukan berarti disepakati: vendor yang menjawab lalu ditolak tidak pernah
membuka gerbang itu. Persetujuan adalah tindakan tersendiri dengan tombolnya
sendiri, di halaman detail balasan — harganya ada di depan mata saat menerima,
dan membuka halaman itu sudah menandai balasannya terbaca, jadi "tidak bisa
disetujui tanpa dibaca" dijamin oleh letak tombolnya, bukan oleh pemeriksaan
yang bisa lupa ditulis.

Yang diisi hanya harga, lingkup kerja, dan termin pembayaran; nama PT, PIC,
judul acara, tanggal, dan lokasi diambil dari data yang sudah ada.

Nomor surat dialokasikan sekali saat baris disimpan, di dalam transaksi, dan
tidak pernah dihitung ulang — dokumen yang dicetak ulang bulan depan tetap
membawa nomor aslinya. Hasilnya file `.docx` berbahasa Indonesia, dengan harga
dieja menjadi terbilang ("lima belas juta rupiah"). Satu SPK per pasangan
acara–vendor; menerbitkan ulang berarti mengedit yang sudah ada.

### 3. Rundown acara

Susunan acara hari-H: daftar kegiatan berurutan dengan durasi, PIC, dan
catatan. Jam mulai dan selesai tiap item tidak pernah disimpan — semuanya
dihitung ulang dari jam mulai acara ditambah durasi kumulatif. Ubah durasi satu
item, semua jam di bawahnya bergeser sendiri. Item bisa dinaikkan, diturunkan,
atau dihapus, dan urutannya selalu rapat tanpa nomor bolong.

Rundown boleh melewati tengah malam: mulai 22:00 dengan total 4 jam berarti
selesai 02:00. Kalau venue punya batas waktu dan acaranya lewat, halaman
memberi peringatan beserta selisih menitnya — memberi tahu, bukan memblokir,
karena acara yang molor tetap acara yang nyata. Halamannya bisa langsung
dicetak: aturan `@media print` menyembunyikan seluruh chrome aplikasi dan
menyisakan jadwalnya saja, seluruhnya dalam bahasa Indonesia karena lembar itu
dipegang kru dan vendor di lokasi. Warna adalah hal pertama yang hilang di
printer hitam-putih, jadi tidak ada satu pun yang bergantung padanya: semua
teks abu-abu kembali jadi hitam, dan peringatan lewat batas venue dicetak
sebagai kalimat biasa, bukan kartu bergaris merah.

### 4. Sponsor & paket

Sisi pemasukan acara. Tiap sponsor punya kontribusi dan satu persentase yang
menentukan berapa besar paket yang boleh dibelanjakan dari kontribusi itu —
default 12%. Paketnya disusun dari katalog `items`: tiap baris punya cost yang
kami bayar dan value yang ditagihkan ke sponsor, jadi halaman bisa melaporkan
sisa budget dan kelipatan nilainya sekaligus.

Uang di baris yang sudah terjual tidak pernah bergerak. Cost dan value
disalin dari katalog saat baris dibuat dan tidak pernah dibaca ulang — begitu
juga surcharge zona acara, yang dibekukan bersamanya. Menaikkan harga katalog
bulan depan meninggalkan setiap paket yang sudah tersusun persis seperti
semula, dan baris yang dihargai dengan tarif zona lama tetap **dilaporkan**
sebagai riwayat, tidak pernah diam-diam disesuaikan. Ini kebalikan dari aturan
rundown: rundown menggambarkan yang akan terjadi jadi selalu dihitung ulang,
paket mencatat yang sudah dijanjikan jadi harus diam di tempat.

Paket yang melewati budget tidak diblokir — halamannya melaporkan berapa
lebihnya dan menawarkan dua jalan keluar, karena staf boleh saja sengaja
melebihi. Ada satu halaman cetak terpisah untuk sponsor, dan halaman itu
**tidak pernah dikirimi angka cost sama sekali** oleh route-nya. Itu
jaminannya: angka internal tidak mungkin ikut tercetak karena tidak pernah
sampai ke template.

Sponsor tidak punya halaman daftar sendiri. Menu Sponsors adalah form tambah
sponsor; sponsor yang sudah ada dibaca lewat acaranya di tracker, karena satu
baris sponsor memang milik satu acara — kolomnya `NOT NULL` dan tabelnya
`UNIQUE(event_id, nama_pt)`.

## Stack

Python 3.12 · FastAPI · Jinja2 · HTMX · SQLite dengan raw SQL · aiosmtplib +
Gmail SMTP · python-docx · Pico.css v2 lewat CDN.

Tanpa ORM, tanpa framework frontend, tanpa build step. Semua query di `db.py`,
logika domain tanpa lapisan web di `core/`, satu router per area di `routes/`,
dan seluruh CSS custom dalam satu blok `<style>` di `templates/base.html`.

## Cara menjalankan

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows; macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

copy .env.example .env          # macOS/Linux: cp .env.example .env
python init_db.py               # skema + seed: 6 kategori, 25 vendor, 1 contoh acara

uvicorn main:app --reload
```

Buka http://127.0.0.1:8000 — otomatis diarahkan ke `/vendors`.

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
tracker tanpa satu pun email benar-benar terkirim.

```bash
python config.py                # tampilkan konfigurasi yang terbaca
python cek_email.py             # kirim satu email percobaan
python init_db.py               # bangun ulang database dari nol (menghapus yang ada)
```

## Batas scope

Ini MVP demo, bukan aplikasi produksi. Yang berikut **sengaja tidak dibangun**,
bukan karena terlewat:

| Tidak dibangun | Alasan |
| --- | --- |
| **LLM / AI di mana pun** | Tidak ada satu pun panggilan model. Semua teks keluar dari template Jinja dan tabel yang ditulis tangan — termasuk terbilang, pesan error SMTP, dan aritmetika rundown. Hasilnya bisa diprediksi dan diuji. |
| **Login / autentikasi** | Tool internal, satu tim kecil di jaringan kantor. Route kirim pun tidak diautentikasi — tidak ada lapisan auth sama sekali. Menambahnya berarti user, session, dan reset password, semuanya di luar masalah yang mau diselesaikan. |
| **Test otomatis** | Tidak ada. Yang diuji manual: alur penuh brief sampai tracker termasuk jalur gagal dan retry, penerbitan dan cetak ulang SPK, serta aritmetika rundown termasuk lewat tengah malam dan batas venue. |
| **Migrasi skema** | Tidak ada, dan memang tidak diperlukan. Perubahan skema dilakukan dengan menyunting `db/schema.sql` lalu membangun ulang database lewat `python init_db.py --force`. Datanya data demo — dibuat ulang, bukan dipertahankan — jadi jalur ALTER TABLE tidak membeli apa pun. Sempat ada `db/migrations/` berisi SQL bernomor untuk empat perubahan; keempatnya toh sudah dilipat ke `schema.sql`, yang memang dipakai setiap build, sehingga file-file itu hanya deskripsi kedua dari skema yang sama dan tidak pernah dijalankan siapa pun. Sudah diverifikasi setara lalu dihapus. Tanpa `--force`, `init_db.py` menolak, menyebut baris apa saja yang akan hilang, dan mencetak perintah backup-nya. |
| **Parsing harga dari lampiran** | Di luar cakupan dan tetap begitu. Menyimpan dan menampilkan balasan adalah satu hal; membaca angka dari PDF atau foto penawaran adalah hal lain, dan yang kedua tidak akan dibangun. |
| **Tabel quotations + perbandingan harga** | Balasan memang sudah terbaca, tapi harganya tidak — dan tanpa angka yang terekstrak otomatis, tabel banding cuma jadi tempat mengetik ulang harga, sama saja dengan spreadsheet yang sudah dipakai. Harga masuk sekali saja, saat SPK diterbitkan. |
| **Lampiran pada RFQ yang dikirim** | Bikin email berisiko masuk spam dan menambah urusan penyimpanan. Detail kebutuhan cukup ditulis di body. Lampiran yang **masuk** justru sebaliknya — lampiran di balasan vendor disimpan ke folder `attachments/` dan bisa diunduh dari halaman balasan, dengan nama file di disk yang kami tentukan sendiri, terpisah dari nama asli kiriman vendor. |
| **Template email per kategori** | Satu template dengan placeholder sudah menutup semua kategori. |
| **Integrasi kalender, Docker, CI** | Tidak menyentuh bottleneck-nya, yaitu loop kirim manual. Dijalankan lokal untuk demo. |

Batasan lain yang perlu diketahui saat demo:

- Pengiriman berjalan sebagai background task di dalam proses uvicorn. Kalau
  server dimatikan di tengah batch, baris yang belum terkirim tetap berstatus
  `draft` dan bisa dilanjutkan lewat tombol retry di halaman tracker.
- Gmail punya batas kirim harian. Untuk batch besar, naikkan
  `SEND_DELAY_SECONDS`.
- **`db/rfq.db` bukan lagi seluruh sistemnya.** Byte lampiran ada di folder
  `attachments/`, jadi menyalin databasenya saja menghasilkan salinan yang
  setiap baris lampirannya utuh — nama file, ukuran, tipe — tanpa satu byte
  isinya, dan setiap unduhan jadi 404. Salin `attachments/` bersamaan dengan
  databasenya. Tidak ada yang mengotomatiskan ini.
- Pengecekan balasan dijalankan lewat tombol, bukan penjadwal. Tidak ada
  poller — `IMAP SEARCH SINCE` cuma punya ketelitian tanggal, jadi setiap
  pemeriksaan mengulang sehari penuh dari pemeriksaan terakhir yang berhasil,
  dan `inbox.message_id UNIQUE` yang membuat tumpang tindih itu tidak
  berdampak. Pemeriksaan yang gagal tidak pernah memajukan watermark-nya.
- Balasan otomatis (out-of-office) tetap disimpan dan ditampilkan, tapi tidak
  ikut dihitung sebagai jawaban. Dideteksi dari header, tidak pernah dari
  subject — vendor di sini menjawab dalam bahasa Indonesia.
