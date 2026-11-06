"""Planner TUNTAS — mengubah catatan rapat menjadi rencana terstruktur.

Dua backend, satu kontrak JSON:

  · StubPlanner  — rencana siap pakai untuk pengujian. Tidak butuh kredit,
                   tidak butuh jaringan, hasilnya selalu sama. Dipakai untuk
                   menjalankan 20 kasus uji secara berulang.
  · LLMPlanner   — mengirim catatan ke model bahasa lewat endpoint yang
                   kompatibel dengan OpenAI (WorkBuddy, Sumopod, DeepSeek).
                   Keluarannya divalidasi dengan kontrak yang sama.

Kontrak rencana (payload):
{
  "request_id": "REQ-...",
  "source": {"file": "rapat-2026-10-28.md", "paragraf": [3, 4]},
  "actions": [
    {"type": "email", "to": {"contact_id": "C-001", "email": "..."},
     "subject": "...", "body": "...", "source_paragraf": 4},
    {"type": "calendar", "title": "...", "start": "2026-10-30T14:00:00+08:00",
     "timezone": "WITA", "source_paragraf": 4},
    {"type": "task", "judul": "...", "pic": "Rafi", "due": "2026-10-29T10:00:00+08:00",
     "source_paragraf": 3}
  ]
}
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


class PlannerError(Exception):
    pass


def _izin_llm() -> bool:
    """Izin jalur LLM HTTP. Nama baru menang; nama lama dibaca sebagai kompatibilitas.

    Alasan nama ganda: produk berganti nama menjadi CATATAN MUROJAAH (30 Okt 2026),
    tetapi skrip/lingkungan lama masih menyetel TUNTAS_IZINKAN_LLM. Membaca
    keduanya tidak melemahkan gerbang — nilai "1" tetap wajib eksplisit.
    """
    for nama in ("CATATAN_MUROJAAH_IZINKAN_LLM", "TUNTAS_IZINKAN_LLM"):
        if os.environ.get(nama, "").strip() == "1":
            return True
    return False


class StubPlanner:
    """Rencana contoh. Dua varian untuk memperagakan klarifikasi."""

    def __init__(self, root: str | Path, varian: str = "mentah"):
        self.root = Path(root)
        self.varian = varian

    def plan(self, teks: str, berkas: str = "rapat-2026-10-28.md") -> dict:
        if self.varian == "mentah":
            aksi = self._mentah()
        elif self.varian == "setelah_klarifikasi":
            aksi = self._bersih()
        else:
            raise PlannerError(f"Varian tidak dikenal: {self.varian}")
        return {
            "request_id": "REQ-2026-10-28-01",
            "source": {"file": berkas, "paragraf": sorted({a["source_paragraf"] for a in aksi})},
            "actions": aksi,
        }

    @staticmethod
    def _mentah() -> list[dict]:
        return [
            {
                "type": "email",
                "to": {"nama": "Pak Budi"},
                "subject": "Notulen rapat 28 Oktober 2026",
                "body": "Pak Budi, terlampir notulen rapat 28 Oktober 2026.",
                "source_paragraf": 4,
            },
            {
                "type": "calendar",
                "title": "Follow-up tindak lanjut stok",
                "start": "2026-10-30T12:00:00+08:00",
                # Revisi 29 Okt malam: gerbang menuntut end atau durasi eksplisit
                # untuk kalender; durasi contoh ini usulan agen, bukan dari rapat.
                "durasi_menit": 60,
                "timezone": "WITA",
                "source_paragraf": 4,
            },
            {
                "type": "task",
                "judul": "Tindak lanjut pemasok",
                "pic": "",
                "due": "2026-10-31T10:00:00+08:00",
                "source_paragraf": 9,
                "kartu": StubPlanner._kartu(
                    "Tindak lanjut pemasok selesai dan hasilnya diketahui.",
                    "Catatan tindak lanjut yang bisa diperiksa.",
                    "Telepon atau pesan ke pemasok.",
                ),
            },
        ]

    @staticmethod
    def _kartu(hasil: str, bukti: str, kanal: str) -> dict:
        """Kartu tindakan versi rencana contoh.

        Semua nilai di sini USULAN_AGEN: rencana contoh tidak punya paragraf
        sumber yang menyebut hasil, bukti, atau kanal. Itu ditampilkan apa adanya
        di layar persetujuan, bukan disembunyikan sebagai fakta rapat.
        """
        return {
            "hasil_diharapkan": {"nilai": hasil, "asal": "USULAN_AGEN"},
            "bukti_penyelesaian": {"nilai": bukti, "asal": "USULAN_AGEN"},
            "kanal": {"nilai": kanal, "asal": "USULAN_AGEN"},
            "perlu_konfirmasi": [],
        }

    @staticmethod
    def _bersih() -> list[dict]:
        return [
            {
                "type": "task",
                "judul": "Cek stok 10 produk prioritas",
                "pic": "Rafi",
                "due": "2026-10-29T10:00:00+08:00",
                "source_paragraf": 3,
                "kartu": StubPlanner._kartu(
                    "Daftar stok 10 produk prioritas tersedia dan selisihnya diketahui.",
                    "Daftar stok tertulis, bertanggal, dengan angka sebelum dan sesudah.",
                    "Hitungan langsung di toko, dicatat tertulis.",
                ),
            },
            {
                "type": "email",
                "to": {"contact_id": "C-001", "email": "budi.santoso@contoh.id"},
                "subject": "Notulen rapat 28 Oktober 2026",
                "body": "Pak Budi, terlampir notulen rapat 28 Oktober 2026.",
                "source_paragraf": 4,
            },
            {
                "type": "calendar",
                "title": "Follow-up tindak lanjut stok",
                "start": "2026-10-30T14:00:00+08:00",
                # Revisi 29 Okt malam: gerbang menuntut end atau durasi eksplisit
                # untuk kalender; durasi contoh ini usulan agen, bukan dari rapat.
                "durasi_menit": 60,
                "timezone": "WITA",
                "source_paragraf": 4,
            },
        ]


class LLMPlanner:
    """Backend model bahasa lewat HTTP. MATI SECARA BAWAAN.

    Ini satu-satunya jalur di seluruh proyek yang membuka soket keluar. Karena
    itu ia dijaga dua lapis:

      1. `CATATAN_MUROJAAH_IZINKAN_LLM=1` harus disetel. Tanpa itu `plan()` menolak
         sebelum menyusun permintaan — tidak ada satu byte pun yang dikirim.
      2. Tiga variabel konfigurasi harus lengkap.

    CATATAN_MUROJAAH_IZINKAN_LLM  "1" untuk mengizinkan (nama baru, menang)
    TUNTAS_IZINKAN_LLM            nama lama, masih dibaca untuk kompatibilitas
    TUNTAS_LLM_URL      contoh: https://api.example.com/v1/chat/completions
    TUNTAS_LLM_KEY      kunci API (JANGAN ditulis ke dokumen/prompt/commit)
    TUNTAS_LLM_MODEL    contoh: deepseek-chat

    Yang dikirim bila diizinkan: seluruh `instructions.md` sebagai pesan sistem
    dan seluruh teks rapat sebagai pesan pengguna. Artinya isi rapat keluar dari
    mesin ini. Itu sebabnya izinnya eksplisit, bukan bawaan.

    Belum ada bukti jalur ini pernah dipakai di proyek ini: tidak ada berkas di
    `evidence/` yang berasal dari `--planner llm`, dan ketiga variabel kosong di
    mesin pengembangan.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.url = os.environ.get("TUNTAS_LLM_URL", "").strip()
        self.key = os.environ.get("TUNTAS_LLM_KEY", "").strip()
        self.model = os.environ.get("TUNTAS_LLM_MODEL", "").strip()
        self.izin = _izin_llm()

    @property
    def siap(self) -> bool:
        return bool(self.url and self.key and self.model)

    def plan(self, teks: str, berkas: str = "rapat-2026-10-28.md") -> dict:
        if not self.izin:
            raise PlannerError(
                "Jalur LLM HTTP tidak diizinkan. Ia mengirim SELURUH teks acara dan "
                "instructions.md ke alamat di luar mesin ini. Setel "
                "CATATAN_MUROJAAH_IZINKAN_LLM=1 (nama lama TUNTAS_IZINKAN_LLM masih "
                "dibaca) hanya bila Anda menerima itu. Tidak ada data yang dikirim "
                "sekarang. Untuk pemakaian normal, pakai --planner model (rencana "
                "disusun di percakapan WorkBuddy) atau --planner rule (deterministik)."
            )
        if not self.siap:
            raise PlannerError(
                "Backend model belum dikonfigurasi. Set TUNTAS_LLM_URL, "
                "TUNTAS_LLM_KEY, dan TUNTAS_LLM_MODEL — atau pakai --planner stub."
            )
        instruksi = (self.root / "instructions.md").read_text(encoding="utf-8")
        badan = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": instruksi},
                {
                    "role": "user",
                    "content": (
                        f"Berkas sumber: {berkas}\n\n"
                        "Keluarkan HANYA JSON rencana sesuai kontrak, tanpa penjelasan.\n\n"
                        f"--- catatan rapat ---\n{teks}"
                    ),
                },
            ],
        }
        permintaan = urllib.request.Request(
            self.url,
            data=json.dumps(badan).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(permintaan, timeout=90) as r:
                jawab = json.loads(r.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise PlannerError(f"Gagal menghubungi model: {e}") from e

        isi = jawab["choices"][0]["message"]["content"].strip()
        if isi.startswith("```"):
            isi = isi.split("```")[1]
            isi = isi[4:] if isi.lower().startswith("json") else isi
        try:
            return json.loads(isi)
        except json.JSONDecodeError as e:
            raise PlannerError(f"Keluaran model bukan JSON yang sah: {e}") from e


def buat_planner(root: str | Path, jenis: str = "stub", varian: str = "mentah"):
    if jenis == "stub":
        return StubPlanner(root, varian=varian)
    if jenis == "llm":
        return LLMPlanner(root)
    raise PlannerError(f"Jenis planner tidak dikenal: {jenis}")
