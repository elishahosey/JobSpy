import argparse
import csv
import os
import time
from datetime import datetime

import pandas as pd
from jobspy import scrape_jobs

r'''
Last-resort / fallback job scraper.

Updated fallback order after the trade scrape:
1. IT infrastructure / technical operations bridge roles
2. Automation / PLC / SCADA / BAS / Controls Technician
3. Electronics Repair / Field Service Technician
4. Industrial Maintenance / Mechatronics Technician, only if paid training or controls exposure exists
5. Electrical Apprentice / Electrician, emergency trade backup only

Purpose:
Scrape fallback roles while the main backend/data/integration job search continues. The
newfound insight is that trade/technician work is usually more physical, credential-heavy,
and field-service-heavy than tech bridge roles. So this scraper now prioritizes IT
infrastructure / technical operations first, then treats automation/electronics/trade lanes
as deeper fallbacks. The goal is not to abandon tech. The goal is to find paid, technical,
short-ramp paths that preserve troubleshooting, systems thinking, documentation, and
resume continuity.

Run with the project venv:
    .\.venv-jobspy\Scripts\python.exe .\lastresort_joblist.py

Run one lane:
    .\.venv-jobspy\Scripts\python.exe .\lastresort_joblist.py --lanes it_infra_support
    .\.venv-jobspy\Scripts\python.exe .\lastresort_joblist.py --lanes automation_controls
    .\.venv-jobspy\Scripts\python.exe .\lastresort_joblist.py --lanes electronics_repair
    .\.venv-jobspy\Scripts\python.exe .\lastresort_joblist.py --lanes industrial_maintenance
    .\.venv-jobspy\Scripts\python.exe .\lastresort_joblist.py --lanes electrical_apprentice

Include entry-level / trainee / apprentice variants:
    .\.venv-jobspy\Scripts\python.exe .\lastresort_joblist.py --include-modified-terms

Inspect filtered noise too:
    .\.venv-jobspy\Scripts\python.exe .\lastresort_joblist.py --keep-noisy

Use proxy:
    set JOBSPY_PROXY=http://user:pass@host:port
    .\.venv-jobspy\Scripts\python.exe .\lastresort_joblist.py

Or:
    .\.venv-jobspy\Scripts\python.exe .\lastresort_joblist.py --proxy http://user:pass@host:port

Notes:
- Scrapes WILL grab unrelated roles.
- Guardrails flag and optionally remove noise, senior roles, nontechnical roles, and school-heavy paths.
- Use --keep-noisy if the guardrails are too aggressive and you want to audit what was removed.
'''

now = datetime.now()
date = f"{now.month}-{now.day}-{now.strftime('%y')}"
DEFAULT_FILENAME = "lastresort-jobs-" + date + ".csv"

DEFAULT_SITE_NAMES = ["indeed", "linkedin", "google"]
DEFAULT_LOCATION = "Texas"
DEFAULT_HOURS_OLD = 168

PROXY_ENV_VARS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]
JOBSPY_PROXY_ENV_VAR = "JOBSPY_PROXY"

CSV_COLUMNS = [
    "id",
    "site",
    "job_url",
    "job_url_direct",
    "title",
    "company",
    "location",
    "date_posted",
    "job_type",
    "salary_source",
    "interval",
    "min_amount",
    "max_amount",
    "currency",
    "is_remote",
    "job_level",
    "job_function",
    "listing_type",
    "emails",
    "description",
    "company_industry",
    "company_url",
    "company_logo",
    "company_url_direct",
    "company_addresses",
    "company_num_employees",
    "company_revenue",
    "company_description",
    "skills",
    "experience_range",
    "company_rating",
    "company_reviews_count",
    "vacancy_count",
    "work_from_home_type",
    "search_lane",
    "search_term_used",
    "review_priority",
    "plan_c_status",
    "ai_resistance",
    "current_resume_viability",
    "entry_path_signal",
    "training_signal",
    "lane_match_score",
    "positive_signals",
    "risk_signals",
    "guardrail_status",
    "guardrail_reason",
    "review_notes",
]

