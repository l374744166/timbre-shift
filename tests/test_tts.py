from pathlib import Path

import pytest

from timbre_shift import tts


def test_tts_rejects_empty_text(tmp_path):
    with pytest.raises(ValueError, match="请输入"):
        tts.synthesize_text_to_wav("", tmp_path / "out.wav")


def test_system_tts_uses_say_and_ffmpeg(monkeypatch, tmp_path):
    commands = []

    def fake_require_binary(name):
        return f"/usr/bin/{name}"

    def fake_run_command(command):
        commands.append(command)
        if "ffmpeg" in Path(command[0]).name:
            Path(command[-1]).write_bytes(b"wav")

    monkeypatch.setattr(tts, "require_binary", fake_require_binary)
    monkeypatch.setattr(tts, "run_command", fake_run_command)

    result = tts.synthesize_text_to_wav("你好，测试。", tmp_path / "out.wav", voice="Tingting", provider="system")

    assert result["provider"] == "system"
    assert result["voice"] == "Tingting"
    assert any("say" in Path(command[0]).name for command in commands)
    assert any("ffmpeg" in Path(command[0]).name for command in commands)


def test_piper_tts_passes_adjustment_controls(monkeypatch, tmp_path):
    commands = []
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"model")

    def fake_require_binary(name):
        return None

    def fake_piper_binary():
        return "/usr/local/bin/piper"

    def fake_run(command, **kwargs):
        commands.append(command)
        Path(command[command.index("--output_file") + 1]).write_bytes(b"wav")

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(tts, "require_binary", fake_require_binary)
    monkeypatch.setattr(tts, "_piper_binary", fake_piper_binary)
    monkeypatch.setattr(tts.subprocess, "run", fake_run)

    result = tts.synthesize_text_to_wav(
        "你好，慢一点测试。",
        tmp_path / "out.wav",
        provider="piper",
        piper_model=model,
        length_scale=1.35,
        noise_scale=0.45,
        noise_w_scale=0.5,
        sentence_silence=0.5,
        volume=1.2,
    )

    command = commands[0]
    assert result["provider"] == "piper"
    assert command[command.index("--length-scale") + 1] == "1.35"
    assert command[command.index("--noise-scale") + 1] == "0.45"
    assert command[command.index("--noise-w-scale") + 1] == "0.5"
    assert command[command.index("--sentence-silence") + 1] == "0.5"
    assert command[command.index("--volume") + 1] == "1.2"


def test_edge_tts_passes_chinese_voice_controls(monkeypatch, tmp_path):
    commands = []

    def fake_require_binary(name):
        return f"/usr/bin/{name}"

    def fake_run_command(command):
        commands.append(command)
        if "ffmpeg" in Path(command[0]).name:
            Path(command[-1]).write_bytes(b"wav")

    def fake_subprocess_run(command, **kwargs):
        commands.append(command)
        Path(command[command.index("--write-media") + 1]).write_bytes(b"mp3")

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(tts, "require_binary", fake_require_binary)
    monkeypatch.setattr(tts, "run_command", fake_run_command)
    monkeypatch.setattr(tts.subprocess, "run", fake_subprocess_run)

    result = tts.synthesize_text_to_wav(
        "你好，测试中文底声。",
        tmp_path / "out.wav",
        provider="edge",
        edge_voice="zh-CN-YunxiNeural",
        edge_rate=-8,
        edge_pitch=4,
        edge_volume=10,
    )

    edge_command = commands[0]
    assert result["provider"] == "edge"
    assert edge_command[edge_command.index("--voice") + 1] == "zh-CN-YunxiNeural"
    assert "--rate=-8%" in edge_command
    assert "--pitch=+4Hz" in edge_command
    assert "--volume=+10%" in edge_command
    assert any("ffmpeg" in Path(command[0]).name for command in commands)
