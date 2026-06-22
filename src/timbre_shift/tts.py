"""Local text-to-speech helpers for spoken voice conversion."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from .commands import require_binary, run_command


DEFAULT_SYSTEM_VOICE = "Tingting"
DEFAULT_PIPER_MODEL = Path("models/piper/zh_CN-huayan-medium.onnx")


def synthesize_text_to_wav(
    text: str,
    output: Path,
    *,
    voice: str = DEFAULT_SYSTEM_VOICE,
    rate: int = 0,
    provider: str = "auto",
    piper_model: Path | None = None,
) -> dict[str, object]:
    """Synthesize text into a mono 44.1 kHz WAV.

    Piper is preferred when a model path is provided; otherwise macOS `say`
    is used as a fast local fallback so demos work out of the box.
    """

    cleaned = " ".join(text.strip().split())
    if not cleaned:
        raise ValueError("请输入要朗读的文字")
    if len(cleaned) > 1000:
        raise ValueError("文字太长，建议先控制在 1000 字以内")

    output.parent.mkdir(parents=True, exist_ok=True)
    piper_model = piper_model or default_piper_model_from_env()
    selected_provider = provider
    if provider == "auto":
        selected_provider = "piper" if piper_model and piper_model.exists() and _piper_binary() else "system"

    if selected_provider == "piper":
        if not piper_model or not piper_model.exists():
            raise FileNotFoundError("未找到 Piper 模型文件")
        _synthesize_with_piper(cleaned, output, piper_model)
        return {"provider": "piper", "voice": piper_model.name, "text_length": len(cleaned)}

    _synthesize_with_macos_say(cleaned, output, voice=voice, rate=rate)
    return {"provider": "system", "voice": voice, "text_length": len(cleaned)}


def _synthesize_with_piper(text: str, output: Path, model: Path) -> None:
    piper = _piper_binary()
    if not piper:
        raise FileNotFoundError("未安装 Piper TTS")
    process = subprocess.run(
        [piper, "--model", str(model), "--output_file", str(output)],
        input=text,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError((process.stderr or process.stdout or "Piper TTS 生成失败").strip())


def _synthesize_with_macos_say(text: str, output: Path, *, voice: str, rate: int) -> None:
    say = require_binary("say")
    ffmpeg = require_binary("ffmpeg")
    if not say:
        raise FileNotFoundError("当前系统没有 say，本地 TTS 不可用")
    if not ffmpeg:
        raise FileNotFoundError("缺少 ffmpeg，无法转换 TTS 音频")

    with tempfile.TemporaryDirectory(prefix="timbre-shift-tts-") as temp_dir:
        aiff = Path(temp_dir) / "tts.aiff"
        command = [say, "-v", voice, "-o", str(aiff)]
        if rate:
            command.extend(["-r", str(rate)])
        command.append(text)
        run_command(command)
        run_command(
            [
                ffmpeg,
                "-y",
                "-i",
                str(aiff),
                "-ac",
                "1",
                "-ar",
                "44100",
                "-vn",
                str(output),
            ]
        )


def default_piper_model_from_env() -> Path | None:
    value = os.environ.get("TIMBRE_SHIFT_PIPER_MODEL", "").strip()
    if value:
        return Path(value).expanduser()
    default_model = Path.cwd() / DEFAULT_PIPER_MODEL
    return default_model if default_model.exists() else None


def _piper_binary() -> str | None:
    return require_binary("piper") or (str(Path.cwd() / ".venv" / "bin" / "piper") if (Path.cwd() / ".venv" / "bin" / "piper").exists() else None)
