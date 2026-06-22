"""Applio RVC inference helpers."""

from __future__ import annotations

import os
import time
from pathlib import Path

from .engines.base import EngineResult
from .rvc_applio_runtime import ApplioCommandError, _run_applio_python, check_applio, resolve_applio_dir


APPLIO_ENGINE_ID = "rvc_applio"
APPLIO_ENGINE_NAME = "Applio RVC"


def convert_with_applio(
    source_vocal: Path,
    model_path: Path,
    output_dir: Path,
    options: dict[str, object],
    engine_id: str = APPLIO_ENGINE_ID,
    engine_name: str = APPLIO_ENGINE_NAME,
) -> EngineResult:
    start = time.perf_counter()
    source_vocal = source_vocal.resolve()
    model_path = model_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "converted-applio.wav"
    root = resolve_applio_dir(Path(str(options["applio_dir"])) if options.get("applio_dir") else None)
    check = check_applio(root)
    if not check.available:
        raise RuntimeError(f"Applio RVC 未安装或未配置：{', '.join(check.missing)}")

    original_index_path = options.get("index_path")

    def infer_code(index_path: object, index_rate: float) -> str:
        return f"""
from core import run_infer_script
_, written = run_infer_script(
    pitch={int(options.get("pitch_shift", 0))},
    index_rate={index_rate},
    volume_envelope={float(options.get("volume_envelope", 1.0))},
    protect={float(options.get("protect", 0.33))},
    f0_method={str(options.get("f0_method", "rmvpe"))!r},
    input_path={str(source_vocal)!r},
    output_path={str(output)!r},
    pth_path={str(model_path)!r},
    index_path={str(index_path or "")!r},
    split_audio={bool(options.get("split_audio", False))!r},
    f0_autotune={bool(options.get("f0_autotune", False))!r},
    f0_autotune_strength={float(options.get("f0_autotune_strength", 1.0))},
    proposed_pitch={bool(options.get("proposed_pitch", False))!r},
    proposed_pitch_threshold={float(options.get("proposed_pitch_threshold", 155.0))},
    clean_audio={bool(options.get("clean_audio", True))!r},
    clean_strength={float(options.get("clean_strength", 0.35))},
    export_format="WAV",
    embedder_model={str(options.get("embedder_model", "contentvec"))!r},
)
print(written)
"""

    index_rate = float(options.get("index_rate", os.environ.get("TIMBRE_SHIFT_APPLIO_INDEX_RATE", "0.0") or "0.0"))
    index_path = original_index_path if index_rate > 0 else ""
    index_fallback_used = False
    crashed = False
    crash_signal = None
    try:
        _run_applio_python(root, infer_code(index_path, index_rate))
    except ApplioCommandError as exc:
        is_native_crash = exc.return_code < 0
        if not index_path or index_rate <= 0 or not is_native_crash:
            raise
        crashed = True
        crash_signal = f"SIG{-exc.return_code}" if exc.return_code < 0 else str(exc.return_code)
        try:
            log_dir = output_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "applio_rvc_error.log").write_text(
                "\n".join(
                    [
                        f"Applio RVC crashed with return code {exc.return_code}",
                        f"Signal: {crash_signal}",
                        f"Model: {model_path}",
                        f"Source: {source_vocal}",
                        f"Index: {index_path}",
                        "Output tail:",
                        *exc.output_tail[-20:],
                    ]
                ),
                encoding="utf-8",
            )
        except OSError:
            pass
        print("Applio RVC index inference crashed; retrying without FAISS index.")
        index_path = ""
        index_rate = 0.0
        index_fallback_used = True
        _run_applio_python(root, infer_code(index_path, index_rate))

    if not output.exists():
        raise FileNotFoundError(f"Applio RVC did not write output: {output}")
    return EngineResult(
        converted_vocal_path=output,
        engine_id=engine_id,
        engine_name=engine_name,
        seconds=time.perf_counter() - start,
        device="cpu",
        cache_hit=False,
        metadata={
            "model_path": str(model_path),
            "index_path": str(original_index_path) if original_index_path else None,
            "effective_index_path": str(index_path) if index_path else None,
            "index_rate": index_rate,
            "index_fallback_used": index_fallback_used,
            "crashed": crashed,
            "crash_signal": crash_signal,
        },
    )
