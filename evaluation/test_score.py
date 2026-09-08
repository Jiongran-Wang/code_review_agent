"""Tests of metric behavior using fabricated outputs, not agent results."""
import copy
import unittest

from score import score


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.labels = [
            {"case_id": "a", "issues": [{"issue_id": "a:1", "file": "module.py",
              "line_start": 4, "line_end": 4, "category": "correctness"}]},
            {"case_id": "b", "issues": []},
        ]
        self.reviews = [
            {"case_id": "a", "status": "ok", "findings": [{"finding_id": "f1",
              "file": "module.py", "line": 4, "description": "A defect"}]},
            {"case_id": "b", "status": "ok", "findings": []},
        ]
        self.judgments = [
            {"case_id": "a", "decisions": [{"finding_id": "f1", "gold_issue_id": "a:1"}]},
            {"case_id": "b", "decisions": []},
        ]

    def result(self):
        return score(self.labels, self.reviews, self.judgments)

    def test_perfect(self):
        result = self.result()
        self.assertEqual(result["f1"], 1)
        self.assertEqual(result["localized_recall"], 1)
        self.assertEqual(result["clean_pr_false_alarm_rate"], 0)

    def test_false_positive_on_clean(self):
        self.reviews[1]["findings"] = copy.deepcopy(self.reviews[0]["findings"])
        self.judgments[1]["decisions"] = [{"finding_id": "f1", "gold_issue_id": None}]
        result = self.result()
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 1)
        self.assertEqual(result["clean_pr_false_alarm_rate"], 1)

    def test_failed_buggy_case_counts_as_miss(self):
        self.reviews[0].update(status="error", findings=[])
        self.judgments[0]["decisions"] = []
        result = self.result()
        self.assertEqual(result["false_negatives"], 1)
        self.assertEqual(result["recall"], 0)
        self.assertEqual(result["completion_rate"], 0.5)
        self.assertIsNone(result["precision"])

    def test_failed_clean_case_not_counted_as_correct(self):
        self.reviews[1]["status"] = "error"
        self.assertIsNone(self.result()["clean_pr_false_alarm_rate"])
        self.assertEqual(self.result()["clean_completed"], 0)

    def test_semantic_detection_and_localization_separate(self):
        self.reviews[0]["findings"][0]["line"] = 5
        self.assertEqual(self.result()["recall"], 1)
        self.assertEqual(self.result()["localized_recall"], 0)

    def test_missing_case_rejected(self):
        self.reviews.pop()
        with self.assertRaises(ValueError):
            self.result()

    def test_duplicate_matching_rejected(self):
        extra = dict(self.reviews[0]["findings"][0], finding_id="f2")
        self.reviews[0]["findings"].append(extra)
        self.judgments[0]["decisions"].append({"finding_id": "f2", "gold_issue_id": "a:1"})
        with self.assertRaises(ValueError):
            self.result()

    def test_cross_case_match_rejected(self):
        self.judgments[0]["decisions"][0]["gold_issue_id"] = "b:1"
        with self.assertRaises(ValueError):
            self.result()


if __name__ == "__main__":
    unittest.main()
