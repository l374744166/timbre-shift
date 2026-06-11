"""Seed-VC inference wrapper."""

from __future__ import annotations

import sys
from pathlib import Path

from .commands import as_strs, bool_arg, run_command


DEVICE_BLOCK = """if torch.cuda.is_available():
    device = torch.device("cuda")
elif torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")
"""

CPU_DEVICE_BLOCK = """# Timbre Shift local patch: CPU is slower, but avoids macOS MPS float64 crashes.
device = torch.device(os.environ.get("SEED_VC_DEVICE", "cpu"))
"""

WHISPER_FP16_LINE = (
    "        whisper_model = WhisperModel.from_pretrained(whisper_name, "
    "torch_dtype=torch.float16).to(device)"
)

WHISPER_DEVICE_DTYPE_LINES = """        whisper_dtype = torch.float16 if device.type != "cpu" else torch.float32
        whisper_model = WhisperModel.from_pretrained(whisper_name, torch_dtype=whisper_dtype).to(device)"""


def ensure_seed_vc_mac_compat(seed_vc_dir: Path) -> None:
    inference = seed_vc_dir / "inference.py"
    text = inference.read_text()
    updated = text

    if DEVICE_BLOCK in updated and CPU_DEVICE_BLOCK not in updated:
        updated = updated.replace(DEVICE_BLOCK, CPU_DEVICE_BLOCK)

    if WHISPER_FP16_LINE in updated and WHISPER_DEVICE_DTYPE_LINES not in updated:
        updated = updated.replace(WHISPER_FP16_LINE, WHISPER_DEVICE_DTYPE_LINES)

    updated = updated.replace(
        "        F0_ori = torch.from_numpy(F0_ori).to(device)[None]\n"
        "        F0_alt = torch.from_numpy(F0_alt).to(device)[None]",
        "        F0_ori = torch.from_numpy(F0_ori).float().to(device)[None]\n"
        "        F0_alt = torch.from_numpy(F0_alt).float().to(device)[None]",
    )

    if updated != text:
        inference.write_text(updated)


def convert_singing_voice(
    seed_vc_dir: Path,
    source_vocal: Path,
    target_voice: Path,
    output_dir: Path,
    diffusion_steps: int = 40,
    length_adjust: float = 1.0,
    inference_cfg_rate: float = 0.7,
    semi_tone_shift: int = 0,
    fp16: bool = False,
) -> Path:
    ensure_seed_vc_mac_compat(seed_vc_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_command(
        as_strs(
            [
                sys.executable,
                "inference.py",
                "--source",
                source_vocal.resolve(),
                "--target",
                target_voice.resolve(),
                "--output",
                output_dir.resolve(),
                "--diffusion-steps",
                diffusion_steps,
                "--length-adjust",
                length_adjust,
                "--inference-cfg-rate",
                inference_cfg_rate,
                "--f0-condition",
                "True",
                "--auto-f0-adjust",
                "False",
                "--semi-tone-shift",
                semi_tone_shift,
                "--fp16",
                bool_arg(fp16),
            ]
        ),
        cwd=seed_vc_dir,
    )
    candidates = sorted(output_dir.glob("*.wav"), key=lambda path: path.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"Seed-VC did not write a wav file in {output_dir}")
    return candidates[-1]
