# BAHAN RAPAT DEMO — Catatan Murojaah

> **Data demonstrasi sintetis.** Seluruh isi berkas ini fiktif dan dibuat
> khusus sebagai bahan uji/presentasi produk CATATAN MUROJAAH. Nama orang,
> perusahaan, angka, dan peristiwa tidak merujuk pada siapa pun yang nyata.
> Jangan memakai berkas ini sebagai data kerja sungguhan.

---

## Profil acara (untuk diisi saat memuat ke aplikasi)

- Judul: Rapat Koordinasi Peluncuran Fitur Penjadwalan — Produk Kita Jaya (fiktif)
- Jenis: rapat kerja
- Tanggal: 3 November 2026, 09.30–10.40 WIB
- Pemateri/pemimpin rapat: Ibu Ratna (Manajer Produk)
- Peserta: Dewa (Frontend), Sari (Backend), Bayu (QA), Rani (Desain), Fajar (Ops)

---

## Transkrip (teks materi, gaya verbatim yang sudah dirapikan)

**Ibu Ratna:** Selamat pagi semua. Kita bertemu hari ini untuk tiga hal: menutup
keputusan soal tanggal rilis fitur penjadwalan, membagi tugas persiapan uji
penerimaan, dan menegaskan siapa yang mengerjakan apa sampai tenggat Jumat
depan. Saya minta semuanya dicatat, karena hasil rapat ini akan dibagikan ke
tim yang tidak hadir. Dimulai dari laporan singkat masing-masing, lalu keputusan,
lalu pembagian tugas.

**Dewa:** Baik. Dari sisi frontend, halaman kalender sudah selesai sepuluh dari
dua belas keadaan. Yang tersisa: keadaan jaringan lambat saat menyimpan, dan
keadaan dua pengguna menyunting slot yang sama. Untuk yang kedua, kami menunggu
sinyal konflik dari backend. Perkiraan saya selesai dalam dua hari kerja kalau
API-nya sudah siap Senin.

**Sari:** Dari backend, endpoint slot sudah hidup di lingkungan staging dan
menjawab dalam rata-rata dua ratus milidetik. Untuk sinyal konflik, saya
merencanakan menambahkan field `revision` pada respons. Kalau `revision` yang
dikirim klien tidak sama dengan yang tersimpan, server menjawab empat ratus
sembilan dengan isi slot terbaru. Rancangannya sudah saya tulis di halaman
dokumentasi internal, bagian tiga. Saya butuh satu hari untuk implementasi dan
satu hari untuk uji sendiri. Target selesai Selasa sore.

**Bayu:** Dari QA, skenario uji penerimaan sudah ada tiga belas kasus dari
target dua puluh. Kasus yang belum: kasus jaringan lambat, kasus konflik
penyuntingan, dan empat kasus aksesibilitas. Saya butuh daftar final perilaku
konflik dari Sari supaya kasusnya tidak perlu ditulis ulang. Kalau daftarnya
turun Selasa, saya selesai menulis semua kasus Rabu malam.

**Rani:** Dari desain, semua aset sudah diserahkan ke Dewa, termasuk keadaan
kosong dan keadaan galat. Satu catatan: teks pada tombol konfirmasi ulang
saya ubah dari "Coba Lagi" menjadi "Muat Ulang Jadwal" supaya tidak rancu dengan
tombol galat jaringan. Perubahan itu sudah dikabarkan ke Dewa lewat pesan,
mohon dicatat di catatan rapat supaya resmi.

**Fajar:** Dari ops, lingkungan uji penerimaan sudah siap dan datanya bisa
direset sepihak dengan satu perintah. Kalimat penting: lingkungan uji ini
memakai data palsu, jadi silakan dipakai bebas tanpa takut merusak apa pun.
Yang saya butuhkan adalah jadwal penggalian versi, supaya saya bisa menyiapkan
paket rilis dan catatan rilisnya. Satu lagi: kutu kecil soal zona waktu di
log lingkungan uji sudah saya betulkan pagi ini, jadi stempel waktu di berkas
hasil sekarang konsisten WIB. Kalau ada yang menemukan stempel waktu aneh di
hasil sebelum Rabu, itu bekas kutu tadi, silakan jalankan ulang kasusnya.

**Ibu Ratna:** Itu catatan yang bagus, Fajar. Mohon ditulis di kanal tim juga,
bukan hanya di sini, supaya Bayu yang menjalankan kasus Rabu tidak salah baca
hasil lamanya.

**Ibu Ratna:** Terima kasih. Sekarang bagian keputusan. Keputusan pertama:
tanggal rilis fitur penjadwalan kami tetapkan **Senin, 16 November 2026**.
Alasannya: memberi jarak lima hari kerja setelah tenggat persiapan uji hari
Jumat ini, jadi ada ruang perbaikan tanpa menggeser tanggal. Keputusan ini
final; kalau nanti ada temuan blokir dari QA, saya yang putuskan apakah rilis
digeser, bukan tiap tim memutuskan sendiri.

**Ibu Ratna:** Keputusan kedua: perilaku konflik penyuntingan mengikuti rancangan
Sari, yaitu pembanding `revision` dengan jawaban empat ratus sembilan. Dewa
wajib menunggu bentuk final API dari Sari sebelum menulis sisa dua keadaan
frontend, supaya tidak ada pekerjaan dibuang.

**Ibu Ratna:** Keputusan ketua: untuk rilis perdana, fitur ekspor ke berkas
lembar kerja **ditunda** ke siklus berikutnya. Saya tahu beberapa dari kalian
bertanya. Alasannya sederhana: dua keadaan frontend yang belum selesai lebih
penting daripada ekspor, dan saya tidak mau membagi perhatian tim di minggu
uji penerimaan. Ekspor masuk kembali ke percakapan perencanaan bulan depan.

