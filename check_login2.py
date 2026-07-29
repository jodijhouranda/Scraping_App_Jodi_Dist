import asyncio
import os
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def run():
    p = await async_playwright().start()
    chrome_path = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
    browser = await p.chromium.launch(
        headless=True,
        executable_path=chrome_path if os.path.exists(chrome_path) else None,
        args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
    )
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
    )
    page = await context.new_page()
    await Stealth().apply_stealth_async(page)
    try:
        await page.goto('https://fasih-sm.bps.go.id/')
        await page.wait_for_timeout(10000)  # Wait longer for F5 challenge
        print('URL:', page.url)
        content = await page.content()
        print('sso in url:', 'sso' in page.url.lower())
        print('login in url:', 'login' in page.url.lower())
        print('title:', await page.title())
        print('challenge in content:', 'bobcmn' in content)
    except Exception as e:
        print('Error:', e)
    finally:
        await browser.close()
        await p.stop()

asyncio.run(run())
