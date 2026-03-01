"""
pipeline/repairer.py
Repair automatique des anomalies réparables (clamp aux bornes).
Flag les anomalies non réparables.
"""

import logging

logger = logging.getLogger(__name__)

# Plages valides
VALID_RANGES = {
    "temperature": (-40.0,  60.0),
    "humidity":    (  0.0, 100.0),
    "moisture":    (  0.0, 100.0),
    "ph":          (  0.0,  14.0),
    "oxygen":      (  0.0,  20.0),
    "ammonia":     (  0.0,  10.0),
    "turbidity":   (  0.0, 500.0),
}

# Tolérance de clamp : si la valeur dépasse les bornes de moins de CLAMP_TOLERANCE,
# elle est réparée. Sinon, elle est flagguée comme non réparable.
CLAMP_TOLERANCE = 0.15  # 15% de la plage


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _is_repairable(value: float, low: float, high: float) -> bool:
    """True si la valeur dépasse les bornes de moins de CLAMP_TOLERANCE × plage."""
    plage = high - low
    if plage == 0:
        return False
    return (
        (value < low and (low - value) / plage <= CLAMP_TOLERANCE)
        or (value > high and (value - high) / plage <= CLAMP_TOLERANCE)
    )


def repair(observation: dict, validation_report=None) -> dict:
    """
    Tente de réparer les anomalies de l'observation.

    Returns l'observation avec :
      - _repairs : liste des réparations effectuées
      - _flags   : liste des anomalies non réparables
      - _repaired : bool
    """
    obs = observation.copy()
    repairs = []
    flags = list(obs.get("_flags", []))

    for field, (low, high) in VALID_RANGES.items():
        val = obs.get(field)
        if val is None:
            flags.append({
                "field": field,
                "type": "missing_field",
                "message": f"{field} manquant — non réparable",
                "repaired": False,
            })
            continue

        try:
            v = float(val)
        except (TypeError, ValueError):
            flags.append({
                "field": field,
                "type": "non_numeric",
                "message": f"{field} non numérique : {val}",
                "repaired": False,
            })
            continue

        if v < low or v > high:
            if _is_repairable(v, low, high):
                repaired_val = _clamp(v, low, high)
                obs[field] = repaired_val
                repairs.append({
                    "field": field,
                    "original": v,
                    "repaired": repaired_val,
                    "method": "clamp",
                })
                logger.debug("Repair %s : %.3f → %.3f (clamp)", field, v, repaired_val)
            else:
                flags.append({
                    "field": field,
                    "type": "out_of_range",
                    "message": f"{field}={v} hors plage [{low},{high}] — non réparable",
                    "repaired": False,
                })

    obs["_repairs"] = repairs
    obs["_flags"] = flags
    obs["_repaired"] = len(repairs) > 0
    obs["_has_unrepairable"] = len(flags) > 0

    return obs
