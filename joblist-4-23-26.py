import csv
import re
import pandas as pd
from datetime import datetime
from jobspy import scrape_jobs

now = datetime.now()
date = f"{now.month}-{now.day}-{now.strftime('%y')}"
filename = "jobs-" + date + ".csv"

"""
Scrape a narrower DE / integration-first lane.

Goals:
- Keep core lane focused on data engineering / ETL / SQL / integration
- Use secondary lane only for nearby roles that still look plausibly data/backend-aligned
- Keep fallback off by default to avoid flooding the funnel with generic SWE/support roles
"""

ANALYZE_MODE=False
market_analysis = [
    #My Skills;referenced from the Profile.yaml in skillfreq
    "sql etl",
    "data pipeline sql",
    "data integration sql",
    "api integration python",
    "backend api sql",
    "data validation sql",
    "data quality sql",
    "json xml sql",
    "database sql",
    "automation python sql",
]
discovered_titles= []

# Core search lane.
# These should make up the majority of the scraped pool.
core_terms = [
    "data engineer",
    "junior data engineer",
    "associate data engineer",
    "etl engineer",
    "etl developer",
    "data integration engineer",
    "etl integration engineer",
    "api integration engineer",
    "systems integration engineer data",
    "data pipeline engineer",
    "data ingestion engineer",
    "sql developer",
    "database developer",
    "data operations engineer",
    "data quality engineer",
    "software engineer data engineering",
]

# Secondary search lane.
# Use for nearby roles that can still plausibly be DE/backend-data adjacent.
secondary_terms = [
    "data platform engineer",
    "data systems engineer",
    "data infrastructure engineer",
    "backend data engineer",
    "pipeline engineer",
    "integration engineer",
    "integration developer",
    "backend engineer data",
    "software engineer data",
    "backend software engineer sql",
    "api integration engineer",
    "software engineer integration",
]

# Fallback lane.
# Only use if core + secondary yield too few results.
bridge_roles = [
    "database engineer",#closest to your SQL + data validation strength
    "automation engineer data",  # keeps Python + scripting signal alive
    "systems analyst sql",
    "systems analyst data integration",
    "systems analyst etl",
    "application engineer data",
    "data analyst sql", #fallback, high volume, SQL-heavy
    "reporting analyst sql", #survival model for analytics-adjacent roles that still use SQL and may have some data engineering adjacent work
]

FALLBACK = True

all_jobs = []

def normalize_title(title: str) -> str:
    if not isinstance(title, str) or not title.strip():
        return "unknown"

    t = title.lower().strip()

    replacements = {
        "sr.": "senior",
        "jr.": "junior",
        "sde": "software engineer",
        "swe": "software engineer",
        "dev": "developer",
        "&": "and",
        "/": " ",
        "-": " ",
    }

    for old, new in replacements.items():
        t = t.replace(old, new)

    # remove level suffixes / roman numerals
    t = re.sub(r"\b(i|ii|iii|iv|v)\b", "", t)

    # collapse whitespace
    t = " ".join(t.split())
    return t

def build_title_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "title" not in df.columns:
        return pd.DataFrame(columns=["normalized_title", "total"])

    summary_df = df.copy()
    summary_df["normalized_title"] = summary_df["title"].apply(normalize_title)

    title_summary = (
        summary_df.groupby("normalized_title", dropna=False)
        .size()
        .reset_index(name="total")
        .sort_values(by="total", ascending=False)
        .reset_index(drop=True)
    )

    return title_summary

def scrape_term(term: str, lane: str, results_wanted: int):
    jobs = scrape_jobs(
        site_name=["indeed", "linkedin", "google"],
        search_term=term,
        google_search_term=f"{term} jobs since the past 1 days in Texas",
        location="Texas",
        results_wanted=results_wanted,
        hours_old=24,
        country_indeed="USA",
        linkedin_fetch_description=True,
    )

    jobs["search_lane"] = lane
    jobs["search_term_used"] = term
    print(f"Found {lane.upper()} jobs for term '{term}': {len(jobs)}")
    return jobs.to_dict(orient="records")


# if FALLBACK:
#     for term in bridge_roles:
#         all_jobs.extend(scrape_term(term, "bridge", 20))
if ANALYZE_MODE:
    for term in market_analysis:
        all_jobs.extend(scrape_term(term, "market_analysis", 100))
else:
    if FALLBACK:
        for term in bridge_roles:
            all_jobs.extend(scrape_term(term, "bridge", 20))
    for term in core_terms:
        all_jobs.extend(scrape_term(term, "core", 100))

    for term in secondary_terms:
        all_jobs.extend(scrape_term(term, "secondary", 30))

jobs = pd.DataFrame(all_jobs)

if jobs.empty:
    print("No jobs found.")
    jobs.to_csv(filename, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)

else:
    if "job_url" in jobs.columns:
            jobs = jobs.drop_duplicates(subset=["job_url"])
    elif "id" in jobs.columns:
        jobs = jobs.drop_duplicates(subset=["id"])
    else:
        jobs = jobs.drop_duplicates(subset=["title", "company", "location"])

    if ANALYZE_MODE:
        filename = "market-analysis-" + date + ".csv"
        title_summary = build_title_summary(jobs)

        summary_filename = "title-summary-" + date + ".csv"
        title_summary.to_csv(summary_filename, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)

        print(f"\nTotal scraped jobs after dedupe: {len(jobs)}")
        print(f"Unique normalized titles: {len(title_summary)}")
        print("\nTop titles:")
        print(title_summary.head(25).to_string(index=False))
        jobs.to_csv(filename, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        print(f"Saved raw jobs to {filename}")

    if not ANALYZE_MODE:
        jobs["review_priority"] = jobs["search_lane"].map({
            "core": 1,
            "secondary": 2,
            "bridge": 3,
        })

        sort_cols = ["review_priority"]
        ascending = [True]

        if "date_posted" in jobs.columns:
            sort_cols.append("date_posted")
            ascending.append(False)

        jobs = jobs.sort_values(by=sort_cols, ascending=ascending)
        jobs.to_csv(filename, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        print(f"Saved prioritized jobs to {filename}")