import asyncio
import json
import os
import re
import html as html_module
import pandas as pd
from datetime import datetime
from survey_manager import load_config
from tqdm.asyncio import tqdm as async_tqdm

dir_path = os.path.dirname(os.path.abspath(__file__))
region_file = os.path.join(dir_path, "region_mapping.json")

async def _fetch_single(page, url, payload, xsrf_token, sem, retry_count):
    full_url = f"https://fasih-sm.bps.go.id{url}" if url.startswith("/") else url
    async with sem:
        for r in range(retry_count):
            try:
                resp = await page.context.request.post(
                    full_url,
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-XSRF-TOKEN': xsrf_token
                    },
                    data=json.dumps(payload)  # HARUS json.dumps() — dict biasa dikirim sbg form-encoded
                )
                if resp.ok:
                    res = await resp.json()
                    if isinstance(res, dict) and "searchData" in res:
                        return res["searchData"]
                    else:
                        # Response OK tapi struktur tidak sesuai — log sekali saja (retry pertama)
                        if r == 0:
                            keys = list(res.keys()) if isinstance(res, dict) else type(res).__name__
                            print(f"\n[DEBUG] API OK tapi 'searchData' tidak ada. Keys: {keys}")
                        await asyncio.sleep(min(2 ** (r + 1), 16))
                else:
                    # Log status HTTP error
                    if r == 0:
                        print(f"\n[DEBUG] API HTTP {resp.status} — kemungkinan payload/sesi bermasalah.")
                    await asyncio.sleep(min(2 ** (r + 1), 16))
            except Exception as e:
                if r == 0:
                    print(f"\n[DEBUG] Exception saat request API: {e}")
                await asyncio.sleep(min(2 ** (r + 1), 16))
        return []

async def fetch_datatable(page, url, payload_template, xsrf_token, sem, name, retry_count=3):
    p_all = payload_template.copy()
    p_all["filterTargetType"] = "ALL"
    
    data_all = await _fetch_single(page, url, p_all, xsrf_token, sem, retry_count)
    if len(data_all) < 1000:
        return name, data_all
        
    # Hit 1000 limit! Split by TARGET and NON_TARGET
    all_data = []
    for ftype in ["TARGET_ONLY", "NON_TARGET_ONLY"]:
        p_sub = payload_template.copy()
        p_sub["filterTargetType"] = ftype
        data_sub = await _fetch_single(page, url, p_sub, xsrf_token, sem, retry_count)
        
        if len(data_sub) < 1000:
            all_data.extend(data_sub)
        else:
            # Hit 1000 again! Split by ASC and DESC
            p_sub["order"] = [{"column": 0, "dir": "asc"}]
            data_asc = await _fetch_single(page, url, p_sub, xsrf_token, sem, retry_count)
            
            p_sub["order"] = [{"column": 0, "dir": "desc"}]
            data_desc = await _fetch_single(page, url, p_sub, xsrf_token, sem, retry_count)
            
            # Merge and deduplicate
            combined = {row["id"]: row for row in data_asc + data_desc if "id" in row}
            all_data.extend(list(combined.values()))
            
    # Final deduplication just in case
    final_combined = {row["id"]: row for row in all_data if "id" in row}
    return name, list(final_combined.values())

