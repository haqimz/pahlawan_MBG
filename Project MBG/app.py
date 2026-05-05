"""
app.py – Sistem Monitoring Stok MBG
Frontend Streamlit untuk prediksi volume restock dan status stok bahan makanan.
Terhubung ke FastAPI (main.py) melalui REST API.
"""

import streamlit as st
import requests

# ── Konfigurasi ────────────────────────────────────────────────────────────────
API_URL = "https://pahlawanmbg.up.railway.app/predict"

# ── Daftar item yang ada di dataset (dari normalisasi Bagian 2) ────────────────
DAFTAR_ITEM = sorted([
    "Beras", "Minyak", "Garam", "Gula", "Tepung Terigu",
    "Telur", "Tahu Pong", "Tempe", "Bakso", "Pisang",
    "Wortel", "Kentang", "Bayam", "Kangkung", "Buncis",
    "Tomat", "Bawang Merah", "Bawang Putih", "Cabai",
    "Daging Ayam", "Daging Sapi", "Ikan", "Udang",
    "Susu", "Mentega", "Mie", "Sagu", "Kecap",
    "Saos", "Lada Bubuk", "Vetsin", "Garam Dolphin",
    "Roti Tawar", "Sari Roti Bun", "Sari Roti Creamy",
    "Roycko", "Dorry", "Dimsum", "Susu Diamond",
    # Tambahkan item lain sesuai data aktual
])

# Mapping bulan tampilan ke ordinal
# CATATAN: Des 2025 – Feb 2026 adalah DATA TRAINING (ordinal 1–3).
# Bulan prediksi dimulai dari Mar 2026 (ordinal 4) agar tidak overlap
# dengan periode historis → mencegah temporal leakage.
BULAN_OPTIONS = {
    "Mar 2026": 4,
    "Apr 2026": 5,
    "Mei 2026": 6,
    "Jun 2026": 7,
    "Jul 2026": 8,
    "Agu 2026": 9,
}

# ── Halaman ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Monitoring Stok MBG",
    page_icon="🍱",
    layout="centered",
)

st.title("🍱 Sistem Monitoring Stok MBG")
st.caption("Prediksi volume restock dan status stok bahan makanan untuk periode berikutnya.")

st.divider()

# ── Form Input ─────────────────────────────────────────────────────────────────
with st.form("form_prediksi"):
    st.subheader("Data Bahan & Periode")

    col1, col2 = st.columns(2)

    with col1:
        item = st.selectbox(
            "Nama Bahan Makanan",
            options=DAFTAR_ITEM,
            help="Pilih bahan makanan yang ingin diprediksi stoknya.",
        )

        vol_lag1 = st.number_input(
            "Volume Beli Periode Terakhir (unit)",
            min_value=0.0,
            max_value=50000.0,
            value=500.0,
            step=10.0,
            help="Jumlah unit bahan yang dibeli pada minggu terakhir.",
        )

        vol_lag2 = st.number_input(
            "Volume Beli 2 Periode Lalu (unit)",
            min_value=0.0,
            max_value=50000.0,
            value=480.0,
            step=10.0,
            help="Jumlah unit bahan yang dibeli dua minggu lalu.",
        )

        vol_ma2 = st.number_input(
            "Rata-rata Volume 2 Periode Terakhir (unit)",
            min_value=0.0,
            max_value=50000.0,
            value=490.0,
            step=10.0,
            help="Rata-rata volume pembelian dari 2 periode terakhir (moving average). "
                 "Isi dengan (Vol Periode Terakhir + Vol 2 Periode Lalu) / 2 jika tidak yakin.",
        )

    with col2:
        bulan_label = st.selectbox(
            "Bulan Prediksi",
            options=list(BULAN_OPTIONS.keys()),
            index=0,   # default Mar 2026 (bulan pertama setelah data training)
            help="Bulan yang akan diprediksi kebutuhan stoknya. "
                 "Dimulai dari Maret 2026 (setelah periode data training Des 2025 – Feb 2026).",
        )
        bulan_ord = BULAN_OPTIONS[bulan_label]

        minggu_ord = st.selectbox(
            "Minggu Prediksi",
            options=[1, 2, 3, 4],
            format_func=lambda x: f"Minggu ke-{x}",
            help="Minggu dalam bulan yang akan diprediksi.",
        )

        # Periode IDX dihitung otomatis dari bulan + minggu (bukan input manual)
        # Rumus sesuai Bagian 2: PERIODE_IDX = (BULAN_ORD - 1) * 4 + MINGGU_ORD
        # Karena data historis sudah ada 10 periode (Des W1 s/d Feb W3),
        # prediksi dimulai dari periode berikutnya
        periode_idx = (bulan_ord - 1) * 4 + minggu_ord
        st.info(
            f"**Indeks Periode otomatis:** {periode_idx}\n\n"
            f"Dihitung dari: ({bulan_ord} - 1) × 4 + {minggu_ord} = {periode_idx}",
            icon="ℹ️",
        )

    # Validasi tampilan sebelum submit
    st.caption(
        f"Rata-rata yang disarankan: **{(vol_lag1 + vol_lag2) / 2:.1f}** unit "
        f"(dari Vol Terakhir + Vol 2 Periode Lalu)"
    )

    submit = st.form_submit_button("🔍 Prediksi Kebutuhan Stok", use_container_width=True)

