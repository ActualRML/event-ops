-- Event Ops — seed data
--
-- Every date is computed from seed time with SQLite date arithmetic, never
-- hardcoded, so a database rebuilt next year still reads as a system in use:
-- two events already past, one a fortnight out, one still being quoted.
--
-- One send is one category, so event 1 goes out in three batches — Tenda,
-- Lighting, Catering — each with its own kebutuhan and deadline, and all three
-- sharing one rundown. That makes the events/requests/category split visible
-- in the data rather than only in the schema.
--
-- Deliverable addresses use plus-addressing on one real inbox so a full batch
-- send can be verified end-to-end. Vendors 15 and 19 carry a data-entry typo
-- on purpose: the @ is missing. Gmail refuses those synchronously (SMTP 553),
-- which is what exercises the failure path — vendor 15 lands in the Lighting
-- batch and 19 in the Catering one, so two of event 1's three rounds show a
-- mixed result. Reserved example.* domains
-- would not work here: Gmail accepts them and bounces later, so they would
-- land in the outbox as status='sent'.

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

-- Ten catalog items, priced the way procurement actually quotes them: cost is
-- what the vendor charges per unit, value the sponsor-facing rate, and the
-- multiple between them is worked out on the page rather than stored.
-- Ungrouped on purpose — see the note on the items table in schema.sql.
-- Names and notes are Indonesian: procurement types them, and they read the
-- same on a printed sheet as on screen.
-- Notes are kept under about thirty characters on purpose: a longer note wraps
-- to a second line in the Item column and doubles the row's height. Four items
-- carry none at all, which is what a real catalogue looks like.
INSERT INTO items (id, nama, satuan, cost, value, catatan) VALUES
    (1,  'Tenda roder 10x20 m',      'unit',  3500000, 12000000, 'Termasuk plafon dan karpet.'),
    (2,  'Tenda sarnafil 5x5 m',     'unit',  1200000,  4000000, 'Untuk booth dan registrasi.'),
    (3,  'Sound system 10.000 watt', 'set',   8500000, 25000000, 'Termasuk operator.'),
    (4,  'Mic wireless handheld',    'pcs',    150000,   500000, ''),
    (5,  'AC standing 5 PK',         'unit',   750000,  2500000, 'Butuh daya tambahan.'),
    (6,  'Par LED 54x3 watt',        'titik',   85000,   300000, ''),
    (7,  'Moving head beam 230',     'titik',  350000,  1200000, 'Minimal enam titik.'),
    (8,  'Coffee break 250 pax',     'pax',      35000,   95000, ''),
    (9,  'Genset silent 100 kVA',    'unit',  2750000,  9000000, 'Bahan bakar delapan jam.'),
    (10, 'Backdrop panggung 8x4 m',  'unit',  2400000,  7500000, '');

-- Four events. Two already run, one a fortnight out, one still being quoted.
--
-- All three zones appear, and lokasi agrees with zona on every row — Bogor and
-- Jakarta are inside Jabodetabek, Bandung is Java but outside it, Bali is
-- outside Java. The two are separate columns because lokasi is an address
-- printed into vendor correspondence while zona is what the surcharge is
-- computed from, but seeding them inconsistently would teach the wrong thing.
--
-- Event 3 is the one carrying sponsors, and it is deliberately the luar_jawa
-- one: the surcharge is then visible on the sponsor pages on first load rather
-- than only after someone edits an event.
INSERT INTO events (id, judul_acara, tanggal_acara, lokasi, created_at, zona) VALUES
    (1, 'Gathering Tahunan Karyawan PT Cipta Karya Sentosa',
        date('now', 'localtime', '-42 days'),
        'Lapangan Parkir Utama, Sentul International Convention Center, Bogor',
        date('now', 'localtime', '-62 days') || ' 08:55:03', 'jabodetabek'),
    (2, 'Resepsi Pernikahan Anindya dan Bagas',
        date('now', 'localtime', '-21 days'),
        'Balai Kartini, Jalan Gatot Subroto Kav. 37, Jakarta Selatan',
        date('now', 'localtime', '-40 days') || ' 13:47:26', 'jabodetabek'),
    (3, 'Peluncuran Produk Nusantara Fresh Series',
        date('now', 'localtime', '+14 days'),
        'Ballroom Hotel Grand Inna, Jalan Pantai Kuta, Badung, Bali',
        date('now', 'localtime', '-13 days') || ' 10:02:41', 'luar_jawa'),
    (4, 'Seminar Nasional Transformasi Digital UMKM',
        date('now', 'localtime', '+42 days'),
        'Auditorium Gedung Serbaguna, Universitas Padjadjaran, Bandung',
        date('now', 'localtime', '-4 days') || ' 15:11:08', 'luar_jabodetabek');

