import sys
import asyncio

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

import streamlit as st
import pandas as pd
import time
import random
import json
import urllib3
from bs4 import BeautifulSoup
from io import BytesIO

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from curl_cffi import requests as cffi_requests

# ─────────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────────

BASE_URL   = "https://phl.kehutanan.go.id/tabular_table"
TABULAR_URL = "https://phl.kehutanan.go.id/tabular"
HOME_URL    = "https://phl.kehutanan.go.id/"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")

NAV_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

AJAX_HEADERS = {
    **NAV_HEADERS,
    "Accept": "text/html, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": TABULAR_URL,
    "Origin": "https://phl.kehutanan.go.id",
}

PROVINSI_LIST = [
    "Aceh", "Sumatera Utara", "Sumatera Barat", "Riau", "Jambi",
    "Sumatera Selatan", "Bengkulu", "Lampung", "Kepulauan Bangka Belitung",
    "Kepulauan Riau", "DKI Jakarta", "Jawa Barat", "Jawa Tengah",
    "DI Yogyakarta", "Jawa Timur", "Banten", "Bali",
    "Nusa Tenggara Barat", "Nusa Tenggara Timur",
    "Kalimantan Barat", "Kalimantan Tengah", "Kalimantan Selatan",
    "Kalimantan Timur", "Kalimantan Utara",
    "Sulawesi Utara", "Sulawesi Tengah", "Sulawesi Selatan",
    "Sulawesi Tenggara", "Gorontalo", "Sulawesi Barat",
    "Maluku", "Maluku Utara", "Papua Barat", "Papua",
]


def build_session() -> tuple:
    """
    Buat curl_cffi Session dengan TLS fingerprint Chrome 124.
    Flow: GET / → GET /tabular (ambil CSRF token dari form)
    Returns (session, csrf_token)
    """
    session = cffi_requests.Session(impersonate="chrome124", verify=False)
    session.headers.update(NAV_HEADERS)

    # Step 1: homepage – dapat sessionid cookie
    session.get(HOME_URL, timeout=20, verify=False)
    time.sleep(random.uniform(0.8, 1.5))

    # Step 2: halaman /tabular – dapat CSRF token dari hidden input
    r = session.get(TABULAR_URL, timeout=20, verify=False)
    csrf = _extract_csrf(r.text)

    return session, csrf


