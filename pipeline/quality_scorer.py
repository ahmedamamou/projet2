"""
pipeline/quality_scorer.py
Calcul du Quality Score Q(o) = Σ wᵢ · fᵢ(o) avec 5 facteurs.

Poids par défaut : w = [0.20, 0.25, 0.15, 0.25, 0.15]
  f1 = complétude
  f2 = confiance unité
  f3 = fraîcheur
  f4 = plausibilité
  f5 = fiabilité capteur
"""

import math
import logging
from datetime import datetime, timezone
from collections import deque

logger = logging.getLogger(__name__)

# Poids par défaut
DEFAULT_WEIGHTS = [0.20, 0.25, 0.15, 0.25, 0.15]

# Paramètre fraîcheur
T_MAX = 1800.0  # secondes (30 minutes)

# Fenêtre glissante pour f5
RELIABILITY_WINDOW = 100

# Historique des violations par capteur
_sensor_violation_history: dict[str, deque] = {}


def compute_f1(observation: dict) -> float:
    """f1 : complétude — proportion de champs requis présents."""
    return float(observation.get("_completeness", 1.0))


def compute_f2(observation: dict) -> float:
    """f2 : confiance unité — native=1.0, known_conv=0.8, heuristic=0.5, unknown=0.2."""
    return float(observation.get("_unit_confidence", 0.8))


def compute_f3(observation: dict, t_max: float = T_MAX) -> float:
    """f3 : fraîcheur — max(0, 1 - (t_now - t_obs) / T_max)."""
    ts_str = observation.get("timestamp")
    if not ts_str:
        return 0.0
    try:
        t_obs = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        if t_obs.tzinfo is None:
            t_obs = t_obs.replace(tzinfo=timezone.utc)
        t_now = datetime.now(timezone.utc)
        delta = (t_now - t_obs).total_seconds()
        return max(0.0, 1.0 - delta / t_max)
    except (ValueError, TypeError):
        return 0.5


def compute_f4(observation: dict) -> float:
    """f4 : plausibilité — sigmoïde douce aux bornes (calculée par le validator)."""
    return float(observation.get("_f4_plausibility", 1.0))


def compute_f5(observation: dict, window: int = RELIABILITY_WINDOW) -> float:
    """
    f5 : fiabilité capteur — 1 - (nb_violations_récentes / N_fenêtre).
    Maintient un historique glissant par capteur.
    """
    sensor_id = observation.get("sensor_id", "unknown")
    has_violation = len(observation.get("_flags", [])) > 0 or observation.get("_f4_plausibility", 1.0) <= 0.5

    if sensor_id not in _sensor_violation_history:
        _sensor_violation_history[sensor_id] = deque(maxlen=window)

    history = _sensor_violation_history[sensor_id]
    history.append(1 if has_violation else 0)

    if len(history) == 0:
        return 1.0

    return 1.0 - sum(history) / len(history)


def compute_quality_score(
    observation: dict,
    weights: list[float] | None = None,
    t_max: float = T_MAX,
) -> dict:
    """
    Calcule Q(o) = Σ wᵢ · fᵢ(o).

    Returns un dict avec le score global et les facteurs individuels.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    assert len(weights) == 5, "5 poids requis"
    assert abs(sum(weights) - 1.0) < 1e-6, "Les poids doivent sommer à 1"

    f1 = compute_f1(observation)
    f2 = compute_f2(observation)
    f3 = compute_f3(observation, t_max=t_max)
    f4 = compute_f4(observation)
    f5 = compute_f5(observation)

    factors = [f1, f2, f3, f4, f5]
    q = sum(w * f for w, f in zip(weights, factors))

    return {
        "Q": round(q, 4),
        "f1_completeness": round(f1, 4),
        "f2_unit_confidence": round(f2, 4),
        "f3_freshness": round(f3, 4),
        "f4_plausibility": round(f4, 4),
        "f5_reliability": round(f5, 4),
        "weights": weights,
    }


def score_observation(observation: dict, weights: list[float] | None = None) -> dict:
    """
    Enrichit l'observation avec son quality score.
    """
    obs = observation.copy()
    qs = compute_quality_score(obs, weights=weights)
    obs["_quality_score"] = qs
    obs["_Q"] = qs["Q"]
    return obs
