import csv
import re
import time
import pandas as pd
from datetime import datetime
from jobspy import scrape_jobs

now = datetime.now()
date = f"{now.month}-{now.day}-{now.strftime('%y')}"
filename = "jobs-" + date + ".csv"

ANALYZE_MODE = False
FALLBACK = True
CONTRACT_ONLY = False
#test zip only
ZIPRECRUITER_ONLY = False

# -----------------------
# SEARCH TERMS
# -----------------------

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

bridge_roles = [
    "database engineer",
    "automation engineer data",
    "systems analyst sql",
    "systems analyst data integration",
    "systems analyst etl",
    "application engineer data",
    "data analyst sql",
    "reporting analyst sql",
]

# -----------------------
# ZIPRECRUITER SAFE CONFIG
# -----------------------

ZIPRECRUITER_CORE_RESULTS = 30
ZIPRECRUITER_SECONDARY_RESULTS = 15
ZIPRECRUITER_BRIDGE_RESULTS = 10

ZIPRECRUITER_TERM_DELAY = 60
ZIPRECRUITER_PROXIES = [
    "http://149.248.215.39:8081",
]

ZIPRECRUITER_TERMS_PER_RUN = 3
ZIPRECRUITER_SECONDARY_TERMS_PER_RUN = 2
ZIPRECRUITER_BRIDGE_TERMS_PER_RUN = 1

all_jobs = []

# -----------------------
# ROTATION LOGIC
# -----------------------

# To avoid hitting ZipRecruiter's rate limits, we rotate through the search terms on a daily basis. This function takes in a list of terms and the number of terms to use per run, and returns a rotated subset of the terms based on the current day of the year.
def rotate_terms(terms, terms_per_run):
    day_index = datetime.now().timetuple().tm_yday
    start = (day_index * terms_per_run) % len(terms)
    end = start + terms_per_run

    if end <= len(terms):
        return terms[start:end]

    return terms[start:] + terms[: end % len(terms)]

# -----------------------
# SCRAPER FUNCTIONS
# -----------------------

def scrape_term(term, lane, results_wanted, site_name=None,hours_old=None, proxies=None):
    if site_name is None:
        site_name = ["indeed", "linkedin", "google"]

    return scrape_site_term(
        term,
        lane,
        results_wanted,
        site_name=site_name,
        hours_old=hours_old,
        proxies=proxies,
    )

def scrape_site_term(term, lane, results_wanted, site_name=None,hours_old=None, proxies=None):
    contract_search = "jobs since the past 1 days in Texas"
    jobs = scrape_jobs(
        site_name=site_name,
        search_term=term,
        google_search_term=f"{term} jobs since the past 1 days in Texas",
        location="Texas",
        results_wanted=results_wanted,
        hours_old=hours_old,
        country_indeed="USA",
        linkedin_fetch_description=True,
        proxies=proxies,
    )

    jobs["search_lane"] = lane
    jobs["search_term_used"] = term
    print(f"Found {lane.upper()} jobs for term '{term}' on {site_name}: {len(jobs)}")
    return jobs.to_dict(orient="records")

def scrape_ziprecruiter_term(term, lane, results_wanted,hours_old=None, proxies=None):
    return scrape_site_term(
        term,
        lane,
        results_wanted,
        site_name=["zip_recruiter"],
        proxies=proxies,
        hours_old=168
    )
    
# -----------------------
# NORMAL SCRAPE
# -----------------------

if not ZIPRECRUITER_ONLY:

    if ANALYZE_MODE:
        for term in market_analysis:
            all_jobs.extend(scrape_term(term, "market_analysis", hours_old=24, results_wanted=100))
    else:
        if FALLBACK:
            for term in bridge_roles:
                all_jobs.extend(scrape_term(term, "bridge", hours_old=24, results_wanted=30))

        for term in core_terms:
            all_jobs.extend(scrape_term(term, "core", hours_old=24, results_wanted=120))

        for term in secondary_terms:
            all_jobs.extend(scrape_term(term, "secondary", hours_old=24, results_wanted=25))

else:
    print("ZIPRECRUITER_ONLY is True - skipping Indeed, LinkedIn, and Google scrapes")
    # -----------------------
    # ZIPRECRUITER SCRAPE
    # -----------------------

    zip_terms = []

    # Core (priority)
    zip_terms.extend([
        (term, "core", ZIPRECRUITER_CORE_RESULTS)
        for term in rotate_terms(core_terms, ZIPRECRUITER_TERMS_PER_RUN)
    ])

    # Secondary
    zip_terms.extend([
        (term, "secondary", ZIPRECRUITER_SECONDARY_RESULTS)
        for term in rotate_terms(secondary_terms, ZIPRECRUITER_SECONDARY_TERMS_PER_RUN)
    ])

    # Bridge (fallback)
    if FALLBACK:
        zip_terms.extend([
            (term, "bridge", ZIPRECRUITER_BRIDGE_RESULTS)
            for term in rotate_terms(bridge_roles, ZIPRECRUITER_BRIDGE_TERMS_PER_RUN)
        ])

    for term, lane, results in zip_terms:
        try:
            all_jobs.extend(
                scrape_ziprecruiter_term(
                    term,
                    lane,
                    results,
                    hours_old=168,
                    proxies=ZIPRECRUITER_PROXIES,
                )
            )
        except Exception as e:
            print(f"ZipRecruiter failed for '{term}' ({lane}): {e}")

        time.sleep(ZIPRECRUITER_TERM_DELAY)

# -----------------------
# POST PROCESSING
# -----------------------

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

    jobs["review_priority"] = jobs["search_lane"].map({
        "core": 1,
        "secondary": 2,
        "bridge": 3,
    })

    sort_cols = ["review_priority"]

    if "date_posted" in jobs.columns:
        sort_cols.append("date_posted")

    jobs = jobs.sort_values(by=sort_cols, ascending=[True, False])
    jobs.to_csv(filename, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)

    print(f"Saved prioritized jobs to {filename}")