-- One send is one category, so a big event is quoted in one batch per trade.
-- Event 1 runs three: Tenda, Lighting and Catering, each with its own
-- kebutuhan and its own deadline, and all three still share one rundown.
--
-- Batch 1 carries the full templates; the rest read them back out rather than
-- repeating thirty lines of email five more times. Every batch stores its own
-- copy, which is what the app does on a real send.
-- Every seeded batch carries a kode. NULL is the right value for rows MIGRATED
-- by 002_kode.sql — those really did go out before codes existed — but it is
-- the wrong value for a fresh seed: without one, no seeded subject carries an
-- [RFQ-xxxx] marker, and tier 2 of the reply ladder has nothing to match on.
-- Half the reply feature would be undemonstrable on a fresh build.
--
-- Fixed literals rather than anything generated, because they appear in the
-- seeded outbox subjects and in the seeded inbox rows below, and all three
-- have to agree.
INSERT INTO requests
    (id, event_id, category_id, kebutuhan, deadline, pengirim_nama,
     created_at, subject_template, body_template, kode)
VALUES (
    1, 1, 1,
    'Tenda roder untuk area utama, kapasitas 800 tamu, outdoor. Loading in H-1 mulai pukul 08.00.',
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
',
    '7A3F');

-- Event 1, round two: lighting.
INSERT INTO requests
    (id, event_id, category_id, kebutuhan, deadline, pengirim_nama, created_at,
     subject_template, body_template, kode)
SELECT 2, 1, 4,
       'Lighting panggung utama dan area tamu, acara malam hari sampai pukul 22.00 WIB.',
       date('now', 'localtime', '-52 days'),
       'Ronald Lilipaly',
       date('now', 'localtime', '-55 days') || ' 10:26:33',
       subject_template, body_template, 'C1B8'
FROM requests WHERE id = 1;

-- Event 1, round three: catering, once the headcount was final.
INSERT INTO requests
    (id, event_id, category_id, kebutuhan, deadline, pengirim_nama, created_at,
     subject_template, body_template, kode)
SELECT 3, 1, 5,
       'Konsumsi prasmanan 800 pax, tiga menu utama dan dua gubugan, termasuk pramusaji.',
       date('now', 'localtime', '-48 days'),
       'Ronald Lilipaly',
       date('now', 'localtime', '-51 days') || ' 09:40:12',
       subject_template, body_template, '4E2D'
FROM requests WHERE id = 1;

INSERT INTO requests
    (id, event_id, category_id, kebutuhan, deadline, pengirim_nama, created_at,
     subject_template, body_template, kode)
SELECT 4, 2, 2,
       'Sound system indoor untuk 600 tamu, akad pukul 09.00 dan resepsi pukul 19.00 WIB.',
       date('now', 'localtime', '-35 days'),
       'Ronald Lilipaly',
       date('now', 'localtime', '-38 days') || ' 14:05:19',
       subject_template, body_template, 'B905'
FROM requests WHERE id = 1;

INSERT INTO requests
    (id, event_id, category_id, kebutuhan, deadline, pengirim_nama, created_at,
     subject_template, body_template, kode)
SELECT 5, 3, 3,
       'Pendingin ruangan tambahan untuk ballroom, 250 tamu undangan dan media.',
       date('now', 'localtime', '-2 days'),
       'Ronald Lilipaly',
       date('now', 'localtime', '-12 days') || ' 11:38:07',
       subject_template, body_template, 'D6A1'
FROM requests WHERE id = 1;

-- Still being quoted: no outbox rows at all, so the tracker shows a batch that
-- has not been dispatched next to five that have.
INSERT INTO requests
    (id, event_id, category_id, kebutuhan, deadline, pengirim_nama, created_at,
     subject_template, body_template, kode)
SELECT 6, 4, 6,
       'Genset silent untuk cadangan daya seminar 400 peserta, sehari penuh.',
       date('now', 'localtime', '+21 days'),
       'Ronald Lilipaly',
       date('now', 'localtime', '-3 days') || ' 16:22:51',
       subject_template, body_template, '2F74'
FROM requests WHERE id = 1;