SEARCH_LANES = {
    "it_infra_support": {
        "priority": 1,
        "plan_c_status": "technical_bridge_first",
        "ai_resistance": "medium_high",
        "current_resume_viability": "plausible_bridge",
        "results_wanted": 80,
        "terms": [
            "data center technician",
            "datacenter technician",
            "noc technician",
            "network operations technician",
            "systems support technician",
            "technical operations technician",
            "technical operations engineer sql",
            "application support analyst sql",
            "production support analyst sql",
            "IT support specialist SQL",
            "desktop support technician SQL",
            "field IT technician",
            "hardware support technician",
            "junior system administrator",
            "cloud support engineer sql",
        ],
    },
    "automation_controls": {
        "priority": 2,
        "plan_c_status": "physical_technical_fallback",
        "ai_resistance": "very_high",
        "current_resume_viability": "training_needed",
        "results_wanted": 70,
        "terms": [
            "automation technician",
            "controls technician",
            "PLC technician",
            "SCADA technician",
            "BAS technician",
            "building automation technician",
            "electro mechanical technician",
            "electromechanical technician",
            "field service technician PLC",
            "industrial automation technician",
            "control systems technician",
            "instrumentation technician",
            "mechatronics technician",
            "HMI technician",
            "junior controls technician",
            "controls technician trainee",
            "automation field service technician",
            "systems integrator junior PLC",
        ],
    },
    "electronics_repair": {
        "priority": 3,
        "plan_c_status": "physical_technical_backup",
        "ai_resistance": "high",
        "current_resume_viability": "research_only",
        "results_wanted": 60,
        "terms": [
            "electronics technician",
            "electrical technician",
            "field service technician electronics",
            "industrial electronics technician",
            "commercial equipment repair technician",
            "electrical electronics repairer",
            "electronic repair technician",
            "equipment repair technician electronics",
            "field service technician equipment repair",
        ],
    },
    "industrial_maintenance": {
        "priority": 4,
        "plan_c_status": "conditional_physical_fallback",
        "ai_resistance": "high",
        "current_resume_viability": "training_needed",
        "results_wanted": 50,
        "terms": [
            "industrial maintenance technician PLC",
            "industrial maintenance apprentice",
            "mechatronics technician",
            "maintenance technician manufacturing PLC",
            "equipment maintenance technician PLC",
            "manufacturing maintenance technician controls",
            "maintenance technician trainee manufacturing",
            "electro mechanical maintenance technician",
            "industrial machinery maintenance apprentice",
        ],
    },
    "electrical_apprentice": {
        "priority": 5,
        "plan_c_status": "emergency_trade_backup",
        "ai_resistance": "very_high",
        "current_resume_viability": "apprenticeship_needed",
        "results_wanted": 40,
        "terms": [
            "electrical apprentice",
            "electrician apprentice",
            "low voltage technician apprentice",
            "low voltage technician trainee",
            "controls electrician apprentice",
            "industrial electrician apprentice",
            "apprentice electrician paid training",
        ],
    },
}
ENTRY_MODIFIERS = [
    "trainee",
    "entry level",
    "apprentice",
    "junior",
    "no experience",
    "paid training",
]

HARD_NOISE_TITLE_TERMS = [
    "driver",
    "delivery",
    "courier",
    "cashier",
    "retail",
    "sales associate",
    "sales representative",
    "inside sales",
    "outside sales",
    "warehouse picker",
    "warehouse associate",
    "package handler",
    "restaurant",
    "server",
    "host",
    "hostess",
    "cook",
    "crew member",
    "fast food",
    "movie theater",
    "call center",
    "customer service representative",
    "front desk",
    "receptionist",
    "pharmacy technician",
    "pharmacy tech",
    "tire technician",
    "lube technician",
    "automotive service advisor",
    "pest control",
    "janitor",
    "custodian",
    "housekeeper",
    "floor technician",
    "production operator",
    "machine operator",
    "forklift operator",
    "bmet",
    "biomedical equipment",
]

SOFT_NOISE_TITLE_TERMS = [
    "coordinator",
    "assistant",
    "clerk",
    "specialist",
    "aide",
    "operator",
    "helper",
]

