from pathlib import Path
from tempfile import TemporaryDirectory

from audio_test_utils import write_test_wav
from timbre_shift.deharsh import deharsh_converted_vocal


def test_deharsh_modes_write_output():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = write_test_wav(root / "converted.wav", seconds=0.2)
        for mode in ["off", "light", "medium", "strong", "rescue"]:
            output = deharsh_converted_vocal(source, root / f"{mode}.wav", mode=mode)
            assert output.exists()
            assert output.stat().st_size > 0
