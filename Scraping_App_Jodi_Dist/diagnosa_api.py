"""
diagnosa_api.py — Test API dengan SLS dari template yang aktual
"""
import asyncio
import json
import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

dir_path = os.path.dirname(os.path.abspath(__file__))
state_file = os.path.join(os.path.dirname(dir_path), "state.json")
config_file = os.path.join(dir_path, "config.json")
region_file = os.path.join(dir_path, "region_mapping.json")
template_file = os.path.join(dir_path, "Template Jodi.xlsx")

import pandas as pd

with open(config_file) as f:
    cfg = json.load(f)

with open(region_file) as f:
    region_data = json.load(f)

# ── Ambil SLS dari TEMPLATE (bukan dari region_mapping langsung) ──
df_tpl = pd.read_excel(template_file, dtype=str)
df_tpl.columns = df_tpl.columns.str.strip()
target_codes = set(df_tpl['idsls'].dropna().str.replace(r'\.0$', '', regex=True).str.strip().tolist())
print(f"Total SLS di template: {len(target_codes)}")

# Cari max 3 SLS dari region_mapping yang cocok dengan template
test_sls_list = []
for kab_code, kab_info in region_data.items():
    kab_id = kab_info.get("id")
    for kec_code, kec_info in kab_info.get("kecamatan", {}).items():
        kec_id = kec_info.get("id")
        for desa_code, desa_info in kec_info.get("desa", {}).items():
            desa_id = desa_info.get("id")
            for sls_code, sls_info in desa_info.get("sls", {}).items():
                if sls_code in target_codes:
                    test_sls_list.append({
                        "kab_id": kab_id, "kec_id": kec_id,
                        "desa_id": desa_id, "sls_id": sls_info.get("id"),
                        "code": sls_code
                    })
                    if len(test_sls_list) >= 3:
                        break
            if len(test_sls_list) >= 3: break
        if len(test_sls_list) >= 3: break
    if len(test_sls_list) >= 3: break

if not test_sls_list:
    print("ERROR: Tidak ada SLS template yang cocok dengan region_mapping!")
    exit(1)

print(f"Test SLS (dari template): {[s['code'] for s in test_sls_list]}")

def make_payload(sls, cfg):
    return {
        "start": 0, "length": 100,
        "assignmentExtraParam": {
            "surveyPeriodId": cfg["survey_period_id"],
            "assignmentErrorStatusType": -1,
            "region1Id": cfg["region1Id"],
            "region2Id": sls["kab_id"],
            "region3Id": sls["kec_id"],
            "region4Id": sls["desa_id"],
            "region5Id": sls["sls_id"]
        },
        "filterTargetType": "ALL",
        "surveyPeriodId": cfg["survey_period_id"],
        "region1Id": cfg["region1Id"],
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

async def do_request(context, token, sls, label):
    url = "https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode"
    payload = make_payload(sls, cfg)
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/plain, */*',
        'X-XSRF-TOKEN': token,
        'X-Requested-With': 'XMLHttpRequest',
    }
    try:
        resp = await context.request.post(url, headers=headers, data=json.dumps(payload))
        body = await resp.text()
        is_html = body.strip().startswith("<!DOCTYPE") or body.strip().startswith("<html")
        if is_html:
            print(f"[{label}] {sls['code']} => HTTP {resp.status} [HTML/WAF - bukan JSON]")
        else:
            try:
                parsed = json.loads(body)
                total = parsed.get("totalHit", "?")
                rows = len(parsed.get("searchData", []))
                print(f"[{label}] {sls['code']} => HTTP {resp.status} | totalHit={total} | searchData rows={rows}")
                if rows > 0:
                    print(f"         Sample: {json.dumps(parsed['searchData'][0])[:200]}")
            except:
                print(f"[{label}] {sls['code']} => HTTP {resp.status} | Body: {body[:200]}")
    except Exception as e:
        print(f"[{label}] {sls['code']} => ERROR: {e}")

async def test():
    p = await async_playwright().start()
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    browser = await p.chromium.launch(
        headless=False,
        executable_path=chrome_path if os.path.exists(chrome_path) else None,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
    )
    ctx_opts = dict(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
        locale="id-ID", timezone_id="Asia/Jakarta",
        java_script_enabled=True, accept_downloads=True,
    )

    if os.path.exists(state_file):
        context = await browser.new_context(storage_state=state_file, **ctx_opts)
    else:
        context = await browser.new_context(**ctx_opts)

    page = await context.new_page()
    await Stealth().apply_stealth_async(page)

    # ── STEP 1: Buka homepage ──
    print("\n[STEP 1] Buka homepage...")
    await page.goto("https://fasih-sm.bps.go.id/")
    await page.wait_for_timeout(3000)

    page_content = await page.content()
    if "login" in page.url.lower() or "sso" in page.url.lower() or "BOT-" in page_content:
        print("Perlu login manual. Login lalu klik Resume di Playwright Inspector.")
        await page.pause()
        await context.storage_state(path=state_file)

    async def get_token():
        for c in await context.cookies():
            if c["name"] == "XSRF-TOKEN":
                return c["value"]
        return ""

    token = await get_token()
    print(f"Token: {token[:20]}... ({len(token)} char)")
    
    if not token:
        print("Token kosong! Login ulang...")
        await page.pause()
        await context.storage_state(path=state_file)
        token = await get_token()
        print(f"Token setelah login: {token[:20]}...")

    # ── TEST A: API langsung setelah homepage ──
    print("\n--- Test A: API setelah homepage ---")
    for sls in test_sls_list:
        await do_request(context, token, sls, "A")

    # ── STEP 2: Navigate ke halaman analytics ──
    print("\n[STEP 2] Navigate ke halaman analytics FASIH...")
    try:
        await page.goto("https://fasih-sm.bps.go.id/app/analytic/assignment", 
                       wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(5000)
        print(f"  URL: {page.url}")
    except Exception as e:
        print(f"  Gagal navigate analytics: {e}")

    token2 = await get_token()
    print(f"Token setelah navigate: {token2[:20]}... ({len(token2)} char)")
    if not token2:
        token2 = token

    # ── TEST B: API setelah navigate ke analytics ──
    print("\n--- Test B: API setelah navigate ke halaman analytics ---")
    for sls in test_sls_list:
        await do_request(context, token2, sls, "B")

    await browser.close()
    await p.stop()
    print("\nDiagnosa selesai.")

asyncio.run(test())
