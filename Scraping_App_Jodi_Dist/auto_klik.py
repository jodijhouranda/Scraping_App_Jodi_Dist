import asyncio
import json
import os
from playwright.async_api import async_playwright

dir_path = os.path.dirname(os.path.abspath(__file__))
state_file = os.path.join(os.path.dirname(dir_path), "state.json")

async def main():
    if not os.path.exists(state_file):
        print("Sesi state.json tidak ditemukan. Harap pastikan sudah login.")
        return
        
    print("Membuka browser untuk mensimulasikan klik...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()
        
        api_responses = {}
        
        async def handle_response(response):
            url = response.url
            if "api" in url.lower() and response.request.method != "OPTIONS":
                try:
                    if response.ok:
                        text = await response.text()
                        try:
                            api_responses[url] = json.loads(text)
                        except:
                            api_responses[url] = text[:500]
                except:
                    pass
                    
        page.on("response", handle_response)
        
        target_url = "https://fasih-sm.bps.go.id/app/assignment/fd68e454-ba45-4b85-8205-f3bf777ded24/b00cf5df-c3f6-42d6-96a0-3b5aa6a6fcf9"
        print(f"Membuka URL: {target_url}")
        await page.goto(target_url, wait_until='domcontentloaded')
        await asyncio.sleep(4)
        
        # Mencoba mencari tombol "Detail", "Edit", atau baris tabel untuk di-klik
        print("Mencoba mengklik elemen data di halaman...")
        try:
            # Cari tombol aksi (biasanya ada ikon mata/edit) atau baris data
            action_buttons = await page.locator("button, a, tr").all()
            clicked = False
            for btn in action_buttons:
                text = await btn.inner_text()
                # Jika tombol mengandung teks relevan atau baris tabel
                if "detail" in text.lower() or "buka" in text.lower() or "view" in text.lower():
                    await btn.click()
                    clicked = True
                    print(f"Berhasil mengklik elemen dengan teks: {text.strip()}")
                    break
            
            if not clicked:
                # Coba klik baris pertama pada tabel jika ada
                row = page.locator("table tbody tr").first
                if await row.is_visible():
                    await row.click()
                    print("Berhasil mengklik baris pertama pada tabel.")
        except Exception as e:
            print(f"Tidak dapat mengklik elemen: {e}")
            
        print("Menunggu API memuat data...")
        await asyncio.sleep(5)
        
        # Menyimpan hasil log API yang terpanggil setelah diklik
        output_file = os.path.join(dir_path, "klik_api_log.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(api_responses, f, indent=2)
            
        print(f"Selesai! {len(api_responses)} API berhasil direkam ke {output_file}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
