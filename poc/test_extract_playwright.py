from playwright.sync_api import sync_playwright
import json

SEARCH_KEYWORD = "data-analyst"  # use hyphens as SEEK does in the URL
LOCATION = "Christchurch-Central-Canterbury"
DATE_RANGE = 3      # days
MAX_JOBS = 20

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    url = f"https://nz.seek.com/{SEARCH_KEYWORD}-jobs/in-{LOCATION}?daterange={DATE_RANGE}"
    print(f"Searching: {url}")

    page.goto(url)
    page.wait_for_timeout(4000)

    page.screenshot(path="seek_results.png")

    jobs = []
    job_cards = page.query_selector_all('article[data-testid="job-card"]')

    for card in job_cards[:MAX_JOBS]:  # slice to limit
        title_el = card.query_selector('[data-automation="jobTitle"]')
        company_el = card.query_selector('[data-automation="jobCompany"]')
        location_el = card.query_selector('[data-automation="jobLocation"]')
        link_el = card.query_selector('a[data-automation="jobTitle"]')

        jobs.append({
            "title": title_el.inner_text() if title_el else "N/A",
            "company": company_el.inner_text() if company_el else "N/A",
            "location": location_el.inner_text() if location_el else "N/A",
            "url": "https://nz.seek.com" + link_el.get_attribute("href") if link_el else "N/A"
        })

    print(f"Found {len(jobs)} jobs (capped at {MAX_JOBS})")
    for job in jobs:
        print(f"  - {job['title']} at {job['company']}")

    with open("jobs.json", "w") as f:
        json.dump(jobs, f, indent=2)

    print("Saved to jobs.json")
    browser.close()