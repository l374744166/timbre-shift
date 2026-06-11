import unittest
from pathlib import Path

from timbre_shift.commands import bool_arg
from timbre_shift.web import create_test_result, safe_filename


class CommandTests(unittest.TestCase):
    def test_bool_arg_matches_seed_vc_cli_values(self):
        self.assertEqual(bool_arg(True), "True")
        self.assertEqual(bool_arg(False), "False")

    def test_safe_filename_removes_path_and_unsafe_chars(self):
        self.assertEqual(safe_filename("../my voice!!.wav"), "my-voice.wav")

    def test_create_test_result_writes_wav(self):
        path = create_test_result(Path("/tmp/timbre-shift-test-result.wav"))

        self.assertTrue(path.exists())
        self.assertGreater(path.stat().st_size, 1000)
