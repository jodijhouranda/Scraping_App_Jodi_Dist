import asyncio
import json
import os
import pandas as pd
from datetime import datetime
from tqdm.asyncio import tqdm as async_tqdm
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# Import dari script yang ada
from survey_manager import load_config
from scraping_manager import (
    fetch_datatable, fetch_detail_api, 
    enrich_detail_output, build_gui_mapping, save_gui_mapping_json
)

dir_path = os.path.dirname(os.path.abspath(__file__))
region_file = os.path.join(dir_path, "region_mapping.json")

async def init_browser_jodi():
    p = await async_playwright().start()

    # ── Gunakan Google Chrome asli untuk bypass deteksi bot WAF BPS ──
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    
    stealth_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process",
        "--lang=id-ID,id",
    ]
    
    # Launch dengan Chrome asli, bukan bundled Chromium
    browser = await p.chromium.launch(
        headless=False,
        executable_path=chrome_path if os.path.exists(chrome_path) else None,
        args=stealth_args
    )

    # ── Context dengan user agent Windows Chrome terbaru ──
    context_opts = dict(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
        locale="id-ID",
        timezone_id="Asia/Jakarta",
        java_script_enabled=True,
        accept_downloads=True,
    )

    state_file = os.path.join(os.path.dirname(dir_path), "state.json")
    if os.path.exists(state_file):
        print("Mencoba login otomatis dengan sesi sebelumnya...")
        context = await browser.new_context(storage_state=state_file, **context_opts)
    else:
        context = await browser.new_context(**context_opts)

    page = await context.new_page()
    await Stealth().apply_stealth_async(page)
    print("Membuka halaman utama...")
    try:
        await page.goto("https://fasih-sm.bps.go.id/")
        await page.wait_for_timeout(3000)
    except Exception as e:
        print(f"Gagal memuat halaman: {e}")

    # Cek kondisi halaman: apakah ada halaman BOT/CAPTCHA atau dialihkan ke halaman SSO/Login
    page_content = ""
    try:
        # Tunggu sampai halaman selesai redirect jika ada
        await page.wait_for_load_state('domcontentloaded', timeout=10000)
        page_content = await page.content()
    except Exception as e:
        print(f"  [DEBUG] Tidak bisa membaca konten halaman saat ini (sedang navigasi): {e}")
        
    is_bot_detected = "BOT-" in page_content or "perilaku yang tidak wajar" in page_content or "captcha" in page_content.lower()
    is_login_page = "login" in page.url.lower() or "sso" in page.url.lower()

    if is_bot_detected or is_login_page:
        print("\n" + "="*55)
        print("PAUSED: TINDAKAN MANUAL DIBUTUHKAN")
        
        if is_bot_detected:
            print("[!] Terdeteksi sebagai bot atau sistem BPS meminta verifikasi CAPTCHA.")
            print("1. Silakan selesaikan CAPTCHA di browser secara manual sampai berhasil.")
        else:
            print("[!] Sesi Anda belum ada atau sudah kedaluwarsa.")
            print("1. Silakan login ke akun Anda di browser yang terbuka.")
            
        print("2. Setelah berhasil masuk ke halaman dashboard/awal aplikasi FASIH,")
        print("3. Buka jendela 'Playwright Inspector' (jendela kecil bawaan script) lalu klik tombol 'Resume' (ikon panah biru) untuk melanjutkan otomatisasi.")
        print("="*55 + "\n")

        # Tunggu pengguna menyelesaikan CAPTCHA atau Login
        await page.pause()

        # Simpan state login untuk digunakan nanti (jika perlu)
        await context.storage_state(path=state_file)
        print("Status sesi/login telah disimpan untuk pemakaian berikutnya!")
    else:
        print("Login otomatis sukses, tidak ada hambatan!")

    # ── KRITIS: Navigate ke halaman analitik sebelum API call ──
    # WAF BPS mensyaratkan browser harus mengunjungi halaman /app/analytic/assignment
    # SEBELUM API datatable bisa dipanggil. Homepage saja tidak cukup (WAF return HTML).
    print("Memuat halaman analitik untuk mengaktifkan sesi API...")
    try:
        await page.goto(
            "https://fasih-sm.bps.go.id/app/analytic/assignment",
            wait_until="domcontentloaded",
            timeout=20000
        )
        await page.wait_for_timeout(4000)
        print(f"  Halaman analitik berhasil dimuat: {page.url[:70]}")
    except Exception as e:
        print(f"  Catatan: Gagal navigate ke analytics ({e}), lanjut dengan sesi saat ini.")

    # ── Ekstrak XSRF Token (setelah navigate ke analytics) ──
    xsrf_token = ""
    for c in await context.cookies():
        if c["name"] == "XSRF-TOKEN":
            xsrf_token = c["value"]
            break

    # ── Validasi Token: Jika kosong, sesi mungkin expired tanpa redirect ──
    if not xsrf_token:
        print("\n" + "="*60)
        print("[!] PERINGATAN: XSRF Token tidak ditemukan!")
        print("   Kemungkinan sesi sudah kedaluwarsa meski halaman terbuka.")
        print("   Silakan login ulang di browser, lalu klik Resume di Playwright Inspector.")
        print("="*60 + "\n")
        await page.pause()
        await context.storage_state(path=state_file)
        # Navigate ulang setelah login
        try:
            await page.goto("https://fasih-sm.bps.go.id/app/analytic/assignment",
                           wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(4000)
        except Exception:
            pass
        # Coba ekstrak ulang setelah login + navigate
        for c in await context.cookies():
            if c["name"] == "XSRF-TOKEN":
                xsrf_token = c["value"]
                break
        if not xsrf_token:
            print("[ERROR] XSRF Token masih tidak ditemukan setelah login ulang. Keluar.")
            await browser.close()
            await p.stop()
            return p, browser, page, ""
        print(f"[OK] XSRF Token berhasil didapatkan setelah login ulang.")
    else:
        print(f"[OK] XSRF Token siap ({len(xsrf_token)} karakter). Memulai scraping...")

    return p, browser, page, xsrf_token

async def scrape_usaha_datatable_jodi(page, xsrf_token, template_file, custom_name="jodi_data_usaha", max_workers=50):
    cfg = load_config()
    survey_id = cfg.get("survey_period_id")
    region1Id = cfg.get("region1Id")
    if not survey_id or not region1Id:
        print("Survey ID atau Provinsi belum diatur. Silakan jalankan Setup Survei terlebih dahulu di main.py.")
        return None

    if not os.path.exists(region_file):
        print("region_mapping.json tidak ditemukan! Silakan jalankan Setup Survei di main.py.")
        return None

    if not os.path.exists(template_file):
        print(f"File template {template_file} tidak ditemukan!")
        return None
    
    df_template = pd.read_excel(template_file)
    if 'idsls' not in df_template.columns:
        print("Kolom 'idsls' tidak ditemukan di template!")
        return None
        
    target_sls_codes = set(df_template['idsls'].dropna().astype(str).tolist())
    print(f"Ditemukan {len(target_sls_codes)} target SLS dari template.")

    with open(region_file, "r", encoding="utf-8") as f:
        region_data = json.load(f)
        
    sls_list = []
    for kab_code, kab_info in region_data.items():
        kab_id = kab_info.get("id")
        for kec_code, kec_info in kab_info.get("kecamatan", {}).items():
            kec_id = kec_info.get("id")
            for desa_code, desa_info in kec_info.get("desa", {}).items():
                desa_id = desa_info.get("id")
                for sls_code, sls_info in desa_info.get("sls", {}).items():
                    if sls_code in target_sls_codes:
                        sls_list.append({
                            "code": sls_code,
                            "kab_id": kab_id,
                            "kec_id": kec_id,
                            "desa_id": desa_id,
                            "sls_id": sls_info.get("id"),
                            "idsls_asli": sls_code
                        })
                    
    if not sls_list:
        print("Tidak ada target SLS yang cocok dengan region_mapping.json.")
        return None
        
    api_url_full = "https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode"
    
    csv_file = os.path.join(dir_path, "hasil_scraping_temp_jodi.csv")
    if os.path.exists(csv_file):
        os.remove(csv_file)
        
    # Kolom standar yang disyaratkan BPS API (Jika meminta data11, API akan me-return error)
    api_columns = [
        {"data": "id", "orderable": True},
        {"data": "codeIdentity", "orderable": True},
        {"data": "data1", "orderable": True},
        {"data": "data2", "orderable": True},
        {"data": "data3", "orderable": True},
        {"data": "data4", "orderable": True},
        {"data": "data5", "orderable": True},
        {"data": "data6", "orderable": True},
        {"data": "data7", "orderable": True},
        {"data": "data8", "orderable": True},
        {"data": "data9", "orderable": True},
        {"data": "data10", "orderable": True},
        {"data": "statusName", "orderable": True}
    ]
    
    # Bangun daftar (name, payload) untuk semua SLS
    sls_tasks = []
    for sls in sls_list:
        payload = {
            "start": 0, "length": 150,
            "assignmentExtraParam": {
                "surveyPeriodId": survey_id,
                "assignmentErrorStatusType": -1,
                "region1Id": region1Id,
                "region2Id": sls["kab_id"],
                "region3Id": sls["kec_id"],
                "region4Id": sls["desa_id"],
                "region5Id": sls["sls_id"]
            },
            "filterTargetType": "ALL",
            "surveyPeriodId": survey_id,
            "region1Id": region1Id,
            "region2Id": sls["kab_id"],
            "region3Id": sls["kec_id"],
            "region4Id": sls["desa_id"],
            "region5Id": sls["sls_id"],
            "columns": api_columns,
            "order": [],
            "search": {"value": "", "regex": False}
        }
        name_str = f"{sls['idsls_asli']}|{sls['code']}"
        sls_tasks.append((name_str, payload))

    # ── Navigate ke analytics TEPAT sebelum fetch (WAF session harus hangat) ──
    print("Menyegarkan sesi WAF sebelum scraping dimulai...")
    try:
        await page.goto(
            "https://fasih-sm.bps.go.id/app/analytic/assignment",
            wait_until="domcontentloaded",
            timeout=20000
        )
        await page.wait_for_timeout(3000)
        print(f"  Halaman analitik siap. Memulai browser fetch untuk {len(sls_tasks)} SLS...")
    except Exception as e:
        print(f"  Catatan: Gagal refresh sesi ({e}), lanjut.")

    # ── Scraping via browser native fetch (page.evaluate) ──
    # Token dipass dari Python (bukan dibaca via document.cookie) karena cookie bisa HttpOnly
    print(f"\n>>> Memulai proses penarikan data (Browser Native Fetch, batch 50 SLS)...")
    
    batch_records = []
    
    from tqdm import tqdm
    print(f"\n>>> Memulai proses penarikan data (Browser Native Fetch)...")
    
    pbar = tqdm(total=len(sls_tasks), desc="Scraping SLS", unit="sls")
    for name_str, payload in sls_tasks:
        sls_asli, sub_code = name_str.split("|")
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                js_result = await page.evaluate(
                    """
                    async ([url, payload, xsrf_token]) => {
                        try {
                            const resp = await fetch(url, {
                                method: 'POST',
                                credentials: 'include',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'Accept': 'application/json, text/plain, */*',
                                    'X-XSRF-TOKEN': xsrf_token,
                                    'X-Requested-With': 'XMLHttpRequest'
                                },
                                body: JSON.stringify(payload)
                            });
                            const text = await resp.text();
                            let data;
                            try { data = JSON.parse(text); } catch(e) { data = { _rawBody: text.substring(0, 200) }; }
                            return { status: resp.status, data: data };
                        } catch (err) {
                            return { status: 0, data: null, error: String(err) };
                        }
                    }
                    """,
                    [api_url_full, payload, xsrf_token]
                )
                
                status = js_result.get("status", 0)
                data = js_result.get("data") or {}
                
                if status == 200:
                    search_data = data.get("searchData", []) if isinstance(data, dict) else []
                    for row in search_data:
                        record = {k: v for k, v in row.items()}
                        record["Assignment ID"] = row.get("id")
                        record["ID_SLS"]        = sls_asli
                        record["ID_SUB_SLS"]    = sub_code
                        batch_records.append(record)
                    
                    # Sukses, delay cukup lama agar aman dari blokir
                    await asyncio.sleep(1.5)
                    break
                elif status == 429:
                    if attempt < max_retries - 1:
                        # Kena rate limit, tunggu agak lama (5 detik) sebelum coba lagi
                        tqdm.write(f"  [INFO] Rate limit di SLS {sls_asli}. Menunggu 5 detik... (Percobaan {attempt+1}/{max_retries})")
                        await asyncio.sleep(5.0)
                        continue
                    else:
                        tqdm.write(f"  [DEBUG] SLS {sls_asli} Gagal (Rate Limit 429) setelah {max_retries} percobaan.")
                        break
                else:
                    tqdm.write(f"  [DEBUG] SLS {sls_asli}: HTTP {status}, Error: {json.dumps(data)[:200]}")
                    break
                    
            except Exception as e:
                tqdm.write(f"  [ERROR] Evaluasi JS gagal untuk SLS {sls_asli}: {e}")
                break
                
        pbar.update(1)
        
    pbar.close()
            

                
    if batch_records:
        df_final = pd.DataFrame(batch_records)
        
        print("\nMenyiapkan data Usaha...")
        for col in df_final.columns:
            if "data" in col.lower() or col == "codeIdentity":
                df_final[col] = df_final[col].astype(str).str.replace(r'\.0$', '', regex=True)
                
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_csv = os.path.join(dir_path, f"{custom_name}_{timestamp}.csv")
        df_final.to_csv(output_csv, index=False)
        print(f"Data usaha (seluruh variabel) siap untuk proses detail.")
        return output_csv
    else:
        print("\nTidak ada data yang didapatkan dari scraping datatable.")
        return None

async def scrape_detail_data_jodi(page, xsrf_token, input_csv, custom_name="jodi_detail", max_workers=50):
    if not input_csv or not os.path.exists(input_csv):
        print("File CSV input untuk detail tidak valid.")
        return None, None
        
    df_existing = pd.read_csv(input_csv, low_memory=False)
    if "Assignment ID" not in df_existing.columns:
        print("Kolom 'Assignment ID' tidak ditemukan.")
        return None, None
        
    all_ids = df_existing["Assignment ID"].dropna().tolist()
    valid_ids = [a_id for a_id in all_ids if str(a_id).strip() and str(a_id) != "TIDAK_DITEMUKAN"]
    unique_assignment_ids = list(dict.fromkeys(valid_ids))
    
    total_found = len(unique_assignment_ids)
    if total_found == 0:
        print("Tidak ada Assignment ID valid untuk detail.")
        return None, None
    
    # --- Checkpoint/Resume: Skip ID yang sudah berhasil di-scrape sebelumnya ---
    checkpoint_file = os.path.join(dir_path, f"{custom_name}_checkpoint.json")
    completed_ids = set()
    resumed_data = []
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as cf:
                checkpoint = json.load(cf)
            completed_ids = set(checkpoint.get("completed_ids", []))
            # Load data yang sudah tersimpan sebelumnya
            checkpoint_data_file = checkpoint_file.replace('.json', '_data.jsonl')
            if os.path.exists(checkpoint_data_file):
                with open(checkpoint_data_file, "r", encoding="utf-8") as cdf:
                    for line in cdf:
                        try:
                            resumed_data.append(json.loads(line.strip()))
                        except:
                            pass
            print(f"[RESUME] Ditemukan {len(completed_ids)} ID yang sudah selesai sebelumnya. Melanjutkan sisa...")
        except Exception:
            completed_ids = set()
    
    # Filter hanya ID yang belum selesai
    pending_ids = [a_id for a_id in unique_assignment_ids if str(a_id) not in completed_ids]
    
    if not pending_ids:
        print(f"Semua {total_found} ID sudah selesai! Menggunakan data checkpoint.")
    else:
        print(f"Akan menarik {len(pending_ids)} ID untuk detail data (dari {total_found} total)...")
    
    sem = asyncio.Semaphore(max_workers)
    tasks = []
    for a_id in pending_ids:
        tasks.append(fetch_detail_api(page, a_id, xsrf_token, sem))
        
    all_api_data = list(resumed_data)  # Mulai dari data checkpoint
    failed_logs = []
    
    # Buka file checkpoint data untuk append
    checkpoint_data_file = checkpoint_file.replace('.json', '_data.jsonl')
    
    for coro in async_tqdm.as_completed(tasks, desc="Scraping Detail Jodi"):
        a_id, result, error = await coro
        if result:
            result['Assignment ID'] = a_id
            all_api_data.append(result)
            completed_ids.add(str(a_id))
            
            # Simpan ke checkpoint setiap berhasil
            try:
                with open(checkpoint_data_file, "a", encoding="utf-8") as cdf:
                    cdf.write(json.dumps(result, ensure_ascii=False) + "\n")
                with open(checkpoint_file, "w", encoding="utf-8") as cf:
                    json.dump({"completed_ids": list(completed_ids)}, cf)
            except Exception:
                pass
                
        if error:
            failed_logs.append({"Assignment ID": a_id, "Error": error})
            
    # --- SWEEP RETRY LOGIC UNTUK DATA YANG GAGAL ---
    sweep = 0
    max_sweeps = 10
    while failed_logs and sweep < max_sweeps:
        sweep += 1
        print(f"\n[INFO] Sweep {sweep}/{max_sweeps}: Mencoba kembali {len(failed_logs)} data yang gagal. Jeda 5 detik...")
        await asyncio.sleep(5)
        
        retry_tasks = []
        for item in failed_logs:
            retry_tasks.append(fetch_detail_api(page, item["Assignment ID"], xsrf_token, sem))
            
        current_failed = []
        
        for coro in async_tqdm.as_completed(retry_tasks, total=len(retry_tasks), desc=f"Retry Sweep {sweep}"):
            a_id, result, error = await coro
            if result:
                result['Assignment ID'] = a_id
                all_api_data.append(result)
                completed_ids.add(str(a_id))
                try:
                    with open(checkpoint_data_file, "a", encoding="utf-8") as cdf:
                        cdf.write(json.dumps(result, ensure_ascii=False) + "\n")
                    with open(checkpoint_file, "w", encoding="utf-8") as cf:
                        json.dump({"completed_ids": list(completed_ids)}, cf)
                except Exception:
                    pass
            if error:
                current_failed.append({"Assignment ID": a_id, "Error": error})
                
        failed_logs = current_failed

    if failed_logs:
        print(f"\n[WARNING] Setelah {sweep} iterasi, {len(failed_logs)} data tetap gagal ditarik (kemungkinan besar data di server bermasalah).")
    else:
        print(f"\n[INFO] Hore! Semua data berhasil ditarik setelah dilakukan {sweep} iterasi retry.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    error_file = None
    if failed_logs:
        error_file = os.path.join(dir_path, f"{custom_name}_error_log_{timestamp}.csv")
        pd.DataFrame(failed_logs).to_csv(error_file, index=False)
        print(f"\n[WARNING] Ada {len(failed_logs)} data detail gagal discrap.")

    output_file = None
    if all_api_data:
        api_data_df = pd.DataFrame(all_api_data)

        # --- Lengkapi schema dengan semua variabel kuesioner ---
        var_opts_file = os.path.join(dir_path, "var_options.json")
        if os.path.exists(var_opts_file):
            with open(var_opts_file, "r", encoding="utf-8") as vf:
                var_opts = json.load(vf)
            skip_css = {'<', '{', 'SE2026'}
            new_cols = {}
            for var_key in var_opts.keys():
                label = var_opts[var_key].get("question", "")
                if any(c in label for c in skip_css):
                    continue
                for prefix_col in [f"ans_{var_key}", f"pre_{var_key}"]:
                    if prefix_col not in api_data_df.columns:
                        new_cols[prefix_col] = [None] * len(api_data_df)
            
            if new_cols:
                new_cols_df = pd.DataFrame(new_cols, index=api_data_df.index)
                api_data_df = pd.concat([api_data_df, new_cols_df], axis=1)
            print(f"Schema dilengkapi: {len(api_data_df.columns)} kolom total.")

        # --- ENRICHMENT: Tambahkan kolom question/block/label untuk GUI ---
        print("Menjalankan enrichment untuk output GUI-ready...")
        gui_map = build_gui_mapping()
        api_data_df = enrich_detail_output(api_data_df, gui_map)

        output_file = os.path.join(dir_path, f"{custom_name}_{timestamp}.csv")
        api_data_df.to_csv(output_file, index=False)
        # Simpan juga sebagai parquet untuk efisiensi
        parquet_file = output_file.replace('.csv', '.parquet')
        api_data_df.to_parquet(parquet_file, index=False)
        print(f"Data detail diunduh: {len(api_data_df)} baris, {len(api_data_df.columns)} kolom.")
        print(f"  CSV   : {output_file}")
        print(f"  Parquet: {parquet_file}")
        
        # Simpan juga GUI mapping JSON untuk referensi di app.py
        save_gui_mapping_json()
    else:
        print("Tidak ada detail informasi yang didapat.")
    
    # Bersihkan checkpoint setelah berhasil
    try:
        if os.path.exists(checkpoint_file): os.remove(checkpoint_file)
        if os.path.exists(checkpoint_data_file): os.remove(checkpoint_data_file)
        print("Checkpoint telah dibersihkan.")
    except Exception:
        pass
        
    return output_file, error_file

async def main(template_file=None, scrape_detail=True, max_workers=80):
    print("==================================================")
    print("      UNIVERSAL BPS SCRAPER - JODI SPECIFIC       ")
    print("==================================================")

    # Jika tidak dipanggil dari CLI dengan argumen, gunakan mode interaktif
    if template_file is None:
        print("\nPILIHAN MENU:")
        print("1. Scraping Datatable Saja (Cepat, tapi tidak ada detail data11-data50)")
        print("2. Scraping Datatable + Detail Data (Lengkap, butuh waktu lebih lama)")
        pilihan = input("Pilih mode (1/2) [default: 2]: ").strip()
        scrape_detail = (pilihan != '1')
        template_file = os.path.join(dir_path, "Template jodi.xlsx")
        max_workers = 25  # Lebih aman dari rate limit server BPS
    else:
        print(f"\nMode: {'Datatable + Detail' if scrape_detail else 'Datatable Saja'}")
        print(f"Template: {template_file}")
        print(f"Max Workers: {max_workers}")
    
    print("\n1. Melakukan inisialisasi browser...")
    p, browser, page, xsrf_token = await init_browser_jodi()
    
    if not page:
        print("Gagal inisialisasi browser. Keluar...")
        return
        
    print("\n2. Menjalankan Menu 2 (Scraping Datatable Usaha)...")
    usaha_csv = await scrape_usaha_datatable_jodi(page, xsrf_token, template_file, custom_name="jodi_data_usaha", max_workers=max_workers)
    
    if usaha_csv:
        detail_csv, error_csv = None, None
        
        if scrape_detail:
            print("\n3. Menjalankan Menu 3 (Scraping Detail Data)...")
            detail_csv, error_csv = await scrape_detail_data_jodi(page, xsrf_token, usaha_csv, custom_name="jodi_detail_assignment", max_workers=max_workers)
        else:
            print("\n3. Melewati Menu 3 (Scraping Detail Data tidak dijalankan).")
            
        print("\n4. Menyimpan hasil ke dalam format CSV...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"Hasil_Scraping_Jodi_Lengkap_{timestamp}"
        
        # 1: Data Usaha
        df_usaha = pd.read_csv(usaha_csv, low_memory=False)
        df_usaha.to_csv(os.path.join(dir_path, f"{prefix}_Data_Usaha.csv"), index=False)
        
        # Buat Pivot assignmentStatusAlias dengan One-to-One matching (16 digit sub SLS)
        if 'codeIdentity' in df_usaha.columns:
            df_usaha['ID_SUB_SLS_REAL'] = df_usaha['codeIdentity'].astype(str).str.extract(r'^(\d{16})')[0]
            df_usaha['ID_SUB_SLS_REAL'] = df_usaha['ID_SUB_SLS_REAL'].fillna(df_usaha['ID_SLS'].astype(str) + "00")
        elif 'ID_SLS' in df_usaha.columns:
            df_usaha['ID_SUB_SLS_REAL'] = df_usaha['ID_SLS'].astype(str) + "00"
            
        if 'ID_SUB_SLS_REAL' in df_usaha.columns and 'assignmentStatusAlias' in df_usaha.columns:
            pivot_df = pd.crosstab(df_usaha['ID_SUB_SLS_REAL'], df_usaha['assignmentStatusAlias'])
            pivot_df = pivot_df.reset_index()
        else:
            pivot_df = pd.DataFrame()
            
        # 2: Template Wilayah + Merge Pivot One-to-One
        df_template = pd.read_excel(template_file)
        
        # Hapus kolom Submit, Draf, Total yang sudah ada di template lama
        cols_to_drop = [c for c in df_template.columns if str(c).strip().lower() in ['submit', 'draf', 'total']]
        df_template = df_template.drop(columns=cols_to_drop, errors='ignore')
        
        if 'idsls' in df_template.columns and not pivot_df.empty:
            idsls_str = df_template['idsls'].astype(str).str.replace(r'\.0$', '', regex=True)
            
            if 'kdsubsls' in df_template.columns:
                kdsubsls_str = df_template['kdsubsls'].astype(str).str.replace(r'\.0$', '', regex=True)
                kdsubsls_str = pd.to_numeric(kdsubsls_str, errors='coerce').fillna(0).astype(int).astype(str).str.zfill(2)
                df_template['id_match'] = idsls_str + kdsubsls_str
            else:
                df_template['id_match'] = idsls_str + "00"
                
            df_merged = pd.merge(df_template, pivot_df, left_on='id_match', right_on='ID_SUB_SLS_REAL', how='left')
            
            # Mengisi 0 pada hasil pivot agar tidak NaN
            status_cols = pivot_df.columns.drop('ID_SUB_SLS_REAL')
            for col in status_cols:
                if col in df_merged.columns:
                    df_merged[col] = df_merged[col].fillna(0).astype(int)
            
            # Ekstrak value spesifik
            val_open = df_merged['OPEN'] if 'OPEN' in df_merged.columns else pd.Series(0, index=df_merged.index)
            
            # Gabungkan semua status 'selesai' ke dalam val_submit
            submit_cols = [c for c in df_merged.columns if c in [
                'SUBMITTED BY Pencacah', 
                'APPROVED BY Pengawas', 
                'COMPLETED BY Admin Kabupaten', 
                'EDITED BY Admin Kabupaten',
                'SUBMITTED RESPONDENT'
            ]]
            if submit_cols:
                val_submit = df_merged[submit_cols].sum(axis=1)
            else:
                val_submit = pd.Series(0, index=df_merged.index)
                
            val_draft = df_merged['DRAFT'] if 'DRAFT' in df_merged.columns else pd.Series(0, index=df_merged.index)
            
            total_all = df_merged[status_cols].sum(axis=1)
            
            # Buat kolom baru sesuai instruksi
            df_merged['Open'] = val_open
            df_merged['Submit'] = val_submit
            df_merged['Draft 1'] = total_all - val_open - val_submit
            df_merged['Total'] = df_merged['Submit'] + df_merged['Draft 1']
            df_merged['Draft 2'] = val_draft
            
            # Susun kolom akhir
            template_base_cols = [c for c in df_template.columns if c != 'id_match']
            other_statuses = [c for c in status_cols if c not in ['OPEN', 'SUBMITTED BY Pencacah', 'DRAFT']]
            
            final_cols = template_base_cols + ['Open', 'Submit', 'Draft 1', 'Total', 'Draft 2'] + other_statuses
            
            df_merged = df_merged[final_cols]
            df_merged.to_csv(os.path.join(dir_path, f"{prefix}_Template_Wilayah.csv"), index=False)
            
            # --- FILE KINERJA PPL ---
            if 'PPL' in df_merged.columns:
                valid_ppl_cols = [c for c in ['Open', 'Submit', 'Draft 1', 'Draft 2'] + other_statuses if c in df_merged.columns]
                
                group_cols = ['PPL']
                if 'Pj-Kuda' in df_merged.columns:
                    group_cols.insert(0, 'Pj-Kuda')
                    
                df_ppl = df_merged.groupby(group_cols)[valid_ppl_cols].sum().reset_index()
                
                # 1. Total semua status (Beban Tugas)
                # Hindari double counting: Beban sesungguhnya adalah Open + Submit + Draft 1
                base_cols = [c for c in ['Open', 'Submit', 'Draft 1'] if c in df_ppl.columns]
                df_ppl['Beban Tugas (Total)'] = df_ppl[base_cols].sum(axis=1)
                
                # 2. Persentase Selesai Lapangan
                # Selesai lapangan = Beban Tugas - Open (alias Submit + Draft 1)
                df_ppl['Selesai Lapangan'] = df_ppl['Beban Tugas (Total)'] - df_ppl.get('Open', 0)
                df_ppl['% Selesai Lapangan'] = (df_ppl['Selesai Lapangan'] / df_ppl['Beban Tugas (Total)'].replace(0, 1) * 100).round(2)
                
                # 3. Rata-rata per hari (dari 15 Juni)
                now = datetime.now()
                start_date = datetime(now.year, 6, 15)
                hari_berjalan = (now - start_date).days
                if hari_berjalan <= 0:
                    hari_berjalan = 1
                    
                df_ppl['Kecepatan (Dokumen/Hari)'] = (df_ppl['Selesai Lapangan'] / hari_berjalan).round(2)
                
                # 4. Metric tambahan untuk pantauan
                df_ppl['Sisa Dokumen (Open)'] = df_ppl.get('Open', 0)
                df_ppl['Estimasi Butuh Waktu (Hari)'] = (df_ppl['Sisa Dokumen (Open)'] / df_ppl['Kecepatan (Dokumen/Hari)'].replace(0, 0.0001)).round(1)
                
                if 'Submit' in df_ppl.columns:
                    df_ppl['% Progress Murni (Submit)'] = (df_ppl['Submit'] / df_ppl['Beban Tugas (Total)'].replace(0, 1) * 100).round(2)
                    
                # Urutkan dari yang % Selesai Lapangan nya paling rendah agar prioritas pantau
                df_ppl = df_ppl.sort_values(by='% Selesai Lapangan', ascending=True)
                df_ppl.to_csv(os.path.join(dir_path, f"{prefix}_Kinerja_PPL.csv"), index=False)
                
                # --- REKAP PCL ---
                print("\nMembuat Rekap PCL...")
                rekap_rows = []
                
                for ppl_name, grp_sls in df_merged.groupby('PPL'):
                    # Total SLS = jumlah SLS unik per PPL
                    total_sls = grp_sls['idsls'].nunique() if 'idsls' in grp_sls.columns else 0
                    
                    # SLS Selesai = SLS di mana semua assignment-nya Submit
                    sls_selesai = 0
                    if 'idsls' in grp_sls.columns and 'Submit' in grp_sls.columns and 'Open' in grp_sls.columns:
                        for sls_id, sls_grp in grp_sls.groupby('idsls'):
                            total_sls_assign = sls_grp[['Open','Submit','Draft 1']].sum(axis=1).sum() if 'Draft 1' in sls_grp.columns else (sls_grp['Open'] + sls_grp['Submit']).sum()
                            submitted_sls = sls_grp['Submit'].sum() if 'Submit' in sls_grp.columns else 0
                            if total_sls_assign > 0 and submitted_sls >= total_sls_assign:
                                sls_selesai += 1
                    
                    pct_sls = round(sls_selesai / total_sls * 100, 2) if total_sls > 0 else 0.0
                    
                    # Jumlah Prelist Awal = total assignment (dari request user)
                    open_val   = int(grp_sls['Open'].sum())   if 'Open'   in grp_sls.columns else 0
                    submit_val = int(grp_sls['Submit'].sum()) if 'Submit' in grp_sls.columns else 0
                    draft_val  = int(grp_sls['Draft 1'].sum()) if 'Draft 1' in grp_sls.columns else 0
                    
                    hardcoded_prelist = {
                        "DEVITA AYUNANI": 804,
                        "DEWI SINTA WAHYUNI": 627,
                        "DIA LESTARI": 787,
                        "HARDIAN": 614,
                        "SABARINA SITORUS": 755,
                        "SELVINA AZAHRA": 882,
                        "SINTA MARGARETA": 226
                    }
                    pcl_key = str(ppl_name).strip().upper()
                    jumlah_prelist = hardcoded_prelist.get(pcl_key, open_val + submit_val + draft_val)
                    
                    total_assign = open_val + submit_val + draft_val
                    asgn_selesai_draft = submit_val + draft_val
                    pct_selesai       = round(submit_val / total_assign * 100, 2) if total_assign > 0 else 0.0
                    pct_selesai_draft = round(asgn_selesai_draft / total_assign * 100, 2) if total_assign > 0 else 0.0
                    
                    rekap_rows.append({
                        'PCL'                           : ppl_name,
                        'Total SLS'                     : total_sls,
                        'SLS Selesai'                   : sls_selesai,
                        '% SLS'                         : pct_sls,
                        'Jumlah Prelist Awal'           : jumlah_prelist,
                        'Total Assignment'              : total_assign,
                        'Assignment Selesai'            : submit_val,
                        'Jumlah Draft'                  : draft_val,
                        'Assignment Selesai + Draft'    : asgn_selesai_draft,
                        '% Assignment Selesai'          : pct_selesai,
                        '% Assignment Selesai + Draft'  : pct_selesai_draft,
                        'Pengawasan'                    : 0,
                        'Pemeriksaan'                   : 0,
                    })
                
                if rekap_rows:
                    df_rekap = pd.DataFrame(rekap_rows).sort_values('PCL').reset_index(drop=True)
                    
                    # Baris TOTAL
                    tot_prelist = df_rekap['Jumlah Prelist Awal'].sum()
                    tot_assign  = df_rekap['Total Assignment'].sum()
                    tot_selesai = df_rekap['Assignment Selesai'].sum()
                    tot_draft   = df_rekap['Jumlah Draft'].sum()
                    tot_sls_done = df_rekap['SLS Selesai'].sum()
                    tot_sls_all  = df_rekap['Total SLS'].sum()
                    total_row = {
                        'PCL'                           : 'TOTAL',
                        'Total SLS'                     : tot_sls_all,
                        'SLS Selesai'                   : tot_sls_done,
                        '% SLS'                         : round(tot_sls_done / tot_sls_all * 100, 2) if tot_sls_all > 0 else 0.0,
                        'Jumlah Prelist Awal'           : tot_prelist,
                        'Total Assignment'              : tot_assign,
                        'Assignment Selesai'            : tot_selesai,
                        'Jumlah Draft'                  : tot_draft,
                        'Assignment Selesai + Draft'    : tot_selesai + tot_draft,
                        '% Assignment Selesai'          : round(tot_selesai / tot_assign * 100, 2) if tot_assign > 0 else 0.0,
                        '% Assignment Selesai + Draft'  : round((tot_selesai + tot_draft) / tot_assign * 100, 2) if tot_assign > 0 else 0.0,
                        'Pengawasan'                    : 0,
                        'Pemeriksaan'                   : 0,
                    }
                    df_rekap = pd.concat([df_rekap, pd.DataFrame([total_row])], ignore_index=True)
                    
                    rekap_file = os.path.join(dir_path, f"{prefix}_Rekap_PCL.csv")
                    df_rekap.to_csv(rekap_file, index=False)
                    
                    print(f"\n{'='*90}")
                    print("REKAP PCL")
                    print(f"{'='*90}")
                    print(df_rekap.to_string(index=False))
                    print(f"{'='*90}")
                    print(f"File rekap disimpan: {prefix}_Rekap_PCL.csv")
                
        else:
            df_template.to_csv(os.path.join(dir_path, f"{prefix}_Template_Wilayah.csv"), index=False)
            if not pivot_df.empty:
                pivot_df.to_csv(os.path.join(dir_path, f"{prefix}_Rekap_Status.csv"), index=False)
        
        # 3: Detail Data
        if detail_csv and os.path.exists(detail_csv):
            parquet_detail = detail_csv.replace('.csv', '.parquet')
            if os.path.exists(parquet_detail):
                df_detail = pd.read_parquet(parquet_detail)
            else:
                df_detail = pd.read_csv(detail_csv, low_memory=False)
            
            # Tambahkan status assignment dan nama PPL dari df_usaha menggunakan codeIdentity
            detail_code_col = '_meta_code_identity' if '_meta_code_identity' in df_detail.columns else 'codeIdentity'
            
            if detail_code_col in df_detail.columns and 'codeIdentity' in df_usaha.columns:
                if 'assignmentStatusAlias' in df_usaha.columns:
                    status_map = df_usaha.set_index('codeIdentity')['assignmentStatusAlias'].to_dict()
                    df_detail['Status Assignment'] = df_detail[detail_code_col].map(status_map)
                    
                if 'currentUserFullname' in df_usaha.columns:
                    ppl_map = df_usaha.set_index('codeIdentity')['currentUserFullname'].to_dict()
                    df_detail['currentUserFullname'] = df_detail[detail_code_col].map(ppl_map)
                
                # Pindahkan kolom ke setelah 'Assignment ID'
                cols = df_detail.columns.tolist()
                if 'Status Assignment' in cols:
                    cols.remove('Status Assignment')
                    if 'Assignment ID' in cols:
                        insert_idx = cols.index('Assignment ID') + 1
                    elif 'id' in cols:
                        insert_idx = cols.index('id') + 1
                    else:
                        insert_idx = 0
                    cols.insert(insert_idx, 'Status Assignment')
                    df_detail = df_detail[cols]
                
            df_detail.to_csv(os.path.join(dir_path, f"{prefix}_Detail_Data.csv"), index=False)
            
        # 4: Error Log (Jika ada)
        if error_csv and os.path.exists(error_csv):
            df_error = pd.read_csv(error_csv, low_memory=False)
            df_error.to_csv(os.path.join(dir_path, f"{prefix}_Error_Log.csv"), index=False)
            
        excel_path = os.path.join(dir_path, f"{prefix}_Laporan_Lengkap.xlsx")
        print(f"\nMenyimpan laporan dalam format Excel ke: {os.path.basename(excel_path)}")
        try:
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                if 'df_rekap' in locals() and not df_rekap.empty:
                    df_rekap.to_excel(writer, sheet_name='Rekap PCL', index=False)
                if 'df_ppl' in locals() and not df_ppl.empty:
                    df_ppl.to_excel(writer, sheet_name='Kinerja PPL', index=False)
                if 'df_merged' in locals() and not df_merged.empty:
                    df_merged.to_excel(writer, sheet_name='Template Wilayah', index=False)
                if 'df_usaha' in locals() and not df_usaha.empty:
                    df_usaha.to_excel(writer, sheet_name='Data Usaha', index=False)
                if 'df_detail' in locals() and not df_detail.empty:
                    df_detail.to_excel(writer, sheet_name='Detail Data', index=False)
                if 'df_error' in locals() and not df_error.empty:
                    df_error.to_excel(writer, sheet_name='Error Log', index=False)
            print(f"Berhasil menyimpan file Excel.")
        except Exception as e:
            print(f"Gagal menyimpan file Excel: {e}")
            
        print(f"\n==================================================")
        print(f"BERHASIL! Data telah disimpan dalam format CSV & Excel dengan prefix:")
        print(f"--> {prefix}_...csv")
        print(f"==================================================")
        
        # --- UPLOAD KE DATABASE TIDB ---
        print("\nMemeriksa kredensial database TiDB di .env...")
        from dotenv import load_dotenv
        from sqlalchemy import create_engine
        
        load_dotenv()
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT", "4000")
        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASS")
        db_name = os.getenv("DB_NAME")
        
        if db_host and db_user and db_pass and db_pass != "MASUKKAN_PASSWORD_DISINI":
            try:
                import certifi
                ca_path = certifi.where()
                
                print(f"Mengunggah tabel ke database {db_name} di {db_host}...")
                
                # Memaksa koneksi TLS/SSL menggunakan certifi (wajib untuk TiDB Cloud Serverless)
                db_url = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}?ssl_ca={ca_path}&ssl_verify_cert=true&ssl_verify_identity=true"
                engine = create_engine(db_url)
                
                if 'df_rekap' in locals() and not df_rekap.empty:
                    print("  Upload Rekap PCL...")
                    df_rekap.to_sql('rekap_pcl', con=engine, if_exists='replace', index=False)
                if 'df_ppl' in locals() and not df_ppl.empty:
                    print("  Upload Kinerja PPL...")
                    df_ppl.to_sql('kinerja_ppl', con=engine, if_exists='replace', index=False)
                if 'df_merged' in locals() and not df_merged.empty:
                    print("  Upload Template Wilayah...")
                    df_merged.to_sql('template_wilayah', con=engine, if_exists='replace', index=False)
                if 'df_usaha' in locals() and not df_usaha.empty:
                    print("  Upload Data Usaha...")
                    df_usaha.to_sql('data_usaha', con=engine, if_exists='replace', index=False)
                if 'df_detail' in locals() and not df_detail.empty:
                    print("  Upload Detail Data...")
                    df_detail.to_sql('detail_data', con=engine, if_exists='replace', index=False)
                if 'df_error' in locals() and not df_error.empty:
                    print("  Upload Error Log...")
                    df_error.to_sql('error_log', con=engine, if_exists='replace', index=False)
                print("Berhasil mengunggah semua tabel ke TiDB!")
            except Exception as e:
                print(f"Gagal mengunggah ke TiDB: {e}")
        else:
            print("Upload ke TiDB dilewati. Password/kredensial di file .env belum diisi.")
        
        # Membersihkan file CSV sementara
        try:
            if os.path.exists(usaha_csv): os.remove(usaha_csv)
            if detail_csv and os.path.exists(detail_csv): os.remove(detail_csv)
            if error_csv and os.path.exists(error_csv): os.remove(error_csv)
            print("File CSV temporary telah dihapus.")
        except Exception as e:
            print(f"Catatan: Gagal menghapus beberapa file sementara: {e}")
            
    else:
        print("\nProses berhenti karena scraping datatable gagal/kosong.")

    await browser.close()
    await p.stop()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="JODI BPS Scraper")
    parser.add_argument("--template", type=str, default=None,
                        help="Path ke file template Excel. Jika tidak diisi, akan prompt interaktif.")
    parser.add_argument("--mode", type=str, choices=["1", "2"], default=None,
                        help="Mode scraping: 1=Datatable saja, 2=Datatable+Detail")
    parser.add_argument("--workers", type=int, default=80,
                        help="Jumlah koneksi paralel (default: 80)")
    args = parser.parse_args()

    if args.template:
        # Dipanggil dari GUI — non-interaktif
        scrape_detail = (args.mode != "1")
        asyncio.run(main(
            template_file=args.template,
            scrape_detail=scrape_detail,
            max_workers=args.workers
        ))
    else:
        # Dipanggil manual dari terminal — interaktif seperti biasa
        asyncio.run(main())
