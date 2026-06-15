import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from timbre_shift.library import (
    archive_song,
    archive_voice_profile,
    get_song,
    init_library,
    list_songs,
    list_voice_profiles,
    save_song_to_library,
    add_voice_sample_to_profile,
    list_voice_samples,
    save_voice_to_library,
    update_song_stems,
)


class LibraryTests(unittest.TestCase):
    def test_init_library_creates_tables(self):
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "library.db"

            init_library(db_path)

            self.assertTrue(db_path.exists())

    def test_save_voice_to_library_filters_allowed_targets(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "library.db"
            audio = root / "voice.wav"
            other_audio = root / "other.wav"
            audio.write_bytes(b"voice")
            other_audio.write_bytes(b"other")

            with patch("timbre_shift.library.normalize_audio", side_effect=self.fake_normalize), \
                patch("timbre_shift.library._make_preview_mp3", side_effect=self.fake_preview), \
                patch("timbre_shift.library._concat_audio_files", side_effect=lambda sources, output: self.fake_normalize(sources[0], output)), \
                patch("timbre_shift.library.probe_duration", return_value=5.0):
                allowed = save_voice_to_library(
                    audio,
                    "Mine",
                    rights_status="own_voice",
                    allowed_as_target=True,
                    library_dir=root / "library",
                    db_path=db_path,
                )
                blocked = save_voice_to_library(
                    other_audio,
                    "Other",
                    rights_status="unknown",
                    allowed_as_target=False,
                    library_dir=root / "library",
                    db_path=db_path,
                )

            targets = list_voice_profiles(only_allowed_targets=True, db_path=db_path)
            self.assertEqual([profile.id for profile in targets], [allowed.id])
            self.assertNotIn(blocked.id, [profile.id for profile in targets])

    def test_save_voice_to_library_allows_rebuilding_same_audio(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "library.db"
            audio = root / "voice.wav"
            audio.write_bytes(b"same")

            with patch("timbre_shift.library.normalize_audio", side_effect=self.fake_normalize), \
                patch("timbre_shift.library._make_preview_mp3", side_effect=self.fake_preview), \
                patch("timbre_shift.library.probe_duration", return_value=5.0):
                first = save_voice_to_library(audio, "One", library_dir=root / "library", db_path=db_path)
                second = save_voice_to_library(audio, "Two", library_dir=root / "library", db_path=db_path)

            self.assertNotEqual(first.id, second.id)
            self.assertEqual(len(list_voice_profiles(db_path=db_path)), 2)

    def test_save_voice_to_library_keeps_clean_sample_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "library.db"
            raw_audio = root / "song.mp3"
            clean_audio = root / "vocals.wav"
            raw_audio.write_bytes(b"raw")
            clean_audio.write_bytes(b"clean")

            with patch("timbre_shift.library.normalize_audio", side_effect=self.fake_normalize), \
                patch("timbre_shift.library._make_preview_mp3", side_effect=self.fake_preview), \
                patch("timbre_shift.library._concat_audio_files", side_effect=lambda sources, output: self.fake_normalize(sources[0], output)), \
                patch("timbre_shift.library.probe_duration", return_value=5.0):
                voice = save_voice_to_library(
                    raw_audio,
                    "Voice",
                    clean_audio=clean_audio,
                    rights_status="own_voice",
                    allowed_as_target=True,
                    library_dir=root / "library",
                    db_path=db_path,
                )

            samples = list_voice_samples(voice.id, db_path=db_path)
            self.assertEqual(len(samples), 1)
            self.assertTrue(Path(samples[0].raw_audio_path).exists())
            self.assertTrue(Path(samples[0].clean_audio_path).exists())

    def test_voice_profile_can_collect_multiple_samples(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "library.db"
            first_audio = root / "first.wav"
            second_audio = root / "second.wav"
            first_audio.write_bytes(b"first")
            second_audio.write_bytes(b"second")

            with patch("timbre_shift.library.normalize_audio", side_effect=self.fake_normalize), \
                patch("timbre_shift.library._make_preview_mp3", side_effect=self.fake_preview), \
                patch("timbre_shift.library._concat_audio_files", side_effect=lambda sources, output: self.fake_normalize(sources[0], output)), \
                patch("timbre_shift.library.probe_duration", return_value=5.0):
                voice = save_voice_to_library(
                    first_audio,
                    "Voice",
                    rights_status="own_voice",
                    allowed_as_target=True,
                    library_dir=root / "library",
                    db_path=db_path,
                )
                sample = add_voice_sample_to_profile(
                    voice.id,
                    second_audio,
                    name="Second",
                    library_dir=root / "library",
                    db_path=db_path,
                )

            samples = list_voice_samples(voice.id, db_path=db_path)
            self.assertEqual(len(samples), 2)
            self.assertEqual(sample.voice_id, voice.id)

    def test_save_song_and_update_stems(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "library.db"
            audio = root / "song.wav"
            vocals = root / "vocals.wav"
            backing = root / "no_vocals.wav"
            audio.write_bytes(b"song")
            vocals.write_bytes(b"vocals")
            backing.write_bytes(b"backing")

            with patch("timbre_shift.library.normalize_audio", side_effect=self.fake_normalize), \
                patch("timbre_shift.library.probe_duration", return_value=60.0):
                song = save_song_to_library(audio, "Song", library_dir=root / "library", db_path=db_path)

            updated = update_song_stems(song.id, vocals, backing, "htdemucs", "cache", db_path=db_path)

            self.assertEqual(updated.vocals_path, str(vocals))
            self.assertEqual(updated.no_vocals_path, str(backing))
            self.assertEqual(len(list_songs(db_path=db_path)), 1)
            self.assertEqual(get_song(song.id, db_path=db_path).demucs_model, "htdemucs")

    def test_archive_records_hides_them(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "library.db"
            voice_audio = root / "voice.wav"
            song_audio = root / "song.wav"
            voice_audio.write_bytes(b"voice")
            song_audio.write_bytes(b"song")

            with patch("timbre_shift.library.normalize_audio", side_effect=self.fake_normalize), \
                patch("timbre_shift.library._make_preview_mp3", side_effect=self.fake_preview), \
                patch("timbre_shift.library.probe_duration", return_value=5.0):
                voice = save_voice_to_library(voice_audio, "Voice", library_dir=root / "library", db_path=db_path)
                song = save_song_to_library(song_audio, "Song", library_dir=root / "library", db_path=db_path)

            archive_voice_profile(voice.id, db_path=db_path)
            archive_song(song.id, db_path=db_path)

            self.assertEqual(list_voice_profiles(db_path=db_path), [])
            self.assertEqual(list_songs(db_path=db_path), [])

    @staticmethod
    def fake_normalize(source, target, **kwargs):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(source).read_bytes())
        return target

    @staticmethod
    def fake_preview(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"preview")
        return target


if __name__ == "__main__":
    unittest.main()
