import unittest
from pathlib import Path
from unittest.mock import patch

from timbre_shift.audio import normalize_audio, polish_vocal


class AudioTests(unittest.TestCase):
    def test_normalize_audio_can_clip_duration(self):
        with patch("timbre_shift.audio.run_command") as run_command:
            normalize_audio(Path("song.mp3"), Path("song.wav"), duration_seconds=30)

        command = run_command.call_args.args[0]
        self.assertIn("-t", command)
        self.assertIn("30", command)

    def test_normalize_audio_can_start_from_middle(self):
        with patch("timbre_shift.audio.run_command") as run_command:
            normalize_audio(Path("song.mp3"), Path("song.wav"), duration_seconds=30, start_seconds=45.5)

        command = run_command.call_args.args[0]
        self.assertIn("-ss", command)
        self.assertIn("45.500", command)

    def test_polish_vocal_applies_song_ready_processing(self):
        with patch("timbre_shift.audio.run_command") as run_command:
            polish_vocal(Path("converted.wav"), Path("optimized.wav"))

        command = run_command.call_args.args[0]
        filters = command[command.index("-af") + 1]
        self.assertIn("highpass=f=70", filters)
        self.assertIn("deesser", filters)
        self.assertIn("acompressor", filters)
        self.assertIn("alimiter", filters)
        self.assertIn("loudnorm", filters)
