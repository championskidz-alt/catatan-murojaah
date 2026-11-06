"""Gerbang eksekusi CATATAN MUROJAAH.

Modul ini TIDAK memanggil model bahasa apa pun dan tidak menerima teks bebas.
Ia hanya bekerja dengan rencana yang sudah tersimpan sebagai JSON, membandingkan
sidik jari (hash) versi rencana dengan versi yang disetujui manusia, lalu
menjalankan aksi ke adaptor simulasi.

Aturan yang ditegakkan di sini, bukan di prompt:
  1. Rencana tanpa sumber (source_paragraf) ditolak saat dibuat.
  2. Persetujuan mengikat versi + hash. Ubah satu field, hash berubah, batal.
  3. Hanya tindakan yang disebut saat menyetujui yang dijalankan.
  4. Satu tindakan hanya bisa dijalankan sekali (action_id deterministik).
  5. Pemberi persetujuan harus punya hak setuju di permissions.csv.
  6. Jumlah penerima tidak boleh melebihi batas peran pemberi persetujuan.
  7. Penolakan manusia dicatat dan menghentikan eksekusi.
  8. Kegagalan adaptor dicatat sebagai FAILED, tidak pernah dianggap berhasil.
  9. Aksi yang dipilih wajib punya informasi wajib sesuai tipenya (task: PIC +
     tenggat; email: penerima; calendar: waktu mulai). Dicek di sini lagi —
     bukan hanya di validator — supaya aksi yang kurang info tidak bisa dieksekusi
     hanya karena dicentang di layar persetujuan.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from adapters import AdapterError, SimulasiAdapter, baca_gagal

WITA = timezone(timedelta(hours=8))

TIPE_AKSI = {"email", "calendar", "task"}

# Informasi wajib per tipe aksi: (jalur nilai dalam dict, label untuk pesan).
# Selaras dengan reviewer.py (PIC_HILANG, TENGGAT_HILANG, dst.) — tapi ditegakkan
# juga di gerbang, sebagai lapis terakhir sebelum eksekusi.
FIELD_WAJIB_AKSI: dict[str, tuple[tuple[str, str], ...]] = {
    "task": (("pic", "PIC"), ("due", "tenggat")),
    "email": (("to.email", "alamat penerima"), ("body", "isi pesan")),
    "calendar": (("title", "judul acara"), ("start", "waktu mulai"), ("timezone", "zona waktu")),
}


def _nilai_aksi(aksi: dict, jalur: str):
    """Ambil nilai bersarang "to.email" → aksi["to"]["email"]; None bila hilang."""
    kini: object = aksi
    for bagian in jalur.split("."):
        if not isinstance(kini, dict) or bagian not in kini:
            return None
        kini = kini[bagian]
    return kini


def _waktu_akhir_kalender(aksi: dict) -> str | None:
    """Kembalikan None bila waktu selesai sah, atau pesan kesalahan bila tidak.

    Menerima "end" (ISO) atau "durasi_menit" (menit, > 0). Tanpa keduanya
    dikembalikan pesan bahwa waktu selesai belum ada.
    """
    mulai = aksi.get("start")
    akhir = aksi.get("end")
    durasi = aksi.get("durasi_menit")
    if akhir:
        try:
            t_mulai = datetime.fromisoformat(str(mulai))
            t_akhir = datetime.fromisoformat(str(akhir))
        except ValueError:
            return "format waktu mulai/akhir tidak bisa dibaca (butuh ISO)."
        if t_akhir <= t_mulai:
            return "waktu selesai tidak boleh sebelum atau sama dengan waktu mulai."
        return None
    if isinstance(durasi, int) and not isinstance(durasi, bool) and durasi > 0:
        return None
    if isinstance(durasi, (int, float)) and not isinstance(durasi, bool) and durasi:
        return "durasi_menit harus bilangan bulat positif."
    return "butuh waktu selesai (end) atau durasi eksplisit (durasi_menit)."


def _info_kurang(rec: dict, indeks_aksi: list[int]) -> list[str]:
    """Daftar "aksi #i: <label> kosong" untuk aksi yang informasi wajibnya kurang."""
    kurang: list[str] = []
    for i in indeks_aksi:
        aksi = rec["payload"]["actions"][i]
        for jalur, label in FIELD_WAJIB_AKSI.get(aksi.get("type", ""), ()):
            v = _nilai_aksi(aksi, jalur)
            if v is None or (isinstance(v, str) and not v.strip()):
                kurang.append(f"aksi #{i}: {label} ({jalur}) kosong")
        if aksi.get("type") == "calendar":
            pesan = _waktu_akhir_kalender(aksi)
            if pesan:
                kurang.append(f"aksi #{i}: {pesan}")
        # Klarifikasi wajib yang masih terbuka menghalangi aksi terkait.
        # Catatan opsional di kartu (perlu_konfirmasi) TIDAK menghalangi —
        # ia tampil di layar sebagai hal yang perlu diperhatikan, dan manusia
        # yang memutuskan.
        for q in rec["payload"].get("pertanyaan_terbuka") or []:
            if q.get("paragraf") == aksi.get("source_paragraf"):
                kurang.append(
                    f"aksi #{i}: klarifikasi wajib masih terbuka — "
                    f"¶{q.get('paragraf')}: {q.get('pertanyaan', '')}"
                )
    return kurang


STATUS_SAH = {
    "DRAFT", "APPROVED", "EXECUTED_MOCK", "CANCELLED", "PARTIAL", "REJECTED", "FAILED",
}


class GateError(Exception):
    """Kesalahan yang disengaja. Kode dipakai di audit log dan di UI."""

    def __init__(self, code: str, pesan: str, **detail):
        super().__init__(pesan)
        self.code = code
        self.pesan = pesan
        self.detail = detail


def _now() -> str:
    return datetime.now(WITA).isoformat(timespec="seconds")


def _canonical(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _hash(payload: dict) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


class Gate:
    def __init__(self, root: str | Path, data_root: str | Path | None = None):
        # data_root opsional: memungkinkan root per-sesi (mis. data/meetings/<id>/)
        # sambil tetap membaca permissions.csv dari folder data proyek.
        self.root = Path(root)
        self.data = Path(data_root) if data_root is not None else self.root / "data"
        self.dir_plans = self.root / "plans"
        self.dir_approvals = self.root / "approvals"
        self.dir_outbox = self.root / "mock_outbox"
        self.audit_path = self.root / "audit.jsonl"
        for d in (self.dir_plans, self.dir_approvals, self.dir_outbox):
            d.mkdir(parents=True, exist_ok=True)

    # ---------- audit ----------

    def _audit(self, event: str, **fields) -> None:
        baris = {"ts": _now(), "event": event, **fields}
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(baris, ensure_ascii=False) + "\n")

    def catat(self, event: str, **fields) -> None:
        """Catat peristiwa di luar alur eksekusi, mis. percobaan memalsukan identitas."""
        self._audit(event, **fields)

    def baca_audit(self) -> list[dict]:
        if not self.audit_path.exists():
            return []
        return [
            json.loads(b)
            for b in self.audit_path.read_text(encoding="utf-8").splitlines()
            if b.strip()
        ]

    # ---------- izin ----------

    def _izin(self) -> dict[str, dict]:
        path = self.data / "permissions.csv"
        # utf-8-sig: berkas CSV yang disimpan dari Excel sering membawa BOM.
        with path.open(encoding="utf-8-sig", newline="") as f:
            baris = [
                {k.strip(): (v or "").strip() for k, v in r.items()}
                for r in csv.DictReader(f)
            ]
        return {r["user_id"]: r for r in baris}

    # ---------- validasi rencana ----------

    def _validasi(self, payload: dict) -> None:
        aksi = payload.get("actions")
        if not isinstance(aksi, list) or not aksi:
            raise GateError("NO_ACTIONS", "Rencana tidak berisi tindakan apa pun.")
        for i, a in enumerate(aksi):
            if a.get("type") not in TIPE_AKSI:
                raise GateError(
                    "BAD_ACTION_TYPE",
                    f"Aksi #{i} punya tipe tidak dikenal: {a.get('type')!r}.",
                )
            if not isinstance(a.get("source_paragraf"), int) or a["source_paragraf"] <= 0:
                raise GateError(
                    "NO_SOURCE",
                    f"Aksi #{i} tidak menunjuk paragraf sumber. Tugas tanpa sumber "
                    "tidak boleh dibuat.",
                )
            if a["type"] == "email":
                to = a.get("to") or {}
                if not to.get("contact_id") or not to.get("email"):
                    raise GateError(
                        "NO_RECIPIENT",
                        f"Aksi #{i} belum punya penerima dengan contact_id dan email.",
                    )
                if not a.get("body"):
                    raise GateError("NO_BODY", f"Aksi #{i} belum punya isi pesan.")
            if a["type"] == "calendar":
                if not a.get("start") or not a.get("timezone"):
                    raise GateError(
                        "NO_TIME",
                        f"Aksi #{i} butuh waktu mulai dan zona waktu eksplisit.",
                    )
                if not (a.get("title") or "").strip():
                    raise GateError(
                        "NO_TITLE",
                        f"Aksi #{i} (kalender) belum punya judul acara.",
                    )
                # Waktu selesai boleh berupa "end" atau "durasi_menit"; kalau
                # "end" diberikan, ia harus benar-benar sesudah "mulai".
                akhir = _waktu_akhir_kalender(a)
                if isinstance(akhir, str):
                    raise GateError("BAD_TIME", f"Aksi #{i} (kalender): {akhir}")

    # ---------- penyimpanan ----------

    def _plan_path(self, plan_id: str) -> Path:
        return self.dir_plans / f"{plan_id}.json"

    def _muat_plan(self, plan_id: str) -> dict:
        p = self._plan_path(plan_id)
        if not p.exists():
            raise GateError("PLAN_NOT_FOUND", f"Rencana {plan_id} tidak ada.")
        return json.loads(p.read_text(encoding="utf-8"))

    def _simpan_plan(self, rec: dict) -> None:
        self._plan_path(rec["plan_id"]).write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _approval_path(self, plan_id: str, version: int) -> Path:
        return self.dir_approvals / f"{plan_id}.v{version}.json"

    def _rejection_path(self, plan_id: str, version: int) -> Path:
        return self.dir_approvals / f"{plan_id}.v{version}.rejected.json"

    def hash_sekarang(self, plan_id: str) -> str:
        return _hash(self._muat_plan(plan_id)["payload"])

    # ---------- API ----------

    def create_plan(self, payload: dict, request_id: str | None = None) -> dict:
        self._validasi(payload)
        plan_id = f"PL-{datetime.now(WITA):%Y%m%d}-{hashlib.sha256(_canonical(payload)).hexdigest()[:6].upper()}"
        rec = {
            "plan_id": plan_id,
            "version": 1,
            "status": "DRAFT",
            "created_at": _now(),
            "request_id": request_id,
            "payload": payload,
        }
        self._simpan_plan(rec)
        self._audit(
            "plan_created",
            plan_id=plan_id,
            version=1,
            plan_hash=_hash(payload)[:16],
            jumlah_aksi=len(payload["actions"]),
        )
        return rec

    def revise(self, plan_id: str, payload: dict) -> dict:
        """Setiap perubahan menaikkan versi. Persetujuan lama tidak berlaku lagi."""
        self._validasi(payload)
        rec = self._muat_plan(plan_id)
        rec["version"] += 1
        rec["payload"] = payload
        rec["status"] = "DRAFT"
        self._simpan_plan(rec)
        self._audit(
            "plan_revised",
            plan_id=plan_id,
            version=rec["version"],
            plan_hash=_hash(payload)[:16],
        )
        return rec

    def approve(
        self,
        plan_id: str,
        version: int,
        plan_hash: str,
        approver_id: str,
        action_ids: list[int] | None = None,
        jalur: str = "web",
        mode_uji: bool = False,
    ) -> dict:
        """Catat persetujuan.

        `jalur` membedakan dua hal yang tidak boleh dicampur:

        · "web" — layar persetujuan (`approval_server.py`). Ini jalur operasional.
        · "cli" — `pipeline.py --approve`. Ini **fasilitas pengujian**, dan hanya
          boleh jalan bila pemanggil menyatakan `mode_uji=True` (dipicu flag
          `--izinkan-uji-persetujuan`). Tanpa itu, agen bisa menyetujui rencananya
          sendiri lewat satu baris perintah.

        Yang TIDAK diklaim: `jalur` bukan bukti bahwa manusia benar-benar menekan
        tombol. Ia hanya mencatat lewat pintu mana persetujuan masuk, sehingga
        persetujuan sintetis bisa dikenali di audit dan tidak disebut persetujuan
        manusia.
        """
        if jalur not in {"web", "cli"}:
            raise GateError("BAD_APPROVAL_CHANNEL", f"Jalur persetujuan {jalur!r} tidak dikenal.")
        if jalur == "cli" and not mode_uji:
            self._audit(
                "approval_rejected",
                plan_id=plan_id,
                alasan="CLI_APPROVAL_REQUIRES_TEST_FLAG",
                actor=approver_id,
            )
            raise GateError(
                "CLI_APPROVAL_REQUIRES_TEST_FLAG",
                "Persetujuan lewat CLI adalah fasilitas uji. Jalankan ulang dengan "
                "--izinkan-uji-persetujuan, atau setujui lewat layar web.",
            )

        rec = self._muat_plan(plan_id)
        if rec["version"] != version:
            self._audit("approval_rejected", plan_id=plan_id, alasan="VERSION_MISMATCH")
            raise GateError(
                "VERSION_MISMATCH",
                f"Rencana sudah berubah ke versi {rec['version']}. Muat ulang layar persetujuan.",
            )

        if _hash(rec["payload"]) != plan_hash:
            self._audit("approval_rejected", plan_id=plan_id, alasan="HASH_MISMATCH")
            raise GateError(
                "HASH_MISMATCH",
                "Isi rencana berbeda dari yang ditampilkan. Persetujuan ditolak.",
            )

        izin = self._izin().get(approver_id)
        if izin is None or izin["boleh_setujui"].strip().lower() != "ya":
            self._audit(
                "approval_rejected", plan_id=plan_id, alasan="NOT_AUTHORIZED",
                actor=approver_id,
            )
            raise GateError(
                "NOT_AUTHORIZED", f"{approver_id} tidak punya hak menyetujui."
            )

        n = len(rec["payload"]["actions"])
        dipilih = list(range(n)) if action_ids is None else list(action_ids)
        if not dipilih:
            raise GateError("NO_SELECTION", "Tidak ada tindakan yang dipilih.")
        for i in dipilih:
            if not isinstance(i, int) or i < 0 or i >= n:
                raise GateError("BAD_SELECTION", f"Indeks tindakan {i} tidak ada.")

        # Lapis terakhir sebelum persetujuan: aksi yang informasi wajibnya belum
        # jelas (PIC, tenggat, penerima, waktu mulai) tidak boleh disetujui hanya
        # karena dicentang. Validator sudah menolak rencana seperti ini lebih awal;
        # penjagaan di sini menghardalkan itu di pintu eksekusi juga.
        kurang = _info_kurang(rec, dipilih)
        if kurang:
            self._audit(
                "approval_rejected", plan_id=plan_id, alasan="ACTION_INFO_INCOMPLETE",
                actor=approver_id, rincian=kurang,
            )
            raise GateError(
                "ACTION_INFO_INCOMPLETE",
                "Aksi yang dipilih masih ada informasi wajib yang kosong — "
                + "; ".join(kurang)
                + ". Lengkapi lewat klarifikasi, jangan setujui dulu.",
            )

        batas = int(izin["batas_penerima"])
        penerima = {
            rec["payload"]["actions"][i]["to"]["email"]
            for i in dipilih
            if rec["payload"]["actions"][i]["type"] == "email"
        }
        if len(penerima) > batas:
            self._audit(
                "approval_rejected", plan_id=plan_id, alasan="LIMIT_EXCEEDED",
                actor=approver_id, jumlah_penerima=len(penerima), batas=batas,
            )
            raise GateError(
                "LIMIT_EXCEEDED",
                f"{len(penerima)} penerima melebihi batas peran ({batas}). "
                "Butuh persetujuan kedua.",
            )

        rec_approval = {
            "plan_id": plan_id,
            "version": version,
            "plan_hash": plan_hash,
            "approver_id": approver_id,
            "approved_action_ids": dipilih,
            "approved_at": _now(),
            "jalur": jalur,
            "mode_uji": bool(mode_uji),
            "catatan": (
                "PERSETUJUAN SINTETIS (mode_uji) — fasilitas pengujian, bukan "
                "persetujuan manusia nyata."
                if mode_uji
                else "Disetujui lewat layar persetujuan lokal (sesi server). "
                     "Bukan autentikasi produksi."
            ),
        }
        self._approval_path(plan_id, version).write_text(
            json.dumps(rec_approval, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        rec["status"] = "APPROVED"
        self._simpan_plan(rec)
        self._audit(
            "plan_approved",
            plan_id=plan_id,
            version=version,
            plan_hash=plan_hash[:16],
            actor=approver_id,
            disetujui=dipilih,
            jalur=jalur,
            mode_uji=bool(mode_uji),
        )
        # Peristiwa terpisah supaya bisa dicari langsung: "siapa yang menyetujui
        # lewat CLI?" tanpa harus menyaring semua plan_approved.
        self._audit(
            "approval_via_cli" if jalur == "cli" else "approval_via_web",
            plan_id=plan_id,
            version=version,
            actor=approver_id,
            mode_uji=bool(mode_uji),
        )
        return rec_approval

    def reject(
        self, plan_id: str, version: int, approver_id: str, alasan: str = ""
    ) -> dict:
        """Manusia menolak. Ini hasil yang sah, bukan kesalahan sistem."""
        rec = self._muat_plan(plan_id)
        if rec["version"] != version:
            self._audit("rejection_rejected", plan_id=plan_id, alasan="VERSION_MISMATCH")
            raise GateError(
                "VERSION_MISMATCH",
                f"Rencana sudah berubah ke versi {rec['version']}. Muat ulang.",
            )

        izin = self._izin().get(approver_id)
        if izin is None or izin["boleh_setujui"].strip().lower() != "ya":
            self._audit(
                "rejection_rejected", plan_id=plan_id, alasan="NOT_AUTHORIZED",
                actor=approver_id,
            )
            raise GateError(
                "NOT_AUTHORIZED", f"{approver_id} tidak punya hak menolak rencana."
            )

        catatan = {
            "plan_id": plan_id,
            "version": version,
            "approver_id": approver_id,
            "alasan": alasan,
            "rejected_at": _now(),
        }
        self._rejection_path(plan_id, version).write_text(
            json.dumps(catatan, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        rec["status"] = "REJECTED"
        self._simpan_plan(rec)
        self._audit(
            "plan_rejected", plan_id=plan_id, version=version,
            actor=approver_id, alasan=alasan or "(tanpa alasan)",
        )
        return catatan

    def execute(self, plan_id: str) -> dict:
        rec = self._muat_plan(plan_id)
        version = rec["version"]
        hash_kini = _hash(rec["payload"])

        ap_path = self._approval_path(plan_id, version)
        if not ap_path.exists():
            if self._rejection_path(plan_id, version).exists():
                self._audit("execute_rejected", plan_id=plan_id, alasan="PLAN_REJECTED")
                raise GateError(
                    "PLAN_REJECTED",
                    "Rencana ini sudah ditolak manusia. Tidak ada yang dijalankan.",
                )
            # Ada persetujuan untuk versi lain? Berarti rencana berubah setelah
            # disetujui — pesannya harus berbeda dari "belum pernah disetujui".
            versi_lama = [
                p for p in sorted(self.dir_approvals.glob(f"{plan_id}.v*.json"))
                if not p.name.endswith(".rejected.json")
            ]
            if versi_lama:
                self._audit(
                    "execute_rejected", plan_id=plan_id, alasan="APPROVAL_INVALIDATED",
                    versi_disetujui=versi_lama[-1].stem.split(".v")[-1], versi_kini=version,
                )
                raise GateError(
                    "APPROVAL_INVALIDATED",
                    "Rencana berubah setelah disetujui. Persetujuan lama batal; "
                    "butuh persetujuan ulang.",
                )
            self._audit("execute_rejected", plan_id=plan_id, alasan="NOT_APPROVED")
            raise GateError(
                "NOT_APPROVED", "Belum ada persetujuan untuk versi rencana ini."
            )

        approval = json.loads(ap_path.read_text(encoding="utf-8"))
        if approval["plan_hash"] != hash_kini:
            self._audit(
                "execute_rejected", plan_id=plan_id, alasan="APPROVAL_INVALIDATED",
                hash_disetujui=approval["plan_hash"][:16], hash_kini=hash_kini[:16],
            )
            raise GateError(
                "APPROVAL_INVALIDATED",
                "Isi rencana berbeda dari yang disetujui. Persetujuan batal.",
            )

        # Penjagaan yang sama dengan approve(), diulang di sini supaya berkas
        # persetujuan yang ditulis tangan tidak bisa menyelipkan aksi tanpa
        # PIC/tenggat/penerima.
        kurang = _info_kurang(rec, approval["approved_action_ids"])
        if kurang:
            self._audit(
                "execute_rejected", plan_id=plan_id, alasan="ACTION_INFO_INCOMPLETE",
                rincian=kurang,
            )
            raise GateError(
                "ACTION_INFO_INCOMPLETE",
                "Aksi yang disetujui masih ada informasi wajib yang kosong — "
                + "; ".join(kurang) + ". Tidak ada yang dijalankan.",
            )

        adaptor = SimulasiAdapter(self.root, gagal=baca_gagal(self.root))
        hasil: list[dict] = []
        dilewati = 0
        gagal = 0

        for i in approval["approved_action_ids"]:
            aksi = rec["payload"]["actions"][i]
            action_id = f"{plan_id}-v{version}-a{i}"
            berkas = adaptor.path(action_id)

            if berkas.exists():
                lama = json.loads(berkas.read_text(encoding="utf-8"))
                # Hanya kegagalan yang boleh dicoba ulang. Yang sudah berhasil
                # atau sudah dibatalkan manusia tidak dijalankan lagi.
                if lama.get("status") != "FAILED":
                    dilewati += 1
                    hasil.append({"action_id": action_id, "status": "SUDAH_DIJALANKAN"})
                    continue

            try:
                adaptor.jalankan(aksi, action_id, plan_id, version, hash_kini)
            except AdapterError as e:
                gagal += 1
                berkas.write_text(
                    json.dumps(
                        {
                            "action_id": action_id,
                            "plan_id": plan_id,
                            "version": version,
                            "tipe": aksi.get("type"),
                            "sumber_paragraf": aksi.get("source_paragraf"),
                            "label": "SIMULASI",
                            "status": "FAILED",
                            "error_kode": e.kode,
                            "error": e.pesan,
                            "failed_at": _now(),
                            "catatan": "Gagal di adaptor simulasi. Tidak ada yang terkirim.",
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                self._audit(
                    "action_failed", plan_id=plan_id, version=version,
                    action_id=action_id, kode=e.kode, pesan=e.pesan,
                )
                hasil.append({"action_id": action_id, "status": "FAILED", "pesan": e.pesan})
                continue

            self._audit(
                "action_executed_mock",
                plan_id=plan_id,
                version=version,
                action_id=action_id,
                tipe=aksi["type"],
                sumber_paragraf=aksi["source_paragraf"],
            )
            hasil.append({"action_id": action_id, "status": "SIMULATED"})

        total = len(approval["approved_action_ids"])
        dijalankan = sum(1 for h in hasil if h["status"] == "SIMULATED")
        if gagal and dijalankan:
            rec["status"] = "PARTIAL"
        elif gagal:
            rec["status"] = "FAILED"
        elif dijalankan:
            rec["status"] = "EXECUTED_MOCK"
        self._simpan_plan(rec)
        return {
            "plan_id": plan_id,
            "version": version,
            "dijalankan": dijalankan,
            "dilewati": dilewati,
            "gagal": gagal,
            "total_disetujui": total,
            "status_plan": rec["status"],
            "hasil": hasil,
        }

    def undo(self, action_id: str, actor: str, jendela_detik: int = 60) -> dict:
        berkas = self.dir_outbox / f"{action_id}.json"
        if not berkas.exists():
            raise GateError("ACTION_NOT_FOUND", f"{action_id} tidak pernah dijalankan.")
        catatan = json.loads(berkas.read_text(encoding="utf-8"))
        if catatan["status"] != "SIMULATED":
            raise GateError("NOT_UNDOABLE", f"Status {catatan['status']} tidak bisa dibatalkan.")

        waktu = datetime.fromisoformat(catatan["executed_at"])
        lewat = (datetime.now(WITA) - waktu).total_seconds()
        if lewat > jendela_detik:
            self._audit("undo_rejected", action_id=action_id, lewat_detik=round(lewat))
            raise GateError(
                "UNDO_WINDOW_PASSED",
                f"Jendela batal {jendela_detik} detik sudah lewat ({round(lewat)} detik).",
            )

        catatan["status"] = "CANCELLED_UNDONE"
        catatan["undone_at"] = _now()
        catatan["undone_by"] = actor
        berkas.write_text(json.dumps(catatan, ensure_ascii=False, indent=2), encoding="utf-8")
        self._audit("action_undone", action_id=action_id, actor=actor, lewat_detik=round(lewat))
        return catatan

    def status(self, plan_id: str) -> dict:
        rec = self._muat_plan(plan_id)
        ap = self._approval_path(plan_id, rec["version"])
        return {
            "plan_id": plan_id,
            "version": rec["version"],
            "status": rec["status"],
            "plan_hash": _hash(rec["payload"])[:16],
            "disetujui": json.loads(ap.read_text(encoding="utf-8"))["approved_action_ids"]
            if ap.exists()
            else [],
        }