# ── Hasil Prediksi ─────────────────────────────────────────────────────────────
if submit:
    # Validasi tambahan sisi frontend
    if vol_lag1 == 0 and vol_lag2 == 0:
        st.warning(
            "Volume periode terakhir dan 2 periode lalu keduanya 0. "
            "Pastikan data yang dimasukkan sudah benar.",
            icon="⚠️",
        )

    payload = {
        "periode_idx": periode_idx,
        "bulan_ord":   bulan_ord,
        "minggu_ord":  minggu_ord,
        "vol_lag1":    vol_lag1,
        "vol_lag2":    vol_lag2,
        "vol_ma2":     vol_ma2,
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        response.raise_for_status()
        res = response.json()

        st.divider()
        st.subheader(f"Hasil Prediksi – {item} ({bulan_label}, Minggu ke-{minggu_ord})")

        col_a, col_b = st.columns(2)

        vol_pred  = res.get("volume_prediksi", 0)
        status    = res.get("status_stok", "-")
        pesan     = res.get("pesan", "")
        icon_map  = {"AMAN": "🟢", "WASPADA": "🟡", "KRITIS": "🔴"}
        icon      = icon_map.get(status, "⚪")

        col_a.metric(
            label="Volume Prediksi Restock",
            value=f"{vol_pred:,} unit",
            delta=f"{vol_pred - vol_lag1:+.0f} dari periode terakhir",
        )
        col_b.metric(
            label="Status Stok",
            value=f"{icon} {status}",
        )

        # Kotak pesan berwarna sesuai status
        msg_type = {"AMAN": st.success, "WASPADA": st.warning, "KRITIS": st.error}
        msg_fn = msg_type.get(status, st.info)
        msg_fn(f"**{item}** – {pesan}", icon=icon)

        # Ringkasan input untuk referensi
        with st.expander("Detail input yang digunakan"):
            st.json({
                "Bahan"               : item,
                "Bulan"               : bulan_label,
                "Minggu"              : f"Minggu ke-{minggu_ord}",
                "Indeks Periode"      : periode_idx,
                "Vol Periode Terakhir": vol_lag1,
                "Vol 2 Periode Lalu"  : vol_lag2,
                "Rata-rata 2 Periode" : vol_ma2,
            })

    except requests.exceptions.ConnectionError:
        st.error(
            "Tidak dapat terhubung ke server API. "
            "Pastikan FastAPI sudah berjalan di `localhost:8000` atau URL Railway sudah dikonfigurasi.",
            icon="🔌",
        )
    except requests.exceptions.Timeout:
        st.error("Server API tidak merespons dalam 10 detik. Coba lagi.", icon="⏱️")
    except requests.exceptions.HTTPError as e:
        st.error(f"Server mengembalikan error: {e}", icon="❌")
    except Exception as e:
        st.error(f"Terjadi kesalahan tidak terduga: {e}", icon="❌")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Sistem Monitoring Stok MBG · Kelompok Pahlawan MBG · "
    "Program Studi Sains Data, Universitas Telkom 2026"
)
