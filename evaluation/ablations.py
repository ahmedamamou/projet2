"""
evaluation/ablations.py
4 ablation variants for the AGRI-SEM framework:
  A1 — Without SHACL: full pipeline minus SHACL validation
  A2 — Without unit normalization: full pipeline minus normalizer
  A3 — Without quality scoring: full pipeline but Q(o) always = 1.0
  A4 — Without repair (flag-only): full pipeline but no auto-repair
"""

import time
import copy
import logging

logger = logging.getLogger(__name__)


def ablation_a1_no_shacl(observations: list) -> tuple:
    """
    A1 — Without SHACL: full pipeline minus SHACL validation step.
    Sets f4_plausibility = 1.0 (no validation penalty).
    """
    from pipeline.normalizer import normalize
    from pipeline.repairer import repair
    from pipeline.quality_scorer import score_observation

    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        try:
            normalized = normalize(processed)
            normalized["_f4_plausibility"] = 1.0   # No SHACL → assume plausible
            repaired = repair(normalized)
            scored = score_observation(repaired)
            scored["_ablation"] = "A1_no_shacl"
            result.append(scored)
        except Exception as exc:
            logger.warning("A1 error: %s", exc)
            processed["_ablation"] = "A1_no_shacl"
            processed["_Q"] = 0.5
            result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def ablation_a2_no_unitnorm(observations: list) -> tuple:
    """
    A2 — Without unit normalization: full pipeline minus normalizer.
    Uses raw values, sets f2_unit_confidence = 0.5 (heuristic).
    """
    from pipeline.validator import validate
    from pipeline.repairer import repair
    from pipeline.quality_scorer import score_observation

    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        try:
            # Skip normalization — use raw values
            processed["_unit_confidence"] = 0.5    # heuristic confidence
            processed["_completeness"] = processed.get("_completeness", 1.0)

            report, f1, f4 = validate(processed)
            processed["_f4_plausibility"] = f4
            processed["_completeness"] = f1
            repaired = repair(processed, report)
            scored = score_observation(repaired)
            scored["_ablation"] = "A2_no_unitnorm"
            result.append(scored)
        except Exception as exc:
            logger.warning("A2 error: %s", exc)
            processed["_ablation"] = "A2_no_unitnorm"
            processed["_Q"] = 0.5
            result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def ablation_a3_no_quality(observations: list) -> tuple:
    """
    A3 — Without quality scoring: full pipeline but Q(o) always = 1.0.
    All conforming observations treated equally.
    """
    from pipeline.normalizer import normalize
    from pipeline.validator import validate
    from pipeline.repairer import repair

    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        try:
            normalized = normalize(processed)
            report, f1, f4 = validate(normalized)
            normalized["_f4_plausibility"] = f4
            normalized["_completeness"] = f1
            repaired = repair(normalized, report)
            repaired["_Q"] = 1.0   # No quality scoring → always 1.0
            repaired["_quality_score"] = {"Q": 1.0}
            repaired["_ablation"] = "A3_no_quality"
            result.append(repaired)
        except Exception as exc:
            logger.warning("A3 error: %s", exc)
            processed["_ablation"] = "A3_no_quality"
            processed["_Q"] = 1.0
            result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def ablation_a4_no_repair(observations: list) -> tuple:
    """
    A4 — Without repair (flag-only): full pipeline but anomalies are flagged only, not repaired.
    """
    from pipeline.normalizer import normalize
    from pipeline.validator import validate
    from pipeline.quality_scorer import score_observation

    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        try:
            normalized = normalize(processed)
            report, f1, f4 = validate(normalized)
            normalized["_f4_plausibility"] = f4
            normalized["_completeness"] = f1
            # Flag only — no repair
            normalized["_repairs"] = []
            normalized["_repaired"] = False
            normalized["_flags"] = [
                {"field": v["field"], "type": "shacl_violation", "message": v["message"],
                 "repaired": False}
                for v in report.violations
            ]
            scored = score_observation(normalized)
            scored["_ablation"] = "A4_no_repair"
            result.append(scored)
        except Exception as exc:
            logger.warning("A4 error: %s", exc)
            processed["_ablation"] = "A4_no_repair"
            processed["_Q"] = 0.5
            result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def run_all_ablations(observations: list) -> dict:
    """Run all 4 ablations on the same batch of observations."""
    return {
        "A1_no_shacl":    ablation_a1_no_shacl(observations),
        "A2_no_unitnorm": ablation_a2_no_unitnorm(observations),
        "A3_no_quality":  ablation_a3_no_quality(observations),
        "A4_no_repair":   ablation_a4_no_repair(observations),
    }
