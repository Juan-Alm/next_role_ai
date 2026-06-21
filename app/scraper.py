# ============================================================
#  scraper.py — Fetches job listings from SEEK NZ
#
#  Uses Playwright to render the page (SEEK is JS-heavy)
#  and extracts structured job data from the results.
# ============================================================

from playwright.sync_api import sync_playwright
import time
import re

# --- Search settings ---
DATE_RANGE_DAYS = 3    # only jobs posted in the last N days
MAX_JOBS = 10          # hard cap on results per search

# --- Description fetching settings ---
DISQUALIFYING_TITLE_KEYWORDS = [
    "senior", "principal", "lead", "head of", "director", "manager",
]

# Headings we look for, in priority order, to find the "requirements" snippet
SNIPPET_HEADING_PATTERNS = [
    "about you",
    "what you'll bring",
    "what you bring",
    "what you'll need",
    "what you need",
    "skills & experience",
    "skills and experience",
    "requirements",
    "what we're looking for",
]


def build_seek_url(keyword: str, location: str, date_range: int = DATE_RANGE_DAYS) -> str:
    """
    Builds a SEEK NZ search URL.
    SEEK expects hyphens in keywords and location, e.g.:
      keyword="data analyst" → "data-analyst"
      location="Christchurch Central Canterbury" → "Christchurch-Central-Canterbury"
    """
    kw = keyword.strip().replace(" ", "-")
    loc = location.strip().replace(" ", "-")
    return f"https://nz.seek.com/{kw}-jobs/in-{loc}?daterange={date_range}"


def extract_job_id(href: str) -> str | None:
    """
    Extracts the numeric job ID from a SEEK URL href.
    e.g. "/job/92710074?type=standard&..." → "92710074"
    This is used for deduplication — the tracking parameters
    after the ID change between searches but the ID never does.
    """
    match = re.search(r'/job/(\d+)', href)
    return match.group(1) if match else None


def is_title_disqualified(title: str) -> bool:
    """
    Quick check against the job title alone — no page visit needed.
    Returns True if the title contains a seniority keyword that
    makes this role not worth fetching a description for.
    """
    title_lower = title.lower()
    return any(keyword in title_lower for keyword in DISQUALIFYING_TITLE_KEYWORDS)


def extract_requirements_snippet(page) -> str | None:
    """
    Looks inside the job description for a heading matching common
    "requirements" section patterns (e.g. "About you", "What you'll bring")
    and returns the text between that heading and the next one.

    Returns None if no matching heading is found — caller should
    fall back to the full description text in that case.
    """
    desc_el = page.query_selector('[data-automation="jobAdDetails"]')
    if not desc_el:
        return None

    headings = desc_el.query_selector_all("h1, h2, h3, h4, strong")

    for i, heading in enumerate(headings):
        heading_text = heading.inner_text().strip().lower()

        if any(pattern in heading_text for pattern in SNIPPET_HEADING_PATTERNS):
            # Found a match — collect text until the next heading.
            # We do this by walking the full description text and
            # slicing between this heading's text and the next one.
            full_text = desc_el.inner_text()
            start_marker = heading.inner_text().strip()

            start_idx = full_text.find(start_marker)
            if start_idx == -1:
                continue

            start_idx += len(start_marker)

            # Find the next heading (if any) to know where to stop
            end_idx = len(full_text)
            if i + 1 < len(headings):
                next_heading_text = headings[i + 1].inner_text().strip()
                next_idx = full_text.find(next_heading_text, start_idx)
                if next_idx != -1:
                    end_idx = next_idx

            snippet = full_text[start_idx:end_idx].strip()
            if snippet:
                return snippet

    return None


