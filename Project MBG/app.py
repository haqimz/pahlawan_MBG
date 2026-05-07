"""
app.py – Sistem Monitoring Stok MBG 
Frontend Streamlit lengkap: prediksi, manajemen inventory, penjadwalan produksi,
laporan & histori, dan notifikasi stok.
Terhubung ke FastAPI (main.py) melalui REST API.
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, date

# ── Konfigurasi ────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"

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
    "Mar 2026": 4,
    "Apr 2026": 5,
    "Mei 2026": 6,
    "Jun 2026": 7,
    "Jul 2026": 8,
    "Agu 2026": 9,
}

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

    # Badge notifikasi belum dibaca
    notif_data, _ = api_get("/notifikasi", {"hanya_belum_dibaca": True})
    belum_dibaca = notif_data["total"] if notif_data else 0
    notif_label = f"🔔 Notifikasi ({belum_dibaca} baru)" if belum_dibaca > 0 else "🔔 Notifikasi"

    halaman = st.radio(
        "Navigasi",
        [
            "📊 Dashboard",
            "🔍 Prediksi Stok",
            "📦 Manajemen Inventory",
            "🍽️ Menu Makanan",
            "📅 Jadwal Produksi",
            "📈 Laporan & Histori",
            notif_label,
        ],
        label_visibility="collapsed",
    )

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
                for b in kritis_list:
                    st.error(f"**{b['nama']}** — Stok: {b['stok']} {b['satuan']}", icon="⚠️")
            else:
                st.success("Tidak ada bahan dengan status kritis.", icon="✅")

        with col_b:
            st.subheader("🟡 Bahan Waspada")
            waspada_list = ringkasan.get("bahan_waspada", [])
            if waspada_list:
                for b in waspada_list:
                    st.warning(f"**{b['nama']}** — Stok: {b['stok']} {b['satuan']}", icon="⚡")
            else:
                st.success("Tidak ada bahan dengan status waspada.", icon="✅")

        # Jadwal mendatang
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

    with st.form("form_prediksi"):
        st.subheader("Data Bahan & Periode")
        col1, col2 = st.columns(2)

        with col1:
            item = st.selectbox("Nama Bahan Makanan", options=DAFTAR_ITEM,
                help="Pilih bahan makanan yang ingin diprediksi stoknya.")
            vol_lag1 = st.number_input("Volume Beli Periode Terakhir (unit)",
                min_value=0.0, max_value=50000.0, value=500.0, step=10.0)
            vol_lag2 = st.number_input("Volume Beli 2 Periode Lalu (unit)",
                min_value=0.0, max_value=50000.0, value=480.0, step=10.0)
            vol_ma2 = st.number_input("Rata-rata Volume 2 Periode Terakhir (unit)",
                min_value=0.0, max_value=50000.0, value=490.0, step=10.0,
                help="Isi dengan (Vol Periode Terakhir + Vol 2 Periode Lalu) / 2 jika tidak yakin.")

        with col2:
            bulan_label = st.selectbox("Bulan Prediksi", options=list(BULAN_OPTIONS.keys()), index=0,
                help="Bulan yang akan diprediksi (mulai Mar 2026 setelah data training Des 2025 – Feb 2026).")
            bulan_ord = BULAN_OPTIONS[bulan_label]
            minggu_ord = st.selectbox("Minggu Prediksi", options=[1, 2, 3, 4],
                format_func=lambda x: f"Minggu ke-{x}")
            periode_idx = (bulan_ord - 1) * 4 + minggu_ord
            st.info(
                f"**Indeks Periode otomatis:** {periode_idx}\n\n"
                f"Dihitung dari: ({bulan_ord} - 1) × 4 + {minggu_ord} = {periode_idx}", icon="ℹ️")

        st.caption(f"Rata-rata yang disarankan: **{(vol_lag1 + vol_lag2) / 2:.1f}** unit")
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
                st.json({
                    "Bahan"               : item,
                    "Bulan"               : bulan_label,
                    "Minggu"              : f"Minggu ke-{minggu_ord}",
                    "Indeks Periode"      : periode_idx,
                    "Vol Periode Terakhir": vol_lag1,
                    "Vol 2 Periode Lalu"  : vol_lag2,
                    "Rata-rata 2 Periode" : vol_ma2,
                })


# ══════════════════════════════════════════════════════════════════════════════
# HALAMAN: MANAJEMEN INVENTORY
# ══════════════════════════════════════════════════════════════════════════════
elif halaman == "📦 Manajemen Inventory":
    st.title("📦 Manajemen Inventory Bahan Makanan")
    tab1, tab2, tab3 = st.tabs(["📋 Daftar Stok", "➕ Tambah / Edit Bahan", "🔄 Transaksi Stok"])

    # ── Tab 1: Daftar Stok ────────────────────────────────────────────────────
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
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Belum ada data inventory. Silakan tambah bahan terlebih dahulu.", icon="ℹ️")

        st.divider()
        st.subheader("🗑️ Hapus Bahan")
        hapus_id = st.number_input("Masukkan ID bahan yang ingin dihapus", min_value=1, step=1, key="hapus_id")
        if st.button("Hapus Bahan", type="primary"):
            res, err = api_delete(f"/inventory/{int(hapus_id)}")
            if err:
                st.error(err, icon="❌")
            else:
                st.success(res.get("pesan", "Berhasil dihapus."), icon="✅")
                st.rerun()

    # ── Tab 2: Tambah / Edit ──────────────────────────────────────────────────
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
                stok_minimum   = c2.number_input("Stok Minimum", min_value=0.0, value=100.0,
                    help="Batas stok; jika ≤ nilai ini maka status KRITIS.")
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

        else:  # Edit
            with st.form("form_edit_bahan"):
                st.subheader("Edit Bahan")
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

    # ── Tab 3: Transaksi Stok ─────────────────────────────────────────────────
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
        with st.form("form_tambah_menu"):
            nama_menu  = st.text_input("Nama Menu *")
            kategori_m = st.selectbox("Kategori", ["Makanan Utama", "Lauk", "Sayuran", "Snack", "Minuman"])
            deskripsi  = st.text_area("Deskripsi Menu")

            st.write("**Komposisi Bahan** (tambahkan satu per satu)")
            st.caption("Format: Nama Bahan | Jumlah per Porsi | Satuan")

            n_bahan = st.number_input("Jumlah bahan dalam menu ini", min_value=1, max_value=20, value=3, step=1)
            komposisi_input = []
            for i in range(int(n_bahan)):
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


# ══════════════════════════════════════════════════════════════════════════════
# HALAMAN: JADWAL PRODUKSI
# ══════════════════════════════════════════════════════════════════════════════
elif halaman == "📅 Jadwal Produksi":
    st.title("📅 Penjadwalan Produksi Makanan")
    tab_j1, tab_j2 = st.tabs(["📋 Daftar Jadwal", "➕ Tambah Jadwal"])

    with tab_j1:
        col_jf1, col_jf2 = st.columns(2)
        tgl_mulai  = col_jf1.date_input("Dari Tanggal", value=None, key="j_mulai")
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

                        # Kebutuhan Bahan
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

        # Ambil daftar menu yang tersedia
        menu_tersedia, _ = api_get("/menu")
        nama_menu_list   = [m["nama_menu"] for m in (menu_tersedia.get("data", []) if menu_tersedia else [])]

        if not nama_menu_list:
            st.warning("Belum ada menu yang terdaftar. Silakan tambahkan menu terlebih dahulu di halaman Menu Makanan.", icon="⚠️")
        else:
            with st.form("form_jadwal"):
                cj1, cj2 = st.columns(2)
                tgl_prod  = cj1.date_input("Tanggal Produksi *", value=date.today())
                sesi_prod = cj1.selectbox("Sesi *", ["pagi", "siang", "sore"])
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

    # ── Tab: Ringkasan Stok ───────────────────────────────────────────────────
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
                    for b in data_rs["bahan_kritis"]:
                        st.error(f"{b['nama']} — {b['stok']} {b['satuan']}", icon="🔴")
                else:
                    st.success("Tidak ada.", icon="✅")

            with col_lb:
                st.write("**Bahan Waspada:**")
                if data_rs["bahan_waspada"]:
                    for b in data_rs["bahan_waspada"]:
                        st.warning(f"{b['nama']} — {b['stok']} {b['satuan']}", icon="🟡")
                else:
                    st.success("Tidak ada.", icon="✅")

            # Grafik distribusi status
            if data_rs["total_bahan"] > 0:
                st.divider()
                st.write("**Distribusi Status Stok:**")
                df_chart = pd.DataFrame({
                    "Status": ["AMAN", "WASPADA", "KRITIS"],
                    "Jumlah": [data_rs["aman"], data_rs["waspada"], data_rs["kritis"]],
                })
                st.bar_chart(df_chart.set_index("Status"))

    # ── Tab: Penggunaan Bahan ─────────────────────────────────────────────────
    with tab_l2:
        st.subheader("Laporan Penggunaan Bahan")
        cp1, cp2 = st.columns(2)
        tgl_dari  = cp1.date_input("Dari Tanggal", value=None, key="lap_dari")
        tgl_sampai= cp2.date_input("Sampai Tanggal", value=None, key="lap_sampai")

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
                    "Bahan"         : r["nama_bahan"],
                    "Total Masuk"   : r["total_masuk"],
                    "Total Keluar"  : r["total_keluar"],
                    "Frekuensi Tx"  : r["frekuensi"],
                } for r in lap_list])
                st.dataframe(df_lap, use_container_width=True, hide_index=True)

                # Grafik 5 bahan teratas penggunaan
                if len(lap_list) > 0:
                    top5 = df_lap.nlargest(min(5, len(df_lap)), "Total Keluar")[["Bahan", "Total Keluar"]].set_index("Bahan")
                    st.bar_chart(top5)
            else:
                st.info("Belum ada data penggunaan bahan untuk periode ini.", icon="ℹ️")

    # ── Tab: Histori Prediksi ─────────────────────────────────────────────────
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
                    "Waktu"           : p["waktu_prediksi"][:16].replace("T", " "),
                    "Bahan"           : p["nama_bahan"],
                    "Vol Prediksi"    : p["volume_prediksi"],
                    "Status"          : badge_status(p["status_stok"]),
                    "Bulan Ord"       : p["bulan_ord"],
                    "Minggu Ord"      : p["minggu_ord"],
                } for p in pred_list])
                st.dataframe(df_pred, use_container_width=True, hide_index=True)
            else:
                st.info("Belum ada histori prediksi.", icon="ℹ️")

        # Ringkasan statistik prediksi
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
else:  # Notifikasi
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

                fn_msg = {
                    "KRITIS" : st.error,
                    "WASPADA": st.warning,
                }.get(tipe, st.info)

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
