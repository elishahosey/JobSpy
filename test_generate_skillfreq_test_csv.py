import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path

from generate_skillfreq_test_csv import COLUMNS, create_test_csv


class SkillFreqTestCsvTests(unittest.TestCase):
    def test_creates_one_job_with_expected_name_and_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            output = create_test_csv(Path(temporary_dir), date(2026, 8, 17))

            self.assertEqual(output.name, "jobs-8-17-26.csv")
            with output.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(list(rows[0]), COLUMNS)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "Test Data Engineer")
            self.assertIn("Python", rows[0]["description"])


if __name__ == "__main__":
    unittest.main()
