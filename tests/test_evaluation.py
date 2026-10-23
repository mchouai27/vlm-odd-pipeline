"""Small deterministic, SYNTHETIC unit tests; not manuscript validation data."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/evaluation"))

from build_odd_slices import PAIRS, build, classify
from compare_to_manuscript import compare
from evaluate_annotation_stages import evaluate as evaluate_stages
from evaluate_annotation_stages import per_class_f1
from evaluate_traffic_signs import evaluate as evaluate_signs
from evaluate_traffic_signs import text_jaccard


class AnnotationMetricsTest(unittest.TestCase):
    def test_per_class_f1_uses_valid_categories(self):
        self.assertAlmostEqual(per_class_f1(["No", "No", "Yes"], ["No", "Yes", "Yes"], ["Yes", "No"]),
                               2 / 3)
        self.assertEqual(per_class_f1(["No"], ["No"], ["Yes", "No"]), 0.5)

    def test_stage_agreement_and_missing_classes(self):
        data = [
            {"sample_token": "a", "attribute": "Water", "reference": "No", "V0": "Yes", "V1": "No", "V2": "No", "V3": "No"},
            {"sample_token": "b", "attribute": "Water", "reference": "Yes", "V0": "No", "V1": "Yes", "V2": "Yes", "V3": "Yes"},
        ]
        out = evaluate_stages(data, {"Water": ["No", "Yes"]})
        self.assertEqual(out["macro_f1"]["V0"], 0.0)
        self.assertEqual(out["macro_f1"]["V3"], 1.0)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            evaluate_stages(data + [data[0]], {"Water": ["No", "Yes"]})


class TrafficSignTest(unittest.TestCase):
    def test_confusion_and_manual_additions(self):
        data = [
            {"sample_token": "s", "sign_id": "1", "reference_category": "Regulatory",
             "predicted_category": "Warning", "origin": "manually_added"},
            {"sample_token": "s", "sign_id": "2", "reference_category": "Information",
             "predicted_category": "Information", "origin": "detector_proposal"},
        ]
        out, _ = evaluate_signs(data, None, 0.8)
        self.assertEqual(out["confusion_matrix"], [[0, 1, 0], [0, 0, 0], [0, 0, 1]])
        self.assertEqual(out["classification_accuracy"], 0.5)
        self.assertEqual(out["detection_origin_counts"]["manually_added"], 1)

    def test_text_similarity(self):
        self.assertEqual(text_jaccard("STOP sign", "stop sign", "token-jaccard", 0.8), 1.0)
        self.assertEqual(text_jaccard("turn left", "no parking", "token-jaccard", 0.8), 0.0)
        self.assertTrue(0 <= text_jaccard("parking", "parkng", "fuzzy-jaccard", 0.8) <= 1)


class OddSliceTest(unittest.TestCase):
    config = {key: key for key in ("day", "night", "volume", "crossroad", "lanes",
                                    "pedestrian_crossing", "standing_water", "droplet_cues")}

    def make_row(self, token, *, night=False, high=False):
        return {"sample_token": token, "day": "No" if night else "Yes",
                "night": "Yes" if night else "No", "volume": "High" if high else "Medium",
                "crossroad": "No", "lanes": "2", "pedestrian_crossing": "No",
                "standing_water": "No", "droplet_cues": "No"}

    def test_slices_are_disjoint_complete(self):
        data = [self.make_row("a"), self.make_row("b", night=True, high=True)]
        groups = build(data, ["a", "b"], self.config)
        self.assertEqual(groups["overall"], ["a", "b"])
        self.assertEqual(groups["night_low_illumination"], ["b"])
        for left, right in PAIRS:
            self.assertEqual(len(groups[left]) + len(groups[right]), 2)
            self.assertFalse(set(groups[left]) & set(groups[right]))

    def test_ambiguous_illumination_is_not_guessed(self):
        row = self.make_row("a")
        row["night"] = "Yes"
        with self.assertRaisesRegex(ValueError, "exclusive"):
            classify(row, self.config)


class ManuscriptConsistencyTest(unittest.TestCase):
    def test_reported_sign_totals(self):
        paper = json.loads((ROOT / "configs/manuscript_targets.json").read_text())
        matrix = paper["traffic_sign_confusion"]
        self.assertEqual(len(paper["annotation_per_attribute_f1"]), 21)
        for i, stage in enumerate(("V0", "V1", "V2", "V3")):
            mean = sum(values[i] for values in paper["annotation_per_attribute_f1"].values()) / 21
            self.assertAlmostEqual(mean, paper["annotation_macro_f1"][stage], delta=0.00051)
        self.assertEqual([sum(row) for row in matrix], [4776, 1379, 793])
        self.assertEqual([sum(row[j] for row in matrix) for j in range(3)], [4500, 1494, 954])
        self.assertEqual(sum(matrix[i][i] for i in range(3)), 5899)
        self.assertEqual(sum(map(sum, matrix)), paper["dataset"]["traffic_signs"])
        for left, right in PAIRS:
            counts = paper["expected_slice_counts"]
            self.assertEqual(counts[left] + counts[right], counts["overall"])

    def test_unavailable_runs_are_not_marked_verified(self):
        paper = json.loads((ROOT / "configs/manuscript_targets.json").read_text())
        checks = compare(paper)
        self.assertTrue(checks)
        self.assertTrue(all(row["status"] == "NOT VERIFIED" for row in checks))


if __name__ == "__main__":
    unittest.main()
