"""Layar persetujuan CATATAN MUROJAAH — satu halaman, tanpa framework.

Server ini hanya menyajikan satu rencana dan meneruskan keputusan manusia ke
gate.py. Tidak ada logika persetujuan di dalam HTML: kalau halaman ini dibuka
tanpa server, tombolnya tidak melakukan apa pun. Itu disengaja — halaman bukan
gerbang, halaman hanya jendela.

Jalankan:
    python approval_server.py --run-dir _run_baru2
lalu buka http://127.0.0.1:8765

Hanya mendengarkan di 127.0.0.1. Tidak ada akses jaringan keluar.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from gate import Gate, GateError

ROOT = Path(__file__).resolve().parent
esc = html.escape

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#f4f5f7;color:#15171a;
     font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:28px 22px 60px}
header{display:flex;align-items:baseline;gap:12px;margin-bottom:4px}
.brand{font-size:20px;font-weight:800;letter-spacing:-.02em}
.brand span{color:#185FA5}
.sub{font-size:13px;color:#666}
.banner{margin:14px 0 18px;padding:10px 13px;border-radius:7px;
        background:#FFF4E5;border:1px solid #F0C27A;color:#7A4A00;font-size:13px;font-weight:600}
.card{background:#fff;border:1px solid #e2e5e9;border-radius:9px;padding:16px 18px;margin-bottom:16px}
.meta{font-size:12.5px;color:#555;font-family:ui-monospace,Menlo,monospace}
.meta b{color:#15171a}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:#666;
   margin:0 0 10px;font-weight:700}
table{width:100%;border-collapse:collapse}
td{padding:11px 8px;border-top:1px solid #eceef1;vertical-align:top}
tr:first-child td{border-top:0}
td.pilih{width:34px;padding-top:13px}
input[type=checkbox]{width:17px;height:17px;accent-color:#185FA5}
.jenis{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.04em;
       padding:2px 7px;border-radius:4px;background:#E6F1FB;color:#185FA5;
       text-transform:uppercase;margin-right:7px}
.jenis.task{background:#EAF3DE;color:#3B6D11}
.jenis.calendar{background:#F1E9FB;color:#5B2C9A}
.utama{font-weight:600}
.detail{font-size:12.5px;color:#555;margin-top:3px}
.sumber{font-size:12px;color:#666;margin-top:5px;padding-left:9px;border-left:2px solid #d8dce1}
.sumber b{color:#185FA5;font-family:ui-monospace,monospace}
.asumsi{font-size:11.5px;color:#8A5A00;background:#FFF8EA;border-radius:4px;
        padding:3px 7px;display:inline-block;margin-top:5px}
.abaikan{font-size:12.5px;background:#FDECEC;border:1px solid #F3C0C0;color:#8A1F1F;
         border-radius:6px;padding:9px 12px;margin-top:10px}
.status{display:inline-block;margin-left:9px;font-size:11px;font-weight:700;
        padding:2px 8px;border-radius:10px;background:#eee;color:#555;vertical-align:2px}
.status.jalan{background:#EAF3DE;color:#2F5410}
.status.batal{background:#F0F1F3;color:#6a6f76}
.baris{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:14px}
select{padding:8px 10px;border:1px solid #cfd4da;border-radius:6px;font-size:14px;background:#fff}
.identitas{font-size:12px;color:#555;background:#EEF3F9;border:1px solid #C7D8EA;
           border-radius:6px;padding:7px 10px}
.identitas b{color:#185FA5}
button{padding:9px 15px;border-radius:6px;border:1px solid transparent;font-size:14px;
       font-weight:600;cursor:pointer}
.ok{background:#185FA5;color:#fff}
.no{background:#fff;color:#8A1F1F;border-color:#E3B4B4}
.run{background:#3B6D11;color:#fff}
.hasil{margin-top:14px;padding:12px 14px;border-radius:7px;font-size:13.5px}
.hasil.good{background:#EAF3DE;border:1px solid #B9D08C;color:#2F5410}
.hasil.bad{background:#FDECEC;border:1px solid #F3C0C0;color:#8A1F1F}
.hasil.info{background:#EEF3F9;border:1px solid #C7D8EA;color:#1B3F66}
code{font-family:ui-monospace,Menlo,monospace;font-size:12px}
.kartu{margin-top:9px;border:1px solid #e6e9ed;border-radius:6px;overflow:hidden}
.krow{padding:8px 11px;border-top:1px solid #eef0f3}
.krow:first-child{border-top:0}
.klabel{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#6b7280}
.knilai{font-size:12.8px;color:#15171a;margin-top:3px}
.kkutip{font-size:11.5px;color:#6b7280;margin-top:3px;font-style:italic}
.asal{display:inline-block;font-size:9.5px;font-weight:800;letter-spacing:.05em;
      padding:1px 6px;border-radius:3px;margin-left:7px;vertical-align:1px}
.asal.sumber{background:#E6F1FB;color:#12507F}
.asal.turunan{background:#FFF4E0;color:#7A4A00}
.asal.usulan{background:#F1E9FB;color:#5B2C9A}
.asal.konfirmasi{background:#E7F5E7;color:#2F6B2F}
.konfirmasi-box{margin-top:8px;padding:8px 11px;border-radius:6px;background:#FFF8EA;
                border:1px solid #F0D9A8;font-size:12.5px;color:#7A4A00}
.konfirmasi-box b{color:#5A3600}
.keputusan{margin-top:6px;padding:7px 10px;border-radius:5px;background:#E7F5E7;
           border:1px solid #B9DBB9;font-size:12px;color:#2F5B2F}
.keputusan b{display:block;font-size:10px;letter-spacing:.05em;text-transform:uppercase;
             margin-bottom:2px;color:#2F6B2F}
.foot{margin-top:22px;font-size:11.5px;color:#777;line-height:1.6}
"""