async def scrape_usaha_datatable(page, xsrf_token, custom_name="", max_workers=50):
    cfg = load_config()
    survey_id = cfg.get("survey_period_id")
    region1Id = cfg.get("region1Id")
    if not survey_id or not region1Id:
        print("Survey ID atau Provinsi belum diatur. Jalankan Setup Survei terlebih dahulu.")
        return None

    if not os.path.exists(region_file):
        print("region_mapping.json tidak ditemukan! Jalankan Setup Survei untuk mengunduh wilayah.")
        return None
        
    with open(region_file, "r", encoding="utf-8") as f:
        region_data = json.load(f)
        
    sls_list = []
    # Dynamic region extraction
    for kab_code, kab_info in region_data.items():
        kab_id = kab_info.get("id")
        for kec_code, kec_info in kab_info.get("kecamatan", {}).items():
            kec_id = kec_info.get("id")
            for desa_code, desa_info in kec_info.get("desa", {}).items():
                desa_id = desa_info.get("id")
                for sls_code, sls_info in desa_info.get("sls", {}).items():
                    sls_list.append({
                        "code": sls_code,
                        "kab_id": kab_id,
                        "kec_id": kec_id,
                        "desa_id": desa_id,
                        "sls_id": sls_info.get("id")
                    })
                    
    if not sls_list:
        print("Tidak ada data SLS di region_mapping.json.")
        return None
        
    print(f"\nAkan menarik data Usaha untuk {len(sls_list)} SLS secara paralel.")
    
    sem = asyncio.Semaphore(max_workers)
    api_url = "/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode"
    
    csv_file = os.path.join(dir_path, "hasil_scraping_temp.csv")
    if os.path.exists(csv_file):
        os.remove(csv_file)
    
    tasks = []
    for sls in sls_list:
        payload = {
            "start": 0, "length": 1000,
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
            "columns": [
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
            ],
            "order": [],
            "search": {"value": "", "regex": False}
        }
        tasks.append(fetch_datatable(page, api_url, payload, xsrf_token, sem, f"SLS {sls['code']}"))
        
    print(f"\n>>> Memulai proses penarikan data (Turbo Mode dengan {max_workers} Koneksi Paralel)...")
    
    batch_records = []
    all_records_count = 0
    total_sls = len(sls_list)
    
    for coro in async_tqdm.as_completed(tasks, desc="Scraping Datatable"):
        sls_code, search_data = await coro
        
        if search_data:
            for row in search_data:
                batch_records.append({
                    "Kode Identitas": row.get("codeIdentity"),
                    "Data 1": row.get("data1"),
                    "Data 2": row.get("data2"),
                    "Data 3": row.get("data3"),
                    "Data 4": row.get("data4"),
                    "Data 5": row.get("data5"),
                    "Data 6": row.get("data6"),
                    "Data 7": row.get("data7"),
                    "Data 8": row.get("data8"),
                    "Data 9": row.get("data9"),
                    "Data 10": row.get("data10"),
                    "Status": row.get("statusName"),
                    "Assignment ID": row.get("id")
                })
                
        if len(batch_records) >= 2000:
            df_batch = pd.DataFrame(batch_records)
            mode = 'a' if os.path.exists(csv_file) else 'w'
            header = not os.path.exists(csv_file)
            df_batch.to_csv(csv_file, mode=mode, header=header, index=False)
            batch_records = []
            
    # Sisa data
    if batch_records:
        df_batch = pd.DataFrame(batch_records)
        mode = 'a' if os.path.exists(csv_file) else 'w'
        header = not os.path.exists(csv_file)
        df_batch.to_csv(csv_file, mode=mode, header=header, index=False)
                
    if os.path.exists(csv_file):
        print("\nMenyimpan data Usaha...")
        df_final = pd.read_csv(csv_file, low_memory=False)
        for col in ["Kode Identitas", "Data 1", "Data 2"]:
            if col in df_final.columns:
                df_final[col] = df_final[col].astype(str).str.replace(r'\.0$', '', regex=True)
                
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = custom_name if custom_name else "universal_data_usaha"
        output_csv = os.path.join(dir_path, f"{prefix}_{timestamp}.csv")
        df_final.to_csv(output_csv, index=False)
        print(f"BERHASIL! Total {len(df_final)} data lengkap disimpan dengan kilat ke: {output_csv}")
        try: os.remove(csv_file)
        except: pass
        return output_csv
    else:
        print("\nTidak ada data yang didapatkan.")
        return None

def parse_answer(ans):
    """Parse satu nilai jawaban dari berbagai format JSON Fasih.
    Returns: (display_value, raw_value) tuple.
    display_value = label yang readable untuk user.
    raw_value = value kode asli.
    """
    if ans is None:
        return "", ""
    if isinstance(ans, list):
        display_vals = []
        raw_vals = []
        for item in ans:
            if isinstance(item, dict):
                if "label" in item:
                    display_vals.append(str(item["label"]))
                    raw_vals.append(str(item.get("value", item["label"])))
                elif "value" in item:
                    display_vals.append(str(item["value"]))
                    raw_vals.append(str(item["value"]))
                else:
                    display_vals.append(str(item))
                    raw_vals.append(str(item))
            else:
                display_vals.append(str(item))
                raw_vals.append(str(item))
        return " | ".join(display_vals), " | ".join(raw_vals)
    elif isinstance(ans, dict):
        if "label" in ans:
            return str(ans["label"]), str(ans.get("value", ans["label"]))
        elif "value" in ans:
            return str(ans["value"]), str(ans["value"])
        return str(ans), str(ans)
    return str(ans), str(ans)


