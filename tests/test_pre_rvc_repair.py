from pathlib import Path
from tempfile import TemporaryDirectory

from audio_test_utils import write_test_wav
from timbre_shift.pre_rvc_repair import repair_source_vocal_before_rvc


def test_pre_rvc_repair_modes_write_output():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = write_test_wav(root / "source.wav", seconds=0.2)
        for mode in ["off", "standard", "ai_generated", "deharsh_strong", "noise_tolerant"]:
            output = repair_source_vocal_before_rvc(source, root / f"{mode}.wav", mode=mode)
            assert output.exists()
            assert output.stat().st_size > 0
