import csv
import hashlib
import json
import os
import re
import threading
import time
import uuid
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from jobspy import scrape_jobs

now = datetime.now()
date = f"{now.month}-{now.day}-{now.strftime('%y')}"
filename = "jobs-" + date + ".csv"

# proxies = [
#     "http://kyepxfcr-US-rotate:6tt6cwkm0mkn@p.webshare.io:80/"
# ]
proxies = None

ANALYZE_MODE = False #no longer used - was for testing market analysis terms
FALLBACK = False
CONTRACT_ONLY = False
ZIPRECRUITER_ONLY = False
QUALIFICATION_SEARCH = True

# Runtime controls. Keep workers modest; every term already fans out across sites.
MAX_TERM_WORKERS = 1
LINKEDIN_FETCH_DESCRIPTION = True
CACHE_ENABLED = True
CACHE_TTL_HOURS = 12
CACHE_DIR = ".job_cache"
SCRAPE_LOG_ENABLED = os.getenv("SCRAPE_LOG_ENABLED", "1") != "0"
SCRAPE_LOG_DIR = os.getenv("SCRAPE_LOG_DIR", "logs")
SCRAPE_RUN_ID = os.getenv(
    "SCRAPE_RUN_ID",
    f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}",
)


class ScrapeProgressLogger:
    def __init__(self, log_dir, run_id, enabled=True):
        self.enabled = enabled
        self.run_id = run_id
        self.lock = threading.Lock()
        self.path = os.path.join(log_dir, f"scrape-progress-{run_id}.jsonl")

        if self.enabled:
            os.makedirs(log_dir, exist_ok=True)

    def emit(self, event, **fields):
        if not self.enabled:
            return

        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "run_id": self.run_id,
            "event": event,
            **fields,
        }
        with self.lock:
            with open(self.path, "a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(record, ensure_ascii=True, default=str) + "\n")


progress_log = ScrapeProgressLogger(
    SCRAPE_LOG_DIR,
    SCRAPE_RUN_ID,
    enabled=SCRAPE_LOG_ENABLED,
)


def log_progress(event, **fields):
    progress_log.emit(event, **fields)


# -----------------------
# SEARCH TERMS
# -----------------------

qualification_terms = [
    # SQL + data quality
    "sql data validation",
    "sql data quality",
    "sql data integrity",
    "sql data reconciliation",
    "sql validation checks",
    "sql data accuracy",
    "sql data discrepancies",
    "sql query optimization",
    "sql indexing",
    "sql server data validation",
    "sql server query optimization",

    # ETL / data workflows
    "etl sql",
    "elt sql",
    "etl data validation",
    "etl data quality",
    "etl data transformation",
    "etl data ingestion",
    "etl data reconciliation",
    "data pipeline sql",
    "data pipeline validation",
    "data pipeline troubleshooting",
    "data workflows sql",
    "batch processing sql",
    "dependency ordering data workflow",
    "failure recovery data pipeline",

    # Data mapping / transformation / schemas
    "data mapping sql",
    "source to target mapping",
    "xml schema validation",
    "schema comparison",
    "schema validation python",
    "transformation rules sql",
    "business rules sql",
    "mapping validation sql",
    "semi structured data xml",
    "semi structured data json",

    # APIs / integrations / external systems
    "rest api sql",
    "soap api sql",
    "api integration sql",
    "api testing postman",
    "soapui api testing",
    "xml json integration",
    "sftp data integration",
    "external systems integration",
    "system to system integration",
    "data exchange sql",
    "http https api integration",
    "request response debugging",

    # Production troubleshooting / observability
    "production support sql",
    "production troubleshooting sql",
    "root cause analysis sql",
    "log analysis sql",
    "opensearch logs",
    "application logs troubleshooting",
    "pipeline failure analysis",
    "data issue troubleshooting",
    "integration issue troubleshooting",
    "incident turnaround sql",
    "runtime debugging logs",
    "environment troubleshooting",

    # Python automation / validation scripts
    "python sql automation",
    "python data validation",
    "python validation scripts",
    "python data processing",
    "python pandas data validation",
    "python csv processing",
    "python xml validation",
    "python json validation",
    "python cli pandas",
    "python excel automation",

    # DevOps / workflow tools
    "azure devops ci cd",
    "ci cd pipeline troubleshooting",
    "git azure devops",
    "jira agile sdlc",
    "multi environment deployment",
    "dev test prod deployment",
    "docker python pipeline",

    # Testing / release quality
    "selenium regression testing",
    "jest junit testing",
    "automated test suites",
    "regression issue reduction",
    "release confidence testing",
    "integration testing api",

    # Education / degree-backed searches
    "computer science sql python",
    "data science sql python",
    "ms data science sql",
    "data science etl sql",
    "computer science data integration",
    "data science data validation",


]



contract_modifiers = [
    "contract",
    "contract to hire",
    "contract-to-hire",
    "temporary",
    "consultant",
    "w2 contract",
]


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
     "advanced sql data validation",
    "sql data workflows",
    "sql data reconciliation",
    "sql data integrity",
    "sql operational data",
    "data mapping sql",
    "source systems sql",
    "external systems sql",
    "third party systems sql",
    "cross system validation sql",
    "production issues sql",
    "application issues sql",
    "issue resolution sql",
    "incident management sql",
    "runbooks sql",
    "slas sql",
    "observability data pipelines",
    "data monitoring sql",
    "pipeline troubleshooting sql",
]




