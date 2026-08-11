-- Event Ops — seed data
--
-- Every date is computed from seed time with SQLite date arithmetic, never
-- hardcoded, so a database rebuilt next year still reads as a system in use:
-- two events already past, one a fortnight out, one still being quoted.
--
-- Deliverable addresses use plus-addressing on one real inbox so a full batch
-- send can be verified end-to-end. Vendors 15 and 19 carry a data-entry typo
-- on purpose: the @ is missing. Gmail refuses those synchronously (SMTP 553),
-- which is what exercises the failure path and gives request 1 its mixed
-- batch. Reserved example.* domains would not work here — Gmail accepts them
-- and bounces later, so they would land in the outbox as status='sent'.

INSERT INTO categories (id, nama) VALUES
    (1, 'Tenda'),
    (2, 'Sound System'),
    (3, 'AC'),
    (4, 'Lighting'),
    (5, 'Catering'),
    (6, 'Genset');

INSERT INTO vendors (id, nama_pt, pic_nama, email, no_hp, area, catatan, aktif) VALUES
    (1,  'PT Sinar Terang Mandiri',    'Budi Santoso',      'rmlilipaly+sinarterang@gmail.com',     '081234567801', 'Bekasi',            'Tenda roder dan plafon, stok besar.',            1),
    (2,  'CV Karya Tenda Nusantara',   'Rina Wijaya',       'rmlilipaly+karyatenda@gmail.com',      '081345678902', 'Depok',             NULL,                                             1),
    (3,  'UD Berkah Jaya Tenda',       'Slamet Riyadi',     'rmlilipaly+berkahjaya@gmail.com',      '081567890123', 'Tangerang',         'Harga bersaing, minimal order 5 unit.',          1),
    (4,  'PT Anugerah Pratama Event',  'Dewi Lestari',      'rmlilipaly+anugerahpratama@gmail.com', '081789012345', 'Jakarta Timur',     'Bisa paket tenda sekalian lighting.',            1),
    (5,  'PT Gema Suara Perkasa',      'Andi Nugroho',      'rmlilipaly+gemasuara@gmail.com',       '081890123456', 'Jakarta Barat',     'Line array untuk outdoor sampai 2000 pax.',      1),
    (6,  'CV Audio Prima Mandiri',     'Hendra Kusuma',     'rmlilipaly+audioprima@gmail.com',      '082112345678', 'Tangerang Selatan', NULL,                                             1),
    (7,  'UD Nada Rezeki',             'Yusuf Maulana',     'rmlilipaly+nadarezeki@gmail.com',      '082223456789', 'Bogor',             'Respon cepat, sering dipakai acara kampus.',     1),
    (8,  'PT Sentra Multi Teknik',     'Fajar Ramadhan',    'rmlilipaly+sentramulti@gmail.com',     '083834567890', 'Jakarta Selatan',   'Vendor paket: sound, lighting, genset.',         1),
    (9,  'PT Adem Sejahtera Teknik',   'Siti Rahmawati',    'rmlilipaly+ademsejahtera@gmail.com',   '085145678901', 'Jakarta Utara',     'AC standing 5PK dan ducting.',                   1),
    (10, 'CV Sejuk Abadi Teknik',      'Agus Setiawan',     'rmlilipaly+sejukabadi@gmail.com',      '085256789012', 'Bekasi',            NULL,                                             1),
    (11, 'UD Angin Sejuk Mandiri',     'Nur Aisyah',        'rmlilipaly+anginsejuk@gmail.com',      '085667890123', 'Depok',             'Sudah tidak beroperasi sejak 2025.',             0),
    (12, 'PT Klima Teknik Indonesia',  'Rudi Hartono',      'rmlilipaly+klimateknik@gmail.com',     '085778901234', 'Jakarta Pusat',     'AC dan genset satu paket, teknisi standby.',     1),
    (13, 'PT Cahaya Gemilang Kreasi',  'Bayu Prasetyo',     'rmlilipaly+cahayagemilang@gmail.com',  '085889012345', 'Jakarta Selatan',   'Moving head dan par LED.',                       1),
    (14, 'CV Lentera Panggung',        'Maya Sari',         'rmlilipaly+lenterapanggung@gmail.com', '085990123456', 'Tangerang',         NULL,                                             1),
    (15, 'UD Sorot Terang',            'Iwan Setiadi',      'kontaksorotterang.co.id',              '087701234567', 'Bogor',             'Alamat email salah ketik saat input, belum dikoreksi.', 1),
    (16, 'PT Visual Cahaya Mandiri',   'Ratna Dewi',        'rmlilipaly+visualcahaya@gmail.com',    '087812345678', 'Jakarta Barat',     'Sekalian videotron kalau diminta.',              1),
    (17, 'PT Selera Nusantara Boga',   'Tuti Handayani',    'rmlilipaly+seleranusantara@gmail.com', '088123456789', 'Jakarta Pusat',     'Prasmanan dan gubugan, halal.',                  1),
    (18, 'CV Dapur Bunda Katering',    'Endang Susilowati', 'rmlilipaly+dapurbunda@gmail.com',      '089534567890', 'Depok',             NULL,                                             1),
    (19, 'UD Rasa Nikmat Catering',    'Joko Purnomo',      'order.rasanikmat.gmail.com',           '089645678901', 'Bekasi',            'Kontak email bermasalah, biasanya via telepon.', 1),
    (20, 'PT Boga Rasa Prima',         'Lina Marlina',      'rmlilipaly+bogarasa@gmail.com',        '081256789012', 'Tangerang Selatan', 'Katering plus tenda untuk acara outdoor.',       1),
    (21, 'PT Daya Listrik Mandiri',    'Eko Wahyudi',       'rmlilipaly+dayalistrik@gmail.com',     '081367890123', 'Jakarta Utara',     'Genset silent 100-500 kVA.',                     1),
    (22, 'CV Sumber Energi Perkasa',   'Dian Puspita',      'rmlilipaly+sumberenergi@gmail.com',    '081578901234', 'Bekasi',            NULL,                                             1),
    (23, 'UD Genset Barokah',          'Ahmad Fauzi',       'rmlilipaly+gensetbarokah@gmail.com',   '081789012346', 'Bogor',             'Termasuk operator selama acara.',                1),
    (24, 'PT Trimitra Power Solusi',   'Reza Pratama',      'rmlilipaly+trimitrapower@gmail.com',   '081890123457', 'Jakarta Timur',     NULL,                                             1),
    (25, 'PT Mitra Sarana Eventindo',  'Wulan Anggraini',   'rmlilipaly+mitrasarana@gmail.com',     '082134567891', 'Jakarta Selatan',   'Sering handle acara korporat.',                  1);

