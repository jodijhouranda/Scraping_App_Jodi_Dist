import asyncio
import json
import os
from playwright.async_api import async_playwright

async def main():
    state_file = 'd:/Kantor/Code/SEJodi/state.json'
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(storage_state=state_file)
        
        xsrf = ''
        for ck in await context.cookies():
            if ck['name'] == 'XSRF-TOKEN':
                xsrf = ck['value']
                
        r = await context.request.get(
            'https://fasih-sm.bps.go.id/app/api/assignment-general/api/assignment/get-by-assignment-id?assignmentId=b00cf5df-c3f6-42d6-96a0-3b5aa6a6fcf9',
            headers={'X-XSRF-TOKEN': xsrf, 'Accept': 'application/json'}
        )
        data = await r.json()
        with open('detail_sample.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        print("Saved detail_sample.json")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
