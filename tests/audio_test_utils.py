from __future__ import annotations

import math
import wave
from pathlib import Path


def write_test_wav(path: Path, seconds: float = 0.35, freq: float = 440.0, sample_rate: int = 44100) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        data = bytearray()
        for index in range(frames):
            sample = int(0.25 * 32767 * math.sin(2 * math.pi * freq * index / sample_rate))
            data.extend(sample.to_bytes(2, byteorder="little", signed=True))
        wav.writeframes(bytes(data))
    return path
