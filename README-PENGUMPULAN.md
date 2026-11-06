# CATATAN MUROJAAH — Paket Kode Sumber (Pengumpulan Hackathon)

Tim: **CATATAN MUROJAAH AI AGENT** — Tencent Cloud Hackathon Indonesia 2026

Identitas build: commit `ae1c213`, versi `2026.11.05.3-web`,
hash frontend (`static/aplikasi.html`, SHA-256)
`70fc210253e52686f3ae573df1add2adbec8fb3e92d5966dc7405f0dd6fa75f1`.
Nama internal historis repositori: TUNTAS (tidak dipakai lagi di artefak publik).

---

## 1. Apa yang diselesaikan produk ini

**CATATAN MUROJAAH** mengubah rekaman atau transkrip rapat/kelas menjadi empat
keluaran yang siap dipakai, disusun dari sumber dengan rujukan paragraf:

1. **Catatan Lengkap** — catatan menyeluruh per bagian, tetap menautkan ke
   sumber aslinya.
2. **Rangkuman & Insight** — poin inti dan pemahaman yang bisa ditindaklanjuti.
3. **Tugas & Komitmen** — daftar tugas dengan PIC dan tenggat yang terbaca
   dari sumber; tugas yang detailnya tidak tersedia di sumber **tidak
   dikarang** — ditandai perlu klarifikasi.
4. **Langkah Penerapan** — rencana eksekusi terstruktur (email/kalender/tugas)
   yang lolos gerbang persetujuan.

Di dalam aplikasi ada asisten **Teman Paham**: panel tanya-jawab bebas yang
menjawab dengan rujukan ke sumber (transkrip/catatan), dengan batas anggaran
permintaan harian yang jujur — bila kunci AI tidak terpasang atau anggaran
habis, panel menyampaikan keterbatasannya dan menyarankan mencoba lagi, tidak
mengarang jawaban.

Pendekatan yang ditegakkan di seluruh kode: **setiap keluaran harus punya
rujukan sumber, persetujuan manusia mengikat versi rencana lewat hash, dan
aksi eksekusi berjalan dalam mode SIMULASI** (lihat §5).

## 2. Isi paket

| Berkas/folder | Isi |
|---|---|
| `app_server.py` | Server utama (pustaka bawaan Python, tanpa framework): mode web publik + panel pemilik, API transkrip, API AI (Teman Paham), halaman hasil A–D |
| `gate.py` | Gerbang eksekusi: validasi rencana, hash persetujuan, batas peran, eksekusi ke adaptor simulasi |
| `approval_server.py` | Layar persetujuan satu halaman (localhost saja) yang meneruskan keputusan manusia ke gerbang |
| `planner.py` | Pengubah catatan menjadi rencana JSON: `StubPlanner` (lokal, tanpa jaringan) dan `LLMPlanner` (endpoint kompatibel OpenAI) |
| `koreksi.py` | Koreksi transkrip dengan riwayat; transkrip asli tidak pernah ditimpa |
| `adapters.py` | Adaptor aksi (email/kalender/tugas) — mode simulasi menulis ke `mock_outbox/` |
| `static/aplikasi.html` + `static/aset/` | Antarmuka web (satu berkas, tanpa build step) |
| `requirements.txt` | Kosong dengan sengaja — seluruh aplikasi memakai pustaka bawaan Python |
| `.env.example` | Contoh variabel lingkungan tanpa nilai rahasia |
| `BAHAN-DEMO/bahan-rapat-demo.md` | Materi rapat **sintetis** untuk mencoba alur produk |
| `README-DEPLOY.md` | Dokumen penerapan mode web (rujukan rute & batas) |

**Yang tidak disertakan dari workspace sumber** (dan alasannya):

- `data/meetings/`, `data/sources/` — data pemakaian nyata; tidak diizinkan
  masuk paket publik. Gunakan bahan demo sintetis di `BAHAN-DEMO/`.
- `PERINTAH-START.txt` — catatan start produksi internal; tidak ada nilai
  rahasia di dalamnya, tetapi memuat ID aplikasi platform dan prosedur
  penerapan internal yang tidak relevan untuk publik. Instruksi ekuivalen
  ada di §3 di bawah.
- `plans_src/` — skenario uji internal.

