"""
Clean the job list by removing non-target jobs, duplicates, and irrelevant entries.
Reads raw job listings from jobs.csv, keeps relevant DE/backend-data/integration roles,
and saves the cleaned list to cleaned_jobs.csv with a fit bucket.

Fit buckets:
- apply  -> stronger fit, direct URL available
- review -> possible fit, needs manual review
- skip   -> not aligned enough
"""

import re
from datetime import datetime

import pandas as pd

now = datetime.now()
date = f"{now.month}-{now.day}-{now.strftime('%y')}"
filename = f"jobs-{date}.csv"
clean_filename = f"cleaned_jobs-{date}.csv"

jobs_df = pd.read_csv(filename)
jobs_df.columns = jobs_df.columns.str.strip().str.lower()

processed_count = len(jobs_df)
print(f"Total jobs before cleaning: {processed_count}")

FALLBACK = True  # Whether to include the fallback bridge roles in the initial scrape and analysis

bridge_roles = [
    "database engineer",
    "data migration engineer",
    "database engineer",#closest to your SQL + data validation strength
    "automation engineer data",  # keeps Python + scripting signal alive
    "systems analyst sql",
    "systems analyst data integration",
    "systems analyst etl",
    "application engineer data",
    "data analyst sql", #fallback, high volume, SQL-heavy
    "reporting analyst sql", #survival model for analytics-adjacent roles that still use SQL and may have some data engineering adjacent work

]

primary_keywords = [
    "data integration engineer",
    "data warehouse engineer",
    "big data engineer",
    "data engineer",
    "data platform engineer",
    "etl engineer",
    "etl developer",
    "analytics engineer",
    "data pipeline engineer",
    "integration engineer",
    "data developer",
    "sql developer",
    "data systems engineer",
    "data quality engineer",
    "data integration developer",
    "data operations engineer",
    "data ingestion engineer",
    "software engineer data engineering",
    "database developer",
]

secondary_keywords = [
    "backend engineer data",
    "backend software engineer data",
    "backend engineer",
    "software engineer data",
    "software developer data",
    "data platform engineer",
    "data infrastructure engineer",
    "data systems engineer",
    "business intelligence engineer",
    "data integration developer",
    "integration developer",
    "application developer data",
    "reporting developer",
]

# Much stricter DE-centered signals.
core_description_keywords = [
    "sql",
    "etl",
    "elt",
    "pipeline",
    "pipelines",
    "data ingestion",
    "data transformation",
    "data integration",
    "integration",
    "api integration",
    "rest api",
    "restful api",
    "api",
    "data warehouse",
    "data modeling",
    "data validation",
    "data quality",
    "reconciliation",
    "batch processing",
    "data processing",
    "source to target",
    "stored procedures",
    "record processing",
    "payload",
    "file transfer",
    "sftp",
    "xml",
    "json",
]

modern_tool_keywords = [
    "spark",
    "airflow",
    "dbt",
    "kafka",
    "microservices",
    "distributed systems",
    "event streaming",
    "stream processing",
    "databricks",
    "snowflake",
    "redshift",
    "bigquery",
    "glue",
    "emr",
    "kinesis",
    "lakehouse",
    "mlops",
    "kubernetes",
    "aks",
    "terraform",
    "synapse",
    "mlflow",
]

exclude_keywords = [
    "senior",
    "sr",
    "lead",
    "principal",
    "staff",
    "vp",
    "director",
    "manager",
    "head",
    "intern",
    "vice president",
    "architect",
    "embedded",
    "firmware",
    "automotive",
    "ecu",
    "lin",
    "can bus",
    "flexray",
    "plc",
    "controls engineer",
    "gpu",
    "front-end",
    "frontend",
    "ui",
    "front end",
    "ui developer",
    "web developer",
    "asp.net developer",
    ".net developer",
    "react developer",
    "angular developer",
    "javascript developer",
    "mobile developer",
    "ios developer",
    "android developer",
    "propulsion",
    "aerospace",
    "mechanical",
    "simulation",
    "aircraft",
    "uas",
    "avionics",
]

