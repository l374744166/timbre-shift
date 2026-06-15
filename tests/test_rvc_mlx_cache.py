import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from timbre_shift.library import VoiceModel
from timbre_shift.rvc_mlx import rvc_mlx_cache_key


class RVCMLXCacheTests(unittest.TestCase):
    def test_cache_key_changes_with_model_and_pitch(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.wav"
            model_path = root / "model.mlx"
            index_path = root / "model.index"
            source.write_bytes(b"source")
            model_path.write_bytes(b"model-a")
            index_path.write_bytes(b"index")
            model = VoiceModel(
                id="model_1",
                voice_id="voice_1",
                engine_id="rvc_mlx",
                model_name="RVC",
                model_path=str(model_path),
                index_path=str(index_path),
                config_path=None,
                dataset_path=None,
                training_seconds=None,
                dataset_seconds=600.0,
                status="ready",
                created_at="now",
                updated_at="now",
                metadata_json=None,
            )

            base = rvc_mlx_cache_key(source, model, {"pitch_shift": 0})
            same = rvc_mlx_cache_key(source, model, {"pitch_shift": 0})
            shifted = rvc_mlx_cache_key(source, model, {"pitch_shift": 1})
            model_path.write_bytes(b"model-b")
            changed_model = rvc_mlx_cache_key(source, model, {"pitch_shift": 0})

            self.assertEqual(base, same)
            self.assertNotEqual(base, shifted)
            self.assertNotEqual(base, changed_model)


if __name__ == "__main__":
    unittest.main()
