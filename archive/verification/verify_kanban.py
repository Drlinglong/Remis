import time
from playwright.sync_api import sync_playwright, expect

def verify_kanban_board(page):
    time.sleep(5)
    print("Navigating to root...")
    page.goto("http://localhost:5173/", timeout=10000)

    print("Checking for page title...")
    # The title in ProjectManagement.jsx is localized: t('page_title_project_management')
    # in zh: "项目管理"
    # in en: "Project Management"
    # We should check for either or loosely.
    # The mock ProjectManagement.jsx has: <Title ...>{t('page_title_project_management')}</Title>

    try:
        expect(page.get_by_role("heading", name="项目管理")).to_be_visible(timeout=5000)
        print("Title found.")
    except:
        print("Title '项目管理' not found. Checking 'Project Management'...")
        expect(page.get_by_role("heading", name="Project Management")).to_be_visible(timeout=5000)
        print("Title found (English).")

    print("Checking for 'New/Import' button...")
    expect(page.get_by_text("新建/导入")).to_be_visible()

    print("Attempting to open Project Select...")
    # Mantine Select structure usually involves an input with a specific class or attribute
    # Since we provided a placeholder, let's try to find it in the DOM even if not an input placeholder
    # Print the HTML of the select container if we fail
    try:
        page.get_by_placeholder("选择一个项目").click(timeout=2000)
    except:
        print("Standard placeholder click failed. Searching text...")
        page.get_by_text("选择一个项目").click()

    print("Selecting project...")
    page.get_by_role("option", name="甲MOD v1.2").click()

    print("Project selected. Checking for tabs...")
    expect(page.get_by_text("任务看板")).to_be_visible()

    # It should switch to taskboard automatically or be default?
    # In code: <Tabs defaultValue="taskboard">. So yes.

    print("Checking for Kanban columns...")
    expect(page.get_by_text("待办")).to_be_visible(timeout=5000)

    print("SUCCESS: Kanban board is visible.")
    page.screenshot(path="verification/kanban_success.png", full_page=True)


if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        try:
            verify_kanban_board(page)
        except Exception as e:
            print(f"Verification failed: {e}")
            print("Dumping page content for debugging:")
            print(page.content())
            page.screenshot(path="verification/failure_debug.png")
        finally:
            browser.close()
