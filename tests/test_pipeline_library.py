import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from timbre_shift.library import create_song_record, create_voice_profile, update_song_stems
from timbre_shift.pipeline import PipelineOptions, run_demo
from timbre_shift.seed_vc import SeedVCResult


def seedvc_result(output: Path) -> SeedVCResult:
    return SeedVCResult(
        output=output,
        cache_hit=False,
        elapsed_seconds=1.0,
        cache_key="test",
        device_requested="mps",
        device_used="mps",
        cpu_fallback_used=False,
    )


class PipelineLibraryTests(unittest.TestCase):
    def test_unallowed_voice_profile_cannot_be_target(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "library.db"
            seed_vc_dir = root / "seed-vc"
            seed_vc_dir.mkdir()
            (seed_vc_dir / "inference.py").write_text("")
            raw = root / "raw.wav"
            song = root / "song.wav"
            raw.write_bytes(b"raw")
            song.write_bytes(b"song")
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
                sha256="abc",
                db_path=db_path,
            )

            with self.assertRaises(PermissionError):
                run_demo(
                    PipelineOptions(
                        voice_profile_id=profile.id,
                        song=song,
                        seed_vc_dir=seed_vc_dir,
                        library_db_path=db_path,
                    )
                )

    def test_song_library_stems_skip_demucs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "library.db"
            seed_vc_dir = root / "seed-vc"
            seed_vc_dir.mkdir()
            (seed_vc_dir / "inference.py").write_text("")
            voice = root / "voice.wav"
            song_audio = root / "song.wav"
            prepared = root / "prepared.wav"
            vocals = root / "vocals.wav"
            backing = root / "no_vocals.wav"
            converted = root / "converted.wav"
            final = root / "final.wav"
            for path in [voice, song_audio, prepared, vocals, backing, converted, final]:
                path.write_bytes(path.name.encode())
            song = create_song_record(
                title="Song",
                artist=None,
                original_audio_path=song_audio,
                prepared_audio_path=prepared,
                sha256="songhash",
                db_path=db_path,
            )
            update_song_stems(song.id, vocals, backing, "htdemucs", db_path=db_path)

            def fake_normalize(source, target, **kwargs):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(Path(source).read_bytes())
                return target

            with patch("timbre_shift.pipeline_prepare.normalize_audio", side_effect=fake_normalize), \
                patch("timbre_shift.pipeline_prepare.middle_start", return_value=None), \
                patch("timbre_shift.pipeline.separate_vocals") as separate_vocals, \
                patch("timbre_shift.pipeline_seedvc.convert_singing_voice_result", return_value=seedvc_result(converted)), \
                patch("timbre_shift.pipeline.polish_vocal", side_effect=lambda source, output: source), \
                patch("timbre_shift.pipeline_output.mix_audio", return_value=final), \
                patch("timbre_shift.pipeline_output.export_mp3", return_value=root / "out" / "final.mp3"):
                result = run_demo(
                    PipelineOptions(
                        voice=voice,
                        song_id=song.id,
                        seed_vc_dir=seed_vc_dir,
                        library_db_path=db_path,
                        render_mode="full_fast",
                    )
                )

            separate_vocals.assert_not_called()
            self.assertEqual(result, final)


if __name__ == "__main__":
    unittest.main()
