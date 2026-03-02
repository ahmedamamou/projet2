"""
generator/payload_generator.py
Generates N realistic payloads × 4 vendor formats with ground truth CSV.
4 vendor formats as specified in the article (section 9):
  Vendor A — Clean JSON: {"deviceId": "sm-01", "ts": "2026-...", "soilMoisture": 23.4, "unit": "%", "plot": "P1"}
  Vendor B — Epoch + fraction: {"id": "node7", "time": 1772273700, "sm": 0.234, "sm_unit": "vwc", "field": "plot-1"}
  Vendor C — Nested + permille: {"meta": {"dev": "A9", "plot": "P1"}, "obs": {"t": "...", "val": 234}, "type": "SOIL_MOIST", "scale": "permille"}
  Vendor D — Compact: {"d": "19", "t": 1772273700, "m": 23, "k": "SM"}
"""

import random
import csv
import os
import uuid
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Realistic agricultural sensor value distributions
BASE_VALUES = {
    "soilMoisture":   (35.0,  8.0,  5.0, 90.0),   # (mean, std, min, max)
    "airTemperature": (22.0,  5.0, -5.0, 45.0),
    "soilTemperature":(18.0,  4.0, -5.0, 45.0),
    "soilPH":         ( 6.8,  0.5,  4.5,  9.0),
    "illuminance":    (50000.0, 20000.0, 0.0, 120000.0),
    "batteryLevel":   (75.0,  15.0, 5.0, 100.0),
    # Legacy fields retained for backward compatibility
    "ph":             ( 6.8,  0.5,  4.5,  9.0),
    "temperature":    (22.0,  5.0, -5.0, 45.0),
    "humidity":       (55.0, 10.0, 10.0,  95.0),
    "moisture":       (35.0,  8.0,  5.0, 90.0),
    "oxygen":         ( 8.0,  1.5,  1.0, 15.0),
    "ammonia":        ( 5.0,  1.5,  0.0,  8.0),
    "turbidity":      (30.0, 10.0,  0.0, 200.0),
}

# Plot definitions (6 plots like a real farm)
PLOTS = ["P1", "P2", "P3", "P4", "P5", "P6"]

# Node to vendor mapping based on node_id % 4 (article spec)
def _get_vendor(node_id: str) -> str:
    try:
        nid = int(''.join(filter(str.isdigit, node_id)) or 0)
        return ["A", "B", "C", "D"][nid % 4]
    except Exception:
        return "A"

NODE_VENDOR_MAP = {
    "node_1": "B",
    "node_2": "C",
    "node_3": "D",
    "node_4": "A",
    "node_5": "B",
    "node_6": "C",
    "node_7": "D",
    "node_8": "A",
}


def _rand_value(field: str, rng: random.Random) -> float:
    mean, std, lo, hi = BASE_VALUES.get(field, (0.0, 1.0, 0.0, 100.0))
    v = rng.gauss(mean, std)
    return round(max(lo, min(hi, v)), 2)


def generate_base_reading(
    node_id: str = "node_4",
    timestamp: Optional[datetime] = None,
    rng: Optional[random.Random] = None,
    plot_id: Optional[str] = None,
) -> dict:
    """Generate a base reading with standardized values."""
    if rng is None:
        rng = random.Random()
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    if plot_id is None:
        # Use deterministic digit-based assignment instead of Python's hash()
        digits = ''.join(filter(str.isdigit, node_id)) or "0"
        plot_id = PLOTS[int(digits[-1]) % len(PLOTS)]

    return {
        "soilMoisture":   _rand_value("soilMoisture", rng),
        "airTemperature": _rand_value("airTemperature", rng),
        "soilTemperature":_rand_value("soilTemperature", rng),
        "soilPH":         _rand_value("soilPH", rng),
        "illuminance":    _rand_value("illuminance", rng),
        "batteryLevel":   _rand_value("batteryLevel", rng),
        # Legacy fields for backward compatibility
        "ph":          _rand_value("ph", rng),
        "temperature": _rand_value("temperature", rng),
        "humidity":    _rand_value("humidity", rng),
        "moisture":    _rand_value("moisture", rng),
        "oxygen":      _rand_value("oxygen", rng),
        "ammonia":     _rand_value("ammonia", rng),
        "turbidity":   _rand_value("turbidity", rng),
        "timestamp":   timestamp.isoformat(),
        "node_id":     node_id,
        "vendor":      NODE_VENDOR_MAP.get(node_id, _get_vendor(node_id)),
        "plot":        plot_id,
    }


def format_vendor_a(reading: dict) -> dict:
    """
    Vendor A — Clean JSON (article spec):
    {"deviceId": "sm-01", "ts": "2026-02-28T10:15:00Z", "soilMoisture": 23.4, "unit": "%", "plot": "P1"}
    """
    return {
        "deviceId":    reading.get("node_id", "sm-01"),
        "ts":          reading.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "soilMoisture": reading.get("soilMoisture", reading.get("moisture", 35.0)),
        "airTemperature": reading.get("airTemperature", reading.get("temperature", 22.0)),
        "soilPH":       reading.get("soilPH", reading.get("ph", 6.8)),
        "batteryLevel": reading.get("batteryLevel", 75.0),
        "unit":         "%",
        "plot":         reading.get("plot", "P1"),
        "_vendor":      "A",
        "_node_id":     reading.get("node_id", "sm-01"),
    }


