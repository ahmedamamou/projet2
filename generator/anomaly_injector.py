"""
generator/anomaly_injector.py
Injecte des anomalies contrôlées avec taux configurable.
"""

import random
import copy
import time
import logging
import yaml
import os
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_config = None


def _load_config():
    global _config
    if _config is not None:
        return _config
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "anomaly_config.yaml"
    )
    try:
        with open(config_path, "r") as f:
            _config = yaml.safe_load(f)
    except Exception:
        _config = {"anomaly_rate": 0.15, "anomaly_types": {}}
    return _config


def inject_unit_error(obs: dict, rng: random.Random) -> dict:
    """Introduit une erreur d'unité dans l'observation."""
    o = copy.deepcopy(obs)
    field = rng.choice(["temperature", "humidity", "moisture"])
    if field == "temperature" and o.get("temperature") is not None:
        o["temperature"] = o["temperature"] * 1.8 + 32
        o["_anomaly_type"] = "unit_error"
        o["_anomaly_field"] = field
    elif field == "humidity" and o.get("humidity") is not None:
        o["humidity"] = o["humidity"] / 100
        o["_anomaly_type"] = "unit_error"
        o["_anomaly_field"] = field
    elif field == "moisture" and o.get("moisture") is not None:
        o["moisture"] = o["moisture"] * 10
        o["_anomaly_type"] = "unit_error"
        o["_anomaly_field"] = field
    return o


def inject_out_of_range(obs: dict, rng: random.Random) -> dict:
    """Introduit une valeur hors plage."""
    o = copy.deepcopy(obs)
    choices = {
        "ph":      lambda v: v * 2.5,
        "humidity": lambda v: v + 60,
        "temperature": lambda v: v + 80,
        "oxygen":  lambda v: v * 3,
    }
    field = rng.choice(list(choices.keys()))
    if o.get(field) is not None:
        o[field] = choices[field](o[field])
        o["_anomaly_type"] = "out_of_range"
        o["_anomaly_field"] = field
    return o


def inject_timestamp_anomaly(obs: dict, rng: random.Random) -> dict:
    """Introduit une anomalie temporelle."""
    o = copy.deepcopy(obs)
    choice = rng.choice(["future", "past"])
    if choice == "future":
        offset = timedelta(hours=24)
    else:
        offset = timedelta(days=-30)

    try:
        ts = datetime.fromisoformat(
            str(o.get("timestamp", datetime.now(timezone.utc).isoformat()))
            .replace("Z", "+00:00")
        )
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        o["timestamp"] = (ts + offset).isoformat()
    except ValueError:
        o["timestamp"] = (datetime.now(timezone.utc) + offset).isoformat()

    o["_anomaly_type"] = "timestamp_anomaly"
    o["_anomaly_field"] = "timestamp"
    return o


def inject_missing_field(obs: dict, rng: random.Random) -> dict:
    """Supprime un champ obligatoire."""
    o = copy.deepcopy(obs)
    field = rng.choice(["temperature", "humidity", "ph", "oxygen"])
    if field in o:
        del o[field]
    o["_anomaly_type"] = "missing_field"
    o["_anomaly_field"] = field
    return o


def inject_stuck_at(obs: dict, rng: random.Random) -> dict:
    """Simule un capteur bloqué (stuck-at)."""
    o = copy.deepcopy(obs)
    o["_stuck_at"] = True
    o["_anomaly_type"] = "stuck_at"
    return o


INJECTORS = {
    "unit_error":       (inject_unit_error,       0.25),
    "out_of_range":     (inject_out_of_range,      0.30),
    "timestamp_anomaly":(inject_timestamp_anomaly, 0.15),
    "missing_field":    (inject_missing_field,     0.20),
    "stuck_at":         (inject_stuck_at,          0.10),
}


def inject_anomaly(observation: dict, rng: random.Random | None = None) -> dict:
    """
    Injecte une anomalie aléatoire pondérée dans l'observation.
    """
    if rng is None:
        rng = random.Random()

    anomaly_types = list(INJECTORS.keys())
    weights = [INJECTORS[t][1] for t in anomaly_types]
    chosen = rng.choices(anomaly_types, weights=weights, k=1)[0]
    fn = INJECTORS[chosen][0]
    return fn(observation, rng)


def inject_batch(
    observations: list[dict],
    anomaly_rate: float = 0.15,
    seed: int | None = None,
) -> tuple[list[dict], list[int]]:
    """
    Injecte des anomalies dans un batch d'observations.

    Returns (observations_avec_anomalies, indices_anomalies)
    """
    rng = random.Random(seed)
    result = []
    anomaly_indices = []

    for i, obs in enumerate(observations):
        if rng.random() < anomaly_rate:
            injected = inject_anomaly(obs, rng)
            injected["_has_anomaly"] = True
            result.append(injected)
            anomaly_indices.append(i)
        else:
            clean = copy.deepcopy(obs)
            clean["_has_anomaly"] = False
            result.append(clean)

    logger.info(
        "Anomalies injectées : %d/%d (%.1f%%)",
        len(anomaly_indices), len(observations),
        100 * len(anomaly_indices) / max(len(observations), 1),
    )
    return result, anomaly_indices
