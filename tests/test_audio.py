import unittest
from pathlib import Path
from unittest.mock import patch

from timbre_shift.audio import normalize_audio


class AudioTests(unittest.TestCase):
    def test_normalize_audio_can_clip_duration(self):
        with patch("timbre_shift.audio.run_command") as run_command:
            normalize_audio(Path("song.mp3"), Path("song.wav"), duration_seconds=30)

        command = run_command.call_args.args[0]
        self.assertIn("-t", command)
        self.assertIn("30", command)

