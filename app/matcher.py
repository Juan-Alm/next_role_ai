# ============================================================
#  matcher.py — The job matching pipeline
#
#  Takes scraped job listings, sends them to Qwen3 one by one,
#  and asks the model to score and explain each match against
#  the candidate's criteria.
# ============================================================

import json
from app.ollama_client import chat
from app.criteria import get_criteria_prompt

# ── System prompt ────────────────────────────────────────────
# This is the instruction set Qwen3 reads before doing anything.
# It defines the model's role and tells it exactly how to respond.

SYSTEM_PROMPT_TEMPLATE = """
You are a job search assistant helping a candidate find the right role.
Your job is to evaluate a job listing and decide if it is a good match.

Here are the candidate's criteria:

{criteria}

---

You may be given just a job title, or a title plus a requirements
snippet/description pulled from the job ad. When a description is
present, prioritise it over guessing from the title alone — for
example, only flag an experience mismatch if the description actually
states a requirement (e.g. "5+ years"), not just because the title
sounds senior.

When given a job listing, respond ONLY with a JSON object in this exact format:

{{
  "score": <integer from 1 to 10>,
  "recommendation": "<STRONG MATCH | GOOD MATCH | WEAK MATCH | SKIP>",
  "reasons": ["<reason 1>", "<reason 2>", "<reason 3>"],
  "concerns": ["<concern 1>"] 
}}

Scoring guide:
  9-10 = Excellent fit, meets almost all criteria
  7-8  = Good fit, meets most criteria
  5-6  = Partial fit, worth considering
  3-4  = Poor fit, significant mismatches
  1-2  = Not suitable, dealbreaker present

Be concise. Each reason or concern should be one short sentence.
Respond with JSON only — no preamble, no explanation outside the JSON.
""".strip()


def build_job_message(job: dict) -> str:
    """Formats a job dict into a clear message for the model."""
    snippet = job.get("description_snippet", "").strip()
    snippet_source = job.get("description_source", "")

    base = f"""
Please evaluate this job listing:

Title:    {job['title']}
Company:  {job['company']}
Location: {job['location']}
URL:      {job['url']}
""".strip()

    if snippet:
        label = "Key requirements (from job ad)" if snippet_source == "snippet" else "Full job description"
        # Cap length to keep prompts fast — snippets are usually short anyway,
        # but a full-description fallback could be long.
        snippet_trimmed = snippet[:1500]
        base += f"\n\n{label}:\n{snippet_trimmed}"
    elif snippet_source == "skipped_title_filter":
        base += "\n\n(No description fetched — title contains a seniority keyword that didn't match candidate's level.)"

    return base


def evaluate_job(job: dict) -> dict:
    """
    Sends a single job to Qwen3 and returns the model's assessment.

    Returns the original job dict enriched with:
      - score (int)
      - recommendation (str)
      - reasons (list)
      - concerns (list)
      - error (str, only if something went wrong)
    """
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(criteria=get_criteria_prompt())
    user_message = build_job_message(job)

    try:
        response_message = chat(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=system_prompt,
        )
        reply = response_message.get("content", "")

        # Strip any accidental markdown fences Qwen3 might add
        clean = reply.strip().removeprefix("```json").removesuffix("```").strip()
        assessment = json.loads(clean)

        # Guard against the model inventing its own label —
        # derive a valid one from the score if needed.
        valid_recommendations = {"STRONG MATCH", "GOOD MATCH", "WEAK MATCH", "SKIP"}
        if assessment.get("recommendation") not in valid_recommendations:
            score = assessment.get("score", 0)
            if score >= 9:
                assessment["recommendation"] = "STRONG MATCH"
            elif score >= 7:
                assessment["recommendation"] = "GOOD MATCH"
            elif score >= 5:
                assessment["recommendation"] = "WEAK MATCH"
            else:
                assessment["recommendation"] = "SKIP"

        return {**job, **assessment}

    except json.JSONDecodeError:
        # Model returned something unexpected — save it for debugging
        print(f"\n    DEBUG — raw reply:\n{reply}\n")
        return {**job, "score": 0, "recommendation": "ERROR", "error": reply}

    except Exception as e:
        print(f"\n    DEBUG — exception type: {type(e).__name__}, message: {e}\n")
        return {**job, "score": 0, "recommendation": "ERROR", "error": str(e)}


def evaluate_all_jobs(jobs: list[dict]) -> list[dict]:
    """
    Evaluates every job in the list and returns results sorted
    by score (highest first).
    """
    print(f"\nEvaluating {len(jobs)} jobs with Qwen3...")
    results = []

    for i, job in enumerate(jobs, 1):
        print(f"  [{i}/{len(jobs)}] {job['title']} at {job['company']}...", end=" ")
        result = evaluate_job(job)
        score = result.get("score", 0)
        rec   = result.get("recommendation", "ERROR")
        print(f"→ {rec} ({score}/10)")
        results.append(result)

    # Sort best matches first
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results


def print_summary(results: list[dict]) -> None:
    """Prints a readable summary of all evaluated jobs to the terminal."""
    print("\n" + "=" * 60)
    print("  JOB MATCH SUMMARY")
    print("=" * 60)

    for job in results:
        score = job.get("score", 0)
        rec   = job.get("recommendation", "?")
        title = job.get("title", "Unknown")
        co    = job.get("company", "Unknown")
        url   = job.get("url", "")

        # Colour-code by recommendation (works in most terminals)
        label = {
            "STRONG MATCH": "🟢",
            "GOOD MATCH":   "🟡",
            "WEAK MATCH":   "🟠",
            "SKIP":         "🔴",
            "ERROR":        "⚠️ ",
        }.get(rec, "❓")

        print(f"\n{label} [{score}/10] {rec}")
        print(f"   {title} — {co}")
        print(f"   {url}")

        if reasons := job.get("reasons"):
            for r in reasons:
                print(f"   ✓ {r}")

        if concerns := job.get("concerns"):
            for c in concerns:
                print(f"   ✗ {c}")

    print("\n" + "=" * 60)
    strong = sum(1 for j in results if j.get("recommendation") in ("STRONG MATCH", "GOOD MATCH"))
    print(f"  {strong} strong/good matches out of {len(results)} listings evaluated.")
    print("=" * 60 + "\n")