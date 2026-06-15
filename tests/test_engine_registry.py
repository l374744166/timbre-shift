import unittest

from timbre_shift.engines import get_engine, list_engines


class EngineRegistryTests(unittest.TestCase):
    def test_registry_lists_seedvc_and_rvc_mlx(self):
        ids = {engine.id for engine in list_engines()}

        self.assertIn("seedvc", ids)
        self.assertIn("rvc_mlx", ids)

    def test_rvc_mlx_missing_does_not_affect_seedvc(self):
        seedvc = get_engine("seedvc")
        rvc_mlx = get_engine("rvc_mlx")

        self.assertTrue(seedvc.is_available())
        self.assertFalse(seedvc.requires_training)
        self.assertTrue(rvc_mlx.requires_training)
        self.assertIn("available", rvc_mlx.check())


if __name__ == "__main__":
    unittest.main()
