"""Koreksi transkrip dengan riwayat — transkrip asli tidak pernah ditimpa.

Masalah yang ditutup: transkrip verbatim dari mesin pengenal suara punya salah
dengar pada nama dan istilah asing ("warpadi" untuk WorkBuddy). Tanpa modul ini,
satu-satunya cara membetulkannya adalah menyunting berkas transkrip — dan itu
menghapus bukti apa yang sebenarnya dikatakan.

Aturan yang ditegakkan di sini:

1. **Transkrip asli tidak ditimpa.** Keluaran selalu berkas baru. SHA-256 asli
   dicatat sebelum dan sesudah; kalau berubah, modul gagal.
2. **Setiap koreksi wajib menunjuk paragraf** (`paragraf`), dan boleh menambah
   `timestamp` sebagai bukti kedua. Koreksi tanpa rujukan ditolak.
3. **Teks lama harus benar-benar ada** di paragraf yang ditunjuk. Kalau tidak,
   koreksi ditolak — bukan diterapkan diam-diam.
4. **Pelaku dicatat apa adanya**: `agen` atau `manusia`. Tidak ada nilai bawaan.
   Koreksi agen berstatus `usulan` sampai ada manusia yang memverifikasi. Modul
   ini **tidak** memberi label "koreksi manusia" pada koreksi agen.
5. **Dasar wajib.** Mengganti nama produk karena "kayaknya begitu" bukan dasar.

Berkas koreksi (JSON):

{
  "transkrip": "audio/kopdar-1/transkrip-paragraf.md",
  "koreksi": [
    {"id": "K1", "paragraf": 1, "teks_lama": "warpadi", "teks_baru": "WorkBuddy",
     "alasan": "...", "dasar": "...", "pelaku": "agen",
     "oleh": "WorkBuddy (percakapan)"}
  ]
}

Keluaran:
  transkrip-terkoreksi.md   teks dengan penanda [K1] setelah tiap ganti
  riwayat-koreksi.jsonl     satu baris per koreksi, termasuk yang tidak diterapkan

Contoh:
    python koreksi.py --transkrip audio/kopdar-1/transkrip-paragraf.md \\
        --koreksi data/koreksi-kopdar-1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POLA_BLOK = re.compile(r"^¶(\d+)\s*([—-])\s*", re.M)
PELAKU_SAH = {"agen", "manusia"}
STATUS_SAH = {"usulan", "terverifikasi"}
MIN_DASAR = 12


class KoreksiError(Exception):
    """Berkas koreksi tidak sah. Tidak ada keluaran yang ditulis."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def baca_blok(teks: str) -> tuple[str, list[dict]]:
    """Pecah berkas menjadi kepala + blok paragraf, tanpa mengubah apa pun.

    Batas blok dihitung dari posisi penanda `¶N`, bukan dari hasil normalisasi,
    supaya spasi dan baris baru asli tetap utuh saat ditulis kembali.
    """
    pos = [(m.start(), m.end(), int(m.group(1))) for m in POLA_BLOK.finditer(teks)]
    kepala = teks[: pos[0][0]] if pos else teks
    blok: list[dict] = []
    for i, (mulai, akhir, no) in enumerate(pos):
        selesai = pos[i + 1][0] if i + 1 < len(pos) else len(teks)
        blok.append(
            {"no": no, "awalan": teks[mulai:akhir], "isi": teks[akhir:selesai]}
        )
    return kepala, blok


def _detik(timestamp: str) -> float:
    """`HH:MM:SS.mmm` atau `MM:SS.mmm` → detik."""
    bagian = [float(x) for x in timestamp.strip().split(":")]
    if len(bagian) == 2:
        return bagian[0] * 60 + bagian[1]
    if len(bagian) == 3:
        return bagian[0] * 3600 + bagian[1] * 60 + bagian[2]
    raise ValueError(f"timestamp tidak bisa dibaca: {timestamp!r}")


def _segmen_di(transkrip: Path, detik: float) -> dict | None:
    """Segmen yang mencakup detik itu, bila berkas segmen tersedia."""
    path = transkrip.parent / "transkrip-segmen.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    for s in data.get("segmen") or []:
        if s["mulai"] <= detik <= s["selesai"]:
            return s
    return None


