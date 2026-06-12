"""Seed-VC inference wrapper."""

from __future__ import annotations

import sys
import subprocess
import hashlib
import json
import shutil
import time
from dataclasses import dataclass
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

SAFE_DEVICE_BLOCK = """# Timbre Shift local patch: explicit device selection with Apple Silicon support.
torch.set_default_dtype(torch.float32)
_requested_device = os.environ.get("SEED_VC_DEVICE", "auto").lower()
if _requested_device == "auto":
    if torch.cuda.is_available():
        device = torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")
else:
    device = torch.device(_requested_device)
print(f"[timbre-shift] Seed-VC device: {device}")
"""

WHISPER_FP16_LINE = (
    "        whisper_model = WhisperModel.from_pretrained(whisper_name, "
    "torch_dtype=torch.float16).to(device)"
)

WHISPER_DEVICE_DTYPE_LINES = """        _mps_fp16 = os.environ.get("SEED_VC_MPS_FP16", "0") == "1"
        whisper_dtype = torch.float16 if device.type == "cuda" or (device.type == "mps" and _mps_fp16) else torch.float32
        whisper_model = WhisperModel.from_pretrained(whisper_name, torch_dtype=whisper_dtype).to(device)"""


def _ensure_import_os(text: str) -> str:
    if "import os" in text:
        return text
    return "import os\n" + text


def ensure_seed_vc_mac_compat(seed_vc_dir: Path) -> None:
    inference = seed_vc_dir / "inference.py"
    text = inference.read_text()
    updated = _ensure_import_os(text)

    if DEVICE_BLOCK in updated:
        updated = updated.replace(DEVICE_BLOCK, SAFE_DEVICE_BLOCK)
    elif CPU_DEVICE_BLOCK in updated:
        updated = updated.replace(CPU_DEVICE_BLOCK, SAFE_DEVICE_BLOCK)

    if WHISPER_FP16_LINE in updated and WHISPER_DEVICE_DTYPE_LINES not in updated:
        updated = updated.replace(WHISPER_FP16_LINE, WHISPER_DEVICE_DTYPE_LINES)

    replacements = {
        "        F0_ori = torch.from_numpy(F0_ori).to(device)[None]":
            "        F0_ori = torch.from_numpy(F0_ori.astype(np.float32)).to(device)[None]",
        "        F0_alt = torch.from_numpy(F0_alt).to(device)[None]":
            "        F0_alt = torch.from_numpy(F0_alt.astype(np.float32)).to(device)[None]",
        "        F0_ori = torch.from_numpy(F0_ori).float().to(device)[None]":
            "        F0_ori = torch.from_numpy(F0_ori.astype(np.float32)).to(device)[None]",
        "        F0_alt = torch.from_numpy(F0_alt).float().to(device)[None]":
            "        F0_alt = torch.from_numpy(F0_alt.astype(np.float32)).to(device)[None]",
    }
    for old, new in replacements.items():
        updated = updated.replace(old, new)

    if updated != text:
        inference.write_text(updated)


