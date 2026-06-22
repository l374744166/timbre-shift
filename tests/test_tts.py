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

    result = tts.synthesize_text_to_wav("你好，测试。", tmp_path / "out.wav", voice="Tingting")

    assert result["provider"] == "system"
    assert result["voice"] == "Tingting"
    assert any("say" in Path(command[0]).name for command in commands)
    assert any("ffmpeg" in Path(command[0]).name for command in commands)
