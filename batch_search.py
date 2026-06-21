# ============================================================
#  main.py — Phase A entry point
#
#  Runs the full pipeline:
#    1. Check Ollama is running
#    2. Scrape SEEK for each role in your criteria
#    3. Evaluate each listing with Qwen3
#    4. Print a summary and save results to JSON
# ============================================================

import json
import os
from datetime import datetime

from app.ollama_client import is_ollama_running
from app.scraper import scrape_multiple_keywords
from app.matcher import evaluate_all_jobs, print_summary
from app.criteria import CRITERIA

# ── Settings ─────────────────────────────────────────────────
LOCATIONS = CRITERIA["locations"]
OUTPUT_DIR = "output"


def save_results(results: list[dict]) -> str:
    """Saves evaluated results to a timestamped JSON file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(OUTPUT_DIR, f"results_{timestamp}.json")

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return filepath


def main():
    print("\n🔍 SEEK Job Agent — Phase A")
    print("=" * 40)

    # Step 1 — Check Ollama
    print("\nChecking Ollama...")
    if not is_ollama_running():
        print("❌ Ollama is not running.")
        print("   Start it with: ollama serve")
        print("   Then run this script again.")
        return
    print("✅ Ollama is running.")

    # Step 2 — Scrape SEEK
    print(f"\nSearching SEEK NZ for roles in {', '.join(LOCATIONS)}...")
    keywords = CRITERIA["roles"]   # uses the roles list from your criteria
    jobs = scrape_multiple_keywords(keywords, locations=LOCATIONS)

    if not jobs:
        print("❌ No jobs found. Check your keywords or SEEK may be blocking requests.")
        return

    # Step 3 — Evaluate with Qwen3
    results = evaluate_all_jobs(jobs)

    # Step 4 — Show summary and save
    print_summary(results)

    filepath = save_results(results)
    print(f"💾 Full results saved to: {filepath}\n")


if __name__ == "__main__":
    main()