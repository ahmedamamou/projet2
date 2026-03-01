"""
evaluation/metrics.py
Calcul des métriques : QSR, F1 anomalies, latence E2E, overhead.
"""

import time
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)


def compute_qsr(observations: list[dict]) -> dict:
    """
    Quality Score Rate (QSR) — moyenne et statistiques de Q(o).
    """
    scores = [obs.get("_Q", 0.0) for obs in observations if "_Q" in obs]
    if not scores:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "n": 0}

    arr = np.array(scores)
    return {
        "mean": round(float(arr.mean()), 4),
        "std": round(float(arr.std()), 4),
        "min": round(float(arr.min()), 4),
        "max": round(float(arr.max()), 4),
        "n": len(scores),
        "ci_95": round(float(1.96 * arr.std() / max(np.sqrt(len(scores)), 1)), 4),
    }


def compute_f1_anomaly(
    observations: list[dict],
    ground_truth_anomalies: list[int] | None = None,
) -> dict:
    """
    F1-score de détection d'anomalies.
    ground_truth_anomalies : indices des vraies anomalies
    """
    if ground_truth_anomalies is None:
        ground_truth_anomalies = [
            i for i, obs in enumerate(observations)
            if obs.get("_has_anomaly", False)
        ]

    detected_anomalies = [
        i for i, obs in enumerate(observations)
        if obs.get("_flags") or obs.get("_repairs") or obs.get("_f4_plausibility", 1.0) <= 0.5
    ]

    gt_set = set(ground_truth_anomalies)
    det_set = set(detected_anomalies)

    tp = len(gt_set & det_set)
    fp = len(det_set - gt_set)
    fn = len(gt_set - det_set)

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "n_gt_anomalies": len(gt_set),
        "n_detected": len(det_set),
    }


def compute_latency(start_time: float, end_time: float, n_observations: int) -> dict:
    """
    Calcule les métriques de latence E2E.
    """
    total_ms = (end_time - start_time) * 1000
    per_obs_ms = total_ms / max(n_observations, 1)
    throughput = n_observations / max((end_time - start_time), 1e-9)

    return {
        "total_ms": round(total_ms, 2),
        "per_observation_ms": round(per_obs_ms, 2),
        "throughput_obs_per_s": round(throughput, 2),
        "n_observations": n_observations,
    }


def compute_overhead(
    pipeline_latency_ms: float,
    baseline_latency_ms: float,
) -> dict:
    """
    Calcule le surcoût sémantique par rapport à une baseline.
    """
    if baseline_latency_ms == 0:
        overhead_pct = 0.0
    else:
        overhead_pct = (pipeline_latency_ms - baseline_latency_ms) / baseline_latency_ms * 100

    return {
        "pipeline_ms": round(pipeline_latency_ms, 2),
        "baseline_ms": round(baseline_latency_ms, 2),
        "overhead_ms": round(pipeline_latency_ms - baseline_latency_ms, 2),
        "overhead_pct": round(overhead_pct, 2),
    }


def compute_repair_rate(observations: list[dict]) -> dict:
    """
    Calcule le taux de réparation automatique.
    """
    n_anomalous = sum(1 for obs in observations if obs.get("_has_anomaly") or obs.get("_flags"))
    n_repaired = sum(1 for obs in observations if obs.get("_repaired"))

    rate = n_repaired / max(n_anomalous, 1)
    return {
        "n_anomalous": n_anomalous,
        "n_repaired": n_repaired,
        "repair_rate": round(rate, 4),
    }


def aggregate_metrics(
    observations: list[dict],
    ground_truth_anomalies: list[int] | None = None,
    latency: dict | None = None,
    baseline_latency_ms: float = 1.0,
) -> dict:
    """
    Agrège toutes les métriques pour un run expérimental.
    """
    qsr = compute_qsr(observations)
    f1 = compute_f1_anomaly(observations, ground_truth_anomalies)
    repair = compute_repair_rate(observations)

    result = {
        "qsr": qsr,
        "f1_anomaly": f1,
        "repair": repair,
    }

    if latency:
        result["latency"] = latency
        result["overhead"] = compute_overhead(
            latency.get("total_ms", 0.0), baseline_latency_ms
        )

    return result