**Ibu Ratna:** Keputusan keempat: seluruh uji penerimaan wajib dijalankan di
lingkungan uji Fajar, bukan di komputer pribadi, supaya hasilnya bisa
direproduksi. Ini berlaku mulai kasus pertama, bukan hanya kasus terakhir.

**Sari:** Setuju dengan keputusan kedua. Satu permintaan ke Dewa: jangan hardcode
angka empat ratus sembilan di banyak tempat; buat satu pembantu kecil di satu
berkas, supaya kalau nanti kita menambah perilaku lain, tempatnya satu.

**Dewa:** Bisa. Saya taruh di berkas util yang sudah ada, dan saya sebut di
catatan permintaan tarik nanti bahwa asal keputusannya rapat ini, paragraf
keputusan kedua.

**Ibu Ratna:** Bagus, itu persis budaya yang saya mau: setiap perubahan bisa
ditelusuri ke keputusan. Lanjut ke bagian pembagian tugas.

**Ibu Ratna:** Pertama, Sari menyelesaikan sinyal konflik dengan field
`revision` di lingkungan staging, selesai **Selasa, 10 November 2026, pukul
17.00 WIB**. Hasilnya berupa dokumentasi singkat: satu halaman berisi bentuk
permintaan, bentuk jawaban, dan dua contoh panggilan. Halaman itu dikirim ke
Dewa dan Bayu di kanal tim.

**Ibu Ratna:** Kedua, Dewa menyelesaikan dua keadaan frontend yang tersisa —
jaringan lambat dan konflik penyuntingan — selesai **Kamis, 12 November 2026,
pukul 12.00 WIB**. Keadaan konflik baru boleh ditulis setelah dokumentasi API
dari Sari diterima. Kalau dokumentasinya molor, Dewa wajib mengabarkan ke saya
paling lambat Rabu pagi, bukan menunggu tenggat.

**Ibu Ratna:** Ketiga, Bayu menyelesaikan dua puluh kasus uji penerimaan, semua
sudah dijalankan sekali di lingkungan uji, selesai **Kamis, 12 November 2026,
pukul 17.00 WIB**. Catat satu per satu hasilnya: lulus, gagal, atau diblokir.
Kasus yang diblokir wajib ada alasannya.

**Ibu Ratna:** Keempat, Fajar menyiapkan paket rilis untuk tanggal target,
termasuk catatan rilis dan langkah penggalian balik, selesai **Jumat, 13
November 2026, pukul 15.00 WIB**. Langkah penggalian balik wajib tertulis,
walaupun kita tidak berencana memakainya.

**Ibu Ratna:** Kelima, untuk penyusunan materi pelatihan pengguna... Sari, kamu
yang biasanya pegang materi pemakaian, tapi minggu ini kamu penuh. Saya belum
memastikan siapa yang mengambil tugas ini, dan sampai hari ini saya juga belum
dengar konfirmasi tenggatnya dari atasan langsung terkait jadwal pelatihan.
Kita jadikan tugas ini terbuka; saya yang kejar keputusannya di luar rapat ini.
Catat saja begitu: pemilik dan tenggatnya belum ada, jangan dikarang.

**Bayu:** Ibu, satu konfirmasi. Untuk dua puluh kasus tadi, kalau saya menemukan
galat berat di lingkungan uji, prosedurnya tetap seperti biasa — hentikan,
catat, kabari kanal?

**Ibu Ratna:** Betul, tetap seperti biasa. Jangan memperbaiki apa pun di
lingkungan uji; itu tugas Fajar bersama pemilik galatnya.

**Rani:** Apa perubahan teks tombol "Muat Ulang Jadwal" tadi sudah cukup
dicatat? Kalau perlu, saya kirim tangkapan layar perbandingannya ke kanal tim
sekalian sebagai lampiran.

**Ibu Ratna:** Cukup dicatat di sini; tangkapan layar boleh dikirim sebagai
kelengkapan, bukan pengganti catatan. Satu hal lagi sebelum kita tutup: semua
tugas yang saya sebut tadi wajib punya rujukan ke bagian rapat ini, supaya
kelak kalau ada yang bertanya "aturan ini dari mana", jawabannya bisa
ditunjuk, bukan ditebak. Baik, rapat saya tutup pukul 10.40. Terima kasih
semuanya.

---

## Daftar isyarat untuk menguji aplikasi (petunjuk penguji, bukan bagian transkrip)

1. **Keputusan ber-tanggal** ada empat (rilis 16 Nov; perilaku konflik pakai
   `revision`; ekspor ditunda; uji di lingkungan Fajar) — layak muncul di
   Rangkuman dan Catatan Lengkap dengan rujukan paragraf.
2. **Tugas jelas ber-PIC dan tenggat** ada empat (Sari, Dewa, Bayu, Fajar) —
   layak muncul di Tugas & Komitmen.
3. **Satu tugas sengaja belum lengkap** (materi pelatihan: pemilik dan tenggat
   tidak disebut) — aplikasi seharusnya **menandai perlu klarifikasi**, bukan
   mengarang PIC atau tanggal.
4. **Perubahan keputusan di dalam kalimat** ("Coba Lagi" → "Muat Ulang Jadwal")
   — uji ketelitian rujukan sumber.
5. **Ketentuan prosedural** (hentikan-catat-kabari; jangan memperbaiki di
   lingkungan uji) — uji kemampuan menangkap aturan, bukan hanya tugas.

*Akhir bahan demo sintetis.*
