# CATATAN MUROJAAH — paket web

Versi baca-saja untuk dibagikan lewat tautan. Pembaca tidak perlu akun dan tidak
ada kunci di URL. Mengubah catatan hanya bisa dilakukan pemilik yang masuk.

## Menjalankan

```bash
export CATATAN_MODE=web
export CATATAN_RAHASIA=<string acak panjang>       # kunci tanda tangan cookie
export CATATAN_OWNER_SANDI=<sandi pemilik>          # atau CATATAN_OWNER_SANDI_SHA256
export PORT=8080                                    # platform biasanya mengisi ini
python app_server.py
```

Tanpa `CATATAN_RAHASIA` atau tanpa sandi pemilik, server **menolak start**
(gagal tertutup) — tidak ada nilai bawaan yang lemah.

## Halaman

| Alamat | Siapa | Isi |
|---|---|---|
| `/` | publik | daftar acara yang bertanda `publik: true` |
| `/meeting/<id>` | publik | catatan A–D, salin, unduh, cetak |
| `/masuk` | pemilik | form sandi; cookie bertanda tangan HMAC, 7 hari |
| `/keluar` | pemilik | hapus cookie |
| `/sehat` | siapa saja | `{"ok":true,"mode":"web","versi":"…"}` |

Rute pengelolaan (`/audit`, `/plans`, `/approvals`, `/sumber`, `/unggah`,
`/proses`, `/tanya`) hanya untuk pemilik. POST dari pembaca publik dijawab
**403 JSON**, bukan HTML.

## Batas yang jujur

- **Transkripsi audio tersedia, tetapi bergantung pada kunci AI di server.**
  `POST /api/transkrip` terbuka di mode web dan meneruskan satu potongan audio
  ke layanan AI. Tanpa kunci AI yang sah di lingkungan server, setiap potongan
  akan gagal (bukan diam-diam kosong). Batas yang berlaku, diukur dari kode:
  satu potongan **2–120 detik** (klien mengirim per 90 detik) dan maksimal
  **8 MB**; **40 potongan / 10 menit** per sesi, ditambah anggaran harian
  bersama. Hasilnya **mentah** — bisa keliru, jadi diperlakukan sebagai bahan
  yang harus diperiksa, bukan catatan jadi. Bukti endpoint hidup: `POST {}` ke
  versi terbit dibalas **400 JSON** `{"kode":"format"}`, bukan 404/HTML.
- **Pertanyaan bebas tersambung ke model, dengan batas anggaran.** Panel
  mengirim `tugas:"tanya"` ke `/api/ai`; bila kunci AI tidak ada atau anggaran
  harian habis, panel menulis pesan jujur dan menyarankan mencoba lagi — ia
  tidak mengarang jawaban.
- **Penyimpanan** memakai berkas JSON/Markdown di dalam paket. Perubahan yang
  dibuat pemilik hilang bila paket di-deploy ulang dari sumber (lihat laporan).
- Eksekusi tindakan tetap berlabel **SIMULASI**; tidak ada pengiriman nyata.
