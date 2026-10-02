import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from jobspy import scrape_jobs
from jobspy.batch import main, scrape_batch
from jobspy.google import Google
from jobspy.indeed import Indeed
from jobspy.linkedin import LinkedIn
from jobspy.model import Country, JobPost, JobResponse, ScraperInput, Site
from jobspy.util import desired_order


SEARCHES = [
    {"query": '  "Data Engineer" -intern  ', "mode": "job_title"},
    {"query": "SQL ETL Python", "mode": "skill_based"},
    {"query": "Backend Engineer SQL API", "mode": "mixed"},
]


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.jobs = pd.DataFrame([{column: None for column in desired_order}]).assign(
            id="li-123",
            site="linkedin",
            title="Data Engineer",
            description='SQL, Python\nBuild "APIs"',
            job_url="https://www.linkedin.com/jobs/view/123",
        )

    @patch("jobspy.batch.scrape_jobs")
    def test_modes_exact_queries_duplicates_columns_and_options(self, scrape):
        scrape.return_value = self.jobs
        searches = copy.deepcopy(SEARCHES)
        options = {
            "site_name": ["linkedin", "indeed"],
            "location": "Austin, TX",
            "results_wanted": 2,
            "hours_old": 72,
            "is_remote": True,
            "fetch_description": True,
        }
        result = scrape_batch(searches, **options)
        self.assertEqual(
            result["search_query"].tolist(), [s["query"] for s in SEARCHES]
        )
        self.assertEqual(result["search_mode"].tolist(), [s["mode"] for s in SEARCHES])
        self.assertEqual(result["id"].tolist(), ["li-123"] * 3)
        self.assertEqual(
            list(result.columns), desired_order + ["search_query", "search_mode"]
        )
        self.assertEqual(list(result.index), [0, 1, 2])
        for index, call in enumerate(scrape.call_args_list):
            self.assertEqual(
                call.kwargs,
                dict(
                    options,
                    search_term=SEARCHES[index]["query"],
                    google_search_term=None,
                ),
            )
            pd.testing.assert_frame_equal(
                result.iloc[[index]][desired_order].reset_index(drop=True), self.jobs
            )
        self.assertNotIn("search_query", self.jobs)
        self.assertEqual(searches, SEARCHES)

    @patch("jobspy.batch.scrape_jobs")
    def test_repeated_searches_and_executions_keep_all_returned_rows(self, scrape):
        scrape.return_value = pd.concat([self.jobs, self.jobs], ignore_index=True)
        first = scrape_batch([SEARCHES[0], SEARCHES[0]])
        second = scrape_batch([SEARCHES[0]])
        self.assertEqual(len(first), 4)
        self.assertEqual(len(pd.concat([first, second])), 6)

    @patch("jobspy.batch.scrape_jobs")
    def test_google_override_is_per_search(self, scrape):
        scrape.return_value = self.jobs
        override = "SQL ETL Python jobs near Austin, TX since yesterday"
        searches = [dict(SEARCHES[1], google_search_term=override), SEARCHES[0]]
        result = scrape_batch(searches, site_name="google")
        self.assertEqual(
            scrape.call_args_list[0].kwargs["google_search_term"], override
        )
        self.assertIsNone(scrape.call_args_list[1].kwargs["google_search_term"])
        self.assertEqual(
            result["search_query"].tolist(), [s["query"] for s in searches]
        )

    @patch("jobspy.batch.scrape_jobs")
    def test_empty_results_have_export_headers_and_extra_columns_survive(self, scrape):
        scrape.return_value = pd.DataFrame()
        result = scrape_batch(SEARCHES)
        self.assertTrue(result.empty)
        self.assertEqual(
            list(result.columns), desired_order + ["search_query", "search_mode"]
        )
        scrape.side_effect = [
            pd.DataFrame(),
            self.jobs.assign(extra_provider_field="value"),
        ]
        result = scrape_batch(SEARCHES[:2])
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0]["extra_provider_field"], "value")
        self.assertEqual(result.iloc[0]["search_mode"], "skill_based")

    @patch("jobspy.batch.scrape_jobs")
    def test_invalid_config_is_rejected_before_any_requests(self, scrape):
        for bad in (
            None,
            [],
            {},
            ["query"],
            [{"query": " ", "mode": "mixed"}],
            [dict(SEARCHES[0], mode="typo")],
            [dict(SEARCHES[0], google_search_term="")],
            [dict(SEARCHES[0], typo=True)],
            [SEARCHES[0], {"query": 123, "mode": "mixed"}],
        ):
            with self.subTest(searches=bad), self.assertRaises(ValueError):
                scrape_batch(bad)
        for key in ("search_term", "google_search_term"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                scrape_batch(SEARCHES, **{key: "shared query"})
        scrape.assert_not_called()

    @patch("jobspy.batch.scrape_jobs", side_effect=RuntimeError("provider failure"))
    def test_provider_exceptions_are_not_hidden(self, scrape):
        with self.assertRaisesRegex(RuntimeError, "provider failure"):
            scrape_batch(SEARCHES)

    def check_export(self, suffix):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "searches.json"
            config.write_text(json.dumps({"searches": SEARCHES}), encoding="utf-8-sig")
            output = Path(directory) / "output" / f"jobs{suffix}"
            with patch("jobspy.batch.scrape_jobs", return_value=self.jobs):
                main([str(config), str(output)])
            result = pd.read_csv(output) if suffix == ".csv" else pd.read_excel(output)
            self.assertEqual(
                result["search_query"].tolist(), [s["query"] for s in SEARCHES]
            )
            self.assertEqual(
                result["search_mode"].tolist(), [s["mode"] for s in SEARCHES]
            )
            self.assertEqual(result["id"].tolist(), ["li-123"] * 3)
            self.assertEqual(
                result["description"].tolist(), [self.jobs.iloc[0]["description"]] * 3
            )
            self.assertEqual(
                list(result.columns), desired_order + ["search_query", "search_mode"]
            )

    def test_csv_cli_roundtrip(self):
        self.check_export(".csv")

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "optional Excel engine")
    def test_excel_cli_roundtrip(self):
        self.check_export(".xlsx")

    @patch("jobspy.batch.scrape_jobs")
    def test_cli_rejects_unsupported_export_before_scraping(self, scrape):
        with self.assertRaises(SystemExit):
            main(["unused.json", "jobs.txt"])
        scrape.assert_not_called()


