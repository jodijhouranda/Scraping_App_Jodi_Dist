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
        
    print("Membuka browser dan merekam jalur API...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()
        
        api_responses = {}
        
        async def handle_response(response):
            # Hanya tangkap request yang merupakan API (mengandung kata 'api' atau JSON)
            if "api" in response.url.lower() or "json" in response.url.lower():
                try:
                    # Ambil JSON jika ada
                    if response.ok:
                        text = await response.text()
                        try:
                            json_data = json.loads(text)
                            api_responses[response.url] = json_data
                        except:
                            api_responses[response.url] = text[:1000] # Jika bukan JSON
                except Exception:
                    pass
                    
        page.on("response", handle_response)
        
        target_url = "https://fasih-sm.bps.go.id/app/assignment/fd68e454-ba45-4b85-8205-f3bf777ded24/b00cf5df-c3f6-42d6-96a0-3b5aa6a6fcf9"
        print(f"Membuka URL: {target_url}")
        try:
            await page.goto(target_url, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(5) # Tunggu ekstra 5 detik agar semua API selesai loading
        except Exception as e:
            print(f"Error saat loading: {e}")
            
        output_file = os.path.join(dir_path, "api_network_log.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(api_responses, f, indent=2)
            
        print(f"BERHASIL! {len(api_responses)} API berhasil direkam ke {output_file}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