SCHOOL_HEAVY_TERMS = [
    "associate degree required",
    "degree required",
    "certificate required",
    "certification required",
    "journeyman required",
    "licensed electrician required",
    "electrician license required",
    "state license required",
    "bmet degree",
    "biomedical equipment technology",
]

ENTRY_PATH_TERMS = [
    "entry level",
    "trainee",
    "apprentice",
    "paid training",
    "training provided",
    "no experience",
    "junior",
    "willing to train",
    "learn",
    "apprenticeship",
]

TRAINING_GATE_TERMS = [
    "2 years experience required",
    "3 years experience required",
    "5 years experience required",
    "5+ years",
    "journeyman",
    "licensed",
    "certification required",
    "strong plc experience",
    "commissioning experience required",
    "terraform",
    "kubernetes",
    "platform ownership",
    "cloud architecture",
]

POSITIVE_TITLE_TERMS_BY_LANE = {
    "it_infra_support": [
        "data center",
        "datacenter",
        "noc",
        "network operations",
        "systems support",
        "technical operations",
        "application support",
        "production support",
        "it support",
        "desktop support",
        "field it",
        "hardware support",
        "system administrator",
        "cloud support",
    ],
    "automation_controls": [
        "automation technician",
        "controls technician",
        "plc",
        "scada",
        "bas technician",
        "building automation",
        "control systems",
        "industrial automation",
        "instrumentation",
        "mechatronics",
        "hmi",
        "systems integrator",
        "electro mechanical",
        "electromechanical",
    ],
    "electronics_repair": [
        "electronics technician",
        "electrical technician",
        "field service",
        "industrial electronics",
        "equipment repair",
        "electronic repair",
        "repair technician",
        "instrumentation technician",
        "electro mechanical",
        "electromechanical",
    ],
    "industrial_maintenance": [
        "industrial maintenance",
        "maintenance technician",
        "mechatronics",
        "electro mechanical",
        "electromechanical",
        "equipment maintenance",
        "manufacturing maintenance",
    ],
    "electrical_apprentice": [
        "electrical apprentice",
        "electrician apprentice",
        "low voltage",
        "apprentice electrician",
        "controls electrician",
        "industrial electrician apprentice",
    ],
}

POSITIVE_DESCRIPTION_TERMS_BY_LANE = {
    "it_infra_support": [
        "troubleshoot",
        "ticket",
        "incident",
        "root cause",
        "monitoring",
        "logs",
        "active directory",
        "windows server",
        "linux",
        "server",
        "network",
        "vpn",
        "hardware",
        "desktop",
        "endpoint",
        "imaging",
        "sql",
        "api",
        "application support",
        "production support",
        "data center",
        "datacenter",
        "noc",
    ],
    "automation_controls": [
        "plc",
        "scada",
        "hmi",
        "automation",
        "controls",
        "control systems",
        "ladder logic",
        "sensors",
        "actuators",
        "motor controls",
        "bas",
        "building automation",
        "bacnet",
        "control panel",
        "instrumentation",
        "troubleshoot",
        "schematic",
        "electrical",
        "diagnostic",
    ],
    "electronics_repair": [
        "electronics",
        "electrical",
        "troubleshoot",
        "diagnostic",
        "repair",
        "maintenance",
        "schematic",
        "multimeter",
        "calibration",
        "equipment",
        "testing",
        "field service",
    ],
    "industrial_maintenance": [
        "maintenance",
        "preventive maintenance",
        "troubleshoot",
        "diagnostic",
        "plc",
        "controls",
        "sensors",
        "motors",
        "hydraulics",
        "pneumatics",
        "schematic",
        "equipment",
        "manufacturing",
    ],
    "electrical_apprentice": [
        "apprentice",
        "electrical",
        "wiring",
        "conduit",
        "low voltage",
        "control panel",
        "schematic",
        "safety",
        "training",
    ],
}

