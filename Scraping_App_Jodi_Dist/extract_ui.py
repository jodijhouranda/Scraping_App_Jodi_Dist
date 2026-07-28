import asyncio
import json
import re
from playwright.async_api import async_playwright

async def main():
    state_file = 'd:/Kantor/Code/SEJodi/state.json'
    url = "https://fasih-sm.bps.go.id/app/assignment/fd68e454-ba45-4b85-8205-f3bf777ded24/b00cf5df-c3f6-42d6-96a0-3b5aa6a6fcf9"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state=state_file,
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        print("Membuka halaman...")
        await page.goto(url, wait_until='domcontentloaded')
        await page.wait_for_timeout(8000)  # Tunggu SPA render
        
        # Ambil screenshot awal
        await page.screenshot(path='fasih_awal.png', full_page=True)
        print("Screenshot awal diambil")
        
        # Cek apakah ada sidebar / navigasi blok
        html_content = await page.content()
        with open('page_html.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"HTML saved: {len(html_content)} chars")
        
        # Cari semua sidebar items / tab / navigasi
        sidebar_items = await page.query_selector_all('a.nav-link, .sidebar-item, .menu-item, li.nav-item a, .list-group-item')
        print(f"Sidebar items ditemukan: {len(sidebar_items)}")
        
        if len(sidebar_items) == 0:
            # Coba cari dengan selector lain
            sidebar_items = await page.query_selector_all('[class*="nav"] a, [class*="menu"] a, [class*="sidebar"] a, [class*="tab"] a')
            print(f"Sidebar items (alt): {len(sidebar_items)}")
        
        if len(sidebar_items) == 0:
            # Coba cari semua link/button yang kelihatan
            sidebar_items = await page.query_selector_all('button, a[href]')
            texts = []
            for item in sidebar_items[:30]:
                txt = await item.inner_text()
                texts.append(txt.strip()[:50])
            print(f"All buttons/links: {texts}")
        
        all_sections = []
        
        # Coba klik sidebar items satu per satu dan ambil konten
        nav_links = await page.query_selector_all('a.nav-link')
        if len(nav_links) == 0:
            nav_links = await page.query_selector_all('.mat-tab-label, [role="tab"]')
        
        print(f"Nav links: {len(nav_links)}")
        
        for i, link in enumerate(nav_links):
            try:
                link_text = await link.inner_text()
                link_text = link_text.strip()
                print(f"\n--- Klik [{i}]: {link_text} ---")
                await link.click()
                await page.wait_for_timeout(2000)
                
                # Ambil screenshot per section
                await page.screenshot(path=f'fasih_section_{i}.png', full_page=True)
                
                # Ekstrak semua visible form fields di area konten
                fields = await page.evaluate("""
                    () => {
                        let results = [];
                        // Cari semua label + input pairs
                        let labels = document.querySelectorAll('label');
                        labels.forEach(lbl => {
                            let text = lbl.innerText.trim();
                            let forAttr = lbl.getAttribute('for');
                            let parent = lbl.closest('.form-group, .formio-component, [class*="field"]');
                            let input = null;
                            if (parent) {
                                input = parent.querySelector('input, select, textarea');
                            }
                            if (!input && forAttr) {
                                input = document.getElementById(forAttr);
                            }
                            let inputName = input ? (input.getAttribute('name') || input.getAttribute('id') || '') : '';
                            let inputValue = input ? (input.value || '') : '';
                            if (text && text.length > 0) {
                                results.push({
                                    label: text.substring(0, 200),
                                    name: inputName,
                                    value: inputValue.substring(0, 100),
                                    visible: lbl.offsetParent !== null
                                });
                            }
                        });
                        return results;
                    }
                """)
                
                visible_fields = [f for f in fields if f.get('visible')]
                print(f"  Fields visible: {len(visible_fields)}")
                
                all_sections.append({
                    'section': link_text,
                    'index': i,
                    'fields': visible_fields
                })
                
            except Exception as e:
                print(f"  Error: {e}")
        
        # Simpan hasil
        with open('kuesioner_mapping_visual.json', 'w', encoding='utf-8') as f:
            json.dump(all_sections, f, indent=2, ensure_ascii=False)
        
        print(f"\n=== TOTAL: {len(all_sections)} sections, {sum(len(s['fields']) for s in all_sections)} fields ===")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
