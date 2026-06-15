import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from timbre_shift.library import create_voice_model_record, create_voice_profile
from timbre_shift.pipeline import PipelineOptions, run_demo
from timbre_shift.engines.base import EngineResult


def fake_normalize(source: Path, target: Path, **kwargs) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(Path(source).read_bytes())
    return target


class FakeRVCMLXEngine:
    id = "rvc_mlx"
    name = "RVC-MLX Experimental"
    requires_training = True

    def __init__(self, converted: Path) -> None:
        self.converted = converted
        self.called = False

    def check(self):
        return {"available": True}

    def is_available(self):
        return True

    def convert(self, **kwargs):
        self.called = True
        return EngineResult(
            converted_vocal_path=self.converted,
            engine_id=self.id,
            engine_name=self.name,
            seconds=2.0,
            device="mlx",
            cache_hit=False,
        )


class PipelineEngineTests(unittest.TestCase):
    def test_rvc_mlx_without_model_has_clear_error(self):
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

            with patch("timbre_shift.pipeline.normalize_audio", side_effect=fake_normalize), \
                patch("timbre_shift.pipeline.middle_start", return_value=None), \
                patch("timbre_shift.pipeline.probe_duration", return_value=10.0):
                with self.assertRaisesRegex(FileNotFoundError, "RVC-MLX 模型不存在"):
                    run_demo(
                        PipelineOptions(
                            voice_profile_id=profile.id,
                            song=song,
                            seed_vc_dir=seed_vc_dir,
                            library_db_path=db_path,
                            work_dir=root / "work",
                            output_dir=root / "out",
                            skip_separation=True,
                            engine_id="rvc_mlx",
                        )
                    )

    def test_rvc_mlx_with_ready_model_calls_engine(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "library.db"
            seed_vc_dir = root / "seed-vc"
            seed_vc_dir.mkdir()
            (seed_vc_dir / "inference.py").write_text("")
            raw = root / "raw.wav"
            song = root / "song.wav"
            model_path = root / "model.mlx"
            converted = root / "converted.wav"
            final = root / "final.wav"
            for path in [raw, song, model_path, converted, final]:
                path.write_bytes(path.name.encode())
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
            create_voice_model_record(
                profile.id,
                engine_id="rvc_mlx",
                model_name="RVC",
                model_path=model_path,
                status="ready",
                db_path=db_path,
            )
            fake_engine = FakeRVCMLXEngine(converted)

            with patch("timbre_shift.pipeline.get_engine", return_value=fake_engine), \
                patch("timbre_shift.pipeline.normalize_audio", side_effect=fake_normalize), \
                patch("timbre_shift.pipeline.middle_start", return_value=None), \
                patch("timbre_shift.pipeline.probe_duration", return_value=10.0), \
                patch("timbre_shift.pipeline.polish_vocal", side_effect=lambda source, output: source), \
                patch("timbre_shift.pipeline.export_mp3", return_value=root / "out" / "final.mp3"):
                result = run_demo(
                    PipelineOptions(
                        voice_profile_id=profile.id,
                        song=song,
                        seed_vc_dir=seed_vc_dir,
                        library_db_path=db_path,
                        work_dir=root / "work",
                        output_dir=root / "out",
                        skip_separation=True,
                        engine_id="rvc_mlx",
                    )
                )

            self.assertTrue(fake_engine.called)
            self.assertEqual(result.read_bytes(), converted.read_bytes())


if __name__ == "__main__":
    unittest.main()
