import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from timbre_shift.pipeline import PipelineOptions, check_environment, run_demo
from timbre_shift.seed_vc import SeedVCResult
from timbre_shift.vocal_segments import CompactVocalResult, VocalSegment


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


class PipelineTests(unittest.TestCase):
    def test_environment_report_mentions_missing_seed_vc(self):
        report = check_environment(Path("/tmp/missing-seed-vc-for-test"))

        self.assertIn("inference.py", report.to_text())

    def test_skip_separation_uses_prepared_song_as_source_vocal(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            voice = root / "voice.wav"
            song = root / "song.wav"
            seed_vc_dir = root / "seed-vc"
            converted = root / "converted.wav"
            voice.write_bytes(b"voice")
            song.write_bytes(b"song")
            converted.write_bytes(b"converted")
            seed_vc_dir.mkdir()
            (seed_vc_dir / "inference.py").write_text("")

            def fake_normalize(source, target, **kwargs):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
                return target

            with patch("timbre_shift.pipeline.normalize_audio", side_effect=fake_normalize), \
                patch("timbre_shift.pipeline.middle_start", return_value=None), \
                patch("timbre_shift.pipeline.separate_vocals") as separate_vocals, \
                patch("timbre_shift.pipeline.convert_singing_voice_result", return_value=seedvc_result(converted)), \
                patch("timbre_shift.pipeline.export_mp3", return_value=root / "out" / "final.mp3"):
                final = run_demo(
                    PipelineOptions(
                        voice=voice,
                        song=song,
                        seed_vc_dir=seed_vc_dir,
                        work_dir=root / "work",
                        output_dir=root / "out",
                        skip_separation=True,
                    )
                )

            separate_vocals.assert_not_called()
            self.assertEqual(final.read_bytes(), b"converted")
            self.assertTrue((root / "out" / "metrics.json").exists())

    def test_m2_mode_compacts_vocals_before_conversion(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            voice = root / "voice.wav"
            song = root / "song.wav"
            seed_vc_dir = root / "seed-vc"
            compact_audio = root / "compact.wav"
            converted = root / "converted.wav"
            restored = root / "restored.wav"
            final = root / "final.wav"
            voice.write_bytes(b"voice")
            song.write_bytes(b"song")
            compact_audio.write_bytes(b"compact")
            converted.write_bytes(b"converted")
            restored.write_bytes(b"restored")
            final.write_bytes(b"final")
            seed_vc_dir.mkdir()
            (seed_vc_dir / "inference.py").write_text("")

            def fake_normalize(source, target, **kwargs):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
                return target

            separation = Mock(
                vocals=root / "vocals.wav",
                backing=root / "backing.wav",
                from_cache=False,
            )
            separation.vocals.write_bytes(b"vocals")
            separation.backing.write_bytes(b"backing")
            compact = CompactVocalResult(
                audio=compact_audio,
                segments=[VocalSegment(10.0, 20.0, 0.0)],
                total_duration=60.0,
            )

            with patch("timbre_shift.pipeline.normalize_audio", side_effect=fake_normalize), \
                patch("timbre_shift.pipeline.middle_start", return_value=None), \
                patch("timbre_shift.pipeline.separate_vocals", return_value=separation), \
                patch("timbre_shift.pipeline.compact_for_conversion", return_value=compact) as compact_for_conversion, \
                patch("timbre_shift.pipeline.convert_singing_voice_result", return_value=seedvc_result(converted)) as convert_singing_voice, \
                patch("timbre_shift.pipeline.restore_compact_vocals", return_value=restored) as restore_compact_vocals, \
                patch("timbre_shift.pipeline.mix_audio", return_value=final), \
                patch("timbre_shift.pipeline.export_mp3", return_value=root / "out" / "final.mp3"):
                result = run_demo(
                    PipelineOptions(
                        voice=voice,
                        song=song,
                        seed_vc_dir=seed_vc_dir,
                        work_dir=root / "work",
                        output_dir=root / "out",
                        render_mode="m2_full_fast",
                    )
                )

            compact_for_conversion.assert_called_once()
            self.assertEqual(convert_singing_voice.call_args.kwargs["source_vocal"], compact_audio)
            restore_compact_vocals.assert_called_once()
            self.assertEqual(result, final)
