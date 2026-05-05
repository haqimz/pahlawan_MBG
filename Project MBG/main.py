"""
main.py – MBG Stock Prediction API
Backend FastAPI untuk prediksi volume restock dan klasifikasi status stok.
Model dimuat dari model_artifacts/ (output Bagian 3 notebook).
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
import numpy as np
import pandas as pd
import joblib
import os

app = FastAPI(
    title="MBG Stock Prediction API",
    description=(
        "API prediksi kebutuhan restock bahan makanan dan klasifikasi status stok "
        "untuk program Makan Bergizi Gratis (MBG). "
        "Menggunakan model Random Forest (regresi) dan Decision Tree / Gradient Boosting (klasifikasi)."
    ),
    version="1.0.0",
)

# ── Load Model Artifacts ───────────────────────────────────────────────────────
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
        "Pastikan folder model_artifacts/ sudah berisi file pkl hasil training Bagian 3."
    )

# Batas atas prediksi volume yang masuk akal untuk konteks MBG
# (max historis Pisang = 34.880, beri buffer 2x)
VOL_MAX_CLIP = 70_000

# ── Schema Input ───────────────────────────────────────────────────────────────
class InputData(BaseModel):
    periode_idx: int   = Field(..., ge=1,  le=200,  description="Indeks periode waktu linear (dihitung otomatis dari bulan+minggu)")
    bulan_ord:   int   = Field(..., ge=4,  le=100,  description="Ordinal bulan prediksi: 4=Mar2026, 5=Apr2026, dst. (1–3 adalah data training)")
    minggu_ord:  int   = Field(..., ge=1, le=4,     description="Minggu dalam bulan (1–4)")
    vol_lag1:    float = Field(..., ge=0, le=70000, description="Volume beli periode terakhir (unit)")
    vol_lag2:    float = Field(..., ge=0, le=70000, description="Volume beli 2 periode lalu (unit)")
    vol_ma2:     float = Field(..., ge=0, le=70000, description="Moving average volume 2 periode terakhir")

    @field_validator("periode_idx")
    @classmethod
    def cek_periode_konsisten(cls, v, info):
        """Validasi periode_idx konsisten dengan bulan_ord dan minggu_ord jika keduanya ada."""
        data = info.data
        if "bulan_ord" in data and "minggu_ord" in data:
            expected = (data["bulan_ord"] - 1) * 4 + data["minggu_ord"]
            if v != expected:
                raise ValueError(
                    f"periode_idx={v} tidak konsisten dengan "
                    f"bulan_ord={data['bulan_ord']}, minggu_ord={data['minggu_ord']}. "
                    f"Seharusnya {expected}."
                )
        return v

    @field_validator("vol_ma2")
    @classmethod
    def cek_ma2_wajar(cls, v, info):
        """vol_ma2 seharusnya mendekati rata-rata lag1 dan lag2."""
        data = info.data
        if "vol_lag1" in data and "vol_lag2" in data:
            rata = (data["vol_lag1"] + data["vol_lag2"]) / 2
            # Toleransi ±50% dari rata-rata; jika 0 semua, lewati
            if rata > 0 and not (rata * 0.5 <= v <= rata * 1.5):
                raise ValueError(
                    f"vol_ma2={v} tampak tidak konsisten dengan rata-rata lag1+lag2 ({rata:.1f}). "
                    "Periksa kembali nilai yang dimasukkan."
                )
        return v


# ── Pesan Status ───────────────────────────────────────────────────────────────
PESAN_STATUS = {
    "AMAN"    : "Stok bahan dalam kondisi aman. Lanjutkan pemantauan berkala.",
    "WASPADA" : "Stok mulai menipis. Pantau ketat dan rencanakan restock dalam waktu dekat.",
    "KRITIS"  : "Stok kritis! Segera lakukan restock untuk menghindari kekurangan bahan produksi.",
}

# ── Endpoints ──────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "status"     : "MBG API aktif",
        "versi"      : "1.0.0",
        "model_reg"  : type(model_reg).__name__,
        "model_clf"  : type(model_clf).__name__,
        "fitur_reg"  : FEAT_REG,
        "fitur_clf"  : FEAT_CLF,
        "keterangan_bulan"  : "bulan_ord 1–3 = data training (Des2025–Feb2026); prediksi mulai bulan_ord 4 (Mar2026+)",
        "kelas_stok" : le.classes_.tolist(),
    }


@app.post("/predict", tags=["Prediksi"])
def predict(data: InputData):
    """
    Prediksi volume restock dan status stok untuk satu bahan makanan.

    **Alur:**
    1. Bangun DataFrame fitur regresi → prediksi VOL_TOTAL (Random Forest Regressor)
    2. Bangun DataFrame fitur klasifikasi (LAG & MA saja, **tanpa VOL_TOTAL** untuk menghindari leakage)
       → prediksi STATUS_STOK (Decision Tree / Gradient Boosting)
    3. Kembalikan volume, status, dan pesan rekomendasi.
    """
    try:
        # ── Problem A: Regresi Volume ──────────────────────────────────────────
        # Fitur: PERIODE_IDX, BULAN_ORD, MINGGU_ORD, VOL_LAG1, VOL_LAG2, VOL_MA2
        X_reg = pd.DataFrame(
            [[data.periode_idx, data.bulan_ord, data.minggu_ord,
              data.vol_lag1, data.vol_lag2, data.vol_ma2]],
            columns=FEAT_REG,
        )
        vol_raw = model_reg.predict(X_reg)[0]

        # Clip ke rentang wajar [0, VOL_MAX_CLIP] — cegah prediksi negatif atau tidak wajar
        vol = int(np.clip(vol_raw, 0, VOL_MAX_CLIP))

        # ── Problem B: Klasifikasi Status Stok ────────────────────────────────
        # PENTING: Fitur klasifikasi TIDAK menyertakan VOL_TOTAL (hasil regresi di atas)
        # karena STATUS_STOK di training dibuat dari VOL_TOTAL → menyebabkan data leakage.
        # Gunakan hanya fitur historis: VOL_LAG1, VOL_LAG2, VOL_MA2, BULAN_ORD, MINGGU_ORD
        X_clf = pd.DataFrame(
            [[data.vol_lag1, data.vol_lag2, data.vol_ma2,
              data.bulan_ord, data.minggu_ord]],
            columns=FEAT_CLF,
        )
        status_encoded = model_clf.predict(X_clf)[0]
        status = le.inverse_transform([status_encoded])[0]

        # Ambil pesan; fallback aman jika label di luar ekspektasi
        pesan = PESAN_STATUS.get(
            status,
            "Status tidak dikenali. Periksa model klasifikasi.",
        )

        return {
            "volume_prediksi" : vol,
            "status_stok"     : status,
            "pesan"           : pesan,
            # Info tambahan untuk debugging / transparansi
            "detail": {
                "vol_raw_sebelum_clip" : round(float(vol_raw), 2),
                "input_periode_idx"    : data.periode_idx,
                "input_bulan_ord"      : data.bulan_ord,
                "input_minggu_ord"     : data.minggu_ord,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kesalahan prediksi: {str(e)}")


@app.get("/health", tags=["Health"])
def health():
    """Cek apakah model berhasil dimuat dan siap melayani prediksi."""
    return {
        "model_regresi_siap"    : model_reg is not None,
        "model_klasifikasi_siap": model_clf is not None,
        "label_encoder_siap"    : le is not None,
        "kelas_yang_dikenali"   : le.classes_.tolist(),
    }