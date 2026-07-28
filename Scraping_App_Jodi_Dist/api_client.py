import os
import json
import asyncio
from playwright.async_api import async_playwright

script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
state_file = os.path.join(script_dir, "state.json")

async def init_browser():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=False)
    try:
        context = await browser.new_context(storage_state=state_file)
    except Exception:
        print("Gagal memuat state.json. Silakan login terlebih dahulu menggunakan login_and_capture.py.")
        await browser.close()
        await p.stop()
        return None, None, None, None

    page = await context.new_page()
    print("Membuka halaman utama untuk inisialisasi sesi & bypass WAF...")
    await page.goto("https://fasih-sm.bps.go.id/")
    await asyncio.sleep(3)

    xsrf_token = ""
    for c in await context.cookies():
        if c["name"] == "XSRF-TOKEN":
            xsrf_token = c["value"]
            break

    return p, browser, page, xsrf_token

async def fetch_json(page, url, method='GET', payload=None, xsrf_token=""):
    full_url = f"https://fasih-sm.bps.go.id{url}" if url.startswith("/") else url
    headers = {
        'Accept': 'application/json',
        'X-XSRF-TOKEN': xsrf_token
    }
    for retry in range(3):
        try:
            if method == 'POST':
                headers['Content-Type'] = 'application/json'
                resp = await page.context.request.post(full_url, headers=headers, data=json.dumps(payload) if payload is not None else None)
            else:
                resp = await page.context.request.get(full_url, headers=headers)
                
            if resp.ok:
                return await resp.json()
            else:
                await asyncio.sleep(2)
        except Exception as e:
            await asyncio.sleep(2)
    return None
