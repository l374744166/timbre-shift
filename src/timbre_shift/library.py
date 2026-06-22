"""Compatibility exports for the local SQLite-backed asset library."""

from __future__ import annotations

from .library_common import make_id, sha256_file, utc_now
from .library_db import DEFAULT_DB_PATH, DEFAULT_LIBRARY_DIR, VOICE_REF_SECONDS, connect, init_library
from .library_models import SongRecord, VoiceModel, VoiceProfile, VoiceSample
from .library_samples import (
    add_voice_sample,
    add_voice_sample_to_profile,
    archive_voice_sample,
    create_voice_sample_record,
    get_voice_sample,
    list_voice_samples,
    refresh_voice_profile_references,
)
from .library_songs import (
    archive_song,
    create_song_record,
    get_song,
    list_songs,
    save_song_to_library,
    update_song_stems,
)
from .library_voice_models import (
    archive_voice_model,
    create_voice_model_record,
    get_voice_model,
    get_voice_model_by_id,
    list_voice_models,
    update_voice_model_status,
)
from .library_voices import (
    archive_voice_profile,
    best_voice_reference,
    create_empty_voice_profile,
    create_voice_profile,
    get_voice_profile,
    list_voice_profiles,
    save_voice_to_library,
)