discovered_titles= []

core_terms = [
   "data engineer",
    "junior data engineer",
    "associate data engineer",
    "etl engineer",
    "etl developer",
    "data analyst sql",
    "data integration engineer",
    "etl integration engineer",
    "api integration engineer",
    "systems integration engineer data",
    "data pipeline engineer",
    "data ingestion engineer",
    "sql developer",
    "sql etl",
    "database developer",
    "data operations engineer",
    "data quality engineer",
    "software engineer data engineering",
    "interface engineer data",
    "middleware engineer data"
]

secondary_terms = [
    "data platform engineer",
    "forward deployed engineer sql",
    "forward deployed engineer data",
    "forward deployed software engineer integration",
    "forward deployed engineer api",
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
    "data warehouse engineer",
    "Data Warehouse Analyst SQL",
    "Analytics Engineer SQL",
    "systems analyst sql etl data integration"
]

bridge_roles = [
    "database engineer",
    "automation engineer data",
    "application data analyst sql",
    "application engineer data",
    "data analyst sql",
    "reporting analyst sql",
    "BI Developer SQL ETL",
    "Application Support Engineer SQL",
    "support engineer data",
    "Technical Support Engineer SQL",
    "technical support analyst sql",
    "Technical Operations Engineer SQL",
    "operations engineer data",
    "database administrator sql",
    "sql database administrator",
    # Application / production support
    "application support analyst sql",
    "production support analyst sql",
    "software support analyst sql",
    "technical support engineer sql",
    "technical operations engineer sql",
    "IT technician SQL",
    "IT support technician SQL",
    "application support technician SQL",
    "technical support technician SQL",
    "data support technician SQL",
    "systems support technician SQL",
    "help desk technician SQL",

    # Integration / interface support
    "integration support analyst",
    "integration support engineer",
    "interface analyst",
    "interface support analyst",
    "api support engineer sql",
    "etl support analyst",

    # Data operations / quality
    "data operations analyst sql",
    "data support analyst sql",
    "data quality analyst sql",
    "data validation analyst sql",
    "reporting analyst sql",
    "application data analyst sql",

    # Systems analyst bridge
    "systems analyst sql",
    "business systems analyst sql",
    "application analyst sql",

    # QA / validation bridge
    "data QA analyst sql",
    "QA analyst SQL",
    "API test analyst",
    "ETL QA analyst",
    "database tester SQL",

    # Reliability / ops bridge
    "application reliability engineer data",
    "reliability engineer data",
    "junior site reliability engineer",
    "cloud support engineer sql",
    "automation engineer data pipelines"
    
]

