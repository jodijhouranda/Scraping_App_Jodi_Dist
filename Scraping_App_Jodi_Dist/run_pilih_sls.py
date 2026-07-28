"""
run_pilih_sls.py — Pilih SLS dari terminal, lalu jalankan scraping
Jalankan dengan: python run_pilih_sls.py
"""
import os
import sys
import json
import asyncio
import pandas as pd
from datetime import datetime

DIR_PATH = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DEFAULT = os.path.join(DIR_PATH, "Template Jodi.xlsx")
REGION_FILE = os.path.join(DIR_PATH, "region_mapping.json")

# ─── Tambahkan dir ke path agar bisa import main.py ───
sys.path.insert(0, DIR_PATH)
os.chdir(DIR_PATH)

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def load_template(path):
    df = pd.read_excel(path, dtype=str)
    df.columns = df.columns.str.strip()
    if 'idsls' not in df.columns:
        print(f"[ERROR] Kolom 'idsls' tidak ditemukan di {path}")
        sys.exit(1)
    df['idsls'] = df['idsls'].str.replace(r'\.0$', '', regex=True).str.strip()
    return df

def load_region_names():
    """Buat dict kode_kab → nama dari region_mapping.json"""
    kab_names = {}
    kec_names = {}
    if os.path.exists(REGION_FILE):
        with open(REGION_FILE, 'r', encoding='utf-8') as f:
            region = json.load(f)
        for kab_code, kab_info in region.items():
            kab_names[kab_code] = kab_info.get('name', kab_code)
            for kec_code, kec_info in kab_info.get('kecamatan', {}).items():
                kec_names[kec_code[:7]] = kec_info.get('name', kec_code)
    return kab_names, kec_names

def tampilkan_daftar(df, kab_names, kec_names):
    """Tampilkan daftar SLS terkelompok per Kabupaten/Kecamatan dengan nomor urut"""
    
    # Buat kolom bantu
    df = df.copy()
    df['kode_kab'] = df['idsls'].str[:4]
    df['kode_kec'] = df['idsls'].str[:7]
    df['nama_kab'] = df['kode_kab'].map(kab_names).fillna(df['kode_kab'])
    df['nama_kec'] = df['kode_kec'].map(kec_names).fillna(df['kode_kec'])
    df['no'] = range(1, len(df)+1)
    
    print()
    print("=" * 70)
    print("  DAFTAR SLS DARI TEMPLATE JODI")
    print("=" * 70)
    
    current_kab = None
    current_kec = None
    
    for _, row in df.iterrows():
        kab = f"[{row['kode_kab']}] {row['nama_kab']}"
        kec = f"  [{row['kode_kec']}] {row['nama_kec']}"
        
        if kab != current_kab:
            print(f"\n  📍 {kab}")
            current_kab = kab
            current_kec = None
        
        if kec != current_kec:
            print(f"    🏘️  {kec}")
            current_kec = kec
        
        # Nama SLS
        nama_sls = ''
        for col in ['nmsls', 'namasls', 'nama_sls']:
            if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
                nama_sls = str(row[col]).strip()
                break
        
        # PPL
        ppl = str(row.get('PPL', '')).strip() if 'PPL' in row.index else ''
        
        print(f"      {row['no']:>4}. {row['idsls']}  {nama_sls:<30} {ppl}")
    
    print()
    print(f"  Total: {len(df)} SLS")
    print("=" * 70)
    
    return df

def parse_pilihan(teks, total):
    """
    Parse input user:
    - 'semua' → semua nomor
    - '1-10'  → nomor 1 sampai 10
    - '1,3,5' → nomor 1, 3, dan 5
    - '1-5,8,10-12' → kombinasi
    """
    teks = teks.strip().lower()
    if teks in ('semua', 'all', 's', 'a'):
        return list(range(1, total + 1))
    
    nomor_set = set()
    for part in teks.split(','):
        part = part.strip()
        if '-' in part:
            try:
                a, b = part.split('-', 1)
                a, b = int(a.strip()), int(b.strip())
                nomor_set.update(range(min(a,b), max(a,b)+1))
            except:
                print(f"  [!] Format tidak valid: '{part}', dilewati.")
        else:
            try:
                nomor_set.add(int(part))
            except:
                print(f"  [!] Bukan angka: '{part}', dilewati.")
    
    valid = sorted(n for n in nomor_set if 1 <= n <= total)
    return valid


