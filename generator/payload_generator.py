"""
generator/payload_generator.py
Génère N payloads réalistes × 4 vendors avec ground truth CSV.
Modes : live (depuis Cooja) et standalone (données synthétiques).
"""

import random
import csv
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Literal

logger = logging.getLogger(__name__)

# Valeurs de base réalistes (issue du format Cooja)
BASE_VALUES = {
    "ph":          (7.0, 0.5,  0.0, 14.0),   # (mean, std, min, max)
    "temperature": (25.0, 3.0, -5.0, 45.0),
    "turbidity":   (30.0, 10.0, 0.0, 200.0),
    "ammonia":     (5.0,  1.5,  0.0,  8.0),
    "oxygen":      (8.0,  1.5,  1.0, 15.0),
    "moisture":    (35.0, 8.0,  5.0, 90.0),
    "humidity":    (55.0, 10.0, 10.0, 95.0),
}

NODE_VENDOR_MAP = {
    "node_2": "A",
    "node_3": "B",
    "node_4": "C",
    "node_5": "D",
    "node_6": "A",
}


def _rand_value(field: str, rng: random.Random) -> float:
    mean, std, lo, hi = BASE_VALUES[field]
    v = rng.gauss(mean, std)
    return round(max(lo, min(hi, v)), 2)


def generate_base_reading(
    node_id: str = "node_2",
    timestamp: datetime | None = None,
    rng: random.Random | None = None,
) -> dict:
    """Génère une lecture de base (valeurs standardisées)."""
    if rng is None:
        rng = random.Random()
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    return {
        "ph":          _rand_value("ph", rng),
        "temperature": _rand_value("temperature", rng),
        "turbidity":   _rand_value("turbidity", rng),
        "ammonia":     _rand_value("ammonia", rng),
        "oxygen":      _rand_value("oxygen", rng),
        "moisture":    _rand_value("moisture", rng),
        "humidity":    _rand_value("humidity", rng),
        "timestamp":   timestamp.isoformat(),
        "node_id":     node_id,
        "vendor":      NODE_VENDOR_MAP.get(node_id, "A"),
    }


def generate_batch(
    n: int = 100,
    nodes: list[str] | None = None,
    start_time: datetime | None = None,
    interval_seconds: float = 30.0,
    seed: int | None = None,
) -> list[dict]:
    """
    Génère N lectures pour les nœuds spécifiés.
    """
    if nodes is None:
        nodes = list(NODE_VENDOR_MAP.keys())
    if start_time is None:
        start_time = datetime.now(timezone.utc)

    rng = random.Random(seed)
    readings = []

    for i in range(n):
        node_id = nodes[i % len(nodes)]
        ts = start_time + timedelta(seconds=i * interval_seconds)
        reading = generate_base_reading(node_id=node_id, timestamp=ts, rng=rng)
        reading["_batch_idx"] = i
        readings.append(reading)

    return readings


def save_ground_truth_csv(
    readings: list[dict],
    filepath: str = "results/ground_truth.csv",
) -> str:
    """
    Sauvegarde les lectures de référence en CSV.
    """
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
    fields = ["_batch_idx", "node_id", "vendor", "timestamp",
              "ph", "temperature", "turbidity", "ammonia",
              "oxygen", "moisture", "humidity"]

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(readings)

    logger.info("Ground truth sauvegardé : %s (%d lignes)", filepath, len(readings))
    return filepath


def load_from_cooja(node_ids: list[str] | None = None, timeout: float = 5.0) -> list[dict]:
    """
    Charge les données en mode LIVE depuis les nœuds Cooja.
    """
    from pipeline.cooja_bridge import fetch_all_nodes, COOJA_NODES
    if node_ids is None:
        node_ids = list(COOJA_NODES.keys())

    from pipeline.cooja_bridge import fetch_node
    readings = []
    for node_id in node_ids:
        data = fetch_node(node_id, timeout=timeout)
        if data:
            readings.append(data)
    return readings
