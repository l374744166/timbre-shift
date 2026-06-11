import tempfile
import unittest
from pathlib import Path

from timbre_shift.seed_vc import ensure_seed_vc_mac_compat


class SeedVcTests(unittest.TestCase):
    def test_mac_compat_patch_forces_cpu_and_float32_f0(self):
        original = """import os
import torch
if torch.cuda.is_available():
    device = torch.device("cuda")
elif torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")
        whisper_model = WhisperModel.from_pretrained(whisper_name, torch_dtype=torch.float16).to(device)
        F0_ori = torch.from_numpy(F0_ori).to(device)[None]
        F0_alt = torch.from_numpy(F0_alt).to(device)[None]
"""
        with tempfile.TemporaryDirectory() as tmp:
            inference = Path(tmp) / "inference.py"
            inference.write_text(original)

            ensure_seed_vc_mac_compat(Path(tmp))

            patched = inference.read_text()
            self.assertIn('torch.device(os.environ.get("SEED_VC_DEVICE", "cpu"))', patched)
            self.assertIn("torch.float32", patched)
            self.assertIn("torch.from_numpy(F0_ori).float().to(device)[None]", patched)
