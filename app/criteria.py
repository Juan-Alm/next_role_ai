# ============================================================
#  criteria.py — Your personal job search brief
#  Edit this file to match what YOU are looking for.
#  Qwen3 will use this as its reference for every decision.
# ============================================================

CRITERIA = {
    # --- What you're looking for ---
    "roles": [
        "Data Analyst",
        "Data Scientist",
    ],

    # --- Location preferences ---
    "locations": ["Christchurch"],

    # --- Work type ---
    "work_type": ["Full-time",],

    # --- Experience level ---
    "experience_level": ["graduate", "entry-level",],

    # --- Salary (optional — SEEK doesn't always show it) ---
    "salary_min_nzd": 0,           # set to 0 to ignore

    # --- Skills you have (model uses this to judge fit) ---
    "skills": [
        "Python",
        "SQL",
        "R",
        "Excel",
        "Power BI",
        "Data visualisation",
        "AI",
    ],

    # --- Things to avoid ---
    "dealbreakers": [
        "requires 5+ years experience",
        "commission only",
    ],

    # --- Any extra notes for the agent ---
    "notes": "I prefer roles that involve working with data and producing insights. "
             "I am open to learning new tools. Culture and growth opportunities matter to me.",
}


def get_criteria_prompt() -> str:
    """
    Formats the criteria dict into a clear block of text
    that can be dropped directly into a system prompt.
    """
    c = CRITERIA
    roles = ", ".join(c["roles"])
    locations = ", ".join(c["locations"])
    work_types = ", ".join(c["work_type"])
    skills = ", ".join(c["skills"])
    dealbreakers = "\n  - ".join(c["dealbreakers"])
    salary = f"NZD ${c['salary_min_nzd']:,}+" if c["salary_min_nzd"] > 0 else "not specified"

    return f"""
## Candidate Job Search Criteria

**Target roles:** {roles}
**Preferred locations:** {locations}
**Work type:** {work_types}
**Experience level:** {c['experience_level']}
**Minimum salary:** {salary}
**Key skills:** {skills}

**Dealbreakers (reject if any apply):**
  - {dealbreakers}

**Additional notes:** {c['notes']}
""".strip()