-- 20 vendors in one category; 4 in two; vendor 8 in three.
INSERT INTO vendor_categories (vendor_id, category_id) VALUES
    (1, 1),
    (2, 1),
    (3, 1),
    (4, 1), (4, 4),
    (5, 2),
    (6, 2),
    (7, 2),
    (8, 2), (8, 4), (8, 6),
    (9, 3),
    (10, 3),
    (11, 3),
    (12, 3), (12, 6),
    (13, 4),
    (14, 4),
    (15, 4),
    (16, 4),
    (17, 5),
    (18, 5),
    (19, 5),
    (20, 5), (20, 1),
    (21, 6),
    (22, 6),
    (23, 6),
    (24, 6),
    (25, 1), (25, 2);

-- Request 1 carries the full templates; the rest read them back out rather
-- than repeating thirty lines of email three more times. Every request stores
-- its own copy, which is what the app does on a real send.
INSERT INTO requests
    (id, judul_acara, tanggal_acara, lokasi, kebutuhan, deadline, pengirim_nama,
     created_at, subject_template, body_template)
VALUES (
    1,
    'Gathering Tahunan Karyawan PT Cipta Karya Sentosa',
    date('now', 'localtime', '-42 days'),
    'Lapangan Parkir Utama, Sentul International Convention Center, Bogor',
    'Kapasitas 800 tamu, acara outdoor mulai pukul 16.00 sampai 22.00 WIB. Loading in H-1 mulai pukul 08.00.',
    date('now', 'localtime', '-56 days'),
    'Ronald Lilipaly',
    date('now', 'localtime', '-60 days') || ' 09:12:44',
    'Permintaan Penawaran {{ kategori }} - {{ nama_pt }} ({{ judul_acara }})',
'Kepada Yth.
Bapak/Ibu {{ pic_nama }}
{{ nama_pt }}
di tempat

Dengan hormat,

Sehubungan dengan rencana penyelenggaraan acara di bawah ini, kami bermaksud
meminta penawaran harga untuk kebutuhan {{ kategori }}.

Nama acara    : {{ judul_acara }}
Tanggal       : {{ tanggal_acara }}
Lokasi        : {{ lokasi }}
Kebutuhan     : {{ kebutuhan }}

Mohon penawaran yang Bapak/Ibu sampaikan mencantumkan hal-hal berikut:

1. Harga satuan dan harga total untuk setiap item yang ditawarkan.
2. Keterangan apakah harga sudah termasuk PPN atau belum.
3. Keterangan apakah biaya pengiriman dan instalasi di lokasi sudah termasuk
   dalam harga, atau ditagihkan terpisah.
4. Masa berlaku penawaran.

Kami mohon penawaran dapat kami terima paling lambat {{ deadline }}. Apabila
ada detail teknis yang perlu didiskusikan lebih dahulu, silakan membalas email
ini atau menghubungi kami langsung.

Atas perhatian dan kerja sama Bapak/Ibu, kami ucapkan terima kasih.

Hormat kami,

{{ pengirim_nama }}
Divisi Procurement
');

INSERT INTO requests
    (id, judul_acara, tanggal_acara, lokasi, kebutuhan, deadline, pengirim_nama,
     created_at, subject_template, body_template)
SELECT 2,
       'Resepsi Pernikahan Anindya dan Bagas',
       date('now', 'localtime', '-21 days'),
       'Balai Kartini, Jalan Gatot Subroto Kav. 37, Jakarta Selatan',
       'Resepsi indoor 600 tamu, akad pukul 09.00 dan resepsi pukul 19.00 WIB. Dekorasi rustic, panggung utama 8x4 m.',
       date('now', 'localtime', '-35 days'),
       'Ronald Lilipaly',
       date('now', 'localtime', '-38 days') || ' 14:05:19',
       subject_template, body_template
FROM requests WHERE id = 1;

INSERT INTO requests
    (id, judul_acara, tanggal_acara, lokasi, kebutuhan, deadline, pengirim_nama,
     created_at, subject_template, body_template)
SELECT 3,
       'Peluncuran Produk Nusantara Fresh Series',
       date('now', 'localtime', '+14 days'),
       'Ballroom Hotel Grand Mercure, Jalan Hayam Wuruk, Jakarta Pusat',
       'Peluncuran produk untuk 250 tamu undangan dan media, indoor. Butuh panggung 6x4 m, LED screen, dan area demo produk.',
       date('now', 'localtime', '-2 days'),
       'Ronald Lilipaly',
       date('now', 'localtime', '-12 days') || ' 11:38:07',
       subject_template, body_template
FROM requests WHERE id = 1;

-- Still being quoted: no outbox rows at all, so the tracker shows a request
-- that has not been dispatched next to three that have.
INSERT INTO requests
    (id, judul_acara, tanggal_acara, lokasi, kebutuhan, deadline, pengirim_nama,
     created_at, subject_template, body_template)
SELECT 4,
       'Seminar Nasional Transformasi Digital UMKM',
       date('now', 'localtime', '+42 days'),
       'Auditorium Gedung Serbaguna, Universitas Padjadjaran, Bandung',
       'Seminar sehari untuk 400 peserta, ruang ber-AC. Butuh sound system, lighting panggung, dan konsumsi untuk dua sesi.',
       date('now', 'localtime', '+21 days'),
       'Ronald Lilipaly',
       date('now', 'localtime', '-3 days') || ' 16:22:51',
       subject_template, body_template
FROM requests WHERE id = 1;

-- Subjects are built from the same pieces renderer.render_email uses, off
-- v_vendor_lengkap, so the stored subject matches what a real send produces
-- for a multi-category vendor instead of being retyped by hand.
-- Request 1: eight vendors, the two typo addresses refused by the server.
INSERT INTO outbox
    (request_id, vendor_id, email_tujuan, subject, status, error_msg, message_id,
     sent_at, created_at)
SELECT 1,
       v.id,
       v.email,
       'Permintaan Penawaran ' || v.kategori || ' - ' || v.nama_pt || ' (' || r.judul_acara || ')',
       CASE WHEN v.id IN (15, 19) THEN 'failed' ELSE 'sent' END,
       CASE WHEN v.id IN (15, 19)
            THEN 'SMTPRecipientsRefused: (553, ''5.1.3 The recipient address <'
                 || v.email || '> is not a valid RFC-5321 address'')' END,
       CASE WHEN v.id NOT IN (15, 19)
            THEN '<CAF' || printf('%015d', v.id * 1000003 + 1) || '@mail.gmail.com>' END,
       CASE WHEN v.id NOT IN (15, 19)
            THEN date('now', 'localtime', '-58 days')
                 || ' 10:' || printf('%02d', 12 + v.id) || ':' || printf('%02d', (v.id * 7) % 60) END,
       date('now', 'localtime', '-58 days') || ' 10:11:03'
FROM v_vendor_lengkap v
JOIN requests r ON r.id = 1
WHERE v.id IN (1, 5, 9, 13, 15, 17, 19, 21);

-- Request 2: six vendors, clean batch.
INSERT INTO outbox
    (request_id, vendor_id, email_tujuan, subject, status, message_id,
     sent_at, created_at)
SELECT 2,
       v.id,
       v.email,
       'Permintaan Penawaran ' || v.kategori || ' - ' || v.nama_pt || ' (' || r.judul_acara || ')',
       'sent',
       '<CAF' || printf('%015d', v.id * 1000003 + 2) || '@mail.gmail.com>',
       date('now', 'localtime', '-37 days')
         || ' 09:' || printf('%02d', 24 + v.id) || ':' || printf('%02d', (v.id * 11) % 60),
       date('now', 'localtime', '-37 days') || ' 09:23:41'
FROM v_vendor_lengkap v
JOIN requests r ON r.id = 2
WHERE v.id IN (4, 6, 10, 14, 18, 22);

-- Request 3: the event a fortnight out, dispatched cleanly, quotes coming in.
INSERT INTO outbox
    (request_id, vendor_id, email_tujuan, subject, status, message_id,
     sent_at, created_at)
SELECT 3,
       v.id,
       v.email,
       'Permintaan Penawaran ' || v.kategori || ' - ' || v.nama_pt || ' (' || r.judul_acara || ')',
       'sent',
       '<CAF' || printf('%015d', v.id * 1000003 + 3) || '@mail.gmail.com>',
       date('now', 'localtime', '-11 days')
         || ' 15:' || printf('%02d', 6 + v.id) || ':' || printf('%02d', (v.id * 13) % 60),
       date('now', 'localtime', '-11 days') || ' 15:05:12'
FROM v_vendor_lengkap v
JOIN requests r ON r.id = 3
WHERE v.id IN (5, 12, 16, 20, 24, 25);

-- Three work orders across the two events already run. The sequence restarts
-- per year, the way db.py allocates it, so a rebuild near New Year still
-- produces numbers the app would go on to extend correctly.
WITH terbit(request_id, vendor_id, harga, lingkup_kerja, termin, tgl) AS (
    VALUES
        (1, 1, 42500000,
         'Sewa 12 unit tenda roder ukuran 10x20 m termasuk plafon, karpet, pemasangan dan pembongkaran di lokasi.',
         '50% DP setelah SPK terbit, 50% H+7 setelah acara selesai.',
         date('now', 'localtime', '-50 days')),
        (1, 17, 58000000,
         'Katering prasmanan untuk 800 pax, tiga menu utama dan dua gubugan, termasuk peralatan saji dan pramusaji.',
         '30% DP, 70% H+14 setelah acara selesai.',
         date('now', 'localtime', '-49 days')),
        (2, 14, 9750000,
         'Paket lighting resepsi: 24 par LED, 4 moving head, 1 follow spot, termasuk operator selama acara berlangsung.',
         '50% DP, 50% H+7 setelah acara selesai.',
         date('now', 'localtime', '-30 days'))
)
INSERT INTO spk
    (request_id, vendor_id, nomor, harga, lingkup_kerja, termin, tanggal_terbit, created_at)
SELECT request_id,
       vendor_id,
       printf('%03d', row_number() OVER (PARTITION BY strftime('%Y', tgl) ORDER BY tgl))
         || '/SPK/PROC/'
         || CASE strftime('%m', tgl)
              WHEN '01' THEN 'I'   WHEN '02' THEN 'II'  WHEN '03' THEN 'III'
              WHEN '04' THEN 'IV'  WHEN '05' THEN 'V'   WHEN '06' THEN 'VI'
              WHEN '07' THEN 'VII' WHEN '08' THEN 'VIII' WHEN '09' THEN 'IX'
              WHEN '10' THEN 'X'   WHEN '11' THEN 'XI'  WHEN '12' THEN 'XII'
            END
         || '/' || strftime('%Y', tgl),
       harga, lingkup_kerja, termin, tgl, tgl || ' 11:20:35'
FROM terbit;

-- Two rundowns. Request 1 finished inside its venue limit; request 3 runs
-- forty minutes past, so the over-limit warning is visible on first load
-- without anyone editing a duration.
INSERT INTO rundown (id, request_id, jam_mulai, batas_venue, created_at) VALUES
    (1, 1, '16:00', '22:00', date('now', 'localtime', '-59 days') || ' 15:40:22'),
    (2, 3, '09:00', '15:00', date('now', 'localtime', '-11 days') || ' 10:05:47');

INSERT INTO rundown_item (rundown_id, urutan, kegiatan, durasi_menit, pic, catatan) VALUES
    (1, 1, 'Registrasi dan ramah tamah',        45, 'Wulan Anggraini', 'Meja registrasi di pintu masuk utama'),
    (1, 2, 'Pembukaan dan sambutan direksi',    30, 'Budi Santoso',    NULL),
    (1, 3, 'Penyerahan penghargaan karyawan',   40, 'Dewi Lestari',    'Daftar penerima sudah dikirim HRD'),
    (1, 4, 'Makan malam bersama',               75, 'Tuti Handayani',  'Prasmanan untuk 800 pax'),
    (1, 5, 'Hiburan band dan doorprize',       105, 'Maya Sari',       'Butuh sound system penuh dan follow spot'),
    (1, 6, 'Penutupan dan foto bersama',        35, 'Wulan Anggraini', NULL),

    (2, 1, 'Registrasi media dan tamu undangan', 60, 'Ratna Dewi',     'Media kit dibagikan saat registrasi'),
    (2, 2, 'Pembukaan dan sambutan manajemen',   30, 'Reza Pratama',   NULL),
    (2, 3, 'Presentasi produk Nusantara Fresh',  45, 'Lina Marlina',   'Slide dan demo di panggung utama'),
    (2, 4, 'Demo produk dan sesi cicip',         75, 'Tuti Handayani', 'Sampel untuk 250 tamu'),
    (2, 5, 'Sesi tanya jawab media',             40, 'Ratna Dewi',     NULL),
    (2, 6, 'Coffee break dan networking',        60, 'Lina Marlina',   'Area lobi ballroom'),
    (2, 7, 'Sesi foto bersama dan penutupan',    90, 'Wulan Anggraini', 'Backdrop di panggung utama');
