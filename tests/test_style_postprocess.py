import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from audio_test_utils import write_test_wav
from timbre_shift.style_postprocess import STYLE_FILTERS, apply_vocal_style


class StylePostprocessTests(unittest.TestCase):
    def test_supported_styles_write_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            vocal = write_test_wav(root / "vocal.wav")
            for style in STYLE_FILTERS:
                output = apply_vocal_style(vocal, root / f"{style}.wav", style=style)
                self.assertTrue(output.exists())
                self.assertGreater(output.stat().st_size, 100)


if __name__ == "__main__":
    unittest.main()
