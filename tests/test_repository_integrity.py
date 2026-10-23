"""Offline checks for the reorganized repository (no nuScenes or API needed)."""

import json
import ast
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositoryLayoutTest(unittest.TestCase):
    def test_all_python_sources_parse(self):
        # Executed by CI on Python 3.11 as well as locally. It catches f-string
        # quoting errors that Python 3.12 accepts but Python 3.11 rejects.
        for source in ROOT.rglob("*.py"):
            with self.subTest(path=source.relative_to(ROOT)):
                ast.parse(source.read_text(encoding="utf-8"), filename=str(source))

    def test_offline_evaluation_command_help(self):
        commands = [
            "evaluate_annotation_stages.py", "evaluate_traffic_signs.py",
            "export_val_tokens.py", "build_odd_slices.py",
            "evaluate_detection_slices.py", "compare_to_manuscript.py",
        ]
        for command in commands:
            with self.subTest(script=command):
                result = subprocess.run(
                    [sys.executable, "-B", str(ROOT / "scripts/evaluation" / command), "--help"],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout.lower())

        for relative in (
            "scripts/data_extraction/make_requests_jsonl.py",
            "scripts/batch/submit_initial_batches.py",
        ):
            with self.subTest(script=relative):
                result = subprocess.run(
                    [sys.executable, "-B", str(ROOT / relative), "--help"],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("usage:", result.stdout.lower())

    def test_pipeline_source_and_prompt_exist(self):
        for relative in [
            "prompts/gpt4o_odd_prompt.txt",
            "scripts/data_extraction/make_requests_jsonl.py",
            "scripts/batch/submit_batches.py",
            "scripts/batch/submit_initial_batches.py",
            "scripts/batch/monitor_batches.py",
            "scripts/batch/retrieve_clean_results.py",
            "scripts/processing/preprocess_normalize.py",
            "scripts/processing/semantic_scene_consistency.py",
            "docs/annotation_guidelines.pdf",
        ]:
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_prompt_still_has_location_injection_sentinel(self):
        prompt = (ROOT / "prompts/gpt4o_odd_prompt.txt").read_text()
        self.assertIn("- CAM_FRONT_RIGHT ", prompt)

    def test_public_app_configs_parse(self):
        for filename in ["ui/review_raw/config.json", "ui/review_flags/config.json"]:
            with self.subTest(path=filename):
                settings = json.loads((ROOT / filename).read_text())
                self.assertEqual(settings["last_index"], 0)


if __name__ == "__main__":
    unittest.main()
