from pathlib import Path
from tempfile import TemporaryDirectory

from timbre_shift.demucs import SeparationResult
from timbre_shift.separation import _find_stem, separate_vocals_smart


def test_demucs_high_quality_uses_stronger_demucs_settings(monkeypatch):
    calls = {}

    def fake_demucs(song, output_dir, model, cache_dir, overlap, shifts):
        calls.update(model=model, overlap=overlap, shifts=shifts)
        vocals = output_dir / "vocals.wav"
        backing = output_dir / "no_vocals.wav"
        vocals.parent.mkdir(parents=True, exist_ok=True)
        vocals.write_bytes(b"v")
        backing.write_bytes(b"b")
        return SeparationResult(vocals=vocals, backing=backing)

    monkeypatch.setattr("timbre_shift.separation.separate_vocals", fake_demucs)
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        song = root / "song.wav"
        song.write_bytes(b"song")
        result = separate_vocals_smart(song, root / "out", mode="demucs_high_quality", overlap=0.1, shifts=0)

    assert result.mode == "demucs_high_quality"
    assert result.engine == "demucs"
    assert calls == {"model": "htdemucs_ft", "overlap": 0.25, "shifts": 1}


def test_ai_tolerant_falls_back_when_audio_separator_missing(monkeypatch):
    def fake_audio_separator(*args, **kwargs):
        raise FileNotFoundError("missing")

    def fake_demucs(song, output_dir, model, cache_dir, overlap, shifts):
        vocals = output_dir / "vocals.wav"
        backing = output_dir / "no_vocals.wav"
        vocals.parent.mkdir(parents=True, exist_ok=True)
        vocals.write_bytes(b"v")
        backing.write_bytes(b"b")
        return SeparationResult(vocals=vocals, backing=backing)

    monkeypatch.setattr("timbre_shift.separation._separate_with_audio_separator", fake_audio_separator)
    monkeypatch.setattr("timbre_shift.separation.separate_vocals", fake_demucs)
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        song = root / "song.wav"
        song.write_bytes(b"song")
        result = separate_vocals_smart(song, root / "out", mode="ai_tolerant")

    assert result.mode == "ai_tolerant"
    assert result.engine == "demucs_high_quality"
    assert result.fallback_used is True
    assert "missing" in (result.fallback_reason or "")


def test_find_audio_separator_stems_by_common_names():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        vocals = root / "song_(Vocals).wav"
        backing = root / "song_(Instrumental).wav"
        vocals.write_bytes(b"v")
        backing.write_bytes(b"b")

        assert _find_stem(root, "vocals") == vocals
        assert _find_stem(root, "backing") == backing
