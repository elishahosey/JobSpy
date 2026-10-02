"""Run ordinary JobSpy searches and retain their origin in a single dataframe."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

from jobspy import scrape_jobs
from jobspy.util import desired_order


_DATE_SUFFIX = re.compile(r"-\d{2}-\d{2}-\d{4}$")


def dated_output_path(output: Path, run_date: date | None = None) -> Path:
    """Insert an ``MM-DD-YYYY`` date before a CSV or Excel suffix."""
    run_date = run_date or date.today()
    if _DATE_SUFFIX.search(output.stem):
        return output
    stamp = run_date.strftime("%m-%d-%Y")
    return output.with_name(f"{output.stem}-{stamp}{output.suffix}")


def scrape_batch(searches: list[dict], **scrape_options) -> pd.DataFrame:
    """Call scrape_jobs once per query, preserving all rows and query text.

    Each search has query, mode, and optional google_search_term/results_wanted.
    Other scrape_jobs options are shared by every search. Modes are metadata only.
    """
    if not isinstance(searches, list) or not searches:
        raise ValueError("searches must be a non-empty list")
    if "search_term" in scrape_options or "google_search_term" in scrape_options:
        raise ValueError("Put query and google_search_term in each search entry")

    # Validate the entire batch before making any provider requests.
    for search in searches:
        if not isinstance(search, dict) or set(search) - {
            "query",
            "mode",
            "google_search_term",
            "results_wanted",
        }:
            raise ValueError(
                "Each search needs query, mode, and optional "
                "google_search_term/results_wanted"
            )
        if not isinstance(search.get("query"), str) or not search["query"].strip():
            raise ValueError("Each query must be a non-empty string")
        if search.get("mode") not in ("job_title", "skill_based", "mixed"):
            raise ValueError("mode must be job_title, skill_based, or mixed")
        google_query = search.get("google_search_term")
        if google_query is not None and (
            not isinstance(google_query, str) or not google_query.strip()
        ):
            raise ValueError("google_search_term must be a non-empty string or null")
        if "results_wanted" in search and (
            type(search["results_wanted"]) is not int or search["results_wanted"] < 1
        ):
            raise ValueError("Per-search results_wanted must be a positive integer")

    frames = []
    for search in searches:
        options = dict(scrape_options)
        if "results_wanted" in search:
            options["results_wanted"] = search["results_wanted"]
        jobs = scrape_jobs(
            search_term=search["query"],
            google_search_term=search.get("google_search_term"),
            **options,
        ).copy()
        # Upstream returns a columnless dataframe when no jobs are found.
        if jobs.empty and len(jobs.columns) == 0:
            jobs = pd.DataFrame(columns=desired_order)
        jobs["search_query"] = search["query"]
        jobs["search_mode"] = search["mode"]
        frames.append(jobs)

    return pd.concat(frames, ignore_index=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "config", type=Path, help="JSON with searches and scrape_options"
    )
    parser.add_argument("output", type=Path, help="Output .csv or .xlsx file")
    args = parser.parse_args(argv)
    suffix = args.output.suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        parser.error("output must end in .csv or .xlsx")
    if suffix == ".xlsx":
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            parser.error("Excel export requires: python -m pip install openpyxl")

    with args.config.open(encoding="utf-8-sig") as config_file:
        config = json.load(config_file)
    if not isinstance(config, dict) or set(config) - {"searches", "scrape_options"}:
        parser.error("config must contain searches and optional scrape_options")
    options = config.get("scrape_options", {})
    if not isinstance(options, dict):
        parser.error("scrape_options must be an object of scrape_jobs arguments")
    jobs = scrape_batch(config.get("searches"), **options)
    output = dated_output_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".csv":
        jobs.to_csv(
            output, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False
        )
    else:
        jobs.to_excel(output, index=False, engine="openpyxl")
    print(f"Exported {len(jobs)} rows to {output}")


if __name__ == "__main__":
    main()