@dataclass(frozen=True)
class SeedVCResult:
    output: Path
    cache_hit: bool
    elapsed_seconds: float
    cache_key: str
    device_requested: str
    device_used: str
    cpu_fallback_used: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seedvc_cache_key(
    seed_vc_dir: Path,
    source_vocal: Path,
    target_voice: Path,
    target_voice_seconds: int,
    diffusion_steps: int,
    inference_cfg_rate: float,
    semi_tone_shift: int,
    device: str,
    f0_condition: bool = True,
    auto_f0_adjust: bool = False,
) -> str:
    inference = seed_vc_dir / "inference.py"
    payload = {
        "source_vocal_hash": sha256_file(source_vocal),
        "target_voice_hash": sha256_file(target_voice),
        "target_voice_seconds": target_voice_seconds,
        "diffusion_steps": diffusion_steps,
        "inference_cfg_rate": inference_cfg_rate,
        "semi_tone_shift": semi_tone_shift,
        "f0_condition": f0_condition,
        "auto_f0_adjust": auto_f0_adjust,
        "inference_hash": sha256_file(inference) if inference.exists() else "",
        "device_family": device,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def convert_singing_voice_result(
    seed_vc_dir: Path,
    source_vocal: Path,
    target_voice: Path,
    output_dir: Path,
    diffusion_steps: int = 10,
    length_adjust: float = 1.0,
    inference_cfg_rate: float = 0.0,
    semi_tone_shift: int = 0,
    fp16: bool = False,
    device: str = "mps",
    target_voice_seconds: int = 16,
    cache_dir: Path | None = None,
    allow_cpu_fallback: bool = False,
    mps_fallback: bool = True,
    retry_cpu_on_failure: bool | None = None,
) -> SeedVCResult:
    start = time.perf_counter()
    ensure_seed_vc_mac_compat(seed_vc_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    key = seedvc_cache_key(
        seed_vc_dir=seed_vc_dir,
        source_vocal=source_vocal,
        target_voice=target_voice,
        target_voice_seconds=target_voice_seconds,
        diffusion_steps=diffusion_steps,
        inference_cfg_rate=inference_cfg_rate,
        semi_tone_shift=semi_tone_shift,
        device=device,
    )
    if cache_dir:
        cached_dir = cache_dir / "seedvc" / key
        cached_output = cached_dir / "converted.wav"
        if cached_output.exists():
            output = output_dir / f"converted-{key[:12]}.wav"
            shutil.copy2(cached_output, output)
            return SeedVCResult(
                output=output,
                cache_hit=True,
                elapsed_seconds=0.0,
                cache_key=key,
                device_requested=device,
                device_used=device,
                cpu_fallback_used=False,
            )

    job_dir = output_dir / f"seedvc-{key[:12]}"
    job_dir.mkdir(parents=True, exist_ok=True)
    command = as_strs(
        [
            sys.executable,
            "inference.py",
            "--source",
            source_vocal.resolve(),
            "--target",
            target_voice.resolve(),
            "--output",
            job_dir.resolve(),
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
    )
    env = {
        "SEED_VC_DEVICE": device,
        "SEED_VC_MPS_FP16": "1" if fp16 else "0",
    }
    if mps_fallback:
        env["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    cpu_fallback_used = False
    try:
        run_command(command, cwd=seed_vc_dir, extra_env=env)
    except subprocess.CalledProcessError:
        if retry_cpu_on_failure is not None:
            allow_cpu_fallback = retry_cpu_on_failure
        if not allow_cpu_fallback or device == "cpu":
            log_dir = Path("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "seedvc_mps_error.log").write_text(
                "MPS failed; CPU fallback disabled for full-song mode.\n",
                encoding="utf-8",
            )
            raise
        cpu_fallback_used = True
        run_command(
            command,
            cwd=seed_vc_dir,
            extra_env={"SEED_VC_DEVICE": "cpu", "SEED_VC_MPS_FP16": "0"},
        )
    candidates = sorted(job_dir.glob("*.wav"), key=lambda path: path.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"Seed-VC did not write a wav file in {job_dir}")
    output = output_dir / f"converted-{key[:12]}.wav"
    shutil.copy2(candidates[-1], output)
    elapsed = time.perf_counter() - start
    if cache_dir:
        cached_dir = cache_dir / "seedvc" / key
        cached_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output, cached_dir / "converted.wav")
        (cached_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "cache_key": key,
                    "diffusion_steps": diffusion_steps,
                    "inference_cfg_rate": inference_cfg_rate,
                    "semi_tone_shift": semi_tone_shift,
                    "device": "cpu" if cpu_fallback_used else device,
                    "elapsed_seconds": elapsed,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return SeedVCResult(
        output=output,
        cache_hit=False,
        elapsed_seconds=elapsed,
        cache_key=key,
        device_requested=device,
        device_used="cpu" if cpu_fallback_used else device,
        cpu_fallback_used=cpu_fallback_used,
    )


def convert_singing_voice(
    seed_vc_dir: Path,
    source_vocal: Path,
    target_voice: Path,
    output_dir: Path,
    diffusion_steps: int = 10,
    length_adjust: float = 1.0,
    inference_cfg_rate: float = 0.0,
    semi_tone_shift: int = 0,
    fp16: bool = False,
    device: str = "mps",
    mps_fallback: bool = True,
    retry_cpu_on_failure: bool = True,
) -> Path:
    return convert_singing_voice_result(
        seed_vc_dir=seed_vc_dir,
        source_vocal=source_vocal,
        target_voice=target_voice,
        output_dir=output_dir,
        diffusion_steps=diffusion_steps,
        length_adjust=length_adjust,
        inference_cfg_rate=inference_cfg_rate,
        semi_tone_shift=semi_tone_shift,
        fp16=fp16,
        device=device,
        allow_cpu_fallback=retry_cpu_on_failure,
        mps_fallback=mps_fallback,
    ).output
