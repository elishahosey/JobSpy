"""Generate a single-row JobSpy CSV for testing SkillFreq intake."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path


COLUMNS = [
    "id", "site", "job_url", "job_url_direct", "title", "company",
    "location", "date_posted", "job_type", "salary_source", "interval",
    "min_amount", "max_amount", "currency", "is_remote", "job_level",
    "job_function", "listing_type", "emails", "description",
    "company_industry", "company_url", "company_logo", "company_url_direct",
    "company_addresses", "company_num_employees", "company_revenue",
    "company_description", "skills", "experience_range", "company_rating",
    "company_reviews_count", "vacancy_count", "work_from_home_type",
    "search_lane", "search_term_used", "review_priority",
]


def dated_filename(run_date: date) -> str:
    """Return the same non-zero-padded filename format used by joblist.py."""
    return f"jobs-{run_date.month}-{run_date.day}-{run_date:%y}.csv"


def create_test_csv(output_dir: Path, run_date: date | None = None) -> Path:
    """Create and return a SkillFreq-compatible, single-job CSV fixture."""
    run_date = run_date or date.today()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / dated_filename(run_date)

    row = {column: "" for column in COLUMNS}
    row.update(
        {
            "id": f"test-{run_date:%Y%m%d}",
            "site": "test",
            "job_url": "https://example.com/jobs/test-data-engineer",
            "title": "Test Data Engineer",
            "company": "SkillFreq Test Company",
            "location": "Remote",
            "date_posted": run_date.isoformat(),
            "job_type": "fulltime",
            "is_remote": "True",
            "description": (
                "Build Python ETL pipelines using SQL, PostgreSQL, Airflow, "
                "Docker, AWS, and REST APIs. This is synthetic test data."
            ),
            "skills": "Python, SQL, PostgreSQL, Airflow, Docker, AWS, REST APIs",
            "experience_range": "3-5 years",
            "search_lane": "core",
            "search_term_used": "data engineer",
            "review_priority": "1",
        }
    )

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=COLUMNS,
            quoting=csv.QUOTE_NONNUMERIC,
            escapechar="\\",
        )
        writer.writeheader()
        writer.writerow(row)

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate one synthetic jobs-M-D-YY.csv for SkillFreq intake."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Destination directory (default: current directory).",
    )
    args = parser.parse_args()
    print(create_test_csv(args.output_dir))


if __name__ == "__main__":
    main()
