-- Vendor RFQ Blast — seed data
-- Deliverable addresses use plus-addressing on one real inbox so a full
-- batch send can be verified end-to-end. Vendors 15 and 19 carry a
-- data-entry typo on purpose: the @ is missing. Gmail refuses those
-- synchronously (SMTP 553), which is what exercises the failure path.
-- Reserved example.* domains would not work here — Gmail accepts them and
-- bounces later, so they would land in the outbox as status='sent'.

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

INSERT INTO requests
    (id, judul_acara, tanggal_acara, lokasi, kebutuhan, deadline, pengirim_nama,
     subject_template, body_template)
VALUES (
    1,
    'Gathering Tahunan PT Cipta Karya Sentosa',
    '2026-09-19',
    'Lapangan Parkir Utama, Sentul International Convention Center, Bogor',
    'Kapasitas 800 tamu, acara outdoor mulai pukul 16.00 sampai 22.00 WIB. Loading in H-1 mulai pukul 08.00.',
    '2026-08-12',
    'Ronald Lilipaly',
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

-- outbox intentionally left empty.