def parse_answer_compat(ans):
    """Wrapper kompatibel: return display_value saja (untuk backward compat)."""
    display, _ = parse_answer(ans)
    return display


def flatten_assignment_data(raw_json):
    """
    Mengekstrak SEMUA data dari satu assignment API response ke dict datar.
    Mencakup: metadata, prelist (pre_*), jawaban (ans_*), anomali, dan roster.
    
    Perbaikan:
    - Roster/datagrid sekarang di-index (ans_var#1, ans_var#2, ...) agar tidak overwrite
    - Menyimpan display value DAN raw value (ans_*_raw) untuk kemudahan GUI
    """
    flat_data = {}
    if not isinstance(raw_json, dict) or "data" not in raw_json:
        return flat_data

    core = raw_json["data"]
    if not isinstance(core, dict):
        return flat_data

    # --- Metadata assignment ---
    flat_data["_id"] = core.get("_id")
    flat_data["survey_period_id"] = core.get("survey_period_id")
    
    # codeIdentity: coba beberapa nama key yang mungkin
    flat_data["codeIdentity"] = (
        core.get("codeIdentity") or
        core.get("code_identity") or
        core.get("codeidentity") or
        core.get("code_master")
    )
    
    flat_data["assignment_error_status_type"] = core.get("assignment_error_status_type")
    
    # Status assignment: ambil dari alias atau status_id
    flat_data["assignmentStatusAlias"] = (
        core.get("assignmentStatusAlias") or
        core.get("assignment_status_alias") or
        core.get("statusAlias")
    )
    
    # PPL: ambil dari nama petugas yang sedang memegang
    flat_data["assigned_PPL"] = (
        core.get("assigned_PPL") or
        core.get("current_user_fullname") or
        core.get("currentUserFullname")
    )
    
    # Waktu mulai/selesai: beberapa variasi nama
    flat_data["mulai"] = (
        core.get("mulai") or
        core.get("date_created") or
        core.get("dateCreated")
    )
    flat_data["selesai"] = (
        core.get("selesai") or
        core.get("date_modified") or
        core.get("dateModified")
    )
    flat_data["date_created"] = core.get("date_created") or core.get("dateCreated")
    flat_data["date_modified"] = core.get("date_modified") or core.get("dateModified")

    if isinstance(core.get("mode"), list) and len(core.get("mode")) > 0:
        flat_data["mode"] = core["mode"][0]
    else:
        flat_data["mode"] = core.get("mode")

    # --- Data Prelist (pre_*) ---
    pre_val = core.get("pre_defined_data")
    if pre_val:
        try:
            pre_json = json.loads(pre_val) if isinstance(pre_val, str) else pre_val
            if isinstance(pre_json, dict) and "predata" in pre_json:
                for item in pre_json["predata"]:
                    dk = item.get("dataKey", "")
                    if not dk:
                        continue
                    ans = item.get("answer")
                    if ans is not None:
                        display, raw = parse_answer(ans)
                        flat_data[f"pre_{dk}"] = display
                        if raw != display:
                            flat_data[f"pre_{dk}_raw"] = raw
                    else:
                        flat_data[f"pre_{dk}"] = ""
        except Exception:
            pass

    # --- Data Jawaban PPL (ans_*) ---
    ans_val = core.get("data")
    if ans_val:
        try:
            ans_json = json.loads(ans_val) if isinstance(ans_val, str) else ans_val
            if isinstance(ans_json, dict) and "answers" in ans_json:
                _flatten_answers(ans_json["answers"], flat_data, prefix="ans")
        except Exception:
            pass

    # --- Tangkap semua key top-level lain yang belum diambil ---
    # (mis. is_assignment_tambahan, jml_usaha_keluarga, dll.)
    skip_keys = {"data", "pre_defined_data", "_id", "survey_period_id", "mode",
                 "assignment_error_status_type", "codeIdentity", "assignmentStatusAlias",
                 "assigned_PPL", "mulai", "selesai"}
    for k, v in core.items():
        if k not in skip_keys and k not in flat_data:
            if isinstance(v, (str, int, float, bool)) or v is None:
                flat_data[f"_meta_{k}"] = v

    return flat_data


