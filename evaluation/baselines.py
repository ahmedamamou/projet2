"""
evaluation/baselines.py
3 baselines de comparaison :
  B1-ETL       : pipeline ETL brut sans sémantique
  B2-RDF-naïf  : RDF sans validation ni quality score
  B3-SHACL-no-Q: SHACL sans quality scoring
"""

import time
import copy
import logging

logger = logging.getLogger(__name__)


def baseline_b1_etl(observations: list[dict]) -> tuple[list[dict], float]:
    """
    B1 - ETL brut : juste normalisation, pas de validation, pas de qualité.
    """
    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        processed["_baseline"] = "B1_ETL"
        processed["_Q"] = 1.0 if not processed.get("_flags") else 0.5
        result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def baseline_b2_rdf_naive(observations: list[dict]) -> tuple[list[dict], float]:
    """
    B2 - RDF naïf : conversion RDF sans validation SHACL ni quality score.
    Simule l'insert direct en RDF sans pipeline de qualité.
    """
    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        processed["_baseline"] = "B2_RDF_naive"
        # Assigne un score qualité uniforme (pas de calcul réel)
        processed["_Q"] = 0.8
        processed["_quality_score"] = {
            "Q": 0.8,
            "f1_completeness": 1.0,
            "f2_unit_confidence": 0.8,
            "f3_freshness": 1.0,
            "f4_plausibility": 0.8,
            "f5_reliability": 0.8,
        }
        result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def baseline_b3_shacl_no_q(observations: list[dict]) -> tuple[list[dict], float]:
    """
    B3 - SHACL sans quality score : validation SHACL mais décision binaire.
    Ignore le quality score pour la décision (seuil binaire SHACL only).
    """
    from pipeline.validator import validate

    t0 = time.perf_counter()
    result = []
    for obs in observations:
        processed = copy.deepcopy(obs)
        processed["_baseline"] = "B3_SHACL_no_Q"
        try:
            report, f1, f4 = validate(processed)
            processed["_validation"] = report.to_dict()
            processed["_f4_plausibility"] = f4
            # Score qualité binaire : valide=1, invalide=0
            processed["_Q"] = 1.0 if report.is_valid() else 0.0
            processed["_quality_score"] = {"Q": processed["_Q"]}
        except Exception as exc:
            logger.warning("B3 validation erreur : %s", exc)
            processed["_Q"] = 0.5
        result.append(processed)
    latency = (time.perf_counter() - t0) * 1000
    return result, latency


def run_all_baselines(
    observations: list[dict],
) -> dict[str, tuple[list[dict], float]]:
    """
    Lance les 3 baselines sur le même batch d'observations.
    """
    return {
        "B1_ETL":       baseline_b1_etl(observations),
        "B2_RDF_naive": baseline_b2_rdf_naive(observations),
        "B3_SHACL_no_Q": baseline_b3_shacl_no_q(observations),
    }