def periksa(transkrip: Path, berkas_koreksi: Path) -> tuple[list[dict], dict]:
    """Validasi seluruh koreksi. Gagal → KoreksiError, tidak ada yang ditulis."""
    data = json.loads(berkas_koreksi.read_text(encoding="utf-8"))
    daftar = data.get("koreksi")
    if not isinstance(daftar, list) or not daftar:
        raise KoreksiError("Berkas koreksi tidak memuat daftar `koreksi`.")

    teks = transkrip.read_text(encoding="utf-8")
    _, blok = baca_blok(teks)
    isi_per = {b["no"]: b["isi"] for b in blok}

    galat: list[str] = []
    hasil: list[dict] = []
    terpakai: set[str] = set()

    for i, k in enumerate(daftar):
        label = k.get("id") or f"#{i}"
        no = k.get("paragraf")
        ts = (k.get("timestamp") or "").strip()
        lama = k.get("teks_lama") or ""
        baru = k.get("teks_baru") or ""
        pelaku = (k.get("pelaku") or "").strip()
        dasar = (k.get("dasar") or "").strip()

        # (2) wajib menunjuk paragraf
        if not isinstance(no, int) or no not in isi_per:
            galat.append(
                f"{label}: tidak menunjuk paragraf yang ada (paragraf={no!r}). "
                "Koreksi tanpa rujukan ditolak."
            )
            continue
        if not lama or not baru:
            galat.append(f"{label}: teks_lama dan teks_baru wajib diisi.")
            continue
        if lama == baru:
            galat.append(f"{label}: teks_lama dan teks_baru sama.")
            continue
        if lama not in isi_per[no]:
            galat.append(
                f"{label}: teks_lama {lama!r} tidak ada di ¶{no}. "
                "Koreksi tidak diterapkan pada teks yang tidak memuatnya."
            )
            continue

        # (4) pelaku wajib, tanpa nilai bawaan
        if pelaku not in PELAKU_SAH:
            galat.append(
                f"{label}: `pelaku` wajib 'agen' atau 'manusia' (dapat {pelaku!r}). "
                "Tidak ada nilai bawaan: koreksi agen bukan koreksi manusia."
            )
            continue

        # (5) dasar wajib
        if len(dasar) < MIN_DASAR:
            galat.append(
                f"{label}: `dasar` terlalu pendek. Mengganti nama tanpa dasar "
                "pemeriksaan hanya dugaan."
            )
            continue

        status = (k.get("status") or "").strip()
        if status and status not in STATUS_SAH:
            galat.append(f"{label}: status {status!r} tidak dikenal.")
            continue
        if not status:
            # Agen: usulan sampai diverifikasi. Manusia: terverifikasi.
            status = "usulan" if pelaku == "agen" else "terverifikasi"
        if pelaku == "agen" and status == "terverifikasi":
            if not (k.get("diverifikasi_oleh") or "").strip():
                galat.append(
                    f"{label}: koreksi agen tidak boleh berstatus terverifikasi "
                    "tanpa `diverifikasi_oleh`."
                )
                continue

        # (2b) timestamp, bila diberikan, harus cocok dengan segmennya
        if ts:
            try:
                detik = _detik(ts)
            except ValueError as e:
                galat.append(f"{label}: {e}")
                continue
            seg = _segmen_di(transkrip, detik)
            if seg is not None and lama.lower() not in (seg.get("teks") or "").lower():
                galat.append(
                    f"{label}: timestamp {ts} menunjuk segmen yang tidak memuat "
                    f"{lama!r}. Rujukan waktu tidak cocok dengan isi."
                )
                continue

        kunci = f"{no}:{lama}"
        if kunci in terpakai:
            galat.append(f"{label}: ¶{no} sudah punya koreksi untuk {lama!r}.")
            continue
        terpakai.add(kunci)

        hasil.append(
            {
                "id": label,
                "paragraf": no,
                "timestamp": ts or None,
                "teks_lama": lama,
                "teks_baru": baru,
                "alasan": k.get("alasan") or "",
                "dasar": dasar,
                "pelaku": pelaku,
                "oleh": (k.get("oleh") or "").strip(),
                "status": status,
                "diverifikasi_oleh": (k.get("diverifikasi_oleh") or "").strip() or None,
            }
        )

    if galat:
        raise KoreksiError("\n".join(galat))
    return hasil, {"kepala": "", "blok": blok, "teks": teks, "catatan": data.get("catatan") or ""}