SHORT_WORD_EXCLUDES = {"sr", "vp"}

wrong_lane_title_keywords = [
    "data analyst",
    "business analyst",
    "reporting analyst",
    "data scientist",
    "applied scientist",
    "ml engineer",
    "machine learning engineer",
    "qa engineer",
    "quality engineer",
    "automation tester",
    "test engineer",
    "application qa",
    "aem engineer",
    "full stack developer",
    "full stack engineer",
    "frontend developer",
    "frontend engineer",
    "ui developer",
    "ui engineer",
    "cloud engineer",
    "cloud infrastructure engineer",
    "devops engineer",
    "site reliability engineer",
    "sre",
    "infrastructure engineer",
    "genai",
    "ai engineer",
]

wrong_lane_desc_keywords = [
    "power bi",
    "tableau",
    "looker",
    "dashboard",
    "dashboards",
    "executive reporting",
    "self-service analytics",
    "predictive analytics",
    "machine learning",
    "deep learning",
    "data scientist",
    "prompt engineering",
    "langchain",
    "openai api",
    "anthropic api",
    "ai agents",
    "selenium",
    "robot framework",
    "functional testing",
    "regression testing",
    "adobe experience platform",
    "aem",
    "scada",
    "wastewater",
    "sewer",
    "gis",
    "arcgis",
]


def normalize_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def extract_years_required(description):
    description = normalize_text(description)

    if not description:
        return None

    description = description.replace("\\+", "+")
    description = description.replace("-", " ")
    description = re.sub(r"\s+", " ", description)

    patterns = [
        r"(\d+)\+\s*years",
        r"(\d+)\s+years",
        r"(\d+)\s*years",
    ]

    years = []

    for pattern in patterns:
        matches = re.findall(pattern, description)
        for m in matches:
            try:
                years.append(int(m))
            except Exception:
                pass

    return max(years) if years else None


def contains_keyword(text, keyword):
    text = normalize_text(text)
    keyword = keyword.lower().strip()

    if keyword in SHORT_WORD_EXCLUDES:
        pattern = rf"\b{re.escape(keyword)}\b"
        return re.search(pattern, text) is not None

    return keyword in text


def count_keywords(text, keywords):
    text = normalize_text(text)
    return sum(1 for keyword in keywords if keyword in text)


def has_direct_url(row):
    direct_url = normalize_text(row.get("job_url_direct", ""))
    return direct_url != ""


def is_excluded_title(row):
    title = normalize_text(row.get("title", ""))

    # Special-case consultant only if not obviously technical/data-oriented
    if "consultant" in title:
        technical_consultant_signals = [
            "data",
            "integration",
            "etl",
            "sql",
            "database",
            "engineer",
            "developer",
        ]
        if not any(sig in title for sig in technical_consultant_signals):
            return True

    return any(contains_keyword(title, keyword) for keyword in exclude_keywords)


def is_wrong_lane_title(row):
    title = normalize_text(row.get("title", ""))
    return any(contains_keyword(title, kw) for kw in wrong_lane_title_keywords)


def wrong_lane_desc_score(row):
    description = normalize_text(row.get("description", ""))
    return sum(1 for kw in wrong_lane_desc_keywords if kw in description)


def core_signal_count(row):
    description = normalize_text(row.get("description", ""))
    return count_keywords(description, core_description_keywords)


def modern_signal_count(row):
    description = normalize_text(row.get("description", ""))
    return count_keywords(description, modern_tool_keywords)


def strong_core_count(row):
    description = normalize_text(row.get("description", ""))

    strong_signals = [
        "sql",
        "etl",
        "pipeline",
        "data validation",
        "reconciliation",
        "data transformation",
        "sftp",
        "payload",
        "data ingestion",
        "data quality",
        "data integration",
        "data warehouse",
        "stored procedures",
    ]
    return sum(1 for kw in strong_signals if kw in description)


