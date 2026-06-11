"""
app.py – Sistem Monitoring Stok MBG v2.0
Frontend Streamlit lengkap: prediksi, manajemen inventory, penjadwalan produksi,
laporan & histori, dan notifikasi stok.
Terhubung ke FastAPI (main.py) melalui REST API.
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, date
import threading
import uvicorn
import main

# Fungsi untuk menjalankan FastAPI di dalam thread background Streamlit

def run_fastapi():
    uvicorn.run(main.app, host="127.0.0.1", port=8000, log_level="warning")

# Jalankan server FastAPI jika belum berjalan
if not any(t.name == "FastAPI_Thread" for t in threading.enumerate()):
    threading.Thread(target=run_fastapi, name="FastAPI_Thread", daemon=True).start()
    
# ── Konfigurasi ────────────────────────────────────────────────────────────────
API_BASE = "http://127.0.0.1:8000"

# ── Daftar item bahan (untuk form prediksi) ───────────────────────────────────
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
])

# Mapping bulan tampilan ke ordinal
BULAN_OPTIONS = {
    "Jun 2026": 9,
    "Jul 2026": 10,
    "Agu 2026": 11,
    "Sep 2026": 12,
    "Okt 2026": 13,
}

# ── Path dataset Excel Mei 2026 ───────────────────────────────────────────────
DATASET_MEI_PATH = "Rekap Nota May 2026.xlsx"

# Nama sheet Minggu ke-3 dan ke-4 Mei 2026
SHEET_MEI_W3 = "Rekap 18 - 23 Mei 2026"   # vol_lag2 (2 periode lalu)
SHEET_MEI_W4 = "Rekap 25 - 30 Mei 2026"   # vol_lag1 (periode terakhir)

# Mapping nama bahan di DAFTAR_ITEM → nama di dataset Excel
# Tambahkan mapping jika nama berbeda
ITEM_NAME_MAP = {
    "Beras"        : ["Beras JBS", "Beras"],
    "Minyak"       : ["Minyak Tropical", "Minyak Fortune", "Minyak"],
    "Garam"        : ["Garam"],
    "Gula"         : ["Gula Pasir", "Gula Jawa", "Gula"],
    "Tepung Terigu": ["Tepung Terigu Segitiga Biru Kg", "Tepung Terigu"],
    "Telur"        : ["Telur Ayam", "Telur"],
    "Tahu Pong"    : ["Tahu Putih", "Tahu Putih Asin", "Tahu Pong"],
    "Tempe"        : ["Tempe"],
    "Bakso"        : ["Bakso"],
    "Pisang"       : ["Pisang Ambon", "Pisang"],
    "Wortel"       : ["Wortel"],
    "Kentang"      : ["Kentang"],
    "Bayam"        : ["Bayam"],
    "Kangkung"     : ["Kangkung"],
    "Buncis"       : ["Buncis"],
    "Tomat"        : ["Tomat", "Tomat Hijau"],
    "Bawang Merah" : ["Bawang Merah Kupas", "Bawang Merah Kulit", "Bawang Merah"],
    "Bawang Putih" : ["Bawang Putih Kupas", "Bawang Putih Kulit", "Bawang Putih"],
    "Cabai"        : ["Cabe Keriting", "Cabai"],
    "Daging Ayam"  : ["Daging Ayam Filet", "Ayam Paha Bawah", "Ayam Paha Atas", "Chicken Slice", "Daging Ayam"],
    "Daging Sapi"  : ["Daging Sapi"],
    "Ikan"         : ["Ikan"],
    "Udang"        : ["Udang"],
    "Susu"         : ["Susu Milklife", "Susu"],
    "Mentega"      : ["Mentega"],
    "Mie"          : ["Mie"],
    "Sagu"         : ["Sagu"],
    "Kecap"        : ["Kecap Bango", "Kecap Lele", "Kecap Ikan Merah", "Kecap"],
    "Saos"         : ["Saos Cabe Delmonte", "Saos Tomat Delmonte", "Saos BBQ Delmonte", "Saos Tiram Kaleng", "Saos"],
    "Lada Bubuk"   : ["Ladaku", "Lada Bubuk"],
    "Vetsin"       : ["Vetsin Ajinomoto", "Vetsin"],
    "Garam Dolphin": ["Garam Dolphin"],
    "Roti Tawar"   : ["Roti Tawar"],
    "Sari Roti Bun": ["Sari Roti Bun"],
    "Sari Roti Creamy": ["Sari Roti Creamy"],
    "Roycko"       : ["Royco Ayam", "Roycko"],
    "Dorry"        : ["Dorry"],
    "Dimsum"       : ["Dimsum"],
    "Susu Diamond" : ["Susu Diamond"],
}


@st.cache_data(show_spinner=False)
def load_dataset_mei() -> dict[str, dict]:
    """
    Load Rekap_Nota_May_2026.xlsx dan kembalikan dict:
      { nama_item_normalized: {"vol_w3": float, "vol_w4": float} }
    W3 = Rekap 18-23 Mei (vol_lag2), W4 = Rekap 25-30 Mei (vol_lag1)
    """
    import os
    if not os.path.exists(DATASET_MEI_PATH):
        return {}
    try:
        xl = pd.ExcelFile(DATASET_MEI_PATH)
        def read_sheet(sheet_name) -> dict:
            df = pd.read_excel(xl, sheet_name=sheet_name)
            df.columns = ["NO", "ITEM", "VOL", "SAT"]
            df = df.dropna(subset=["ITEM"])
            df["ITEM"] = df["ITEM"].astype(str).str.strip().str.lower()
            df["VOL"]  = pd.to_numeric(df["VOL"], errors="coerce").fillna(0)
            # Jika ada duplikat ITEM dalam satu sheet, jumlahkan
            return df.groupby("ITEM")["VOL"].sum().to_dict()
        w3 = read_sheet(SHEET_MEI_W3)
        w4 = read_sheet(SHEET_MEI_W4)
        # Gabungkan semua item yang dikenal
        result = {}
        for item_display, aliases in ITEM_NAME_MAP.items():
            vol_w3 = sum(w3.get(a.lower(), 0) for a in aliases)
            vol_w4 = sum(w4.get(a.lower(), 0) for a in aliases)
            result[item_display] = {"vol_w3": round(vol_w3, 2), "vol_w4": round(vol_w4, 2)}
        return result
    except Exception as e:
        st.warning(f"Gagal membaca dataset Mei 2026: {e}")
        return {}


def get_autofill_jun_w1(item: str) -> tuple[float, float, float] | None:
    """
    Untuk prediksi Jun 2026 Minggu 1:
    vol_lag1 = vol_w4 (Mei Minggu 4 = periode terakhir)
    vol_lag2 = vol_w3 (Mei Minggu 3 = 2 periode lalu)
    vol_ma2  = rata-rata keduanya
    Return (vol_lag1, vol_lag2, vol_ma2) atau None jika tidak ada data
    """
    data = load_dataset_mei()
    if item not in data:
        return None
    d = data[item]
    lag1 = d["vol_w4"]
    lag2 = d["vol_w3"]
    ma2  = round((lag1 + lag2) / 2, 2)
    return lag1, lag2, ma2


# ── Helper API ─────────────────────────────────────────────────────────────────
def api_get(path, params=None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Tidak dapat terhubung ke server API. Pastikan FastAPI sudah berjalan di `localhost:8000`."
    except requests.exceptions.Timeout:
        return None, "Server API tidak merespons dalam 10 detik."
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return None, f"Error dari server: {detail}"
    except Exception as e:
        return None, f"Terjadi kesalahan: {e}"

def api_post(path, payload):
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=10)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Tidak dapat terhubung ke server API."
    except requests.exceptions.Timeout:
        return None, "Server API tidak merespons dalam 10 detik."
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return None, f"Error dari server: {detail}"
    except Exception as e:
        return None, f"Terjadi kesalahan: {e}"

def api_put(path, payload):
    try:
        r = requests.put(f"{API_BASE}{path}", json=payload, timeout=10)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Tidak dapat terhubung ke server API."
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return None, f"Error dari server: {detail}"
    except Exception as e:
        return None, f"Terjadi kesalahan: {e}"

def api_delete(path):
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json(), None
    except requests.exceptions.ConnectionError:
        return None, "Tidak dapat terhubung ke server API."
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return None, f"Error dari server: {detail}"
    except Exception as e:
        return None, f"Terjadi kesalahan: {e}"

def badge_status(status: str) -> str:
    return {"AMAN": "🟢 AMAN", "WASPADA": "🟡 WASPADA", "KRITIS": "🔴 KRITIS"}.get(status, f"⚪ {status}")

def paginate(data: list, key: str, page_size: int = 10):
    """Tampilkan data dengan pagination. key harus unik per tabel."""
    total = len(data)
    total_pages = max(1, -(-total // page_size))  # ceiling division
    page_key = f"page_{key}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1

    page = st.session_state[page_key]
    start = (page - 1) * page_size
    end   = start + page_size

    hasil = data[start:end]

    col_info, col_prev, col_page, col_next = st.columns([4, 1, 1, 1])
    col_info.caption(f"Menampilkan {start+1}–{min(end, total)} dari **{total}** data")
    if col_prev.button("◀ Prev", key=f"prev_{key}", disabled=(page <= 1)):
        st.session_state[page_key] -= 1
        st.rerun()
    col_page.markdown(f"<div style='text-align:center;padding-top:6px'>{page}/{total_pages}</div>", unsafe_allow_html=True)
    if col_next.button("Next ▶", key=f"next_{key}", disabled=(page >= total_pages)):
        st.session_state[page_key] += 1
        st.rerun()

    return hasil

# ── Konfigurasi Halaman ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Monitoring Stok MBG",
    page_icon="🍱",
    layout="wide",
)

# ── Notifikasi di Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.title("🍱 MBG Stock System")
    st.caption("Sistem Monitoring Stok Makan Bergizi Gratis")
    st.divider()

    notif_data, _ = api_get("/notifikasi", {"hanya_belum_dibaca": True})
    belum_dibaca = notif_data["total"] if notif_data else 0
    notif_label = f"🔔 Notifikasi ({belum_dibaca} baru)" if belum_dibaca > 0 else "🔔 Notifikasi"

    NAV_OPTIONS = [
        "📊 Dashboard",
        "🔍 Prediksi Stok",
        "📦 Manajemen Inventory",
        "🍽️ Menu Makanan",
        "📅 Jadwal Produksi",
        "📈 Laporan & Histori",
        notif_label,
    ]

    if "halaman" not in st.session_state:
        st.session_state["halaman"] = "📊 Dashboard"

    # Sinkronkan jika notif_label berubah (jumlah notif berubah)
    if st.session_state["halaman"] not in NAV_OPTIONS:
        # Kemungkinan notif_label berubah, pertahankan di halaman notifikasi
        if "Notifikasi" in st.session_state["halaman"]:
            st.session_state["halaman"] = notif_label

    halaman = st.radio(
        "Navigasi",
        NAV_OPTIONS,
        index=NAV_OPTIONS.index(st.session_state["halaman"]),
        label_visibility="collapsed",
        key="nav_radio",
    )
    st.session_state["halaman"] = halaman

    st.divider()
    st.caption("Kelompok Pahlawan MBG\nProdi Sains Data, Universitas Telkom 2026")


# ══════════════════════════════════════════════════════════════════════════════
# HALAMAN: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if halaman == "📊 Dashboard":
    st.title("📊 Dashboard Monitoring Stok MBG")

    ringkasan, err = api_get("/laporan/ringkasan-stok")
    jadwal_lap, _  = api_get("/laporan/jadwal-produksi")

    if err:
        st.error(err, icon="🔌")
    else:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Bahan", ringkasan.get("total_bahan", 0))
        col2.metric("🟢 Aman",    ringkasan.get("aman", 0))
        col3.metric("🟡 Waspada", ringkasan.get("waspada", 0))
        col4.metric("🔴 Kritis",  ringkasan.get("kritis", 0))
        if jadwal_lap:
            col5.metric("Jadwal Produksi", jadwal_lap.get("total_jadwal", 0))

        st.divider()

        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("🔴 Bahan Kritis")
            kritis_list = ringkasan.get("bahan_kritis", [])
            if kritis_list:
                page_kritis = paginate(kritis_list, key="dash_kritis")
                df_kritis = pd.DataFrame([{
                    "Nama"  : b["nama"],
                    "Stok"  : b["stok"],
                    "Satuan": b["satuan"],
                    "Status": "🔴 KRITIS",
                } for b in page_kritis])
                st.dataframe(df_kritis, use_container_width=True, hide_index=True)
            else:
                st.success("Tidak ada bahan dengan status kritis.", icon="✅")

        with col_b:
            st.subheader("🟡 Bahan Waspada")
            waspada_list = ringkasan.get("bahan_waspada", [])
            if waspada_list:
                page_waspada = paginate(waspada_list, key="dash_waspada")
                df_waspada = pd.DataFrame([{
                    "Nama"  : b["nama"],
                    "Stok"  : b["stok"],
                    "Satuan": b["satuan"],
                    "Status": "🟡 WASPADA",
                } for b in page_waspada])
                st.dataframe(df_waspada, use_container_width=True, hide_index=True)
            else:
                st.success("Tidak ada bahan dengan status waspada.", icon="✅")

        if jadwal_lap and jadwal_lap.get("jadwal_mendatang"):
            st.divider()
            st.subheader("📅 Jadwal Produksi Mendatang")
            for j in jadwal_lap["jadwal_mendatang"]:
                st.info(
                    f"**{j['tanggal']}** – {j['sesi'].capitalize()} | "
                    f"Menu: {j['nama_menu']} | Porsi: {j['jumlah_porsi']:,}",
                    icon="📅",
                )


# ══════════════════════════════════════════════════════════════════════════════
# HALAMAN: PREDIKSI STOK
# ══════════════════════════════════════════════════════════════════════════════
elif halaman == "🔍 Prediksi Stok":
    st.title("🔍 Prediksi Kebutuhan Restock")
    st.caption("Prediksi volume restock dan status stok bahan makanan untuk periode berikutnya.")
    st.divider()

    # ── Pemilihan bahan & bulan/minggu dulu (di luar form) ───────────────────
    col_sel1, col_sel2, col_sel3 = st.columns(3)
    item = col_sel1.selectbox(
        "Nama Bahan Makanan", options=DAFTAR_ITEM,
        help="Pilih bahan makanan yang ingin diprediksi stoknya."
    )
    bulan_label = col_sel2.selectbox(
        "Bulan Prediksi", options=list(BULAN_OPTIONS.keys()),
        help="Bulan yang akan diprediksi."
    )
    minggu_ord = col_sel3.selectbox(
        "Minggu Prediksi", options=[1, 2, 3, 4],
        format_func=lambda x: f"Minggu ke-{x}"
    )

    bulan_ord   = BULAN_OPTIONS[bulan_label]
    periode_idx = (bulan_ord - 1) * 4 + minggu_ord

    # ── Logika Auto-fill ──────────────────────────────────────────────────────
    IS_JUN_W1 = (bulan_label == "Jun 2026" and minggu_ord == 1)
    autofill   = get_autofill_jun_w1(item) if IS_JUN_W1 else None

    if IS_JUN_W1:
        if autofill:
            lag1_default, lag2_default, ma2_default = autofill
            st.success(
                f"📂 **Data otomatis dari Rekap Mei 2026** untuk **{item}**:\n\n"
                f"- Vol Beli Periode Terakhir (Mei Minggu 4): **{lag1_default}**\n"
                f"- Vol Beli 2 Periode Lalu (Mei Minggu 3): **{lag2_default}**\n"
                f"- Rata-rata 2 Periode: **{ma2_default}**",
                icon="✅"
            )
        else:
            lag1_default, lag2_default, ma2_default = 0.0, 0.0, 0.0
            st.warning(
                f"⚠️ Data untuk **{item}** tidak ditemukan di Rekap Mei 2026. "
                "Silakan isi volume secara manual.",
                icon="⚠️"
            )
    else:
        lag1_default, lag2_default = 500.0, 480.0
        ma2_default = round((lag1_default + lag2_default) / 2, 2)

    # ── Form Prediksi ─────────────────────────────────────────────────────────
    with st.form("form_prediksi"):
        st.subheader("Data Volume & Periode")

        col1, col2 = st.columns(2)

        with col1:
            if IS_JUN_W1 and autofill:
                # Tampilkan sebagai read-only metric (tidak bisa diedit)
                st.metric("Volume Beli Periode Terakhir (unit)", lag1_default,
                          help="Diambil otomatis dari Rekap Mei 2026 Minggu ke-4 (25–30 Mei)")
                st.metric("Volume Beli 2 Periode Lalu (unit)", lag2_default,
                          help="Diambil otomatis dari Rekap Mei 2026 Minggu ke-3 (18–23 Mei)")
                st.metric("Rata-rata Volume 2 Periode Terakhir (unit)", ma2_default,
                          help="Dihitung otomatis: (Minggu 4 + Minggu 3) / 2")
                vol_lag1 = lag1_default
                vol_lag2 = lag2_default
                vol_ma2  = ma2_default
            else:
                vol_lag1 = st.number_input(
                    "Volume Beli Periode Terakhir (unit)",
                    min_value=0.0, max_value=50000.0, value=float(lag1_default), step=10.0
                )
                vol_lag2 = st.number_input(
                    "Volume Beli 2 Periode Lalu (unit)",
                    min_value=0.0, max_value=50000.0, value=float(lag2_default), step=10.0
                )
                # vol_ma2 dihitung otomatis, tidak perlu diisi user
                vol_ma2 = round((vol_lag1 + vol_lag2) / 2, 2)
                st.info(
                    f"🧮 **Rata-rata 2 Periode dihitung otomatis:** {vol_ma2} unit\n\n"
                    f"Rumus: ({vol_lag1} + {vol_lag2}) / 2 = {vol_ma2}",
                    icon="ℹ️"
                )

        with col2:
            bulan_ord_info  = bulan_ord
            minggu_ord_info = minggu_ord
            st.info(
                f"**Ringkasan Periode:**\n\n"
                f"- Bulan: {bulan_label} (ordinal: {bulan_ord_info})\n"
                f"- Minggu ke-{minggu_ord_info}\n"
                f"- **Indeks Periode: {periode_idx}**\n\n"
                f"Rumus: ({bulan_ord_info} - 1) × 4 + {minggu_ord_info} = {periode_idx}",
                icon="ℹ️"
            )
            if IS_JUN_W1:
                st.info(
                    "🤖 **Mode Otomatis Aktif**\n\n"
                    "Jun 2026 Minggu 1 menggunakan data langsung dari "
                    "**Rekap_Nota_May_2026.xlsx** tanpa input manual.",
                    icon="📂"
                )

        submit = st.form_submit_button("🔍 Prediksi Kebutuhan Stok", use_container_width=True)

    if submit:
        if vol_lag1 == 0 and vol_lag2 == 0:
            st.warning("Volume periode terakhir dan 2 periode lalu keduanya 0. Pastikan data sudah benar.", icon="⚠️")

        payload = {
            "nama_bahan" : item,
            "periode_idx": periode_idx,
            "bulan_ord"  : bulan_ord,
            "minggu_ord" : minggu_ord,
            "vol_lag1"   : vol_lag1,
            "vol_lag2"   : vol_lag2,
            "vol_ma2"    : vol_ma2,
        }
        res, err = api_post("/predict", payload)

        if err:
            st.error(err, icon="❌")
        else:
            st.divider()
            st.subheader(f"Hasil Prediksi – {item} ({bulan_label}, Minggu ke-{minggu_ord})")

            vol_pred = res.get("volume_prediksi", 0)
            status   = res.get("status_stok", "-")
            pesan    = res.get("pesan", "")
            icon_map = {"AMAN": "🟢", "WASPADA": "🟡", "KRITIS": "🔴"}
            icon     = icon_map.get(status, "⚪")

            col_a, col_b = st.columns(2)
            col_a.metric("Volume Prediksi Restock", f"{vol_pred:,} unit",
                         delta=f"{vol_pred - vol_lag1:+.0f} dari periode terakhir")
            col_b.metric("Status Stok", f"{icon} {status}")

            msg_fn = {"AMAN": st.success, "WASPADA": st.warning, "KRITIS": st.error}.get(status, st.info)
            msg_fn(f"**{item}** – {pesan}", icon=icon)

            with st.expander("Detail input yang digunakan"):
                sumber = "Otomatis dari Rekap Mei 2026" if IS_JUN_W1 and autofill else "Input Manual"
                st.json({
                    "Bahan"               : item,
                    "Bulan"               : bulan_label,
                    "Minggu"              : f"Minggu ke-{minggu_ord}",
                    "Indeks Periode"      : periode_idx,
                    "Vol Periode Terakhir": vol_lag1,
                    "Vol 2 Periode Lalu"  : vol_lag2,
                    "Rata-rata 2 Periode" : vol_ma2,
                    "Sumber Data Volume"  : sumber,
                })


# ══════════════════════════════════════════════════════════════════════════════
# HALAMAN: MANAJEMEN INVENTORY
# ══════════════════════════════════════════════════════════════════════════════
elif halaman == "📦 Manajemen Inventory":
    st.title("📦 Manajemen Inventory Bahan Makanan")
    tab1, tab2, tab3 = st.tabs(["📋 Daftar Stok", "➕ Tambah / Edit Bahan", "🔄 Transaksi Stok"])

    with tab1:
        col_filter1, col_filter2 = st.columns(2)
        filter_status   = col_filter1.selectbox("Filter Status", ["Semua", "AMAN", "WASPADA", "KRITIS"])
        filter_kategori = col_filter2.text_input("Filter Kategori (kosongkan untuk semua)")

        params = {}
        if filter_status != "Semua":
            params["status"] = filter_status
        if filter_kategori:
            params["kategori"] = filter_kategori

        inv, err = api_get("/inventory", params)
        if err:
            st.error(err, icon="🔌")
        elif inv:
            data = inv.get("data", [])
            st.caption(f"Total: **{inv['total']}** bahan")
            if data:
                rows = []
                for b in data:
                    rows.append({
                        "ID"           : b["id"],
                        "Nama"         : b["nama"],
                        "Kategori"     : b.get("kategori", "-"),
                        "Stok"         : b["stok_saat_ini"],
                        "Satuan"       : b.get("satuan", "unit"),
                        "Min"          : b.get("stok_minimum", 0),
                        "Maks"         : b.get("stok_maksimum", 0),
                        "Status"       : badge_status(b.get("status_stok", "-")),
                        "Supplier"     : b.get("supplier", "-"),
                        "Harga/unit"   : b.get("harga_per_unit", 0),
                    })
                df = pd.DataFrame(rows)
                page_inv = paginate(rows, key="inv_daftar")
                st.dataframe(pd.DataFrame(page_inv), use_container_width=True, hide_index=True)
            else:
                st.info("Belum ada data inventory. Silakan tambah bahan terlebih dahulu.", icon="ℹ️")

    with tab2:
        mode = st.radio("Mode", ["Tambah Bahan Baru", "Edit Bahan yang Ada"], horizontal=True)

        if mode == "Tambah Bahan Baru":
            with st.form("form_tambah_bahan"):
                st.subheader("Tambah Bahan Baru")
                c1, c2 = st.columns(2)
                nama           = c1.text_input("Nama Bahan *")
                satuan         = c1.selectbox("Satuan", ["unit", "kg", "gram", "liter", "ml", "butir", "ikat", "buah"])
                kategori       = c1.selectbox("Kategori", ["Umum", "Sayuran", "Protein", "Bumbu", "Karbohidrat", "Minuman", "Lainnya"])
                stok_saat_ini  = c2.number_input("Stok Saat Ini", min_value=0.0, value=0.0)
                stok_minimum   = c2.number_input("Stok Minimum", min_value=0.0, value=100.0)
                stok_maksimum  = c2.number_input("Stok Maksimum", min_value=0.0, value=10000.0)
                harga_per_unit = c1.number_input("Harga per Unit (Rp)", min_value=0.0, value=0.0)
                supplier       = c2.text_input("Supplier")
                keterangan     = st.text_area("Keterangan")
                ok = st.form_submit_button("➕ Tambah Bahan", use_container_width=True)

            if ok:
                if not nama:
                    st.warning("Nama bahan tidak boleh kosong.", icon="⚠️")
                else:
                    payload = {
                        "nama": nama, "satuan": satuan, "kategori": kategori,
                        "stok_saat_ini": stok_saat_ini, "stok_minimum": stok_minimum,
                        "stok_maksimum": stok_maksimum, "harga_per_unit": harga_per_unit,
                        "supplier": supplier, "keterangan": keterangan,
                    }
                    res, err = api_post("/inventory", payload)
                    if err:
                        st.error(err, icon="❌")
                    else:
                        st.success(res.get("pesan", "Berhasil ditambahkan."), icon="✅")

        else:
            # ── Tabel referensi daftar stok ───────────────────────────────
            st.subheader("📋 Daftar Bahan (Referensi ID)")
            inv_ref, _ = api_get("/inventory")
            if inv_ref and inv_ref.get("data"):
                rows_ref = [{
                    "ID"    : b["id"],
                    "Nama"  : b["nama"],
                    "Stok"  : b["stok_saat_ini"],
                    "Satuan": b.get("satuan", "-"),
                    "Status": badge_status(b.get("status_stok", "-")),
                } for b in inv_ref["data"]]
                page_ref = paginate(rows_ref, key="edit_ref")
                st.dataframe(pd.DataFrame(page_ref), use_container_width=True, hide_index=True)
            else:
                st.info("Belum ada data inventory.", icon="ℹ️")

            st.divider()
            
            with st.form("form_edit_bahan"):
                st.subheader("✏️ Edit Bahan")
                edit_id = st.number_input("ID Bahan yang Akan Diedit *", min_value=1, step=1)
                c1, c2 = st.columns(2)
                nama_baru          = c1.text_input("Nama Baru (kosongkan jika tidak berubah)")
                satuan_baru        = c1.selectbox("Satuan", ["(tidak berubah)", "unit", "kg", "gram", "liter", "ml", "butir", "ikat", "buah"])
                stok_baru          = c2.number_input("Stok Saat Ini Baru (-1 = tidak berubah)", min_value=-1.0, value=-1.0)
                stok_min_baru      = c2.number_input("Stok Minimum Baru (-1 = tidak berubah)", min_value=-1.0, value=-1.0)
                stok_maks_baru     = c2.number_input("Stok Maksimum Baru (-1 = tidak berubah)", min_value=-1.0, value=-1.0)
                harga_baru         = c1.number_input("Harga/unit Baru (-1 = tidak berubah)", min_value=-1.0, value=-1.0)
                supplier_baru      = c1.text_input("Supplier Baru (kosongkan jika tidak berubah)")
                ok_edit = st.form_submit_button("💾 Simpan Perubahan", use_container_width=True)

            if ok_edit:
                payload = {}
                if nama_baru:          payload["nama"]           = nama_baru
                if satuan_baru != "(tidak berubah)": payload["satuan"] = satuan_baru
                if stok_baru   >= 0:   payload["stok_saat_ini"]  = stok_baru
                if stok_min_baru >= 0: payload["stok_minimum"]   = stok_min_baru
                if stok_maks_baru >= 0:payload["stok_maksimum"]  = stok_maks_baru
                if harga_baru  >= 0:   payload["harga_per_unit"] = harga_baru
                if supplier_baru:      payload["supplier"]       = supplier_baru

                if not payload:
                    st.warning("Tidak ada perubahan yang diisi.", icon="⚠️")
                else:
                    res, err = api_put(f"/inventory/{int(edit_id)}", payload)
                    if err:
                        st.error(err, icon="❌")
                    else:
                        st.success(res.get("pesan", "Berhasil diperbarui."), icon="✅")
                        st.rerun()
            
            st.divider()

            # ── Form Hapus ────────────────────────────────────────────────
            st.subheader("🗑️ Hapus Bahan")

            # Tabel referensi untuk hapus
            inv_ref_hapus, _ = api_get("/inventory")
            if inv_ref_hapus and inv_ref_hapus.get("data"):
                rows_hapus = [{
                    "ID"    : b["id"],
                    "Nama"  : b["nama"],
                    "Stok"  : b["stok_saat_ini"],
                    "Satuan": b.get("satuan", "-"),
                    "Status": badge_status(b.get("status_stok", "-")),
                } for b in inv_ref_hapus["data"]]
                page_hapus = paginate(rows_hapus, key="hapus_ref")
                st.dataframe(pd.DataFrame(page_hapus), use_container_width=True, hide_index=True)
            else:
                st.info("Belum ada data inventory.", icon="ℹ️")
                
            with st.form("form_hapus_bahan"):
                hapus_id = st.number_input("ID Bahan yang Ingin Dihapus *", min_value=1, step=1, key="hapus_id_tab2")
                ok_hapus = st.form_submit_button("🗑️ Hapus Bahan", type="primary", use_container_width=True)

            if ok_hapus:
                res, err = api_delete(f"/inventory/{int(hapus_id)}")
                if err:
                    st.error(err, icon="❌")
                else:
                    st.success(res.get("pesan", "Berhasil dihapus."), icon="✅")
                    st.rerun()
    with tab3:
        st.subheader("🔄 Catat Stok Masuk / Keluar")
        with st.form("form_transaksi"):
            c1, c2 = st.columns(2)
            tx_nama   = c1.text_input("Nama Bahan *")
            tx_jenis  = c1.radio("Jenis Transaksi", ["masuk", "keluar"], horizontal=True)
            tx_jumlah = c2.number_input("Jumlah *", min_value=0.1, value=100.0, step=1.0)
            tx_ket    = c2.text_input("Keterangan")
            tx_submit = st.form_submit_button("📝 Catat Transaksi", use_container_width=True)

        if tx_submit:
            if not tx_nama:
                st.warning("Nama bahan tidak boleh kosong.", icon="⚠️")
            else:
                payload = {
                    "nama_bahan": tx_nama, "jenis": tx_jenis,
                    "jumlah": tx_jumlah, "keterangan": tx_ket,
                    "tanggal": datetime.now().isoformat(),
                }
                res, err = api_post("/inventory/transaksi", payload)
                if err:
                    st.error(err, icon="❌")
                else:
                    fn = st.success if tx_jenis == "masuk" else st.warning
                    fn(
                        f"{res.get('pesan', 'Berhasil.')} "
                        f"Stok: {res.get('stok_sebelum', '?')} → {res.get('stok_sesudah', '?')} | "
                        f"Status: {badge_status(res.get('status_stok', '-'))}",
                        icon="✅",
                    )

        st.divider()
        st.subheader("📜 Riwayat Transaksi Stok")
        col_f1, col_f2, col_f3 = st.columns(3)
        riwayat_nama  = col_f1.text_input("Filter nama bahan", key="riw_nama")
        riwayat_jenis = col_f2.selectbox("Filter jenis", ["Semua", "masuk", "keluar"], key="riw_jenis")
        riwayat_limit = col_f3.number_input("Tampilkan N terakhir", min_value=10, max_value=500, value=50, step=10)

        params_riw = {"limit": riwayat_limit}
        if riwayat_nama:
            params_riw["nama_bahan"] = riwayat_nama
        if riwayat_jenis != "Semua":
            params_riw["jenis"] = riwayat_jenis

        riw, err = api_get("/inventory/riwayat", params_riw)
        if err:
            st.error(err, icon="🔌")
        elif riw:
            data_riw = riw.get("data", [])
            st.caption(f"Menampilkan {len(data_riw)} dari {riw['total']} transaksi")
            if data_riw:
                df_riw = pd.DataFrame([{
                    "Tanggal"      : r["tanggal"][:10] if r.get("tanggal") else "-",
                    "Bahan"        : r["nama_bahan"],
                    "Jenis"        : "⬆️ Masuk" if r["jenis"] == "masuk" else "⬇️ Keluar",
                    "Jumlah"       : r["jumlah"],
                    "Stok Sebelum" : r.get("stok_sebelum", "-"),
                    "Stok Sesudah" : r.get("stok_sesudah", "-"),
                    "Keterangan"   : r.get("keterangan", "-"),
                } for r in data_riw])
                st.dataframe(df_riw, use_container_width=True, hide_index=True)
            else:
                st.info("Belum ada riwayat transaksi.", icon="ℹ️")


# ══════════════════════════════════════════════════════════════════════════════
# HALAMAN: MENU MAKANAN
# ══════════════════════════════════════════════════════════════════════════════
elif halaman == "🍽️ Menu Makanan":
    st.title("🍽️ Manajemen Menu Makanan")
    tab_m1, tab_m2 = st.tabs(["📋 Daftar Menu", "➕ Tambah Menu"])

    with tab_m1:
        menu_data, err = api_get("/menu")
        if err:
            st.error(err, icon="🔌")
        elif menu_data:
            menus = menu_data.get("data", [])
            st.caption(f"Total: **{menu_data['total']}** menu")
            if menus:
                for m in menus:
                    with st.expander(f"🍴 {m['nama_menu']}  ·  {m.get('kategori', '-')}  ·  ID {m['id']}"):
                        if m.get("deskripsi"):
                            st.write(m["deskripsi"])
                        st.write("**Komposisi Bahan:**")
                        komposisi = m.get("komposisi", [])
                        if komposisi:
                            df_kom = pd.DataFrame([{
                                "Bahan"          : k["nama_bahan"],
                                "Jumlah/Porsi"   : k["jumlah_per_porsi"],
                                "Satuan"         : k.get("satuan", "gram"),
                            } for k in komposisi])
                            st.dataframe(df_kom, use_container_width=True, hide_index=True)

                        if st.button(f"🗑️ Hapus Menu ID {m['id']}", key=f"hapus_menu_{m['id']}"):
                            res, err2 = api_delete(f"/menu/{m['id']}")
                            if err2:
                                st.error(err2, icon="❌")
                            else:
                                st.success(res.get("pesan", "Berhasil dihapus."), icon="✅")
                                st.rerun()
            else:
                st.info("Belum ada menu yang terdaftar.", icon="ℹ️")

    with tab_m2:
        st.subheader("Tambah Menu Baru")

        # n_bahan di luar form agar dinamis
        if "n_bahan_menu" not in st.session_state:
            st.session_state["n_bahan_menu"] = 3

        col_nb1, col_nb2, col_nb3 = st.columns([3, 1, 3])
        col_nb1.write("**Jumlah bahan dalam menu ini**")
        if col_nb2.button("➖", key="kurang_bahan") and st.session_state["n_bahan_menu"] > 1:
            st.session_state["n_bahan_menu"] -= 1
            st.rerun()
        if col_nb3.button("➕", key="tambah_bahan"):
            if st.session_state["n_bahan_menu"] < 20:
                st.session_state["n_bahan_menu"] += 1
                st.rerun()
        st.info(f"Jumlah bahan: **{st.session_state['n_bahan_menu']}**", icon="ℹ️")

        
        with st.form("form_tambah_menu"):
            nama_menu  = st.text_input("Nama Menu *")
            kategori_m = st.selectbox("Kategori", ["Makanan Utama", "Lauk", "Sayuran", "Snack", "Minuman"])
            deskripsi  = st.text_area("Deskripsi Menu")

            st.write("**Komposisi Bahan** (tambahkan satu per satu)")
            st.caption("Format: Nama Bahan | Jumlah per Porsi | Satuan")

            n_bahan = st.session_state["n_bahan_menu"]
            komposisi_input = []
            for i in range(n_bahan):
                ca, cb, cc = st.columns([3, 2, 2])
                nb   = ca.text_input(f"Bahan #{i+1}", key=f"bahan_{i}")
                jpp  = cb.number_input(f"Jumlah/Porsi #{i+1}", min_value=0.0, step=0.1, key=f"jpp_{i}")
                sat  = cc.selectbox(f"Satuan #{i+1}", ["gram", "ml", "unit", "butir", "sdm", "sdt"], key=f"sat_{i}")
                if nb:
                    komposisi_input.append({"nama_bahan": nb, "jumlah_per_porsi": jpp, "satuan": sat})

            ok_menu = st.form_submit_button("➕ Simpan Menu", use_container_width=True)

        if ok_menu:
            if not nama_menu:
                st.warning("Nama menu tidak boleh kosong.", icon="⚠️")
            elif not komposisi_input:
                st.warning("Komposisi bahan tidak boleh kosong.", icon="⚠️")
            else:
                payload = {
                    "nama_menu": nama_menu, "kategori": kategori_m,
                    "deskripsi": deskripsi, "komposisi": komposisi_input,
                }
                res, err = api_post("/menu", payload)
                if err:
                    st.error(err, icon="❌")
                else:
                    st.success(res.get("pesan", "Berhasil ditambahkan."), icon="✅")
                    st.session_state["n_bahan_menu"] = 3  # reset


# ══════════════════════════════════════════════════════════════════════════════
# HALAMAN: JADWAL PRODUKSI
# ══════════════════════════════════════════════════════════════════════════════
elif halaman == "📅 Jadwal Produksi":
    st.title("📅 Penjadwalan Produksi Makanan")
    tab_j1, tab_j2 = st.tabs(["📋 Daftar Jadwal", "➕ Tambah Jadwal"])

    with tab_j1:
        col_jf1, col_jf2 = st.columns(2)
        tgl_mulai   = col_jf1.date_input("Dari Tanggal", value=None, key="j_mulai")
        tgl_selesai = col_jf2.date_input("Sampai Tanggal", value=None, key="j_selesai")

        params_j = {}
        if tgl_mulai:
            params_j["tanggal_mulai"] = str(tgl_mulai)
        if tgl_selesai:
            params_j["tanggal_selesai"] = str(tgl_selesai)

        jadwal_data, err = api_get("/jadwal", params_j)
        if err:
            st.error(err, icon="🔌")
        elif jadwal_data:
            jadwals = jadwal_data.get("data", [])
            st.caption(f"Total: **{jadwal_data['total']}** jadwal")
            if jadwals:
                for j in jadwals:
                    status_j = j.get("status", "terjadwal")
                    icon_j   = "✅" if status_j == "selesai" else "⏳"
                    with st.expander(
                        f"{icon_j} {j['tanggal']} – {j['sesi'].capitalize()} | "
                        f"{j['nama_menu']} ({j['jumlah_porsi']:,} porsi) | ID {j['id']}"
                    ):
                        c_j1, c_j2 = st.columns(2)
                        c_j1.write(f"**Lokasi:** {j.get('lokasi_distribusi', '-')}")
                        c_j1.write(f"**Penanggung Jawab:** {j.get('penanggung_jawab', '-')}")
                        c_j2.write(f"**Status:** {'✅ Selesai' if status_j == 'selesai' else '⏳ Terjadwal'}")
                        if j.get("keterangan"):
                            st.write(f"**Keterangan:** {j['keterangan']}")

                        kb = j.get("kebutuhan_bahan", [])
                        if kb:
                            st.write("**Kebutuhan Bahan:**")
                            df_kb = pd.DataFrame([{
                                "Bahan"         : k["nama_bahan"],
                                "Dibutuhkan"    : k["jumlah_dibutuhkan"],
                                "Satuan"        : k["satuan"],
                                "Stok Tersedia" : k["stok_tersedia"],
                                "Cukup"         : "✅" if k["cukup"] else "❌",
                            } for k in kb])
                            st.dataframe(df_kb, use_container_width=True, hide_index=True)

                        col_btn1, col_btn2 = st.columns(2)
                        if status_j != "selesai":
                            if col_btn1.button(f"✅ Tandai Selesai (ID {j['id']})", key=f"selesai_{j['id']}"):
                                res, err2 = api_post(f"/jadwal/{j['id']}/selesai", {})
                                if err2:
                                    # Coba parse detail bahan kurang
                                    try:
                                        import json
                                        detail = json.loads(err2.replace("Error dari server: ", ""))
                                        st.error(detail.get("pesan", err2), icon="❌")
                                        for bk in detail.get("bahan_kurang", []):
                                            st.warning(f"⚠️ {bk}", icon="⚠️")
                                    except Exception:
                                        st.error(err2, icon="❌")
                                else:
                                    st.success(res.get("pesan", "Jadwal ditandai selesai."), icon="✅")
                                    st.rerun()
                        if col_btn2.button(f"🗑️ Hapus Jadwal ID {j['id']}", key=f"hapus_jadwal_{j['id']}"):
                            res, err2 = api_delete(f"/jadwal/{j['id']}")
                            if err2:
                                st.error(err2, icon="❌")
                            else:
                                st.success(res.get("pesan", "Berhasil dihapus."), icon="✅")
                                st.rerun()
            else:
                st.info("Belum ada jadwal produksi.", icon="ℹ️")

    with tab_j2:
        st.subheader("Tambah Jadwal Produksi Baru")
        menu_tersedia, _ = api_get("/menu")
        nama_menu_list   = [m["nama_menu"] for m in (menu_tersedia.get("data", []) if menu_tersedia else [])]

        if not nama_menu_list:
            st.warning("Belum ada menu yang terdaftar. Silakan tambahkan menu terlebih dahulu di halaman Menu Makanan.", icon="⚠️")
        else:
            with st.form("form_jadwal"):
                cj1, cj2 = st.columns(2)
                tgl_prod  = cj1.date_input("Tanggal Produksi *", value=date.today())
                sesi_prod = cj1.selectbox("Sesi *", ["siang"])
                menu_pilih= cj2.selectbox("Menu *", nama_menu_list)
                jml_porsi = cj2.number_input("Jumlah Porsi *", min_value=1, value=100, step=10)
                lokasi    = cj1.text_input("Lokasi Distribusi")
                pj        = cj2.text_input("Penanggung Jawab")
                ket_prod  = st.text_area("Keterangan")
                ok_jadwal = st.form_submit_button("📅 Simpan Jadwal", use_container_width=True)

            if ok_jadwal:
                payload = {
                    "tanggal"           : str(tgl_prod),
                    "sesi"              : sesi_prod,
                    "nama_menu"         : menu_pilih,
                    "jumlah_porsi"      : jml_porsi,
                    "lokasi_distribusi" : lokasi,
                    "penanggung_jawab"  : pj,
                    "keterangan"        : ket_prod,
                }
                res, err = api_post("/jadwal", payload)
                if err:
                    st.error(err, icon="❌")
                else:
                    st.success(res.get("pesan", "Jadwal berhasil ditambahkan."), icon="✅")
                    if res.get("peringatan_stok"):
                        for pw in res["peringatan_stok"]:
                            st.warning(f"⚠️ Stok kurang: {pw}", icon="⚠️")


# ══════════════════════════════════════════════════════════════════════════════
# HALAMAN: LAPORAN & HISTORI
# ══════════════════════════════════════════════════════════════════════════════
elif halaman == "📈 Laporan & Histori":
    st.title("📈 Laporan & Histori")
    tab_l1, tab_l2, tab_l3 = st.tabs(["📦 Ringkasan Stok", "📊 Penggunaan Bahan", "🔍 Histori Prediksi"])

    with tab_l1:
        st.subheader("Ringkasan Status Stok")
        data_rs, err = api_get("/laporan/ringkasan-stok")
        if err:
            st.error(err, icon="🔌")
        elif data_rs:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Bahan", data_rs["total_bahan"])
            c2.metric("🟢 Aman",    data_rs["aman"])
            c3.metric("🟡 Waspada", data_rs["waspada"])
            c4.metric("🔴 Kritis",  data_rs["kritis"])

            col_la, col_lb = st.columns(2)

            with col_la:
                st.write("**Bahan Kritis:**")
                if data_rs["bahan_kritis"]:
                    page_kritis_lap = paginate(data_rs["bahan_kritis"], key="lap_kritis")
                    df_kritis_lap = pd.DataFrame([{
                        "Nama"  : b["nama"],
                        "Stok"  : b["stok"],
                        "Satuan": b["satuan"],
                        "Status": "🔴 KRITIS",
                    } for b in page_kritis_lap])
                    st.dataframe(df_kritis_lap, use_container_width=True, hide_index=True)
                else:
                    st.success("Tidak ada.", icon="✅")

            with col_lb:
                st.write("**Bahan Waspada:**")
                if data_rs["bahan_waspada"]:
                    page_waspada_lap = paginate(data_rs["bahan_waspada"], key="lap_waspada")
                    df_waspada_lap = pd.DataFrame([{
                        "Nama"  : b["nama"],
                        "Stok"  : b["stok"],
                        "Satuan": b["satuan"],
                        "Status": "🟡 WASPADA",
                    } for b in page_waspada_lap])
                    st.dataframe(df_waspada_lap, use_container_width=True, hide_index=True)
                else:
                    st.success("Tidak ada.", icon="✅")

            if data_rs["total_bahan"] > 0:
                st.divider()
                st.write("**Distribusi Status Stok:**")
                df_chart = pd.DataFrame({
                    "Status": ["AMAN", "WASPADA", "KRITIS"],
                    "Jumlah": [data_rs["aman"], data_rs["waspada"], data_rs["kritis"]],
                })
                st.bar_chart(df_chart.set_index("Status"))

    with tab_l2:
        st.subheader("Laporan Penggunaan Bahan")
        cp1, cp2 = st.columns(2)
        tgl_dari   = cp1.date_input("Dari Tanggal", value=None, key="lap_dari")
        tgl_sampai = cp2.date_input("Sampai Tanggal", value=None, key="lap_sampai")

        params_lap = {}
        if tgl_dari:
            params_lap["tanggal_mulai"] = str(tgl_dari)
        if tgl_sampai:
            params_lap["tanggal_selesai"] = str(tgl_sampai)

        data_penggunaan, err = api_get("/laporan/penggunaan-bahan", params_lap)
        if err:
            st.error(err, icon="🔌")
        elif data_penggunaan:
            lap_list = data_penggunaan.get("data", [])
            periode  = data_penggunaan.get("periode", {})
            if periode.get("mulai") or periode.get("selesai"):
                st.caption(f"Periode: {periode.get('mulai', '-')} s/d {periode.get('selesai', '-')}")
            if lap_list:
                df_lap = pd.DataFrame([{
                    "Bahan"        : r["nama_bahan"],
                    "Total Masuk"  : r["total_masuk"],
                    "Total Keluar" : r["total_keluar"],
                    "Frekuensi Tx" : r["frekuensi"],
                } for r in lap_list])
                st.dataframe(df_lap, use_container_width=True, hide_index=True)
                if len(lap_list) > 0:
                    top5 = df_lap.nlargest(min(5, len(df_lap)), "Total Keluar")[["Bahan", "Total Keluar"]].set_index("Bahan")
                    st.bar_chart(top5)
            else:
                st.info("Belum ada data penggunaan bahan untuk periode ini.", icon="ℹ️")

    with tab_l3:
        st.subheader("Histori Prediksi Restock")
        filter_bahan_pred = st.text_input("Filter nama bahan (kosongkan untuk semua)", key="filt_pred")

        params_pred = {}
        if filter_bahan_pred:
            params_pred["nama_bahan"] = filter_bahan_pred

        data_pred, err = api_get("/predict/histori", params_pred)
        if err:
            st.error(err, icon="🔌")
        elif data_pred:
            pred_list = data_pred.get("data", [])
            st.caption(f"Total prediksi tersimpan: **{data_pred['total']}**")
            if pred_list:
                df_pred = pd.DataFrame([{
                    "Waktu"        : p["waktu_prediksi"][:16].replace("T", " "),
                    "Bahan"        : p["nama_bahan"],
                    "Vol Prediksi" : p["volume_prediksi"],
                    "Status"       : badge_status(p["status_stok"]),
                    "Bulan Ord"    : p["bulan_ord"],
                    "Minggu Ord"   : p["minggu_ord"],
                } for p in pred_list])
                st.dataframe(df_pred, use_container_width=True, hide_index=True)
            else:
                st.info("Belum ada histori prediksi.", icon="ℹ️")

        st.divider()
        st.write("**Ringkasan Statistik Prediksi per Bahan:**")
        data_lap_pred, _ = api_get("/laporan/histori-prediksi-ringkasan")
        if data_lap_pred and data_lap_pred.get("data"):
            df_ring = pd.DataFrame([{
                "Bahan"              : r["nama_bahan"],
                "Jumlah Prediksi"    : r["jumlah_prediksi"],
                "Rata-rata Vol"      : f"{r['rata_vol_prediksi']:,.0f}",
                "Terakhir Diprediksi": r["terakhir_prediksi"][:10] if r.get("terakhir_prediksi") else "-",
            } for r in data_lap_pred["per_bahan"]])
            st.dataframe(df_ring, use_container_width=True, hide_index=True)

            dist = data_lap_pred.get("distribusi_status", {})
            if dist:
                df_dist = pd.DataFrame({"Status": list(dist.keys()), "Jumlah": list(dist.values())}).set_index("Status")
                st.bar_chart(df_dist)
        elif data_lap_pred:
            st.info(data_lap_pred.get("pesan", "Belum ada data."), icon="ℹ️")


# ══════════════════════════════════════════════════════════════════════════════
# HALAMAN: NOTIFIKASI
# ══════════════════════════════════════════════════════════════════════════════
else:
    st.title("🔔 Notifikasi Stok")

    col_n1, col_n2, col_n3 = st.columns([2, 1, 1])
    tampilkan_semua = col_n1.checkbox("Tampilkan semua (termasuk sudah dibaca)", value=False)

    params_notif = {}
    if not tampilkan_semua:
        params_notif["hanya_belum_dibaca"] = True

    data_notif, err = api_get("/notifikasi", params_notif)
    if err:
        st.error(err, icon="🔌")
    else:
        notifs = data_notif.get("data", [])
        belum  = data_notif.get("belum_dibaca", 0)
        st.caption(f"**{belum}** notifikasi belum dibaca dari **{data_notif['total']}** total")

        if col_n2.button("✅ Tandai Semua Dibaca"):
            res, err2 = api_post("/notifikasi/baca-semua", {})
            if err2:
                st.error(err2, icon="❌")
            else:
                st.success("Semua notifikasi ditandai dibaca.", icon="✅")
                st.rerun()

        if col_n3.button("🗑️ Hapus Semua Notifikasi"):
            res, err2 = api_delete("/notifikasi/hapus-semua")
            if err2:
                st.error(err2, icon="❌")
            else:
                st.success("Semua notifikasi dihapus.", icon="✅")
                st.rerun()

        st.divider()

        if notifs:
            for n in notifs:
                tipe    = n.get("tipe", "INFO")
                dibaca  = n.get("dibaca", False)
                waktu   = n["waktu"][:16].replace("T", " ") if n.get("waktu") else "-"
                pesan_n = n.get("pesan", "")

                fn_msg = {"KRITIS": st.error, "WASPADA": st.warning}.get(tipe, st.info)
                suffix = " *(sudah dibaca)*" if dibaca else ""
                fn_msg(
                    f"**[{tipe}]** {pesan_n}  \n🕐 {waktu}{suffix}",
                    icon={"KRITIS": "🔴", "WASPADA": "🟡"}.get(tipe, "ℹ️"),
                )

                if not dibaca:
                    if st.button(f"Tandai Dibaca (ID {n['id']})", key=f"baca_{n['id']}"):
                        res, err2 = api_post(f"/notifikasi/{n['id']}/baca", {})
                        if err2:
                            st.error(err2, icon="❌")
                        else:
                            st.rerun()
        else:
            st.success("Tidak ada notifikasi baru.", icon="✅")

# ── Footer ─────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Sistem Monitoring Stok MBG · Kelompok Pahlawan MBG · "
    "Program Studi Sains Data, Universitas Telkom 2026"
)