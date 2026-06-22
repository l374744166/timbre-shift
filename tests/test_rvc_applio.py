import unittest
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
