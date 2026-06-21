from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # headless=False so you can SEE it
    page = browser.new_page()
    page.goto("https://nz.seek.com/")
    page.wait_for_timeout(3000)  # wait 3 seconds so you can look at it
    browser.close()