"""
pipeline/normalizer.py
Normalise toutes les unités vers un standard commun :
  - fraction (0-1) → % (×100)
  - permille (‰)   → % (÷10)
  - °F → °C         ((v-32)×5/9)
  - epoch ms → ISO8601
  - epoch s  → ISO8601
"""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Confiance unité (f2) selon la source de conversion
UNIT_CONFIDENCE = {
    "native":           1.0,
    "known_conversion": 0.8,
    "heuristic":        0.5,
    "unknown":          0.2,
}

REQUIRED_FIELDS = ["temperature", "humidity", "moisture", "ph", "oxygen", "ammonia", "turbidity"]


def _epoch_to_iso(value, unit="ms") -> str:
    try:
        v = float(value)
        ts = v / 1000 if unit == "ms" else v
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def normalize_vendor_a(payload: dict) -> dict:
    """Vendor A : déjà en %, °C, ISO. Confiance native."""
    result = {
        "humidity":    float(payload.get("humidity_pct", 55.0)),
        "moisture":    float(payload.get("moisture_pct", 35.0)),
        "temperature": float(payload.get("temperature_c", 25.0)),
        "ph":          float(payload.get("ph_value", 7.0)),
        "oxygen":      float(payload.get("oxygen_mgl", 8.0)),
        "ammonia":     float(payload.get("ammonia_mgl", 5.0)),
        "turbidity":   float(payload.get("turbidity_ntu", 30.0)),
        "timestamp":   payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "sensor_id":   payload.get("sensor_id", "unknown"),
        "_vendor":     "A",
        "_unit_confidence": UNIT_CONFIDENCE["native"],
        "_conversions": [],
    }
    return result


def normalize_vendor_b(payload: dict) -> dict:
    """Vendor B : fraction→%, °F→°C, epoch ms→ISO."""
    conversions = []

    hum_raw = float(payload.get("hum", 0.55))
    hum = hum_raw * 100
    conversions.append("humidity: fraction→%")

    moi_raw = float(payload.get("moi", 0.35))
    moi = moi_raw * 100
    conversions.append("moisture: fraction→%")

    temp_f = float(payload.get("temp_f", 77.0))
    temp_c = (temp_f - 32) * 5 / 9
    conversions.append("temperature: °F→°C")

    ts_raw = payload.get("ts", 0)
    ts_iso = _epoch_to_iso(ts_raw, unit="ms")
    conversions.append("timestamp: epoch_ms→ISO")

    result = {
        "humidity":    round(hum, 2),
        "moisture":    round(moi, 2),
        "temperature": round(temp_c, 2),
        "ph":          float(payload.get("ph", 7.0)),
        "oxygen":      float(payload.get("oxy", 8.0)),
        "ammonia":     float(payload.get("amm", 5.0)),
        "turbidity":   float(payload.get("turb", 30.0)),
        "timestamp":   ts_iso,
        "sensor_id":   payload.get("node", "unknown"),
        "_vendor":     "B",
        "_unit_confidence": UNIT_CONFIDENCE["known_conversion"],
        "_conversions": conversions,
    }
    return result


def normalize_vendor_c(payload: dict) -> dict:
    """Vendor C : permille→%, JSON imbriqué aplatit."""
    conversions = []

    env = payload.get("data", {}).get("env", {})
    soil = payload.get("data", {}).get("soil", {})
    water = payload.get("data", {}).get("water", {})
    meta = payload.get("meta", {})

    hum_pm = float(env.get("humidity_pm", 550.0))
    hum = hum_pm / 10
    conversions.append("humidity: permille→%")

    moi_pm = float(soil.get("moisture_pm", 350.0))
    moi = moi_pm / 10
    conversions.append("moisture: permille→%")

    result = {
        "humidity":    round(hum, 2),
        "moisture":    round(moi, 2),
        "temperature": float(env.get("temperature_c", 25.0)),
        "ph":          float(soil.get("ph", 7.0)),
        "oxygen":      float(water.get("oxygen_mgl", 8.0)),
        "ammonia":     float(water.get("ammonia_mgl", 5.0)),
        "turbidity":   float(water.get("turbidity_ntu", 30.0)),
        "timestamp":   meta.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "sensor_id":   meta.get("device", "unknown"),
        "_vendor":     "C",
        "_unit_confidence": UNIT_CONFIDENCE["known_conversion"],
        "_conversions": conversions,
    }
    return result


def normalize_vendor_d(payload: dict) -> dict:
    """Vendor D : clés courtes, epoch s→ISO. Valeurs entières."""
    conversions = []

    ts_raw = payload.get("ts", 0)
    ts_iso = _epoch_to_iso(ts_raw, unit="s")
    conversions.append("timestamp: epoch_s→ISO")

    result = {
        "humidity":    float(payload.get("h", 55)),
        "moisture":    float(payload.get("m", 35)),
        "temperature": float(payload.get("t", 25)),
        "ph":          float(payload.get("p", 7)),
        "oxygen":      float(payload.get("o", 8)),
        "ammonia":     float(payload.get("a", 5)),
        "turbidity":   float(payload.get("tb", 30)),
        "timestamp":   ts_iso,
        "sensor_id":   payload.get("id", "unknown"),
        "_vendor":     "D",
        "_unit_confidence": UNIT_CONFIDENCE["known_conversion"],
        "_conversions": conversions,
    }
    return result


NORMALIZER_MAP = {
    "A": normalize_vendor_a,
    "B": normalize_vendor_b,
    "C": normalize_vendor_c,
    "D": normalize_vendor_d,
}


def normalize(payload: dict) -> dict:
    """
    Normalise un payload selon son vendor (_vendor key).
    """
    vendor = payload.get("_vendor", "A")
    fn = NORMALIZER_MAP.get(vendor, normalize_vendor_a)
    normalized = fn(payload)

    # Calcul f1 : complétude
    present = sum(1 for f in REQUIRED_FIELDS if normalized.get(f) is not None)
    normalized["_completeness"] = present / len(REQUIRED_FIELDS)

    return normalized