def format_vendor_b(reading: dict) -> dict:
    """
    Vendor B — Epoch + fraction (article spec):
    {"id": "node7", "time": 1772273700, "sm": 0.234, "sm_unit": "vwc", "field": "plot-1"}
    """
    ts = reading.get("timestamp", datetime.now(timezone.utc).isoformat())
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        epoch = int(dt.timestamp())
    except ValueError:
        epoch = int(time.time())

    moisture = reading.get("soilMoisture", reading.get("moisture", 35.0))
    return {
        "id":      reading.get("node_id", "node7"),
        "time":    epoch,
        "sm":      round(float(moisture) / 100.0, 4),   # fraction
        "sm_unit": "vwc",
        "field":   f"plot-{reading.get('plot', 'P1').replace('P', '')}",
        "_vendor": "B",
        "_node_id": reading.get("node_id", "node7"),
        # Extra fields for full data preservation
        "temp_c":   reading.get("airTemperature", reading.get("temperature", 22.0)),
        "ph":       reading.get("soilPH", reading.get("ph", 6.8)),
        "battery":  reading.get("batteryLevel", 75.0),
    }


def format_vendor_c(reading: dict) -> dict:
    """
    Vendor C — Nested + permille (article spec):
    {"meta": {"dev": "A9", "plot": "P1"}, "obs": {"t": "2026-02-28 10:15:00", "val": 234},
     "type": "SOIL_MOIST", "scale": "permille"}
    """
    ts = reading.get("timestamp", datetime.now(timezone.utc).isoformat())
    ts_fmt = str(ts).replace("T", " ").replace("+00:00", "").replace("Z", "")

    moisture = reading.get("soilMoisture", reading.get("moisture", 35.0))
    return {
        "meta": {
            "dev":  reading.get("node_id", "A9"),
            "plot": reading.get("plot", "P1"),
        },
        "obs": {
            "t":   ts_fmt,
            "val": int(float(moisture) * 10),   # permille
        },
        "type":    "SOIL_MOIST",
        "scale":   "permille",
        "_vendor": "C",
        "_node_id": reading.get("node_id", "A9"),
        # Extra fields
        "airTemperature": reading.get("airTemperature", reading.get("temperature", 22.0)),
        "soilPH":         reading.get("soilPH", reading.get("ph", 6.8)),
        "batteryLevel":   reading.get("batteryLevel", 75.0),
    }


def format_vendor_d(reading: dict) -> dict:
    """
    Vendor D — Compact (article spec):
    {"d": "19", "t": 1772273700, "m": 23, "k": "SM"}
    """
    ts = reading.get("timestamp", datetime.now(timezone.utc).isoformat())
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        epoch = int(dt.timestamp())
    except ValueError:
        epoch = int(time.time())

    moisture = reading.get("soilMoisture", reading.get("moisture", 35.0))
    return {
        "d": reading.get("node_id", "19"),
        "t": epoch,
        "m": int(round(float(moisture))),    # integer percent
        "k": "SM",
        "_vendor": "D",
        "_node_id": reading.get("node_id", "19"),
        # Extra fields
        "temp":    int(round(reading.get("airTemperature", reading.get("temperature", 22.0)))),
        "ph_x10":  int(round(reading.get("soilPH", reading.get("ph", 6.8)) * 10)),
        "batt":    int(round(reading.get("batteryLevel", 75.0))),
    }


VENDOR_FORMATTERS = {
    "A": format_vendor_a,
    "B": format_vendor_b,
    "C": format_vendor_c,
    "D": format_vendor_d,
}


def generate_batch(
    n: int = 100,
    nodes: Optional[list] = None,
    start_time: Optional[datetime] = None,
    interval_seconds: float = 30.0,
    seed: Optional[int] = None,
    apply_vendor_format: bool = True,
) -> list:
    """
    Generate N readings for specified nodes.
    If apply_vendor_format=True, applies the article-spec vendor format.
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

        if apply_vendor_format:
            vendor = reading.get("vendor", "A")
            formatter = VENDOR_FORMATTERS.get(vendor, format_vendor_a)
            formatted = formatter(reading)
            formatted["_batch_idx"] = i
            formatted["_original"] = reading
            readings.append(formatted)
        else:
            readings.append(reading)

    return readings


def save_ground_truth_csv(
    readings: list,
    filepath: str = "results/ground_truth.csv",
) -> str:
    """Save base readings as ground truth CSV."""
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
    fields = ["_batch_idx", "node_id", "vendor", "timestamp", "plot",
              "soilMoisture", "airTemperature", "soilTemperature", "soilPH",
              "illuminance", "batteryLevel",
              "ph", "temperature", "humidity", "moisture", "oxygen", "ammonia", "turbidity"]

    def _extract(r):
        orig = r.get("_original", r)
        row = {f: orig.get(f, r.get(f)) for f in fields}
        # Map vendor format fields back
        if row.get("soilMoisture") is None:
            row["soilMoisture"] = r.get("soilMoisture", r.get("m"))
        if row.get("airTemperature") is None:
            row["airTemperature"] = r.get("airTemperature", r.get("temp_c"))
        return row

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows([_extract(r) for r in readings])

    logger.info("Ground truth saved: %s (%d rows)", filepath, len(readings))
    return filepath


def load_from_cooja(node_ids: Optional[list] = None, timeout: float = 5.0) -> list:
    """Load data in LIVE mode from Cooja nodes."""
    from pipeline.cooja_bridge import COOJA_NODES
    if node_ids is None:
        node_ids = list(COOJA_NODES.keys())

    from pipeline.cooja_bridge import fetch_node
    readings = []
    for node_id in node_ids:
        data = fetch_node(node_id, timeout=timeout)
        if data:
            readings.append(data)
    return readings
