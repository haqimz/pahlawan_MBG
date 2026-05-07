"""
main.py – MBG Stock Management 
Backend FastAPI lengkap: prediksi restock, manajemen inventory,
penjadwalan produksi, laporan, dan notifikasi stok MBG.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import numpy as np
import pandas as pd
import joblib
import os
import json

app = FastAPI(
    title="MBG Stock Management API",
    description=(
        "API lengkap untuk sistem Makan Bergizi Gratis (MBG): "
        "prediksi restock, manajemen inventory, penjadwalan produksi, laporan & notifikasi."
    ),
    version="2.0.0",
)

# ══════════════════════════════════════════════════════════════════════
# LOAD MODEL ARTIFACTS
# ══════════════════════════════════════════════════════════════════════
ARTIFACT_DIR = "model_artifacts"

try:
    model_reg = joblib.load(os.path.join(ARTIFACT_DIR, "model_regresi.pkl"))
    model_clf = joblib.load(os.path.join(ARTIFACT_DIR, "model_klasifikasi.pkl"))
    le        = joblib.load(os.path.join(ARTIFACT_DIR, "label_encoder.pkl"))
    FEAT_REG  = joblib.load(os.path.join(ARTIFACT_DIR, "feat_reg.pkl"))
    FEAT_CLF  = joblib.load(os.path.join(ARTIFACT_DIR, "feat_clf.pkl"))
except FileNotFoundError as e:
    raise RuntimeError(
        f"Model artifact tidak ditemukan: {e}. "
        "Pastikan folder model_artifacts/ sudah berisi file pkl hasil training."
    )

VOL_MAX_CLIP = 70_000

# ══════════════════════════════════════════════════════════════════════
# IN-MEMORY DATABASE  (JSON flat-file — ganti SQLite/PostgreSQL di prod)
# ══════════════════════════════════════════════════════════════════════
DATA_FILE = "mbg_data.json"

def _load_db() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "inventory"         : [],
        "riwayat_stok"      : [],
        "jadwal_produksi"   : [],
        "menu"              : [],
        "histori_prediksi"  : [],
        "notifikasi"        : [],
    }

def _save_db(db: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(db, f, ensure_ascii=False, indent=2, default=str)

def _next_id(collection: list) -> int:
    return max((item.get("id", 0) for item in collection), default=0) + 1

PESAN_STATUS = {
    "AMAN"    : "Stok bahan dalam kondisi aman. Lanjutkan pemantauan berkala.",
    "WASPADA" : "Stok mulai menipis. Pantau ketat dan rencanakan restock segera.",
    "KRITIS"  : "Stok kritis! Segera lakukan restock untuk menghindari kekurangan bahan.",
}

# ══════════════════════════════════════════════════════════════════════
# SCHEMAS
# ══════════════════════════════════════════════════════════════════════

class InputPrediksi(BaseModel):
    nama_bahan  : str
    periode_idx : int   = Field(..., ge=1,  le=200)
    bulan_ord   : int   = Field(..., ge=4,  le=100,
                                description="Ordinal bulan: 4=Mar2026, 5=Apr2026 dst (1-3=training)")
    minggu_ord  : int   = Field(..., ge=1,  le=4)
    vol_lag1    : float = Field(..., ge=0,  le=70000)
    vol_lag2    : float = Field(..., ge=0,  le=70000)
    vol_ma2     : float = Field(..., ge=0,  le=70000)

    @field_validator("periode_idx")
    @classmethod
    def cek_periode(cls, v, info):
        d = info.data
        if "bulan_ord" in d and "minggu_ord" in d:
            exp = (d["bulan_ord"] - 1) * 4 + d["minggu_ord"]
            if v != exp:
                raise ValueError(f"periode_idx={v} seharusnya {exp}")
        return v

    @field_validator("vol_ma2")
    @classmethod
    def cek_ma2(cls, v, info):
        d = info.data
        if "vol_lag1" in d and "vol_lag2" in d:
            rata = (d["vol_lag1"] + d["vol_lag2"]) / 2
            if rata > 0 and not (rata * 0.5 <= v <= rata * 1.5):
                raise ValueError(f"vol_ma2={v} tidak konsisten dengan rata-rata lag ({rata:.1f})")
        return v


class BahanMakanan(BaseModel):
    nama           : str
    satuan         : str   = "unit"
    stok_saat_ini  : float = 0.0
    stok_minimum   : float = 100.0
    stok_maksimum  : float = 10000.0
    kategori       : str   = "Umum"
    harga_per_unit : float = 0.0
    supplier       : str   = ""
    keterangan     : str   = ""

class UpdateBahan(BaseModel):
    nama           : Optional[str]   = None
    satuan         : Optional[str]   = None
    stok_saat_ini  : Optional[float] = None
    stok_minimum   : Optional[float] = None
    stok_maksimum  : Optional[float] = None
    kategori       : Optional[str]   = None
    harga_per_unit : Optional[float] = None
    supplier       : Optional[str]   = None
    keterangan     : Optional[str]   = None

class TransaksiStok(BaseModel):
    nama_bahan  : str
    jenis       : str   = Field(..., description="'masuk' atau 'keluar'")
    jumlah      : float = Field(..., gt=0)
    keterangan  : str   = ""
    tanggal     : str   = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator("jenis")
    @classmethod
    def cek_jenis(cls, v):
        if v not in ("masuk", "keluar"):
            raise ValueError("jenis harus 'masuk' atau 'keluar'")
        return v


class KomposisiBahan(BaseModel):
    nama_bahan        : str
    jumlah_per_porsi  : float
    satuan            : str = "gram"

class Menu(BaseModel):
    nama_menu   : str
    deskripsi   : str = ""
    komposisi   : List[KomposisiBahan]
    kategori    : str = "Makanan Utama"

class UpdateMenu(BaseModel):
    nama_menu : Optional[str]               = None
    deskripsi : Optional[str]               = None
    komposisi : Optional[List[KomposisiBahan]] = None
    kategori  : Optional[str]               = None


class JadwalProduksi(BaseModel):
    tanggal              : str  = Field(..., description="Format: YYYY-MM-DD")
    sesi                 : str  = Field(..., description="'pagi', 'siang', atau 'sore'")
    nama_menu            : str
    jumlah_porsi         : int  = Field(..., gt=0)
    lokasi_distribusi    : str  = ""
    penanggung_jawab     : str  = ""
    keterangan           : str  = ""


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════

def _hitung_status_stok(bahan: dict) -> str:
    stok     = bahan.get("stok_saat_ini", 0)
    minimum  = bahan.get("stok_minimum", 100)
    maksimum = bahan.get("stok_maksimum", 10000)
    if stok <= minimum:
        return "KRITIS"
    elif maksimum > 0 and stok / maksimum < 0.3:
        return "WASPADA"
    return "AMAN"

def _buat_notifikasi(db: dict, tipe: str, pesan: str, bahan: str = ""):
    db["notifikasi"].append({
        "id"     : _next_id(db["notifikasi"]),
        "tipe"   : tipe,
        "pesan"  : pesan,
        "bahan"  : bahan,
        "waktu"  : datetime.now().isoformat(),
        "dibaca" : False,
    })

def _cek_dan_notif_stok(db: dict, bahan: dict):
    status = _hitung_status_stok(bahan)
    nama   = bahan["nama"]
    if status == "KRITIS":
        _buat_notifikasi(db, "KRITIS",
            f"⚠️ Stok {nama} KRITIS ({bahan['stok_saat_ini']} {bahan['satuan']}). Segera restock!", nama)
    elif status == "WASPADA":
        _buat_notifikasi(db, "WASPADA",
            f"⚡ Stok {nama} mulai menipis ({bahan['stok_saat_ini']} {bahan['satuan']}). Rencanakan restock.", nama)


# ══════════════════════════════════════════════════════════════════════
# HEALTH
# ══════════════════════════════════════════════════════════════════════

@app.get("/", tags=["Health"])
def root():
    return {
        "status"  : "MBG API v2.0 aktif",
        "fitur"   : ["prediksi", "inventory", "menu", "jadwal_produksi", "laporan", "notifikasi"],
        "keterangan_periode": "bulan_ord 1-3=data training (Des25-Feb26); prediksi mulai bulan_ord 4 (Mar26+)",
    }

@app.get("/health", tags=["Health"])
def health():
    return {
        "model_regresi_siap"    : model_reg is not None,
        "model_klasifikasi_siap": model_clf is not None,
        "kelas_yang_dikenali"   : le.classes_.tolist(),
    }


# ══════════════════════════════════════════════════════════════════════
# PREDIKSI
# ══════════════════════════════════════════════════════════════════════

@app.post("/predict", tags=["Prediksi"])
def predict(data: InputPrediksi):
    """Prediksi volume restock & status stok; simpan ke histori prediksi."""
    try:
        X_reg = pd.DataFrame(
            [[data.periode_idx, data.bulan_ord, data.minggu_ord,
              data.vol_lag1, data.vol_lag2, data.vol_ma2]],
            columns=FEAT_REG,
        )
        vol_raw = model_reg.predict(X_reg)[0]
        vol = int(np.clip(vol_raw, 0, VOL_MAX_CLIP))

        X_clf = pd.DataFrame(
            [[data.vol_lag1, data.vol_lag2, data.vol_ma2,
              data.bulan_ord, data.minggu_ord]],
            columns=FEAT_CLF,
        )
        status_encoded = model_clf.predict(X_clf)[0]
        status = le.inverse_transform([status_encoded])[0]
        pesan  = PESAN_STATUS.get(status, "Status tidak dikenali.")

        db = _load_db()
        record = {
            "id"              : _next_id(db["histori_prediksi"]),
            "nama_bahan"      : data.nama_bahan,
            "bulan_ord"       : data.bulan_ord,
            "minggu_ord"      : data.minggu_ord,
            "periode_idx"     : data.periode_idx,
            "vol_lag1"        : data.vol_lag1,
            "vol_lag2"        : data.vol_lag2,
            "vol_ma2"         : data.vol_ma2,
            "volume_prediksi" : vol,
            "status_stok"     : status,
            "waktu_prediksi"  : datetime.now().isoformat(),
        }
        db["histori_prediksi"].append(record)
        if status in ("KRITIS", "WASPADA"):
            _buat_notifikasi(db, status, f"Prediksi {data.nama_bahan}: {pesan}", data.nama_bahan)
        _save_db(db)

        return {
            "volume_prediksi" : vol,
            "status_stok"     : status,
            "pesan"           : pesan,
            "detail": {
                "vol_raw_sebelum_clip": round(float(vol_raw), 2),
                "input_periode_idx"  : data.periode_idx,
                "input_bulan_ord"    : data.bulan_ord,
                "input_minggu_ord"   : data.minggu_ord,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kesalahan prediksi: {str(e)}")


@app.get("/predict/histori", tags=["Prediksi"])
def get_histori_prediksi(nama_bahan: Optional[str] = None, limit: int = 50):
    """Ambil histori semua prediksi yang pernah dilakukan."""
    db = _load_db()
    data = db["histori_prediksi"]
    if nama_bahan:
        data = [d for d in data if d["nama_bahan"].lower() == nama_bahan.lower()]
    return {"total": len(data), "data": data[-limit:][::-1]}


# ══════════════════════════════════════════════════════════════════════
# INVENTORY
# ══════════════════════════════════════════════════════════════════════

@app.get("/inventory", tags=["Inventory"])
def get_inventory(kategori: Optional[str] = None, status: Optional[str] = None):
    db = _load_db()
    data = db["inventory"]
    for b in data:
        b["status_stok"] = _hitung_status_stok(b)
    if kategori:
        data = [b for b in data if b.get("kategori", "").lower() == kategori.lower()]
    if status:
        data = [b for b in data if b.get("status_stok", "").upper() == status.upper()]
    return {"total": len(data), "data": data}


@app.post("/inventory", tags=["Inventory"], status_code=201)
def tambah_bahan(bahan: BahanMakanan):
    db = _load_db()
    if any(b["nama"].lower() == bahan.nama.lower() for b in db["inventory"]):
        raise HTTPException(status_code=400, detail=f"Bahan '{bahan.nama}' sudah ada.")
    record = {"id": _next_id(db["inventory"]), **bahan.model_dump()}
    db["inventory"].append(record)
    _cek_dan_notif_stok(db, record)
    _save_db(db)
    return {"pesan": f"Bahan '{bahan.nama}' berhasil ditambahkan.", "data": record}


@app.put("/inventory/{bahan_id}", tags=["Inventory"])
def edit_bahan(bahan_id: int, update: UpdateBahan):
    db = _load_db()
    for b in db["inventory"]:
        if b["id"] == bahan_id:
            for k, v in update.model_dump(exclude_none=True).items():
                b[k] = v
            b["status_stok"] = _hitung_status_stok(b)
            _cek_dan_notif_stok(db, b)
            _save_db(db)
            return {"pesan": "Berhasil diperbarui.", "data": b}
    raise HTTPException(status_code=404, detail=f"Bahan ID {bahan_id} tidak ditemukan.")


@app.delete("/inventory/{bahan_id}", tags=["Inventory"])
def hapus_bahan(bahan_id: int):
    db = _load_db()
    before = len(db["inventory"])
    db["inventory"] = [b for b in db["inventory"] if b["id"] != bahan_id]
    if len(db["inventory"]) == before:
        raise HTTPException(status_code=404, detail=f"Bahan ID {bahan_id} tidak ditemukan.")
    _save_db(db)
    return {"pesan": f"Bahan ID {bahan_id} berhasil dihapus."}


@app.post("/inventory/transaksi", tags=["Inventory"])
def transaksi_stok(tx: TransaksiStok):
    """Catat stok masuk/keluar; update stok dan riwayat otomatis."""
    db = _load_db()
    bahan = next((b for b in db["inventory"]
                  if b["nama"].lower() == tx.nama_bahan.lower()), None)
    if not bahan:
        raise HTTPException(status_code=404, detail=f"Bahan '{tx.nama_bahan}' tidak ada di inventory.")

    stok_sebelum = bahan["stok_saat_ini"]
    if tx.jenis == "masuk":
        bahan["stok_saat_ini"] += tx.jumlah
    else:
        if bahan["stok_saat_ini"] < tx.jumlah:
            raise HTTPException(status_code=400,
                detail=f"Stok tidak cukup. Tersedia: {bahan['stok_saat_ini']}, diminta: {tx.jumlah}")
        bahan["stok_saat_ini"] -= tx.jumlah

    bahan["status_stok"] = _hitung_status_stok(bahan)
    db["riwayat_stok"].append({
        "id"           : _next_id(db["riwayat_stok"]),
        "nama_bahan"   : tx.nama_bahan,
        "jenis"        : tx.jenis,
        "jumlah"       : tx.jumlah,
        "stok_sebelum" : stok_sebelum,
        "stok_sesudah" : bahan["stok_saat_ini"],
        "keterangan"   : tx.keterangan,
        "tanggal"      : tx.tanggal,
    })
    _cek_dan_notif_stok(db, bahan)
    _save_db(db)
    return {
        "pesan"        : f"Stok {tx.nama_bahan} berhasil diperbarui.",
        "stok_sebelum" : stok_sebelum,
        "stok_sesudah" : bahan["stok_saat_ini"],
        "status_stok"  : bahan["status_stok"],
    }


@app.get("/inventory/riwayat", tags=["Inventory"])
def get_riwayat_stok(nama_bahan: Optional[str] = None, jenis: Optional[str] = None, limit: int = 100):
    db = _load_db()
    data = db["riwayat_stok"]
    if nama_bahan:
        data = [r for r in data if r["nama_bahan"].lower() == nama_bahan.lower()]
    if jenis:
        data = [r for r in data if r["jenis"] == jenis]
    return {"total": len(data), "data": data[-limit:][::-1]}


# ══════════════════════════════════════════════════════════════════════
# MENU
# ══════════════════════════════════════════════════════════════════════

@app.get("/menu", tags=["Menu"])
def get_menu():
    db = _load_db()
    return {"total": len(db["menu"]), "data": db["menu"]}


@app.post("/menu", tags=["Menu"], status_code=201)
def tambah_menu(menu: Menu):
    db = _load_db()
    if any(m["nama_menu"].lower() == menu.nama_menu.lower() for m in db["menu"]):
        raise HTTPException(status_code=400, detail=f"Menu '{menu.nama_menu}' sudah ada.")
    record = {"id": _next_id(db["menu"]), **menu.model_dump()}
    db["menu"].append(record)
    _save_db(db)
    return {"pesan": f"Menu '{menu.nama_menu}' berhasil ditambahkan.", "data": record}


@app.put("/menu/{menu_id}", tags=["Menu"])
def edit_menu(menu_id: int, update: UpdateMenu):
    db = _load_db()
    for m in db["menu"]:
        if m["id"] == menu_id:
            for k, v in update.model_dump(exclude_none=True).items():
                m[k] = v
            _save_db(db)
            return {"pesan": "Menu berhasil diperbarui.", "data": m}
    raise HTTPException(status_code=404, detail=f"Menu ID {menu_id} tidak ditemukan.")


@app.delete("/menu/{menu_id}", tags=["Menu"])
def hapus_menu(menu_id: int):
    db = _load_db()
    before = len(db["menu"])
    db["menu"] = [m for m in db["menu"] if m["id"] != menu_id]
    if len(db["menu"]) == before:
        raise HTTPException(status_code=404, detail=f"Menu ID {menu_id} tidak ditemukan.")
    _save_db(db)
    return {"pesan": f"Menu ID {menu_id} berhasil dihapus."}


# ══════════════════════════════════════════════════════════════════════
# JADWAL PRODUKSI
# ══════════════════════════════════════════════════════════════════════

@app.get("/jadwal", tags=["Jadwal Produksi"])
def get_jadwal(tanggal_mulai: Optional[str] = None, tanggal_selesai: Optional[str] = None):
    db = _load_db()
    data = db["jadwal_produksi"]
    if tanggal_mulai:
        data = [j for j in data if j["tanggal"] >= tanggal_mulai]
    if tanggal_selesai:
        data = [j for j in data if j["tanggal"] <= tanggal_selesai]
    return {"total": len(data), "data": sorted(data, key=lambda x: (x["tanggal"], x.get("sesi", "")))}


@app.post("/jadwal", tags=["Jadwal Produksi"], status_code=201)
def tambah_jadwal(jadwal: JadwalProduksi):
    """Tambah jadwal produksi; hitung kebutuhan bahan & cek kecukupan stok."""
    db = _load_db()
    menu = next((m for m in db["menu"]
                 if m["nama_menu"].lower() == jadwal.nama_menu.lower()), None)
    if not menu:
        raise HTTPException(status_code=404,
            detail=f"Menu '{jadwal.nama_menu}' tidak ditemukan. Tambahkan menu terlebih dahulu.")

    kebutuhan = []
    peringatan_stok = []
    for k in menu["komposisi"]:
        total = k["jumlah_per_porsi"] * jadwal.jumlah_porsi
        bahan = next((b for b in db["inventory"]
                      if b["nama"].lower() == k["nama_bahan"].lower()), None)
        stok_tersedia = bahan["stok_saat_ini"] if bahan else 0
        cukup = stok_tersedia >= total
        if not cukup:
            peringatan_stok.append(
                f"{k['nama_bahan']}: butuh {total} {k['satuan']}, tersedia {stok_tersedia}")
        kebutuhan.append({
            "nama_bahan"        : k["nama_bahan"],
            "jumlah_dibutuhkan" : total,
            "satuan"            : k["satuan"],
            "stok_tersedia"     : stok_tersedia,
            "cukup"             : cukup,
        })

    record = {
        "id"                : _next_id(db["jadwal_produksi"]),
        "tanggal"           : jadwal.tanggal,
        "sesi"              : jadwal.sesi,
        "nama_menu"         : jadwal.nama_menu,
        "jumlah_porsi"      : jadwal.jumlah_porsi,
        "lokasi_distribusi" : jadwal.lokasi_distribusi,
        "penanggung_jawab"  : jadwal.penanggung_jawab,
        "keterangan"        : jadwal.keterangan,
        "kebutuhan_bahan"   : kebutuhan,
        "status"            : "terjadwal",
        "created_at"        : datetime.now().isoformat(),
    }
    db["jadwal_produksi"].append(record)

    for pw in peringatan_stok:
        _buat_notifikasi(db, "WASPADA",
            f"Stok kurang untuk jadwal {jadwal.tanggal} ({jadwal.nama_menu}): {pw}")

    _save_db(db)
    return {
        "pesan"           : "Jadwal produksi berhasil ditambahkan.",
        "data"            : record,
        "peringatan_stok" : peringatan_stok,
    }


@app.post("/jadwal/{jadwal_id}/selesai", tags=["Jadwal Produksi"])
def tandai_selesai(jadwal_id: int, kurangi_stok: bool = True):
    """Tandai jadwal selesai; kurangi stok bahan otomatis jika kurangi_stok=True."""
    db = _load_db()
    jadwal = next((j for j in db["jadwal_produksi"] if j["id"] == jadwal_id), None)
    if not jadwal:
        raise HTTPException(status_code=404, detail=f"Jadwal ID {jadwal_id} tidak ditemukan.")
    if jadwal["status"] == "selesai":
        raise HTTPException(status_code=400, detail="Jadwal sudah ditandai selesai.")

    log_transaksi = []
    if kurangi_stok:
        for kb in jadwal.get("kebutuhan_bahan", []):
            bahan = next((b for b in db["inventory"]
                          if b["nama"].lower() == kb["nama_bahan"].lower()), None)
            if bahan:
                stok_sebelum = bahan["stok_saat_ini"]
                bahan["stok_saat_ini"] = max(0, bahan["stok_saat_ini"] - kb["jumlah_dibutuhkan"])
                bahan["status_stok"] = _hitung_status_stok(bahan)
                db["riwayat_stok"].append({
                    "id"          : _next_id(db["riwayat_stok"]),
                    "nama_bahan"  : bahan["nama"],
                    "jenis"       : "keluar",
                    "jumlah"      : kb["jumlah_dibutuhkan"],
                    "stok_sebelum": stok_sebelum,
                    "stok_sesudah": bahan["stok_saat_ini"],
                    "keterangan"  : f"Produksi jadwal ID {jadwal_id}: {jadwal['nama_menu']}",
                    "tanggal"     : datetime.now().isoformat(),
                })
                _cek_dan_notif_stok(db, bahan)
                log_transaksi.append({
                    "bahan"    : bahan["nama"],
                    "dikurangi": kb["jumlah_dibutuhkan"],
                    "stok_sisa": bahan["stok_saat_ini"],
                })

    jadwal["status"]     = "selesai"
    jadwal["selesai_at"] = datetime.now().isoformat()
    _save_db(db)
    return {
        "pesan"         : f"Jadwal ID {jadwal_id} ditandai selesai.",
        "log_transaksi" : log_transaksi,
    }


@app.delete("/jadwal/{jadwal_id}", tags=["Jadwal Produksi"])
def hapus_jadwal(jadwal_id: int):
    db = _load_db()
    before = len(db["jadwal_produksi"])
    db["jadwal_produksi"] = [j for j in db["jadwal_produksi"] if j["id"] != jadwal_id]
    if len(db["jadwal_produksi"]) == before:
        raise HTTPException(status_code=404, detail=f"Jadwal ID {jadwal_id} tidak ditemukan.")
    _save_db(db)
    return {"pesan": f"Jadwal ID {jadwal_id} berhasil dihapus."}


# ══════════════════════════════════════════════════════════════════════
# LAPORAN
# ══════════════════════════════════════════════════════════════════════

@app.get("/laporan/ringkasan-stok", tags=["Laporan"])
def laporan_ringkasan_stok():
    db = _load_db()
    inv = db["inventory"]
    for b in inv:
        b["status_stok"] = _hitung_status_stok(b)
    aman    = [b for b in inv if b["status_stok"] == "AMAN"]
    waspada = [b for b in inv if b["status_stok"] == "WASPADA"]
    kritis  = [b for b in inv if b["status_stok"] == "KRITIS"]
    return {
        "total_bahan"   : len(inv),
        "aman"          : len(aman),
        "waspada"       : len(waspada),
        "kritis"        : len(kritis),
        "bahan_kritis"  : [{"nama": b["nama"], "stok": b["stok_saat_ini"], "satuan": b["satuan"]} for b in kritis],
        "bahan_waspada" : [{"nama": b["nama"], "stok": b["stok_saat_ini"], "satuan": b["satuan"]} for b in waspada],
    }


@app.get("/laporan/penggunaan-bahan", tags=["Laporan"])
def laporan_penggunaan_bahan(tanggal_mulai: Optional[str] = None, tanggal_selesai: Optional[str] = None):
    db = _load_db()
    riwayat = db["riwayat_stok"]
    if tanggal_mulai:
        riwayat = [r for r in riwayat if r["tanggal"] >= tanggal_mulai]
    if tanggal_selesai:
        riwayat = [r for r in riwayat if r["tanggal"] <= tanggal_selesai]
    rekap: dict = {}
    for r in riwayat:
        n = r["nama_bahan"]
        if n not in rekap:
            rekap[n] = {"nama_bahan": n, "total_masuk": 0.0, "total_keluar": 0.0, "frekuensi": 0}
        rekap[n]["total_masuk"  if r["jenis"] == "masuk" else "total_keluar"] += r["jumlah"]
        rekap[n]["frekuensi"] += 1
    return {
        "periode" : {"mulai": tanggal_mulai, "selesai": tanggal_selesai},
        "data"    : sorted(rekap.values(), key=lambda x: x["total_keluar"], reverse=True),
    }


@app.get("/laporan/jadwal-produksi", tags=["Laporan"])
def laporan_jadwal():
    db = _load_db()
    jadwal    = db["jadwal_produksi"]
    selesai   = [j for j in jadwal if j.get("status") == "selesai"]
    terjadwal = [j for j in jadwal if j.get("status") == "terjadwal"]
    return {
        "total_jadwal"           : len(jadwal),
        "terjadwal"              : len(terjadwal),
        "selesai"                : len(selesai),
        "total_porsi_diproduksi" : sum(j["jumlah_porsi"] for j in selesai),
        "jadwal_mendatang"       : sorted(terjadwal, key=lambda x: x["tanggal"])[:5],
    }


@app.get("/laporan/histori-prediksi-ringkasan", tags=["Laporan"])
def laporan_prediksi():
    db = _load_db()
    hist = db["histori_prediksi"]
    if not hist:
        return {"pesan": "Belum ada data prediksi.", "data": []}
    df = pd.DataFrame(hist)
    rekap = df.groupby("nama_bahan").agg(
        jumlah_prediksi   = ("id", "count"),
        rata_vol_prediksi = ("volume_prediksi", "mean"),
        terakhir_prediksi = ("waktu_prediksi", "max"),
    ).reset_index().to_dict(orient="records")
    return {
        "total_prediksi"    : len(hist),
        "distribusi_status" : df["status_stok"].value_counts().to_dict(),
        "per_bahan"         : rekap,
    }


# ══════════════════════════════════════════════════════════════════════
# NOTIFIKASI
# ══════════════════════════════════════════════════════════════════════

@app.get("/notifikasi", tags=["Notifikasi"])
def get_notifikasi(hanya_belum_dibaca: bool = False):
    db = _load_db()
    data = db["notifikasi"]
    if hanya_belum_dibaca:
        data = [n for n in data if not n["dibaca"]]
    return {"total": len(data), "belum_dibaca": sum(1 for n in db["notifikasi"] if not n["dibaca"]), "data": data[::-1]}


@app.post("/notifikasi/{notif_id}/baca", tags=["Notifikasi"])
def tandai_baca(notif_id: int):
    db = _load_db()
    for n in db["notifikasi"]:
        if n["id"] == notif_id:
            n["dibaca"] = True
            _save_db(db)
            return {"pesan": f"Notifikasi ID {notif_id} ditandai dibaca."}
    raise HTTPException(status_code=404, detail=f"Notifikasi ID {notif_id} tidak ditemukan.")


@app.post("/notifikasi/baca-semua", tags=["Notifikasi"])
def tandai_baca_semua():
    db = _load_db()
    for n in db["notifikasi"]:
        n["dibaca"] = True
    _save_db(db)
    return {"pesan": "Semua notifikasi ditandai dibaca."}


@app.delete("/notifikasi/hapus-semua", tags=["Notifikasi"])
def hapus_semua_notifikasi():
    db = _load_db()
    db["notifikasi"] = []
    _save_db(db)
    return {"pesan": "Semua notifikasi dihapus."}
