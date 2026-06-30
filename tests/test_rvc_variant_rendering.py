from pathlib import Path
from tempfile import TemporaryDirectory

from timbre_shift.pipeline_rvc import _render_rvc_variants


def test_rvc_variants_skip_current_selected_preset(monkeypatch):
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        base = root / "base.wav"
        source = root / "source.wav"
        base.write_bytes(b"base")
        source.write_bytes(b"source")

        def fake_postprocess(converted_vocal, source_vocal, converted_dir, **kwargs):
            converted_dir.mkdir(parents=True, exist_ok=True)
            processed = converted_dir / "processed.wav"
            processed.write_bytes(b"processed")
            return processed, {"consonant_blend": 0.0}

        monkeypatch.setattr("timbre_shift.pipeline_rvc._postprocess_rvc_vocal", fake_postprocess)
        monkeypatch.setattr("timbre_shift.pipeline_rvc.export_mp3", lambda wav, mp3: mp3)

        variants = _render_rvc_variants(
            base_vocal=base,
            source_vocal=source,
            backing_track=None,
            converted_dir=root / "work",
            output_dir=root / "out",
            exclude_preset_id="stable_balanced",
        )

        ids = [item["id"] for item in variants]
        assert ids == ["clear_diction", "stronger_timbre_safe"]
        assert "stable_balanced" not in ids