def _flatten_answers(answers_list, flat_data, prefix="ans", roster_idx=None):
    """
    Rekursif flatten jawaban, termasuk nested roster/datagrid.
    Roster items mendapat index: ans_var#1, ans_var#2, ...
    """
    for item in answers_list:
        dk = item.get("dataKey", "")
        if not dk:
            continue
        ans = item.get("answer")
        
        # Kunci kolom dengan index roster jika ada
        col_suffix = f"#{roster_idx}" if roster_idx is not None else ""
        col_key = f"{prefix}_{dk}{col_suffix}"

        # Kasus 1: Jawaban adalah list-of-dicts dengan field 'dataKey'
        # → Ini adalah ROSTER/DATAGRID (mis. data anggota keluarga)
        if isinstance(ans, list) and ans and isinstance(ans[0], dict) and "dataKey" in ans[0]:
            # Cek apakah ini daftar baris roster (list of list-of-answers)
            # atau daftar sub-answers (single roster row)
            # Coba deteksi: jika semua item punya dataKey, ini satu baris roster
            # Simpan jumlah roster items
            flat_data[f"{prefix}_{dk}_count{col_suffix}"] = len(ans)
            
            # Group by roster rows berdasarkan pola dataKey
            # Fasih biasanya menyimpan semua sub-fields flat dalam satu list
            _flatten_answers(ans, flat_data, prefix=prefix, roster_idx=roster_idx)
        
        elif isinstance(ans, list) and ans and isinstance(ans[0], list):
            # Kasus: Multi-row roster — list of lists
            flat_data[f"{prefix}_{dk}_count{col_suffix}"] = len(ans)
            for row_idx, row in enumerate(ans, 1):
                if isinstance(row, list):
                    _flatten_answers(row, flat_data, prefix=prefix, roster_idx=row_idx)
                    
        else:
            # Kasus 2: Jawaban biasa (skalar, pilihan, teks)
            if ans is not None:
                display, raw = parse_answer(ans)
                flat_data[col_key] = display
                if raw != display:
                    flat_data[f"{col_key}_raw"] = raw
            else:
                flat_data[col_key] = ""

async def fetch_detail_api(page, a_id, xsrf_token, sem, retry_count=7):
    api_url = f"https://fasih-sm.bps.go.id/app/api/assignment-general/api/assignment/get-by-assignment-id?assignmentId={a_id}"
    import random
    async with sem:
        last_error = "Unknown"
        for r in range(retry_count):
            try:
                resp = await page.context.request.get(
                    api_url,
                    headers={
                        'Accept': 'application/json',
                        'X-XSRF-TOKEN': xsrf_token
                    },
                    timeout=60000
                )
                if resp.ok:
                    res = await resp.json()
                    if isinstance(res, dict) and res.get("success") == True:
                        flat_row = flatten_assignment_data(res)
                        flat_row["_origin_assignmentId"] = a_id
                        return (a_id, flat_row, None)
                    else:
                        last_error = "Response not successful"
                        await asyncio.sleep(min(2 ** (r + 1), 20) + random.uniform(0, 2))
                else:
                    last_error = f"ERROR_{resp.status}"
                    await asyncio.sleep(min(2 ** (r + 1), 20) + random.uniform(0, 2))
            except Exception as e:
                last_error = f"Exception: {str(e)}"
                await asyncio.sleep(min(2 ** (r + 1), 20) + random.uniform(0, 2))
        return (a_id, None, last_error)

