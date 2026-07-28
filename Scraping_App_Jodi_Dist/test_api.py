import asyncio
import json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state='d:/Kantor/Code/SEJodi/state.json')
        
        xsrf = ''
        for ck in await context.cookies():
            if ck['name'] == 'XSRF-TOKEN':
                xsrf = ck['value']
                break
                
        r = await context.request.get(
            'https://fasih-sm.bps.go.id/app/api/assignment-general/api/assignments/get-principal-values-by-smallest-code/fd68e454-ba45-4b85-8205-f3bf777ded24/6102040014002600',
            headers={'X-XSRF-TOKEN': xsrf, 'Accept': 'application/json'}
        )
        try:
            data = await r.json()
            with open('resp.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            print("Saved to resp.json")
        except Exception as e:
            print("Error parsing json:", e)
            with open('resp.txt', 'w', encoding='utf-8') as f:
                f.write(await r.text())
        
        await browser.close()

asyncio.run(main())
