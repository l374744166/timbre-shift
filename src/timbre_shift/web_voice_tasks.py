"""Voice-library task helpers used by the web API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .demucs import separate_vocals
from .library import (
    DEFAULT_DB_PATH,
    DEFAULT_LIBRARY_DIR,
    add_voice_sample_to_profile,
    list_voice_samples,
    save_voice_to_library,
)
from .vocal_segments import compact_for_conversion
from .web_state import PROGRESS


@dataclass(frozen=True)
class PreparedVoiceUpload:
    original: Path
    clean: Path
    source_type: str


def add_voice_samples_from_uploads(
    voice_uploads: list[Path],
    voice_name: str,
    voice_source_type: str,
    voice_profile_id: str,
    root: Path,
) -> dict[str, object]:
    if not voice_profile_id:
        raise ValueError("先选择一个已保存音色")

    PROGRESS.reset("准备添加声音素材", 5, "running")
    prepared = prepare_voice_uploads(
        voice_uploads,
        voice_source_type,
        root=root,
        output_subdir="voice_samples",
        task_label="素材",
    )
    sample = None
    added_count = 0
    for index, item in enumerate(prepared, start=1):
        if PROGRESS.is_cancelled():
            raise RuntimeError(f"任务已停止；已成功导入 {added_count}/{len(prepared)} 个素材")
        PROGRESS.update(f"添加素材并刷新参考音频 {index}/{len(prepared)}", 85)
        sample = add_voice_sample_to_profile(
            voice_id=voice_profile_id,
            input_audio=item.original,
            clean_audio=item.clean,
            name=voice_name if len(prepared) == 1 else f"{voice_name} {index}",
            source_type=item.source_type,
            library_dir=DEFAULT_LIBRARY_DIR,
            db_path=DEFAULT_DB_PATH,
        )
        added_count += 1

    sample_count = len(list_voice_samples(voice_profile_id, db_path=DEFAULT_DB_PATH))
    PROGRESS.update("素材已添加", 100, "completed")
    return {
        "id": sample.id if sample else None,
        "voice_profile_id": voice_profile_id,
        "sample_count": sample_count,
        "added_count": added_count,
        "requested_count": len(voice_uploads),
        "quality_score": sample.quality_score if sample else None,
        "noise_score": sample.noise_score if sample else None,
        "message": "素材已添加",
    }


def save_voice_profile_from_uploads(
    voice_uploads: list[Path],
    voice_name: str,
    voice_source_type: str,
    root: Path,
) -> dict[str, object]:
    PROGRESS.reset("准备保存音色", 5, "running")
    prepared = prepare_voice_uploads(
        voice_uploads,
        voice_source_type,
        root=root,
        output_subdir="voice_separated",
        task_label="音色",
    )
    PROGRESS.update("保存音色", 80)
    first = prepared[0]
    profile = save_voice_to_library(
        input_audio=first.original,
        clean_audio=first.clean,
        name=voice_name,
        description=None,
        source_type=first.source_type,
        rights_status="own_voice",
        allowed_as_target=True,
        library_dir=DEFAULT_LIBRARY_DIR,
        db_path=DEFAULT_DB_PATH,
    )
    for index, item in enumerate(prepared[1:], start=2):
        if PROGRESS.is_cancelled():
            raise RuntimeError(f"任务已停止；已成功保存 {index - 1}/{len(prepared)} 个音色素材")
        percent = min(98, 80 + int(index / len(prepared) * 15))
        PROGRESS.update(f"追加音色素材 {index}/{len(prepared)}", percent)
        add_voice_sample_to_profile(
            voice_id=profile.id,
            input_audio=item.original,
            clean_audio=item.clean,
            name=f"{voice_name} {index}",
            source_type=item.source_type,
            library_dir=DEFAULT_LIBRARY_DIR,
            db_path=DEFAULT_DB_PATH,
        )

    sample_count = len(list_voice_samples(profile.id, db_path=DEFAULT_DB_PATH))
    PROGRESS.update("音色已保存", 100, "completed")
    return {
        "id": profile.id,
        "name": profile.name,
        "source_type": first.source_type,
        "sample_count": sample_count,
        "added_count": len(prepared),
        "message": "音色已保存",
    }


def prepare_voice_uploads(
    voice_uploads: list[Path],
    voice_source_type: str,
    *,
    root: Path,
    output_subdir: str,
    task_label: str,
) -> list[PreparedVoiceUpload]:
    prepared: list[PreparedVoiceUpload] = []
    for index, voice_path in enumerate(voice_uploads, start=1):
        if PROGRESS.is_cancelled():
            raise RuntimeError(f"任务已停止；已成功准备 {len(prepared)}/{len(voice_uploads)} 个{task_label}素材")
        source_type = "upload_voice"
        clean_path = voice_path
        if voice_source_type == "mixed_voice":
            PROGRESS.reset(f"高质量分离{task_label}人声 {index}/{len(voice_uploads)}", 5, "running")
            separated = separate_vocals(
                voice_path,
                output_dir=root / "data" / "processed" / "web" / output_subdir,
                model="htdemucs_ft",
                cache_dir=root / "data" / "cache",
                overlap=0.25,
                shifts=0,
            )
            clean_path = separated.vocals
            source_type = "separated_compact_voice"
            try:
                PROGRESS.update(f"筛选有效{task_label}人声片段 {index}/{len(voice_uploads)}", 70)
                compact = compact_for_conversion(
                    separated.vocals,
                    clean_path.parent / f"compact_voice_{index}.wav",
                )
                clean_path = compact.audio
            except ValueError:
                source_type = "separated_voice"
        prepared.append(PreparedVoiceUpload(voice_path, clean_path, source_type))
    return prepared