ROLE_IDENTITY_RISK_TERMS = [
    "senior controls engineer",
    "lead controls engineer",
    "principal controls engineer",
    "controls engineer iii",
    "controls engineer iv",
    "automation engineer iii",
    "automation engineer iv",
    "process controls engineer",
    "i&c engineer",
    "instrumentation and controls engineer",
    "electrical engineer iii",
    "electrical engineer iv",
    "controls manager",
    "automation manager",
    "project manager",
    "plc programmer",
    "commissioning engineer",
    "dcs engineer",
    "sis engineer",
]

GENERIC_FIELD_SERVICE_SUPPORT_TERMS = [
    "equipment",
    "electronics",
    "electrical",
    "instrumentation",
    "repair",
    "diagnostic",
    "maintenance",
    "automation",
    "controls",
    "plc",
    "scada",
    "hmi",
    "bas",
    "sensor",
    "motor",
]


def normalize_text(value):
    if pd.isna(value):
        return ""
    return str(value).lower()


def base_lane(search_lane):
    if not isinstance(search_lane, str):
        return ""
    return search_lane.removesuffix("_modified").removesuffix("_ziprecruiter")


def lane_config(search_lane):
    return SEARCH_LANES.get(base_lane(search_lane), {})


def priority_for_lane(search_lane):
    return lane_config(search_lane).get("priority", 99)


def contains_any(text, terms):
    return any(term in text for term in terms)


def matching_terms(text, terms):
    return [term for term in terms if term in text]


def generate_modified_terms(terms):
    modified_terms = []
    for term in terms:
        for modifier in ENTRY_MODIFIERS:
            modified_terms.append(f"{term} {modifier}")
    return modified_terms


def build_google_search_term(term, location, hours_old):
    days_old = max(1, round(hours_old / 24))
    return f"{term} jobs since the past {days_old} days in {location}"


def normalize_site_names(site_name):
    if site_name is None:
        return DEFAULT_SITE_NAMES
    if isinstance(site_name, str):
        return [site_name]
    return site_name


def clear_environment_proxies():
    cleared = [var for var in PROXY_ENV_VARS if os.environ.pop(var, None)]
    if cleared:
        print(f"Ignoring environment proxy settings for this run: {', '.join(cleared)}")


def selected_proxies(args):
    proxy = args.proxy or os.environ.get(JOBSPY_PROXY_ENV_VAR)
    if not proxy:
        return None
    print("Using explicit scraper proxy from --proxy or JOBSPY_PROXY")
    return [proxy]


def selected_lanes(args):
    if not args.lanes:
        return SEARCH_LANES
    invalid_lanes = [lane for lane in args.lanes if lane not in SEARCH_LANES]
    if invalid_lanes:
        valid_lanes = ", ".join(SEARCH_LANES.keys())
        raise ValueError(f"Invalid lane(s): {', '.join(invalid_lanes)}. Valid lanes: {valid_lanes}")
    return {lane: SEARCH_LANES[lane] for lane in args.lanes}


def title_has_positive_signal(title, lane):
    return contains_any(title, POSITIVE_TITLE_TERMS_BY_LANE.get(base_lane(lane), []))


def description_positive_terms(description, lane):
    return matching_terms(description, POSITIVE_DESCRIPTION_TERMS_BY_LANE.get(base_lane(lane), []))


def scrape_site_term(term, lane, results_wanted, site_name=None, location=DEFAULT_LOCATION, hours_old=DEFAULT_HOURS_OLD, proxies=None):
    all_records = []
    for site in normalize_site_names(site_name):
        try:
            jobs = scrape_jobs(
                site_name=[site],
                search_term=term,
                google_search_term=build_google_search_term(term, location, hours_old),
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed="USA",
                linkedin_fetch_description=True,
                proxies=proxies,
            )
        except Exception as exc:
            print(f"{site} failed for '{term}' ({lane}): {exc}")
            continue

        if jobs is None or jobs.empty:
            print(f"Found {lane.upper()} jobs for term '{term}' on {site}: 0")
            continue

        jobs["search_lane"] = lane
        jobs["search_term_used"] = term
        print(f"Found {lane.upper()} jobs for term '{term}' on {site}: {len(jobs)}")
        all_records.extend(jobs.to_dict(orient="records"))
    return all_records