async def jalankan_scraping(df_selected, scrape_detail, max_workers):
    """Import dan jalankan main() dengan template sementara"""
    from main import init_browser_jodi, scrape_usaha_datatable_jodi, scrape_detail_data_jodi
    
    # Simpan template sementara (hanya kolom asli, tanpa kolom bantu)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = os.path.join(DIR_PATH, f"_temp_pilihan_{ts}.xlsx")
    
    # Simpan hanya kolom yang ada di template asli (buang kode_kab, kode_kec, dll)
    cols_to_drop = [c for c in ['kode_kab', 'kode_kec', 'nama_kab', 'nama_kec', 'no'] if c in df_selected.columns]
    df_save = df_selected.drop(columns=cols_to_drop)
    df_save.to_excel(temp_path, index=False)
    print(f"\n  [INFO] Template sementara disimpan: {os.path.basename(temp_path)}")
    
    try:
        print("  [INFO] Menginisialisasi browser...")
        p, browser, page, xsrf_token = await init_browser_jodi()
        
        if not page:
            print("  [ERROR] Gagal inisialisasi browser.")
            return
        
        print("  [INFO] Memulai scraping datatable usaha...")
        usaha_csv = await scrape_usaha_datatable_jodi(
            page, xsrf_token, temp_path,
            custom_name="jodi_data_usaha", max_workers=max_workers
        )
        
        detail_csv, error_csv = None, None
        if usaha_csv and scrape_detail:
            print("  [INFO] Memulai scraping detail data...")
            detail_csv, error_csv = await scrape_detail_data_jodi(
                page, xsrf_token, usaha_csv,
                custom_name="jodi_detail_assignment", max_workers=max_workers
            )
        
        await browser.close()
        await p.stop()
        
        # ── Assembly output (sama persis dengan main.py) ──
        if usaha_csv:
            _assembly_output(usaha_csv, detail_csv, error_csv, temp_path, scrape_detail)
        else:
            print("\n  [ERROR] Scraping datatable gagal / tidak ada data.")
    
    finally:
        # Hapus template sementara
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass


def _assembly_output(usaha_csv, detail_csv, error_csv, temp_path, scrape_detail):
    """Assembly file output akhir — dijadikan 1 file Excel dengan beberapa sheet"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        # Template Wilayah (Siapkan dulu untuk mapping nama RT & PPL)
        df_template = pd.read_excel(temp_path)
        
        sls_name_col = next((c for c in ['nmsls', 'namasls', 'nama_sls'] if c in df_template.columns), None)
        ppl_name_col = next((c for c in ['PPL', 'ppl', 'Nama PPL'] if c in df_template.columns), None)
        
        nama_sls_str = "Multi_SLS"
        nama_ppl_str = "Multi_PPL"
        
        if sls_name_col and not df_template[sls_name_col].empty:
            sls_unique = df_template[sls_name_col].dropna().unique()
            if len(sls_unique) == 1:
                nama_sls_str = str(sls_unique[0]).replace('/', '_').replace('\\', '_').replace(':', '_')[:30]
                
        if ppl_name_col and not df_template[ppl_name_col].empty:
            ppl_unique = df_template[ppl_name_col].dropna().unique()
            if len(ppl_unique) == 1:
                nama_ppl_str = str(ppl_unique[0]).replace('/', '_').replace('\\', '_').replace(':', '_')[:30]

        prefix = f"Jodi_{nama_sls_str}_{nama_ppl_str}_{timestamp}"
        excel_path = os.path.join(DIR_PATH, f"{prefix}_All_in_One.xlsx")
        print(f"\n  [INFO] Menyusun file output tunggal Excel: {prefix}_All_in_One.xlsx")
        
        writer = pd.ExcelWriter(excel_path, engine='openpyxl')
        cols_to_drop = [c for c in df_template.columns if str(c).strip().lower() in ['submit', 'draf', 'total']]
        df_template = df_template.drop(columns=cols_to_drop, errors='ignore')
        
        if 'idsls' in df_template.columns:
            idsls_str = df_template['idsls'].astype(str).str.replace(r'\.0$', '', regex=True)
            if 'kdsubsls' in df_template.columns:
                kdsubsls_str = pd.to_numeric(df_template['kdsubsls'], errors='coerce').fillna(0).astype(int).astype(str).str.zfill(2)
                df_template['id_match'] = idsls_str + kdsubsls_str
            else:
                df_template['id_match'] = idsls_str + "00"
        else:
            df_template['id_match'] = None
    
        # Cari kolom nama RT dan PPL untuk digabungkan
        sls_name_col = next((c for c in ['nmsls', 'namasls', 'nama_sls'] if c in df_template.columns), None)
        ppl_name_col = next((c for c in ['PPL', 'ppl', 'Nama PPL'] if c in df_template.columns), None)
        map_cols = ['id_match']
        if sls_name_col: map_cols.append(sls_name_col)
        if ppl_name_col: map_cols.append(ppl_name_col)
        
        df_usaha = pd.read_csv(usaha_csv, low_memory=False)
        
        # Pivot status per SLS
        if 'codeIdentity' in df_usaha.columns:
            df_usaha['ID_SUB_SLS_REAL'] = df_usaha['codeIdentity'].astype(str).str.extract(r'^(\d{16})')[0]
            df_usaha['ID_SUB_SLS_REAL'] = df_usaha['ID_SUB_SLS_REAL'].fillna(
                df_usaha.get('ID_SLS', df_usaha['codeIdentity']).astype(str) + "00"
            )
            
            # Merge nama RT dan PPL ke Data Usaha
            if len(map_cols) > 1 and df_template['id_match'].notna().any():
                df_usaha = pd.merge(df_usaha, df_template[map_cols].drop_duplicates('id_match'), 
                                    left_on='ID_SUB_SLS_REAL', right_on='id_match', how='left')
                if 'id_match' in df_usaha.columns:
                    df_usaha = df_usaha.drop(columns=['id_match'])
                    
                # Pindahkan kolom nama SLS & PPL ke depan (setelah codeIdentity)
                cols = df_usaha.columns.tolist()
                insert_idx = cols.index('codeIdentity') + 1 if 'codeIdentity' in cols else 0
                for c in reversed([sls_name_col, ppl_name_col]):
                    if c and c in cols:
                        cols.insert(insert_idx, cols.pop(cols.index(c)))
                df_usaha = df_usaha[cols]
                
        if 'ID_SUB_SLS_REAL' in df_usaha.columns and 'assignmentStatusAlias' in df_usaha.columns:
            pivot_df = pd.crosstab(df_usaha['ID_SUB_SLS_REAL'], df_usaha['assignmentStatusAlias']).reset_index()
        else:
            pivot_df = pd.DataFrame()
        
        if 'idsls' in df_template.columns and not pivot_df.empty:
            df_merged = pd.merge(df_template, pivot_df, left_on='id_match', right_on='ID_SUB_SLS_REAL', how='left')
            status_cols = pivot_df.columns.drop('ID_SUB_SLS_REAL')
            for col in status_cols:
                if col in df_merged.columns:
                    df_merged[col] = df_merged[col].fillna(0).astype(int)
            
            val_open = df_merged.get('OPEN', 0)
            val_submit = df_merged.get('SUBMITTED BY Pencacah', 0)
            val_draft = df_merged.get('DRAFT', 0)
            total_all = df_merged[status_cols].sum(axis=1)
            
            df_merged['Open'] = val_open
            df_merged['Submit'] = val_submit
            df_merged['Draft 1'] = total_all - val_open - val_submit
            df_merged['Total'] = df_merged['Submit'] + df_merged['Draft 1']
            df_merged['Draft 2'] = val_draft
            
            template_base_cols = [c for c in df_template.columns if c != 'id_match']
            other_statuses = [c for c in status_cols if c not in ['OPEN', 'SUBMITTED BY Pencacah', 'DRAFT']]
            final_cols = template_base_cols + ['Open', 'Submit', 'Draft 1', 'Total', 'Draft 2'] + other_statuses
            df_merged[[c for c in final_cols if c in df_merged.columns]].to_excel(writer, sheet_name='Template_Wilayah', index=False)
            
            # Kinerja PPL
            if 'PPL' in df_merged.columns:
                valid_cols = [c for c in ['Open', 'Submit', 'Draft 1', 'Draft 2'] + list(other_statuses) if c in df_merged.columns]
                group_cols = ['Pj-Kuda', 'PPL'] if 'Pj-Kuda' in df_merged.columns else ['PPL']
                df_ppl = df_merged.groupby(group_cols)[valid_cols].sum().reset_index()
                
                base_cols = [c for c in ['Open', 'Submit', 'Draft 1'] if c in df_ppl.columns]
                df_ppl['Beban Tugas (Total)'] = df_ppl[base_cols].sum(axis=1)
                df_ppl['Selesai Lapangan'] = df_ppl['Beban Tugas (Total)'] - df_ppl.get('Open', 0)
                df_ppl['% Selesai Lapangan'] = (
                    df_ppl['Selesai Lapangan'] / df_ppl['Beban Tugas (Total)'].replace(0, 1) * 100
                ).round(2)
                
                start_date = datetime(datetime.now().year, 6, 15)
                hari = max(1, (datetime.now() - start_date).days)
                df_ppl['Kecepatan (Dokumen/Hari)'] = (df_ppl['Selesai Lapangan'] / hari).round(2)
                df_ppl.sort_values('% Selesai Lapangan').to_excel(writer, sheet_name='Kinerja_PPL', index=False)
        else:
            df_template.to_excel(writer, sheet_name='Template_Wilayah', index=False)
            
        df_usaha.to_excel(writer, sheet_name='Data_Usaha', index=False)
        
        # Detail data
        if detail_csv and os.path.exists(detail_csv):
            parquet_path = detail_csv.replace('.csv', '.parquet')
            if os.path.exists(parquet_path):
                df_detail = pd.read_parquet(parquet_path)
            else:
                df_detail = pd.read_csv(detail_csv, low_memory=False)
                
            detail_code_col = '_meta_code_identity' if '_meta_code_identity' in df_detail.columns else 'codeIdentity'
            if detail_code_col in df_detail.columns:
                # Ambil ID SLS asli
                df_detail['ID_SUB_SLS_REAL'] = df_detail[detail_code_col].astype(str).str.extract(r'^(\d{16})')[0]
                
                # Merge nama RT dan PPL ke Detail Data
                if len(map_cols) > 1 and df_template['id_match'].notna().any():
                    df_detail = pd.merge(df_detail, df_template[map_cols].drop_duplicates('id_match'), 
                                         left_on='ID_SUB_SLS_REAL', right_on='id_match', how='left')
                    if 'id_match' in df_detail.columns:
                        df_detail = df_detail.drop(columns=['id_match'])
                        
                    # Pindahkan kolom nama SLS & PPL ke urutan awal
                    cols = df_detail.columns.tolist()
                    insert_idx = cols.index(detail_code_col) + 1 if detail_code_col in cols else 0
                    for c in reversed([sls_name_col, ppl_name_col]):
                        if c and c in cols:
                            cols.insert(insert_idx, cols.pop(cols.index(c)))
                    df_detail = df_detail[cols]
                    
                df_detail = df_detail.drop(columns=['ID_SUB_SLS_REAL'], errors='ignore')
                
            # --- Sheet Tambahan: Gabungan Tdk Ditemukan (Keluarga & Usaha) ---
            df_tdk_kel = pd.DataFrame()
            if 'ans_ada_keluarga' in df_detail.columns:
                df_tdk_kel = df_detail[df_detail['ans_ada_keluarga'].astype(str) == '0. Tidak Ditemukan (STOP)'].copy()
                if not df_tdk_kel.empty:
                    df_tdk_kel['Jenis Prelist'] = 'Keluarga'
                    
            df_tdk_ush = pd.DataFrame()
            if 'ans_ada_bang_usaha' in df_detail.columns:
                mask = df_detail['ans_ada_bang_usaha'].notna() & (df_detail['ans_ada_bang_usaha'].astype(str).str.strip() != '') & (df_detail['ans_ada_bang_usaha'].astype(str).str.lower() != 'nan')
                df_tdk_ush = df_detail[mask].copy()
                if not df_tdk_ush.empty:
                    df_tdk_ush['Jenis Prelist'] = 'Usaha'
                    
            df_gabung = pd.concat([df_tdk_kel, df_tdk_ush], ignore_index=True)
            
            if not df_gabung.empty:
                # Hanya ambil identitas dasar + Jenis Prelist + ans_nama_principal + catatan
                cols_to_keep = []
                for id_col in [detail_code_col, sls_name_col, ppl_name_col]:
                    if id_col and id_col in df_gabung.columns:
                        cols_to_keep.append(id_col)
                        
                cols_to_keep.append('Jenis Prelist')
                
                # Tambahkan kolom alasan (sumber filter)
                for filter_col in ['ans_ada_keluarga', 'ans_ada_bang_usaha']:
                    if filter_col in df_gabung.columns:
                        cols_to_keep.append(filter_col)
                
                # Pastikan nama principal terambil
                if 'ans_nama_principal' in df_gabung.columns:
                    cols_to_keep.append('ans_nama_principal')
                else:
                    alt_nama = next((c for c in df_gabung.columns if 'nama_principal' in str(c).lower() or 'nama_kk' in str(c).lower() or 'nama_krt' in str(c).lower()), None)
                    if alt_nama:
                        cols_to_keep.append(alt_nama)
                        
                catatan_cols = [c for c in df_gabung.columns if 'catatan' in str(c).lower() and not str(c).startswith('pre_')]
                cols_to_keep.extend([c for c in catatan_cols if c not in cols_to_keep])
                
                # Buang duplikat jika ada (berjaga-jaga jika 1 assignment masuk ke 2 kriteria)
                df_gabung = df_gabung.drop_duplicates(subset=[detail_code_col] if detail_code_col in df_gabung.columns else df_gabung.columns)
                
                df_gabung[cols_to_keep].to_excel(writer, sheet_name='Tdk_Ditemukan_Gabungan', index=False)

            # --- Bersihkan kolom pre_* ---
            cols_to_keep = [c for c in df_detail.columns if not (str(c).startswith('pre_') or str(c).endswith('_question') or str(c).endswith('_block') or str(c).endswith('_raw'))]
            df_detail = df_detail[cols_to_keep]
                
            df_detail.to_excel(writer, sheet_name='Detail_Data', index=False)
        
        if error_csv and os.path.exists(error_csv):
            df_err = pd.read_csv(error_csv)
            if 'Assignment ID' in df_err.columns and 'Assignment ID' in df_usaha.columns:
                cols_to_add = [c for c in df_usaha.columns if str(c).startswith('data') or c == 'codeIdentity']
                df_err = pd.merge(df_err, df_usaha[['Assignment ID'] + [c for c in cols_to_add if c in df_usaha.columns and c not in df_err.columns]], on='Assignment ID', how='left')
            df_err.to_excel(writer, sheet_name='Error_Log', index=False)
            
    finally:
        # Pastikan writer tertutup (meski jika error)
        try: writer.close()
        except: pass
        
        # Hapus file intermediate
        for f in [usaha_csv, detail_csv, error_csv]:
            try:
                if f and os.path.exists(f): os.remove(f)
            except: pass
            
        print(f"""
  ══════════════════════════════════════════════════════════
  ✅  SELESAI! File tersimpan:
      {prefix}_All_in_One.xlsx
  ══════════════════════════════════════════════════════════""")


def main():
    clear()
    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║    SCRAPING MANAGER SE2026 — JODI BPS       ║")
    print("  ╚══════════════════════════════════════════════╝")
    
    # ── Pilih file template ──
    print(f"\n  Template default: {TEMPLATE_DEFAULT}")
    custom_path = input("  Gunakan template lain? (enter = pakai default): ").strip()
    template_path = custom_path if custom_path and os.path.exists(custom_path) else TEMPLATE_DEFAULT
    
    if not os.path.exists(template_path):
        print(f"\n  [ERROR] File tidak ditemukan: {template_path}")
        sys.exit(1)
    
    print(f"\n  Membaca template: {os.path.basename(template_path)}...")
    df = load_template(template_path)
    kab_names, kec_names = load_region_names()
    
    # ── Tampilkan daftar SLS ──
    df_numbered = tampilkan_daftar(df, kab_names, kec_names)
    total = len(df_numbered)
    
    # ── Input pilihan SLS ──
    print()
    print("  Cara pilih SLS yang akan di-scrape:")
    print("    semua       → scrape semua SLS")
    print("    1-10        → nomor 1 sampai 10")
    print("    1,3,5       → hanya nomor 1, 3, dan 5")
    print("    1-5,8,10-12 → kombinasi range dan individual")
    print()
    
    while True:
        pilihan_str = input("  Pilih SLS [semua / nomor]: ").strip()
        if not pilihan_str:
            continue
        nomor_terpilih = parse_pilihan(pilihan_str, total)
        if nomor_terpilih:
            break
        print("  [!] Tidak ada SLS valid yang dipilih, coba lagi.")
    
    df_selected = df_numbered[df_numbered['no'].isin(nomor_terpilih)].copy()
    
    print(f"\n  ✅ {len(df_selected)} SLS terpilih:")
    for _, row in df_selected.iterrows():
        nama = ''
        for col in ['nmsls', 'namasls', 'nama_sls']:
            if col in row.index and pd.notna(row[col]):
                nama = str(row[col]); break
        print(f"     {row['no']:>4}. {row['idsls']}  {nama}")
    
    # ── Mode scraping ──
    print()
    print("  Mode Scraping:")
    print("    1. Datatable + Detail  (Lengkap — semua variabel kuesioner)")
    print("    2. Datatable Saja      (Cepat — hanya status & identitas usaha)")
    mode_input = input("  Pilih mode [1/2, default=1]: ").strip()
    scrape_detail = (mode_input != '2')
    
    # ── Max workers
    try:
        workers_input = input("  Masukkan batas koneksi paralel (default 25): ").strip()
        max_workers = int(workers_input) if workers_input else 25
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception:
        max_workers = 25
    
    # ── Konfirmasi ──
    mode_label = "Datatable + Detail" if scrape_detail else "Datatable Saja"
    print(f"""
  ══════════════════════════════════════════════════════════
  Siap scraping dengan konfigurasi:
    SLS dipilih  : {len(df_selected)} SLS
    Mode         : {mode_label}
    Paralel      : {max_workers} koneksi
  ══════════════════════════════════════════════════════════""")
    
    konfirmasi = input("  Lanjutkan? [y/n, default=y]: ").strip().lower()
    if konfirmasi == 'n':
        print("  Dibatalkan.")
        sys.exit(0)
    
    # ── Jalankan ──
    asyncio.run(jalankan_scraping(df_selected, scrape_detail, max_workers))


if __name__ == "__main__":
    main()