def _extract_csrf(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for inp in soup.find_all("input"):
        if "csrf" in inp.get("name", "").lower():
            return inp.get("value", "")
    # fallback: regex
    import re
    m = re.search(r'csrfmiddlewaretoken["\s]+value=["\']([^"\']+)', html)
    if m:
        return m.group(1)
    return ""


def fetch_table(session_tuple, tahun: int, provinsi: str, tabular_id: int = 32) -> pd.DataFrame | None:
    """
    POST ke /tabular_table dengan csrfmiddlewaretoken.
    Terbukti: POST 200, GET 403.
    """
    session, csrf = session_tuple
    form_data = {
        "csrfmiddlewaretoken": csrf,
        "tabular_id": str(tabular_id),
        "TANGGAL_LHP": str(tahun),
        "PROVINSI": provinsi,
    }
    headers = {**AJAX_HEADERS, "X-CSRFToken": csrf}

    for attempt in range(1, 4):
        try:
            resp = session.post(
                BASE_URL,
                data=form_data,
                headers=headers,
                timeout=30,
                verify=False,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                return parse_html_table(resp.text, tahun, provinsi)
            elif resp.status_code in (403, 429, 500):
                wait = attempt * random.uniform(5, 10)
                st.warning(f"⚠️ HTTP {resp.status_code} (attempt {attempt}/3) – menunggu {wait:.1f}s, refresh sesi...")
                time.sleep(wait)
                # Refresh CSRF token
                try:
                    r = session.get(TABULAR_URL, timeout=20, verify=False)
                    new_csrf = _extract_csrf(r.text)
                    if new_csrf:
                        session_tuple = (session, new_csrf)
                        csrf = new_csrf
                        form_data["csrfmiddlewaretoken"] = csrf
                        headers["X-CSRFToken"] = csrf
                except Exception:
                    pass
            else:
                st.error(f"HTTP {resp.status_code} untuk {tahun} – {provinsi}")
                return None
        except Exception as exc:
            st.warning(f"Percobaan {attempt}/3 error: {exc}")
            time.sleep(attempt * 3)

    st.error(f"Gagal mengambil data {tahun} – {provinsi} setelah 3 percobaan.")
    return None


def parse_html_table(html: str, tahun: int, provinsi: str) -> pd.DataFrame | None:
    """
    Parse HTML response – tabel HTML dan fallback JSON.
    pd.read_html butuh StringIO di pandas >= 2.x
    """
    from io import StringIO

    soup = BeautifulSoup(html, "html.parser")

    # ── coba semua <table> ──
    tables = soup.find_all("table")
    if tables:
        best = max(tables, key=lambda t: len(t.find_all("tr")))
        try:
            dfs = pd.read_html(StringIO(str(best)))
            if dfs:
                df = dfs[0]
                df.insert(0, "Tahun", tahun)
                df.insert(1, "Provinsi", provinsi)
                return df
        except Exception:
            pass

    # ── fallback: JSON ──
    try:
        data = json.loads(html)
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            for key in ("data", "rows", "result", "records"):
                if key in data and isinstance(data[key], list):
                    df = pd.DataFrame(data[key])
                    break
            else:
                df = pd.DataFrame([data])
        df.insert(0, "Tahun", tahun)
        df.insert(1, "Provinsi", provinsi)
        return df
    except (json.JSONDecodeError, UnboundLocalError):
        pass

    st.warning(f"Tidak ada tabel ditemukan untuk {tahun} – {provinsi}")
    return None


def to_excel(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    return buf.getvalue()


# ─────────────────────────────────────────────
# STREAMLIT UI
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Scraper PHL Kehutanan",
    page_icon="🌲",
    layout="wide",
)

st.title("🌲 Scraper Data PHL Kehutanan")
st.caption("Sumber: https://phl.kehutanan.go.id/tabular_table")

with st.sidebar:
    st.header("⚙️ Pengaturan")

    tabular_id = st.number_input(
        "Tabular ID",
        min_value=1,
        max_value=999,
        value=32,
        step=1,
        help="ID tabel yang ingin di-scrape",
    )

    st.subheader("Rentang Tahun")
    col1, col2 = st.columns(2)
    with col1:
        tahun_mulai = st.number_input("Dari", min_value=2000, max_value=2030, value=2022)
    with col2:
        tahun_akhir = st.number_input("Sampai", min_value=2000, max_value=2030, value=2026)

    tahun_list = list(range(int(tahun_mulai), int(tahun_akhir) + 1))
    st.info(f"Tahun dipilih: {tahun_list}")

    st.subheader("Provinsi")
    pilih_semua = st.checkbox("Pilih semua provinsi", value=False)
    if pilih_semua:
        provinsi_dipilih = PROVINSI_LIST
    else:
        provinsi_dipilih = st.multiselect(
            "Pilih Provinsi",
            PROVINSI_LIST,
            default=["Kalimantan Barat"],
        )

    delay_antar_request = st.slider(
        "Delay antar request (detik)",
        min_value=1,
        max_value=15,
        value=4,
        help="Delay acak untuk menghindari deteksi bot",
    )

    tombol_scrape = st.button("🚀 Mulai Scraping", use_container_width=True, type="primary")

# ─── AREA UTAMA ───────────────────────────────
if tombol_scrape:
    if not provinsi_dipilih:
        st.error("Pilih minimal satu provinsi!")
        st.stop()
    if tahun_mulai > tahun_akhir:
        st.error("Tahun mulai harus ≤ tahun akhir!")
        st.stop()

    total_request = len(tahun_list) * len(provinsi_dipilih)
    st.info(f"Total request yang akan dilakukan: **{total_request}**")

    with st.spinner("Membangun sesi browser (warming + ambil CSRF)..."):
        session_tuple = build_session()
        csrf_ok = bool(session_tuple[1])
    st.caption(f"Mode: **curl_cffi Chrome124** | CSRF token: {'✅ ditemukan' if csrf_ok else '❌ tidak ditemukan'}")

    all_dfs = []
    progress = st.progress(0)
    status_text = st.empty()
    log_container = st.expander("📋 Log Proses", expanded=False)
    logs = []

    req_count = 0
    for provinsi in provinsi_dipilih:
        for tahun in tahun_list:
            req_count += 1
            pct = req_count / total_request
            status_text.text(f"⏳ Scraping {provinsi} – Tahun {tahun} ({req_count}/{total_request})")
            progress.progress(pct)

            df = fetch_table(session_tuple, tahun, provinsi, int(tabular_id))
            if df is not None and not df.empty:
                all_dfs.append(df)
                logs.append(f"✅ {provinsi} {tahun}: {len(df)} baris")
            else:
                logs.append(f"❌ {provinsi} {tahun}: tidak ada data")

            with log_container:
                st.text("\n".join(logs[-20:]))  # tampilkan 20 log terakhir

            if req_count < total_request:
                jitter = random.uniform(0, 2)
                time.sleep(delay_antar_request + jitter)

    progress.progress(1.0)
    status_text.text("✅ Scraping selesai!")

    if all_dfs:
        result_df = pd.concat(all_dfs, ignore_index=True)

        st.success(f"Berhasil mengambil **{len(result_df)} baris** data dari **{len(all_dfs)} request**.")

        # ── Tampilan tabel ──
        st.subheader("📊 Hasil Data")
        st.dataframe(result_df, use_container_width=True, height=500)

        # ── Statistik ringkas ──
        with st.expander("📈 Statistik Ringkas"):
            st.write(result_df.describe(include="all"))

        # ── Download ──
        st.subheader("⬇️ Unduh Data")
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            csv_data = result_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 Download CSV",
                data=csv_data,
                file_name=f"phl_kehutanan_{tahun_mulai}_{tahun_akhir}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_dl2:
            xlsx_data = to_excel(result_df)
            st.download_button(
                "📥 Download Excel",
                data=xlsx_data,
                file_name=f"phl_kehutanan_{tahun_mulai}_{tahun_akhir}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        # simpan di session state agar bisa diakses ulang
        st.session_state["last_result"] = result_df
    else:
        st.error("Tidak ada data yang berhasil di-scrape. Cek koneksi / parameter.")

elif "last_result" in st.session_state:
    st.info("Menampilkan hasil scraping sebelumnya.")
    st.dataframe(st.session_state["last_result"], use_container_width=True, height=500)
else:
    st.markdown(
        """
        ### Cara Penggunaan
        1. Atur **Tabular ID** (default 32)
        2. Tentukan **rentang tahun** yang ingin diambil
        3. Pilih satu atau beberapa **Provinsi**
        4. Klik **🚀 Mulai Scraping**
        
        **Fitur anti-bot:**
        - Menggunakan `cloudscraper` untuk bypass Cloudflare
        - Header browser Chrome 124 yang realistis
        - Delay acak antar request
        - Retry otomatis hingga 3x jika gagal
        """
    )
