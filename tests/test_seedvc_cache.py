import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from timbre_shift.seed_vc import seedvc_cache_key


class SeedVCCacheTests(unittest.TestCase):
    def test_cache_key_is_stable_and_parameter_sensitive(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            seed_vc_dir = root / "seed-vc"
            seed_vc_dir.mkdir()
            source = root / "source.wav"
            target = root / "target.wav"
            source.write_bytes(b"source")
            target.write_bytes(b"target")
            (seed_vc_dir / "inference.py").write_text("print('seed')", encoding="utf-8")

            first = seedvc_cache_key(
                seed_vc_dir=seed_vc_dir,
                source_vocal=source,
                target_voice=target,
                target_voice_seconds=16,
                diffusion_steps=16,
                inference_cfg_rate=0.0,
                semi_tone_shift=0,
                device="mps",
            )
            same = seedvc_cache_key(
                seed_vc_dir=seed_vc_dir,
                source_vocal=source,
                target_voice=target,
                target_voice_seconds=16,
                diffusion_steps=16,
                inference_cfg_rate=0.0,
                semi_tone_shift=0,
                device="mps",
            )
            changed_steps = seedvc_cache_key(
                seed_vc_dir=seed_vc_dir,
                source_vocal=source,
                target_voice=target,
                target_voice_seconds=16,
                diffusion_steps=20,
                inference_cfg_rate=0.0,
                semi_tone_shift=0,
                device="mps",
            )

            self.assertEqual(first, same)
            self.assertNotEqual(first, changed_steps)


if __name__ == "__main__":
    unittest.main()