def data_centric_score(row):
    description = normalize_text(row.get("description", ""))

    data_centric_terms = [
        "etl",
        "elt",
        "pipeline",
        "pipelines",
        "data ingestion",
        "data transformation",
        "data validation",
        "data quality",
        "reconciliation",
        "data warehouse",
        "data integration",
        "data modeling",
        "payload",
        "record processing",
        "batch jobs",
        "batch processing",
        "source to target",
        "stored procedures",
    ]
    return sum(1 for term in data_centric_terms if term in description)


def is_data_centric(row):
    return row["data_centric_score"] >= 2


def title_has_backend_or_integration_signal(row):
    title = normalize_text(row.get("title", ""))
    signals = [
        "backend engineer",
        "backend developer",
        "software engineer",
        "software developer",
        "integration engineer",
        "integration developer",
        "data developer",
        "database developer",
        "database engineer",
        "platform engineer",
        "api engineer",
        "api developer",
        "reporting developer",
    ]
    return any(signal in title for signal in signals)


BAD_OTHER_TITLE_TERMS = [
    "analyst",
    "scientist",
    "ai",
    "genai",
    "machine learning",
    "ml",
    "qa",
    #"quality",
   # "test",
    "automation",
    "infrastructure",
    "cloud",
    "devops",
    "sre",
    "visualization",
    "bi engineer",
    "business intelligence",
    "architect"
]


def other_title_hard_reject(row):
    title = normalize_text(row.get("title", ""))
    if row["title_type"] != "other":
        return False
    return any(term in title for term in BAD_OTHER_TITLE_TERMS)


def title_has_backend_or_integration_signal(row):
    title = normalize_text(row.get("title", ""))
    signals = [
        "backend engineer",
        "backend developer",
        "software engineer",
        "software developer",
        "integration engineer",
        "integration developer",
        "data developer",
        "reporting developer",
    ]
    return any(signal in title for signal in signals)


def soft_recovery_match(row):
    """
    Rescue messy-but-viable backend/data/integration roles that are not cleanly titled
    as DE but still look aligned in the description.
    """
    if row["is_excluded"] or row["wrong_lane_title"] or row["other_title_hard_reject"]:
        return False

    if row["years_required"] is not None and row["years_required"] >= 5:
        return False

    if row["wrong_lane_desc_score"] >= 2 and row["data_centric_score"] < 3:
        return False

    if row["modern_tool_dominant"] or row["ml_heavy"]:
        return False

    core_count = row["core_signal_count"]
    strong_count = row["strong_core_count"]
    data_score = row["data_centric_score"]
    modern_count = row["modern_signal_count"]
    role_type = row["title_type"]
    title_signal = row["title_backend_or_integration_signal"]
    description = normalize_text(row.get("description", ""))

    has_sql = "sql" in description
    has_lane_support = any(
        phrase in description
        for phrase in [
            "etl",
            "elt",
            "pipeline",
            "pipelines",
            "integration",
            "data integration",
            "data ingestion",
            "data transformation",
            "data validation",
            "reconciliation",
            "stored procedures",
            "payload",
            "json",
            "xml",
            "sftp",
            "api",
            "rest api",
            "restful api",
        ]
    )

    return (
        role_type == "other"
        and title_signal
        and has_sql
        and has_lane_support
        and core_count >= 4
        and strong_count >= 2
        and data_score >= 2
        and modern_count <= 2
    )


def description_only_match(row):
    core_count = row["core_signal_count"]
    strong_count = row["strong_core_count"]
    modern_count = row["modern_signal_count"]
    data_score = row["data_centric_score"]
    wrong_lane_score = row["wrong_lane_desc_score"]

    return (
        core_count >= 6
        and strong_count >= 3
        and modern_count <= 2
        and data_score >= 3
        and wrong_lane_score == 0
    )


