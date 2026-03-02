"""
evaluation/sensitivity.py
Sensitivity analysis for quality score weights w1-w5.
Varies each weight ±20% in 5 steps and analyzes QSR/F1/FP rate robustness.
"""

import logging
import copy
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = [0.20, 0.25, 0.15, 0.25, 0.15]
WEIGHT_NAMES = ["w1_completeness", "w2_unit_confidence", "w3_freshness",
                "w4_plausibility", "w5_reliability"]

# Variation steps: -20%, -10%, 0%, +10%, +20%
VARIATION_STEPS = [-0.20, -0.10, 0.0, 0.10, 0.20]


def _normalize_weights(weights: list) -> list:
    """Normalize weights to sum to 1.0."""
    total = sum(weights)
    if total <= 0:
        return [1.0 / len(weights)] * len(weights)
    return [w / total for w in weights]


def vary_weight(base_weights: list, weight_idx: int, variation: float) -> list:
    """
    Vary a single weight by a relative amount (e.g., +0.10 = +10%),
    then re-normalize all weights to sum to 1.0.
    """
    weights = list(base_weights)
    weights[weight_idx] = weights[weight_idx] * (1.0 + variation)
    weights[weight_idx] = max(0.001, weights[weight_idx])  # avoid zero
    return _normalize_weights(weights)


def compute_metrics_with_weights(
    observations: list,
    weights: list,
    ground_truth_anomalies: Optional[list] = None,
) -> dict:
    """
    Re-compute QSR and F1 with custom weights.
    """
    from pipeline.quality_scorer import compute_quality_score
    from evaluation.metrics import compute_qsr, compute_f1_anomaly

    # Re-score observations with new weights
    rescored = []
    for obs in observations:
        obs_copy = copy.deepcopy(obs)
        qs = compute_quality_score(obs_copy, weights=weights)
        obs_copy["_Q"] = qs["Q"]
        obs_copy["_quality_score"] = qs
        rescored.append(obs_copy)

    qsr = compute_qsr(rescored)
    f1_metric = compute_f1_anomaly(rescored, ground_truth_anomalies)

    # FP rate
    n = len(rescored)
    fp_count = f1_metric.get("fp", 0)
    fp_rate = fp_count / max(n, 1)

    return {
        "qsr_mean": qsr["mean"],
        "qsr_std": qsr["std"],
        "f1": f1_metric["f1"],
        "precision": f1_metric["precision"],
        "recall": f1_metric["recall"],
        "fp_rate": round(fp_rate, 4),
        "weights": weights,
    }


def run_sensitivity_analysis(
    observations: list,
    base_weights: Optional[list] = None,
    ground_truth_anomalies: Optional[list] = None,
) -> list:
    """
    Run sensitivity analysis: vary each weight by ±20% in 5 steps.
    
    Returns list of result dicts with columns:
        weight_name, variation_pct, qsr_mean, f1, fp_rate, weights
    """
    if base_weights is None:
        base_weights = DEFAULT_WEIGHTS

    results = []

    for i, weight_name in enumerate(WEIGHT_NAMES):
        for variation in VARIATION_STEPS:
            varied_weights = vary_weight(base_weights, i, variation)
            metrics = compute_metrics_with_weights(
                observations, varied_weights, ground_truth_anomalies
            )
            results.append({
                "weight_name":  weight_name,
                "weight_idx":   i,
                "variation_pct": int(variation * 100),
                "original_weight": base_weights[i],
                "varied_weight":   varied_weights[i],
                **metrics,
            })

    return results


def analyze_robustness(sensitivity_results: list) -> dict:
    """
    Analyze robustness: compute coefficient of variation (CV) for QSR and F1
    across all weight variations.
    """
    qsr_values = [r["qsr_mean"] for r in sensitivity_results]
    f1_values = [r["f1"] for r in sensitivity_results]
    fp_values = [r["fp_rate"] for r in sensitivity_results]

    def cv(values):
        arr = np.array(values)
        mean = arr.mean()
        return float(arr.std() / mean) if mean > 1e-9 else 0.0

    return {
        "qsr_cv":    round(cv(qsr_values), 4),
        "f1_cv":     round(cv(f1_values), 4),
        "fp_cv":     round(cv(fp_values), 4),
        "qsr_range": (round(min(qsr_values), 4), round(max(qsr_values), 4)),
        "f1_range":  (round(min(f1_values), 4), round(max(f1_values), 4)),
        "robust":    cv(qsr_values) < 0.05 and cv(f1_values) < 0.05,
    }