-- Subjects name the batch's category, not the vendor's own list — a vendor in
-- three categories quoted on the Lighting batch is written to about Lighting
-- and nothing else. Built off the batch's category here for exactly the reason
-- db.konteks_vendor does it at runtime.
-- Batch 1 (event 1, Tenda): six vendors, clean batch.
INSERT INTO outbox
    (request_id, vendor_id, email_tujuan, subject, status, message_id,
     sent_at, created_at)
SELECT 1, v.id, v.email,
       'Permintaan Penawaran ' || c.nama || ' - ' || v.nama_pt
         || ' (' || e.judul_acara || ') [RFQ-' || r.kode || ']',
       'sent',
       '<CAF' || printf('%015d', v.id * 1000003 + 1) || '@mail.gmail.com>',
       date('now', 'localtime', '-58 days')
         || ' 10:' || printf('%02d', 12 + v.id) || ':' || printf('%02d', (v.id * 7) % 60),
       date('now', 'localtime', '-58 days') || ' 10:11:03'
FROM v_vendor_lengkap v
JOIN requests r ON r.id = 1
JOIN events e ON e.id = r.event_id
JOIN categories c ON c.id = r.category_id
WHERE v.id IN (1, 2, 3, 4, 20, 25);

-- Batch 2 (event 1, Lighting): five vendors including the three-category one,
-- plus the typo address that the server refuses.
INSERT INTO outbox
    (request_id, vendor_id, email_tujuan, subject, status, error_msg, message_id,
     sent_at, created_at)
SELECT 2, v.id, v.email,
       'Permintaan Penawaran ' || c.nama || ' - ' || v.nama_pt
         || ' (' || e.judul_acara || ') [RFQ-' || r.kode || ']',
       CASE WHEN v.id = 15 THEN 'failed' ELSE 'sent' END,
       CASE WHEN v.id = 15
            THEN 'SMTPRecipientsRefused: (553, ''5.1.3 The recipient address <'
                 || v.email || '> is not a valid RFC-5321 address'')' END,
       CASE WHEN v.id <> 15
            THEN '<CAF' || printf('%015d', v.id * 1000003 + 2) || '@mail.gmail.com>' END,
       CASE WHEN v.id <> 15
            THEN date('now', 'localtime', '-54 days')
                 || ' 09:' || printf('%02d', 18 + v.id) || ':' || printf('%02d', (v.id * 7) % 60) END,
       date('now', 'localtime', '-54 days') || ' 09:17:52'
FROM v_vendor_lengkap v
JOIN requests r ON r.id = 2
JOIN events e ON e.id = r.event_id
JOIN categories c ON c.id = r.category_id
WHERE v.id IN (8, 13, 14, 15, 16);

-- Batch 3 (event 1, Catering): three vendors, the other typo address.
INSERT INTO outbox
    (request_id, vendor_id, email_tujuan, subject, status, error_msg, message_id,
     sent_at, created_at)
SELECT 3, v.id, v.email,
       'Permintaan Penawaran ' || c.nama || ' - ' || v.nama_pt
         || ' (' || e.judul_acara || ') [RFQ-' || r.kode || ']',
       CASE WHEN v.id = 19 THEN 'failed' ELSE 'sent' END,
       CASE WHEN v.id = 19
            THEN 'SMTPRecipientsRefused: (553, ''5.1.3 The recipient address <'
                 || v.email || '> is not a valid RFC-5321 address'')' END,
       CASE WHEN v.id <> 19
            THEN '<CAF' || printf('%015d', v.id * 1000003 + 3) || '@mail.gmail.com>' END,
       CASE WHEN v.id <> 19
            THEN date('now', 'localtime', '-50 days')
                 || ' 11:' || printf('%02d', 4 + v.id) || ':' || printf('%02d', (v.id * 11) % 60) END,
       date('now', 'localtime', '-50 days') || ' 11:03:28'
FROM v_vendor_lengkap v
JOIN requests r ON r.id = 3
JOIN events e ON e.id = r.event_id
JOIN categories c ON c.id = r.category_id
WHERE v.id IN (17, 18, 19);

-- Batch 4 (event 2, Sound System): four vendors, clean batch.
--
-- Vendor 25 is here AND in batch 1, and that overlap is deliberate. It is the
-- only vendor written to on two batches, and they belong to two different
-- events — Tenda for event 1, Sound System for event 2 — which is exactly the
-- situation tier 3 exists for. When that vendor sends a fresh message rather
-- than a reply, their address alone cannot say which conversation it answers,
-- so the ladder holds it instead of guessing. With every vendor on a single
-- batch the assign chooser only ever offered one option and the whole manual
-- step looked like ceremony.
--
-- Realistic, not contrived: vendor 25 carries categories Tenda and Sound
-- System, and a supplier quoting both is the many-to-many case the schema
-- notes already call out.
INSERT INTO outbox
    (request_id, vendor_id, email_tujuan, subject, status, message_id,
     sent_at, created_at)
