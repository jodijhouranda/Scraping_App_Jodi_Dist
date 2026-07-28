import json
import os
import asyncio
from api_client import fetch_json
from tqdm.asyncio import tqdm as async_tqdm

dir_path = os.path.dirname(os.path.abspath(__file__))
config_file = os.path.join(dir_path, "config.json")
region_file = os.path.join(dir_path, "region_mapping.json")

def load_config():
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            return json.load(f)
    return {}

def save_config(cfg):
    with open(config_file, "w") as f:
        json.dump(cfg, f, indent=4)

async def fetch_region_hierarchy(page, xsrf_token, group_id, sel_prov):
    print(f"\n>> Mulai mengunduh hirarki wilayah (Kabupaten -> Kecamatan -> Desa -> SLS) untuk {sel_prov['name']}...")
    sem = asyncio.Semaphore(15)
    
    async def fetch_level(url_suffix, name):
        async with sem:
            url = f"/app/api/region/api/v1/region/{url_suffix}"
            res = await fetch_json(page, url, xsrf_token=xsrf_token)
            if res and "data" in res:
                return res["data"]
            return []

    # 1. Kab
    kabs = await fetch_level(f"level2?groupId={group_id}&level1FullCode={sel_prov['fullCode']}", "Kabupaten")
    if not kabs:
        print("Gagal mengambil Kabupaten.")
        return
        
    region_tree = {}
    
    # 2. Kec
    tasks = []
    for kab in kabs:
        region_tree[kab["fullCode"]] = {"id": kab["id"], "name": kab["name"], "kecamatan": {}}
        tasks.append(fetch_level(f"level3?groupId={group_id}&level2FullCode={kab['fullCode']}", f"Kecamatan di {kab['name']}"))
    
    kecs_results = await async_tqdm.gather(*tasks, desc="Mengambil Kecamatan")
    all_kecs = []
    for kab, kecs in zip(kabs, kecs_results):
        for kec in kecs:
            region_tree[kab["fullCode"]]["kecamatan"][kec["fullCode"]] = {"id": kec["id"], "name": kec["name"], "desa": {}}
            all_kecs.append((kab["fullCode"], kec))
            
    # 3. Desa
    tasks = []
    for kab_code, kec in all_kecs:
        tasks.append(fetch_level(f"level4?groupId={group_id}&level3FullCode={kec['fullCode']}", f"Desa di {kec['name']}"))
    
    desas_results = await async_tqdm.gather(*tasks, desc="Mengambil Desa")
    all_desas = []
    for (kab_code, kec), desas in zip(all_kecs, desas_results):
        for desa in desas:
            region_tree[kab_code]["kecamatan"][kec["fullCode"]]["desa"][desa["fullCode"]] = {"id": desa["id"], "name": desa["name"], "sls": {}}
            all_desas.append((kab_code, kec["fullCode"], desa))
            
    # 4. SLS
    tasks = []
    for kab_code, kec_code, desa in all_desas:
        tasks.append(fetch_level(f"level5?groupId={group_id}&level4FullCode={desa['fullCode']}", f"SLS di {desa['name']}"))
        
    sls_results = await async_tqdm.gather(*tasks, desc="Mengambil SLS")
    total_sls = 0
    all_slses = []
    for (kab_code, kec_code, desa), slses in zip(all_desas, sls_results):
        for sls in slses:
            region_tree[kab_code]["kecamatan"][kec_code]["desa"][desa["fullCode"]]["sls"][sls["fullCode"]] = {"id": sls["id"], "name": sls["name"], "sub_sls": {}}
            all_slses.append((kab_code, kec_code, desa["fullCode"], sls))
            total_sls += 1
            
    # 5. Sub SLS
    tasks = []
    for kab_code, kec_code, desa_code, sls in all_slses:
        tasks.append(fetch_level(f"level6?groupId={group_id}&level5FullCode={sls['fullCode']}", f"Sub SLS di {sls['name']}"))
        
    sub_sls_results = await async_tqdm.gather(*tasks, desc="Mengambil Sub SLS")
    total_sub_sls = 0
    for (kab_code, kec_code, desa_code, sls), sub_slses in zip(all_slses, sub_sls_results):
        for sub_sls in sub_slses:
            region_tree[kab_code]["kecamatan"][kec_code]["desa"][desa_code]["sls"][sls["fullCode"]]["sub_sls"][sub_sls["fullCode"]] = {"id": sub_sls["id"], "name": sub_sls["name"]}
            total_sub_sls += 1
            
    with open(region_file, "w", encoding="utf-8") as f:
        json.dump(region_tree, f, indent=4)
        
    print(f"\nBerhasil menyimpan {total_sls} SLS dan {total_sub_sls} Sub SLS ke region_mapping.json.")


async def setup_survey(page, xsrf_token):
    cfg = load_config()
    print(f"\n[Konfigurasi Saat Ini]")
    print(f"Survey Period ID : {cfg.get('survey_period_id', 'Belum Diatur')}")
    print(f"Group ID         : {cfg.get('group_id', 'Belum Diatur')}")
    print(f"Provinsi Target  : {cfg.get('prov_name', 'Belum Diatur')}")
    
    ubah = input("\nIngin mengubah/mengisi parameter survei? (y/n): ").strip().lower()
    if ubah == 'y' or not cfg.get('survey_period_id') or not cfg.get('group_id'):
        s_id = input("Masukkan Survey Period ID baru (Kosongi jika tidak diubah): ").strip()
        g_id = input("Masukkan Group ID baru (Kosongi jika tidak diubah): ").strip()
        if s_id: cfg["survey_period_id"] = s_id
        if g_id: cfg["group_id"] = g_id
        save_config(cfg)
        print("Konfigurasi survei berhasil disimpan.")
        
    if not cfg.get("group_id"):
        print("Group ID belum diatur. Pemilihan Provinsi tidak bisa dilanjutkan.")
        return

    fetch_prov = input("Tarik ulang daftar Provinsi dan Mapping Wilayah? (y/n): ").strip().lower()
    if fetch_prov == 'y':
        url = f"/app/api/region/api/v1/region/level1?groupId={cfg['group_id']}"
        res = await fetch_json(page, url, xsrf_token=xsrf_token)
        if not res or "data" not in res:
            print("Gagal mengambil daftar Provinsi. Pastikan Group ID benar dan Anda sudah login.")
            return
            
        provs = res["data"]
        print("\n[Daftar Provinsi]")
        for idx, p in enumerate(provs):
            print(f"{idx+1}. [{p['fullCode']}] {p['name']}")
            
        pil_prov = input("\nPilih nomor Provinsi yang akan di-scrape: ").strip()
        try:
            p_idx = int(pil_prov) - 1
            sel_prov = provs[p_idx]
            cfg["region1Id"] = sel_prov["id"]
            cfg["prov_code"] = sel_prov["fullCode"]
            cfg["prov_name"] = sel_prov["name"]
            save_config(cfg)
            print(f"Provinsi {sel_prov['name']} terpilih.")
            
            await fetch_region_hierarchy(page, xsrf_token, cfg['group_id'], sel_prov)
        except Exception:
            print("Pilihan tidak valid.")
