import unittest

from timbre_shift.rvc_presets import RVC_PRESETS, get_rvc_preset


class RVCPresetTests(unittest.TestCase):
    def test_stable_presets_do_not_enable_index(self):
        for preset_id in ["stable_balanced", "clear_diction", "stronger_timbre_safe"]:
            self.assertEqual(RVC_PRESETS[preset_id].index_rate, 0.0)

    def test_experimental_index_requires_explicit_allow(self):
        blocked = get_rvc_preset("experimental_index_light", allow_experimental_index=False)
        allowed = get_rvc_preset("experimental_index_light", allow_experimental_index=True)

        self.assertEqual(blocked.id, "stable_balanced")
        self.assertEqual(allowed.index_rate, 0.25)


if __name__ == "__main__":
    unittest.main()