SELECT 4, v.id, v.email,
       'Permintaan Penawaran ' || c.nama || ' - ' || v.nama_pt
         || ' (' || e.judul_acara || ') [RFQ-' || r.kode || ']',
       'sent',
       '<CAF' || printf('%015d', v.id * 1000003 + 4) || '@mail.gmail.com>',
       date('now', 'localtime', '-37 days')
         || ' 09:' || printf('%02d', 24 + v.id) || ':' || printf('%02d', (v.id * 11) % 60),
       date('now', 'localtime', '-37 days') || ' 09:23:41'
FROM v_vendor_lengkap v
JOIN requests r ON r.id = 4
JOIN events e ON e.id = r.event_id
JOIN categories c ON c.id = r.category_id
WHERE v.id IN (5, 6, 7, 25);

-- Batch 5 (event 3, AC): the event a fortnight out, dispatched cleanly.
INSERT INTO outbox
    (request_id, vendor_id, email_tujuan, subject, status, message_id,
     sent_at, created_at)
SELECT 5, v.id, v.email,
       'Permintaan Penawaran ' || c.nama || ' - ' || v.nama_pt
         || ' (' || e.judul_acara || ') [RFQ-' || r.kode || ']',
       'sent',
       '<CAF' || printf('%015d', v.id * 1000003 + 5) || '@mail.gmail.com>',
       date('now', 'localtime', '-11 days')
         || ' 15:' || printf('%02d', 6 + v.id) || ':' || printf('%02d', (v.id * 13) % 60),
       date('now', 'localtime', '-11 days') || ' 15:05:12'
FROM v_vendor_lengkap v
JOIN requests r ON r.id = 5
JOIN events e ON e.id = r.event_id
JOIN categories c ON c.id = r.category_id
WHERE v.id IN (9, 10, 12);

-- Three replies, all against batch 4 (event 2, Sound System, three vendors),
-- so one batch shows every state the feature can be in at once. Same reasoning
-- as the deliberately over-budget sponsor and the two typo'd email addresses:
-- the interesting states have to be visible on first load, or nobody
-- demonstrating this finds them.
--
-- Batch 4 therefore reads "1 of 4 vendors have replied", and that number is
-- the whole point — it is only right because the auto-reply below is excluded.
-- If a change ever makes it read 2 of 4, that exclusion has broken.
--
--   vendor 5   tier 1, a real quote     -> counted, unread, has an attachment
--   vendor 6   tier 1, an out-of-office -> stored, shown, NOT counted
--   vendor 25  tier 3, sender only      -> held; that vendor is on TWO batches
--
-- The attachment on the first one is NOT seeded here. Its bytes live on the
-- filesystem and SQL cannot copy a file, so init_db.py does it — see
-- salin_lampiran there, which writes db/seed_files/penawaran-contoh.pdf into
-- attachments/ and inserts the matching inbox_attachment row.
--
-- The two are coupled through the MESSAGE-ID below, not through a row id, so
-- adding another reply above this one is safe. If you change that message_id,
-- change SEED_LAMPIRAN in init_db.py to match — otherwise the build prints a
-- warning and the seeded reply simply has no attachment.
--
-- message_id here is the INCOMING message's own id, from the vendor's server,
-- which is why these do not look like the '<CAF...@mail.gmail.com>' ids in
-- outbox: those are ours.

-- Tier 1. Answers the exact outbox row, matched through In-Reply-To, and is
-- what a real quote looks like: a short body and the numbers in an attachment.
INSERT INTO inbox
    (message_id, from_email, from_nama, subject, received_at, body, tier,
     request_id, outbox_id, vendor_id, read_at, auto_reply, created_at)
