"""TUNTAS — notulen lengkap dari SELURUH transkrip.

Beda dengan `notulen.py` (yang menyusun notulen dari daftar aksi), modul ini
menelusuri **setiap paragraf transkrip** dan memastikan tidak ada yang hilang:

· Paragraf substantif SELALU muncul, termasuk yang tidak menghasilkan tugas.
  Kalau rencana tidak punya butir untuk paragraf itu, isinya tetap ditampilkan
  apa adanya dan ditandai `belum diringkas` — bukan dibuang.
· Paragraf yang memang bukan bahasan (pembukaan, penutupan, keterangan hadir)
  dicatat di bagian tersendiri **beserta alasannya**.
· Paragraf yang sengaja tidak dipakai (mis. berisi instruksi tersisip) dicatat
  dengan alasan dari rencana.
· Tambahan dari agen (hitungan cakupan, cap waktu, catatan) ditaruh di bagian
  berlabel "Catatan agen" supaya tidak tertukar dengan isi rapat.

Transkrip tidak diubah. Modul ini hanya membaca dan mencatat sha256-nya.

Contoh:
    python notulen_lengkap.py --transkrip audio/kopdar-1/transkrip-paragraf.md \\
        --sumber data/sources/kopdar-1.md --plan plans_src/kopdar-1.plan.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Paragraf yang bukan bahasan rapat. Setiap aturan membawa ALASAN yang dicetak,
# supaya pembaca bisa menilai sendiri apakah penggolongan ini masuk akal.
BUKAN_BAHASAN = [
    (re.compile(r"\b(membuka|memulai)\s+rapat\b|\brapat\s+(dibuka|dimulai)\b", re.I),
     "pembukaan rapat"),
    (re.compile(r"\b(menutup|mengakhiri)\s+rapat\b|\brapat\s+(ditutup|selesai|berakhir)\b", re.I),
     "penutupan rapat"),
    (re.compile(r"\b(tidak\s+hadir|tidak\s+ada\s+laporan)\b", re.I),
     "keterangan kehadiran tanpa isi bahasan"),
]

SIFAT_URUT = ["keputusan", "penugasan", "laporan", "usulan", "pembahasan", "pertanyaan"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baca_paragraf(path: Path) -> dict[int, str]:
    """Baca format `¶N — isi` (sama dengan yang dipakai wb_planner)."""
    teks = path.read_text(encoding="utf-8")
    bagian = re.split(r"^¶(\d+)\s*[—-]\s*", teks, flags=re.M)
    out: dict[int, str] = {}
    for i in range(1, len(bagian) - 1, 2):
        out[int(bagian[i])] = " ".join(bagian[i + 1].split())
    return out


def cap_waktu(transkrip_paragraf: Path) -> dict[int, tuple[float, float]]:
    """Ambil cap waktu paragraf dari JSON segmen, bila ada.

    Paragraf di `transkrip-paragraf.md` disusun dari segmen bernomor; berkas
    `transkrip-segmen.json` menyimpan detik mulai/selesai tiap segmen.
    """
    json_segmen = transkrip_paragraf.parent / "transkrip-segmen.json"
    if not json_segmen.exists():
        return {}
    data = json.loads(json_segmen.read_text(encoding="utf-8"))
    return {s["no"]: (s["mulai"], s["selesai"]) for s in data.get("segmen") or []}


def fmt(detik: float) -> str:
    j = int(detik // 3600)
    m = int((detik % 3600) // 60)
    s = detik % 60
    return f"{j:02d}:{m:02d}:{s:06.3f}"


def alasan_bukan_bahasan(teks: str) -> str | None:
    for pola, alasan in BUKAN_BAHASAN:
        if pola.search(teks):
            return alasan
    return None


def susun(
    *,
    nama: str,
    paragraf: dict[int, str],
    sumber: Path | None,
    plan: dict | None,
    cap: dict[int, tuple[float, float]],
    meta_audio: dict | None,
) -> tuple[str, dict]:
    items = (plan or {}).get("items") or []
    aksi = (plan or {}).get("actions") or []
    diabaikan = {d["paragraf"]: d.get("alasan", "") for d in (plan or {}).get("diabaikan") or []}

    item_per: dict[int, list[dict]] = {}
    for x in items:
        item_per.setdefault(x["paragraf"], []).append(x)
    aksi_per: dict[int, list[dict]] = {}
    for a in aksi:
        aksi_per.setdefault(a["source_paragraf"], []).append(a)

    substantif: list[int] = []
    bukan: list[tuple[int, str]] = []
    for no in sorted(paragraf):
        if no in diabaikan:
            continue
        alasan = alasan_bukan_bahasan(paragraf[no])
        if alasan:
            bukan.append((no, alasan))
        else:
            substantif.append(no)

    tanpa_butir = [no for no in substantif if no not in item_per]

    baris: list[str] = []
    baris.append(f"# Notulen lengkap — {nama}")
    baris.append("")
    baris.append("> Disusun dari SELURUH paragraf transkrip, bukan dari daftar tugas.")
    baris.append("> Paragraf yang tidak menghasilkan tugas tetap dimuat.")
    baris.append("")

    baris.append("## Kepala")
    baris.append("")
    if sumber:
        baris.append(f"- Berkas sumber: `{sumber.as_posix().split('/tuntas/')[-1]}` (tidak diubah)")
        baris.append(f"- SHA-256 sumber: `{sha256(sumber)}`")
    if meta_audio:
        baris.append(f"- Audio asli: `{meta_audio.get('audio_asli')}` "
                     f"· durasi {meta_audio.get('durasi_detik', 0) / 60:.1f} menit")
        baris.append(f"- SHA-256 audio: `{meta_audio.get('audio_sha256')}`")
        baris.append(f"- Transkripsi: faster-whisper `{meta_audio.get('model')}` "
                     f"(int8, CPU), bahasa `{meta_audio.get('bahasa_terdeteksi')}` "
                     f"({meta_audio.get('probabilitas_bahasa')})")
        baris.append(f"- Segmen tidak jelas: {meta_audio.get('segmen_tidak_jelas', 0)} "
                     f"dari {meta_audio.get('jumlah_segmen', 0)} "
                     f"(ditandai `[tidak jelas]` di transkrip)")
    baris.append(f"- Paragraf di transkrip: {len(paragraf)} "
                 f"· substantif: {len(substantif)} · bukan bahasan: {len(bukan)} "
                 f"· sengaja tidak dipakai: {len(diabaikan)}")
    baris.append(f"- Butir rencana: {len(items)} · aksi: {len(aksi)}")
    baris.append(f"- Paragraf substantif tanpa butir rencana: {len(tanpa_butir)}")
    baris.append("")

    # ---- Pembahasan lengkap, paragraf demi paragraf -------------------------
    baris.append("## Pembahasan lengkap")
    baris.append("")
    baris.append("> Urut menurut paragraf. Kutipan ditulis apa adanya dari transkrip.")
    baris.append("")
    for no in substantif:
        teks = paragraf[no]
        cap_teks = ""
        if no in cap:
            cap_teks = f" · {fmt(cap[no][0])}"
        baris.append(f"### ¶{no}{cap_teks}")
        baris.append("")
        daftar_item = item_per.get(no, [])
        if daftar_item:
            for x in daftar_item:
                baris.append(f"- **{x.get('sifat', 'pembahasan')}** — {x.get('ringkas', '')}")
        else:
            baris.append("- **belum diringkas** — tidak ada butir rencana untuk paragraf ini; "
                         "isi dipertahankan apa adanya")
        baris.append("")
        baris.append(f"> “{teks}”")
        baris.append("")
        for a in aksi_per.get(no, []):
            baris.append(f"- → aksi `{a['type']}`: {_ringkas_aksi(a)}")
            baris.extend(_kartu_baris(a))
        if aksi_per.get(no):
            baris.append("")

    # ---- Bagian per jenis, dari butir yang ada ----------------------------
    for sifat in SIFAT_URUT:
        isi = [x for x in items if x.get("sifat") == sifat]
        if not isi:
            continue
        judul = {
            "keputusan": "Keputusan", "penugasan": "Penugasan", "laporan": "Laporan",
            "usulan": "Usulan (belum diputuskan)", "pembahasan": "Pembahasan (ringkas)",
            "pertanyaan": "Pertanyaan",
        }[sifat]
        baris.append(f"## {judul}")
        baris.append("")
        for x in isi:
            baris.append(f"- ¶{x['paragraf']} — {x.get('ringkas', '')}")
        baris.append("")

    terbuka = (plan or {}).get("pertanyaan_terbuka") or []
    if terbuka:
        baris.append("## Pertanyaan terbuka")
        baris.append("")
        for q in terbuka:
            baris.append(f"- ¶{q['paragraf']} — {q['pertanyaan']}")
        baris.append("")

    # ---- Keputusan pengguna, dipisah dari isi rapat ----------------------
    klarifikasi = [(i, a) for i, a in enumerate(aksi) if a.get("catatan_klarifikasi")]
    if klarifikasi:
        dijawab_oleh = (plan or {}).get("dijawab_oleh") or "(tidak dicatat)"
        baris.append("## Keputusan pengguna (BUKAN ucapan rekaman)")
        baris.append("")
        baris.append(f"> Bagian ini berasal dari jawaban manusia — {dijawab_oleh} — dan **bukan**")
        baris.append("> dari transkrip. Jangan membacanya sebagai ucapan peserta rapat.")
        baris.append("")
        for i, a in klarifikasi:
            nama_aksi = a.get("judul") or a.get("title") or a.get("type")
            for c in a["catatan_klarifikasi"]:
                baris.append(f"- aksi #{i} “{nama_aksi}” — {c}")
        baris.append("")

    # ---- Yang tidak masuk, beserta alasan --------------------------------
    if bukan or diabaikan:
        baris.append("## Paragraf yang tidak dimuat sebagai bahasan")
        baris.append("")
        baris.append("| ¶ | alasan |")
        baris.append("|---|---|")
        for no, alasan in bukan:
            baris.append(f"| ¶{no} | {alasan} |")
        for no, alasan in sorted(diabaikan.items()):
            baris.append(f"| ¶{no} | {alasan} |")
        baris.append("")

    # ---- Cakupan --------------------------------------------------------
    baris.append("## Cakupan paragraf")
    baris.append("")
    muncul = set(substantif) | {no for no, _ in bukan} | set(diabaikan)
    hilang = sorted(set(paragraf) - muncul)
    baris.append(f"- Paragraf di transkrip: {len(paragraf)}")
    baris.append(f"- Muncul di notulen: {len(paragraf) - len(hilang)}")
    baris.append(f"- Hilang tanpa alasan: {len(hilang)}"
                 + (f" → {hilang}" if hilang else ""))
    baris.append(f"- Substantif yang belum punya butir rencana: {len(tanpa_butir)}"
                 + (f" → {tanpa_butir}" if tanpa_butir else ""))
    baris.append("")

    # ---- Tambahan agen, diberi label terpisah ---------------------------
    baris.append("## Catatan agen (tambahan, BUKAN isi rapat)")
    baris.append("")
    baris.append("Bagian ini disusun agen, bukan diucapkan di rapat. Dipisahkan supaya")
    baris.append("tidak tertukar dengan isi transkrip.")
    baris.append("")
    baris.append(f"- Cap waktu per paragraf diambil dari segmen mesin pengenal suara; "
                 f"itu perkiraan batas waktu, bukan penanda pembicara.")
    if tanpa_butir:
        baris.append(f"- {len(tanpa_butir)} paragraf substantif belum punya butir rencana "
                     f"({', '.join('¶' + str(n) for n in tanpa_butir)}). Isinya tetap dimuat, "
                     f"tetapi belum diringkas dan belum ada tindakan yang diturunkan.")
    if diabaikan:
        baris.append(f"- {len(diabaikan)} paragraf sengaja tidak dipakai: "
                     + "; ".join(f"¶{n} ({a})" for n, a in sorted(diabaikan.items())))
    if not meta_audio:
        baris.append("- Notulen ini dibaca dari berkas teks; tidak ada audio yang diperiksa.")
    baris.append("")

    baris.append("## Batas")
    baris.append("")
    baris.append("- Transkrip berasal dari mesin pengenal suara otomatis: salah dengar pada")
    baris.append("  nama, angka, dan istilah lokal masih mungkin. Bagian yang keyakinannya")
    baris.append("  rendah sudah ditandai `[tidak jelas]` dan didaftar di `tidak-jelas.json`.")
    baris.append("- Tidak ada penandaan pembicara otomatis (diarisasi).")
    baris.append("- Ringkasan butir rencana disusun model bahasa di percakapan, lalu diperiksa")
    baris.append("  `wb_planner.py`. Kutipan tetap verbatim dari transkrip.")
    baris.append("- Setiap nilai pada kartu tindakan membawa label asalnya: `SUMBER_RAPAT`,")
    baris.append("  `TURUNAN_DENGAN_DASAR`, `USULAN_AGEN`, atau `KONFIRMASI_PENGGUNA`.")
    baris.append("  Yang berlabel `USULAN_AGEN` belum diucapkan siapa pun di rapat.")
    baris.append("")

    cakupan = {
        "paragraf_total": len(paragraf),
        "substantif": len(substantif),
        "bukan_bahasan": len(bukan),
        "sengaja_tidak_dipakai": len(diabaikan),
        "hilang": hilang,
        "substantif_tanpa_butir": tanpa_butir,
        "cakupan_persen": round(
            100.0 * (len(paragraf) - len(hilang)) / len(paragraf), 1) if paragraf else 0.0,
    }
    return "\n".join(baris), cakupan


def _kartu_baris(a: dict) -> list[str]:
    """Rincian kartu tindakan, dengan label asal tiap nilai.

    Label ini sengaja ditulis apa adanya di notulen: pembaca harus bisa melihat
    mana yang diucapkan di rapat dan mana yang diusulkan agen.
    """
    kartu = a.get("kartu") or {}
    out: list[str] = []
    for field, label in (
        ("hasil_diharapkan", "hasil yang diharapkan"),
        ("bukti_penyelesaian", "bukti penyelesaian"),
        ("kanal", "kanal"),
    ):
        isi = kartu.get(field) or {}
        if isi.get("nilai"):
            out.append(f"  - {label} [{isi.get('asal', '?')}]: {isi['nilai']}")
    for x in kartu.get("perlu_konfirmasi") or []:
        out.append(f"  - perlu dikonfirmasi: {x}")
    return out


def _ringkas_aksi(a: dict) -> str:
    if a["type"] == "task":
        return f"tugas “{a.get('judul', '')}” · PIC {a.get('pic') or '—'} · tenggat {a.get('due') or '—'}"
    if a["type"] == "calendar":
        return f"kalender “{a.get('title', '')}” · {a.get('start')} {a.get('timezone')}"
    to = a.get("to") or {}
    return f"email ke {to.get('contact_id') or to.get('nama') or '—'} · “{a.get('subject', '')}”"


def main() -> int:
    p = argparse.ArgumentParser(description="Notulen lengkap dari seluruh transkrip")
    p.add_argument("--transkrip", required=True, help="audio/<nama>/transkrip-paragraf.md")
    p.add_argument("--sumber", default=None, help="data/sources/<nama>.md (opsional)")
    p.add_argument("--plan", default=None, help="plans_src/<nama>.plan.json (opsional)")
    p.add_argument("--out", default=None)
    p.add_argument("--nama", default=None)
    p.add_argument("--blokir-jika-belum-dicakup", action="store_true",
                   help="keluar dengan kode 4 bila ada paragraf substantif tanpa butir rencana")
    a = p.parse_args()

    transkrip = Path(a.transkrip)
    if not transkrip.is_absolute():
        transkrip = ROOT / transkrip
    if not transkrip.exists():
        print(f"Transkrip tidak ditemukan: {transkrip}")
        return 2

    paragraf = baca_paragraf(transkrip)
    if not paragraf:
        print(f"Tidak ada paragraf ¶N di {transkrip}")
        return 2

    if a.nama:
        nama = a.nama
    elif transkrip.parent.name == "sources":
        nama = transkrip.stem
    else:
        nama = transkrip.parent.name

    plan = None
    if a.plan:
        path_plan = Path(a.plan) if Path(a.plan).is_absolute() else ROOT / a.plan
        plan = json.loads(path_plan.read_text(encoding="utf-8"))

    meta_audio = None
    meta_path = transkrip.parent / "meta.json"
    if meta_path.exists():
        meta_audio = json.loads(meta_path.read_text(encoding="utf-8"))

    sumber = None
    if a.sumber:
        sumber = Path(a.sumber) if Path(a.sumber).is_absolute() else ROOT / a.sumber

    isi, cakupan = susun(
        nama=nama, paragraf=paragraf, sumber=sumber if sumber and sumber.exists() else None,
        plan=plan, cap=cap_waktu(transkrip), meta_audio=meta_audio,
    )

    out = Path(a.out) if a.out else ROOT / "notulen" / f"notulen-lengkap-{nama}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(isi, encoding="utf-8")

    print(f"Notulen lengkap: {out}")
    print(f"  paragraf {cakupan['paragraf_total']} · substantif {cakupan['substantif']} "
          f"· bukan bahasan {cakupan['bukan_bahasan']} · tidak dipakai {cakupan['sengaja_tidak_dipakai']}")
    print(f"  hilang tanpa alasan: {len(cakupan['hilang'])} · cakupan {cakupan['cakupan_persen']}%")
    print(f"  substantif tanpa butir rencana: {len(cakupan['substantif_tanpa_butir'])}"
          + (f" → {cakupan['substantif_tanpa_butir']}"
             if cakupan["substantif_tanpa_butir"] else ""))

    if a.blokir_jika_belum_dicakup and cakupan["substantif_tanpa_butir"]:
        print("\n  BLOK: masih ada paragraf substantif tanpa butir rencana.")
        print("  Isi notulen tetap ditulis, tetapi rencana belum dianggap lengkap.")
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
