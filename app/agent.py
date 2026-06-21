# ============================================================
#  agent.py — The agentic loop
#
#  Defines the search_seek tool, and runs a conversation loop
#  where Qwen3 can decide to call it, see the results, and
#  reply to you in natural language.
# ============================================================

import json
from app.ollama_client import chat
from app.scraper import scrape_seek
from app.criteria import get_criteria_prompt
from app.memory import filter_unseen, init_db
from app.matcher import evaluate_job

# Make sure the database and table exist before anything runs
init_db()


# ── Tool definition ──────────────────────────────────────────
# This is the schema Ollama expects. It tells Qwen3 the tool's
# name, what it does, and what parameters it takes.

SEARCH_SEEK_TOOL = {
    "type": "function",
    "function": {
        "name": "search_seek",
        "description": (
            "Search SEEK New Zealand for job listings matching ONE specific "
            "job title or skill at a time. Returns a list of jobs with title, "
            "company, location, and URL. "
            "IMPORTANT: the keyword parameter must be a single job title or "
            "skill (e.g. 'data analyst'). Do NOT combine multiple roles into "
            "one call using 'OR', commas, or slashes — if the user wants "
            "results for several roles (e.g. 'data analyst and data "
            "scientist jobs'), call this tool once per role instead."
        ),
        "parameters": {
            "type": "object",
            "required": ["keyword", "location"],
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": (
                        "A SINGLE job title or skill to search for, e.g. "
                        "'data analyst'. Never combine multiple roles here."
                    ),
                },
                "location": {
                    "type": "string",
                    "description": "City or region in New Zealand, e.g. 'Christchurch'",
                },
            },
        },
    },
}

AVAILABLE_TOOLS = [SEARCH_SEEK_TOOL]


def run_tool(name: str, arguments: dict) -> str:
    """
    Executes a tool call requested by the model and returns the
    result as a string (Ollama expects tool results as text).
    """
    if name == "search_seek":
        keyword = arguments.get("keyword", "")
        location = arguments.get("location", "Christchurch")
        print(f"  🔧 Agent is searching SEEK: keyword='{keyword}', location='{location}'")

        jobs = scrape_seek(keyword, location)

        # Filter out jobs already seen in past searches
        new_jobs = filter_unseen(jobs)
        skipped = len(jobs) - len(new_jobs)
        if skipped:
            print(f"  🧠 Skipped {skipped} already-seen job(s)")

        if not new_jobs:
            return json.dumps([])

        # Score every job the same way batch_search.py does — this keeps
        # the chat agent's judgements consistent with the structured
        # pipeline instead of letting the model freely re-judge each time.
        print(f"  🧮 Scoring {len(new_jobs)} job(s)...")
        scored_jobs = []
        for job in new_jobs:
            result = evaluate_job(job)
            scored_jobs.append({
                "title": result.get("title"),
                "company": result.get("company"),
                "location": result.get("location"),
                "url": result.get("url"),
                "score": result.get("score"),
                "recommendation": result.get("recommendation"),
                "reasons": result.get("reasons", []),
                "concerns": result.get("concerns", []),
            })

        # Sort best matches first so the model sees strong results up top
        scored_jobs.sort(key=lambda j: j.get("score", 0), reverse=True)

        return json.dumps(scored_jobs)

    return json.dumps({"error": f"Unknown tool: {name}"})


SYSTEM_PROMPT = f"""
You are a helpful job search assistant. You can search SEEK New Zealand
for job listings using the search_seek tool.

The candidate's criteria are:

{get_criteria_prompt()}

IMPORTANT: search_seek accepts only ONE job title/keyword per call. If
the user asks about multiple roles (e.g. "data analyst and data
scientist jobs"), call search_seek once for each role separately —
never combine roles into a single keyword with "OR", commas, or
slashes, as SEEK will not understand that and will return irrelevant
results.

The search_seek tool returns jobs that have ALREADY been scored against
the candidate's criteria. Each job includes a "score" (1-10), a
"recommendation" (STRONG MATCH, GOOD MATCH, WEAK MATCH, or SKIP), and
lists of "reasons" and "concerns". Do NOT re-judge or override these
scores yourself — they come from a consistent scoring process. Your
job is to present them clearly and faithfully:

- Lead with STRONG MATCH and GOOD MATCH jobs, clearly labelled as such.
- Mention WEAK MATCH jobs only briefly, and be upfront that they're a
  weak fit — don't talk them up.
- You can omit SKIP jobs entirely, or mention there were some that
  didn't fit well, without listing them individually.
- Never describe a WEAK MATCH or SKIP job using positive framing like
  "why it fits" — that misrepresents the score.

Note: the search tool only returns NEW listings the candidate hasn't
been shown before. If it returns an empty list, that means there are
no new jobs right now — tell the user that clearly rather than
inventing results, and suggest trying a different keyword or location.
""".strip()


def agent_loop(user_message: str, history: list[dict] = None) -> tuple[str, list[dict]]:
    """
    Runs one full turn of the agent: sends the user's message,
    handles any tool calls the model makes, and returns the final
    text reply plus the updated conversation history.

    Args:
        user_message: what the user typed
        history: prior conversation (list of message dicts), or None to start fresh

    Returns:
        (reply_text, updated_history)
    """
    messages = list(history) if history else []
    messages.append({"role": "user", "content": user_message})

    # Allow a few rounds of tool calls in case the model wants to
    # search more than once before giving a final answer.
    MAX_TOOL_ROUNDS = 4

    for _ in range(MAX_TOOL_ROUNDS):
        response_message = chat(
            messages=messages,
            system_prompt=SYSTEM_PROMPT,
            tools=AVAILABLE_TOOLS,
        )
        messages.append(response_message)

        tool_calls = response_message.get("tool_calls")
        if not tool_calls:
            # No tool call — the model gave its final answer
            return response_message.get("content", ""), messages

        # The model wants to call one or more tools — run them
        for call in tool_calls:
            fn_name = call["function"]["name"]
            fn_args = call["function"]["arguments"]
            result = run_tool(fn_name, fn_args)

            messages.append({
                "role": "tool",
                "content": result,
            })

    # Safety net — if we somehow loop too many times, return whatever we have
    return "I searched but couldn't finish reasoning about the results — try rephrasing.", messages