SELECT '<20260715.9f2a41@mail.gemasuara.co.id>',
       v.email, v.pic_nama,
       'Re: ' || o.subject,
       date('now', 'localtime', '-36 days') || ' 14:22:10',
       'Kepada Yth. Bapak Ronald,' || char(10) || char(10) ||
       'Terima kasih atas undangan penawaran untuk acara resepsi tersebut.' || char(10) ||
       'Terlampir penawaran kami untuk sound system indoor 600 tamu, sudah' || char(10) ||
       'termasuk operator dan instalasi di lokasi. Harga belum termasuk PPN.' || char(10) || char(10) ||
       'Penawaran berlaku 14 hari. Mohon konfirmasi jika ada yang perlu' || char(10) ||
       'didiskusikan lebih dahulu.' || char(10) || char(10) ||
       'Hormat kami,' || char(10) || v.pic_nama || char(10) || v.nama_pt,
       1, 4, o.id, v.id,
       NULL,   -- unread, so the drawer badge has something to show
       0,
       date('now', 'localtime', '-36 days') || ' 14:25:03'
FROM outbox o JOIN vendors v ON v.id = o.vendor_id
WHERE o.request_id = 4 AND o.vendor_id = 5;

-- Tier 1 as well, and that is the point: an out-of-office comes from the
-- vendor's OWN address and carries In-Reply-To, so it matches the exact outbox
-- row and nothing in the gate or the ladder can tell it apart. Only the
-- Auto-Submitted header can, which is why auto_reply exists as a column.
INSERT INTO inbox
    (message_id, from_email, from_nama, subject, received_at, body, tier,
     request_id, outbox_id, vendor_id, read_at, auto_reply, created_at)
SELECT '<autoreply-20260715-8812@audioprima.co.id>',
       v.email, v.pic_nama,
       'Automatic reply: ' || o.subject,
       date('now', 'localtime', '-36 days') || ' 09:03:47',
       'Terima kasih atas email Anda.' || char(10) || char(10) ||
       'Saat ini saya sedang cuti dan akan kembali pada tanggal 20.' || char(10) ||
       'Email Anda akan saya balas setelah kembali bertugas. Untuk hal' || char(10) ||
       'mendesak silakan hubungi bagian operasional.' || char(10) || char(10) ||
       'Hormat kami,' || char(10) || v.pic_nama,
       1, 4, o.id, v.id,
       NULL,   -- unread AND uncounted: proves the badge excludes it too
       1,
       date('now', 'localtime', '-36 days') || ' 09:03:52'
FROM outbox o JOIN vendors v ON v.id = o.vendor_id
WHERE o.request_id = 4 AND o.vendor_id = 6;

-- Tier 3, and the reason the tier exists. A fresh message rather than a reply:
-- no In-Reply-To, no code in the subject. The sender is a known vendor and
-- that is ALL we know.
--
-- From vendor 25 on purpose — the one vendor written to on two batches, on two
-- different events. The subject says "penawaran" and nothing else, so the
-- address cannot say whether this answers the Tenda round on event 1 or the
-- Sound System round on event 2. A ladder that guessed would be right half the
-- time and silently wrong the other half, which is why it holds instead. The
-- chooser on the Replies page offers both batches and a human picks.
--
-- Deliberately ambiguous copy: it mentions neither category, so the demo does
-- not hand the answer to whoever is looking at it.
INSERT INTO inbox
    (message_id, from_email, from_nama, subject, received_at, body, tier,
     request_id, outbox_id, vendor_id, read_at, auto_reply, created_at)
SELECT '<CAF-mitrasarana-20260716-4471@mail.gmail.com>',
       v.email, v.pic_nama,
       'Penawaran untuk acara bulan depan',
       date('now', 'localtime', '-35 days') || ' 11:48:29',
       'Selamat siang Pak Ronald,' || char(10) || char(10) ||
       'Menindaklanjuti pembicaraan kita via telepon kemarin, berikut kami' || char(10) ||
       'sampaikan penawaran untuk kebutuhan acara tersebut. Mohon dicek dan' || char(10) ||
       'kami tunggu kabarnya.' || char(10) || char(10) ||
       'Terima kasih,' || char(10) || v.pic_nama || char(10) || v.nama_pt,
       3,
       NULL,   -- NEVER attached by the ladder: this vendor is on two batches
       NULL,   -- across two events, and an address cannot tell them apart
       v.id,
       NULL, 0,
       date('now', 'localtime', '-35 days') || ' 11:50:14'
FROM vendors v WHERE v.id = 25;

-- One successful check on record, so the Tracker and Replies pages show a
-- "last checked" time rather than "never checked" on first load. Without this
-- a fresh demo cannot tell the two apart, which is the exact confusion the
-- inbox_check table exists to prevent.
INSERT INTO inbox_check (started_at, ok, error_msg, examined, kept)
VALUES (date('now', 'localtime', '-35 days') || ' 12:00:00', 1, NULL, 12, 3);

