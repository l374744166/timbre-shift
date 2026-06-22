import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from audio_test_utils import write_test_wav
from timbre_shift.diction import enhance_diction


class DictionTests(unittest.TestCase):
    def test_off_copies_audio(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = write_test_wav(root / "source.wav")
            converted = write_test_wav(root / "converted.wav", freq=330)
            output = enhance_diction(converted, source, root / "out.wav", mode="off")

            self.assertTrue(output.exists())
            self.assertEqual(output.read_bytes(), converted.read_bytes())

    def test_strength_modes_write_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = write_test_wav(root / "source.wav")
            converted = write_test_wav(root / "converted.wav", freq=330)
            for mode in ["light", "medium", "strong"]:
                output = enhance_diction(converted, source, root / f"{mode}.wav", mode=mode)
                self.assertTrue(output.exists())
                self.assertGreater(output.stat().st_size, 100)


if __name__ == "__main__":
    unittest.main()
