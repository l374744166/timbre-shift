import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from timbre_shift.library import (
    archive_voice_model,
    create_voice_model_record,
    create_voice_profile,
    get_voice_model,
    list_voice_models,
)


class VoiceModelTests(unittest.TestCase):
    def test_create_and_get_ready_voice_model(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "library.db"
            raw = root / "raw.wav"
            model = root / "model.mlx"
            raw.write_bytes(b"raw")
            model.write_bytes(b"model")
            profile = create_voice_profile(
                name="Allowed",
                description=None,
                source_type="upload_voice",
                rights_status="own_voice",
                allowed_as_target=True,
                raw_audio_path=raw,
                ref_8s_path=raw,
                ref_16s_path=raw,
                ref_20s_path=raw,
                ref_25s_path=raw,
                preview_mp3_path=None,
                sha256="voice",
                db_path=db_path,
            )

            record = create_voice_model_record(
                profile.id,
                engine_id="rvc_mlx",
                model_name="Allowed RVC",
                model_path=model,
                dataset_seconds=612.0,
                status="ready",
                db_path=db_path,
            )

            self.assertEqual(get_voice_model(profile.id, db_path=db_path), record)
            self.assertEqual(list_voice_models(profile.id, db_path=db_path), [record])

            archive_voice_model(record.id, db_path=db_path)
            self.assertIsNone(get_voice_model(profile.id, db_path=db_path))
            self.assertEqual(list_voice_models(profile.id, db_path=db_path), [])

    def test_unallowed_voice_cannot_create_model(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "library.db"
            raw = root / "raw.wav"
            raw.write_bytes(b"raw")
            profile = create_voice_profile(
                name="Blocked",
                description=None,
                source_type="upload_voice",
                rights_status="unknown",
                allowed_as_target=False,
                raw_audio_path=raw,
                ref_8s_path=raw,
                ref_16s_path=raw,
                ref_20s_path=raw,
                ref_25s_path=raw,
                preview_mp3_path=None,
                sha256="voice",
                db_path=db_path,
            )

            with self.assertRaises(PermissionError):
                create_voice_model_record(
                    profile.id,
                    engine_id="rvc_mlx",
                    model_name="Blocked RVC",
                    model_path=root / "model.mlx",
                    db_path=db_path,
                )


if __name__ == "__main__":
    unittest.main()