def scrape_lanes(args):
    all_jobs = []
    scraper_proxies = selected_proxies(args)
    lanes_to_scrape = selected_lanes(args)

    for lane, config in lanes_to_scrape.items():
        for term in config["terms"]:
            all_jobs.extend(
                scrape_site_term(
                    term=term,
                    lane=lane,
                    results_wanted=config["results_wanted"],
                    location=args.location,
                    hours_old=args.hours_old,
                    proxies=scraper_proxies,
                )
            )
            time.sleep(args.term_delay)

    if args.include_modified_terms:
        print("Running modified entry-level/trainee term scrape layer")
        for lane, config in lanes_to_scrape.items():
            for term in generate_modified_terms(config["terms"]):
                all_jobs.extend(
                    scrape_site_term(
                        term=term,
                        lane=f"{lane}_modified",
                        results_wanted=max(15, config["results_wanted"] // 2),
                        location=args.location,
                        hours_old=args.hours_old,
                        proxies=scraper_proxies,
                    )
                )
                time.sleep(args.term_delay)

    return all_jobs


def classify_entry_path(row):
    combined = " ".join([
        normalize_text(row.get("title")),
        normalize_text(row.get("description")),
        normalize_text(row.get("experience_range")),
        normalize_text(row.get("job_level")),
    ])
    found = matching_terms(combined, ENTRY_PATH_TERMS)
    return "possible_entry_path: " + "; ".join(found[:6]) if found else "unclear"


def classify_training_gate(row):
    combined = " ".join([
        normalize_text(row.get("title")),
        normalize_text(row.get("description")),
        normalize_text(row.get("experience_range")),
        normalize_text(row.get("job_level")),
    ])
    found = matching_terms(combined, TRAINING_GATE_TERMS + SCHOOL_HEAVY_TERMS)
    return "possible_gate: " + "; ".join(found[:6]) if found else "not_obvious"


def score_lane_match(row):
    title = normalize_text(row.get("title"))
    description = normalize_text(row.get("description"))
    lane = normalize_text(row.get("search_lane"))

    score = 0
    positives = []

    title_hits = matching_terms(title, POSITIVE_TITLE_TERMS_BY_LANE.get(base_lane(lane), []))
    desc_hits = description_positive_terms(description, lane)

    if title_hits:
        score += 3
        positives.extend(["title:" + term for term in title_hits[:5]])
    if desc_hits:
        score += min(5, len(desc_hits))
        positives.extend(["desc:" + term for term in desc_hits[:8]])

    entry_hits = matching_terms(description, ENTRY_PATH_TERMS)
    if entry_hits:
        score += 2
        positives.extend(["entry:" + term for term in entry_hits[:4]])

    return score, positives


def classify_guardrail(row):
    title = normalize_text(row.get("title"))
    description = normalize_text(row.get("description"))
    combined = f"{title} {description}"
    lane = normalize_text(row.get("search_lane"))

    score, positives = score_lane_match(row)
    risks = []

    hard_noise_hits = matching_terms(title, HARD_NOISE_TITLE_TERMS)
    if hard_noise_hits:
        risks.extend(["hard_noise_title:" + term for term in hard_noise_hits[:5]])
        return "exclude_noise", "; ".join(risks), score, positives, risks

    role_identity_hits = matching_terms(title, ROLE_IDENTITY_RISK_TERMS)
    if role_identity_hits:
        risks.extend(["senior_or_engineering_identity:" + term for term in role_identity_hits[:5]])
        return "exclude_role_identity", "; ".join(risks), score, positives, risks

    school_hits = matching_terms(combined, SCHOOL_HEAVY_TERMS)
    if school_hits and not matching_terms(combined, ENTRY_PATH_TERMS):
        risks.extend(["school_or_license_gate:" + term for term in school_hits[:5]])
        return "exclude_gate", "; ".join(risks), score, positives, risks

    soft_noise_hits = matching_terms(title, SOFT_NOISE_TITLE_TERMS)
    if soft_noise_hits and score < 3:
        risks.extend(["soft_noise_low_signal:" + term for term in soft_noise_hits[:5]])
        return "exclude_low_signal", "; ".join(risks), score, positives, risks

    if "field service" in title and not contains_any(combined, GENERIC_FIELD_SERVICE_SUPPORT_TERMS):
        risks.append("generic_field_service_without_equipment_or_controls_signal")
        return "exclude_generic_field_service", "; ".join(risks), score, positives, risks

    if base_lane(lane) == "it_infra_support":
        # Keep IT support only when it preserves a technical story: systems, tickets, logs,
        # infrastructure, application support, data center/NOC, SQL/API, or endpoint troubleshooting.
        if contains_any(title, ["help desk", "service desk", "desktop", "it support"]) and not contains_any(
            combined,
            [
                "sql", "api", "logs", "ticket", "incident", "root cause", "active directory",
                "vpn", "network", "server", "linux", "windows server", "data center",
                "datacenter", "noc", "application support", "production support", "endpoint",
                "imaging", "hardware troubleshooting",
            ],
        ):
            risks.append("generic_it_support_without_systems_or_data_signal")
            return "exclude_generic_it_support", "; ".join(risks), score, positives, risks

    if base_lane(lane) == "industrial_maintenance":
        if not contains_any(combined, ["plc", "controls", "electrical", "electronics", "schematic", "sensor", "motor", "mechatronics", "apprentice", "trainee"]):
            risks.append("generic_maintenance_without_controls_or_electrical_signal")
            return "exclude_generic_maintenance", "; ".join(risks), score, positives, risks

    if base_lane(lane) == "electrical_apprentice":
        if not contains_any(combined, ["apprentice", "trainee", "paid training", "training provided", "low voltage"]):
            risks.append("electrical_role_without_apprentice_or_training_signal")
            return "exclude_electrical_no_training_path", "; ".join(risks), score, positives, risks

    if score < 2:
        risks.append("low_lane_match_score")
        return "exclude_low_signal", "; ".join(risks), score, positives, risks

    return "keep", "", score, positives, risks


def build_review_notes(row):
    lane = normalize_text(row.get("search_lane"))
    status = row.get("guardrail_status", "")
    entry = row.get("entry_path_signal", "")
    training = row.get("training_signal", "")
    score = row.get("lane_match_score", "")

    notes = [f"lane={base_lane(lane)}", f"guardrail={status}", f"score={score}"]

    if "possible_entry_path" in str(entry):
        notes.append("entry_or_training_signal_present")
    if "possible_gate" in str(training):
        notes.append("training_or_experience_gate_possible")

    if base_lane(lane) == "it_infra_support":
        notes.append("preferred_before_trade_fallbacks_keep_if_systems_tickets_logs_data_or_infra")
    if base_lane(lane) == "automation_controls":
        notes.append("physical_technical_fallback_target_technician_side_not_controls_engineer")
    if base_lane(lane) == "industrial_maintenance":
        notes.append("keep_only_if_controls_or_electrical_skill_building")
    if base_lane(lane) == "electrical_apprentice":
        notes.append("emergency_backup_only")

    return "; ".join(notes)


def add_plan_c_fields(jobs):
    jobs["review_priority"] = jobs["search_lane"].map(priority_for_lane)
    jobs["plan_c_status"] = jobs["search_lane"].apply(lambda lane: lane_config(lane).get("plan_c_status", "unknown"))
    jobs["ai_resistance"] = jobs["search_lane"].apply(lambda lane: lane_config(lane).get("ai_resistance", "unknown"))
    jobs["current_resume_viability"] = jobs["search_lane"].apply(lambda lane: lane_config(lane).get("current_resume_viability", "unknown"))
    jobs["entry_path_signal"] = jobs.apply(classify_entry_path, axis=1)
    jobs["training_signal"] = jobs.apply(classify_training_gate, axis=1)

    guardrail_results = jobs.apply(classify_guardrail, axis=1)
    jobs["guardrail_status"] = guardrail_results.apply(lambda result: result[0])
    jobs["guardrail_reason"] = guardrail_results.apply(lambda result: result[1])
    jobs["lane_match_score"] = guardrail_results.apply(lambda result: result[2])
    jobs["positive_signals"] = guardrail_results.apply(lambda result: "; ".join(result[3]))
    jobs["risk_signals"] = guardrail_results.apply(lambda result: "; ".join(result[4]))
    jobs["review_notes"] = jobs.apply(build_review_notes, axis=1)

    return jobs


def write_jobs_csv(all_jobs, filename, keep_noisy=False):
    jobs = pd.DataFrame(all_jobs)

    if jobs.empty:
        jobs = pd.DataFrame(columns=CSV_COLUMNS)
        jobs.to_csv(filename, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        print("No jobs found.")
        return

    if "job_url" in jobs.columns:
        jobs = jobs.drop_duplicates(subset=["job_url"])
    elif "id" in jobs.columns:
        jobs = jobs.drop_duplicates(subset=["id"])
    else:
        jobs = jobs.drop_duplicates(subset=["title", "company", "location"])

    jobs = add_plan_c_fields(jobs)

    total_before_filter = len(jobs)
    if not keep_noisy:
        jobs = jobs[jobs["guardrail_status"] == "keep"].copy()
    total_after_filter = len(jobs)
    removed_count = total_before_filter - total_after_filter

    for column in CSV_COLUMNS:
        if column not in jobs.columns:
            jobs[column] = pd.NA

    extra_columns = [column for column in jobs.columns if column not in CSV_COLUMNS]
    jobs = jobs[CSV_COLUMNS + extra_columns]

    sort_cols = ["review_priority", "lane_match_score"]
    ascending = [True, False]
    if "date_posted" in jobs.columns:
        sort_cols.append("date_posted")
        ascending.append(False)

    jobs = jobs.sort_values(by=sort_cols, ascending=ascending)
    jobs.to_csv(filename, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)

    print(f"Saved prioritized Plan C jobs to {filename}")
    print(f"Rows before guardrail filter: {total_before_filter}")
    print(f"Rows after guardrail filter: {total_after_filter}")
    print(f"Rows removed by guardrails: {removed_count}")

    print("\nLane counts after filtering:")
    try:
        print(jobs["search_lane"].value_counts(dropna=False).to_string())
    except Exception:
        pass

    print("\nGuardrail status counts:")
    try:
        print(jobs["guardrail_status"].value_counts(dropna=False).to_string())
    except Exception:
        pass


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape guarded fallback jobs: IT infra/support first, then automation/PLC/BAS, electronics repair, industrial maintenance, and electrical apprenticeship."
    )
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--hours-old", type=int, default=DEFAULT_HOURS_OLD)
    parser.add_argument("--output", default=DEFAULT_FILENAME)
    parser.add_argument(
        "--lanes",
        nargs="+",
        choices=list(SEARCH_LANES.keys()),
        default=None,
        help="Optional lane filter.",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="Explicit proxy URL for scraping. Can also be set with JOBSPY_PROXY.",
    )
    parser.add_argument(
        "--include-modified-terms",
        action="store_true",
        help="Also search trainee, entry-level, apprentice, paid-training, and related variants.",
    )
    parser.add_argument(
        "--keep-noisy",
        action="store_true",
        help="Keep rows excluded by guardrails instead of filtering them out.",
    )
    parser.add_argument(
        "--term-delay",
        type=float,
        default=2.0,
        help="Delay between search terms to reduce rate-limit pressure.",
    )
    return parser.parse_args()


def main():
    clear_environment_proxies()
    args = parse_args()

    print("Starting guarded Plan C scrape")
    print(f"Location: {args.location}")
    print(f"Hours old: {args.hours_old}")
    print(f"Output: {args.output}")

    if args.lanes:
        print(f"Lanes: {', '.join(args.lanes)}")
    else:
        print("Lanes: IT infra/support + automation/PLC/BAS + electronics repair + industrial maintenance + electrical apprenticeship")

    if args.include_modified_terms:
        print("Modified entry-level/trainee terms enabled")

    all_jobs = scrape_lanes(args)
    write_jobs_csv(all_jobs, args.output, keep_noisy=args.keep_noisy)


if __name__ == "__main__":
    main()
