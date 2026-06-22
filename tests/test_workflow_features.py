import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from audio_test_utils import write_test_wav
from timbre_shift.audio import limit_audio_peak
from timbre_shift.download_names import build_output_basename
from timbre_shift.generation_history import archive_generation_history, list_generation_history
from timbre_shift.library import create_empty_voice_profile, list_voice_samples
from timbre_shift.history_actions import delete_history_job, restore_history_job
from timbre_shift.mix_styles import get_mix_style
from timbre_shift.pre_rvc_cleanup import preprocess_source_vocal_for_rvc
from timbre_shift.result_scorecard import build_result_scorecard
from timbre_shift.voice_preferences import get_voice_preference, save_voice_preference


class WorkflowFeatureTests(unittest.TestCase):
    def test_voice_preference_round_trip(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "voice_preferences.json"
            saved = save_voice_preference(
                "voice_1",
                {
                    "engine_id": "rvc_applio",
                    "rvc_goal": "clear_diction",
                    "diction_mode": "medium",
                    "vocal_style": "close_intimate",
                    "mix_style": "vocal_forward",
                    "ignored": "nope",
                },
                path=path,
            )

            loaded = get_voice_preference("voice_1", path=path)

            self.assertEqual(saved["rvc_goal"], "clear_diction")
            self.assertEqual(loaded["mix_style"], "vocal_forward")
            self.assertNotIn("ignored", loaded)

    def test_mix_style_presets_have_expected_gains(self):
        self.assertEqual(get_mix_style("natural").backing_gain, 0.90)
        self.assertGreater(get_mix_style("vocal_forward").vocal_gain, 1.0)
        self.assertGreater(get_mix_style("blend_with_backing").backing_gain, 0.90)
        self.assertEqual(get_mix_style("missing").id, "natural")

    def test_create_empty_rvc_voice_library(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = create_empty_voice_profile(
                "毛不易音色库",
                library_dir=root / "library",
                db_path=root / "library.db",
            )
            samples = list_voice_samples(profile.id, db_path=root / "library.db")

            self.assertEqual(profile.name, "毛不易音色库")
            self.assertEqual(profile.source_type, "rvc_training_library")
            self.assertTrue(profile.allowed_as_target)
            self.assertEqual(profile.duration_seconds, 0.0)
            self.assertEqual(samples, [])

    def test_pre_rvc_cleanup_modes_write_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = write_test_wav(root / "source.wav")
            for mode in ["off", "standard", "strong"]:
                output = preprocess_source_vocal_for_rvc(source, root / f"{mode}.wav", mode=mode)
                self.assertTrue(output.exists())
                self.assertGreater(output.stat().st_size, 100)

    def test_generation_history_archives_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "outputs" / "web"
            output_dir.mkdir(parents=True)
            write_test_wav(output_dir / "final.wav")
            write_test_wav(output_dir / "dry_vocal.wav")
            (output_dir / "final.mp3").write_bytes(b"fake mp3")
            (output_dir / "dry_vocal.mp3").write_bytes(b"fake dry mp3")
            metrics = {"rvc_preset": "stable_balanced", "mix_style": "natural", "total_seconds": 3.5}
            (output_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")

            history_dir = archive_generation_history(
                output_dir,
                metrics,
                voice_profile_id="voice_1",
                voice_profile_name="Demo Voice",
                song_id="song_1",
                song_title="Demo Song",
                engine_id="rvc_applio",
                render_mode="m2max_hq_30",
            )
            jobs = list_generation_history(root / "outputs" / "history")

            self.assertTrue((history_dir / "final.wav").exists())
            self.assertTrue((history_dir / "final.mp3").exists())
            self.assertTrue((history_dir / "dry_vocal.wav").exists())
            self.assertTrue((history_dir / "dry_vocal.mp3").exists())
            self.assertEqual(jobs[0]["voice_profile_name"], "Demo Voice")
            self.assertTrue(jobs[0]["has_mp3"])
            self.assertTrue(jobs[0]["has_dry_vocal_mp3"])
            self.assertEqual(jobs[0]["rvc_preset"], "stable_balanced")

    def test_history_restore_and_delete(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "outputs" / "web"
            output_dir.mkdir(parents=True)
            write_test_wav(output_dir / "final.wav")
            write_test_wav(output_dir / "dry_vocal.wav")
            (output_dir / "final.mp3").write_bytes(b"fake mp3")
            (output_dir / "dry_vocal.mp3").write_bytes(b"fake dry mp3")
            metrics = {"rvc_preset": "clear_diction", "mix_style": "vocal_forward"}
            (output_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")

            history_dir = archive_generation_history(
                output_dir,
                metrics,
                voice_profile_id="voice_1",
                voice_profile_name="Demo Voice",
                song_id=None,
                song_title="Demo Song",
                engine_id="rvc_applio",
                render_mode="m2max_hq_30",
            )
            current_dir = root / "outputs" / "current"

            payload = restore_history_job(root / "outputs" / "history", current_dir, history_dir.name)
            self.assertEqual(payload["message"], "已设为当前最终版本")
            self.assertTrue((current_dir / "final.wav").exists())
            self.assertTrue((current_dir / "dry_vocal.wav").exists())
            self.assertEqual(payload["dry_vocal_download_mp3_url"], "/download/dry_vocal.mp3")

            delete_history_job(root / "outputs" / "history", history_dir.name)
            self.assertFalse(history_dir.exists())

    def test_result_scorecard_and_download_name(self):
        metrics = {
            "voice_profile_name": "三首歌音色",
            "song_title": "测试歌",
            "rvc_preset": "clear_diction",
            "diction_mode": "medium",
            "mix_style": "vocal_forward",
            "active_ratio": 0.6,
            "final_peak_after": 0.91,
            "clipping_prevented": True,
            "diagnostics": {"issues": []},
        }

        cards = build_result_scorecard(metrics)
        basename = build_output_basename(metrics)

        self.assertEqual(cards[0]["label"], "音量安全")
        self.assertIn("三首歌音色", basename)
        self.assertIn("歌词更清楚", basename)

    def test_limit_audio_peak_writes_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = write_test_wav(root / "source.wav", seconds=0.35)
            output = limit_audio_peak(source, root / "limited.wav")

            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 100)


if __name__ == "__main__":
    unittest.main()