class UpstreamCompatibilityTests(unittest.TestCase):
    def test_single_query_api_keeps_original_schema(self):
        post = JobPost(
            id="li-123",
            title="Data Engineer",
            company_name="Example",
            job_url="https://www.linkedin.com/jobs/view/123",
            location=None,
        )
        with patch("jobspy.LinkedIn") as provider:
            provider.__name__ = "LinkedIn"
            provider.return_value.scrape.return_value = JobResponse(jobs=[post])
            result = scrape_jobs(site_name="linkedin", search_term="SQL ETL Python")
        self.assertEqual(list(result.columns), desired_order)
        self.assertEqual(result.iloc[0]["id"], "li-123")
        self.assertEqual(
            provider.return_value.scrape.call_args.args[0].search_term, "SQL ETL Python"
        )

    def test_linkedin_keyword_mapping(self):
        with patch("jobspy.linkedin.create_session") as create_session:
            create_session.return_value.get.return_value = Mock(
                status_code=200, text=""
            )
            scraper = LinkedIn()
            for search in SEARCHES:
                scraper.scrape(
                    ScraperInput(
                        site_type=[Site.LINKEDIN],
                        search_term=search["query"],
                        results_wanted=1,
                    )
                )
                self.assertEqual(
                    scraper.session.get.call_args.kwargs["params"]["keywords"],
                    search["query"],
                )

    def test_indeed_preserves_query_syntax_in_request(self):
        query = '"Data Engineer" (SQL OR Python) -intern'
        with patch("jobspy.indeed.create_session") as create_session:
            create_session.return_value.post.return_value = Mock(
                ok=True,
                json=Mock(
                    return_value={
                        "data": {
                            "jobSearch": {
                                "results": [],
                                "pageInfo": {"nextCursor": None},
                            }
                        }
                    }
                ),
            )
            scraper = Indeed()
            scraper.scrape(
                ScraperInput(
                    site_type=[Site.INDEED],
                    search_term=query,
                    country=Country.USA,
                    results_wanted=1,
                )
            )
            payload = scraper.session.post.call_args.kwargs["json"]["query"]
            self.assertIn('what: "' + query.replace('"', '\\"') + '"', payload)

    def test_google_generated_query_and_explicit_override(self):
        scraper = Google()
        scraper.session = Mock()
        scraper.session.get.return_value.text = ""
        with patch("jobspy.google.find_job_info_initial_page", return_value=[]):
            for override in (None, "Custom Google query near Austin"):
                scraper.scraper_input = ScraperInput(
                    site_type=[Site.GOOGLE],
                    search_term="SQL ETL Python",
                    google_search_term=override,
                    location="Austin, TX",
                    hours_old=24,
                )
                scraper._get_initial_cursor_and_jobs()
                self.assertEqual(
                    scraper.session.get.call_args.kwargs["params"]["q"],
                    override or "SQL ETL Python jobs near Austin, TX since yesterday",
                )


if __name__ == "__main__":
    unittest.main()