## 3. Cara menjalankan lokal

Prasyarat: Python 3.12+ (dikembangkan dengan Python 3.14). Tidak ada
dependensi pihak ketiga — `pip install` tidak diperlukan.

```bash
# 1. Salin contoh konfigurasi dan isi nilai yang wajib
cp .env.example .env
#    - CATATAN_MODE=web (atau hapus untuk mode lokal)
#    - CATATAN_RAHASIA=<string acak panjang>
#    - CATATAN_OWNER_SANDI=<sandi pemilik>  (atau CATATAN_OWNER_SANDI_SHA256)

# 2. Muat variabel (contoh bash):
export $(grep -v '^#' .env | xargs)

# 3. Jalankan server:
python app_server.py
```

Tanpa `CATATAN_RAHASIA` atau tanpa sandi pemilik, server **menolak start**
(gagal tertutup) — tidak ada nilai bawaan yang lemah. Ini perilaku yang
disengaja, verifikasi di `app_server.py`.

Di mode lokal (tanpa `CATATAN_MODE=web`) server mengikat `127.0.0.1` dan
membuka browser otomatis (matikan dengan `CATATAN_TANPA_BROWSER=1`).

Rute utama mode web:

| Alamat | Siapa | Isi |
|---|---|---|
| `/` | publik | daftar acara bertanda `publik: true` |
| `/meeting/<id>` | publik | catatan A–D, salin, unduh, cetak |
| `/masuk` / `/keluar` | pemilik | sandi → cookie HMAC bertanda tangan, 7 hari |
| `/sehat` | siapa saja | `{"ok":true,"mode":"web","versi":"…"}` |
| `/panel`, `/unggah`, `/proses`, `/tanya`, `/audit`, `/plans`, `/approvals`, `/sumber` | pemilik | pengelolaan |

Semua POST dari pembaca publik dijawab **403 JSON**, bukan HTML.

## 4. Konfigurasi wajib dan opsional

Lihat `.env.example` (disusun dari variabel yang benar-benar dibaca kode).
Ringkas:

- **Wajib mode web:** `CATATAN_MODE=web`, `CATATAN_RAHASIA`, dan
  `CATATAN_OWNER_SANDI` **atau** `CATATAN_OWNER_SANDI_SHA256`.
- **Kunci AI** (transkripsi audio + Teman Paham): cara utama memasangnya
  lewat halaman `/panel` setelah server berjalan (tersimpan di toko runtime
  `data-rw/`, di luar paket deploy, tidak pernah masuk repo/log). Fallback:
  env `CATATAN_AI_KEY` (endpoint kompatibel OpenAI; `CATATAN_AI_BASE`,
  `CATATAN_AI_MODEL` opsional).
- **Anggaran harian AI:** `CATATAN_AI_HARIAN` (bawaan aman 200 permintaan/hari;
  0 = tanpa batas, hanya pemakaian pribadi).
- **Pengizin LLM planner:** `CATATAN_MUROJAAH_IZINKAN_LLM=1` diperlukan
  eksplisit sebelum planner boleh memanggil model sungguhan; tanpa itu
  `StubPlanner` lokal dipakai.

## 5. Apa yang bisa diuji tanpa kredensial vs yang butuh layanan

**Bisa diuji tanpa kredensial apa pun:**

- Server start dan seluruh halaman publik (beranda, daftar acara, halaman
  hasil A–D, salin/unduh/cetak, `/sehat`).
- Alur masuk pemilik (sandi + cookie HMAC) dan seluruh panel pengelolaan.
- Alur **planner → persetujuan → eksekusi** memakai `StubPlanner` dan adaptor
  simulasi: layar persetujuan (`approval_server.py`, hanya `127.0.0.1`),
  pengikatan hash rencana, penolakan aksi tanpa info wajib, eksekusi sekali,
  catatan keputusan — semuanya lokal, tanpa jaringan keluar.
- Koreksi transkrip (`koreksi.py`): aturan riwayat + rujukan paragraf.
- Tugas sengaja tidak lengkap di bahan demo akan ditolak/ditandai oleh
  gerbang — ini perilaku produk, bukan bug (lihat `gate.py` aturan 9).

**Butuh layanan/model eksternal (kunci AI di server):**

