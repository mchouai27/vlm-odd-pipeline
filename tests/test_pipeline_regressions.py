"""Focused regressions for normalization and remote-batch state handling.

All batch API interactions use fake sessions: no network or paid calls.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_batch_module():
    fake_requests = types.ModuleType("requests")
    fake_requests.Session = object
    spec = importlib.util.spec_from_file_location(
        "odd_submit_batches_under_test", ROOT / "scripts/batch/submit_batches.py"
    )
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"requests": fake_requests}):
        spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, data, status_code=200):
        self.data = data
        self.text = data if isinstance(data, str) else json.dumps(data)
        self.status_code = status_code

    def json(self):
        return self.data


class FakeSession:
    def __init__(self, status, output):
        self.status = status
        self.output = output

    def get(self, url, timeout):
        if url.endswith("/batch-test"):
            return FakeResponse(self.status)
        if url.endswith("/file-test/content"):
            return FakeResponse(self.output)
        raise AssertionError(f"Unexpected endpoint: {url}")


class BatchRegressionTest(unittest.TestCase):
    def setUp(self):
        self.batch = load_batch_module()

    def test_pending_does_not_count_as_success(self):
        with tempfile.TemporaryDirectory() as folder:
            ids = Path(folder) / "ids.txt"
            ids.write_text("batch-test\n")
            session = FakeSession({"status": "in_progress"}, "")
            done = self.batch.extract_api_results(session, 1, folder, {}, str(ids))
            self.assertFalse(done)
            self.assertFalse((Path(folder) / "iteration_1/invalid_results_iteration_1.jsonl").exists())

    def test_invalid_response_is_kept_for_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            ids = Path(folder) / "ids.txt"
            ids.write_text("batch-test\n")
            good = {"custom_id": "good", "response": {"status_code": 200,
                    "body": {"choices": [{"message": {"content": "{\"ok\": true}"}}]}}}
            failed = {"custom_id": "failed", "response": {"status_code": 500, "body": {}},
                      "error": {"message": "temporary failure"}}
            session = FakeSession({"status": "completed", "output_file_id": "file-test"},
                                  "\n".join(json.dumps(item) for item in (good, failed)))
            done = self.batch.extract_api_results(session, 1, folder, {}, str(ids))
            self.assertTrue(done)
            invalid = (Path(folder) / "iteration_1/invalid_results_iteration_1.jsonl").read_text()
            self.assertIn('"custom_id": "failed"', invalid)
            self.assertNotIn('"custom_id": "good"', invalid)

    def test_failed_batch_stops_instead_of_claiming_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            ids = Path(folder) / "ids.txt"
            ids.write_text("batch-test\n")
            with self.assertRaisesRegex(RuntimeError, "did not complete"):
                self.batch.extract_api_results(
                    FakeSession({"status": "failed"}, ""), 1, folder, {}, str(ids)
                )

    def test_initial_batch_splitting_is_deterministic_and_checks_duplicates(self):
        spec = importlib.util.spec_from_file_location(
            "odd_initial_batch_under_test", ROOT / "scripts/batch/submit_initial_batches.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "requests.jsonl"
            request = lambda key: {"custom_id": key, "method": "POST",
                                   "url": "/v1/chat/completions", "body": {"model": "gpt-4o", "messages": []}}
            source.write_text("\n".join(json.dumps(request(k)) for k in ("a", "b", "c")), encoding="utf-8")
            chunks = module.split_requests(source, Path(folder) / "batches", max_requests=2, max_bytes=1000)
            self.assertEqual(len(chunks), 2)
            self.assertEqual([sum(bool(line.strip()) for line in chunk.read_text().splitlines()) for chunk in chunks], [2, 1])
            source.write_text("\n".join(json.dumps(request(k)) for k in ("a", "a")), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                module.split_requests(source, Path(folder) / "different", 2, 1000)


@unittest.skipUnless(importlib.util.find_spec("pandas"), "pandas not installed")
class PreprocessorRegressionTest(unittest.TestCase):
    def test_nan_to_nan_not_counted_as_modification(self):
        import pandas as pd

        module_path = ROOT / "scripts/processing/preprocess_normalize.py"
        spec = importlib.util.spec_from_file_location("odd_preprocess_under_test", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        before = pd.Series([float("nan"), "No", "Maybe"])
        after = pd.Series([float("nan"), "No", "No"])
        self.assertEqual(module._count_changes(before, after), 1)

    def test_processing_cli_smoke_with_no_modifications(self):
        import pandas as pd

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            src, normalized, flagged, mods = (root / name for name in
                                               ("raw.csv", "normalized.csv", "flagged.csv", "changes.csv"))
            pd.DataFrame({"Scene": ["scene-one"] * 3,
                "EnvironmentalConditions.Illumination.Day": ["Yes"] * 3,
                "EnvironmentalConditions.Illumination.Night": ["No"] * 3}).to_csv(src, index=False)
            for script, args in (
                ("preprocess_normalize.py", ["--input", str(src), "--output", str(normalized),
                                              "--mods-report", str(mods)]),
                ("semantic_scene_consistency.py", ["--input", str(normalized),
                                                   "--output", str(flagged), "--scene-col", "Scene"]),
            ):
                finished = subprocess.run(
                    [sys.executable, "-B", str(ROOT / "scripts/processing" / script), *args],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(finished.returncode, 0, finished.stderr)
            self.assertEqual(len(pd.read_csv(flagged)), 3)
            self.assertEqual(list(pd.read_csv(mods).columns),
                             ["Column", "Modifications", "Percentage (%)"])


class RequestBuilderTest(unittest.TestCase):
    def test_three_camera_request_shape(self):
        spec = importlib.util.spec_from_file_location(
            "odd_request_builder_under_test", ROOT / "scripts/data_extraction/make_requests_jsonl.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        prompt = module.make_prompt("- CAM_FRONT_RIGHT ", "- CAM_FRONT_RIGHT ", "Singapore", "left")
        request = module.build_request("scene__sample", prompt, ["data:image/jpeg;base64,AA=="] * 3)
        self.assertEqual(request["custom_id"], "scene__sample")
        content = request["body"]["messages"][0]["content"]
        self.assertEqual([item["type"] for item in content],
                         ["text", "image_url", "image_url", "image_url"])
        self.assertIn("Singapore", content[0]["text"])


if __name__ == "__main__":
    unittest.main()