-- Three work orders, each from a different batch and so a different category:
-- tenda and catering out of event 1's first and third rounds, sound system out
-- of event 2. The sequence restarts per year, the way db.next_nomor does it.
WITH terbit(request_id, vendor_id, harga, lingkup_kerja, termin, tgl) AS (
    VALUES
        (1, 1, 42500000,
         'Sewa 12 unit tenda roder ukuran 10x20 m termasuk plafon, karpet, pemasangan dan pembongkaran di lokasi.',
         '50% DP setelah SPK terbit, 50% H+7 setelah acara selesai.',
         date('now', 'localtime', '-50 days')),
        (3, 17, 58000000,
         'Katering prasmanan untuk 800 pax, tiga menu utama dan dua gubugan, termasuk peralatan saji dan pramusaji.',
         '30% DP, 70% H+14 setelah acara selesai.',
         date('now', 'localtime', '-44 days')),
        (4, 6, 21500000,
         'Paket sound system indoor 600 pax: line array, mixer digital, 4 monitor panggung, termasuk operator.',
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

-- Two rundowns, hung off events. Event 1 has three batches and still exactly
-- one running order. Event 1 finished inside its venue limit; event 3 runs
-- forty minutes past, so the over-limit warning is visible on first load
-- without anyone editing a duration.
INSERT INTO rundown (id, event_id, jam_mulai, batas_venue, created_at) VALUES
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

-- Two sponsors on event 3, the product launch that is a fortnight out and the
-- one still being quoted — so the package sits alongside a live rundown.
--
-- Sponsor 2 is deliberately over budget: 12% of 15.000.000 is 1.800.000, and
-- its two lines cost 2.550.000, so the detail page opens on the warning state
-- without anyone having to type a number to see it. Overspending is a decision
-- staff are allowed to make, so it is flagged and never blocked.
INSERT INTO sponsors (id, event_id, nama_pt, kontribusi, persen_budget, catatan, created_at) VALUES
    (1, 3, 'PT Boga Rasa Nusantara',  50000000, 12,
        'Kontrak sponsor utama, pembayaran dua termin.',
        date('now', 'localtime', '-12 days') || ' 09:31:18'),
    (2, 3, 'CV Mitra Segar Abadi',    15000000, 12,
        'Sponsor pendukung, minta tambahan lighting di luar paket.',
        date('now', 'localtime', '-9 days') || ' 14:05:52');

-- cost and value are the catalog prices as they stood when each line was added,
-- copied in rather than joined — the same snapshot the app writes. Editing an
-- item in /items afterwards leaves these untouched, which is the whole point.
--
-- Both sponsors are on event 3, which is luar_jawa, so every amount here is the
-- catalog base with +10% already applied: (base * 110 + 50) / 100, the same
-- arithmetic db.harga_zona does. zona_pct records the 10 that produced them, so
-- moving event 3 to another zone makes these lines show as older-rate rather
-- than as numbers that do not add up.
--
--   item 1  3.500.000 -> 3.850.000    12.000.000 -> 13.200.000
--   item 4    150.000 ->   165.000       500.000 ->    550.000
--   item 6     85.000 ->    93.500       300.000 ->    330.000
--   item 5    750.000 ->   825.000     2.500.000 ->  2.750.000
--   item 7    350.000 ->   385.000     1.200.000 ->  1.320.000
INSERT INTO sponsor_item (sponsor_id, item_id, qty, cost, value, created_at, zona_pct) VALUES
    -- 5.071.000 of a 6.000.000 budget: 929.000 still free.
    (1, 1, 1, 3850000, 13200000, date('now', 'localtime', '-12 days') || ' 09:40:02', 10),
    (1, 4, 4,  165000,   550000, date('now', 'localtime', '-12 days') || ' 09:41:37', 10),
    (1, 6, 6,   93500,   330000, date('now', 'localtime', '-11 days') || ' 16:22:41', 10),
    -- 2.805.000 against a 1.800.000 budget: 1.005.000 over. Still the
    -- deliberate over-budget sponsor after the surcharge — the warning state
    -- renders on first load, which is the reason this row is here.
    (2, 5, 2,  825000,  2750000, date('now', 'localtime',  '-9 days') || ' 14:18:09', 10),
    (2, 7, 3,  385000,  1320000, date('now', 'localtime',  '-8 days') || ' 11:07:33', 10);
