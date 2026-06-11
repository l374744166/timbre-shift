import unittest

from timbre_shift.commands import bool_arg
from timbre_shift.web import safe_filename


class CommandTests(unittest.TestCase):
    def test_bool_arg_matches_seed_vc_cli_values(self):
        self.assertEqual(bool_arg(True), "True")
        self.assertEqual(bool_arg(False), "False")

    def test_safe_filename_removes_path_and_unsafe_chars(self):
        self.assertEqual(safe_filename("../my voice!!.wav"), "my-voice.wav")
