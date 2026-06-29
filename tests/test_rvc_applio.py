import unittest
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from timbre_shift.rvc_applio import ApplioCheck, ApplioCommandError, convert_with_applio


class RVCApplioTests(unittest.TestCase):
    def test_convert_disables_index_by_default(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            applio_dir = root / "applio"
            applio_dir.mkdir()
            source = root / "source.wav"
            model = root / "model.pth"
            index = root / "model.index"
            output_dir = root / "out"
            source.write_bytes(b"source")
            model.write_bytes(b"model")
            index.write_bytes(b"index")
            check = ApplioCheck(True, applio_dir, applio_dir / "python", [])
            calls = []

            def fake_run(_root, code, on_output=None):
                calls.append(code)
                (output_dir / "converted-applio.wav").write_bytes(b"converted")

            with patch.dict("os.environ", {}, clear=True), \
                patch("timbre_shift.rvc_applio_infer.check_applio", return_value=check), \
                patch("timbre_shift.rvc_applio_infer._run_applio_python", side_effect=fake_run):
                result = convert_with_applio(
                    source_vocal=source,
                    model_path=model,
                    output_dir=output_dir,
                    options={
                        "applio_dir": applio_dir,
                        "index_path": index,
                    },
                )

            self.assertEqual(len(calls), 1)
            self.assertIn("index_rate=0.0", calls[0])
            self.assertIn("index_path=''", calls[0])
            self.assertFalse(result.metadata["index_fallback_used"])
            self.assertIsNone(result.metadata["effective_index_path"])

    def test_convert_retries_without_index_after_native_crash(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            applio_dir = root / "applio"
            applio_dir.mkdir()
            source = root / "source.wav"
            model = root / "model.pth"
            index = root / "model.index"
            output_dir = root / "out"
            source.write_bytes(b"source")
            model.write_bytes(b"model")
            index.write_bytes(b"index")
            check = ApplioCheck(True, applio_dir, applio_dir / "python", [])
            calls = []

            def fake_run(_root, code, on_output=None):
                calls.append(code)
                if len(calls) == 1:
                    raise ApplioCommandError(["python"], -11, [])
                (output_dir / "converted-applio.wav").write_bytes(b"converted")

            with patch("timbre_shift.rvc_applio_infer.check_applio", return_value=check), \
                patch("timbre_shift.rvc_applio_infer._run_applio_python", side_effect=fake_run):
                result = convert_with_applio(
                    source_vocal=source,
                    model_path=model,
                    output_dir=output_dir,
                    options={
                        "applio_dir": applio_dir,
                        "index_path": index,
                        "index_rate": 0.75,
                    },
                )

            self.assertEqual(len(calls), 2)
            self.assertIn("index_rate=0.75", calls[0])
            self.assertIn(f"index_path={str(index)!r}", calls[0])
            self.assertIn("index_rate=0.0", calls[1])
            self.assertIn("index_path=''", calls[1])
            self.assertEqual(result.converted_vocal_path.read_bytes(), b"converted")
            self.assertEqual(result.device, "cpu")
            self.assertTrue(result.metadata["index_fallback_used"])
            self.assertIsNone(result.metadata["effective_index_path"])


if __name__ == "__main__":
    unittest.main()


def test_train_progress_reports_saved_epoch_without_jumping_to_98_percent():
    from timbre_shift.library_models import VoiceModel, VoiceProfile
    from timbre_shift.rvc_applio_train import train_applio_model
    from timbre_shift.rvc_mlx import RVCDatasetResult

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        applio_dir = root / "applio"
        applio_dir.mkdir()
        dataset = root / "dataset"
        wavs = dataset / "wavs"
        wavs.mkdir(parents=True)
        (wavs / "sample.wav").write_bytes(b"wav")
        check = ApplioCheck(True, applio_dir, applio_dir / "python", [])
        progress_calls = []
        created_model_paths = []

        profile = VoiceProfile(
            id="voice-test",
            name="测试音色",
            description=None,
            source_type="rvc",
            rights_status="confirmed",
            allowed_as_target=True,
            raw_audio_path="",
            ref_8s_path=None,
            ref_16s_path=None,
            ref_20s_path=None,
            ref_25s_path=None,
            preview_mp3_path=None,
            sha256="",
            duration_seconds=None,
            sample_rate=None,
            channels=None,
            source_song_id=None,
            created_at="now",
            updated_at="now",
        )

        def fake_run(_root, code, on_output=None):
            match = re.search(r"run_train_script\('([^']+)'", code)
            assert match, code
            model_name = match.group(1)
            logs = applio_dir / "logs" / model_name
            logs.mkdir(parents=True)
            model_file = logs / f"{model_name}_12e_1860s_best_epoch.pth"
            index_file = logs / f"{model_name}.index"
            if on_output:
                on_output(f"Saved model {model_file.name}")
            model_file.write_bytes(b"model")
            index_file.write_bytes(b"index")

        def fake_create_voice_model_record(**kwargs):
            created_model_paths.append(str(kwargs["model_path"]))
            return VoiceModel(
                id="model-test",
                voice_id=kwargs["voice_id"],
                engine_id=kwargs["engine_id"],
                model_name=kwargs["model_name"],
                model_path=str(kwargs["model_path"]),
                index_path=str(kwargs["index_path"]),
                config_path=None,
                dataset_path=str(kwargs["dataset_path"]),
                training_seconds=kwargs["training_seconds"],
                dataset_seconds=kwargs["dataset_seconds"],
                status="ready",
                created_at="now",
                updated_at="now",
                metadata_json=None,
            )

        with patch("timbre_shift.rvc_applio_train.get_voice_profile", return_value=profile), \
            patch("timbre_shift.rvc_applio_train.check_applio", return_value=check), \
            patch("timbre_shift.rvc_applio_train.prepare_applio_dataset", return_value=RVCDatasetResult(dataset, dataset / "metadata.json", 120.0, 1, 1, ["sample.wav"], [])), \
            patch("timbre_shift.rvc_applio_train._run_applio_python", side_effect=fake_run), \
            patch("timbre_shift.rvc_applio_train.create_voice_model_record", side_effect=fake_create_voice_model_record):
            train_applio_model(
                "voice-test",
                library_dir=root,
                db_path=root / "library.db",
                applio_dir=applio_dir,
                epochs=80,
                progress=lambda step, percent, details=None: progress_calls.append((step, percent, details or {})),
            )

        saved_updates = [call for call in progress_calls if call[2].get("latest_saved_epoch") == 12]
        assert saved_updates
        assert saved_updates[-1][1] < 98
        assert saved_updates[-1][2]["current_epoch"] == 12
        assert saved_updates[-1][2]["total_epochs"] == 80
        assert created_model_paths
        assert "_80e_" in created_model_paths[-1]
