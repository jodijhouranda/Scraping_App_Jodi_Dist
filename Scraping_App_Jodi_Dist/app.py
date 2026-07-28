import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Dashboard Anomali SE2026", layout="wide", page_icon="⚡")

# --- CUSTOM CSS FOR MODERN LOOK ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }
    
    .stApp {
        background-color: #F8FAFC;
    }
    
    .modern-card {
        background-color: white;
        padding: 24px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        margin-bottom: 24px;
        border: 1px solid #E2E8F0;
    }
    
    h1, h2, h3 {
        color: #0F172A;
        font-weight: 600 !important;
    }
    
    .title-gradient {
        background: -webkit-linear-gradient(45deg, #2563EB, #7C3AED);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        font-size: 2.2rem;
        margin-bottom: 0px;
    }
    
    .ai-output {
        background-color: #F1F5F9;
        border-left: 4px solid #8B5CF6;
        padding: 16px 20px;
        border-radius: 0 8px 8px 0;
        color: #334155;
        font-size: 0.95rem;
        line-height: 1.6;
    }
    
    .stButton>button {
        background-color: #0F172A;
        color: white;
        border-radius: 8px;
        font-weight: 500;
        border: none;
        padding: 0.5rem 1rem;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        background-color: #1E293B;
        color: white;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.15);
    }
    
    /* Custom Styling for Anomaly Variables */
    .var-row {
        padding: 12px 16px;
        border-radius: 8px;
        border: 1px solid #E2E8F0;
        margin-bottom: 12px;
        background: white;
        transition: all 0.2s ease;
    }
    .var-row:hover {
        border-color: #CBD5E1;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .var-anomaly {
        background: #FEF2F2;
        border-left: 4px solid #EF4444;
        border-top: 1px solid #FEE2E2;
        border-right: 1px solid #FEE2E2;
        border-bottom: 1px solid #FEE2E2;
    }
    .var-anomaly:hover {
        border-color: #FCA5A5;
        border-left: 4px solid #EF4444;
    }
    .status-badge-ok {
        background: #D1FAE5;
        color: #065F46;
        padding: 4px 12px;
        border-radius: 99px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }
    .status-badge-err {
        background: #FEE2E2;
        color: #991B1B;
        padding: 4px 12px;
        border-radius: 99px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# --- MOCK DATA LOADING & PARSER ---
def get_available_files():
    import glob
    # Baca file Parquet dan CSV hasil scraping baru
    files = glob.glob('*Detail_Data.csv') + glob.glob('*jodi_detail_assignment*.parquet') + glob.glob('*jodi_detail_assignment*.csv')
    return sorted(list(set(files)), reverse=True)

@st.cache_data
def load_data(file_path):
    if not file_path or not os.path.exists(file_path):
        return pd.DataFrame()
        
    try:
        if file_path.endswith('.parquet'):
            df = pd.read_parquet(file_path)
        else:
            df = pd.read_csv(file_path, low_memory=False)
            
        # PPL identifier
        if 'user_id_responsibility' in df.columns and 'currentUserFullname' not in df.columns:
            df['currentUserFullname'] = df['user_id_responsibility']
            
        if 'codeIdentity' in df.columns and 'ans_nama_usaha_edit#2' in df.columns:
            df['Human_ID'] = df['codeIdentity'].astype(str) + " | " + df['ans_nama_usaha_edit#2'].astype(str)
        elif 'codeIdentity' in df.columns:
            df['Human_ID'] = df['codeIdentity']
            
        if 'assignmentStatusAlias' not in df.columns:
            if 'Status Assignment' in df.columns:
                df['assignmentStatusAlias'] = df['Status Assignment']
            else:
                df['assignmentStatusAlias'] = 'SUBMIT'
            
        # Append Status to Human ID for the Deep Dive Dropdown
        if 'Human_ID' in df.columns:
            df['Human_ID_With_Status'] = df['Human_ID'].astype(str) + " (" + df['assignmentStatusAlias'].astype(str) + ")"
            
        return df
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return pd.DataFrame()

@st.cache_data
def parse_kamus():
    """Load GUI mapping dari gui_mapping.json untuk merender tabs dan urutan variabel."""
    import json
    blocks = {}
    try:
        with open('gui_mapping.json', 'r', encoding='utf-8') as f:
            mapping = json.load(f)
        
        for var_name, info in mapping.items():
            block_name = info.get("block", "General")
            if not block_name:
                block_name = "General"
                
            if block_name not in blocks:
                blocks[block_name] = []
                
            blocks[block_name].append({'var': var_name, 'question': info.get('question', var_name)})
            
        # Urutkan berdasarkan kemunculan atau abjad
        return blocks
    except Exception as e:
        st.error(f"Gagal memuat gui_mapping.json: {e}")
        return {}

@st.cache_data
def load_var_options():
    """Load Kamus_Bridging.json - mapping variabel mesin ke pertanyaan asli Fasih CAPI."""
    import json
    # Prioritas: Kamus_Bridging.json (lebih lengkap, sudah di-filter CSS)
    for fname in ['Kamus_Bridging.json', 'var_options.json']:
        try:
            with open(fname, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except:
            continue
    return {}

var_options = load_var_options()

available_files = get_available_files()

# Add a global dataset selector at the top of the sidebar (since it's a global config, sidebar is the best place for settings)
# If user hates sidebar for navigation, it's okay, but for file selection it's standard. Let's put it at the top of the app instead to strictly follow "jangan di side bar".
st.markdown("<div style='background:#F8FAFC; border:1px solid #E2E8F0; padding:12px; border-radius:8px; margin-bottom:20px; display:flex; align-items:center; gap:16px;'>", unsafe_allow_html=True)
selected_file = st.selectbox("📂 Pilih Sumber Data (CSV/Parquet):", options=available_files, index=0 if available_files else None)
st.markdown("</div>", unsafe_allow_html=True)

if selected_file:
    df_raw = load_data(selected_file)
else:
    df_raw = load_data(None)

kamus_blocks = parse_kamus()
if 'assigned_PPL' in df_raw.columns:
    list_ppl = sorted(df_raw['assigned_PPL'].dropna().unique().tolist())
elif 'currentUserFullname' in df_raw.columns:
    list_ppl = sorted(df_raw['currentUserFullname'].dropna().unique().tolist())
else:
    list_ppl = ["PPL Mock 1", "PPL Mock 2"]

# --- SIDEBAR AI CONFIG ---
with st.sidebar:
    st.markdown("<h3 style='color:#0F172A; font-weight:700;'>🤖 AI Model Config</h3>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:0.8rem; color:#64748B;'>Konfigurasi model Qwen / DeepSeek via Streamlit Secrets.</p>", unsafe_allow_html=True)
        
    available_models = [
        "qwen3.7-max-2026-05-20",
        "qwen3.7-max-2026-05-17",
        "deepseek-v4-pro",
        "qwen3.7-plus-2026-05-26",
        "qwen3.6-plus-2026-04-02",
        "qwen3.5-plus-2026-04-20",
        "qwen3.5-plus",
        "qwen3-max-2026-01-23",
        "qwen3-max-2025-09-23",
        "glm-5.1"
    ]
    
    ai_model = st.selectbox("Pilih Model AI", options=available_models, index=available_models.index(st.session_state.get('ai_model', available_models[0])) if st.session_state.get('ai_model') in available_models else 0)
    
    if st.session_state.get('ai_model') != ai_model:
        st.session_state['ai_model'] = ai_model
        st.rerun()
        
    st.markdown("---")

# --- PAGES ---

# Analyze function
def analyze_ppl(df_ppl, ppl_name):
    anomalies = []
    
    # Filter hanya yang berstatus SUBMIT atau DRAFT
    mask_sub = df_ppl['assignmentStatusAlias'].str.contains("SUBMIT|DRAFT", case=False, na=False) if 'assignmentStatusAlias' in df_ppl.columns else pd.Series(True, index=df_ppl.index)
    df_sub = df_ppl[mask_sub].copy()
    if df_sub.empty:
        return [{
            "PPL": ppl_name,
            "Anomali Pattern": "PPL belum melakukan Submit/Draft (semua dokumen masih OPEN/kosong).",
            "Tingkat Anomali": "Info",
            "Data Detail": pd.DataFrame()
        }]

    expert_dfs = []
    
    def append_expert(mask, rule, ket, blok, rincian, cols_to_show, suffix_val="2"):
        if not mask.any(): return
        bad = df_sub[mask].copy()
        
        usaha_name_col = f"ans_nama_usaha_edit#{suffix_val}"
        fallback_col = f"ans_nama_usaha#{suffix_val}"
        
        if usaha_name_col in bad.columns:
            bad['Usaha'] = bad[usaha_name_col]
        elif fallback_col in bad.columns:
            bad['Usaha'] = bad[fallback_col]
        else:
            bad['Usaha'] = ""
            
        bad['Blok'] = blok
        bad['Rincian'] = rincian
        bad['Rule Dilanggar'] = rule
        
        if isinstance(ket, str):
            bad['Keterangan'] = ket
        else:
            bad['Keterangan'] = ket(bad)
            
        cols = ['codeIdentity', 'Usaha', 'Blok', 'Rincian', 'Rule Dilanggar', 'Keterangan']
        expert_dfs.append(bad[cols])

    # 1. Speed-run Anomaly
    if 'ans_waktu_selesai' in df_sub.columns and ('ans_mulai' in df_sub.columns or 'ans_ec_mulai' in df_sub.columns):
        mulai_col = 'ans_mulai' if 'ans_mulai' in df_sub.columns else 'ans_ec_mulai'
        
        try:
            w_selesai = pd.to_datetime(df_sub['ans_waktu_selesai'], errors='coerce', utc=True)
            w_mulai = pd.to_datetime(df_sub[mulai_col], errors='coerce', utc=True)
            diff_mins = (w_selesai - w_mulai).dt.total_seconds() / 60.0
            
            mask_valid = pd.Series(False, index=df_sub.index)
            if 'ans_ada_keluarga' in df_sub.columns:
                mask_valid = df_sub['ans_ada_keluarga'].astype(str).str.contains(r'^[12]\.', na=False)
            elif 'ans_kode_keberadaan_usaha#1' in df_sub.columns:
                mask_valid = df_sub['ans_kode_keberadaan_usaha#1'].astype(str).str.contains(r'^[124]\.', na=False)
                
            mask_fast = mask_valid & (diff_mins >= 0) & (diff_mins < 2)
            fast_count = mask_fast.sum()
            
            if fast_count > 5:
                bad_rows = df_sub[mask_fast].copy()
                bad_rows['Waktu_Mulai'] = bad_rows[mulai_col]
                bad_rows['Waktu_Selesai'] = bad_rows['ans_waktu_selesai']
                bad_rows['Durasi_Menit'] = diff_mins[mask_fast].round(2)
                bad_rows['Blok'] = 'Sistem CAPI'
                bad_rows['Rincian'] = 'Waktu Wawancara'
                
                display_cols = ['codeIdentity', 'Blok', 'Rincian', 'Waktu_Mulai', 'Waktu_Selesai', 'Durasi_Menit']
                if 'ans_nama_usaha_edit#2' in bad_rows.columns: display_cols.insert(1, 'ans_nama_usaha_edit#2')
                anomalies.append({
                    "PPL": ppl_name,
                    "Anomali Pattern": f"Speed-run: {fast_count} dokumen diselesaikan dengan durasi riil < 2 menit per dokumen.",
                    "Tingkat Anomali": "Parah",
                    "Data Detail": bad_rows[display_cols]
                })
        except: pass

    # 1b. Lazy Skip: Listrik
    if 'ans_sumber_penerangan' in df_sub.columns:
        mask_lazy = df_sub['ans_sumber_penerangan'].astype(str).str.contains("tanpa meteran", case=False, na=False)
        lazy_count = mask_lazy.sum()
        if lazy_count > 0:
            bad_rows = df_sub[mask_lazy].copy()
            bad_rows['Blok'] = 'Blok I: Identitas'
            bad_rows['Rincian'] = 'Listrik'
            display_cols = ['codeIdentity', 'Blok', 'Rincian', 'ans_sumber_penerangan']
            if 'ans_nama_usaha_edit#2' in bad_rows.columns: display_cols.insert(1, 'ans_nama_usaha_edit#2')
            anomalies.append({
                "PPL": ppl_name,
                "Anomali Pattern": f"Lazy Skip: {lazy_count} dokumen memilih 'Listrik PLN tanpa meteran' (diduga untuk menghindari input ID Pelanggan).",
                "Tingkat Anomali": "Sedang",
                "Data Detail": bad_rows[display_cols]
            })

    # Multivariate loops using vectorized column access
    tk_cols = [c for c in df_sub.columns if c.startswith('ans_tk_dibayar#')]
    for tk_c in tk_cols:
        suffix = tk_c.split('#')[1]
        gaji_c = f"ans_gaji#{suffix}"
        if gaji_c in df_sub.columns:
            tk_val = pd.to_numeric(df_sub[tk_c], errors='coerce').fillna(0)
            gaji_val = pd.to_numeric(df_sub[gaji_c], errors='coerce').fillna(0)
            mask_gaji = (tk_val > 0) & (gaji_val <= 0)
            if mask_gaji.sum() > 0:
                bad_rows = df_sub[mask_gaji].copy()
                bad_rows['Blok'] = 'Blok V & VI'
                bad_rows['Rincian'] = 'Rincian 501 & 602'
                display_cols = ['codeIdentity', 'Blok', 'Rincian', tk_c, gaji_c]
                if 'ans_nama_usaha_edit#2' in bad_rows.columns: display_cols.insert(1, 'ans_nama_usaha_edit#2')
                anomalies.append({
                    "PPL": ppl_name,
                    "Anomali Pattern": f"Tenaga Kerja vs Gaji (Usaha #{suffix}): {mask_gaji.sum()} dokumen melaporkan punya tenaga kerja dibayar, tapi Total Gaji = 0.",
                    "Tingkat Anomali": "Parah",
                    "Data Detail": bad_rows[display_cols]
                })

    peng_cols = [c for c in df_sub.columns if c.startswith('ans_total_pengeluaran#')]
    for peng_c in peng_cols:
        suffix = peng_c.split('#')[1]
        pend_c = f"ans_total_pendapatan#{suffix}"
        if pend_c in df_sub.columns:
            peng_val = pd.to_numeric(df_sub[peng_c], errors='coerce').fillna(0)
            pend_val = pd.to_numeric(df_sub[pend_c], errors='coerce').fillna(0)
            mask_rugi = (peng_val > pend_val) & (pend_val > 0)
            if mask_rugi.sum() > 0:
                bad_rows = df_sub[mask_rugi].copy()
                bad_rows['Blok'] = 'Blok VI: Keuangan'
                bad_rows['Rincian'] = 'Rincian 601 & 602'
                display_cols = ['codeIdentity', 'Blok', 'Rincian', peng_c, pend_c]
                if 'ans_nama_usaha_edit#2' in bad_rows.columns: display_cols.insert(1, 'ans_nama_usaha_edit#2')
                anomalies.append({
                    "PPL": ppl_name,
                    "Anomali Pattern": f"Rugi Finansial Ekstrem (Usaha #{suffix}): {mask_rugi.sum()} dokumen melaporkan Pengeluaran melebihi Total Pendapatan.",
                    "Tingkat Anomali": "Sedang",
                    "Data Detail": bad_rows[display_cols]
                })

    data_cols = [c for c in df_sub.columns if c.startswith('ans_')]
    if data_cols:
        missing_rates = df_sub[data_cols].isnull().mean(axis=1)
        mask_missing = missing_rates > 0.5
        if mask_missing.sum() > 0:
            bad_rows = df_sub[mask_missing].copy()
            bad_rows['Persentase_Kosong'] = (missing_rates[mask_missing] * 100).round(1).astype(str) + "%"
            bad_rows['Blok'] = 'Kuesioner Utama'
            bad_rows['Rincian'] = 'Seluruh Rincian'
            display_cols = ['codeIdentity', 'Blok', 'Rincian', 'Persentase_Kosong']
            if 'ans_nama_usaha_edit#2' in bad_rows.columns: display_cols.insert(1, 'ans_nama_usaha_edit#2')
            anomalies.append({
                "PPL": ppl_name,
                "Anomali Pattern": f"Missing Data: {mask_missing.sum()} dokumen memiliki lebih dari 50% kolom kosong.",
                "Tingkat Anomali": "Sedang",
                "Data Detail": bad_rows[display_cols]
            })

    # --- EXPERT RULES VECTORIZED ---
    tk_cols_tot = [c for c in df_sub.columns if c.startswith('ans_total_tk_jk#')]
    for tc in tk_cols_tot:
        suffix = tc.split('#')[1]
        dibayar_c = f"ans_tk_dibayar#{suffix}"
        tdk_dibayar_c = f"ans_tk_tdk_dibayar#{suffix}"
        badan_c = f"ans_badan_usaha#{suffix}"
        
        tot = pd.to_numeric(df_sub[tc], errors='coerce').fillna(0)
        
        if dibayar_c in df_sub.columns and tdk_dibayar_c in df_sub.columns:
            dib = pd.to_numeric(df_sub[dibayar_c], errors='coerce').fillna(0)
            tdk = pd.to_numeric(df_sub[tdk_dibayar_c], errors='coerce').fillna(0)
            
            # Pekerja Tunggal
            mask1 = (tot == 1) & (dib > 0)
            append_expert(mask1, "Pekerja Tunggal", f"Usaha #{suffix} punya 1 pekerja tapi dicatat sebagai 'dibayar'. Seharusnya 'tidak dibayar' (pemilik).", "Blok V: Tenaga Kerja", "Rincian 501", [], suffix)
            
            # Konsistensi Penjumlahan
            mask_sum = (tot > 0) & (tot != (dib + tdk))
            append_expert(mask_sum, "Konsistensi Penjumlahan", lambda df: f"Usaha #{suffix}: Total pekerja tidak sama dengan jumlah dibayar + tidak dibayar.", "Blok V: Tenaga Kerja", "Rincian 501", [], suffix)
            
            # JK Tunggal
            laki_c = f"ans_tk_laki#{suffix}"
            jk_peng_c = f"ans_jk_var#{suffix}"
            if laki_c in df_sub.columns and jk_peng_c in df_sub.columns:
                laki = pd.to_numeric(df_sub[laki_c], errors='coerce').fillna(0)
                jk_peng = pd.to_numeric(df_sub[jk_peng_c], errors='coerce').fillna(0)
                mask_jk = (tot == 1) & (((jk_peng == 1) & (laki != 1)) | ((jk_peng == 2) & (laki != 0)))
                append_expert(mask_jk, "Jenis Kelamin Tunggal", f"Usaha #{suffix} berpekerja 1 orang, tapi isian pekerja Laki-laki tidak selaras dengan Jenis Kelamin Pengusaha.", "Blok V: Tenaga Kerja", "Rincian 501", [], suffix)
                
            # BUM Desa
            if badan_c in df_sub.columns:
                mask_bum = df_sub[badan_c].astype(str).str.contains(r"^(6\.|BUM Desa|BUMNag)", case=False, na=False)
                if mask_bum.sum() > 0:
                    pem = pd.to_numeric(df_sub.get(f"ans_modal_pemerintah#{suffix}", pd.Series(0, index=df_sub.index)), errors='coerce').fillna(0)
                    prib = pd.to_numeric(df_sub.get(f"ans_modal_pribadi#{suffix}", pd.Series(0, index=df_sub.index)), errors='coerce').fillna(0)
                    asing = pd.to_numeric(df_sub.get(f"ans_modal_asing#{suffix}", pd.Series(0, index=df_sub.index)), errors='coerce').fillna(0)
                    swasta = pd.to_numeric(df_sub.get(f"ans_modal_swasta#{suffix}", pd.Series(0, index=df_sub.index)), errors='coerce').fillna(0)
                    korp = pd.to_numeric(df_sub.get(f"ans_modal_korporasi#{suffix}", pd.Series(0, index=df_sub.index)), errors='coerce').fillna(0)
                    
                    tot_modal = pem + prib + asing + swasta + korp
                    
                    if f"ans_modal_pemerintah#{suffix}" in df_sub.columns:
                        append_expert(mask_bum & (pem <= 0), "Modal BUM Desa", f"Usaha #{suffix} (BUM Desa) tapi Modal Pemerintah 0%.", "Blok II: Legalitas", "Rincian 202", [], suffix)
                        append_expert(mask_bum & (pem <= prib) & (pem > 0), "Modal BUM Desa", f"Usaha #{suffix} (BUM Desa) tapi Modal Pemerintah <= Pribadi.", "Blok II: Legalitas", "Rincian 202", [], suffix)
                        append_expert(mask_bum & ((asing + swasta + korp) >= 50), "Modal BUM Desa", f"Usaha #{suffix} (BUM Desa) tapi Gabungan Asing/Swasta/Korp >= 50%.", "Blok II: Legalitas", "Rincian 202", [], suffix)
                        append_expert(mask_bum & (tot_modal > 0) & (tot_modal != 100), "Total Modal", f"Total persentase modal Usaha #{suffix} tidak 100%.", "Blok II: Legalitas", "Rincian 202", [], suffix)

        if badan_c in df_sub.columns:
            mask_formal = df_sub[badan_c].astype(str).str.contains(r'^[1-2]\.|PT|CV|Yayasan', case=False, na=False)
            if tdk_dibayar_c in df_sub.columns:
                tdk = pd.to_numeric(df_sub[tdk_dibayar_c], errors='coerce').fillna(0)
                append_expert(mask_formal & (tdk > 0), "Badan Usaha Formal", f"Usaha #{suffix} adalah Badan Usaha Formal tapi ada pekerja 'tidak dibayar'.", "Blok V: Tenaga Kerja", "Rincian 501", [], suffix)
            
            mask_kop = df_sub[badan_c].astype(str).str.contains(r"^(3\.|Koperasi)", case=False, na=False)
            append_expert(mask_kop & (tot > 0) & (tot < 3), "Logika Koperasi", f"Usaha #{suffix} adalah Koperasi tapi total pekerjanya < 3.", "Blok II: Legalitas", "Rincian 201", [], suffix)

    pend_cols = [c for c in df_sub.columns if c.startswith('ans_total_pendapatan_thn#') or c.startswith('ans_total_pendapatan#')]
    for pc in pend_cols:
        suffix = pc.split('#')[1]
        kat_c = f"ans_kategori#{suffix}"
        if kat_c in df_sub.columns:
            pend = pd.to_numeric(df_sub[pc], errors='coerce').fillna(0)
            mask_omzet = (pend > 0) & (pend < 100000) & ~df_sub[kat_c].astype(str).str.contains(r'^(A\.|Pertanian)', case=False, na=False)
            append_expert(mask_omzet, "Batas Minimal Omzet", lambda df: "Omzet Usaha di bawah batas minimal 100k.", "Blok VI: Keuangan", "Rincian 601", [], suffix)
            
            beli_c = f"ans_biaya_beli_barang#{suffix}"
            if beli_c not in df_sub.columns: beli_c = f"ans_biaya_beli_barang_bln#{suffix}"
            if beli_c not in df_sub.columns: beli_c = f"ans_biaya_beli_barang_thn#{suffix}"
            if beli_c in df_sub.columns:
                beli = pd.to_numeric(df_sub[beli_c], errors='coerce').fillna(0)
                mask_beli = (beli > 0) & ~df_sub[kat_c].astype(str).str.contains(r'^(G\.|Perdagangan)', case=False, na=False)
                append_expert(mask_beli, "Salah Kamar Biaya Dagang", "Sektor bukan Perdagangan tapi ada biaya 'Beli Barang Dagangan'.", "Blok VI: Keuangan", "Rincian 602", [], suffix)
                
            prod_c = f"ans_biaya_produksi#{suffix}"
            if prod_c not in df_sub.columns: prod_c = f"ans_biaya_produksi_bln#{suffix}"
            if prod_c not in df_sub.columns: prod_c = f"ans_biaya_produksi_thn#{suffix}"
            if prod_c in df_sub.columns:
                prod = pd.to_numeric(df_sub[prod_c], errors='coerce').fillna(0)
                mask_prod = (prod == 0) & df_sub[kat_c].astype(str).str.contains(r'^(B\.|C\.|D\.|E\.|F\.|I\.|Industri|Tambang|Makan)', case=False, na=False)
                append_expert(mask_prod, "Biaya Produksi Gaib", "Sektor Produksi/Mamin tapi Biaya Produksi Rp 0.", "Blok VI: Keuangan", "Rincian 602", [], suffix)

    aset_cols = [c for c in df_sub.columns if c.startswith('ans_total_aset_thn#') or c.startswith('ans_total_aset_bln#')]
    for ac in aset_cols:
        suffix = ac.split('#')[1]
        t_type = "thn" if "thn" in ac else "bln"
        tnh_c = f"ans_aset_tanah_{t_type}#{suffix}"
        lain_c = f"ans_aset_lain_{t_type}#{suffix}"
        luas_c = f"ans_luas_tanah_{t_type}#{suffix}"
        
        tot = pd.to_numeric(df_sub[ac], errors='coerce').fillna(0)
        if tnh_c in df_sub.columns and lain_c in df_sub.columns:
            tnh = pd.to_numeric(df_sub[tnh_c], errors='coerce').fillna(0)
            lain = pd.to_numeric(df_sub[lain_c], errors='coerce').fillna(0)
            mask_9999 = (tot == 9999) & ((tnh != 9999) | (lain != 9999))
            append_expert(mask_9999, "Aturan Aset 9999", "Total Aset diisi 9999 (Tidak Tahu) namun rincian tanah/lainnya ada yang bukan 9999.", "Blok VII: Aset", "Rincian 701", [], suffix)
            
        if tnh_c in df_sub.columns and luas_c in df_sub.columns:
            tnh = pd.to_numeric(df_sub[tnh_c], errors='coerce').fillna(0)
            luas = pd.to_numeric(df_sub[luas_c], errors='coerce').fillna(0)
            mask_luas = (tnh > 0) & (tnh != 9999) & (luas == 0)
            append_expert(mask_luas, "Tanah Tanpa Luas", "Aset Tanah dan Bangunan ada tapi Luas Tanah (m2) diisi 0.", "Blok VII: Aset", "Rincian 701", [], suffix)

    sosek_pend_cols = [c for c in df_sub.columns if c.startswith('ans_pend_usaha#') or c.startswith('ans_pend_usaha_lain#')]
    if sosek_pend_cols:
        kategori_cols = [c for c in df_sub.columns if c.startswith('ans_kategori#')]
        if kategori_cols:
            has_kategori = df_sub[kategori_cols].notnull().any(axis=1)
            has_sosek_pend = pd.Series(False, index=df_sub.index)
            for pc in sosek_pend_cols:
                pend_val = pd.to_numeric(df_sub[pc], errors='coerce').fillna(0)
                has_sosek_pend = has_sosek_pend | (pend_val > 0)
            mask_hidden = has_sosek_pend & ~has_kategori
            append_expert(mask_hidden, "Usaha Tersembunyi", "Keluarga memiliki pendapatan usaha (Sosek), tetapi tidak ada Kuesioner Usaha (L).", "Sosek/Keluarga", "Rincian 18b", [])

    nama_cols = [c for c in df_sub.columns if c.startswith('ans_nama_usaha_edit#')]
    for nc in nama_cols:
        suffix = nc.split('#')[1]
        nama_val = df_sub[nc].astype(str).str.lower()
        kbli_c = f"ans_kbli_akhir#{suffix}"
        
        mask_kreator = nama_val.str.contains('youtube|konten|affiliate|joki|freelance', case=False, na=False)
        if kbli_c in df_sub.columns:
            mask_wrong_kbli = mask_kreator & ~df_sub[kbli_c].astype(str).str.contains('5911|73100|59202', na=False)
            append_expert(mask_wrong_kbli, "KBLI Konten Kreator", "Terdeteksi digital/kreator tapi KBLI bukan 5911/73100/59202.", "Blok III: Karakteristik", "Rincian 302", [], suffix)
            
        prod_c = f"ans_biaya_produksi_bln#{suffix}"
        if prod_c not in df_sub.columns: prod_c = f"ans_biaya_produksi_thn#{suffix}"
        if prod_c not in df_sub.columns: prod_c = f"ans_biaya_produksi#{suffix}"
        if prod_c in df_sub.columns:
            prod = pd.to_numeric(df_sub[prod_c], errors='coerce').fillna(0)
            append_expert(mask_kreator & (prod > 0), "Biaya Produksi Digital", "Usaha Digital/Freelance memiliki Biaya Produksi > 0. Seharusnya Operasional.", "Blok VI: Keuangan", "Rincian 602", [], suffix)
            
        mask_catering = nama_val.str.contains('catering|katering', case=False, na=False)
        aset_c = f"ans_total_aset_bln#{suffix}"
        if aset_c not in df_sub.columns: aset_c = f"ans_total_aset_thn#{suffix}"
        omzet_c = f"ans_total_pendapatan_bln#{suffix}"
        if omzet_c not in df_sub.columns: omzet_c = f"ans_total_pendapatan_thn#{suffix}"
        if omzet_c not in df_sub.columns: omzet_c = f"ans_total_pendapatan#{suffix}"
        
        if aset_c in df_sub.columns and omzet_c in df_sub.columns:
            aset = pd.to_numeric(df_sub[aset_c], errors='coerce').fillna(0)
            omzet = pd.to_numeric(df_sub[omzet_c], errors='coerce').fillna(0)
            append_expert(mask_catering & (aset == 0) & (omzet > 1000000), "Aset Katering Fiktif", "Usaha Katering beromzet > Rp1 Juta tapi Aset diisi 0.", "Blok VII: Aset", "Rincian 701", [], suffix)

        izin_c = f"ans_izin_edar#{suffix}"
        if izin_c in df_sub.columns:
            mask_warung = nama_val.str.contains('warung|gorengan|kaki lima|keliling', case=False, na=False)
            mask_bpom = df_sub[izin_c].astype(str).str.contains('BPOM', case=False, na=False)
            append_expert(mask_warung & mask_bpom, "BPOM Fiktif", "Usaha Mikro diklaim memiliki izin BPOM Pusat.", "Blok III: Karakteristik", "Rincian 305", [], suffix)
            
        mask_ganda = nama_val.str.contains(' dan ', case=False, na=False) & nama_val.str.contains('jual|buka|warung|jasa|sewa', case=False, na=False)
        append_expert(mask_ganda, "Usaha Ganda", lambda df: "Nama usaha terindikasi menggabungkan lebih dari 1 aktivitas.", "Blok III: Karakteristik", "Rincian 301", [], suffix)

    if 'ans_sewa_kontrak' in df_sub.columns:
        sewa_k = pd.to_numeric(df_sub['ans_sewa_kontrak'], errors='coerce').fillna(0)
        append_expert(sewa_k == 80000000, "Trik Batas Sewa", "Nilai sewa rumah diisi pas 80.000.000 (batas maksimal aplikasi).", "Sosek/Keluarga", "Sewa Rumah", [])
        
    if 'ans_sewa_sendiri' in df_sub.columns:
        sewa_s = pd.to_numeric(df_sub['ans_sewa_sendiri'], errors='coerce').fillna(0)
        append_expert(sewa_s == 80000000, "Trik Batas Sewa", "Perkiraan sewa sendiri diisi pas 80.000.000 (batas maksimal aplikasi).", "Sosek/Keluarga", "Sewa Rumah", [])

    peng_cols_f = [c for c in df_sub.columns if 'pengeluaran_keluarga_sebulan' in c]
    if peng_cols_f and 'ans_jumlah_motor' in df_sub.columns:
        peng = pd.to_numeric(df_sub[peng_cols_f[0]], errors='coerce').fillna(0)
        mtr = pd.to_numeric(df_sub['ans_jumlah_motor'], errors='coerce').fillna(0)
        append_expert((peng < 2000000) & (peng > 0) & (mtr >= 2), "Motor Keluarga Miskin", "Pengeluaran sebulan < 2 Juta tapi punya Motor >= 2.", "Sosek/Keluarga", "Aset Motor", [])

    if 'ans_nik_pengusaha_var' in df_sub.columns:
        mask_nik = df_sub['ans_nik_pengusaha_var'].astype(str).str.match(r'^(?:(.)\1{15}|1234567890123456|0123456789012345)$')
        append_expert(mask_nik, "NIK Fiktif", "NIK pengusaha terdeteksi dummy.", "Blok I: Identitas", "Rincian NIK", [])
        
    if 'dtsen_no_kk' in df_sub.columns:
        mask_kk = df_sub['dtsen_no_kk'].astype(str).str.match(r'^(?:(.)\1{15}|1234567890123456|0123456789012345)$')
        append_expert(mask_kk, "No KK Fiktif", "Nomor KK terdeteksi dummy.", "Blok I: Identitas", "Rincian No KK", [])

    for tc in [c for c in df_sub.columns if c.startswith('ans_tk_dibayar#')]:
        suffix = tc.split('#')[1]
        gaji_c = f"ans_gaji#{suffix}"
        if gaji_c in df_sub.columns:
            tk = pd.to_numeric(df_sub[tc], errors='coerce').fillna(0)
            gaji = pd.to_numeric(df_sub[gaji_c], errors='coerce').fillna(0)
            mask_gaji_murah = (tk > 0) & (gaji > 0) & ((gaji / tk) < 100000)
            append_expert(mask_gaji_murah, "Gaji Ditekan", "Rata-rata gaji per pekerja < Rp 100.000 sebulan.", "Blok V & VI", "Rincian 501 & 602", [], suffix)

    if 'skala_usaha' in df_sub.columns:
        pend_cols = [c for c in df_sub.columns if c.startswith('ans_total_pendapatan_thn#') or c.startswith('ans_total_pendapatan#')]
        if pend_cols:
            for pc in pend_cols:
                pend = pd.to_numeric(df_sub[pc], errors='coerce').fillna(0)
                mask_ub = (df_sub['skala_usaha'].astype(str).str.upper() == 'UB') & (pend > 0) & (pend < 50000000000)
                append_expert(mask_ub, "Batas Omzet UB", "Usaha berskala UB tapi omzet di bawah Rp 50 Miliar.", "Blok VI: Keuangan", "Rincian 601", [])

    # Process all expert rules at once
    if expert_dfs:
        df_err_all = pd.concat(expert_dfs, ignore_index=True)
        
        # Check Catatan
        cat_cols = [c for c in df_sub.columns if c.startswith('ans_catatan')]
        catatan_dict = {}
        if cat_cols:
            df_sub['cat_len'] = 0
            for c in cat_cols:
                df_sub['cat_len'] += df_sub[c].astype(str).apply(lambda x: 0 if x in ['nan', 'None', '<NA>', ''] else len(x))
            
            for code, length in zip(df_sub.get('codeIdentity', []), df_sub['cat_len']):
                catatan_dict[code] = (length > 5)

        fatal_rules = ["Aturan Aset 9999", "Tanah Tanpa Luas", "Trik Batas Sewa", "Gaji Ditekan", "Aset Katering Fiktif"]
        
        mask_fatal = df_err_all['Rule Dilanggar'].isin(fatal_rules)
        for idx in df_err_all[mask_fatal].index:
            code_val = df_err_all.at[idx, 'codeIdentity']
            if not catatan_dict.get(code_val, True):
                df_err_all.at[idx, 'Rule Dilanggar'] = "FATAL: " + df_err_all.at[idx, 'Rule Dilanggar'] + " Tanpa Catatan"
                df_err_all.at[idx, 'Keterangan'] += " (PPL tidak memberikan penjelasan apapun di Blok Catatan)."

        for rule, group in df_err_all.groupby('Rule Dilanggar'):
            is_parah = any(k in rule for k in ["FATAL", "NIK Fiktif", "No KK Fiktif", "Pekerja Tunggal", "Gaji Ditekan", "Trik", "Usaha Ganda"])
            anomalies.append({
                "PPL": ppl_name,
                "Anomali Pattern": f"[Substantif: {rule}] Ditemukan {len(group)} dokumen terindikasi anomali.",
                "Tingkat Anomali": "Parah" if is_parah else "Sedang",
                "Data Detail": group
            })

    if not anomalies:
        anomalies.append({
            "PPL": ppl_name,
            "Anomali Pattern": "Tidak terdeteksi anomali pola statistik yang signifikan.",
            "Tingkat Anomali": "Aman",
            "Data Detail": pd.DataFrame()
        })
    return anomalies


def page_macro():
    st.markdown("<div class='title-gradient'>Macro Pattern Analysis</div>", unsafe_allow_html=True)
    st.markdown("<p style='color:#64748B; margin-bottom: 24px;'>Pemeriksaan pola anomali secara agregat berdasarkan perilaku PPL (Petugas Pencacah Lapangan) dan pola isi data secara keseluruhan.</p>", unsafe_allow_html=True)

    # Clean Streamlit Container for Filters
    with st.container(border=True):
        st.subheader("1. Konfigurasi Analisis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            pilih_ppl_pattern = st.selectbox(
                "Pilih Petugas (PPL):", 
                ["Semua PPL (Global Scan)"] + list_ppl
            )
            
        with col2:
            all_statuses = df_raw['assignmentStatusAlias'].dropna().unique().tolist() if 'assignmentStatusAlias' in df_raw.columns else ["SUBMIT", "DRAFT"]
            # Fix: Use substring search since real status might be "SUBMITTED BY Pencacah"
            default_statuses = [s for s in all_statuses if "DRAFT" in s.upper() or "SUBMIT" in s.upper()]
            if not default_statuses: default_statuses = all_statuses
            
            selected_statuses = st.multiselect(
                "Pilih Status Assignment:", 
                options=all_statuses, 
                default=default_statuses
            )
            
        # Calculate how many assignments are queued
        df_filtered = df_raw.copy()
        if 'assignmentStatusAlias' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['assignmentStatusAlias'].isin(selected_statuses)]
        
        if 'assigned_PPL' not in df_filtered.columns and 'currentUserFullname' in df_filtered.columns:
            # Fallback jika data belum sempat tergabung sempurna
            df_filtered['assigned_PPL'] = df_filtered['currentUserFullname']
            
        if pilih_ppl_pattern != "Semua PPL (Global Scan)" and 'assigned_PPL' in df_filtered.columns:
            df_filtered = df_filtered[df_filtered['assigned_PPL'] == pilih_ppl_pattern]
            
        st.info(f"📌 Terdapat **{len(df_filtered)} Assignment** yang siap diperiksa untuk pola anomali.")
        
        analyze_btn = st.button("Jalankan Analisis Pola", type="primary")
        
    if analyze_btn:
        with st.spinner("Statistik sedang membedah ribuan baris data..."):
            import time; time.sleep(2)  # Memberikan jeda agar loading terlihat natural
            
            st.subheader("📊 Hasil Temuan Pola Anomali")
            
            results = []
            

            # Execute Analysis
            if pilih_ppl_pattern == "Semua PPL (Global Scan)":
                target_ppls = df_filtered['assigned_PPL'].dropna().unique().tolist()
                for ppl in target_ppls:
                    group = df_filtered[df_filtered['assigned_PPL'] == ppl]
                    results.extend(analyze_ppl(group, ppl))
            else:
                results.extend(analyze_ppl(df_filtered, pilih_ppl_pattern))
                
            # Filter results for Global Scan
            if pilih_ppl_pattern == "Semua PPL (Global Scan)":
                results = [r for r in results if r['Tingkat Anomali'] in ["Parah", "Sedang"]]
                if len(results) == 0:
                    st.info("✅ Global Scan Selesai. Semua PPL yang telah mengumpulkan data terdeteksi Aman atau masih berstatus OPEN.")
            
            # Render UI with Expanders
            if len(results) > 0:
                st.markdown("### Daftar Temuan")
                for res in results:
                    color = "#EF4444" if res['Tingkat Anomali'] == "Parah" else "#F59E0B" if res['Tingkat Anomali'] == "Sedang" else "#10B981"
                    bg_color = "#FEF2F2" if res['Tingkat Anomali'] == "Parah" else "#FFFBEB" if res['Tingkat Anomali'] == "Sedang" else "#F0FDF4"
                    
                    st.markdown(f"""
                    <div style="background-color: {bg_color}; border-left: 4px solid {color}; padding: 12px 16px; margin-bottom: 8px; border-radius: 4px;">
                        <strong style="font-size: 1.1em; color: #1E293B;">{res['PPL']}</strong> &nbsp;
                        <span style="background-color: {color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold;">{res['Tingkat Anomali']}</span><br>
                        <span style="color: #475569;">{res['Anomali Pattern']}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    df_detail = res.get('Data Detail')
                    if df_detail is not None and not df_detail.empty:
                        with st.expander(f"🔍 Lihat Data Detail ({len(df_detail)} Baris)"):
                            st.dataframe(df_detail, use_container_width=True, hide_index=True)


def page_deepdive():
    st.markdown("<div class='title-gradient'>Deep Dive Inspection</div>", unsafe_allow_html=True)
    st.markdown("<p style='color:#64748B; margin-bottom: 20px;'>Evaluasi mendalam per assignment dan tanya jawab ke Pedoman SE2026 (RAG).</p>", unsafe_allow_html=True)

    st.markdown("<div class='modern-card'>", unsafe_allow_html=True)
    st.markdown("<h3>1. Pilih Assignment</h3>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 2])
    with col1:
        pilih_ppl = st.selectbox("Filter PPL", list_ppl, key="dd_ppl")
    
    with col2:
        if 'assigned_PPL' in df_raw.columns and 'Human_ID_With_Status' in df_raw.columns:
            assignments = df_raw[df_raw['assigned_PPL'] == pilih_ppl]['Human_ID_With_Status'].dropna().unique().tolist()
        elif 'currentUserFullname' in df_raw.columns and 'Human_ID_With_Status' in df_raw.columns:
            assignments = df_raw[df_raw['currentUserFullname'] == pilih_ppl]['Human_ID_With_Status'].dropna().unique().tolist()
        else:
            assignments = ["UMKM - Budi (SUBMIT)", "UMKM - Siti (DRAFT)"]
        
        pilih_assignment = st.selectbox("Pilih Responden (ID / Nama)", assignments, key="dd_assign")
        
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='modern-card'>", unsafe_allow_html=True)
    st.markdown("<h3>2. Temuan AI pada Rincian Data</h3>", unsafe_allow_html=True)
    
    # 1. Fetch real data for selected assignment
    code_id = str(pilih_assignment).split(" | ")[0].strip()
    df_single = df_raw[df_raw['codeIdentity'].astype(str) == code_id].copy() if 'codeIdentity' in df_raw.columns else pd.DataFrame()
    
    # 2. Run analyze_ppl for anomalies
    anomalies = []
    if not df_single.empty:
        anomalies = analyze_ppl(df_single, pilih_ppl)
        
    total_err = sum([len(a.get('Data Detail', [])) for a in anomalies])
    
    # System Summary
    if total_err > 0:
        summary_text = f"<span style='color:#DC2626;'>Terdapat <b>{total_err} Anomali</b> pada kuesioner ini berdasarkan pemeriksaan Rule Engine. Silakan periksa blok terkait di bawah.</span>"
        border_color = "#EF4444"
        bg_color = "#FEF2F2"
    else:
        summary_text = "<span style='color:#10B981;'><b>Aman!</b> Tidak ditemukan anomali Mayor/Minor pada kuesioner ini.</span>"
        border_color = "#10B981"
        bg_color = "#F0FDF4"
        
    st.markdown(f"""
    <div style='background:{bg_color}; border-left:4px solid {border_color}; padding:16px; border-radius:4px; margin-bottom:20px;'>
        <strong style='color:#1E293B;'>Ringkasan Evaluasi Sistem (Macro):</strong><br>
        {summary_text}
    </div>
    """, unsafe_allow_html=True)
    
    if kamus_blocks and not df_single.empty:
        subtabs = st.tabs(list(kamus_blocks.keys()))
        for i, (block_name, variables) in enumerate(kamus_blocks.items()):
            with subtabs[i]:
                st.markdown(f"<br>", unsafe_allow_html=True)
                
                # Check for anomalies in this block
                block_anomalies = []
                for an in anomalies:
                    df_det = an.get('Data Detail')
                    if df_det is not None and not df_det.empty:
                        rule_blok = str(df_det['Blok'].iloc[0]) if 'Blok' in df_det.columns else "General"
                        block_core = block_name.replace("SE2026 - L ", "").replace("SE2026 - P ", "").strip()
                        
                        # Match logic
                        if block_core.lower() in rule_blok.lower() or rule_blok.lower() in block_core.lower() or "Sistem CAPI" in rule_blok:
                            catatan_list = df_det['Keterangan'].tolist() if 'Keterangan' in df_det.columns else []
                            if catatan_list:
                                cat_str = "<br>".join(f"&bull; {c}" for c in catatan_list)
                            else:
                                cat_str = "<i>Terdeteksi inkonsistensi data.</i>"
                                
                            catatan = f"<b>{an['Anomali Pattern']}</b><br>{cat_str}"
                            # Prevent duplicates for the same rule
                            if catatan not in block_anomalies:
                                block_anomalies.append(catatan)
                                
                if block_anomalies:
                    st.markdown(f"""
<div style='background:#FEE2E2; border-left:4px solid #DC2626; padding:16px; border-radius:4px; margin-bottom:20px;'>
    <strong style='color:#991B1B;'>⚠️ Anomali Terdeteksi di Blok Ini:</strong><br>
    <ul style='color:#7F1D1D; margin-top:8px; margin-bottom:0;'>
        {''.join([f"<li>{a}</li><br>" for a in block_anomalies])}
    </ul>
</div>
""", unsafe_allow_html=True)
                
                # Render variables
                for v in variables:
                    var_name = v['var']
                    # Prefer Kamus_Bridging label (from real template.json) over Kamus_Variabel_Final.md
                    bridge_def = var_options.get(var_name, {})
                    bridge_q = bridge_def.get('question', '').strip()
                    question = bridge_q if bridge_q and not any(c in bridge_q for c in ['<', '{', '#']) else v['question']
                    
                    possible_vars = [var_name, f"ans_{var_name}", f"pre_{var_name}"]
                    matching_cols = [c for c in df_single.columns if (c.split('#')[0] if '#' in c else c) in possible_vars]
                    if not matching_cols: continue
                        
                    # Group by suffix for prelist & ans comparison
                    suffixes = set()
                    for c in matching_cols:
                        if '#' in c:
                            suffixes.add(c.split('#')[1])
                        else:
                            suffixes.add("")
                            
                    for suffix in sorted(list(suffixes)):
                        suffix_str = f"#{suffix}" if suffix else ""
                        ans_col = f"ans_{var_name}{suffix_str}"
                        pre_col = f"pre_{var_name}{suffix_str}"
                        
                        has_ans = ans_col in df_single.columns
                        has_pre = pre_col in df_single.columns
                        
                        ans_val = df_single.iloc[0][ans_col] if has_ans else None
                        pre_val = df_single.iloc[0][pre_col] if has_pre else None
                        
                        ans_str = "Tidak Diisi" if pd.isna(ans_val) or str(ans_val).strip() == "" else str(ans_val)
                        pre_str = "Tidak Diisi" if pd.isna(pre_val) or str(pre_val).strip() == "" else str(pre_val)
                        
                        title_suffix = f" <span style='color:#3B82F6; font-size:0.85rem;'>(Baris {suffix})</span>" if suffix else ""
                        
                        # Generate UI for Prelist and Jawaban PPL
                        
                        # Use _label enriched columns if available
                        ans_label_col = f"{ans_col}_label"
                        pre_label_col = f"{pre_col}_label"
                        
                        if has_ans and ans_label_col in df_single.columns and pd.notna(df_single.iloc[0][ans_label_col]) and str(df_single.iloc[0][ans_label_col]).strip():
                            ans_str = str(df_single.iloc[0][ans_label_col])
                        
                        if has_pre and pre_label_col in df_single.columns and pd.notna(df_single.iloc[0][pre_label_col]) and str(df_single.iloc[0][pre_label_col]).strip():
                            pre_str = str(df_single.iloc[0][pre_label_col])
                        
                        def render_field(val_str, is_prelist=False):
                            bg_color = "#F8FAFC" if is_prelist else "#F0FDF4"
                            border_color = "#94A3B8" if is_prelist else "#10B981"
                            title = "📋 Data Prelist" if is_prelist else "📝 Jawaban PPL"
                            title_color = "#64748B" if is_prelist else "#059669"
                            val_color = "#334155" if is_prelist else "#064E3B"
                            
                            html = f"""
<div style="flex:1; min-width:200px; background:{bg_color}; padding:12px 16px; border-radius:6px; border-left:3px solid {border_color};">
    <div style="font-size:0.75rem; color:{title_color}; font-weight:800; letter-spacing:0.5px; margin-bottom:10px; text-transform:uppercase;">{title}</div>
"""
                            
                            if val_str == "Tidak Diisi" or val_str == "Tidak ada kolom":
                                return html + f"<div style='color:#94A3B8; font-style:italic; font-size:0.9rem;'>{val_str}</div></div>"
                                
                            # Cukup render text val_str karena sudah memuat '_label' (pilihan yg sudah diubah ke readable format)
                            html += f"""
<div style="padding:8px 12px; border:1px solid #CBD5E1; border-radius:4px; background:white; color:{val_color}; font-weight:600; font-size:0.95rem;">
    {str(val_str).replace('"', '&quot;')}
</div>
"""
                                
                            html += "</div>"
                            return html
                            
                        pre_html = render_field(pre_str if has_pre else "Tidak Diisi", is_prelist=True)
                        ans_html = render_field(ans_str if has_ans else "Tidak ada kolom", is_prelist=False)

                        st.markdown(f"""
<div style="background:white; border:1px solid #E2E8F0; padding:20px; border-radius:8px; margin-bottom:16px; box-shadow:0 2px 4px rgba(0,0,0,0.04);">
    <div style="font-weight:700; color:#0F172A; font-size:1.1rem; margin-bottom:6px; line-height:1.4;">
        {question}{title_suffix}
    </div>
    <div style="font-size:0.8rem; color:#64748B; margin-bottom:16px; font-family:monospace; background:#F1F5F9; display:inline-block; padding:2px 8px; border-radius:4px;">
        {var_name}{suffix_str}
    </div>
    
    <div style="display:flex; gap:16px; flex-wrap:wrap;">
        {pre_html}
        {ans_html}
    </div>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("Pilih assignment atau muat kamus variabel terlebih dahulu.")
    st.markdown("</div>", unsafe_allow_html=True)
        
    st.markdown("<div class='modern-card'>", unsafe_allow_html=True)
    st.markdown("<h3>💬 RAG Assistant (Bedah Pedoman)</h3>", unsafe_allow_html=True)
    
    user_prompt = st.text_input("Tanya AI tentang pedoman SE2026 atau instruksikan untuk membedah data di atas:", 
                               placeholder="Contoh: Tolong carikan di buku pedoman, apa saja syarat usaha yang masuk kategori kasus batas?")
    
    if st.button("Kirim ke AI", use_container_width=False):
        if user_prompt:
            # Fallback to defaults if secrets are missing somehow
            try:
                api_key = st.secrets["dashscope"]["api_key"]
                base_url = st.secrets["dashscope"]["base_url"]
            except:
                api_key = "sk-ws-H.IXIMLD.p98m.MEYCIQDxCzptqM7giW_iDjD-PN5sU1eiQ9wJticzQrGRFbNa7wIhAMMhFLrIHo3Dxg83qdPtvqx6TfTIK8vnMWt0xvhjW2Iy"
                base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
                
            model_name = st.session_state.get('ai_model', "qwen3.7-max-2026-05-20")
            
            if not api_key:
                st.error("⚠️ Mohon isi API Key di menu pengaturan (Sidebar).")
            else:
                with st.spinner(f"AI ({model_name}) sedang membaca PDF Pedoman dan menganalisis..."):
                    try:
                        from langchain_openai import ChatOpenAI
                        from langchain_community.vectorstores import FAISS
                        from langchain_community.embeddings import HuggingFaceEmbeddings
                        from langchain.chains import create_retrieval_chain
                        from langchain.chains.combine_documents import create_stuff_documents_chain
                        from langchain_core.prompts import ChatPromptTemplate
                        
                        os.environ["OPENAI_API_KEY"] = api_key
                        
                        llm = ChatOpenAI(
                            base_url=base_url,
                            api_key=api_key,
                            model=model_name,
                            temperature=0.2
                        )
                        
                        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
                        vectorstore = FAISS.load_local('faiss_index', embeddings, allow_dangerous_deserialization=True)
                        retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
                        
                        system_prompt = (
                            "Anda adalah asisten ahli metodologi Sensus Ekonomi 2026 (SE2026) BPS. "
                            "Gunakan potongan dokumen pedoman berikut untuk menjawab pertanyaan pengguna.\n\n"
                            "Context:\n{context}\n\n"
                        )
                        prompt = ChatPromptTemplate.from_messages([
                            ("system", system_prompt),
                            ("human", "{input}"),
                        ])
                        
                        question_answer_chain = create_stuff_documents_chain(llm, prompt)
                        chain = create_retrieval_chain(retriever, question_answer_chain)
                        
                        response = chain.invoke({"input": user_prompt})
                        answer_text = response['answer'].replace(chr(10), '<br>')
                        
                        st.markdown(f"""
                        <div class='ai-output'>
                            <strong>🤖 RAG Response ({model_name}):</strong><br><br>
                            {answer_text}
                        </div>
                        """, unsafe_allow_html=True)
                        
                    except Exception as e:
                        st.error(f"Gagal menghubungkan ke Model AI / FAISS: {e}")
        else:
            st.warning("Masukkan pertanyaan terlebih dahulu.")
    st.markdown("</div>", unsafe_allow_html=True)

def page_expert():
    st.markdown("<div class='title-gradient'>Expert Analytics</div>", unsafe_allow_html=True)
    st.markdown("<p style='color:#64748B; margin-bottom: 20px;'>Advanced cross-variable consistency and regional hotspot mapping.</p>", unsafe_allow_html=True)

    # --- SE2026 EXPERT RULE ENGINE ---
    
    st.info("💡 Seluruh 20+ Rule Substantif & Expert Analytics telah dipindahkan ke tab **Macro Pattern Analysis**. Silakan periksa tab tersebut untuk melihat profil pelanggaran yang dikelompokkan secara spesifik per PPL.")

# --- NAVIGATION SETUP ---# --- NAVIGATION SETUP ---
pg = st.navigation([
    st.Page(page_macro, title="Macro Pattern Analysis", icon="📊"),
    st.Page(page_deepdive, title="Deep Dive Inspection", icon="🔍"),
    st.Page(page_expert, title="Expert Analytics", icon="🧠"),
])

pg.run()
