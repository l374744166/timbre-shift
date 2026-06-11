import unittest
from pathlib import Path

from timbre_shift.pipeline import check_environment


class PipelineTests(unittest.TestCase):
    def test_environment_report_mentions_missing_seed_vc(self):
        report = check_environment(Path("/tmp/missing-seed-vc-for-test"))

        self.assertIn("inference.py", report.to_text())