ASAL_LABEL = {
    "SUMBER_RAPAT": ("sumber", "SUMBER RAPAT"),
    "TURUNAN_DENGAN_DASAR": ("turunan", "TURUNAN DENGAN DASAR"),
    "USULAN_AGEN": ("usulan", "USULAN AGEN — belum disetujui"),
    "KONFIRMASI_PENGGUNA": ("konfirmasi", "KONFIRMASI PENGGUNA"),
}

FIELD_LABEL = (
    ("hasil_diharapkan", "Hasil yang diharapkan"),
    ("bukti_penyelesaian", "Bukti penyelesaian"),
    ("kanal", "Kanal / alat pelaksanaan"),
)


# ---------------------------------------------------------------- bantuan


def muat_plan(root: Path) -> dict | None:
    berkas = sorted((root / "plans").glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not berkas:
        return None
    return json.loads(berkas[-1].read_text(encoding="utf-8"))


def muat_sumber(root: Path, nama: str) -> dict[int, str]:
    path = root / "data" / "sources" / nama
    if not path.exists():
        return {}
    teks = path.read_text(encoding="utf-8")
    bagian = re.split(r"^¶(\d+)\s*[—-]\s*", teks, flags=re.M)
    out: dict[int, str] = {}
    for i in range(1, len(bagian) - 1, 2):
        out[int(bagian[i])] = " ".join(bagian[i + 1].split())
    return out


def daftar_approver(root: Path) -> list[dict]:
    path = root / "data" / "permissions.csv"
    with path.open(encoding="utf-8-sig", newline="") as f:
        baris = list(csv.DictReader(f))
    return [r for r in baris if (r.get("boleh_setujui") or "").strip().lower() == "ya"]


def potong(teks: str, n: int = 200) -> str:
    teks = " ".join((teks or "").split())
    return teks if len(teks) <= n else teks[: n - 1] + "…"


# ---------------------------------------------------------------- tampilan


def render_kartu(a: dict) -> str:
    """Tampilkan kartu tindakan. Setiap nilai membawa label asalnya.

    Pemisahan ini yang membuat layar jujur: yang diucapkan di rapat, yang
    diturunkan, yang diusulkan agen, dan yang diputuskan pengguna tidak
    dilebur menjadi satu kolom "hasil" yang terlihat sama rata.
    """
    kartu = a.get("kartu")
    if not isinstance(kartu, dict):
        return ""
    baris: list[str] = []
    for field, label in FIELD_LABEL:
        isi = kartu.get(field)
        if not isinstance(isi, dict):
            continue
        kelas, teks = ASAL_LABEL.get(
            (isi.get("asal") or "").strip(), ("usulan", str(isi.get("asal") or "?"))
        )
        ekstra = ""
        if isi.get("kutipan"):
            ekstra = f'<div class="kkutip">kutipan ¶: “{esc(potong(isi["kutipan"], 120))}”</div>'
        elif isi.get("dasar"):
            ekstra = f'<div class="kkutip">dasar: {esc(potong(isi["dasar"], 170))}</div>'
        baris.append(
            f'<div class="krow"><span class="klabel">{esc(label)}</span>'
            f'<span class="asal {kelas}">{esc(teks)}</span>'
            f'<div class="knilai">{esc(isi.get("nilai") or "—")}</div>{ekstra}</div>'
        )
    konf = "".join(f"<div>• {esc(x)}</div>" for x in kartu.get("perlu_konfirmasi") or [])
    if konf:
        baris.append(
            '<div class="krow"><span class="klabel">Perlu dikonfirmasi</span>'
            '<span class="asal turunan">BELUM PASTI</span>'
            f'<div class="knilai">{konf}</div></div>'
        )
    return f'<div class="kartu">{"".join(baris)}</div>' if baris else ""


def render_aksi(
    i: int,
    a: dict,
    paragraf: dict[int, str],
    bisa_pilih: bool,
    status: str = "",
    jenis_status: str = "",
) -> str:
    jenis = a.get("type", "?")
    if jenis == "email":
        tujuan = a["to"].get("contact_id") or a["to"].get("nama") or "?"
        utama = f"Email ke {esc(str(tujuan))}"
        detail = (
            f"Subjek: {esc(a.get('subject', ''))}<br>"
            f"Isi: {esc(potong(a.get('body', ''), 150))}"
        )
    elif jenis == "calendar":
        utama = f"Kalender: {esc(a.get('title', ''))}"
        detail = f"{esc(a.get('start') or '(kosong)')} · {esc(a.get('timezone') or '(kosong)')}"
    else:
        utama = f"Tugas: {esc(a.get('judul', ''))}"
        detail = (
            f"PIC {esc(a.get('pic') or '—')} · tenggat {esc(a.get('due') or '—')}"
        )

    no = a.get("source_paragraf")
    kutipan = potong(paragraf.get(no, "(paragraf tidak ditemukan)"), 180)

    kotak = (
        f'<input type="checkbox" name="aksi" value="{i}" checked>'
        if bisa_pilih
        else ""
    )
    asumsi = "".join(
        f'<div class="asumsi">turunan: {esc(x)}</div>' for x in a.get("asumsi") or []
    )
    # Nilai dari jawaban manusia diberi label tegas: ia BUKAN ucapan rekaman.
    # Sebelumnya hanya ditulis "dijawab:", yang terlalu mudah dibaca sebagai
    # bagian dari rapat.
    dijawab = "".join(
        '<div class="keputusan"><b>Keputusan pengguna — bukan ucapan rekaman</b>'
        f"{esc(x)}</div>"
        for x in a.get("catatan_klarifikasi") or []
    )
    lencana = (
        f'<span class="status {esc(jenis_status)}">{esc(status)}</span>' if status else ""
    )
    return (
        f"<tr><td class=\"pilih\">{kotak}</td><td>"
        f'<span class="jenis {esc(jenis)}">{esc(jenis)}</span>'
        f'<span class="utama">{utama}</span>{lencana}'
        f'<div class="detail">{detail}</div>{render_kartu(a)}{asumsi}{dijawab}'
        f'<div class="sumber"><b>¶{esc(str(no))}</b> “{esc(kutipan)}”</div>'
        f"</td></tr>"
    )


def halaman(
    root: Path, pesan: str = "", jenis_pesan: str = "info", sesi: dict | None = None
) -> str:
    sesi = sesi or {}
    csrf = esc(sesi.get("csrf", ""))
    approver = esc(sesi.get("approver_id", "?"))
    nama_approver = esc(sesi.get("nama", ""))
    rec = muat_plan(root)
    if rec is None:
        return (
            "<!DOCTYPE html><html lang=id><head><meta charset=utf-8>"
            f"<title>CATATAN MUROJAAH</title><style>{CSS}</style></head><body><div class=wrap>"
            "<header><div class=brand>CATATAN <span>MUROJAAH</span></div></header>"
            "<div class=card>Belum ada rencana di folder kerja ini. "
            "Jalankan <code>python pipeline.py --planner rule --sumber "
            "rapat-2026-10-29.md --run-dir _run_baru2</code> lebih dulu.</div>"
            "</div></body></html>"
        )

    payload = rec["payload"]
    paragraf = muat_sumber(root, payload["source"]["file"])
    gate = Gate(root)
    hash_ = gate.hash_sekarang(rec["plan_id"])

    status = rec["status"]
    sudah_setuju = (root / "approvals" / f"{rec['plan_id']}.v{rec['version']}.json").exists()
    sudah_tolak = (
        root / "approvals" / f"{rec['plan_id']}.v{rec['version']}.rejected.json"
    ).exists()
    bisa_pilih = not (sudah_setuju or sudah_tolak or status.startswith("EXECUTED"))

    berkas_setuju = root / "approvals" / f"{rec['plan_id']}.v{rec['version']}.json"
    disetujui: list[int] = (
        json.loads(berkas_setuju.read_text(encoding="utf-8"))["approved_action_ids"]
        if berkas_setuju.exists()
        else []
    )

    def status_aksi(i: int) -> tuple[str, str]:
        out = root / "mock_outbox" / f"{rec['plan_id']}-v{rec['version']}-a{i}.json"
        if out.exists():
            isi = json.loads(out.read_text(encoding="utf-8"))
            if isi.get("status") == "SIMULATED":
                return "SIMULASI dijalankan", "jalan"
            if isi.get("status") == "FAILED":
                return "gagal di adaptor", "batal"
        if sudah_tolak:
            return "rencana ditolak", "batal"
        if disetujui and i not in disetujui:
            return "tidak disetujui", "batal"
        return "", ""

    baris = "".join(
        render_aksi(i, a, paragraf, bisa_pilih, *status_aksi(i))
        for i, a in enumerate(payload["actions"])
    )

    diabaikan = "".join(
        f'<div class="abaikan">¶{esc(str(d["paragraf"]))} diabaikan — {esc(d["alasan"])}</div>'
        for d in payload.get("diabaikan") or []
    )

    if bisa_pilih:
        tombol = (
            f'<div class="baris">'
            f'<span class="identitas">Pemberi persetujuan: <b>{approver}</b> — {nama_approver}'
            " · ditetapkan server, bukan dari halaman</span>"
            '<button class="ok" type="submit" formaction="/setujui">Setujui yang dipilih</button>'
            '<button class="no" type="submit" formaction="/tolak">Tolak rencana</button>'
            "</div>"
            '<div class="foot">Centang tindakan yang disetujui. Yang tidak dicentang '
            "tidak akan pernah dijalankan. Identitas tidak bisa diubah dari halaman: "
            "server memakai sesi yang dibuatnya sendiri saat start.</div>"
        )
    elif sudah_tolak:
        tombol = '<div class="foot">Rencana ini sudah ditolak. Tidak ada yang dijalankan.</div>'
    elif status.startswith("EXECUTED"):
        tombol = '<div class="foot">Sudah dieksekusi sebagai simulasi.</div>'
    else:
        tombol = (
            f'<form method="post" action="/jalankan">'
            f'<input type="hidden" name="csrf" value="{csrf}">'
            '<div class="baris">'
            '<button class="run" type="submit">Jalankan simulasi</button>'
            "</div></form>"
        )

    hasil = f'<div class="hasil {esc(jenis_pesan)}">{esc(pesan)}</div>' if pesan else ""

    return f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CATATAN MUROJAAH — Persetujuan {esc(rec['plan_id'])}</title>
<style>{CSS}</style></head><body><div class="wrap">
<header><div class="brand">CATATAN <span>MUROJAAH</span></div>
<div class="sub">Layar persetujuan · satu halaman</div></header>

<div class="banner">Semua eksekusi berlabel SIMULASI. Tidak ada pesan, email, atau
undangan kalender sungguhan yang dikirim.<br>
Setiap nilai di kartu tindakan membawa asalnya: <b>SUMBER RAPAT</b> (diucapkan),
<b>TURUNAN DENGAN DASAR</b> (dihitung), <b>USULAN AGEN</b> (belum disetujui), dan
<b>KONFIRMASI PENGGUNA</b> (keputusan manusia, bukan ucapan rapat).</div>

<div class="card">
  <div class="meta">
    plan <b>{esc(rec['plan_id'])}</b> · versi <b>{rec['version']}</b> ·
    status <b>{esc(status)}</b><br>
    hash <b>{esc(hash_[:16])}…</b> · sumber <b>{esc(payload['source']['file'])}</b>
    ¶{esc(", ¶".join(str(x) for x in payload['source']['paragraf']))}
    {f"<br>keputusan pengguna oleh <b>{esc(payload.get('dijawab_oleh',''))}</b> — bukan ucapan rekaman" if payload.get('dijawab_oleh') else ""}
  </div>
</div>

{hasil}

<div class="card">
<h2>Tindakan dalam rencana</h2>
<form method="post" action="/setujui">
<input type="hidden" name="csrf" value="{csrf}">
<table>{baris}</table>
{diabaikan}
{tombol}
</form>
</div>

<div class="foot">
Halaman ini hanya jendela. Persetujuan dicatat oleh <code>gate.py</code> dengan
mengikat versi rencana dan hash isinya. Mengubah satu field setelah persetujuan
membatalkan persetujuan itu — termasuk mengubah berkas rencana langsung di disk.
</div>
</div></body></html>"""


# ---------------------------------------------------------------- server


def halaman_tolak(alasan: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8"><title>CATATAN MUROJAAH — ditolak</title>
<style>{CSS}</style></head><body><div class="wrap">
<header><div class="brand">CATATAN <span>MUROJAAH</span></div></div>
<div class="card"><h2>Permintaan ditolak</h2>
<p>{esc(alasan)}</p>
<div class="foot">Halaman persetujuan hanya menerima permintaan dari sesi yang dibuat
server saat start. Identitas pemberi persetujuan tidak diambil dari formulir maupun
dari JSON, sehingga mengubah nilai di browser tidak mengubah siapa yang menyetujui.</div>
</div></div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    root: Path = ROOT
    sesi: dict = {}

    def _kirim(self, isi: str, kode: int = 200) -> None:
        data = isi.encode("utf-8")
        self.send_response(kode)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _alihkan(self, pesan: str, jenis: str = "info") -> None:
        q = urllib.parse.urlencode({"pesan": pesan, "jenis": jenis})
        self.send_response(303)
        self.send_header("Location", f"/?{q}")
        self.end_headers()

    # ---- keamanan sesi ----

    def _host_sah(self) -> bool:
        """Tolak permintaan yang Host-nya bukan localhost (proteksi DNS rebinding)."""
        host = (self.headers.get("Host") or "").strip().lower()
        port = self.server.server_address[1]
        return host in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _sid(self) -> str:
        for bagian in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = bagian.strip().partition("=")
            if k == "tuntas_sid":
                return v
        return ""

    def _sesi_sah(self) -> bool:
        sid = self._sid()
        return bool(sid) and secrets.compare_digest(sid, self.sesi.get("sid", ""))

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_sah():
            self._kirim(halaman_tolak("Host tidak dikenal"), 403)
            return
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        kunci = (q.get("k") or [""])[0]

        if not self._sesi_sah():
            if kunci and secrets.compare_digest(kunci, self.sesi.get("sid", "")):
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header(
                    "Set-Cookie",
                    f"tuntas_sid={kunci}; HttpOnly; SameSite=Strict; Path=/",
                )
                self.end_headers()
                return
            self._kirim(halaman_tolak("Sesi tidak sah atau sudah berakhir"), 403)
            return

        pesan = (q.get("pesan") or [""])[0]
        jenis = (q.get("jenis") or ["info"])[0]
        self._kirim(halaman(self.root, pesan, jenis, self.sesi))

    def _buang_badan(self) -> None:
        """Baca dan buang badan permintaan sebelum menolak.

        Tanpa ini server menutup soket sementara masih ada data yang belum
        dibaca; Windows mengirim RST sehingga klien melihat
        `ConnectionAbortedError` alih-alih halaman 403 (terukur 1 Nov 2026,
        uji P07 yang gagal acak).
        """
        try:
            panjang = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            panjang = 0
        if panjang > 0:
            try:
                self.rfile.read(min(panjang, 1_000_000))
            except OSError:
                pass

    def do_POST(self) -> None:  # noqa: N802
        if not self._host_sah():
            self._buang_badan()
            self._kirim(halaman_tolak("Host tidak dikenal"), 403)
            return
        if not self._sesi_sah():
            self._buang_badan()
            self._kirim(halaman_tolak("Sesi tidak sah. Buka tautan yang dicetak server."), 403)
            return

        panjang = int(self.headers.get("Content-Length") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(panjang).decode("utf-8"))

        kirim = (form.get("csrf") or [""])[0]
        if not secrets.compare_digest(kirim, self.sesi.get("csrf", "")):
            Gate(self.root).catat("csrf_rejected", jalur=self.path)
            self._kirim(halaman_tolak("Token formulir tidak cocok"), 403)
            return

        rec = muat_plan(self.root)
        if rec is None:
            self._alihkan("Belum ada rencana.", "bad")
            return
        gate = Gate(self.root)
        pid, versi = rec["plan_id"], rec["version"]

        # Identitas SELALU dari sesi server. Kalau request mencoba mengirim
        # approver sendiri, nilainya dibuang dan percobaannya dicatat.
        approver = self.sesi.get("approver_id", "")
        if "approver" in form:
            gate.catat(
                "identity_from_request_ignored",
                dicoba=(form.get("approver") or [""])[0],
                dipakai=approver,
                jalur=self.path,
            )

        try:
            if self.path.startswith("/setujui"):
                pilih = [int(x) for x in form.get("aksi", [])]
                if not pilih:
                    self._alihkan("Tidak ada tindakan yang dicentang.", "bad")
                    return
                gate.approve(
                    pid, versi, gate.hash_sekarang(pid), approver,
                    action_ids=pilih, jalur="web", mode_uji=False,
                )
                self._alihkan(
                    f"Disetujui oleh {approver}: {len(pilih)} tindakan. "
                    "Belum ada yang dijalankan.",
                    "good",
                )
            elif self.path.startswith("/tolak"):
                gate.reject(pid, versi, approver, "Ditolak lewat layar persetujuan.")
                self._alihkan("Rencana ditolak. Tidak ada yang dijalankan.", "bad")
            elif self.path.startswith("/jalankan"):
                hasil = gate.execute(pid)
                self._alihkan(
                    f"SIMULASI: {hasil['dijalankan']} dijalankan, "
                    f"{hasil['dilewati']} dilewati, {hasil['gagal']} gagal. "
                    "Tidak ada pesan sungguhan yang terkirim.",
                    "good" if hasil["status_plan"] == "EXECUTED_MOCK" else "info",
                )
            else:
                self._alihkan("Alamat tidak dikenal.", "bad")
        except GateError as e:
            self._alihkan(f"Ditolak [{e.code}] {e.pesan}", "bad")

    def log_message(self, *args) -> None:  # senyap
        return


def buat_server(
    root: Path, port: int = 0, approver: str = "U-01"
) -> tuple[ThreadingHTTPServer, dict]:
    """Siapkan server + sesi. Identitas approver ditetapkan di sini, sekali."""
    izin = {r["user_id"]: r for r in daftar_approver(root)}
    if approver not in izin:
        raise SystemExit(f"{approver} tidak punya hak menyetujui di permissions.csv")

    sesi = {
        "sid": secrets.token_urlsafe(24),
        "csrf": secrets.token_urlsafe(24),
        "approver_id": approver,
        "nama": izin[approver]["nama"],
    }
    Handler.root = root
    Handler.sesi = sesi
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return srv, sesi


def main() -> int:
    p = argparse.ArgumentParser(description="Layar persetujuan CATATAN MUROJAAH")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument(
        "--approver",
        default="U-01",
        help="user_id yang akan tercatat menyetujui. Ditetapkan saat server start.",
    )
    a = p.parse_args()

    root = Path(a.run_dir).resolve()
    if not (root / "plans").exists():
        print(f"Folder kerja tidak berisi plans/: {root}")
        return 2

    srv, sesi = buat_server(root, a.port, a.approver)
    port = srv.server_address[1]
    print(f"CATATAN MUROJAAH · layar persetujuan → http://127.0.0.1:{port}/?k={sesi['sid']}")
    print(f"Folder kerja : {root}")
    print(f"Approver     : {sesi['approver_id']} — {sesi['nama']} (ditetapkan server)")
    print("Tautan di atas membawa kunci sesi. Tanpa kunci itu, halaman menolak.")
    print("Batas: ini sesi lokal, bukan autentikasi produksi. Lihat RUNBOOK.md.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nberhenti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
