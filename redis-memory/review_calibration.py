"""ReviewCalibration — Calibration set + drift detection for review gates.

Kocoro-inspired calibration system:
- Maintains a calibration set of 10 papers with known ground-truth quality
- After every N reviews, re-evaluates on the calibration set
- Detects harshness/leniency drift over time
- Alerts when drift exceeds threshold
"""

import json
import statistics
import time
from datetime import datetime, timezone
from typing import Optional


CALIBRATION_SET = [
    {
        "id": "cal-01",
        "title": "Transformer for Few-Shot Fault Diagnosis",
        "ground_truth": {"quality": 7.5, "issues": ["limited ablation", "small dataset"]},
        "expected_verdict": "revise",
    },
    {
        "id": "cal-02",
        "title": "Physics-Informed Neural Network Review",
        "ground_truth": {"quality": 8.0, "issues": []},
        "expected_verdict": "pass",
    },
    {
        "id": "cal-03",
        "title": "Hyperparameter Optimization for Deep Learning",
        "ground_truth": {"quality": 5.0, "issues": ["no novelty", "incomplete comparison"]},
        "expected_verdict": "fail",
    },
    {
        "id": "cal-04",
        "title": "Attention Mechanisms in Time Series",
        "ground_truth": {"quality": 6.5, "issues": ["incremental contribution"]},
        "expected_verdict": "revise",
    },
    {
        "id": "cal-05",
        "title": "Graph Neural Networks for Machinery Prognostics",
        "ground_truth": {"quality": 8.5, "issues": []},
        "expected_verdict": "pass",
    },
    {
        "id": "cal-06",
        "title": "GAN-Based Data Augmentation for Bearing Faults",
        "ground_truth": {"quality": 4.5, "issues": ["flawed evaluation", "missing baseline"]},
        "expected_verdict": "fail",
    },
    {
        "id": "cal-07",
        "title": "Meta-Learning for Rotating Machinery Diagnosis",
        "ground_truth": {"quality": 7.0, "issues": ["computational cost unclear"]},
        "expected_verdict": "revise",
    },
    {
        "id": "cal-08",
        "title": "Wavelet Transform for Vibration Analysis",
        "ground_truth": {"quality": 6.0, "issues": ["outdated methods compared"]},
        "expected_verdict": "revise",
    },
    {
        "id": "cal-09",
        "title": "Contrastive Learning for Fault Classification",
        "ground_truth": {"quality": 8.2, "issues": []},
        "expected_verdict": "pass",
    },
    {
        "id": "cal-10",
        "title": "LSTM for Remaining Useful Life Prediction",
        "ground_truth": {"quality": 3.5, "issues": ["major methodological flaws",
                       "no comparison to SOTA", "evaluation not reproducible"]},
        "expected_verdict": "fail",
    },
]

VERDICT_MAP = {"pass": 2, "revise": 1, "fail": 0}


class ReviewCalibrator:
    """Calibration set evaluator for review gate drift detection.

    Tracks:
    - Harshness drift: reviewer gives lower scores than calibration set
    - Leniency drift: reviewer gives higher scores than calibration set
    - Miss rate: issues present in ground truth but missed by reviewer
    - False positive rate: issues flagged by reviewer but not in ground truth
    """

    def __init__(self):
        self.calibration_set = CALIBRATION_SET
        self.history: list[dict] = []
        self.drift_alerts: list[dict] = []

    def evaluate(self, recent_reviews: list[dict]) -> dict:
        """Compare recent review distribution vs calibration set.

        Args:
            recent_reviews: list of {"verdict": str, "issues": list, "gate_id": int}

        Returns:
            {"drift_detected": bool, "harshness_delta": float, ...}
        """
        scores = []
        for r in recent_reviews:
            v = r.get("verdict", "pass")
            scores.append(VERDICT_MAP.get(v, 1))

        if not scores:
            return {"drift_detected": False, "error": "no reviews"}

        avg_score = statistics.mean(scores) if len(scores) > 1 else scores[0]
        cal_scores = [VERDICT_MAP[c["expected_verdict"]] for c in self.calibration_set]
        cal_avg = statistics.mean(cal_scores)

        drift = avg_score - cal_avg
        drift_detected = abs(drift) > 0.3

        result = {
            "drift_detected": drift_detected,
            "review_avg_score": round(avg_score, 2),
            "calibration_avg_score": round(cal_avg, 2),
            "harshness_delta": round(-drift, 2),
            "leniency_delta": round(drift, 2),
            "reviews_analyzed": len(scores),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if drift_detected:
            direction = "harsh" if drift < 0 else "lenient"
            severity = "high" if abs(drift) > 0.6 else "medium"
            alert = {
                "type": f"{direction}_drift",
                "severity": severity,
                "delta": round(drift, 2),
                "timestamp": result["timestamp"],
            }
            self.drift_alerts.append(alert)
            result["alert"] = alert

        self.history.append(result)
        return result

    def evaluate_single(self, paper_id: str, verdict: str, issues: list[str]) -> dict:
        """Compare a single review against its ground truth."""
        cal_item = next((c for c in self.calibration_set if c["id"] == paper_id), None)
        if not cal_item:
            return {"error": f"paper {paper_id} not in calibration set"}

        gt = cal_item["ground_truth"]
        expected = cal_item["expected_verdict"]

        correct_verdict = verdict == expected

        gt_issues = set(gt.get("issues", []))
        reported_issues = set(issues)

        missed = gt_issues - reported_issues
        false_positives = reported_issues - gt_issues

        miss_rate = len(missed) / max(len(gt_issues), 1)
        fp_rate = len(false_positives) / max(len(reported_issues), 1)

        return {
            "paper_id": paper_id,
            "title": cal_item["title"],
            "correct_verdict": correct_verdict,
            "miss_rate": round(miss_rate, 2),
            "false_positive_rate": round(fp_rate, 2),
            "missed_issues": list(missed),
            "false_positive_issues": list(false_positives),
        }

    def get_history(self, limit: int = 20) -> list[dict]:
        return self.history[-limit:]

    def get_alerts(self, severity: Optional[str] = None) -> list[dict]:
        if severity:
            return [a for a in self.drift_alerts if a.get("severity") == severity]
        return self.drift_alerts
