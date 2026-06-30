from pathlib import Path
from tempfile import TemporaryDirectory

from timbre_shift.pipeline import PipelineOptions, run_demo
from timbre_shift.engines.base import EngineResult
from timbre_shift.library import create_voice_model_record, create_voice_profile
from audio_test_utils import write_test_wav


class FakeApplioEngine:
    id = "rvc_applio"
    name = "Applio RVC"
    requires_training = True

    def __init__(self) -> None:
        self.calls = 0

    def check(self):
        return {"available": True}

    def is_available(self):
        return True

    def convert(self, **kwargs):
        self.calls += 1
        output_dir = Path(kwargs["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / f"converted_{self.calls}.wav"
        write_test_wav(output, seconds=0.3, freq=440 + self.calls * 20)
        return EngineResult(
            converted_vocal_path=output,
            engine_id=self.id,
            engine_name=self.name,
            seconds=0.5,
            device="cpu",
            cache_hit=False,
        )


def test_warning_source_adds_ai_source_repair_variant(monkeypatch):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        db_path = root / "library.db"
        seed_vc_dir = root / "seed-vc"
        seed_vc_dir.mkdir()
        (seed_vc_dir / "inference.py").write_text("")
        raw = write_test_wav(root / "raw.wav", seconds=0.3)
        song = write_test_wav(root / "song.wav", seconds=0.3)
        model_path = root / "model.pth"
        model_path.write_bytes(b"model")
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
            engine_id="rvc_applio",
            model_name="RVC",
            model_path=model_path,
            status="ready",
            db_path=db_path,
        )
        fake_engine = FakeApplioEngine()
        monkeypatch.setattr("timbre_shift.pipeline.get_engine", lambda _engine_id: fake_engine)
        monkeypatch.setattr(
            "timbre_shift.pipeline.analyze_source_vocal_quality",
            lambda *args, **kwargs: {
                "source_quality_score": 45,
                "source_quality_summary": "高潮段有风险",
                "source_problem_segment_count": 1,
                "problem_segments": [{"start": 0, "end": 0.3, "risk_level": "bad"}],
                "source_has_clipping": False,
                "source_high_freq_risk": True,
                "source_harshness_risk": True,
                "harshness_score": 0.8,
            },
        )

        run_demo(
            PipelineOptions(
                voice_profile_id=profile.id,
                song=song,
                seed_vc_dir=seed_vc_dir,
                library_db_path=db_path,
                work_dir=root / "work",
                output_dir=root / "out",
                skip_separation=True,
                engine_id="rvc_applio",
                generate_variants=True,
                source_vocal_quality_enabled=True,
            )
        )

        metrics = (root / "out" / "metrics.json").read_text(encoding="utf-8")
        assert "ai_source_repair" in metrics
        assert fake_engine.calls >= 2