async def scrape_detail_data(page, xsrf_token, input_excel, custom_name="", start_idx=0, end_idx=None, max_workers=50):
    if not os.path.exists(input_excel):
        print(f"File {input_excel} tidak ditemukan.")
        return None
        
    try:
        if input_excel.endswith('.csv'):
            df_existing = pd.read_csv(input_excel, low_memory=False)
        else:
            df_existing = pd.read_excel(input_excel)
            if "Assignment ID" not in df_existing.columns:
                try: df_existing = pd.read_excel(input_excel, sheet_name='Data_Usaha')
                except Exception: pass
                
        if "Assignment ID" not in df_existing.columns:
            print("Kolom 'Assignment ID' tidak ditemukan pada file sumber.")
            return None
            
        all_ids = df_existing["Assignment ID"].dropna().tolist()
        valid_ids = [a_id for a_id in all_ids if str(a_id).strip() and str(a_id) != "TIDAK_DITEMUKAN"]
        unique_assignment_ids = list(dict.fromkeys(valid_ids))
        
        total_found = len(unique_assignment_ids)
        if total_found == 0:
            print("Tidak ada Assignment ID valid yang bisa diproses.")
            return None
            
        if end_idx is None or end_idx > total_found:
            end_idx = total_found
        if start_idx < 0:
            start_idx = 0
            
        unique_assignment_ids = unique_assignment_ids[start_idx:end_idx]
        
        if not unique_assignment_ids:
            print("Rentang baris tidak valid. Tidak ada Assignment ID untuk ditarik.")
            return None
            
        print(f"Berhasil menemukan {total_found} ID. Akan memproses baris {start_idx + 1} hingga {end_idx} (Total: {len(unique_assignment_ids)} ID).")
    except Exception as e:
        print(f"Gagal membaca file sumber: {e}")
        return None

    sem = asyncio.Semaphore(max_workers)
    tasks = []
    for a_id in unique_assignment_ids:
        tasks.append(fetch_detail_api(page, a_id, xsrf_token, sem))
        
    print(f"\n>>> Memulai proses penarikan data detail (Turbo Mode dengan {max_workers} Koneksi Paralel)...")
    
    all_api_data = []
    failed_logs = []
    
    for coro in async_tqdm.as_completed(tasks, desc="Scraping Detail"):
        a_id, result, error = await coro
        if result:
            all_api_data.append(result)
        else:
            failed_logs.append({"Assignment ID": a_id, "Error": error})
            
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = custom_name if custom_name else "universal_detail_assignment"
    
    if failed_logs:
        error_file = os.path.join(dir_path, f"{prefix}_error_log_{timestamp}.csv")
        pd.DataFrame(failed_logs).to_csv(error_file, index=False)
        print(f"\n[WARNING] Ada {len(failed_logs)} data yang gagal discrap. Log error disimpan ke: {error_file}")

    if all_api_data:
        api_data_df = pd.DataFrame(all_api_data)

        # --- Lengkapi schema dengan semua variabel kuesioner dari var_options.json ---
        var_opts_file = os.path.join(dir_path, "var_options.json")
        if os.path.exists(var_opts_file):
            with open(var_opts_file, "r", encoding="utf-8") as vf:
                var_opts = json.load(vf)
            # Tambahkan kolom yang belum ada sebagai NaN (agar skema lengkap)
            # Lewati variabel CSS/HTML container (labelnya panjang dan mengandung '{' atau '<')
            skip_css = {'<', '{', '#', 'SE2026'}
            for var_key in var_opts.keys():
                label = var_opts[var_key].get("question", "")
                if any(c in label for c in skip_css):
                    continue
                ans_col = f"ans_{var_key}"
                pre_col = f"pre_{var_key}"
                if ans_col not in api_data_df.columns:
                    api_data_df[ans_col] = None
                if pre_col not in api_data_df.columns:
                    api_data_df[pre_col] = None
            print(f"Schema dilengkapi: {len(api_data_df.columns)} kolom total.")

        output_file = os.path.join(dir_path, f"{prefix}_{timestamp}.csv")
        print(f"\nMenyimpan ke file CSV ({output_file})...")
        try:
            api_data_df.to_parquet(output_file.replace('.csv', '.parquet'), index=False)
            api_data_df.to_csv(output_file, index=False)
            print(f"Data BERHASIL disimpan! Total baris: {len(api_data_df)}, Kolom: {len(api_data_df.columns)}")
            return output_file
        except Exception as e:
            print(f"\n[ERROR] Terjadi kesalahan saat menyimpan file: {e}")
    else:
        print("\nTidak ada detail informasi yang didapatkan.")
        return None


# =========================================================================
# ENRICHMENT LAYER — Untuk membuat output GUI-ready
# =========================================================================

