"""Scrape exactly one real job and write it to a dated JobSpy CSV."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from jobspy import scrape_jobs

from generate_skillfreq_test_csv import dated_filename


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--term", default="data engineer")
    parser.add_argument("--location", default="Texas")
    parser.add_argument("--site", default="indeed")
    parser.add_argument("--hours-old", type=int, default=168)
    parser.add_argument("--output-dir", type=Path, default=Path.cwd())
    args = parser.parse_args()

    jobs = scrape_jobs(
        site_name=[args.site],
        search_term=args.term,
        location=args.location,
        results_wanted=1,
        hours_old=args.hours_old,
        country_indeed="USA",
    )
    jobs = jobs.dropna(how="all").head(1).copy()
    if jobs.empty:
        raise SystemExit("No job was found; try another term, site, or location.")

    jobs["search_lane"] = "test"
    jobs["search_term_used"] = args.term
    jobs["review_priority"] = 1

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / dated_filename(date.today())
    jobs.to_csv(
        output,
        quoting=csv.QUOTE_NONNUMERIC,
        escapechar="\\",
        index=False,
    )
    print(f"Saved exactly {len(jobs)} real job to {output}")


if __name__ == "__main__":
    main()
