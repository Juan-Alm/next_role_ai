from playwright.sync_api import sync_playwright

SEARCH_KEYWORD = "data analyst"
LOCATION = "Canterbury"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    # Go to SEEK and search
    page.goto(f"https://nz.seek.com/{SEARCH_KEYWORD.replace(' ', '-')}-jobs/in-{LOCATION}")
    page.wait_for_timeout(3000)

    # Take a screenshot so you can inspect what loaded
    page.screenshot(path="seek_results.png")
    print("Screenshot saved.")
    browser.close()