def terapkan(
    transkrip: Path, berkas_koreksi: Path, out_dir: Path | None = None,
    hanya_terverifikasi: bool = False,
) -> dict:
    sha_sebelum = sha256(transkrip)
    koreksi, konteks = periksa(transkrip, berkas_koreksi)
    teks = konteks["teks"]

    kepala, blok = baca_blok(teks)
    per_paragraf: dict[int, list[dict]] = {}
    for k in koreksi:
        per_paragraf.setdefault(k["paragraf"], []).append(k)

    riwayat: list[dict] = []
    for b in blok:
        isi = b["isi"]
        for k in per_paragraf.get(b["no"], []):
            diterapkan = k["status"] == "terverifikasi" or not hanya_terverifikasi
            jumlah = isi.count(k["teks_lama"]) if diterapkan else 0
            if diterapkan and jumlah:
                isi = isi.replace(
                    k["teks_lama"], f"{k['teks_baru']} [{k['id']}]"
                )
            riwayat.append(
                {
                    **k,
                    "diterapkan": bool(jumlah),
                    "jumlah_ganti": jumlah,
                    "waktu_dicatat": datetime.now().isoformat(timespec="seconds"),
                }
            )
        b["baru"] = isi

    badan = "".join(b["awalan"] + b["baru"] for b in blok)
    keluar = kepala + badan

    usulan = [k for k in riwayat if k["status"] == "usulan"]
    terverif = [k for k in riwayat if k["status"] == "terverifikasi"]
    diterapkan = [k for k in riwayat if k["diterapkan"]]

    judul = [
        f"<!-- transkrip-terkoreksi.md — dibuat oleh koreksi.py, {datetime.now():%Y-%m-%d %H:%M} -->",
        "<!-- Transkrip ASLI tidak diubah. Berkas ini turunan, bukan pengganti. -->",
        f"<!-- sha256 transkrip asli: {sha_sebelum} -->",
        f"<!-- koreksi diterapkan: {len(diterapkan)} "
        f"(terverifikasi manusia {len(terverif)}, usulan agen {len(usulan)}) -->",
    ]
    if usulan:
        judul.append(
            "<!-- PERINGATAN: sebagian teks di bawah adalah USULAN KOREKSI AGEN yang "
            "BELUM diverifikasi manusia. Jangan dibaca sebagai ucapan yang terverifikasi. -->"
        )

    if out_dir is None:
        out_dir = transkrip.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    path_teks = out_dir / "transkrip-terkoreksi.md"
    path_riwayat = out_dir / "riwayat-koreksi.jsonl"

    path_teks.write_text("\n".join(judul) + "\n\n" + keluar, encoding="utf-8")
    with path_riwayat.open("w", encoding="utf-8") as f:
        for k in riwayat:
            f.write(json.dumps({**k, "sha256_transkrip": sha_sebelum},
                               ensure_ascii=False) + "\n")

    sha_sesudah = sha256(transkrip)
    if sha_sesudah != sha_sebelum:
        raise KoreksiError(
            "Transkrip asli berubah saat proses — ini tidak boleh terjadi. "
            f"sebelum={sha_sebelum} sesudah={sha_sesudah}"
        )

    return {
        "transkrip_asli": str(transkrip),
        "sha256_sebelum": sha_sebelum,
        "sha256_sesudah": sha_sesudah,
        "asli_utuh": sha_sesudah == sha_sebelum,
        "keluaran": str(path_teks),
        "riwayat": str(path_riwayat),
        "jumlah_koreksi": len(riwayat),
        "diterapkan": len(diterapkan),
        "terverifikasi_manusia": len(terverif),
        "usulan_agen": len(usulan),
        "hanya_terverifikasi": hanya_terverifikasi,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Koreksi transkrip dengan riwayat")
    p.add_argument("--transkrip", required=True, help="transkrip verbatim (¶N)")
    p.add_argument("--koreksi", required=True, help="berkas JSON daftar koreksi")
    p.add_argument("--out-dir", default=None,
                   help="folder keluaran (bawaan: folder transkrip)")
    p.add_argument("--hanya-terverifikasi", action="store_true",
                   help="terapkan hanya koreksi yang sudah diverifikasi manusia")
    a = p.parse_args()

    transkrip = Path(a.transkrip)
    if not transkrip.is_absolute():
        transkrip = ROOT / transkrip
    berkas = Path(a.koreksi)
    if not berkas.is_absolute():
        berkas = ROOT / berkas
    if not transkrip.exists():
        print(f"Transkrip tidak ditemukan: {transkrip}")
        return 2
    if not berkas.exists():
        print(f"Berkas koreksi tidak ditemukan: {berkas}")
        return 2

    try:
        hasil = terapkan(
            transkrip, berkas,
            Path(a.out_dir) if a.out_dir else None,
            hanya_terverifikasi=a.hanya_terverifikasi,
        )
    except KoreksiError as e:
        print("KOREKSI DITOLAK — tidak ada berkas yang ditulis.")
        for baris in str(e).splitlines():
            print(f"  - {baris}")
        return 4
    except json.JSONDecodeError as e:
        print(f"Berkas koreksi bukan JSON yang sah: {e}")
        return 3

    print(f"Transkrip asli : {hasil['transkrip_asli']}")
    print(f"  sha256       : {hasil['sha256_sebelum']}")
    print(f"  utuh?        : {'ya, tidak berubah' if hasil['asli_utuh'] else 'TIDAK — gagal'}")
    print(f"Koreksi        : {hasil['jumlah_koreksi']} "
          f"(diterapkan {hasil['diterapkan']})")
    print(f"  terverifikasi manusia: {hasil['terverifikasi_manusia']}")
    print(f"  usulan agen (belum diverifikasi): {hasil['usulan_agen']}")
    print(f"Keluaran       : {hasil['keluaran']}")
    print(f"Riwayat        : {hasil['riwayat']}")
    if hasil["usulan_agen"]:
        print("\n  PERINGATAN: teks yang ditandai [K…] dari agen masih USULAN.")
        print("  Ia belum diperiksa manusia dan tidak boleh dikutip sebagai fakta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