def is_modern_tool_dominant(row):
    """
    Modern-stack-heavy roles should not become apply unless there is very strong
    core lane evidence.
    """
    core_count = row["core_signal_count"]
    modern_count = row["modern_signal_count"]
    strong_count = row["strong_core_count"]
    data_score = row["data_centric_score"]
    description = normalize_text(row.get("description", ""))

    hard_require_phrases = [
        "must have spark",
        "required spark",
        "experience with spark required",
        "must have databricks",
        "required databricks",
        "must have airflow",
        "required airflow",
        "must have kafka",
        "required kafka",
        "must have kubernetes",
        "required kubernetes",
        "must have mlops",
        "required mlops",
    ]

    hard_required = any(phrase in description for phrase in hard_require_phrases)

    if hard_required:
        return True

    if modern_count >= 6:
        return True

    if modern_count >= 5 and core_count <= 4:
        return True

    if modern_count >= 4 and core_count <= 3 and strong_count <= 1:
        return True

    if modern_count >= 4 and data_score <= 1:
        return True

    return False


def is_ml_heavy(row):
    description = normalize_text(row.get("description", ""))

    ml_terms = [
        "machine learning",
        "ai",
        "nlp",
        "classification",
        "regression",
        "predictive",
        "model",
        "data science",
        "data scientist",
    ]

    return sum(1 for term in ml_terms if term in description) >= 2


def title_type(row):
    title = normalize_text(row.get("title", ""))

    if any(keyword in title for keyword in primary_keywords):
        return "primary"

    if any(keyword in title for keyword in secondary_keywords):
        return "secondary"

    if FALLBACK and any(keyword in title for keyword in bridge_roles):
        return "bridge"

    return "other"


def assign_fit_bucket(row):
    if row["is_excluded"]:
        return "skip"

    if row["wrong_lane_title"]:
        return "skip"

    if row["other_title_hard_reject"]:
        return "skip"

    if row["wrong_lane_desc_score"] >= 2 and row["data_centric_score"] < 3:
        return "skip"

    if row["modern_tool_dominant"] and not row["soft_recovery_match"]:
        return "skip"

    if row["years_required"] is not None and row["years_required"] >= 5:
        return "skip"

    # ML-heavy roles should not become apply
    if row["ml_heavy"]:
        return "review" if row["core_signal_count"] >= 4 and row["data_centric_score"] >= 2 and row["strong_core_count"] >= 2 else "skip"

    role_type = row["title_type"]
    core_count = row["core_signal_count"]
    strong_count = row["strong_core_count"]
    modern_count = row["modern_signal_count"]
    data_score = row["data_centric_score"]
    direct_url = row["has_direct_url"]

    # Bridge roles: very strict
    if role_type == "bridge":
        if core_count >= 6 and strong_count >= 3 and data_score >= 3 and modern_count <= 2:
            return "review"
        return "skip"

    # Primary roles: restore strong apply path.
    if role_type == "primary":
        if core_count >= 5 and strong_count >= 3 and data_score >= 3 and modern_count <= 2:
            return "apply" if direct_url else "review"

        if core_count >= 4 and strong_count >= 2 and data_score >= 2:
            if modern_count >= 3:
                return "review"
            return "apply" if direct_url else "review"

        if core_count >= 3 and strong_count >= 2 and data_score >= 2:
            return "review"

        return "skip"

    # Secondary roles: keep review-only but allow solid adjacent matches.
    if role_type == "secondary":
        if core_count >= 5 and strong_count >= 2 and data_score >= 3 and modern_count <= 2:
            return "review"

        if core_count >= 4 and strong_count >= 2 and data_score >= 2 and modern_count <= 2:
            return "review"

        return "skip"

    # Weird titles with very strong DE-shaped descriptions.
    if role_type == "other" and description_only_match(row) and not row["other_title_hard_reject"]:
        return "review"

    # Rescue vague backend/software/integration titles with real data lane evidence.
    if row["soft_recovery_match"]:
        return "review"

    return "skip"