- `POST /api/transkrip` — meneruskan potongan audio (2–120 detik per potongan,
  maks 8 MB, 40 potongan/sesi + anggaran harian bersama) ke layanan AI.
  Tanpa kunci yang sah, tiap potongan **gagal terbuka** (bukan diam-diam
  kosong).
- Panel **Teman Paham** (`tugas:"tanya"` → `POST /api/ai`) — jawaban bebas
  dengan rujukan; tanpa kunci/anggaran, panel menulis pesan jujur dan menyarankan
  mencoba lagi.
- `LLMPlanner` (opsional) — hanya bila `CATATAN_MUROJAAH_IZINKAN_LLM=1` dan
  `TUNTAS_LLM_*` diisi.

**Cara penyusunan keluaran A–D yang dipakai build ini:** penulisan catatan
berjalan lewat percakapan asisten (alur "satu langkah tempel" di panel
pemilik: unduh berkas permintaan → tempel ke percakapan → tempel kembali
jawaban JSON). Ini dinyatakan jujur di UI-nya sendiri: bukan panggilan API
otomatis penuh.

## 6. Simulasi vs layanan nyata (jujur)

- **Persetujuan + eksekusi tindakan: SIMULASI.** Adaptor menulis bukti
  eksekusi ke folder `mock_outbox/` (berkas JSON lokal). Tidak ada email,
  kalender, atau tugas yang benar-benar dikirim/dibuat. Ini disengaja supaya
  penilaian aman dijalankan siapa pun.
- **Pengiriman email/kalender nyata: TIDAK ADA** di paket ini.
- **Transkripsi & tanya-jawab: layanan nyata** — bergantung kunci AI di
  server; tanpa kunci, fitur gagal terbuka dengan pesan jelas.
- **Penyimpanan:** berkas JSON/Markdown di dalam paket (mode web menulis ke
  `data-rw/`). Deploy ulang dari sumber dapat menghilangkan perubahan pemilik
  di dalam paket.

## 7. Data demo

Paket ini **tidak memuat data pengguna nyata**. Untuk mencoba alur lengkap,
gunakan materi rapat sintetis di **`BAHAN-DEMO/bahan-rapat-demo.md`**
(berlabel "Data demonstrasi sintetis"; rapat kerja fiktif dengan keputusan,
tugas ber-PIC, dan satu tugas sengaja belum lengkap). Muat sebagai transkrip
sumber melalui panel pemilik (`/unggah`), atau tempel ke alur pemrosesan.

## 8. Ringkasan pengujian

- **Regresi final: 15/18 `exit=0`.** Tiga kegagalan terdiagnosis sebagai
  **fixture uji yang hilang** (bukan cacat produk), telah dipulihkan dan
  diulang lewat run susulan. Sumber bukti: folder `evidence/` workspace
  (tidak ikut paket kode; rujukan: `evidence/RUN-20261106-0322-jalankan_regresi_final-regresi-final/RINGKASAN.md`).
  Contoh cakupan: unit baterai 233/233, sesi panjang 52/52, migrasi skema
  12/12, alur baru Chrome+Edge 150/150, dan lainnya per tabel regresi.
- **Uji internal berlabel UJI INTERNAL, 0 kasus resmi** — dataset resmi dari
  panitia belum diterima pada saat pengumpulan. Tidak ada klaim akurasi
  terhadap dataset resmi.
- Semua angka di dokumen ini diambil dari catatan regresi yang ada; tidak ada
  angka lain yang dikarang.

## 9. Keterbatasan saat ini (jujur)

