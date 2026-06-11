import unittest

from timbre_shift.commands import bool_arg


class CommandTests(unittest.TestCase):
    def test_bool_arg_matches_seed_vc_cli_values(self):
        self.assertEqual(bool_arg(True), "True")
        self.assertEqual(bool_arg(False), "False")