def _clean_html_label(label):
    """Bersihkan CSS/HTML dari label pertanyaan agar readable."""
    if not isinstance(label, str):
        return ''
    s = re.sub(r'<style.*?</style>', '', label, flags=re.DOTALL)
    s = re.sub(r'<script.*?</script>', '', s, flags=re.DOTALL)
    s = re.sub(r'<[^>]+>', '', s)
    s = html_module.unescape(s)
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.DOTALL)  # Hapus CSS comments
    s = re.sub(r'\{[^}]*\}', '', s)  # Hapus CSS rules
    s = re.sub(r'#\w+\s*\{[^}]*\}', '', s, flags=re.DOTALL)  # Hapus CSS selectors
    s = re.sub(r'\s+', ' ', s).strip()
    # Jika setelah dibersihkan masih sangat pendek atau kosong, return as-is
    return s if len(s) > 2 else ''


def _walk_template_for_blocks(node, mapping, current_block=''):
    """Rekursif traverse template.json untuk membangun mapping var → nama blok."""
    if isinstance(node, list):
        for item in node:
            _walk_template_for_blocks(item, mapping, current_block)
        return
    if not isinstance(node, dict):
        return
    ntype = node.get('type', '')
    label = _clean_html_label(node.get('label', ''))
    key = node.get('dataKey', '')
    if ntype == 1:  # type 1 = BLOK/PANEL
        current_block = label
    if key:
        mapping[key] = current_block
    for child_key in ['components', 'columns', 'rows']:
        if child_key in node:
            _walk_template_for_blocks(node[child_key], mapping, current_block)


def build_gui_mapping():
    """
    Bangun mapping lengkap variabel → {question, options, block, type_str}
    dari semua sumber yang tersedia (template.json, Kamus_Bridging.json, var_options.json).
    
    Returns: dict dengan format:
    {
        "usaha_kos": {
            "question": "Apakah memiliki usaha penyewaan lahan...?",
            "type_str": "Pilihan Radio",
            "options": [{"label": "1. Ya", "value": "1"}, ...],
            "block": "KETERANGAN KELUARGA DAN USAHA",
            "label_map": {"1": "1. Ya", "2": "2. Tidak"}
        },
        ...
    }
    """
    gui_map = {}
    
    # 1. Load Kamus_Bridging.json (sumber utama: question + options + type_str)
    bridge_file = os.path.join(dir_path, "Kamus_Bridging.json")
    if os.path.exists(bridge_file):
        with open(bridge_file, "r", encoding="utf-8") as f:
            bridge = json.load(f)
        for var_key, info in bridge.items():
            question_raw = info.get("question", "")
            question_clean = _clean_html_label(question_raw) if question_raw else var_key
            options = info.get("options", [])
            label_map = {}
            for opt in options:
                if isinstance(opt, dict) and "value" in opt and "label" in opt:
                    label_map[str(opt["value"])] = str(opt["label"])
            gui_map[var_key] = {
                "question": question_clean if question_clean else var_key,
                "type_str": info.get("type_str", ""),
                "options": options,
                "block": "",
                "label_map": label_map
            }
    
    # 2. Enrichkan/fallback dari var_options.json
    var_opts_file = os.path.join(dir_path, "var_options.json")
    if os.path.exists(var_opts_file):
        with open(var_opts_file, "r", encoding="utf-8") as f:
            var_opts = json.load(f)
        for var_key, info in var_opts.items():
            if var_key not in gui_map:
                question_raw = info.get("question", "")
                question_clean = _clean_html_label(question_raw) if question_raw else var_key
                options = info.get("options", [])
                label_map = {}
                for opt in options:
                    if isinstance(opt, dict) and "value" in opt and "label" in opt:
                        label_map[str(opt["value"])] = str(opt["label"])
                gui_map[var_key] = {
                    "question": question_clean if question_clean else var_key,
                    "type_str": "",
                    "options": options,
                    "block": "",
                    "label_map": label_map
                }
            else:
                # Jika question di bridge kosong, fallback ke var_options
                if not gui_map[var_key]["question"] or gui_map[var_key]["question"] == var_key:
                    q = _clean_html_label(info.get("question", ""))
                    if q:
                        gui_map[var_key]["question"] = q
                # Jika options di bridge kosong tapi var_options punya, ambil
                if not gui_map[var_key]["options"] and info.get("options"):
                    gui_map[var_key]["options"] = info["options"]
                    for opt in info["options"]:
                        if isinstance(opt, dict) and "value" in opt and "label" in opt:
                            gui_map[var_key]["label_map"][str(opt["value"])] = str(opt["label"])
    
    # 3. Tambahkan nama blok dari template.json
    template_file = os.path.join(dir_path, "template.json")
    if os.path.exists(template_file):
        with open(template_file, "r", encoding="utf-8") as f:
            template = json.load(f)
        block_mapping = {}
        _walk_template_for_blocks(template.get("components", []), block_mapping)
        for var_key in gui_map:
            if var_key in block_mapping:
                gui_map[var_key]["block"] = block_mapping[var_key]
    
    return gui_map


