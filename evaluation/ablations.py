"""
evaluation/ablations.py
4 ablations pour l'analyse d'impact de chaque composant :
  -SHACL      : pipeline sans validation SHACL
  -UnitNorm   : pipeline sans normalisation d'unités
  -QualityScore: pipeline sans quality scoring
  -Repair     : pipeline sans réparation automatique
"""

import time
import copy
import logging

logger = logging.getLogger(__name__)


def run_full_pipeline(observations: list[dict]) -> tuple[list[dict], float]:
    """Pipeline complet (référence pour les ablations)."""
    from pipeline.validator import validate
    from pipeline.repairer import repair
    from pipeline.quality_scorer import score_observation

    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        report, f1, f4 = validate(processed)
        processed["_validation"] = report.to_dict()
        processed["_f4_plausibility"] = f4
        processed["_completeness"] = f1
        processed = repair(processed, report)
        processed = score_observation(processed)
        result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def ablation_no_shacl(observations: list[dict]) -> tuple[list[dict], float]:
    """Ablation -SHACL : saute la validation SHACL."""
    from pipeline.repairer import repair
    from pipeline.quality_scorer import score_observation

    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        processed["_ablation"] = "no_shacl"
        processed["_f4_plausibility"] = 1.0  # pas de validation → plausibilité supposée parfaite
        processed["_completeness"] = processed.get("_completeness", 1.0)
        processed = repair(processed)
        processed = score_observation(processed)
        result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def ablation_no_unitnorm(observations: list[dict]) -> tuple[list[dict], float]:
    """Ablation -UnitNorm : saute la normalisation d'unités."""
    from pipeline.validator import validate
    from pipeline.repairer import repair
    from pipeline.quality_scorer import score_observation

    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        processed["_ablation"] = "no_unitnorm"
        # Confiance unité dégradée car pas de normalisation
        processed["_unit_confidence"] = 0.5
        report, f1, f4 = validate(processed)
        processed["_validation"] = report.to_dict()
        processed["_f4_plausibility"] = f4
        processed["_completeness"] = f1
        processed = repair(processed, report)
        processed = score_observation(processed)
        result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def ablation_no_quality(observations: list[dict]) -> tuple[list[dict], float]:
    """Ablation -QualityScore : saute le quality scoring (Q=1.0 uniforme)."""
    from pipeline.validator import validate
    from pipeline.repairer import repair

    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        processed["_ablation"] = "no_quality"
        report, f1, f4 = validate(processed)
        processed["_validation"] = report.to_dict()
        processed["_f4_plausibility"] = f4
        processed["_completeness"] = f1
        processed = repair(processed, report)
        # Pas de quality scoring → Q uniforme
        processed["_Q"] = 1.0
        processed["_quality_score"] = {"Q": 1.0}
        result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def ablation_no_repair(observations: list[dict]) -> tuple[list[dict], float]:
    """Ablation -Repair : saute la réparation automatique."""
    from pipeline.validator import validate
    from pipeline.quality_scorer import score_observation

    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        processed["_ablation"] = "no_repair"
        report, f1, f4 = validate(processed)
        processed["_validation"] = report.to_dict()
        processed["_f4_plausibility"] = f4
        processed["_completeness"] = f1
        # Pas de réparation → les anomalies restent
        processed["_repairs"] = []
        processed["_repaired"] = False
        processed = score_observation(processed)
        result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def run_all_ablations(
    observations: list[dict],
) -> dict[str, tuple[list[dict], float]]:
    """Lance les 4 ablations + full pipeline sur le même batch."""
    return {
        "full":          run_full_pipeline(observations),
        "no_shacl":      ablation_no_shacl(observations),
        "no_unitnorm":   ablation_no_unitnorm(observations),
        "no_quality":    ablation_no_quality(observations),
        "no_repair":     ablation_no_repair(observations),
    }
