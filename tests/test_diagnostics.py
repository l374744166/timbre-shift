import math
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from timbre_shift.diagnostics import AnalyzerContext, analyze_generation


class DiagnosticsTests(unittest.TestCase):
    def test_rule_based_diagnostics_returns_stable_schema(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            vocal = root / "vocal.wav"
            final = root / "final.wav"
            self.write_wav(vocal, amplitude=0.05)
            self.write_wav(final, amplitude=1.0)

            report = analyze_generation(
                AnalyzerContext(
                    source_vocal=vocal,
                    converted_vocal=final,
                    polished_vocal=final,
                    final_mix=final,
                    active_ratio=0.2,
                )
            )

        self.assertEqual(report["version"], 1)
        self.assertEqual(report["analyzer_chain"], ["rules_v1"])
        self.assertIn("most_likely_issue", report)
        self.assertTrue(report["issues"])
        self.assertTrue(report["suggestions"])

    def write_wav(self, path: Path, amplitude: float) -> None:
        sample_rate = 16000
        duration = 1.0
        samples = np.arange(int(sample_rate * duration))
        audio = amplitude * np.sin(2 * math.pi * 440 * samples / sample_rate)
        pcm = np.clip(audio, -1.0, 1.0)
        pcm16 = (pcm * 32767).astype(np.int16)
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(pcm16.tobytes())


if __name__ == "__main__":
    unittest.main()
