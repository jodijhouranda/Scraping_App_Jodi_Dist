import asyncio
from playwright.async_api import async_playwright

async def run():
    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True)
    page = await browser.new_page()
    try:
        await page.goto('https://fasih-sm.bps.go.id/')
        await page.wait_for_timeout(5000)
        print("URL:", page.url)
        content = await page.content()
        print("Content preview:", content[:200])
        print("sso in url:", "sso" in page.url.lower())
        print("login in url:", "login" in page.url.lower())
        print("BOT- in content:", "BOT-" in content)
    except Exception as e:
        print('Error:', e)
    finally:
        await browser.close()
        await p.stop()

asyncio.run(run())
