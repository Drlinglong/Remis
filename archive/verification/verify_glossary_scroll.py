
import os
import time
from playwright.sync_api import sync_playwright, expect

def verify_glossary_scroll():
    with sync_playwright() as p:
        # Launch browser with specific locale to match app defaults if needed
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()

        try:
            print("Navigating to app...")
            # Wait for Vite to be ready (simple retry loop)
            for i in range(10):
                try:
                    page.goto("http://localhost:5173", timeout=5000)
                    break
                except:
                    time.sleep(2)

            print("Waiting for page load...")
            page.wait_for_load_state("networkidle")

            # Click Glossary Manager in sidebar
            print("Clicking Glossary Manager sidebar link...")
            # Note: Based on layout image, it's likely "Glossary Manager"
            page.get_by_role("link", name="Glossary Manager").click()

            # Wait for Glossary Manager content to load
            print("Waiting for Glossary Manager content...")
            # Wait for the 'Select a file' or table to appear
            # Using a locator for the table or a header
            expect(page.get_by_role("heading", name="Glossary Manager").first).to_be_visible()

            # Wait for tree to load (network request)
            page.wait_for_timeout(2000)

            # Select the first game in the dropdown if needed (it defaults to first)
            # Select a file from the tree to populate the table
            print("Selecting a file from the tree...")
            # We need to find a leaf node. The tree structure uses NavLinks.
            # Let's try to find the first file-like element.
            # Based on code: nodes.map... NavLink with IconFileText
            # We can look for a button/link that looks like a file.
            # Or just wait and see if there are files.

            # Take a screenshot of initial state
            page.screenshot(path="/home/jules/verification/glossary_manager_initial.png")

            # Find a file in the sidebar.
            # The tree items are NavLinks, which render as anchors <a> or buttons.
            # Let's click the first available file.
            # Assuming the tree is expanded or we can expand it.
            # The code says defaultOpened={true} for folders.

            # Try to click a file.
            # The file icon is IconFileText.
            # Let's just click the text of a known file if we can guess, or the first leaf.
            # We'll click the first element that is a file.
            # If no file is visible, we might need to select a game first.

            # Let's verify if there is a scroll area in the main panel.
            # The main panel scroll area contains the Table.
            # We need to verify if the scroll area has the correct styles.

            print("Verifying ScrollArea styles...")
            # The ScrollArea in the main panel wraps the table.
            # We can find the table and check its parent.
            table = page.locator("table")
            scroll_area_viewport = table.locator("..").locator("..")
            # Mantine ScrollArea structure: Root -> Viewport -> Container -> Content
            # Actually Mantine v7 ScrollArea: Root -> Viewport -> div -> content
            # The style {{ flex: 1, minHeight: 0 }} is on the Root.

            # Let's evaluate the CSS of the scroll area root.
            # We can target the closest .mantine-ScrollArea-root
            scroll_root = table.locator("xpath=ancestor::div[contains(@class, 'mantine-ScrollArea-root')]").first

            min_height = scroll_root.evaluate("el => getComputedStyle(el).minHeight")
            flex_grow = scroll_root.evaluate("el => getComputedStyle(el).flexGrow")

            print(f"ScrollArea Root min-height: {min_height}")
            print(f"ScrollArea Root flex-grow: {flex_grow}")

            if min_height == "0px":
                print("SUCCESS: min-height is 0px")
            else:
                print(f"FAILURE: min-height is {min_height}")

            # Verify Table CSS
            table_el = page.locator("table.mantine-Table-table").first # Mantine table class might vary, checking generic table
            # But we added a class `dataTable` from module.
            # We can't easily select by module class hash.
            # Just select 'table'

            table_min_height = page.locator("table").first.evaluate("el => getComputedStyle(el).minHeight")
            print(f"Table min-height: {table_min_height}")

            # Take final screenshot
            page.screenshot(path="/home/jules/verification/glossary_manager_fixed.png")

        except Exception as e:
            print(f"Error: {e}")
            page.screenshot(path="/home/jules/verification/error.png")
            raise e
        finally:
            browser.close()

if __name__ == "__main__":
    verify_glossary_scroll()
