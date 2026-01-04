import time
from playwright.sync_api import sync_playwright

def verify_themes():
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()

        print("Navigating to Settings page (for full layout check)...")
        try:
            page.goto("http://localhost:5173/settings", timeout=60000)
            page.wait_for_selector("body", timeout=10000)
        except Exception as e:
            print(f"Failed to load page: {e}")
            browser.close()
            return

        print("Page loaded.")
        time.sleep(3)

        def get_computed_style(selector, property_name):
            value = page.evaluate(f"""() => {{
                const el = document.querySelector('{selector}');
                if (!el) return "ELEMENT_NOT_FOUND";
                return window.getComputedStyle(el).getPropertyValue('{property_name}');
            }}""")
            return value

        def set_theme(theme_name):
            print(f"Attempting to set theme to {theme_name}...")
            page.evaluate(f"localStorage.setItem('theme', '{theme_name}')")
            page.reload()
            time.sleep(3)

            # Check Sidebar Background (should be glass/transparent-ish)
            # We look for the sidebar container. Based on Mantine AppShell, usually 'nav' or specific class
            # But we applied styles to a Box inside AppSider, so we look for that specific sidebar class logic if possible
            # Or just check the nav element since we applied styles to the Box that *is* the navbar content

            # In AppSider.jsx, we return a Box. This box is inside AppShell.Navbar (if using that) or just placed in layout.
            # Wait, MainLayout puts AppSider directly in a flex Box. So it's just a div.
            # We can search by text content "Remis" or "R" which is in the sidebar header

            sidebar_bg = page.evaluate("""() => {
                // Find the element containing the logo text "Remis" or "R"
                const logo = Array.from(document.querySelectorAll('div')).find(el => el.textContent === 'Remis' || el.textContent === 'R');
                if (!logo) return "LOGO_NOT_FOUND";
                // The sidebar container is likely a parent of the logo
                // The logo is in a Stack, which is in the Box (sidebar)
                const sidebar = logo.closest('[class*="sidebarLeft"]');
                if (!sidebar) return "SIDEBAR_NOT_FOUND";
                return window.getComputedStyle(sidebar).backgroundColor;
            }""")
            print(f"Theme {theme_name} - Sidebar BG: {sidebar_bg}")

            page.screenshot(path=f"verification/layout_theme_{theme_name}.png")

        # Test main 3 themes
        themes = ['scifi', 'victorian', 'byzantine']

        for theme in themes:
            set_theme(theme)

        browser.close()

if __name__ == "__main__":
    verify_themes()
