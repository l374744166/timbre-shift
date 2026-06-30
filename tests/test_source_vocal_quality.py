from __future__ import annotations

import math
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

from timbre_shift.source_vocal_quality import analyze_source_vocal_quality


def write_wave(path: Path, samples: list[float], sample_rate: int = 44100) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        data = bytearray()
        for sample in samples:
            value = int(max(-0.99, min(0.99, sample)) * 32767)
            data.extend(value.to_bytes(2, "little", signed=True))
        wav.writeframes(bytes(data))
    return path


def test_clean_vocal_like_wav_is_ok():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        sample_rate = 44100
        samples = [0.2 * math.sin(2 * math.pi * 220 * i / sample_rate) for i in range(sample_rate)]
        wav = write_wave(root / "clean.wav", samples, sample_rate)

        result = analyze_source_vocal_quality(wav, root / "quality.json", segment_seconds=0.25)

        assert result["source_quality_summary"] in {"良好", "一般"}
        assert result["source_problem_segment_count"] == 0
        assert (root / "quality.json").exists()


def test_high_frequency_noise_is_warning_or_bad():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        sample_rate = 44100
        samples = []
        for i in range(sample_rate):
            base = 0.12 * math.sin(2 * math.pi * 220 * i / sample_rate)
            harsh = 0.42 * math.sin(2 * math.pi * 7600 * i / sample_rate)
            samples.append(base + harsh)
        wav = write_wave(root / "harsh.wav", samples, sample_rate)

        result = analyze_source_vocal_quality(wav, segment_seconds=0.25)

        assert result["source_problem_segment_count"] > 0
        assert result["source_quality_summary"] in {"一般", "高潮段有风险"}
        assert result["source_high_freq_risk"] or result["source_harshness_risk"]
