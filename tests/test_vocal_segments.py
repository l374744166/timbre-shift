import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from timbre_shift.vocal_segments import (
    VocalSegment,
    compact_vocals,
    detect_vocal_segments,
    restore_compact_vocals,
)


class VocalSegmentTests(unittest.TestCase):
    def test_detect_vocal_segments_inverts_silence(self):
        stderr = "\n".join(
            [
                "[silencedetect] silence_start: 0",
                "[silencedetect] silence_end: 1.0 | silence_duration: 1.0",
                "[silencedetect] silence_start: 3.0",
                "[silencedetect] silence_end: 4.0 | silence_duration: 1.0",
                "[silencedetect] silence_start: 8.0",
            ]
        )
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=stderr)

        with patch("timbre_shift.vocal_segments.probe_duration", return_value=10.0), \
            patch("timbre_shift.vocal_segments.subprocess.run", return_value=completed):
            segments, total = detect_vocal_segments(
                Path("vocals.wav"),
                padding=0.0,
                merge_gap=0.0,
                min_segment_duration=0.0,
            )

        self.assertEqual(total, 10.0)
        self.assertEqual(
            [(round(item.original_start, 1), round(item.original_end, 1)) for item in segments],
            [(1.0, 3.0), (4.0, 8.0)],
        )
        self.assertEqual(segments[1].compact_start, 2.0)

    def test_compact_vocals_uses_concat_filter(self):
        segments = [
            VocalSegment(1.0, 2.5, 0.0),
            VocalSegment(5.0, 6.0, 1.5),
        ]
        with patch("timbre_shift.vocal_segments.run_command") as run_command:
            compact_vocals(Path("vocals.wav"), Path("compact.wav"), segments)

        command = run_command.call_args.args[0]
        self.assertIn("concat=n=2", " ".join(command))
        self.assertIn("atrim=start=1.000:end=2.500", " ".join(command))

    def test_restore_compact_vocals_uses_original_delays(self):
        segments = [
            VocalSegment(1.0, 2.0, 0.0),
            VocalSegment(4.0, 5.0, 1.0),
        ]
        with patch("timbre_shift.vocal_segments.run_command") as run_command:
            restore_compact_vocals(Path("converted.wav"), Path("restored.wav"), segments, 6.0)

        command = run_command.call_args.args[0]
        joined = " ".join(command)
        self.assertIn("adelay=1000|1000", joined)
        self.assertIn("adelay=4000|4000", joined)
        self.assertIn("amix=inputs=3", joined)


if __name__ == "__main__":
    unittest.main()
