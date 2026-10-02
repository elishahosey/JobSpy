"""Verify result-count overrides and the normal, editable JSON entry point."""

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from jobspy.batch import dated_output_path, main, scrape_batch


class SearchConfigTests(unittest.TestCase):
    @patch("jobspy.batch.scrape_jobs", return_value=pd.DataFrame())
    def test_query_limit_overrides_shared_limit_without_leaking(self, scrape):
        searches = [
            {"query": "Data Engineer", "mode": "job_title", "results_wanted": 120},
            {"query": "SQL ETL", "mode": "skill_based"},
            {"query": "Engineer SQL", "mode": "mixed", "results_wanted": 2},
            {"query": "Developer", "mode": "job_title"},
        ]
        original = copy.deepcopy(searches)
        options = {"results_wanted": 1, "location": "Texas", "hours_old": 24}
        scrape_batch(searches, **options)
        self.assertEqual(
            [call.kwargs["results_wanted"] for call in scrape.call_args_list],
            [120, 1, 2, 1],
        )
        for call in scrape.call_args_list:
            self.assertEqual(call.kwargs["location"], "Texas")
            self.assertEqual(call.kwargs["hours_old"], 24)
        self.assertEqual(searches, original)
        self.assertEqual(options["results_wanted"], 1)

    @patch("jobspy.batch.scrape_jobs", return_value=pd.DataFrame())
    def test_no_limit_still_uses_upstream_default(self, scrape):
        scrape_batch(
            [
                {"query": "Engineer", "mode": "job_title", "results_wanted": 2},
                {"query": "SQL", "mode": "skill_based"},
            ]
        )
        self.assertEqual(scrape.call_args_list[0].kwargs["results_wanted"], 2)
        self.assertNotIn("results_wanted", scrape.call_args_list[1].kwargs)

    @patch("jobspy.batch.scrape_jobs")
    def test_bad_query_limits_are_rejected_before_any_requests(self, scrape):
        for limit in (None, True, False, 0, -1, 1.5, "2", []):
            with (
                self.subTest(limit=limit),
                self.assertRaisesRegex(ValueError, "positive integer"),
            ):
                scrape_batch(
                    [
                        {"query": "Engineer", "mode": "job_title"},
                        {
                            "query": "SQL",
                            "mode": "skill_based",
                            "results_wanted": limit,
                        },
                    ]
                )
        scrape.assert_not_called()

    def check_real_config_export(self, suffix):
        # Read current configuration, not a frozen copy: users can edit searches.
        config_path = Path(__file__).resolve().parents[1] / "config/searches.json"
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        searches = config["searches"]
        jobs = pd.DataFrame(
            [
                {
                    "id": "li-same-job",
                    "site": "linkedin",
                    "title": "Example",
                    "description": 'SQL, Python\nBuild "APIs"',
                    "job_url": "https://example.com/job",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / f"jobs{suffix}"
            with patch("jobspy.batch.scrape_jobs", return_value=jobs) as scrape:
                main([str(config_path), str(output)])
            dated_output = dated_output_path(output)
            result = (
                pd.read_csv(dated_output)
                if suffix == ".csv"
                else pd.read_excel(dated_output)
            )
        self.assertEqual(scrape.call_count, len(searches))
        self.assertEqual(
            result["search_query"].tolist(), [s["query"] for s in searches]
        )
        self.assertEqual(result["search_mode"].tolist(), [s["mode"] for s in searches])
        self.assertEqual(result["id"].tolist(), ["li-same-job"] * len(searches))
        self.assertEqual(
            result["description"].tolist(),
            [jobs.iloc[0]["description"]] * len(searches),
        )
        self.assertEqual(
            list(result.columns), list(jobs.columns) + ["search_query", "search_mode"]
        )
        for search, call in zip(searches, scrape.call_args_list):
            expected = dict(config.get("scrape_options", {}))
            if "results_wanted" in search:
                expected["results_wanted"] = search["results_wanted"]
            expected.update(
                search_term=search["query"],
                google_search_term=search.get("google_search_term"),
            )
            self.assertEqual(call.kwargs, expected)

    def test_normal_config_csv_cli_preserves_queries_and_duplicate_jobs(self):
        self.check_real_config_export(".csv")

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "optional Excel engine")
    def test_normal_config_excel_cli_preserves_queries_and_duplicate_jobs(self):
        self.check_real_config_export(".xlsx")


if __name__ == "__main__":
    unittest.main()
