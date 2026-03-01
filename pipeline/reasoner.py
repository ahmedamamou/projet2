"""
pipeline/reasoner.py
Raisonnement quality-aware : calcul Confiance(A), décision pondérée,
résolution de conflits entre sources.

Confiance(A) = Σ Q(o) / |O_A|
Déclencher A ⟺ Confiance(A) ≥ τ_A
"""

import logging
import yaml
import os
from collections import defaultdict

logger = logging.getLogger(__name__)

# Seuils par défaut
DEFAULT_THRESHOLDS = {
    "drought":       0.65,
    "irrigation":    0.70,
    "fertilization": 0.75,
    "frost":         0.80,
    "ph_alert":      0.70,
}

# Conditions de déclenchement par défaut
DEFAULT_CONDITIONS = {
    "drought":       {"moisture": {"max": 25.0}, "humidity": {"max": 30.0}},
    "irrigation":    {"moisture": {"max": 30.0}, "humidity": {"max": 40.0}},
    "fertilization": {"ph": {"min": 5.0, "max": 6.0}, "ammonia": {"max": 2.0}},
    "frost":         {"temperature": {"max": 2.0}},
    "ph_alert":      {"ph": {"min": 7.5}},
}

_loaded_thresholds = None


def _load_thresholds():
    global _loaded_thresholds
    if _loaded_thresholds is not None:
        return _loaded_thresholds

    config_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "thresholds.yaml"
    )
    try:
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)
        dt = cfg.get("decision_thresholds", {})
        _loaded_thresholds = {
            action: dt[action]["threshold"]
            for action in dt
        }
    except Exception:
        _loaded_thresholds = DEFAULT_THRESHOLDS

    return _loaded_thresholds


def compute_confidence(observations: list[dict]) -> float:
    """
    Confiance(A) = moyenne des Q(o) sur les observations.
    """
    if not observations:
        return 0.0
    scores = [obs.get("_Q", 0.0) for obs in observations]
    return sum(scores) / len(scores)


def _check_condition(observation: dict, conditions: dict) -> bool:
    """Vérifie si une observation satisfait les conditions d'une action."""
    for field, bounds in conditions.items():
        val = observation.get(field)
        if val is None:
            return False
        v = float(val)
        if "min" in bounds and v < bounds["min"]:
            return False
        if "max" in bounds and v > bounds["max"]:
            return False
    return True


def decide(observations: list[dict], thresholds: dict | None = None) -> dict:
    """
    Prend des décisions quality-aware basées sur les observations.

    Returns un dict avec les actions déclenchées et les métriques de confiance.
    """
    if thresholds is None:
        thresholds = _load_thresholds()

    if not observations:
        return {
            "actions": [],
            "confidence": 0.0,
            "n_observations": 0,
            "decisions": {},
        }

    confidence = compute_confidence(observations)
    decisions = {}

    for action, tau in thresholds.items():
        conditions = DEFAULT_CONDITIONS.get(action, {})

        # Filtrer les observations satisfaisant les conditions
        qualifying = [
            obs for obs in observations
            if _check_condition(obs, conditions)
        ]

        if not qualifying:
            decisions[action] = {
                "triggered": False,
                "confidence": 0.0,
                "threshold": tau,
                "n_qualifying": 0,
                "reason": "Aucune observation satisfait les conditions",
            }
            continue

        action_confidence = compute_confidence(qualifying)
        triggered = action_confidence >= tau

        decisions[action] = {
            "triggered": triggered,
            "confidence": round(action_confidence, 4),
            "threshold": tau,
            "n_qualifying": len(qualifying),
            "reason": f"Confiance({round(action_confidence, 4)}) {'≥' if triggered else '<'} τ({tau})",
        }

    triggered_actions = [
        action for action, d in decisions.items() if d["triggered"]
    ]

    return {
        "actions": triggered_actions,
        "confidence": round(confidence, 4),
        "n_observations": len(observations),
        "decisions": decisions,
    }


def resolve_conflicts(
    observations_by_vendor: dict[str, list[dict]],
) -> dict:
    """
    Résolution de conflits entre sources vendors.
    Pondère les décisions par la confiance de chaque vendor.
    """
    vendor_decisions = {}
    for vendor, obs in observations_by_vendor.items():
        vendor_decisions[vendor] = {
            "confidence": compute_confidence(obs),
            "n_observations": len(obs),
        }

    # Décision finale : moyenne pondérée par confiance
    total_weight = sum(d["confidence"] for d in vendor_decisions.values())
    if total_weight == 0:
        return {"resolved": False, "reason": "Aucune donnée de qualité"}

    all_obs = []
    for obs_list in observations_by_vendor.values():
        all_obs.extend(obs_list)

    final_decision = decide(all_obs)

    return {
        "resolved": True,
        "vendor_decisions": vendor_decisions,
        "final": final_decision,
        "total_weight": round(total_weight, 4),
    }