Dari catatan serah terima internal (Direktif #16 §5):

1. **HP fisik belum diuji.** Semua uji layar memakai Chrome/Edge headless
   dengan mikrofon palsu dan viewport 390×844.
2. **Catatan akhir bukan salinan verbatim transkrip.** Pada fixture 100 menit,
   transkrip 30/30 tersambung, tetapi kalimat penanda muncul 0/30 persis di
   catatan karena model menyusun ulang kalimat. Belum diperbaiki.
3. **Dua kemunculan angka hilang** pada bahan 12 menit (112/114 ≈ 98,2%):
   kata angka "dua belas" dan "tiga puluh satu" masing-masing 2/3. Status
   BELUM SELESAI untuk dua kasus itu — tidak dikarang.
4. **Detektor hening NONAKTIF:** `uji_hening.py` 4/6 pada deret sintetis
   (suara pelan dari kejauhan dinilai hening); karena itu berhenti-otomatis
   5 menit tetap dimatikan.
5. **Tab latar sungguhan tidak terukur** di Chrome headless
   (`visibilityState` tetap `visible`); yang terbukti hanya penangan kejadian
   yang disuntikkan, bukan penangguhan timer sungguhan.
6. Perubahan data pemilik di dalam paket dapat hilang pada deploy ulang dari
   sumber (penyimpanan berbasis berkas).

## 10. Catatan keamanan paket

- Paket telah dipindai pola rahasia (API key, token, bearer, password,
  cookie, kredensial, email pribadi, IP privat): **bersih**.
- Tidak ada kunci, sandi, atau berkas `.env` berisi nilai asli di paket.
  `.gitignore` mengecualikan `.env`, `.env.*`, `__pycache__/`, dan berkas
  log/bootstrap lokal.
- Alamat email di `planner.py` adalah contoh sintetis (domain `contoh.id`).
- Bila Anda meng-clone repo ini: buat `.env` dari `.env.example`, isi nilai
  sendiri, dan jangan pernah meng-commit `.env` berisi nilai asli.

## 11. Lisensi

Keputusan lisensi open source adalah hak pemilik proyek. Lisensi **sengaja
belum ditempatkan** di paket ini.

## Konfigurasi layanan AI — teruji pada uji paket bersih (6 Nov 2026)

Uji alur dari hasil ekstraksi ZIP ini (7/7 lulus: bahan → Buat Catatan →
catatan terbuka → muat ulang) berhasil dengan konfigurasi berikut:

1. **Kunci layanan AI** dipasang oleh pengelola lewat halaman `/panel`
   (form "Kunci" → `POST /panel/kunci`). Kunci diverifikasi ke provider saat
   dipasang dan disimpan di toko runtime server (`data-rw/`, izin 0600),
   tidak pernah masuk repo/log/URL. Alternatif env `CATATAN_AI_KEY` hanya
   fallback platform; jalur panel adalah yang teruji.
2. **ID model** wajib diset lewat `/panel` → form "ID model" (`POST /panel/konfig`)
   dengan bentuk `provider/nama-model` yang DITERIMA provider untuk kunci Anda
   (cek daftar model di dashboard provider). Bila model bawaan/bentuk salah,
   server mengembalikan galat 400 yang jelas ("Invalid model name") — aplikasi
   tetap menyimpan bahan dan menampilkan pesan jujur.
3. Tanpa kunci: aplikasi tetap berjalan — bahan tersimpan lokal, dan semua
   pembuatan hasil memberi pesan "layanan AI belum siap" tanpa mengarang isi.

Tidak ada kredensial dalam paket ini.

## Konfigurasi layanan AI — teruji pada uji paket bersih (6 Nov 2026)

Uji alur dari hasil ekstraksi ZIP ini (7/7 lulus: bahan → Buat Catatan →
catatan terbuka → muat ulang) berhasil dengan konfigurasi berikut:

1. **Kunci layanan AI** dipasang oleh pengelola lewat halaman `/panel`
   (form "Kunci" → `POST /panel/kunci`). Kunci diverifikasi ke provider saat
   dipasang dan disimpan di toko runtime server (`data-rw/`, izin 0600),
   tidak pernah masuk repo/log/URL. Alternatif env `CATATAN_AI_KEY` hanya
   fallback platform; jalur panel adalah yang teruji.
2. **ID model** wajib diset lewat `/panel` → form "ID model" (`POST /panel/konfig`)
   dengan bentuk `provider/nama-model` yang DITERIMA provider untuk kunci Anda
   (cek daftar model di dashboard provider). Bila model bawaan/bentuk salah,
   server mengembalikan galat 400 yang jelas ("Invalid model name") — aplikasi
   tetap menyimpan bahan dan menampilkan pesan jujur.
3. Tanpa kunci: aplikasi tetap berjalan — bahan tersimpan lokal, dan semua
   pembuatan hasil memberi pesan "layanan AI belum siap" tanpa mengarang isi.

Tidak ada kredensial dalam paket ini.
