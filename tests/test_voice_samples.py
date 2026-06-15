import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from timbre_shift.library import add_voice_sample, create_voice_profile, list_voice_samples
from timbre_shift.rvc_mlx import prepare_rvc_mlx_dataset


def fake_normalize(source: Path, target: Path, **kwargs) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(Path(source).read_bytes())
    return target


class VoiceSampleTests(unittest.TestCase):
    def test_voice_profile_deduplicates_samples_by_sha256(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "library.db"
            library_dir = root / "library"
            raw = root / "raw.wav"
            raw.write_bytes(b"same-audio")
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

            with patch("timbre_shift.library.normalize_audio", side_effect=fake_normalize), \
                patch("timbre_shift.library.probe_duration", return_value=12.0), \
                patch("timbre_shift.library._make_preview_mp3", side_effect=lambda source, output: fake_normalize(source, output)), \
                patch("timbre_shift.library.analyze_generation", return_value={"issues": []}):
                first = add_voice_sample(
                    profile.id,
                    raw,
                    name="sample",
                    source_type="upload_voice",
                    library_dir=library_dir,
                    db_path=db_path,
                )
                second = add_voice_sample(
                    profile.id,
                    raw,
                    name="sample again",
                    source_type="upload_voice",
                    library_dir=library_dir,
                    db_path=db_path,
                )

            self.assertEqual(first.id, second.id)
            self.assertEqual(len(list_voice_samples(profile.id, db_path=db_path)), 1)

    def test_unallowed_voice_cannot_prepare_rvc_dataset(self):
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
                prepare_rvc_mlx_dataset(profile.id, library_dir=root / "library", db_path=db_path)


if __name__ == "__main__":
    unittest.main()