def build_dedupe_key(row):
    direct_url = normalize_text(row.get("job_url_direct", ""))
    job_url = normalize_text(row.get("job_url", ""))
    title = normalize_text(row.get("title", ""))
    company = normalize_text(row.get("company", ""))
    description = normalize_text(row.get("description", ""))

    if direct_url:
        return f"direct::{direct_url}"
    if job_url:
        return f"url::{job_url}"
    if title and company:
        return f"title_company::{title}::{company}"
    return f"description::{description[:500]}"


jobs_df["ml_heavy"] = jobs_df.apply(is_ml_heavy, axis=1)
jobs_df["years_required"] = jobs_df["description"].apply(extract_years_required)
jobs_df["title_type"] = jobs_df.apply(title_type, axis=1)
jobs_df["core_signal_count"] = jobs_df.apply(core_signal_count, axis=1)
jobs_df["modern_signal_count"] = jobs_df.apply(modern_signal_count, axis=1)
jobs_df["strong_core_count"] = jobs_df.apply(strong_core_count, axis=1)
jobs_df["data_centric_score"] = jobs_df.apply(data_centric_score, axis=1)
jobs_df["modern_tool_dominant"] = jobs_df.apply(is_modern_tool_dominant, axis=1)
jobs_df["is_excluded"] = jobs_df.apply(is_excluded_title, axis=1)
jobs_df["wrong_lane_title"] = jobs_df.apply(is_wrong_lane_title, axis=1)
jobs_df["wrong_lane_desc_score"] = jobs_df.apply(wrong_lane_desc_score, axis=1)
jobs_df["has_direct_url"] = jobs_df.apply(has_direct_url, axis=1)
jobs_df["title_backend_or_integration_signal"] = jobs_df.apply(title_has_backend_or_integration_signal, axis=1)
jobs_df["other_title_hard_reject"] = jobs_df.apply(other_title_hard_reject, axis=1)
jobs_df["soft_recovery_match"] = jobs_df.apply(soft_recovery_match, axis=1)
jobs_df["fit_bucket"] = jobs_df.apply(assign_fit_bucket, axis=1)

print("\nFit bucket counts before dedupe:")
print(jobs_df["fit_bucket"].value_counts(dropna=False))

cleaned_jobs_df = jobs_df[jobs_df["fit_bucket"].isin(["apply", "review"])].copy()

print(
    f"\nTotal jobs after fit filtering: {len(cleaned_jobs_df)} "
    f"({len(cleaned_jobs_df) / processed_count:.2%} of original)"
)

cleaned_jobs_df["dedupe_key"] = cleaned_jobs_df.apply(build_dedupe_key, axis=1)
cleaned_jobs_df = cleaned_jobs_df.drop_duplicates(subset=["dedupe_key"], keep="first")

cleaned_jobs_df["manual_review"] = cleaned_jobs_df["fit_bucket"] == "review"

print("\nFit bucket counts after dedupe:")
print(cleaned_jobs_df["fit_bucket"].value_counts(dropna=False))
print(f"Manual review jobs: {cleaned_jobs_df['manual_review'].sum()}")

bucket_order = {"apply": 0, "review": 1}
cleaned_jobs_df["bucket_sort"] = cleaned_jobs_df["fit_bucket"].map(bucket_order)
cleaned_jobs_df = cleaned_jobs_df.sort_values(
    by=[
        "bucket_sort",
        "core_signal_count",
        "strong_core_count",
        "data_centric_score",
        "company",
        "title",
    ],
    ascending=[True, False, False, False, True, True],
).drop(columns=["bucket_sort"])

cleaned_jobs_df = cleaned_jobs_df.drop(columns=["dedupe_key"])

cleaned_jobs_df.to_csv(clean_filename, index=False)
print(f"\nSaved cleaned jobs to {clean_filename}")