survival_terms = [
    # Data specialist layer
    "data operations specialist",
    "data processing specialist",
    "data quality specialist",
    "data integrity specialist",
    "data validation specialist",
    "data reconciliation specialist",
    "data verification specialist",
    "master data specialist",
    "file processing specialist",
    "batch processing specialist",

    # SQL/data-adjacent
    "data specialist sql",
    "operations specialist sql",
    "reporting specialist sql",
    "quality specialist sql",
    "data processing sql",
    "data validation sql",
    "data reconciliation sql",

    # Systems/process specialist layer
    "application specialist",
    "systems specialist",
    "business systems specialist",
    "platform support specialist",
    "configuration specialist software",
    "workflow specialist",
    "process specialist systems",

    # Domain-specific data/systems
    "claims data specialist",
    "claims systems specialist",
    "healthcare data specialist",
    "healthcare systems specialist",
    "provider data specialist",
    "payer data specialist",
    "eligibility data specialist",
    "revenue cycle data specialist",

    # Reporting/compliance data layer
    "reporting specialist",
    "operations reporting specialist",
    "business reporting specialist",
    "compliance data specialist",
    "audit data specialist",
    "quality data specialist"
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

def generate_contract_terms(terms):
    contract_terms = []
    for term in terms:
        for modifier in contract_modifiers:
            contract_terms.append(f"{term} {modifier}")
    return contract_terms


def unique_terms(terms):
    seen = set()
    unique = []
    for term in terms:
        normalized = term.strip().lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(term)
    return unique


def cache_key(term, lane, site_name, results_wanted, hours_old):
    payload = {
        "term": term.strip().lower(),
        "lane": lane,
        "sites": normalize_sites(site_name),
        "results_wanted": results_wanted,
        "hours_old": hours_old,
        "linkedin_fetch_description": LINKEDIN_FETCH_DESCRIPTION,
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def cache_path(term, lane, site_name, results_wanted, hours_old):
    return os.path.join(
        CACHE_DIR,
        f"{lane}-{cache_key(term, lane, site_name, results_wanted, hours_old)}.json",
    )


def load_cached_jobs(term, lane, site_name, results_wanted, hours_old):
    if not CACHE_ENABLED:
        return None

    path = cache_path(term, lane, site_name, results_wanted, hours_old)
    if not os.path.exists(path):
        return None

    age_hours = (time.time() - os.path.getmtime(path)) / 3600
    if age_hours > CACHE_TTL_HOURS:
        log_progress(
            "cache_stale",
            term=term,
            lane=lane,
            sites=normalize_sites(site_name),
            cache_age_hours=round(age_hours, 2),
            cache_ttl_hours=CACHE_TTL_HOURS,
        )
        return None

    try:
        with open(path, "r", encoding="utf-8") as cache_file:
            jobs = json.load(cache_file)
    except (OSError, json.JSONDecodeError):
        log_progress(
            "cache_read_failed",
            term=term,
            lane=lane,
            sites=normalize_sites(site_name),
            cache_path=path,
        )
        return None

    print(f"Using cached {lane.upper()} jobs for term '{term}': {len(jobs)}")
    log_progress(
        "cache_hit",
        term=term,
        lane=lane,
        sites=normalize_sites(site_name),
        job_count=len(jobs),
        cache_age_hours=round(age_hours, 2),
    )
    return jobs


def save_cached_jobs(term, lane, site_name, results_wanted, hours_old, jobs):
    if not CACHE_ENABLED:
        return

    os.makedirs(CACHE_DIR, exist_ok=True)
    path = cache_path(term, lane, site_name, results_wanted, hours_old)
    try:
        with open(path, "w", encoding="utf-8") as cache_file:
            json.dump(jobs, cache_file, ensure_ascii=True, default=str)
    except OSError as e:
        print(f"Unable to write cache for '{term}' ({lane}): {e}")
        log_progress(
            "cache_write_failed",
            term=term,
            lane=lane,
            sites=normalize_sites(site_name),
            error_type=type(e).__name__,
            error_message=str(e),
        )
        return

    log_progress(
        "cache_write",
        term=term,
        lane=lane,
        sites=normalize_sites(site_name),
        job_count=len(jobs),
        cache_path=path,
    )


def run_scrape_tasks(tasks, max_workers=MAX_TERM_WORKERS):
    if not tasks:
        return []

    started_at = time.perf_counter()
    if max_workers <= 1:
        results = []
        log_progress(
            "task_batch_started",
            task_count=len(tasks),
            max_workers=max_workers,
            lanes=sorted({task["lane"] for task in tasks}),
        )
        for task in tasks:
            results.extend(scrape_term(**task))
        log_progress(
            "task_batch_completed",
            task_count=len(tasks),
            max_workers=max_workers,
            job_count=len(results),
            duration_seconds=round(time.perf_counter() - started_at, 2),
        )
        return results

    jobs = []
    workers = min(max_workers, len(tasks))
    print(f"Scraping {len(tasks)} term/lane combinations with {workers} workers")
    log_progress(
        "task_batch_started",
        task_count=len(tasks),
        max_workers=workers,
        lanes=sorted({task["lane"] for task in tasks}),
    )
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_task = {executor.submit(scrape_term, **task): task for task in tasks}
        for future in as_completed(future_to_task):
            task = future_to_task[future]
            try:
                jobs.extend(future.result())
            except Exception as e:
                print(
                    f"Term failed for '{task['term']}' ({task['lane']}): "
                    f"{type(e).__name__}: {e}"
                )
                log_progress(
                    "term_failed",
                    term=task["term"],
                    lane=task["lane"],
                    sites=normalize_sites(task.get("site_name")),
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
    log_progress(
        "task_batch_completed",
        task_count=len(tasks),
        max_workers=workers,
        job_count=len(jobs),
        duration_seconds=round(time.perf_counter() - started_at, 2),
    )
    return jobs


def add_tasks(
    tasks,
    terms,
    lane,
    results_wanted,
    hours_old=24,
    site_name=None,
    proxies=None,
    seen_terms=None,
):
    for term in unique_terms(terms):
        normalized = term.strip().lower()
        if seen_terms is not None:
            if normalized in seen_terms:
                print(f"Skipping duplicate term '{term}' for lane '{lane}'")
                continue
            seen_terms.add(normalized)

        tasks.append(
            {
                "term": term,
                "lane": lane,
                "results_wanted": results_wanted,
                "site_name": site_name,
                "hours_old": hours_old,
                "proxies": proxies,
            }
        )


def scrape_term(term, lane, results_wanted, site_name=None, hours_old=24, proxies=None):
    if site_name is None:
        site_name = ["indeed", "linkedin", "google"]

    started_at = time.perf_counter()
    log_progress(
        "term_started",
        term=term,
        lane=lane,
        sites=normalize_sites(site_name),
        results_wanted=results_wanted,
        hours_old=hours_old,
        cache_enabled=CACHE_ENABLED,
    )

    cached_jobs = load_cached_jobs(term, lane, site_name, results_wanted, hours_old)
    if cached_jobs is not None:
        log_progress(
            "term_completed",
            term=term,
            lane=lane,
            sites=normalize_sites(site_name),
            job_count=len(cached_jobs),
            cached=True,
            duration_seconds=round(time.perf_counter() - started_at, 2),
        )
        return cached_jobs

    jobs = scrape_site_term(
        term,
        lane,
        results_wanted,
        site_name=site_name,
        hours_old=hours_old,
        proxies=proxies,
    )
    save_cached_jobs(term, lane, site_name, results_wanted, hours_old, jobs)
    log_progress(
        "term_completed",
        term=term,
        lane=lane,
        sites=normalize_sites(site_name),
        job_count=len(jobs),
        cached=False,
        duration_seconds=round(time.perf_counter() - started_at, 2),
    )
    return jobs

def normalize_sites(site_name):
    if isinstance(site_name, str):
        return [site_name]

    return list(site_name or [])


def failed_site(error, sites):
    message = str(error).lower()
    failure_reasons = {
        "rate limited": ("429", "too many", "/sorry/"),
        "timed out": ("timed out", "timeout", "read timed out"),
        "connection failed": (
            "connection error",
            "connection aborted",
            "connection reset",
            "proxyerror",
            "ssl",
            "handshake",
        ),
    }
    failure_reason = None
    for reason, patterns in failure_reasons.items():
        if any(pattern in message for pattern in patterns):
            failure_reason = reason
            break

    if failure_reason is None:
        return None

    site_patterns = {
        "google": ("google.com", "www.google.com", "/sorry/", "google"),
        "linkedin": ("linkedin.com", "www.linkedin.com", "linkedin"),
        "indeed": ("indeed.com", "apis.indeed.com", "www.indeed.com", "indeed"),
    }

    for site in sites:
        for pattern in site_patterns.get(site, (site,)):
            if pattern in message:
                return site, failure_reason

    return None


def scrape_jobs_with_site_fallback(
    term, lane, site_name, results_wanted, hours_old=24, proxies=None
):
    sites = normalize_sites(site_name)
    scrape_args = dict(
        search_term=term,
        google_search_term=f"{term} jobs since the past 1 days in Texas",
        location="Texas",
        results_wanted=results_wanted,
        hours_old=hours_old,
        country_indeed="USA",
        linkedin_fetch_description=LINKEDIN_FETCH_DESCRIPTION,
        proxies=proxies,
    )

    try:
        jobs = scrape_jobs(site_name=sites, **scrape_args)
        log_progress(
            "combined_scrape_completed",
            term=term,
            lane=lane,
            sites=sites,
            job_count=len(jobs),
        )
        return jobs, sites
    except Exception as e:
        print(
            f"Combined scrape failed for '{term}' ({lane}); "
            f"retrying sites individually: {type(e).__name__}: {e}"
        )
        log_progress(
            "combined_scrape_failed",
            term=term,
            lane=lane,
            sites=sites,
            error_type=type(e).__name__,
            error_message=str(e),
        )

    jobs_by_site = []
    scraped_sites = []

    for site in sites:
        try:
            site_jobs = scrape_jobs(site_name=site, **scrape_args)
        except Exception as e:
            print(
                f"{site} failed for '{term}' ({lane}); skipping site: "
                f"{type(e).__name__}: {e}"
            )
            log_progress(
                "site_scrape_failed",
                term=term,
                lane=lane,
                site=site,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            continue

        jobs_by_site.append(site_jobs)
        scraped_sites.append(site)
        log_progress(
            "site_scrape_completed",
            term=term,
            lane=lane,
            site=site,
            job_count=len(site_jobs),
        )

    if not jobs_by_site:
        log_progress("all_sites_failed", term=term, lane=lane, sites=sites)
        return pd.DataFrame(), scraped_sites

    return pd.concat(jobs_by_site, ignore_index=True), scraped_sites


def scrape_site_term(
    term, lane, results_wanted, site_name=None, hours_old=24, proxies=None
):
    contract_search = "jobs since the past 1 days in Texas"
    jobs, scraped_sites = scrape_jobs_with_site_fallback(
        term,
        lane,
        site_name,
        results_wanted,
        hours_old,
        proxies,
    )

    jobs["search_lane"] = lane
    jobs["search_term_used"] = term
    print(f"Found {lane.upper()} jobs for term '{term}' on {scraped_sites}: {len(jobs)}")
    log_progress(
        "term_results_found",
        term=term,
        lane=lane,
        sites=scraped_sites,
        job_count=len(jobs),
    )
    return jobs.to_dict(orient="records")

def scrape_ziprecruiter_term(term, lane, results_wanted, hours_old=24, proxies=None):
    return scrape_site_term(
        term,
        lane,
        results_wanted,
        site_name=["zip_recruiter"],
        proxies=proxies,
        hours_old=hours_old
    )

#TESTING, only need one job in csv for now
# contract_core_terms = generate_contract_terms(core_terms)
# contract_secondary_terms = generate_contract_terms(secondary_terms)
# contract_bridge_terms = generate_contract_terms(bridge_roles)
# contract_survival_terms = generate_contract_terms(survival_terms)

if ANALYZE_MODE:
    filename = "market_analysis_" + date + ".csv"

log_progress(
    "run_started",
    output_csv=filename,
    analyze_mode=ANALYZE_MODE,
    fallback=FALLBACK,
    contract_only=CONTRACT_ONLY,
    ziprecruiter_only=ZIPRECRUITER_ONLY,
    qualification_search=QUALIFICATION_SEARCH,
    max_term_workers=MAX_TERM_WORKERS,
    cache_enabled=CACHE_ENABLED,
    cache_ttl_hours=CACHE_TTL_HOURS,
    log_path=progress_log.path,
)
    
# -----------------------
# NORMAL SCRAPE
# -----------------------

if not ZIPRECRUITER_ONLY:

    if ANALYZE_MODE:
        scrape_tasks = []
        add_tasks(
            scrape_tasks,
            market_analysis,
            "market_analysis",
            hours_old=24 * 14,
            results_wanted=100,
            proxies=proxies,
        )
        all_jobs.extend(run_scrape_tasks(scrape_tasks))
    
    elif CONTRACT_ONLY:#ONLY scrape contract roles
        print("Running CONTRACT ONLY mode")
        scrape_tasks = []
        seen_terms = set()

        add_tasks(
            scrape_tasks,
            contract_core_terms,
            "contract_core",
            hours_old=24,
            results_wanted=80,
            proxies=proxies,
            seen_terms=seen_terms,
        )

        add_tasks(
            scrape_tasks,
            contract_secondary_terms,
            "contract_secondary",
            hours_old=24,
            results_wanted=40,
            proxies=proxies,
            seen_terms=seen_terms,
        )

        if FALLBACK:
            add_tasks(
                scrape_tasks,
                contract_bridge_terms,
                "contract_bridge",
                hours_old=24,
                results_wanted=100,
                proxies=proxies,
                seen_terms=seen_terms,
            )

        all_jobs.extend(run_scrape_tasks(scrape_tasks))
    
    else:
        scrape_tasks = []
        seen_terms = set()

        add_tasks(
            scrape_tasks,
            core_terms,
            "core",
            hours_old=24,
            results_wanted=120,
            proxies=proxies,
            seen_terms=seen_terms,
        )

        if QUALIFICATION_SEARCH:
            print("Adding QUALIFICATION scrape layer")
            add_tasks(
                scrape_tasks,
                qualification_terms,
                "qualification",
                hours_old=24,
                results_wanted=1,
                proxies=proxies,
                seen_terms=seen_terms,
            )

        add_tasks(
            scrape_tasks,
            secondary_terms,
            "secondary",
            hours_old=24,
            results_wanted=1,
            proxies=proxies,
            seen_terms=seen_terms,
        )

        if FALLBACK:
            add_tasks(
                scrape_tasks,
                bridge_roles,
                "bridge",
                hours_old=24,
                results_wanted=1,
                proxies=proxies,
                seen_terms=seen_terms,
            )
            
            # add_tasks(
            #     scrape_tasks,
            #     survival_terms,
            #     "survival",
            #     hours_old=24,
            #     results_wanted=1,
            #     proxies=proxies,
            #     seen_terms=seen_terms,
            # )

        #RUN CONTRACT ALONGSIDE NORMAL TERMS
        ''' 
        skip contract scrape for now, now in final phase of job search, but leaving code here for future use if needed
        print("Running CONTRACT scrape layer")

        add_tasks(
            scrape_tasks,
            contract_core_terms,
            "contract_core",
            hours_old=24,
            results_wanted=80,
            proxies=proxies,
            seen_terms=seen_terms,
        )

        add_tasks(
            scrape_tasks,
            contract_secondary_terms,
            "contract_secondary",
            hours_old=24,
            results_wanted=40,
            proxies=proxies,
            seen_terms=seen_terms,
        )

        if FALLBACK:
            add_tasks(
                scrape_tasks,
                contract_bridge_terms,
                "contract_bridge",
                hours_old=24,
                results_wanted=100,
                proxies=proxies,
                seen_terms=seen_terms,
            )
            
            add_tasks(
                scrape_tasks,
                contract_survival_terms,
                "contract_survival",
                hours_old=24,
                results_wanted=30,
                proxies=proxies,
                seen_terms=seen_terms,
            )
    '''
        all_jobs.extend(run_scrape_tasks(scrape_tasks))
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
            log_progress(
                "term_failed",
                term=term,
                lane=lane,
                sites=["zip_recruiter"],
                error_type=type(e).__name__,
                error_message=str(e),
            )

        time.sleep(ZIPRECRUITER_TERM_DELAY)

# -----------------------
# POST PROCESSING
# -----------------------

jobs = pd.DataFrame(all_jobs)
jobs = jobs.dropna(how="all")

if jobs.empty:
    print("No jobs found.")
    jobs.to_csv(filename, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
    log_progress("run_completed", output_csv=filename, raw_count=0, final_count=0)

else:
    raw_count = len(jobs)
    dedupe_passes = []
    if "job_url" in jobs.columns:
        dedupe_passes.append(["job_url"])
    if "id" in jobs.columns:
        dedupe_passes.append(["id"])
    if all(
        column in jobs.columns
        for column in ["title", "company", "location", "description"]
    ):
        dedupe_passes.append(["title", "company", "location", "description"])

    for dedupe_subset in dedupe_passes:
        complete_key = jobs[dedupe_subset].notna().all(axis=1)
        keyed_jobs = jobs[complete_key].drop_duplicates(subset=dedupe_subset)
        jobs = pd.concat([keyed_jobs, jobs[~complete_key]], ignore_index=True)

    print(
        f"Removed {raw_count - len(jobs)} duplicate rows using "
        f"{' then '.join(', '.join(columns) for columns in dedupe_passes)}"
    )
    log_progress(
        "dedupe_completed",
        raw_count=raw_count,
        final_count=len(jobs),
        duplicates_removed=raw_count - len(jobs),
        dedupe_passes=dedupe_passes,
    )

    jobs["review_priority"] = jobs["search_lane"].map({
        "core": 1,
        "contract_core": 1,
        "qualification": 2,
        "secondary": 3,
        "contract_secondary": 3,
        "bridge": 4,
        "contract_bridge": 4,
        "survival": 5,
        "contract_survival": 5
    })

    sort_cols = ["review_priority"]

    if "date_posted" in jobs.columns:
        sort_cols.append("date_posted")


    ascending = [True] + ([False] if "date_posted" in sort_cols else [])
    jobs = jobs.sort_values(by=sort_cols, ascending=ascending)
    jobs.to_csv(filename, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)


    print(f"Saved prioritized jobs to {filename}")
    log_progress(
        "run_completed",
        output_csv=filename,
        raw_count=raw_count,
        final_count=len(jobs),
        duplicates_removed=raw_count - len(jobs),
    )
    