def enrich_detail_output(df, gui_map=None):
    """
    Memperkaya DataFrame output detail dengan kolom tambahan untuk GUI:
    - Untuk setiap kolom ans_* atau pre_*, tambahkan:
      - *_question: Pertanyaan kuesioner asli
      - *_block: Nama blok/section
      - *_label: Label jawaban yang readable (jika ada mapping)
    
    Args:
        df: DataFrame output dari scraping detail
        gui_map: dict mapping dari build_gui_mapping(). Jika None, akan di-build.
    
    Returns:
        DataFrame yang sudah di-enrich
    """
    if gui_map is None:
        gui_map = build_gui_mapping()
    
    if not gui_map:
        print("[WARNING] Tidak ada data mapping untuk enrichment. Output tidak di-enrich.")
        return df
    
    enriched_cols = {}
    
    for col in df.columns:
        # Hanya proses kolom ans_* dan pre_*
        if not (col.startswith("ans_") or col.startswith("pre_")):
            continue
        
        # Ekstrak nama variabel dari kolom (hapus prefix ans_/pre_ dan suffix #N/_raw)
        var_name = col
        for pfx in ["ans_", "pre_"]:
            if var_name.startswith(pfx):
                var_name = var_name[len(pfx):]
                break
        
        # Skip kolom _raw, _count, _question, _block, _label (turunan)
        if var_name.endswith("_raw") or var_name.endswith("_count"):
            continue
        if var_name.endswith("_question") or var_name.endswith("_block") or var_name.endswith("_label"):
            continue
        
        # Hapus roster index (#1, #2, ...)
        base_var = re.sub(r'#\d+$', '', var_name)
        
        if base_var in gui_map:
            info = gui_map[base_var]
            
            # Tambahkan kolom pertanyaan
            q_col = f"{col}_question"
            if q_col not in df.columns:
                enriched_cols[q_col] = info["question"]
            
            # Tambahkan kolom blok
            b_col = f"{col}_block"
            if b_col not in df.columns and info["block"]:
                enriched_cols[b_col] = info["block"]
            
            # Tambahkan kolom label jawaban (resolve value → label)
            if info["label_map"]:
                l_col = f"{col}_label"
                if l_col not in df.columns:
                    # Resolve setiap nilai di kolom ke label readable-nya
                    enriched_cols[l_col] = df[col].apply(
                        lambda v, lm=info["label_map"]: lm.get(str(v).strip(), str(v)) if pd.notna(v) and str(v).strip() else ""
                    )
    
    # Tambahkan semua kolom enrichment sekaligus menggunakan pd.concat untuk mencegah fragmentasi memori
    if enriched_cols:
        # Konversi skalar menjadi list agar bisa dibuat dataframe
        for k, v in enriched_cols.items():
            if isinstance(v, str):
                enriched_cols[k] = [v] * len(df)
        
        new_cols_df = pd.DataFrame(enriched_cols, index=df.index)
        df = pd.concat([df, new_cols_df], axis=1)
        print(f"[ENRICHMENT] Berhasil menambahkan {len(enriched_cols)} kolom enrichment (question/block/label).")
    
    return df


def save_gui_mapping_json(output_path=None):
    """
    Simpan GUI mapping ke file JSON untuk referensi di GUI app.
    Berguna agar app.py bisa langsung load mapping tanpa rebuild.
    """
    if output_path is None:
        output_path = os.path.join(dir_path, "gui_mapping.json")
    
    gui_map = build_gui_mapping()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(gui_map, f, indent=2, ensure_ascii=False)
    
    print(f"GUI mapping disimpan ke {output_path} ({len(gui_map)} variabel)")
    return output_path