def fetch_job_description(job_url: str) -> dict:
    """
    Visits a single job's page and extracts a requirements snippet
    (preferred) or the full description (fallback).

    Returns a dict: {"snippet": str, "source": "snippet" | "full" | "error"}
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            page.goto(job_url, timeout=30000)
            page.wait_for_timeout(3000)

            snippet = extract_requirements_snippet(page)
            if snippet:
                return {"snippet": snippet, "source": "snippet"}

            # Fallback — no matching heading found, use full description
            desc_el = page.query_selector('[data-automation="jobAdDetails"]')
            if desc_el:
                return {"snippet": desc_el.inner_text().strip(), "source": "full"}

            return {"snippet": "", "source": "error"}

        except Exception as e:
            print(f"    Description fetch error for {job_url}: {e}")
            return {"snippet": "", "source": "error"}

        finally:
            browser.close()


def scrape_seek(keyword: str, location: str, fetch_descriptions: bool = True) -> list[dict]:
    """
    Opens SEEK, performs a search, and extracts job listings.

    Args:
        keyword:  job title or skill to search for (e.g. "data analyst")
        location: SEEK location string (e.g. "Christchurch-Central-Canterbury")
        fetch_descriptions: if True, visits each promising job's page to
                             extract a requirements snippet. Jobs whose
                             title contains a disqualifying keyword
                             (e.g. "Senior") skip this step entirely.

    Returns:
        List of job dicts with keys: job_id, title, company, location, url,
        keyword, description_snippet, description_source
    """
    url = build_seek_url(keyword, location)
    print(f"  Scraping: {url}")

    jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            page.goto(url, timeout=15000)
            page.wait_for_timeout(4000)

            job_cards = page.query_selector_all('article[data-testid="job-card"]')

            if not job_cards:
                print("  Warning: No job cards found. SEEK may have changed its layout.")
                return []

            for card in job_cards[:MAX_JOBS]:
                title_el    = card.query_selector('[data-automation="jobTitle"]')
                company_el  = card.query_selector('[data-automation="jobCompany"]')
                location_el = card.query_selector('[data-automation="jobLocation"]')
                link_el     = card.query_selector('a[data-automation="jobTitle"]')

                title   = title_el.inner_text().strip()    if title_el    else "N/A"
                company = company_el.inner_text().strip()   if company_el  else "N/A"
                loc     = location_el.inner_text().strip()  if location_el else "N/A"
                href    = link_el.get_attribute("href")     if link_el     else None

                # Clean URL — strip tracking parameters after the job ID
                job_id  = extract_job_id(href) if href else None
                job_url = f"https://nz.seek.com/job/{job_id}" if job_id else "N/A"

                jobs.append({
                    "job_id":   job_id,
                    "title":    title,
                    "company":  company,
                    "location": loc,
                    "url":      job_url,
                    "keyword":  keyword,
                })

        except Exception as e:
            print(f"  Scraper error: {e}")

        finally:
            browser.close()

    print(f"  Found {len(jobs)} listings for '{keyword}'")

    if fetch_descriptions:
        jobs = _attach_descriptions(jobs)

    return jobs


def _attach_descriptions(jobs: list[dict]) -> list[dict]:
    """
    For each job that passes the title pre-filter, visits its page
    and attaches a requirements snippet. Disqualified-by-title jobs
    are skipped (no page visit) to save time.
    """
    for job in jobs:
        if is_title_disqualified(job["title"]):
            print(f"    ⏭  Skipping description (title filtered): {job['title']}")
            job["description_snippet"] = ""
            job["description_source"] = "skipped_title_filter"
            continue

        if job["url"] == "N/A":
            job["description_snippet"] = ""
            job["description_source"] = "no_url"
            continue

        print(f"    📄 Fetching description: {job['title']}")
        result = fetch_job_description(job["url"])
        job["description_snippet"] = result["snippet"]
        job["description_source"] = result["source"]
        time.sleep(1)  # be polite between page visits

    return jobs


def scrape_multiple_keywords(keywords: list[str], locations: list[str]) -> list[dict]:
    """
    Runs scrape_seek for each combination of keyword and location,
    returning a combined deduplicated list (by job ID).
    """
    seen_ids = set()
    all_jobs = []

    for location in locations:
        for keyword in keywords:
            results = scrape_seek(keyword, location)
            time.sleep(2)

            for job in results:
                job_id = job.get("job_id")
                if job_id and job_id not in seen_ids:
                    seen_ids.add(job_id)
                    all_jobs.append(job)

    print(f"\nTotal unique listings found: {len(all_jobs)}")
    return all_jobs