"""
app_scraping.py — GUI Pemilihan SLS & Manajemen Scraping (v2 - Redesign)
Jalankan dengan: streamlit run app_scraping.py
"""

import streamlit as st
import pandas as pd
import os
import json
import subprocess
import sys
import time
import threading
import tempfile
from datetime import datetime

DIR_PATH = os.path.dirname(os.path.abspath(__file__))
MAIN_PY = os.path.join(DIR_PATH, "main.py")
REGION_FILE = os.path.join(DIR_PATH, "region_mapping.json")
CONFIG_FILE = os.path.join(DIR_PATH, "config.json")
TEMPLATE_DEFAULT = os.path.join(DIR_PATH, "Template Jodi.xlsx")

st.set_page_config(
    page_title="Scraping Manager SE2026",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*, html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* Background */
.stApp { background-color: #F0F4F8; }
section[data-testid="stSidebar"] { background-color: #1E293B; }
section[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stMultiSelect label,
section[data-testid="stSidebar"] .stFileUploader label { color: #94A3B8 !important; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.05em; }

/* Sidebar multiselect tags */
section[data-testid="stSidebar"] span[data-baseweb="tag"] { background-color: #3B82F6 !important; }

/* Header bar */
.top-bar {
    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    border-radius: 14px;
    padding: 20px 28px;
    margin-bottom: 20px;
    display: flex; align-items: center; justify-content: space-between;
    box-shadow: 0 4px 20px rgba(0,0,0,0.12);
}
.top-bar-title { color: white; font-size: 1.5rem; font-weight: 700; margin: 0; }
.top-bar-sub { color: #94A3B8; font-size: 0.85rem; margin: 2px 0 0 0; }

/* Stats row */
.stat-row { display: flex; gap: 12px; margin-bottom: 16px; }
.stat-box {
    flex: 1; background: white; border-radius: 10px;
    padding: 14px 18px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    border: 1px solid #E2E8F0;
    text-align: center;
}
.stat-num { font-size: 1.8rem; font-weight: 700; color: #1E293B; line-height: 1; }
.stat-lbl { font-size: 0.75rem; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px; }
.stat-num.blue { color: #3B82F6; }
.stat-num.green { color: #10B981; }
.stat-num.orange { color: #F59E0B; }

/* Table card */
.table-card {
    background: white; border-radius: 12px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    overflow: hidden;
    margin-bottom: 16px;
}
.table-header {
    padding: 16px 20px;
    border-bottom: 1px solid #F1F5F9;
    display: flex; align-items: center; justify-content: space-between;
}
.table-title { font-weight: 600; color: #1E293B; font-size: 0.95rem; }
.table-sub { color: #64748B; font-size: 0.8rem; }

/* Buttons */
div.stButton > button {
    border-radius: 8px !important; font-weight: 600 !important;
    border: none !important; transition: all 0.15s !important;
}
/* Primary */
div[data-testid="column"]:first-child div.stButton > button,
.btn-primary div.stButton > button {
    background: #3B82F6 !important; color: white !important;
    box-shadow: 0 2px 8px rgba(59,130,246,0.35) !important;
}
div.stButton > button:hover { filter: brightness(1.08) !important; transform: translateY(-1px) !important; }

/* Tag badges */
.badge {
    display: inline-block; padding: 3px 10px; border-radius: 99px;
    font-size: 0.72rem; font-weight: 600; margin-right: 4px;
}
.badge-blue { background: #EFF6FF; color: #2563EB; }
.badge-green { background: #ECFDF5; color: #059669; }
.badge-red { background: #FEF2F2; color: #DC2626; }
.badge-gray { background: #F1F5F9; color: #475569; }

/* Status row untuk tabel */
.status-open { color: #F59E0B; font-weight: 600; }
.status-submit { color: #10B981; font-weight: 600; }

/* Log box */
.log-terminal {
    background: #0D1117; border-radius: 10px;
    padding: 16px; font-family: 'Courier New', monospace;
    font-size: 0.78rem; color: #7EE787;
    max-height: 320px; overflow-y: auto;
    white-space: pre-wrap; line-height: 1.6;
    border: 1px solid #30363D;
}

/* Bottom action bar */
.action-bar {
    position: sticky; bottom: 0;
    background: white; border-top: 1px solid #E2E8F0;
    padding: 14px 20px; margin-top: 16px;
    border-radius: 0 0 12px 12px;
    box-shadow: 0 -4px 16px rgba(0,0,0,0.06);
    display: flex; align-items: center; gap: 12px;
}

/* Remove default streamlit padding */
.block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }

/* Streamlit default overrides */
[data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ───
for k, v in {
    'sls_df': None, 'selected_idsls': set(),
    'scraping_running': False, 'scraping_log': [],
    'scraping_proc': None, 'scraping_done': False,
    'temp_template_path': None, '_log_done_flag': [],
    'active_tab': 'pilih',
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── HELPERS ───
@st.cache_data
def load_region_mapping():
    if not os.path.exists(REGION_FILE):
        return {}
    with open(REGION_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_codes(idsls):
    s = str(idsls).replace(".", "").strip().zfill(16)
    return {'kode_kab': s[:4], 'kode_kec': s[:7]}

@st.cache_data
def load_template_cached(key):
    path = key
    try:
        df = pd.read_excel(path, dtype=str)
        df.columns = df.columns.str.strip()
        if 'idsls' not in df.columns:
            return None
        df['idsls'] = df['idsls'].str.replace(r'\.0$', '', regex=True).str.strip()
        extracted = df['idsls'].apply(extract_codes).apply(pd.Series)
        for col in extracted.columns:
            if col not in df.columns:
                df[col] = extracted[col]
        return df
    except:
        return None

def read_proc_output(proc, log_list, done_flag):
    try:
        for line in iter(proc.stdout.readline, ''):
            if line:
                log_list.append(line.rstrip())
        proc.wait()
    finally:
        done_flag.append(True)

def create_temp_template(df_sel):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(DIR_PATH, f"_temp_{ts}.xlsx")
    df_sel.to_excel(path, index=False)
    return path

# ─── LOAD CONFIG ───
cfg = {}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE) as f:
        cfg = json.load(f)
region_data = load_region_mapping()

# ═══════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="padding: 8px 0 20px 0;">
        <div style="font-size:1.15rem; font-weight:700; color:white;">⚡ Scraping Manager</div>
        <div style="font-size:0.75rem; color:#64748B;">SE2026 · FASIH BPS</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Load Template ──
    st.markdown("<div style='font-size:0.75rem; color:#64748B; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;'>Template Jodi</div>", unsafe_allow_html=True)

    uploaded = st.file_uploader("Upload file baru", type=["xlsx"], label_visibility="collapsed")
    load_default_btn = st.button("Gunakan File Default", use_container_width=True)

    if uploaded:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        tmp.write(uploaded.read()); tmp.close()
        load_template_cached.clear()
        df_tpl = load_template_cached(tmp.name)
        if df_tpl is not None:
            st.session_state.sls_df = df_tpl
            st.session_state.selected_idsls = set()
            st.success(f"{uploaded.name} ({len(df_tpl)} SLS)")
        else:
            st.error("Kolom `idsls` tidak ditemukan!")
    elif load_default_btn:
        if os.path.exists(TEMPLATE_DEFAULT):
            load_template_cached.clear()
            df_tpl = load_template_cached(TEMPLATE_DEFAULT)
            if df_tpl is not None:
                st.session_state.sls_df = df_tpl
                st.session_state.selected_idsls = set()
                st.success(f"Template Jodi.xlsx ({len(df_tpl)} SLS)")
            else:
                st.error("Gagal baca template!")
        else:
            st.error("File default tidak ada!")
    elif st.session_state.sls_df is None and os.path.exists(TEMPLATE_DEFAULT):
        df_tpl = load_template_cached(TEMPLATE_DEFAULT)
        if df_tpl is not None:
            st.session_state.sls_df = df_tpl

    st.markdown("---")

    # ── Filter Wilayah ──
    if st.session_state.sls_df is not None:
        df_all = st.session_state.sls_df

        st.markdown("<div style='font-size:0.75rem; color:#64748B; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;'>Filter Wilayah</div>", unsafe_allow_html=True)

        # Kabupaten
        kab_codes = sorted(df_all['kode_kab'].dropna().unique()) if 'kode_kab' in df_all.columns else []
        kab_labels = {}
        for code in kab_codes:
            name = region_data.get(code, {}).get("name", "") if region_data else ""
            kab_labels[code] = f"{code} — {name}" if name else code

        sel_kab = st.multiselect(
            "Kabupaten/Kota",
            options=list(kab_labels.values()),
            placeholder="Semua kabupaten…"
        )
        sel_kab_codes = [k for k, v in kab_labels.items() if v in sel_kab]

        # Kecamatan (dinamis)
        df_kec_src = df_all[df_all['kode_kab'].isin(sel_kab_codes)] if sel_kab_codes and 'kode_kab' in df_all.columns else df_all
        kec_codes = sorted(df_kec_src['kode_kec'].dropna().unique()) if 'kode_kec' in df_kec_src.columns else []
        kec_labels = {}
        for code in kec_codes:
            kab_code = code[:4]
            name = ""
            if region_data and kab_code in region_data:
                for kc, ki in region_data[kab_code].get("kecamatan", {}).items():
                    if kc[:7] == code:
                        name = ki.get("name", ""); break
            kec_labels[code] = f"{code} — {name}" if name else code

        sel_kec = st.multiselect(
            "Kecamatan",
            options=list(kec_labels.values()),
            placeholder="Semua kecamatan…"
        )
        sel_kec_codes = [k for k, v in kec_labels.items() if v in sel_kec]

        # Filter PPL
        ppl_list = []
        if 'PPL' in df_all.columns:
            ppl_list = sorted(df_all['PPL'].dropna().unique().tolist())
        sel_ppl = st.multiselect("PPL", options=ppl_list, placeholder="Semua PPL…")

        st.markdown("---")

        # ── Info Terpilih ──
        total_sel = len(st.session_state.selected_idsls)
        st.markdown(f"""
        <div style="background:#1E3A5F; border-radius:10px; padding:14px 16px;">
            <div style="font-size:0.75rem; color:#93C5FD; text-transform:uppercase; letter-spacing:0.05em;">SLS Dipilih</div>
            <div style="font-size:2rem; font-weight:700; color:white; line-height:1.2;">{total_sel}</div>
            <div style="font-size:0.75rem; color:#64748B;">dari {len(df_all)} total SLS</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # ── Tombol aksi ──
        if st.button("Pilih Semua yang Tampil", use_container_width=True):
            # akan dihitung dari df_filtered di bawah
            st.session_state['_select_all_filtered'] = True
            st.rerun()
        if st.button("Batalkan Semua yang Tampil", use_container_width=True):
            st.session_state['_deselect_all_filtered'] = True
            st.rerun()
        if st.button("Reset Semua Pilihan", use_container_width=True):
            st.session_state.selected_idsls = set()
            st.rerun()

        st.markdown("---")

        # ── Konfigurasi Scraping ──
        st.markdown("<div style='font-size:0.75rem; color:#64748B; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;'>Pengaturan Scraping</div>", unsafe_allow_html=True)

        mode_detail = st.toggle(
            "Scrape Detail Data",
            value=True,
            help="Aktif = ambil semua jawaban kuesioner (lebih lengkap tapi lebih lama). Nonaktif = hanya data status & identitas usaha."
        )
        max_w = st.select_slider(
            "Koneksi Paralel",
            options=[10, 20, 30, 50, 80, 100, 150],
            value=80,
            help="Lebih tinggi = lebih cepat, tapi lebih berisiko rate-limit."
        )

# ═══════════════════════════════════════
# MAIN CONTENT
# ═══════════════════════════════════════

if st.session_state.sls_df is None:
    # ── Empty state ──
    st.markdown("""
    <div style="text-align:center; padding: 80px 20px;">
        <div style="font-size:3rem; margin-bottom:16px;">📋</div>
        <div style="font-size:1.2rem; font-weight:600; color:#1E293B; margin-bottom:8px;">Belum ada Template</div>
        <div style="color:#64748B;">Upload file Template Jodi.xlsx atau klik "Gunakan File Default" di sidebar kiri.</div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

df_all = st.session_state.sls_df

# ── Apply filter ──
df_filtered = df_all.copy()
if sel_kab_codes and 'kode_kab' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['kode_kab'].isin(sel_kab_codes)]
if sel_kec_codes and 'kode_kec' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['kode_kec'].isin(sel_kec_codes)]
if sel_ppl and 'PPL' in df_filtered.columns:
    df_filtered = df_filtered[df_filtered['PPL'].isin(sel_ppl)]

# ── Handle "select all filtered" / "deselect all filtered" ──
if st.session_state.pop('_select_all_filtered', False):
    for idsls in df_filtered['idsls'].tolist():
        st.session_state.selected_idsls.add(str(idsls))
if st.session_state.pop('_deselect_all_filtered', False):
    for idsls in df_filtered['idsls'].tolist():
        st.session_state.selected_idsls.discard(str(idsls))

# ── TOP BAR ──
n_sel = len(st.session_state.selected_idsls)
n_filt = len(df_filtered)
n_all = len(df_all)
prov_label = cfg.get('prov_name', 'Belum diatur')

st.markdown(f"""
<div class="top-bar">
    <div>
        <div class="top-bar-title">Scraping Manager SE2026</div>
        <div class="top-bar-sub">Provinsi: {prov_label} &nbsp;·&nbsp; Template: {n_all} SLS</div>
    </div>
    <div style="display:flex; gap:24px; text-align:right;">
        <div>
            <div style="font-size:1.6rem; font-weight:700; color:#60A5FA; line-height:1;">{n_filt}</div>
            <div style="font-size:0.7rem; color:#64748B; text-transform:uppercase;">Tampil</div>
        </div>
        <div>
            <div style="font-size:1.6rem; font-weight:700; color:#34D399; line-height:1;">{n_sel}</div>
            <div style="font-size:0.7rem; color:#64748B; text-transform:uppercase;">Dipilih</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── TABEL SLS ──

# Kolom yang ditampilkan
display_cols = ['idsls']
for c in ['nmsls', 'nama_sls', 'namasls', 'kdsubsls', 'PPL', 'Pj-Kuda', 'Kecamatan', 'kecamatan', 'Kabupaten', 'kabupaten', 'kode_kab', 'kode_kec']:
    if c in df_filtered.columns:
        display_cols.append(c)

# Tambahkan kolom status pilihan
df_show = df_filtered[display_cols].copy()
df_show.insert(0, '✓', df_show['idsls'].apply(
    lambda x: '✓' if str(x) in st.session_state.selected_idsls else ''
))

# Pagination
PAGE_SIZE = 30
n_pages = max(1, (n_filt + PAGE_SIZE - 1) // PAGE_SIZE)
h1, h2, h3 = st.columns([4, 1, 1])
with h1:
    st.markdown(f"""
    <div style="background:white; border-radius:10px; border:1px solid #E2E8F0; padding:12px 16px; margin-bottom:8px;">
        <span style="font-weight:600; color:#1E293B;">Daftar SLS</span>
        <span style="color:#64748B; font-size:0.85rem; margin-left:8px;">— klik baris untuk centang/uncentang</span>
    </div>
    """, unsafe_allow_html=True)
with h2:
    page_num = st.number_input("Hal", min_value=1, max_value=n_pages, value=1, step=1, label_visibility="collapsed")
with h3:
    st.markdown(f"<div style='padding:8px 0; color:#64748B; font-size:0.85rem;'>/{n_pages} hal</div>", unsafe_allow_html=True)

start = (page_num - 1) * PAGE_SIZE
df_page = df_filtered.iloc[start:start+PAGE_SIZE].copy()
df_page.insert(0, '✓', df_page['idsls'].apply(
    lambda x: '✓' if str(x) in st.session_state.selected_idsls else ''
))
page_display_cols = ['✓'] + [c for c in display_cols if c in df_page.columns]

# Gunakan st.data_editor untuk interaksi centang lewat checkbox kolom boolean
df_page_edit = df_page[page_display_cols].copy()
df_page_edit['Pilih'] = df_page_edit['idsls'].apply(
    lambda x: str(x) in st.session_state.selected_idsls
)
cols_for_edit = ['Pilih'] + [c for c in display_cols if c in df_page_edit.columns]

edited = st.data_editor(
    df_page_edit[cols_for_edit],
    use_container_width=True,
    hide_index=True,
    height=min(35 * len(df_page_edit) + 40, 520),
    column_config={
        "Pilih": st.column_config.CheckboxColumn("Pilih", width=60),
        "idsls": st.column_config.TextColumn("ID SLS", width=180),
        "PPL": st.column_config.TextColumn("PPL", width=160),
        "nmsls": st.column_config.TextColumn("Nama SLS"),
        "namasls": st.column_config.TextColumn("Nama SLS"),
        "kdsubsls": st.column_config.TextColumn("Kode Sub SLS", width=100),
        "kode_kab": st.column_config.TextColumn("Kode Kab", width=90),
        "kode_kec": st.column_config.TextColumn("Kode Kec", width=90),
    },
    disabled=[c for c in cols_for_edit if c != 'Pilih'],
    key="sls_editor"
)

# Sinkronisasi hasil edit ke selected_idsls
if edited is not None and 'Pilih' in edited.columns and 'idsls' in edited.columns:
    changed = False
    for _, row in edited.iterrows():
        idsls_val = str(row['idsls'])
        was_selected = idsls_val in st.session_state.selected_idsls
        now_selected = bool(row['Pilih'])
        if was_selected != now_selected:
            changed = True
            if now_selected:
                st.session_state.selected_idsls.add(idsls_val)
            else:
                st.session_state.selected_idsls.discard(idsls_val)
    if changed:
        st.rerun()

st.caption(f"Baris {start+1}–{min(start+PAGE_SIZE, n_filt)} dari {n_filt} · Halaman {page_num}/{n_pages}")

# ── TOMBOL MULAI SCRAPING (sticky bottom-ish) ──
st.markdown("---")

config_ok = bool(cfg.get("survey_period_id") and cfg.get("region1Id"))
region_ok = os.path.exists(REGION_FILE)
can_scrape = config_ok and region_ok and n_sel > 0 and not st.session_state.scraping_running

b1, b2, b3 = st.columns([2, 1, 1])
with b1:
    if n_sel == 0:
        st.info("Centang SLS yang ingin di-scrape dari tabel di atas.")
    elif not config_ok or not region_ok:
        st.error("config.json atau region_mapping.json belum siap. Jalankan setup survei di main.py dulu.")
    else:
        mode_label = "Datatable + Detail" if mode_detail else "Datatable Saja"
        st.markdown(f"""
        <div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:10px; padding:12px 16px;">
            <div style="font-weight:600; color:#166534;">Siap scraping {n_sel} SLS</div>
            <div style="color:#16A34A; font-size:0.85rem;">Mode: {mode_label} · Paralel: {max_w}</div>
        </div>
        """, unsafe_allow_html=True)

with b2:
    if st.button(
        "Mulai Scraping" if not st.session_state.scraping_running else "Sedang Berjalan...",
        use_container_width=True,
        disabled=not can_scrape,
        type="primary"
    ):
        df_sel = df_all[df_all['idsls'].isin(st.session_state.selected_idsls)].copy()
        temp_path = create_temp_template(df_sel)
        st.session_state.temp_template_path = temp_path

        # Panggil main.py langsung dengan argumen — proses login, scraping,
        # assembly output (Hasil_Scraping_Jodi_Lengkap_*) semuanya berjalan normal
        mode_arg = "1" if not mode_detail else "2"
        proc = subprocess.Popen(
            [
                sys.executable, MAIN_PY,
                "--template", temp_path,
                "--mode", mode_arg,
                "--workers", str(max_w)
            ],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', bufsize=1, cwd=DIR_PATH
        )
        st.session_state.scraping_proc = proc
        st.session_state.scraping_running = True
        st.session_state.scraping_done = False
        ts_now = datetime.now().strftime('%H:%M:%S')
        st.session_state.scraping_log = [
            f"[{ts_now}] Scraping dimulai · {n_sel} SLS · {'Detail' if mode_detail else 'Datatable saja'}",
            "─" * 50
        ]
        done_flag = []
        st.session_state._log_done_flag = done_flag
        threading.Thread(
            target=read_proc_output,
            args=(proc, st.session_state.scraping_log, done_flag),
            daemon=True
        ).start()
        st.rerun()

with b3:
    if st.session_state.scraping_running:
        if st.button("Hentikan", use_container_width=True):
            proc = st.session_state.scraping_proc
            if proc: proc.terminate()
            st.session_state.scraping_running = False
            st.session_state.scraping_log.append("⛔ Dihentikan oleh user.")
            try:
                if st.session_state.temp_template_path and os.path.exists(st.session_state.temp_template_path):
                    os.remove(st.session_state.temp_template_path)
            except: pass
            st.rerun()

# ── LOG OUTPUT ──
if st.session_state.scraping_log:
    st.markdown("#### Log Output")

    proc = st.session_state.scraping_proc
    if proc and proc.poll() is not None and st.session_state.scraping_running:
        if st.session_state._log_done_flag:
            rc = proc.returncode
            if rc == 0:
                st.session_state.scraping_log.append("\n✅ Scraping BERHASIL selesai! File output tersimpan di folder project.")
                st.session_state.scraping_done = True
                # Hapus template sementara
                try:
                    if st.session_state.temp_template_path and os.path.exists(st.session_state.temp_template_path):
                        os.remove(st.session_state.temp_template_path)
                except: pass
            else:
                st.session_state.scraping_log.append(f"❌ Error (exit code {rc})")
            st.session_state.scraping_running = False

    log_txt = "\n".join(st.session_state.scraping_log[-200:])
    st.code(log_txt, language="bash")

    if st.session_state.scraping_running:
        st.progress(0.5, text="Berjalan...")
        time.sleep(1.5)
        st.rerun()
    elif st.session_state.scraping_done:
        st.success("Scraping selesai! File output ada di folder project.")
        # Tampilkan file output
        try:
            out_files = sorted(
                [f for f in os.listdir(DIR_PATH)
                 if f.startswith("Hasil_Scraping_Jodi_Lengkap_")],
                key=lambda x: os.path.getmtime(os.path.join(DIR_PATH, x)), reverse=True
            )[:8]
            if out_files:
                st.markdown("**📁 File Output Terbaru:**")
                for fn in out_files:
                    fpath = os.path.join(DIR_PATH, fn)
                    sz = os.path.getsize(fpath) / 1_048_576
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%d/%m/%Y %H:%M')
                    st.markdown(f"- 📄 `{fn}` — **{sz:.1f} MB** · {mtime}")
        except: pass
        if st.button("Reset"):
            st.session_state.scraping_done = False
            st.session_state.scraping_log = []
            st.rerun()
