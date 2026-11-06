"""Adaptor alat simulasi CATATAN MUROJAAH.

Tidak ada koneksi jaringan dan tidak ada pesan sungguhan. Setiap catatan yang
dihasilkan berlabel SIMULASI dan ditulis ke mock_outbox/ supaya bisa diperiksa
satu per satu setelah eksekusi.

Kegagalan alat bisa disuntik untuk pengujian, dua cara:
  · variabel lingkungan  TUNTAS_FAIL_ADAPTER=email
  · berkas               data/adapter_failures.json  {"tipe": ["email"], "pesan": "..."}

Tujuannya bukan membuat sistem terlihat tangguh, tetapi supaya kegagalan alat
benar-benar bisa diperlihatkan — termasuk status akhir rencana saat sebagian
tindakan gagal.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

WITA = timezone(timedelta(hours=8))

LABEL = "SIMULASI"
CATATAN = "Eksekusi simulasi. Tidak ada pesan sungguhan yang terkirim."


class AdapterError(Exception):
    """Adaptor melaporkan gagal. Bukan bug — ini kondisi yang harus ditangani."""

    def __init__(self, kode: str, pesan: str):
        super().__init__(pesan)
        self.kode = kode
        self.pesan = pesan


def _now() -> str:
    return datetime.now(WITA).isoformat(timespec="seconds")


def baca_gagal(root: str | Path) -> list[str]:
    env = os.environ.get("TUNTAS_FAIL_ADAPTER", "").strip()
    if env:
        return [x.strip() for x in env.split(",") if x.strip()]

    path = Path(root) / "data" / "adapter_failures.json"
    if path.exists():
        try:
            return list(json.loads(path.read_text(encoding="utf-8")).get("tipe", []))
        except (json.JSONDecodeError, AttributeError):
            return []
    return []


class SimulasiAdapter:
    def __init__(self, root: str | Path, gagal: list[str] | None = None):
        self.root = Path(root)
        self.dir = self.root / "mock_outbox"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.gagal = set(gagal if gagal is not None else baca_gagal(self.root))

    def path(self, action_id: str) -> Path:
        return self.dir / f"{action_id}.json"

    def jalankan(
        self,
        aksi: dict,
        action_id: str,
        plan_id: str,
        version: int,
        plan_hash: str,
    ) -> dict:
        tipe = aksi.get("type", "?")
        if tipe in self.gagal:
            raise AdapterError(
                "ADAPTER_GAGAL",
                f"Adaptor {tipe} melaporkan gagal (disuntik untuk uji).",
            )

        catatan = {
            "action_id": action_id,
            "plan_id": plan_id,
            "version": version,
            "plan_hash": plan_hash,
            "tipe": tipe,
            "sumber_paragraf": aksi.get("source_paragraf"),
            "label": LABEL,
            "status": "SIMULATED",
            "executed_at": _now(),
            "catatan": CATATAN,
            "payload": aksi,
        }
        self.path(action_id).write_text(
            json.dumps(catatan, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return catatan
